"""
Email Forwarder — Mengirim email yang sudah di-scan ke inbox asli (Gmail/Outlook).

Flow:
  Pipeline Worker → Decision Engine → label CLEAN/WARN/QUARANTINE
  ↓
  Email Forwarder (dipanggil dari worker)
  ↓
  if CLEAN → forward ke Gmail/Outlook via SMTP with TLS
  if WARN  → forward + inject X-Spam-Reason header
  if QUARANTINE → jangan forward (tahan di dashboard)

Konfigurasi via env vars:
  FORWARDER_SMTP_HOST     — SMTP server tujuan (contoh: smtp.gmail.com)
  FORWARDER_SMTP_PORT     — Port SMTP tujuan (587 untuk STARTTLS)
  FORWARDER_SMTP_USER     — Username/email akun pengirim
  FORWARDER_SMTP_PASS     — App password / SMTP password
  FORWARDER_DOMAIN_MAP    — JSON mapping domain tujuan ke akun SMTP
"""

import logging
import os
import re
from email import policy
from email.parser import Parser

import aiosmtplib
from email.utils import getaddresses
from mail_delivery import deliver_direct_mx

logger = logging.getLogger(__name__)

FORWARDER_SMTP_HOST = os.getenv("FORWARDER_SMTP_HOST", "")
FORWARDER_SMTP_PORT = int(os.getenv("FORWARDER_SMTP_PORT", "587"))
FORWARDER_SMTP_USER = os.getenv("FORWARDER_SMTP_USER", "")
FORWARDER_SMTP_PASS = os.getenv("FORWARDER_SMTP_PASS", "")
FORWARDER_FROM = os.getenv("FORWARDER_FROM", "").strip().lower()
FORWARDER_STARTTLS = os.getenv("FORWARDER_STARTTLS", "true").lower() in {"1", "true", "yes", "on"}
FORWARDER_DOMAIN_MAP = os.getenv("FORWARDER_DOMAIN_MAP", "{}")
FORWARDER_DESTINATION_OVERRIDE = os.getenv("FORWARDER_DESTINATION_OVERRIDE", "")
OUTBOUND_SMTP_MODE = os.getenv("OUTBOUND_SMTP_MODE", "relay").strip().lower()

# Header X-Spam untuk email WARN
SPAM_HEADER = "X-Spam-Reason"
SPAM_HEADER_VAL = "CogniMail: Potential spam (score {score:.2f})"

# Regex untuk extract recipient domain
RE_DOMAIN = re.compile(r"@([\w.-]+)")


def _normalize_recipients(values) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    addresses = []
    for _, address in getaddresses([str(value) for value in values if value]):
        clean = address.strip().lower()
        if clean:
            addresses.append(clean)
    if addresses:
        return list(dict.fromkeys(addresses))
    fallback = [str(value).strip().lower() for value in values if str(value).strip()]
    return list(dict.fromkeys(fallback))


def _parse_recipients(raw_email: str, payload_recipients: list) -> list:
    """Extract recipient addresses from raw email or payload."""
    if payload_recipients:
        return _normalize_recipients(payload_recipients)
    # Parse From/To dari raw email
    recipients = []
    for line in raw_email.splitlines():
        if line.lower().startswith("to:"):
            addr = line[3:].strip()
            if addr:
                recipients.append(addr)
    return _normalize_recipients(recipients)


def _prepare_forward_message(
    raw_email: str,
    envelope_from: str,
    recipients: list[str],
    fusion_label: str,
    fused_score: float,
) -> bytes:
    """Rewrite forwarding headers so SPF can align with RFC5322 From.

    Keeping the original external From while using a CogniMail envelope sender
    causes DMARC alignment failures. Reply-To and X-CogniMail-Original-From
    preserve the actual author for replies and auditing.
    """
    message = Parser(policy=policy.SMTP).parsestr(raw_email)
    original_from = str(message.get("From", "")).strip()

    for header in (
        "Return-Path",
        "Delivered-To",
        "Bcc",
        "X-CogniMail-Original-From",
        "X-CogniMail-Forwarded-By",
        SPAM_HEADER,
    ):
        while header in message:
            del message[header]
    for header in ("To", "Cc"):
        while header in message:
            del message[header]

    if "From" in message:
        message.replace_header("From", envelope_from)
    else:
        message["From"] = envelope_from
    message["To"] = ", ".join(recipients)
    if original_from:
        if "Reply-To" not in message:
            message["Reply-To"] = original_from
        message["X-CogniMail-Original-From"] = original_from
    message["X-CogniMail-Forwarded-By"] = envelope_from
    if fusion_label == "WARN":
        message[SPAM_HEADER] = SPAM_HEADER_VAL.format(score=fused_score)
    return message.as_bytes(policy=policy.SMTP)


async def forward_email(raw_email: str, fusion_label: str, fused_score: float,
                         payload: dict) -> bool:
    """
    Forward email ke recipient asli via SMTP.
    
    Args:
        raw_email: Raw email content
        fusion_label: CLEAN / WARN / QUARANTINE
        fused_score: Fusion score 0.0-1.0
        payload: Original payload dari Redis queue (berisi sender, recipients, dll)
    
    Returns:
        True jika sukses forward, False jika tidak
    """
    # QUARANTINE → jangan forward
    if fusion_label == "QUARANTINE":
        return False

    # Cek konfigurasi forwarder
    if OUTBOUND_SMTP_MODE not in {"direct", "relay"}:
        logger.error("Invalid OUTBOUND_SMTP_MODE=%r", OUTBOUND_SMTP_MODE)
        return False
    if OUTBOUND_SMTP_MODE == "relay" and not FORWARDER_SMTP_HOST:
        logger.warning("FORWARDER_SMTP_HOST not set — skipping forward")
        return False

    # Parse recipients. Payload recipients are explicit targets from mailbox
    # forwarder settings and must not be replaced by the legacy override.
    payload_recipients = payload.get("recipients", [])
    if payload_recipients:
        recipients = _normalize_recipients(payload_recipients)
    elif FORWARDER_DESTINATION_OVERRIDE:
        recipients = _normalize_recipients([FORWARDER_DESTINATION_OVERRIDE])
    else:
        recipients = _parse_recipients(raw_email, payload_recipients)
    if not recipients:
        logger.warning("No recipients found — cannot forward")
        return False

    # Forward via direct MX delivery or an authenticated relay.
    try:
        envelope_from = (
            str(payload.get("forward_from") or "").strip().lower()
            or FORWARDER_FROM
        )
        if not envelope_from or "@" not in envelope_from:
            logger.error("Forward sender mailbox is missing or invalid")
            return False
        email_to_send = _prepare_forward_message(
            raw_email,
            envelope_from,
            recipients,
            fusion_label,
            fused_score,
        )
        if OUTBOUND_SMTP_MODE == "direct":
            delivered = await deliver_direct_mx(
                email_to_send,
                envelope_from,
                recipients,
                helo_hostname=os.getenv("OUTBOUND_HELO_HOSTNAME", "").strip() or None,
            )
            logger.info(
                "Forwarded %s directly to MX %s (label=%s, score=%.2f)",
                payload.get("email_id", "?"), delivered, fusion_label, fused_score,
            )
            return True

        async with aiosmtplib.SMTP(
            hostname=FORWARDER_SMTP_HOST,
            port=FORWARDER_SMTP_PORT,
            use_tls=FORWARDER_SMTP_PORT == 465,
        ) as smtp:
            if FORWARDER_SMTP_PORT != 465 and FORWARDER_STARTTLS:
                await smtp.starttls()
            if FORWARDER_SMTP_USER and FORWARDER_SMTP_PASS:
                await smtp.login(FORWARDER_SMTP_USER, FORWARDER_SMTP_PASS)

            for recipient in recipients:
                await smtp.sendmail(
                    envelope_from,
                    [recipient],
                    email_to_send,
                )
                logger.info("Forwarded %s to %s (label=%s, score=%.2f)",
                            payload.get("email_id", "?"), recipient,
                            fusion_label, fused_score)
        return True
    except Exception as e:
        logger.error("Forward failed: %s", e)
        return False

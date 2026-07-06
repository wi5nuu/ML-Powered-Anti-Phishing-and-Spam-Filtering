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

import asyncio, json, logging, os, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import policy
from email.parser import BytesParser

import aiosmtplib

logger = logging.getLogger(__name__)

FORWARDER_SMTP_HOST = os.getenv("FORWARDER_SMTP_HOST", "")
FORWARDER_SMTP_PORT = int(os.getenv("FORWARDER_SMTP_PORT", "587"))
FORWARDER_SMTP_USER = os.getenv("FORWARDER_SMTP_USER", "")
FORWARDER_SMTP_PASS = os.getenv("FORWARDER_SMTP_PASS", "")
FORWARDER_FROM      = os.getenv("FORWARDER_FROM", "cognimail@lodaya.id")
FORWARDER_STARTTLS = os.getenv("FORWARDER_STARTTLS", "true").lower() in {"1", "true", "yes", "on"}
FORWARDER_DOMAIN_MAP = os.getenv("FORWARDER_DOMAIN_MAP", "{}")
FORWARDER_DESTINATION_OVERRIDE = os.getenv("FORWARDER_DESTINATION_OVERRIDE", "")

# Header X-Spam untuk email WARN
SPAM_HEADER = "X-Spam-Reason"
SPAM_HEADER_VAL = "CogniMail: Potential spam (score {score:.2f})"

# Regex untuk extract recipient domain
RE_DOMAIN = re.compile(r"@([\w.-]+)")


def _parse_recipients(raw_email: str, payload_recipients: list) -> list:
    """Extract recipient addresses from raw email or payload."""
    if payload_recipients:
        return payload_recipients
    # Parse From/To dari raw email
    recipients = []
    for line in raw_email.splitlines():
        if line.lower().startswith("to:"):
            addr = line[3:].strip()
            if addr:
                recipients.append(addr)
    return recipients


def _inject_header(raw_email: str, header_name: str, header_val: str) -> str:
    """Inject custom header ke raw email sebelum forward."""
    lines = raw_email.splitlines(keepends=True)
    # Cari baris kosong pertama (pisah header dan body)
    for i, line in enumerate(lines):
        if line.strip() == "":
            # Inject header sebelum baris kosong
            lines.insert(i, f"{header_name}: {header_val}\r\n")
            break
    return "".join(lines)


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
    if not FORWARDER_SMTP_HOST:
        logger.warning("FORWARDER_SMTP_HOST not set — skipping forward")
        return False

    # Parse recipients. Payload recipients are explicit targets from mailbox
    # forwarder settings and must not be replaced by the legacy override.
    payload_recipients = payload.get("recipients", [])
    if payload_recipients:
        recipients = payload_recipients
    elif FORWARDER_DESTINATION_OVERRIDE:
        recipients = [FORWARDER_DESTINATION_OVERRIDE]
    else:
        recipients = _parse_recipients(raw_email, payload_recipients)
    if not recipients:
        logger.warning("No recipients found — cannot forward")
        return False

    # Inject header untuk WARN
    email_to_send = raw_email
    if fusion_label == "WARN":
        email_to_send = _inject_header(
            raw_email, SPAM_HEADER,
            SPAM_HEADER_VAL.format(score=fused_score)
        )

    # Forward via SMTP
    try:
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
                    FORWARDER_FROM,
                    [recipient],
                    email_to_send.encode("utf-8", errors="replace"),
                )
                logger.info("Forwarded %s to %s (label=%s, score=%.2f)",
                            payload.get("email_id", "?"), recipient,
                            fusion_label, fused_score)
        return True
    except Exception as e:
        logger.error("Forward failed: %s", e)
        return False

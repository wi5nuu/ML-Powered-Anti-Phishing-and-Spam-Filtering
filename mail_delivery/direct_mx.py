"""Direct-to-MX SMTP delivery.

This module turns CogniMail into a basic outbound MTA: recipient MX records are
resolved and messages are delivered to those servers over SMTP port 25.  It is
shared by the dashboard send/reply endpoint and the pipeline forwarder.
"""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from email import policy
from email.message import Message

import aiosmtplib
import dns.exception
import dns.resolver


class DirectDeliveryError(RuntimeError):
    """Raised when one or more recipient domains reject direct delivery."""

    def __init__(self, failures: dict[str, str]):
        self.failures = failures
        detail = "; ".join(f"{domain}: {reason}" for domain, reason in failures.items())
        super().__init__(f"Pengiriman SMTP langsung gagal ({detail})")


def _message_bytes(message: Message | bytes | str) -> bytes:
    if isinstance(message, bytes):
        return message
    if isinstance(message, str):
        return message.encode("utf-8", errors="replace")
    return message.as_bytes(policy=policy.SMTP)


def _recipient_domain(recipient: str) -> str:
    clean = (recipient or "").strip().lower()
    if "@" not in clean:
        raise ValueError(f"Alamat penerima tidak valid: {recipient}")
    return clean.rsplit("@", 1)[1].encode("idna").decode("ascii")


def _resolve_mx_sync(domain: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.timeout = float(os.getenv("OUTBOUND_DNS_TIMEOUT", "5"))
    resolver.lifetime = float(os.getenv("OUTBOUND_DNS_LIFETIME", "10"))
    try:
        answers = resolver.resolve(domain, "MX")
        records = sorted(
            (int(answer.preference), str(answer.exchange).rstrip("."))
            for answer in answers
        )
        if any(not host for _, host in records):
            raise ValueError(f"Domain {domain} menyatakan tidak menerima email (Null MX)")
        return [host for _, host in records]
    except dns.resolver.NoAnswer:
        # RFC 5321 fallback: when no MX exists, deliver to the domain itself if
        # it has an address record.
        resolver.resolve(domain, "A")
        return [domain]


async def _resolve_mx(domain: str) -> list[str]:
    return await asyncio.to_thread(_resolve_mx_sync, domain)


async def deliver_direct_mx(
    message: Message | bytes | str,
    envelope_from: str,
    recipients: list[str],
    *,
    helo_hostname: str | None = None,
) -> dict[str, str]:
    """Deliver a message directly to every recipient domain's MX server.

    Returns a mapping from recipient domain to the MX host that accepted the
    message. Raises :class:`DirectDeliveryError` if any domain fails after all
    of its MX hosts have been attempted.
    """

    if not envelope_from or "@" not in envelope_from:
        raise ValueError("Envelope sender outbound tidak valid")

    grouped: dict[str, list[str]] = defaultdict(list)
    for recipient in recipients:
        grouped[_recipient_domain(recipient)].append(recipient.strip().lower())
    if not grouped:
        raise ValueError("Penerima outbound tidak tersedia")

    raw_message = _message_bytes(message)
    helo = (
        helo_hostname
        or os.getenv("OUTBOUND_HELO_HOSTNAME")
        or os.getenv("SMTP_DOMAIN")
        or os.getenv("HOSTNAME", "")
        or "mail.cognimail.local"
    ).strip()
    timeout = float(os.getenv("OUTBOUND_SMTP_TIMEOUT", "30"))
    delivered: dict[str, str] = {}
    failures: dict[str, str] = {}

    for domain, domain_recipients in grouped.items():
        try:
            mx_hosts = await _resolve_mx(domain)
        except (dns.exception.DNSException, ValueError, OSError) as exc:
            failures[domain] = f"MX tidak dapat ditemukan: {exc}"
            continue

        last_error = "tidak ada MX yang dapat dihubungi"
        for mx_host in mx_hosts:
            try:
                async with aiosmtplib.SMTP(
                    hostname=mx_host,
                    port=25,
                    timeout=timeout,
                    local_hostname=helo,
                    use_tls=False,
                    start_tls=None,
                ) as smtp:
                    await smtp.sendmail(envelope_from, domain_recipients, raw_message)
                delivered[domain] = mx_host
                break
            except Exception as exc:  # Try the next MX before failing a domain.
                last_error = f"{mx_host}: {exc}"
        else:
            failures[domain] = last_error

    if failures:
        raise DirectDeliveryError(failures)
    return delivered

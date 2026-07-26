"""DKIM signing for outbound CogniMail messages."""

from __future__ import annotations

import base64
import os
from email import policy
from email.message import Message
from pathlib import Path


class DkimConfigurationError(RuntimeError):
    """Raised when DKIM is required but cannot be used safely."""


def _message_bytes(message: Message | bytes | str) -> bytes:
    if isinstance(message, bytes):
        return message
    if isinstance(message, str):
        return message.encode("utf-8", errors="replace")
    return message.as_bytes(policy=policy.SMTP)


def _private_key() -> bytes | None:
    encoded = os.getenv("OUTBOUND_DKIM_PRIVATE_KEY_B64", "").strip()
    if encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise DkimConfigurationError("OUTBOUND_DKIM_PRIVATE_KEY_B64 tidak valid") from exc

    inline = os.getenv("OUTBOUND_DKIM_PRIVATE_KEY", "").strip()
    if inline:
        return inline.replace("\\n", "\n").encode("utf-8")

    key_file = os.getenv("OUTBOUND_DKIM_PRIVATE_KEY_FILE", "").strip()
    if key_file:
        path = Path(key_file)
        if not path.is_file():
            raise DkimConfigurationError(f"Private key DKIM tidak ditemukan: {key_file}")
        return path.read_bytes()
    return None


def sign_outbound_message(
    message: Message | bytes | str,
    sender: str,
) -> bytes:
    """Return RFC 5322 bytes, signed when outbound DKIM is configured."""
    raw = _message_bytes(message)
    required = os.getenv("OUTBOUND_DKIM_REQUIRED", "false").lower() in {
        "1", "true", "yes", "on",
    }
    key = _private_key()
    if not key:
        if required:
            raise DkimConfigurationError(
                "DKIM diwajibkan tetapi private key outbound belum dikonfigurasi"
            )
        return raw

    domain = os.getenv("OUTBOUND_DKIM_DOMAIN", "").strip().lower()
    selector = os.getenv("OUTBOUND_DKIM_SELECTOR", "").strip()
    sender_domain = sender.rsplit("@", 1)[-1].strip().lower() if "@" in sender else ""
    if not domain or not selector:
        raise DkimConfigurationError("OUTBOUND_DKIM_DOMAIN dan OUTBOUND_DKIM_SELECTOR wajib diisi")
    if sender_domain != domain and not sender_domain.endswith(f".{domain}"):
        raise DkimConfigurationError(
            f"Domain From {sender_domain or '-'} tidak selaras dengan domain DKIM {domain}"
        )

    try:
        import dkim

        signature = dkim.sign(
            raw,
            selector=selector.encode("ascii"),
            domain=domain.encode("idna"),
            privkey=key,
            canonicalize=(b"relaxed", b"relaxed"),
            signature_algorithm=b"rsa-sha256",
            include_headers=[
                b"from", b"to", b"subject", b"date", b"message-id",
                b"reply-to", b"in-reply-to", b"references", b"mime-version",
                b"content-type",
            ],
        )
    except DkimConfigurationError:
        raise
    except Exception as exc:
        raise DkimConfigurationError(f"Gagal menandatangani email dengan DKIM: {exc}") from exc
    return signature + raw

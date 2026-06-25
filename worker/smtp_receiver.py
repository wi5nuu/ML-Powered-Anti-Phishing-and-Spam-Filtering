"""
SMTP Receiver — Menerima email asli dari internet via SMTP (port 25).

Production flow:
  Pengirim → DNS MX Record → Server:25 (SMTP Receiver) → Redis Queue → Pipeline → Forward ke Inbox

Wajib di-deploy sebagai service yang listen di port 25 (root privilege).
Untuk development/testing bisa pakai port lain (misal 1025).
"""

import asyncio, hashlib, json, logging, os
from datetime import datetime, timezone

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP

import redis.asyncio as aio_redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smtp_receiver")

REDIS_URL      = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME     = os.getenv("REDIS_QUEUE_NAME", "email_pipeline")
SMTP_HOST      = os.getenv("SMTP_HOST", "0.0.0.0")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "25"))  # 25 = production, 1025 = testing
SMTP_DOMAIN    = os.getenv("SMTP_DOMAIN", "mail.lodaya.id")


class EmailReceiverHandler:
    """Handle incoming SMTP connections — satu email per koneksi."""

    async def handle_DATA(self, server: SMTP, session, envelope):
        """Dipanggil saat seluruh email sudah diterima via SMTP."""
        raw_email = envelope.content.decode("utf-8", errors="replace")
        email_id = hashlib.sha256(raw_email.encode()).hexdigest()[:16]

        # Parse recipient
        recipients = [str(rcpt) for rcpt in envelope.rcpt_tos]
        logger.info("Received email from=%s to=%s id=%s size=%d",
                     envelope.mail_from, recipients, email_id, len(raw_email))

        # Push to Redis queue
        try:
            r = await aio_redis.from_url(REDIS_URL)
            payload = {
                "email_id": email_id,
                "raw_email": raw_email,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "raw_hash": email_id,
                "sender": envelope.mail_from or "",
                "recipients": recipients,
            }
            await r.rpush(QUEUE_NAME, json.dumps(payload))
            await r.aclose()
            logger.info("Queued email_id=%s to %s", email_id, QUEUE_NAME)
            return "250 OK: Queued for processing"
        except Exception as e:
            logger.error("Redis error: %s", e)
            return "451 Requested action aborted: local error in processing"


async def run_smtp_receiver():
    """Start SMTP server."""
    handler = EmailReceiverHandler()
    controller = Controller(
        handler,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        server_hostname=SMTP_DOMAIN,
    )
    controller.start()
    logger.info("SMTP Receiver listening on %s:%d (%s)", SMTP_HOST, SMTP_PORT, SMTP_DOMAIN)

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        controller.stop()
        logger.info("SMTP Receiver stopped")


if __name__ == "__main__":
    asyncio.run(run_smtp_receiver())

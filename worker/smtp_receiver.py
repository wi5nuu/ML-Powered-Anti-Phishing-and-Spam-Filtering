import asyncio
import hashlib
import json
import logging
import os
import ssl
from datetime import datetime, timezone

import redis.asyncio as aio_redis
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database.models import AdminMailbox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smtp_receiver")

REDIS_URL       = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME      = os.getenv("REDIS_QUEUE_NAME", "email_pipeline")
SMTP_HOST       = os.getenv("SMTP_HOST", "0.0.0.0")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "25"))
SMTP_DOMAIN     = os.getenv("SMTP_DOMAIN", "mail.example.com")
MAX_MESSAGE_BYTES = int(os.getenv("MAX_MESSAGE_BYTES", str(25 * 1024 * 1024)))

# STARTTLS config — enable when TLS cert/key paths are provided
SMTP_TLS_CERT   = os.getenv("SMTP_TLS_CERT", "")   # e.g. /certs/fullchain.pem
SMTP_TLS_KEY    = os.getenv("SMTP_TLS_KEY", "")    # e.g. /certs/privkey.pem
SMTP_REQUIRE_TLS = os.getenv("SMTP_REQUIRE_TLS", "false").lower() == "true"

# Maximum connections allowed per IP to mitigate abuse
MAX_CONNECTIONS_PER_IP = int(os.getenv("SMTP_MAX_CONN_PER_IP", "10"))

ACCEPTED_MAIL_DOMAINS = {
    domain.strip().lower()
    for domain in os.getenv(
        "ACCEPTED_MAIL_DOMAINS",
        os.getenv("VITE_MAIL_DOMAIN", "zenime.my.id"),
    ).split(",")
    if domain.strip()
}

# ── Shared Redis connection pool ───────────────────────────────────────────────
_redis_pool: aio_redis.Redis | None = None


def _get_redis() -> aio_redis.Redis:
    """Return the shared Redis client, creating it on first call."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aio_redis.from_url(REDIS_URL, decode_responses=False)
    return _redis_pool


# ── Lazy DB engine ─────────────────────────────────────────────────────────────
_db_engine = None
_DbSession = None


def _get_db_session():
    """Return (engine, session_factory), creating them on first call."""
    global _db_engine, _DbSession
    if _DbSession is None:
        db_url = os.getenv("WORKER_DB_URL") or os.getenv("DB_ASYNC_URL") or os.getenv("DB_URL")
        if not db_url:
            raise RuntimeError(
                "WORKER_DB_URL tidak ditemukan. "
                "Set env var WORKER_DB_URL dengan PostgreSQL async URL. "
                "Contoh: postgresql+asyncpg://cogniuser:password@postgres:5432/cognimail"
            )
        if "sqlite" in db_url.lower():
            raise RuntimeError(
                "SQLite tidak didukung. "
                "Gunakan: postgresql+asyncpg://cogniuser:password@postgres:5432/cognimail"
            )
        _db_engine = create_async_engine(db_url, pool_pre_ping=True)
        _DbSession = async_sessionmaker(_db_engine, expire_on_commit=False)
    return _db_engine, _DbSession


# ── Per-IP connection rate limiting ───────────────────────────────────────────
_ip_connection_count: dict[str, int] = {}


def _ip_connect(ip: str) -> bool:
    """Track connection; return False if limit exceeded."""
    count = _ip_connection_count.get(ip, 0)
    if count >= MAX_CONNECTIONS_PER_IP:
        logger.warning("SMTP connection limit exceeded for IP=%s (count=%d)", ip, count)
        return False
    _ip_connection_count[ip] = count + 1
    return True


def _ip_disconnect(ip: str) -> None:
    """Decrement connection count for IP."""
    count = _ip_connection_count.get(ip, 0)
    if count > 1:
        _ip_connection_count[ip] = count - 1
    else:
        _ip_connection_count.pop(ip, None)


async def mailbox_exists(address: str) -> bool:
    _, DbSession = _get_db_session()
    async with DbSession() as db:
        result = await db.execute(
            select(AdminMailbox.id).where(
                func.lower(AdminMailbox.email) == address.lower(),
                AdminMailbox.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None


class EmailReceiverHandler:
    async def handle_EHLO(self, server: "SMTP", session, envelope, hostname):
        """Announce STARTTLS capability if cert is configured."""
        session.host_name = hostname
        return "250-{}\r\n250 STARTTLS".format(SMTP_DOMAIN)

    async def handle_RCPT(self, server: "SMTP", session, envelope, address, rcpt_options):
        # SECURITY: Reject if TLS required but not active
        if SMTP_REQUIRE_TLS and not getattr(session, "ssl", None):
            return "530 5.7.0 Must issue a STARTTLS command first"

        normalized = str(address or "").strip().lower()
        domain = normalized.rsplit("@", 1)[-1] if "@" in normalized else ""
        if not normalized or domain not in ACCEPTED_MAIL_DOMAINS:
            logger.warning("Rejected non-local SMTP recipient=%s peer=%s", normalized, session.peer)
            return "550 5.7.1 Relay access denied"
        try:
            if not await mailbox_exists(normalized):
                logger.info("Rejected unknown SMTP mailbox=%s peer=%s", normalized, session.peer)
                return "550 5.1.1 Mailbox does not exist"
        except Exception as exc:
            logger.error("Mailbox lookup failed for %s: %s", normalized, exc)
            return "451 4.3.0 Temporary database failure"
        envelope.rcpt_tos.append(normalized)
        return "250 2.1.5 Recipient OK"

    async def handle_DATA(self, server: "SMTP", session, envelope):
        raw_email = envelope.content.decode("utf-8", errors="replace")
        email_id = hashlib.sha256(raw_email.encode()).hexdigest()[:16]
        recipients = [str(rcpt) for rcpt in envelope.rcpt_tos]
        peer_ip = session.peer[0] if session.peer else "unknown"

        logger.info(
            "Received email from=%s to=%s id=%s size=%d peer=%s tls=%s",
            envelope.mail_from,
            recipients,
            email_id,
            len(raw_email),
            peer_ip,
            bool(getattr(session, "ssl", None)),
        )

        try:
            r = _get_redis()
            payload = {
                "email_id": email_id,
                "raw_email": raw_email,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "raw_hash": email_id,
                "sender": envelope.mail_from or "",
                "recipients": recipients,
            }
            await r.rpush(QUEUE_NAME, json.dumps(payload))
            logger.info("Queued email_id=%s to %s", email_id, QUEUE_NAME)
            return "250 OK: Queued for processing"
        except Exception as exc:
            logger.error("Redis error: %s", exc)
            return "451 Requested action aborted: local error in processing"


def _build_tls_context() -> ssl.SSLContext | None:
    """Build STARTTLS context if cert/key env vars are set."""
    if not SMTP_TLS_CERT or not SMTP_TLS_KEY:
        return None
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=SMTP_TLS_CERT, keyfile=SMTP_TLS_KEY)
        # Disable old TLS versions (< 1.2) for security
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:!aNULL:!eNULL:!RC4:!3DES")
        logger.info("STARTTLS enabled with cert=%s", SMTP_TLS_CERT)
        return ctx
    except Exception as exc:
        logger.error("Failed to load TLS cert/key: %s — STARTTLS disabled", exc)
        return None


async def run_smtp_receiver():
    handler = EmailReceiverHandler()
    tls_context = _build_tls_context()

    controller_kwargs: dict = {
        "hostname": SMTP_HOST,
        "port": SMTP_PORT,
        "server_hostname": SMTP_DOMAIN,
        "data_size_limit": MAX_MESSAGE_BYTES,
    }

    # Enable STARTTLS when cert is available
    if tls_context is not None:
        controller_kwargs["tls_context"] = tls_context
        logger.info("SMTP STARTTLS enabled")
    else:
        logger.warning(
            "SMTP STARTTLS not configured. Set SMTP_TLS_CERT and SMTP_TLS_KEY env vars "
            "to enable TLS. Running plaintext SMTP only."
        )

    controller = Controller(handler, **controller_kwargs)
    controller.start()
    logger.info(
        "SMTP Receiver listening on %s:%d domain=%s tls=%s require_tls=%s",
        SMTP_HOST, SMTP_PORT, SMTP_DOMAIN,
        tls_context is not None, SMTP_REQUIRE_TLS,
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        controller.stop()
        logger.info("SMTP Receiver stopped")
    finally:
        engine, _ = _get_db_session()
        if engine is not None:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_smtp_receiver())

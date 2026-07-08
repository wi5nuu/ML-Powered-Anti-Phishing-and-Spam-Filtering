"""
Pipeline Worker — Enterprise Edition with WebSocket pub/sub, multi-channel alerting, and metrics.

Flow per email:
  1. Ambil dari Redis queue
  2. SpamAssassin scoring (via spamc subprocess atau socket)
  3. ML Classifier scoring (via HTTP ke classifier service) — dual layer
  4. Decision Engine 3-way fusion
  5. Broadcast ke WebSocket via Redis pub/sub
  6. Save ke database
  7. Multi-channel alerting (Slack, Telegram, Email) untuk CRITICAL/HIGH
  8. Track pipeline metrics
"""

import asyncio
import base64
import html
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from email import policy
from email.parser import Parser

import httpx
import redis.asyncio as aio_redis
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from database.models import AdminMailbox, QuarantineEmail, PipelineMetrics
from decision_engine.fusion import FusionResult, fuse
from decision_engine.xai import build_xai_header
from worker.notifier import AlertManager, AlertPayload, alert_manager
from worker.email_forwarder import forward_email

load_dotenv()
logger = structlog.get_logger()

REDIS_URL          = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME         = os.getenv("REDIS_QUEUE_NAME", "email_pipeline")
PUBSUB_CHANNEL     = os.getenv("PUBSUB_CHANNEL", "email:processed")
CLASSIFIER_URL     = os.getenv("CLASSIFIER_URL", "http://classifier:8001")
SA_HOST            = os.getenv("SPAMASSASSIN_HOST", "spamassassin")
SA_PORT            = int(os.getenv("SPAMASSASSIN_PORT", "783"))
DB_URL             = (
    os.getenv("WORKER_DB_URL")
    or os.getenv("DB_ASYNC_URL")
    or os.getenv("DB_URL")
    or "sqlite+aiosqlite:///./cognimail.db"
)
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "10"))
MAX_ATTACHMENT_BYTES = int(os.getenv("MAX_ATTACHMENT_BYTES", str(10 * 1024 * 1024)))
MAX_STORED_ATTACHMENTS = int(os.getenv("MAX_STORED_ATTACHMENTS", "20"))
AUTH_RESULT_VALUES = ("pass", "fail", "softfail", "neutral", "none", "temperror", "permerror", "policy")
THREAT_CATEGORIES = {"spam", "phishing", "malware"}

PHISHING_HINTS = (
    "phishing", "verify your account", "verify account", "confirm your account",
    "account suspended", "account locked", "password", "login", "log in",
    "security alert", "unusual activity", "update your account", "bank",
    "paypal", "wallet", "credential", "click here", "reset your",
)
MALWARE_HINTS = (
    "malware", "trojan", "virus", "ransomware", "keylogger", "payload",
    ".exe", ".scr", ".bat", ".cmd", ".js attachment", ".vbs", "macro enabled",
)
SPAM_HINTS = (
    "free shipping", "lose weight", "limited time", "cash grants",
    "insurance", "mortgage", "unsubscribe", "newsletter", "viagra",
    "lowest price", "special offer", "earn money", "mlm",
)
PHISHING_STRONG_HINTS = (
    "verify your account", "verify account", "confirm your account",
    "account suspended", "account locked", "update your account",
    "security alert", "unusual activity", "credential", "password",
    "login", "log in", "reset your", "verifikasi", "konfirmasi",
)
SUSPICIOUS_URL_HINTS = (
    "secure-account", "account-verification", "verification", "verify",
    "login", "signin", "password", "session", "update",
)
SPAM_STRONG_HINTS = (
    "lose weight", "life insurance", "insurance", "mortgage", "viagra",
    "lowest price", "special offer", "earn money", "cash grants",
    "fortune 500", "at home reps", "customer base", "e-mail marketing",
    "email marketing", "limited time", "guaranteed to lose",
    "membership to 5 sites", "multiply your customer", "bank account",
)


def _safe_html(content: str) -> str:
    content = re.sub(r"(?is)<(script|iframe|object|embed|form|style)\b.*?</\1>", "", content or "")
    content = re.sub(r"(?i)\son[a-z]+\s*=\s*(['\"]).*?\1", "", content)
    content = re.sub(r"(?i)javascript:", "", content)
    return content


def _linkify_plain_text(content: str) -> str:
    escaped = html.escape(content or "")
    linked = re.sub(
        r"(https?://[^\s<]+)",
        r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
        escaped,
    )
    return linked.replace("\n", "<br>")


def _decode_email_bytes(data: bytes, charset: str | None) -> str:
    for candidate in [charset, "utf-8", "latin-1"]:
        if not candidate:
            continue
        try:
            return data.decode(candidate, errors="replace")
        except LookupError:
            continue
    return data.decode("utf-8", errors="replace")


def _db_text(value, limit: int | None = None) -> str:
    text_value = str(value or "").replace("\x00", "")
    return text_value[:limit] if limit else text_value


def _auth_value(source: str, key: str) -> str:
    match = re.search(
        rf"\b{re.escape(key)}\s*=\s*({'|'.join(AUTH_RESULT_VALUES)})\b",
        source or "",
        re.IGNORECASE,
    )
    return match.group(1).upper() if match else ""


def derive_auth_results(raw_email: str, sender: str = "") -> dict:
    try:
        msg = Parser(policy=policy.default).parsestr(raw_email or "")
        auth_headers = " ".join(msg.get_all("Authentication-Results", []) or [])
        received_spf = " ".join(msg.get_all("Received-SPF", []) or [])
        dkim_signature = bool(msg.get("DKIM-Signature"))
    except Exception:
        auth_headers = ""
        received_spf = ""
        dkim_signature = False

    combined = f"{auth_headers} {received_spf}"
    spf = _auth_value(combined, "spf")
    dkim = _auth_value(auth_headers, "dkim")
    dmarc = _auth_value(auth_headers, "dmarc")

    if not spf and received_spf:
        lowered = received_spf.lower()
        spf = next((value.upper() for value in AUTH_RESULT_VALUES if value in lowered), "")
    if not dkim and dkim_signature:
        dkim = "SIGNED"

    domain_match = re.search(r"@([A-Za-z0-9.-]+)", sender or "")
    domain = domain_match.group(1).lower() if domain_match else ""
    fallback = "LOCAL TEST" if domain.endswith(".test") or domain in {"local.test", "localhost", "example.test"} else "N/A"
    return {
        "spf_result": spf or fallback,
        "dkim_result": dkim or fallback,
        "dmarc_result": dmarc or fallback,
    }


def infer_threat_category(raw_email: str, fusion_label: str, existing_category: str = "") -> str:
    category = (existing_category or "").strip().lower()
    if category in THREAT_CATEGORIES or category in {"clean", "sent", "draft"}:
        return category
    if fusion_label == "CLEAN":
        return "clean"

    text = (raw_email or "").lower()
    if any(hint in text for hint in MALWARE_HINTS):
        return "malware"
    if any(hint in text for hint in PHISHING_HINTS):
        return "phishing"
    if any(hint in text for hint in SPAM_HINTS):
        return "spam"
    return "spam" if fusion_label in {"WARN", "QUARANTINE"} else category


def _urls_from_text(raw_email: str) -> list[str]:
    return re.findall(r"https?://[^\s\"'<>)]{4,}", raw_email or "", flags=re.IGNORECASE)


def content_threat_evidence(raw_email: str, ml_probability: float, sa_score: float, anomaly_score: float) -> tuple[str, str]:
    text = (raw_email or "").lower()
    urls = [url.lower() for url in _urls_from_text(raw_email)]

    phishing_hint = any(hint in text for hint in PHISHING_STRONG_HINTS)
    suspicious_url = any(any(hint in url for hint in SUSPICIOUS_URL_HINTS) for url in urls)
    spam_hint = any(hint in text for hint in SPAM_STRONG_HINTS)

    if spam_hint and not suspicious_url and ml_probability >= 0.70 and (sa_score >= 5.0 or anomaly_score >= 0.70):
        evidence = ["strong spam language"]
        if ml_probability >= 0.70:
            evidence.append(f"ML={ml_probability:.3f}")
        if sa_score >= 5.0:
            evidence.append(f"SA={sa_score:.1f}")
        if anomaly_score >= 0.70:
            evidence.append(f"anomaly={anomaly_score:.3f}")
        return "spam", ", ".join(evidence)

    if ml_probability >= 0.85 and phishing_hint and (suspicious_url or anomaly_score >= 0.72 or sa_score >= 8.0):
        evidence = ["ML high", "phishing language"]
        if suspicious_url:
            evidence.append("suspicious verification/login URL")
        if anomaly_score >= 0.72:
            evidence.append(f"anomaly={anomaly_score:.3f}")
        if sa_score >= 8.0:
            evidence.append(f"SA={sa_score:.1f}")
        return "phishing", ", ".join(evidence)

    if ml_probability >= 0.85 and spam_hint and (sa_score >= 5.0 or anomaly_score >= 0.72):
        evidence = ["ML high", "strong spam language"]
        if sa_score >= 5.0:
            evidence.append(f"SA={sa_score:.1f}")
        if anomaly_score >= 0.72:
            evidence.append(f"anomaly={anomaly_score:.3f}")
        return "spam", ", ".join(evidence)

    return "", ""


def apply_content_guard(fusion: FusionResult, raw_email: str, ml_probability: float, sa_score: float, anomaly_score: float) -> tuple[FusionResult, str]:
    if fusion.label != "CLEAN":
        return fusion, ""

    category, evidence = content_threat_evidence(raw_email, ml_probability, sa_score, anomaly_score)
    if not category:
        return fusion, ""

    guarded = FusionResult(
        sa_score=fusion.sa_score,
        ml_probability=fusion.ml_probability,
        anomaly_score=fusion.anomaly_score,
        sa_normalized=fusion.sa_normalized,
        fused_score=max(fusion.fused_score, 0.86),
        label="QUARANTINE",
        routing_reason=f"Content evidence guard: {category} ({evidence}); {fusion.routing_reason}",
    )
    return guarded, category


def parse_message_for_storage(raw_email: str, payload: dict) -> dict:
    try:
        msg = Parser(policy=policy.default).parsestr(raw_email)
    except Exception:
        return {
            "subject": "",
            "sender": payload.get("sender", ""),
            "recipients": payload.get("recipients", []),
            "body_html": _linkify_plain_text(raw_email),
            "attachments": [],
        }

    subject = str(msg.get("subject", "") or "")
    sender = str(msg.get("from", "") or payload.get("sender", "") or "")
    recipients = msg.get_all("to", []) or payload.get("recipients", [])
    if isinstance(recipients, str):
        recipients = [recipients]

    html_body = ""
    plain_body = ""
    attachments = []

    for part in msg.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        disposition = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()

        if disposition in {"attachment", "inline"} or filename:
            if len(attachments) >= MAX_STORED_ATTACHMENTS:
                continue
            data = part.get_payload(decode=True) or b""
            attachments.append({
                "index": len(attachments),
                "filename": filename or f"attachment-{len(attachments) + 1}",
                "content_type": content_type,
                "size": len(data),
                "stored": len(data) <= MAX_ATTACHMENT_BYTES,
                "data": base64.b64encode(data).decode("ascii") if len(data) <= MAX_ATTACHMENT_BYTES else "",
            })
            continue

        try:
            content = part.get_content()
        except Exception:
            payload_text = part.get_payload(decode=True) or b""
            content = _decode_email_bytes(payload_text, part.get_content_charset())

        if content_type == "text/html" and not html_body:
            html_body = str(content)
        elif content_type == "text/plain" and not plain_body:
            plain_body = str(content)

    if html_body:
        body_html = _safe_html(html_body)
    elif plain_body:
        body_html = _linkify_plain_text(plain_body)
    else:
        body_html = _linkify_plain_text(raw_email)

    return {
        "subject": subject,
        "sender": sender,
        "recipients": recipients,
        "body_html": body_html,
        "attachments": attachments,
    }


async def score_with_spamassassin(raw_email: str) -> float:
    """
    Skor email dengan SpamAssassin via spamd protocol (blocking socket in executor).

    SpamAssassin membutuhkan EOF pada sisi tulis sebelum memproses.
    """
    import socket as _socket

    def _sa_score(email_bytes: bytes) -> float:
        """Synchronous SA scoring via raw socket."""
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.settimeout(25.0)
        try:
            sock.connect((SA_HOST, SA_PORT))
            req = (
                f"SYMBOLS SPAMC/1.0\r\n"
                f"Content-length: {len(email_bytes)}\r\n"
                f"User: cognimail-worker\r\n\r\n"
            ).encode() + email_bytes
            sock.sendall(req)
            sock.shutdown(_socket.SHUT_WR)

            resp = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
                if b"\r\n\r\n" in resp:
                    break

            header = resp.decode("utf-8", errors="replace")
            for line in header.splitlines():
                if line.lower().startswith("spam:"):
                    parts = line.split(";")
                    score_part = parts[-1].strip()
                    return float(score_part.split("/")[0].strip())
            logger.warning("sa_score_parse_failed", response=header[:200])
            return 0.0
        finally:
            sock.close()

    try:
        body = raw_email.encode("utf-8", errors="replace")
        loop = asyncio.get_running_loop()
        score = await asyncio.wait_for(
            loop.run_in_executor(None, _sa_score, body),
            timeout=30.0,
        )
        return score
    except asyncio.TimeoutError:
        logger.error("spamassassin_timeout")
        return 0.0
    except Exception as e:
        logger.error("spamassassin_error", error=str(e))
        return 0.0


async def score_with_ml(raw_email: str, email_id: str,
                        client: httpx.AsyncClient) -> dict:
    """Call dual-layer classifier service, return supervised + unsupervised scores."""
    try:
        resp = await client.post(
            f"{CLASSIFIER_URL}/predict-dual",
            json={"raw_email": raw_email, "email_id": email_id},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        logger.error("classifier_timeout", email_id=email_id)
        return {"spam_probability": 0.0, "anomaly_score": 0.0,
                "xai_summary": "Classifier timeout", "top_reasons": []}
    except httpx.HTTPStatusError as e:
        logger.error("classifier_http_error", status=e.response.status_code)
        return {"spam_probability": 0.0, "anomaly_score": 0.0,
                "xai_summary": "Classifier error", "top_reasons": []}
    except Exception as e:
        logger.error("classifier_error", error=str(e))
        return {"spam_probability": 0.0, "anomaly_score": 0.0,
                "xai_summary": str(e), "top_reasons": []}


async def process_one_email(payload: dict, http_client: httpx.AsyncClient,
                             db_session: AsyncSession):
    """Process satu email end-to-end."""
    email_id   = payload.get("email_id", "unknown")
    raw_email  = payload.get("raw_email", "")
    received_at = payload.get("received_at", datetime.now(timezone.utc).isoformat())

    start = time.monotonic()

    # ── Skor paralel: SA + Dual ML (Supervised + Unsupervised) ──────────────
    sa_task  = asyncio.create_task(score_with_spamassassin(raw_email))
    ml_task  = asyncio.create_task(score_with_ml(raw_email, email_id, http_client))
    sa_score, ml_result = await asyncio.gather(sa_task, ml_task)

    ml_prob       = ml_result.get("spam_probability", 0.0)
    anomaly_score = ml_result.get("anomaly_score", 0.0)
    xai_str       = ml_result.get("xai_summary", "")

    # Parse auth dari raw email untuk fusion
    spf_pass   = "spf=pass"  in raw_email.lower()
    dkim_pass  = "dkim=pass" in raw_email.lower()
    dmarc_pass = "dmarc=pass" in raw_email.lower()

    # ── Decision Engine (3-way fusion) ──────────────────────────────────────
    fusion = fuse(
        sa_score=sa_score,
        ml_probability=ml_prob,
        anomaly_score=anomaly_score,
        spf_pass=spf_pass,
        dkim_pass=dkim_pass,
        dmarc_pass=dmarc_pass,
    )
    fusion, guarded_category = apply_content_guard(
        fusion,
        raw_email=raw_email,
        ml_probability=ml_prob,
        sa_score=sa_score,
        anomaly_score=anomaly_score,
    )

    elapsed_ms = (time.monotonic() - start) * 1000

    logger.info(
        "email_processed",
        email_id=email_id,
        sa_score=sa_score,
        ml_prob=ml_prob,
        fused_score=fusion.fused_score,
        label=fusion.label,
        elapsed_ms=round(elapsed_ms, 1),
    )

    # ── Ekstrak subject/sender dari raw email ────────────────────────────
    message_data = parse_message_for_storage(raw_email, payload)
    subject = message_data["subject"]
    sender = message_data["sender"]
    recipients = message_data["recipients"]
    auth_results = derive_auth_results(raw_email, sender)
    threat_category = guarded_category or infer_threat_category(raw_email, fusion.label, payload.get("category", ""))

    # ── Simpan ke DB ──────────────────────────────────────────────────────
    # Simpan semua email. Untuk email CLEAN, simpan konten minimal saja untuk menghemat DB space.
    quarantine_entry = QuarantineEmail(
        email_id=email_id,
        received_at=_db_text(received_at, 32),
        label=fusion.label,
        fused_score=fusion.fused_score,
        sa_score=sa_score,
        ml_probability=ml_prob,
        anomaly_score=anomaly_score,
        xai_summary=_db_text(xai_str),
        routing_reason=_db_text(fusion.routing_reason),
        raw_content_hash=_db_text(payload.get("raw_hash", ""), 64),
        raw_content=_db_text(message_data["body_html"], 200000),
        attachments_json=_db_text(json.dumps(message_data["attachments"])),
        status="released" if fusion.label == "CLEAN" else "pending",
        subject=_db_text(subject, 512),
        sender=_db_text(sender, 256),
        recipient_list=_db_text(", ".join(recipients)),
        category=threat_category,
        spf_result=_db_text(auth_results["spf_result"], 32),
        dkim_result=_db_text(auth_results["dkim_result"], 32),
        dmarc_result=_db_text(auth_results["dmarc_result"], 32),
    )
    db_session.add(quarantine_entry)
    await db_session.commit()

    # ── Broadcast ke WebSocket via Redis pub/sub ─────────────────────────
    pubsub_payload = json.dumps({
        "type": "email_processed",
        "email_id": email_id,
        "subject": subject,
        "label": fusion.label,
        "fused_score": fusion.fused_score,
        "anomaly_score": anomaly_score,
        "ml_probability": ml_prob,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r_pub = await aio_redis.from_url(REDIS_URL)
        await r_pub.publish(PUBSUB_CHANNEL, pubsub_payload)
        await r_pub.aclose()
    except Exception as e:
        logger.warning("pubsub_publish_failed", error=str(e))

    # ── Multi-channel alerting untuk QUARANTINE ──────────────────────────
    if fusion.label == "QUARANTINE":
        severity = "CRITICAL" if anomaly_score > 0.5 else "HIGH"
        alert_payload = AlertPayload(
            email_id=email_id,
            subject=subject,
            sender=sender,
            fused_score=fusion.fused_score,
            ml_probability=ml_prob,
            anomaly_score=anomaly_score,
            label=fusion.label,
            xai_summary=xai_str,
            severity=severity,
        )
        asyncio.create_task(alert_manager.send_all(alert_payload))

    # ── Forward CLEAN/WARN ke inbox asli ────────────────────────────────
    import os as _os
    category = threat_category
    should_forward = (
        _os.getenv("FORWARDER_SMTP_HOST")
        and fusion.label != "QUARANTINE"
        and category not in THREAT_CATEGORIES
    )
    if should_forward:
        recipient_lowers = {recipient.lower() for recipient in recipients}
        result = await db_session.execute(
            select(AdminMailbox).where(
                AdminMailbox.is_active == True,
                AdminMailbox.forward_enabled == True,
                AdminMailbox.forward_to != "",
            )
        )
        for mailbox in result.scalars().all():
            if mailbox.email.lower() not in recipient_lowers:
                continue
            forward_payload = dict(payload)
            forward_recipients = [mailbox.forward_to]
            if mailbox.forward_keep_copy:
                forward_recipients.append(mailbox.email)
            forward_payload["recipients"] = list(dict.fromkeys(
                recipient.strip().lower() for recipient in forward_recipients if recipient
            ))
            forward_payload["email_id"] = f"{email_id}:forward:{mailbox.id}"
            asyncio.create_task(forward_email(
                raw_email, fusion.label, fusion.fused_score, forward_payload
            ))

    return fusion


async def run_worker():
    """Main worker loop."""
    r = aio_redis.from_url(REDIS_URL, socket_timeout=15, socket_connect_timeout=10)
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "postgresql":
            await conn.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN IF NOT EXISTS forward_to VARCHAR(255) DEFAULT ''"))
            await conn.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN IF NOT EXISTS forward_enabled BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN IF NOT EXISTS forward_keep_copy BOOLEAN DEFAULT TRUE"))
            await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS attachments_json TEXT"))
            await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS spf_result VARCHAR(32) DEFAULT ''"))
            await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dkim_result VARCHAR(32) DEFAULT ''"))
            await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dmarc_result VARCHAR(32) DEFAULT ''"))
        elif dialect == "sqlite":
            result = await conn.execute(text("PRAGMA table_info(admin_mailboxes)"))
            mailbox_columns = [row[1] for row in result.fetchall()]
            if "forward_to" not in mailbox_columns:
                await conn.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN forward_to VARCHAR(255) DEFAULT ''"))
            if "forward_enabled" not in mailbox_columns:
                await conn.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN forward_enabled BOOLEAN DEFAULT FALSE"))
            if "forward_keep_copy" not in mailbox_columns:
                await conn.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN forward_keep_copy BOOLEAN DEFAULT TRUE"))
            result = await conn.execute(text("PRAGMA table_info(quarantine_emails)"))
            columns = [row[1] for row in result.fetchall()]
            if "attachments_json" not in columns:
                await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN attachments_json TEXT"))
            if "spf_result" not in columns:
                await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN spf_result VARCHAR(32) DEFAULT ''"))
            if "dkim_result" not in columns:
                await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN dkim_result VARCHAR(32) DEFAULT ''"))
            if "dmarc_result" not in columns:
                await conn.execute(text("ALTER TABLE quarantine_emails ADD COLUMN dmarc_result VARCHAR(32) DEFAULT ''"))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    sem = asyncio.Semaphore(WORKER_CONCURRENCY)  # Batasi concurrency

    async with httpx.AsyncClient() as http_client:
        async with async_session() as session:
            logger.info("worker_started", queue=QUEUE_NAME, concurrency=WORKER_CONCURRENCY)
            while True:
                try:
                    # Blocking pop dengan timeout 5 detik
                    item = await r.blpop(QUEUE_NAME, timeout=5)
                    if item is None:
                        continue
                    _, raw_payload = item
                    payload = json.loads(raw_payload)

                    async with sem:
                        await process_one_email(payload, http_client, session)

                except json.JSONDecodeError as e:
                    logger.error("json_decode_error", error=str(e))
                except Exception as e:
                    logger.exception("worker_error", error=str(e))
                    await asyncio.sleep(1)  # Backoff kecil sebelum retry


if __name__ == "__main__":
    asyncio.run(run_worker())



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
import json
import logging
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

import httpx
import redis.asyncio as aio_redis
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.models import QuarantineEmail, PipelineMetrics
from decision_engine.fusion import fuse
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
DB_URL             = os.getenv("DB_URL", "sqlite+aiosqlite:///./lti_antiphishing.db")
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "10"))


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
                f"User: lti-worker\r\n\r\n"
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
    subject = ""
    sender = ""
    for line in raw_email.splitlines():
        if line.lower().startswith("subject:"):
            subject = line[8:].strip()
        elif line.lower().startswith("from:"):
            sender = line[5:].strip()
        if subject and sender:
            break

    # ── Simpan ke DB jika bukan CLEAN ─────────────────────────────────────
    if fusion.label in ("WARN", "QUARANTINE"):
        quarantine_entry = QuarantineEmail(
            email_id=email_id,
            received_at=received_at,
            label=fusion.label,
            fused_score=fusion.fused_score,
            sa_score=sa_score,
            ml_probability=ml_prob,
            anomaly_score=anomaly_score,
            xai_summary=xai_str,
            routing_reason=fusion.routing_reason,
            raw_content_hash=payload.get("raw_hash", ""),
            raw_content=raw_email[:50000],  # Simpan 50KB pertama untuk forensik
            status="pending",
            subject=subject,
            sender=sender,
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
    # Hanya forward jika FORWARDER_SMTP_HOST di-set
    import os as _os
    if _os.getenv("FORWARDER_SMTP_HOST"):
        asyncio.create_task(forward_email(
            raw_email, fusion.label, fusion.fused_score, payload
        ))

    return fusion


async def run_worker():
    """Main worker loop."""
    r = aio_redis.from_url(REDIS_URL)
    engine = create_async_engine(DB_URL, echo=False)
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

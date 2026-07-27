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
import os
import re
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from email import policy
from email.parser import Parser
from email.utils import getaddresses

import httpx
import redis.asyncio as aio_redis
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from database.models import AdminMailbox, Base, QuarantineEmail
from decision_engine.content_guard import content_threat_evidence, dangerous_attachment_name
from decision_engine.fusion import FusionResult, fuse
from worker.notifier import AlertPayload, alert_manager
from worker.email_forwarder import build_warning_xai_header, forward_email

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
)
if not DB_URL:
    raise RuntimeError(
        "WORKER_DB_URL tidak ditemukan. "
        "Set env var WORKER_DB_URL dengan PostgreSQL async URL. "
        "Contoh: postgresql+asyncpg://cogniuser:password@postgres:5432/cognimail"
    )
if "sqlite" in DB_URL.lower():
    raise RuntimeError(
        "SQLite tidak didukung. Gunakan: postgresql+asyncpg://cogniuser:password@postgres:5432/cognimail"
    )
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "10"))
MAX_ATTACHMENT_BYTES = int(os.getenv("MAX_ATTACHMENT_BYTES", str(10 * 1024 * 1024)))
MAX_STORED_ATTACHMENTS = int(os.getenv("MAX_STORED_ATTACHMENTS", "20"))
AUTH_RESULT_VALUES = ("pass", "fail", "softfail", "neutral", "none", "temperror", "permerror", "policy")
THREAT_CATEGORIES = {"spam", "phishing"}


def normalize_addresses(values) -> list[str]:
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
    if category == "malware":
        return "phishing"
    if dangerous_attachment_name(raw_email):
        return "phishing"
    if category in THREAT_CATEGORIES or category in {"clean", "sent", "draft"}:
        return category
    if fusion_label == "CLEAN":
        return "clean"

    text = (raw_email or "").lower()
    if any(hint in text for hint in MALWARE_HINTS):
        # CogniMail exposes two actionable threat buckets. Attachment/payload
        # based threats are reviewed in Phishing instead of a separate
        # Malware mailbox category.
        return "phishing"
    if any(hint in text for hint in PHISHING_HINTS):
        return "phishing"
    if any(hint in text for hint in SPAM_HINTS):
        return "spam"
    return "spam" if fusion_label in {"WARN", "QUARANTINE"} else category


def apply_content_guard(fusion: FusionResult, raw_email: str, ml_probability: float, sa_score: float, anomaly_score: float) -> tuple[FusionResult, str]:
    category, evidence = content_threat_evidence(raw_email, ml_probability, sa_score, anomaly_score)
    # A statistical hard/review threshold can quarantine before deterministic
    # content analysis. Preserve that routing decision, but still return the
    # content-derived category so a phishing message is not put in Spam merely
    # because it reached quarantine early.
    if fusion.label == "QUARANTINE":
        return fusion, category

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


def calibrate_short_benign_message(
    fusion: FusionResult,
    message_data: dict,
    sa_score: float,
    classifier_error: bool = False,
) -> FusionResult:
    """Prevent MIME/anomaly noise from quarantining trivial plain messages."""
    # SpamAssassin's default spam threshold is 5.0. A score below it is
    # corroborating non-spam evidence, while >=5.0 must never be auto-cleaned.
    if classifier_error or sa_score < 0 or sa_score >= 5.0 or message_data.get("attachments"):
        return fusion
    visible = " ".join(
        str(message_data.get(key) or "") for key in ("subject", "body_text")
    ).strip()
    if not visible or len(visible) > 160 or len(visible.split()) > 20:
        return fusion
    if re.search(r"https?://|www\.|\b(?:password|login|otp|verify|verification|verifikasi|credential|rekening|transfer|invoice|hadiah|gratis|klik|click)\b", visible, re.I):
        return fusion
    if not re.fullmatch(r"[\w\s.,!?;:'\"()@+\-/]+", visible, re.UNICODE):
        return fusion
    if fusion.label == "CLEAN":
        return fusion
    return FusionResult(
        sa_score=fusion.sa_score,
        ml_probability=fusion.ml_probability,
        anomaly_score=fusion.anomaly_score,
        sa_normalized=fusion.sa_normalized,
        fused_score=min(fusion.fused_score, 0.2999),
        label="CLEAN",
        routing_reason=(
            "Short benign-message calibration: no URL, attachment, or threat "
            f"language; SpamAssassin={sa_score:.2f}"
        ),
    )


def parse_message_for_storage(raw_email: str, payload: dict) -> dict:
    try:
        msg = Parser(policy=policy.default).parsestr(raw_email)
    except Exception:
        return {
            "subject": "",
            "sender": payload.get("sender", ""),
            "recipients": payload.get("recipients", []),
            "message_id_header": "",
            "references_header": "",
            "body_html": _linkify_plain_text(raw_email),
            "body_text": raw_email,
            "analysis_content": raw_email,
            "attachments": [],
        }

    subject = str(msg.get("subject", "") or "")
    sender = str(msg.get("from", "") or payload.get("sender", "") or "")
    recipients = normalize_addresses(payload.get("recipients", []))
    if not recipients:
        recipients = normalize_addresses(msg.get_all("to", []))

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

    body_text = plain_body.strip()
    if not body_text and html_body:
        body_text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", html_body))
        body_text = " ".join(body_text.split())
    analysis_content = f"Subject: {subject}\n\n{body_text}".strip()
    for attachment in attachments:
        analysis_content += f'\nContent-Disposition: attachment; filename="{attachment["filename"]}"'

    thread_references = " ".join(dict.fromkeys(re.findall(
        r"<[^<>\s]+>",
        f'{msg.get("references", "") or ""} {msg.get("in-reply-to", "") or ""}',
    )))

    return {
        "subject": subject,
        "sender": sender,
        "recipients": recipients,
        "message_id_header": str(msg.get("message-id", "") or "").strip(),
        "references_header": thread_references,
        "body_html": body_html,
        "body_text": body_text,
        "analysis_content": analysis_content,
        "attachments": attachments,
    }


async def score_with_spamassassin(raw_email: str) -> float:
    """
    Skor email dengan SpamAssassin via spamd protocol (blocking socket in executor).

    SpamAssassin membutuhkan EOF pada sisi tulis sebelum memproses.
    """
    import socket as _socket

    def _spamc_request(email_bytes: bytes) -> bytes:
        # SpamAssassin 4 mis-parses MIME headers when clients announce the
        # obsolete SPAMC/1.0 protocol, producing false MISSING_* rules. 1.5 is
        # supported by both current spamd and older maintained releases.
        return (
            "SYMBOLS SPAMC/1.5\r\n"
            f"Content-length: {len(email_bytes)}\r\n"
            "User: cognimail-worker\r\n\r\n"
        ).encode() + email_bytes

    def _sa_score(email_bytes: bytes) -> float:
        """Synchronous SA scoring via raw socket."""
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.settimeout(25.0)
        try:
            sock.connect((SA_HOST, SA_PORT))
            sock.sendall(_spamc_request(email_bytes))
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
        return -1.0  # Sentinel: timeout, not CLEAN
    except Exception as e:
        logger.error("spamassassin_error", error=str(e))
        return -1.0  # Sentinel: error, not CLEAN


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
                "xai_summary": "Classifier timeout", "top_reasons": [],
                "classifier_error": True}
    except httpx.HTTPStatusError as e:
        logger.error("classifier_http_error", status=e.response.status_code)
        return {"spam_probability": 0.0, "anomaly_score": 0.0,
                "xai_summary": f"Classifier HTTP {e.response.status_code}", "top_reasons": [],
                "classifier_error": True}
    except Exception as e:
        logger.error("classifier_error", error=str(e))
        return {"spam_probability": 0.0, "anomaly_score": 0.0,
                "xai_summary": str(e), "top_reasons": [],
                "classifier_error": True}


async def process_one_email(payload: dict, http_client: httpx.AsyncClient,
                             db_session: AsyncSession,
                             redis_client: aio_redis.Redis | None = None):
    """Process satu email end-to-end."""
    email_id   = payload.get("email_id", "unknown")
    raw_email  = payload.get("raw_email", "")
    received_at = payload.get("received_at", datetime.now(timezone.utc).isoformat())
    message_data = parse_message_for_storage(raw_email, payload)
    analysis_content = message_data.get("analysis_content") or raw_email

    start = time.monotonic()

    # ── Skor paralel: SA + Dual ML (Supervised + Unsupervised) ──────────────
    sa_task  = asyncio.create_task(score_with_spamassassin(raw_email))
    ml_task  = asyncio.create_task(score_with_ml(raw_email, email_id, http_client))
    sa_score, ml_result = await asyncio.gather(sa_task, ml_task)

    ml_prob       = ml_result.get("spam_probability", 0.0)
    anomaly_score = ml_result.get("anomaly_score", 0.0)
    xai_str       = ml_result.get("xai_summary", "")
    shap_features = []
    for reason in ml_result.get("top_reasons", []) or []:
        if not isinstance(reason, dict) or not reason.get("feature"):
            continue
        try:
            shap_value = float(reason.get("shap_value", 0.0))
        except (TypeError, ValueError):
            continue
        shap_features.append({
            "name": str(reason["feature"]),
            "shap": round(shap_value, 6),
            "direction": str(reason.get("direction") or ("spam" if shap_value > 0 else "ham")),
        })
    shap_payload = {
        "source": "xgboost_pred_contribs",
        "features": shap_features,
        "prediction_probability": round(float(ml_prob), 6),
        "is_anomaly": bool(ml_result.get("is_anomaly", False)),
    }

    # Authentication-Results inside raw MIME is attacker-controlled. Only
    # receiver-side verification may populate this trusted payload field.
    verified_auth = payload.get("verified_auth") or {}
    spf_pass = verified_auth.get("spf") is True
    dkim_pass = verified_auth.get("dkim") is True
    dmarc_pass = verified_auth.get("dmarc") is True

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
        raw_email=analysis_content,
        ml_probability=ml_prob,
        sa_score=sa_score,
        anomaly_score=anomaly_score,
    )
    if not guarded_category:
        fusion = calibrate_short_benign_message(
            fusion,
            message_data,
            sa_score,
            classifier_error=bool(ml_result.get("classifier_error")),
        )
    if ml_result.get("classifier_error") and fusion.label == "CLEAN":
        # A classifier outage is uncertainty, not proof that an email is
        # clean. Hold the message for admin review and never forward it to the
        # user's inbox until all detection layers have actually run.
        fusion = FusionResult(
            sa_score=fusion.sa_score,
            ml_probability=fusion.ml_probability,
            anomaly_score=fusion.anomaly_score,
            sa_normalized=fusion.sa_normalized,
            fused_score=max(fusion.fused_score, 0.30),
            label="WARN",
            routing_reason=(
                f"Classifier unavailable; held for manual review. "
                f"{fusion.routing_reason}"
            ),
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
    subject = message_data["subject"]
    sender = message_data["sender"]
    recipients = message_data["recipients"]
    auth_results = {
        "spf_result": "PASS" if spf_pass else "N/A",
        "dkim_result": "PASS" if dkim_pass else "N/A",
        "dmarc_result": "PASS" if dmarc_pass else "N/A",
    }
    # Always pass the final candidate through the canonicalizer. This prevents
    # a guarded spam result or a caller-supplied legacy value from bypassing
    # the malware -> phishing product rule.
    threat_category = infer_threat_category(
        analysis_content,
        fusion.label,
        guarded_category or payload.get("category", ""),
    )
    warn_is_deliverable = fusion.label == "WARN" and not ml_result.get("classifier_error")
    delivery_status = (
        "released"
        if fusion.label == "CLEAN"
        else "warn_delivered"
        if warn_is_deliverable
        else "pending"
    )
    warning_xai_payload = {
        "ml_probability": ml_prob,
        "sa_score": sa_score,
        "anomaly_score": anomaly_score,
        "shap_features": shap_features,
        "routing_reason": fusion.routing_reason,
    }
    if warn_is_deliverable:
        # Persist the exact value used for the outbound X-Spam-Reason header.
        # This makes the header auditable from the database and keeps the UI,
        # SMTP delivery, and classifier explanation on one source of truth.
        shap_payload["warning_header"] = build_warning_xai_header(
            fusion.fused_score,
            warning_xai_payload,
        )

    # ── Simpan ke DB ──────────────────────────────────────────────────────
    # Simpan semua email. Untuk email CLEAN, simpan konten minimal saja untuk menghemat DB space.
    quarantine_entry = QuarantineEmail(
        email_id=email_id,
        received_at=datetime.fromisoformat(received_at) if isinstance(received_at, str) else received_at,
        label=fusion.label,
        fused_score=fusion.fused_score,
        sa_score=sa_score,
        ml_probability=ml_prob,
        anomaly_score=anomaly_score,
        shap_json=_db_text(json.dumps(shap_payload)),
        xai_summary=_db_text(xai_str),
        routing_reason=_db_text(fusion.routing_reason),
        raw_content_hash=_db_text(payload.get("raw_hash", ""), 64),
        raw_content=_db_text(raw_email),
        attachments_json=_db_text(json.dumps(message_data["attachments"])),
        status=delivery_status,
        subject=_db_text(subject, 512),
        sender=_db_text(sender, 256),
        recipient_list=_db_text(", ".join(recipients)),
        message_id_header=_db_text(message_data["message_id_header"], 998),
        references_header=_db_text(message_data["references_header"], 8000),
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
        "category": threat_category,
        "status": delivery_status,
        "recipients": recipients,
        "fused_score": fusion.fused_score,
        "anomaly_score": anomaly_score,
        "ml_probability": ml_prob,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    try:
        if redis_client is not None:
            await redis_client.publish(PUBSUB_CHANNEL, pubsub_payload)
        else:
            # Fallback: open a one-shot connection if no shared client provided
            r_pub = await aio_redis.from_url(REDIS_URL)
            try:
                await r_pub.publish(PUBSUB_CHANNEL, pubsub_payload)
            finally:
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

    # ── Forward CLEAN/WARN ke tujuan mailbox ────────────────────────────
    # Fusion is the final routing decision. The heuristic category may still
    # contain "spam" for a message that fusion explicitly released as CLEAN;
    # using both values here silently skipped legitimate forwarding.
    should_forward = fusion.label == "CLEAN" or warn_is_deliverable
    if should_forward:
        recipient_lowers = {recipient.lower() for recipient in recipients}
        result = await db_session.execute(
            select(AdminMailbox).where(
                AdminMailbox.is_active.is_(True),
                AdminMailbox.forward_enabled.is_(True),
                AdminMailbox.forward_to != "",
            )
        )
        for mailbox in result.scalars().all():
            if mailbox.email.lower() not in recipient_lowers:
                continue
            forward_payload = dict(payload)
            forward_recipients = [mailbox.forward_to]
            forward_payload["recipients"] = list(dict.fromkeys(
                recipient.strip().lower() for recipient in forward_recipients if recipient
            ))
            forward_payload["forward_from"] = mailbox.email.lower()
            forward_payload["email_id"] = f"{email_id}:forward:{mailbox.id}"
            forward_payload.update(warning_xai_payload)
            logger.info(
                "mailbox_forward_started",
                email_id=email_id,
                mailbox=mailbox.email,
                destination=mailbox.forward_to,
                label=fusion.label,
            )
            forwarded = await forward_email(
                raw_email, fusion.label, fusion.fused_score, forward_payload
            )
            if forwarded:
                logger.info(
                    "mailbox_forward_succeeded",
                    email_id=email_id,
                    mailbox=mailbox.email,
                    destination=mailbox.forward_to,
                )
            else:
                logger.error(
                    "mailbox_forward_failed",
                    email_id=email_id,
                    mailbox=mailbox.email,
                    destination=mailbox.forward_to,
                )
    else:
        logger.info(
            "mailbox_forward_skipped",
            email_id=email_id,
            label=fusion.label,
            category=threat_category,
            reason="final_decision_not_forwardable",
        )

    return fusion


async def run_worker():
    """Main worker loop."""
    r = aio_redis.from_url(REDIS_URL, socket_timeout=15, socket_connect_timeout=10)

    # Retry loop — tunggu PostgreSQL siap sebelum lanjut
    engine = create_async_engine(
        DB_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    for attempt in range(1, 31):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            break
        except Exception as exc:
            logger.warning("db_not_ready", attempt=attempt, error=str(exc))
            if attempt == 30:
                raise RuntimeError(f"PostgreSQL tidak tersedia setelah 30 percobaan: {exc}")
            await asyncio.sleep(2)

    async with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect != "postgresql":
            logger.warning("dialect_not_postgresql", dialect=dialect)
        else:
            await conn.run_sync(Base.metadata.create_all)
            rows = await conn.execute(text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name IN ('admin_mailboxes', 'quarantine_emails')"
            ))
            existing_columns = {(row[0], row[1]) for row in rows}
            required_migrations = {
                ("admin_mailboxes", "forward_to"): "ALTER TABLE admin_mailboxes ADD COLUMN forward_to VARCHAR(255) DEFAULT ''",
                ("admin_mailboxes", "forward_enabled"): "ALTER TABLE admin_mailboxes ADD COLUMN forward_enabled BOOLEAN DEFAULT FALSE",
                ("admin_mailboxes", "forward_keep_copy"): "ALTER TABLE admin_mailboxes ADD COLUMN forward_keep_copy BOOLEAN DEFAULT TRUE",
                ("quarantine_emails", "attachments_json"): "ALTER TABLE quarantine_emails ADD COLUMN attachments_json TEXT",
                ("quarantine_emails", "is_read"): "ALTER TABLE quarantine_emails ADD COLUMN is_read BOOLEAN DEFAULT FALSE",
                ("quarantine_emails", "spf_result"): "ALTER TABLE quarantine_emails ADD COLUMN spf_result VARCHAR(32) DEFAULT ''",
                ("quarantine_emails", "dkim_result"): "ALTER TABLE quarantine_emails ADD COLUMN dkim_result VARCHAR(32) DEFAULT ''",
                ("quarantine_emails", "dmarc_result"): "ALTER TABLE quarantine_emails ADD COLUMN dmarc_result VARCHAR(32) DEFAULT ''",
                ("quarantine_emails", "message_id_header"): "ALTER TABLE quarantine_emails ADD COLUMN message_id_header VARCHAR(998) DEFAULT ''",
                ("quarantine_emails", "references_header"): "ALTER TABLE quarantine_emails ADD COLUMN references_header TEXT DEFAULT ''",
            }
            missing_statements = [
                statement
                for column, statement in required_migrations.items()
                if column not in existing_columns
            ]
            if missing_statements:
                await conn.execute(text("SET LOCAL lock_timeout = '10s'"))
                for statement in missing_statements:
                    await conn.execute(text(statement))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    sem = asyncio.Semaphore(WORKER_CONCURRENCY)  # Batasi concurrency
    DEAD_LETTER_QUEUE = QUEUE_NAME + ":dead"
    PROCESSING_QUEUE = QUEUE_NAME + ":processing"

    # Recover jobs reserved by a worker that stopped before acknowledgement.
    while await r.llen(PROCESSING_QUEUE):
        await r.rpoplpush(PROCESSING_QUEUE, QUEUE_NAME)

    async def _handle_with_sem(p: dict, reserved_payload):
        """Acquire semaphore then process; push to DLQ on unrecoverable failure."""
        async with sem:
            try:
                async with async_session() as session:
                    await process_one_email(p, http_client, session, redis_client=r)
                await r.lrem(PROCESSING_QUEUE, 1, reserved_payload)
            except Exception as exc:
                logger.exception("process_one_email_failed", email_id=p.get("email_id"), error=str(exc))
                try:
                    await r.rpush(DEAD_LETTER_QUEUE, json.dumps(p))
                    await r.lrem(PROCESSING_QUEUE, 1, reserved_payload)
                except Exception as dlq_exc:
                    logger.error("dead_letter_push_failed", error=str(dlq_exc))

    async with httpx.AsyncClient() as http_client:
        logger.info("worker_started", queue=QUEUE_NAME, concurrency=WORKER_CONCURRENCY)
        while True:
            try:
                # A short-lived heartbeat lets the dashboard distinguish an
                # idle worker from a stopped worker without inventing status
                # from historical pipeline metrics.
                await r.set(
                    "cognimail:worker:heartbeat",
                    datetime.now(timezone.utc).isoformat(),
                    ex=15,
                )
                # Atomically reserve before processing. A crash leaves the
                # payload recoverable in PROCESSING_QUEUE on the next start.
                raw_payload = await r.blmove(
                    QUEUE_NAME, PROCESSING_QUEUE, timeout=5, src="LEFT", dest="RIGHT"
                )
                if raw_payload is None:
                    continue
                try:
                    payload = json.loads(raw_payload)
                except json.JSONDecodeError:
                    await r.rpush(DEAD_LETTER_QUEUE, raw_payload)
                    await r.lrem(PROCESSING_QUEUE, 1, raw_payload)
                    raise

                # Spawn a task so the main loop keeps dequeuing while workers run
                asyncio.create_task(_handle_with_sem(payload, raw_payload))

            except json.JSONDecodeError as e:
                logger.error("json_decode_error", error=str(e))
            except Exception as e:
                logger.exception("worker_error", error=str(e))
                await asyncio.sleep(1)  # Backoff kecil sebelum retry


if __name__ == "__main__":
    asyncio.run(run_worker())



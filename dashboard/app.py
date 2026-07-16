"""
CogniMail Dashboard — Enterprise Edition.

Features:
  1. JWT authentication with RBAC (superadmin/admin/user)
  2. Quarantine table with Dual Detection badges
  3. Email detail with SHAP force plot (interactive)
  4. WebSocket live feed for real-time updates
  5. Audit logging for all actions
  6. Dark mode toggle
  7. Email preview (expandable rows)
  8. Health endpoint
  9. Metrics panel with charts
  10. Feedback loop
"""

import asyncio
import base64
import contextlib
import html
import json
import logging
import mimetypes
import os
import re
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import secrets as _secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import httpx
import redis.asyncio as aio_redis
import uuid
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email import policy
from email.parser import Parser
from email.utils import getaddresses

from pydantic import BaseModel
import csv
import io
import random
from fastapi import FastAPI, Request, Depends, Form, HTTPException, WebSocket, WebSocketDisconnect, Query, UploadFile
from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, case, text, or_, and_
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator

from database.models import QuarantineEmail, Feedback, User, AuditLog, Organization, PipelineMetrics, Report, AdminMailbox, UserRole
from dashboard.database import get_db, SessionLocal
from dashboard.auth import (
    hash_password, verify_password, create_access_token, decode_token, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user, require_role, log_audit, verify_api_key
)
from dashboard.rbac import (
    Permission, check_permission, check_role, get_user_permissions, has_permission_dict, ROLE_DESCRIPTIONS, UserRole as RBACUserRole
)
from dashboard import admin_routes

logger = logging.getLogger(__name__)
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Jakarta"))


def app_now() -> datetime:
    return datetime.now(APP_TIMEZONE)


def app_now_iso() -> str:
    return app_now().isoformat(timespec="seconds")

THREAT_RETENTION_DAYS = int(os.getenv("MAX_QUARANTINE_DAYS", "30"))
THREAT_CATEGORIES = ["spam", "phishing", "malware"]


def purge_expired_emails(db: Session) -> int:
    cutoff = app_now() - timedelta(days=THREAT_RETENTION_DAYS)
    trash_deleted = db.query(QuarantineEmail).filter(
        QuarantineEmail.status == "trash",
        QuarantineEmail.deleted_at < cutoff,
    ).delete(synchronize_session=False)

    threat_deleted = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
        QuarantineEmail.label.notin_(["DRAFT", "SENT", "CLEAN"]),
        QuarantineEmail.created_at < cutoff,
        or_(
            QuarantineEmail.label == "QUARANTINE",
            QuarantineEmail.category.in_(THREAT_CATEGORIES),
        ),
    ).delete(synchronize_session=False)
    return (trash_deleted or 0) + (threat_deleted or 0)

DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY")
if not DASHBOARD_SECRET_KEY:
    DASHBOARD_SECRET_KEY = _secrets.token_hex(32)
    logger.warning("DASHBOARD_SECRET_KEY not set. Generated ephemeral key.")

static_dir = Path(__file__).parent / "static"

app = FastAPI(title="CogniMail Dashboard", version="3.0.0")
Instrumentator().instrument(app).expose(app)

csrf_secret = os.getenv("DASHBOARD_SECRET_KEY") or _secrets.token_hex(32)
app.add_middleware(SessionMiddleware, secret_key=csrf_secret, same_site="lax", https_only=False)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(","))
# Default CORS origins — includes Vite dev (5173), production build (8081), and configurable extras
_default_cors = "http://localhost:5173,http://localhost:8081,http://127.0.0.1:5173,http://127.0.0.1:8081"
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", _default_cors).split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/emails/") and "/attachments/" in request.url.path:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        else:
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if os.getenv("ENV", "development") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register RBAC admin routes
app.include_router(admin_routes.router)




# ─── WebSocket Connection Manager ───────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)

manager = ConnectionManager()
PUBSUB_CHANNEL = os.getenv("PUBSUB_CHANNEL", "email:processed")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
    token = token or websocket.cookies.get("access_token", "")
    if not token:
        await websocket.close(code=4001)
        return
    try:
        payload = decode_token(token)
        if not payload.get("sub"):
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ─── Redis Pub/Sub → WebSocket Bridge (background task) ────────────────────────

REDIS_URL_WS = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def redis_pubsub_bridge(stop_event: asyncio.Event = None):
    """Listen for Redis pub/sub messages and broadcast to WebSocket clients."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        logger.info("REDIS_URL not set. Pub/sub bridge disabled.")
        return
    while True:
        r = None
        try:
            r = aio_redis.from_url(redis_url, socket_timeout=5, socket_connect_timeout=3)
            await r.ping()
            async with r.pubsub() as pubsub:
                await pubsub.subscribe(PUBSUB_CHANNEL)
                logger.info("Redis pub/sub bridge started on channel: %s", PUBSUB_CHANNEL)
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if not message:
                        if stop_event and stop_event.is_set():
                            return
                        continue
                    if message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            await manager.broadcast(data)
                        except Exception as e:
                            logger.warning("pubsub_bridge_parse_error: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Redis pub/sub unavailable: %s. Skipping.", e)
            return
        finally:
            if r is not None:
                with contextlib.suppress(Exception):
                    await r.aclose()


@app.on_event("startup")
async def start_pubsub_bridge():
    app.state.pubsub_stop = asyncio.Event()
    app.state.pubsub_task = asyncio.create_task(redis_pubsub_bridge(app.state.pubsub_stop))


@app.on_event("shutdown")
async def stop_pubsub_bridge():
    task = getattr(app.state, "pubsub_task", None)
    stop = getattr(app.state, "pubsub_stop", None)
    if stop:
        stop.set()
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# ─── Seed Admin User ────────────────────────────────────────────────────────────

ALLOWED_ROLES = {"superadmin", "admin", "user"}


def _upsert_seed_user(db, username: str, password: str, role: str, email: str = None, legacy_usernames=None):
    legacy_usernames = legacy_usernames or []
    user = db.query(User).filter(User.username == username).first()
    if not user:
        for old_username in legacy_usernames:
            legacy = db.query(User).filter(User.username == old_username).first()
            if legacy:
                legacy.username = username
                user = legacy
                break
    if not user:
        user = User(username=username)
        db.add(user)

    user.email = email
    user.hashed_password = hash_password(password)
    user.role = role
    user.is_active = True
    return user


def seed_admin():
    import random
    db = SessionLocal()
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS attachments_json TEXT"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS spf_result VARCHAR(32) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dkim_result VARCHAR(32) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dmarc_result VARCHAR(32) DEFAULT ''"))
    elif dialect == "sqlite":
        columns = [row[1] for row in db.execute(text("PRAGMA table_info(quarantine_emails)")).fetchall()]
        if "deleted_at" not in columns:
            db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN deleted_at TIMESTAMP"))
        if "attachments_json" not in columns:
            db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN attachments_json TEXT"))
        if "spf_result" not in columns:
            db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN spf_result VARCHAR(32) DEFAULT ''"))
        if "dkim_result" not in columns:
            db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN dkim_result VARCHAR(32) DEFAULT ''"))
        if "dmarc_result" not in columns:
            db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN dmarc_result VARCHAR(32) DEFAULT ''"))
    purge_expired_emails(db)
    db.query(QuarantineEmail).filter(
        QuarantineEmail.status == "released",
        QuarantineEmail.label.in_(["WARN", "QUARANTINE"]),
    ).update({"label": "CLEAN", "category": "clean"}, synchronize_session=False)
    legacy_user_roles = ["ana" + "lyst", "mail" + "_" + "re" + "view" + "er"]
    db.query(User).filter(User.role.in_(legacy_user_roles)).update({"role": "user"})
    db.query(User).filter(User.role == "security" + "_admin").update({"role": "admin"})

    _upsert_seed_user(
        db,
        os.getenv("SUPERADMIN_USERNAME", "super"),
        os.getenv("SUPERADMIN_PASSWORD", "super"),
        "superadmin",
        os.getenv("SUPERADMIN_EMAIL") or None,
        legacy_usernames=["superadmin"],
    )

    companies = [
        {"name": "PT Maju Jaya", "domain": "majujaya.com", "admin": "admin_maju", "admin_password": "admin123", "emails_per_mailbox": 10000, "mailboxes": ["info@majujaya.com", "sales@majujaya.com", "support@majujaya.com"]},
        {"name": "CV Sukses Abadi", "domain": "suksesabadi.co.id", "admin": "admin_sukses", "admin_password": "admin123", "emails_per_mailbox": 10000, "mailboxes": ["info@suksesabadi.co.id", "order@suksesabadi.co.id", "cs@suksesabadi.co.id"]},
        {"name": "PT Teknologi Digital", "domain": "teknodigital.id", "admin": "admin_teknologi", "admin_password": "admin123", "emails_per_mailbox": 10000, "mailboxes": ["info@teknodigital.id", "hello@teknodigital.id", "care@teknodigital.id"]},
    ]
    sample_ips = [
        "192.168.1.100", "10.0.0.45", "172.16.0.88", "203.0.113.42", "198.51.100.7",
        "185.220.101.1", "45.33.32.156", "104.28.7.1", "91.121.87.34", "51.75.144.1",
        "103.235.46.1", "159.89.192.1", "128.199.0.1", "165.227.0.1", "178.62.0.1",
    ]
    spam_subjects = [
        "You won $10,000,000!!!", "Act Now! Limited Time Offer", "Buy Cheap Medications Online",
        "Work From Home - Earn $5000/week", "Congratulations! You are our Lucky Winner",
        "Your Account Has Been Compromised", "Secret Investment Opportunity",
        "Meet Singles in Your Area Tonight", "Get Rich Quick with Crypto",
        "Re: Your outstanding invoice", "FWD: FWD: FWD: Funny Cat Video",
        "You have been selected for a free iPhone", "Low interest loans approved",
        "Your Tax Refund is Ready", "Nigerian Prince Needs Your Help",
    ]
    phishing_subjects = [
        "Urgent: Verify Your Account Now", "Security Alert: Suspicious Login",
        "Password Reset Request", "Your Invoice #INV-2024-8932",
        "Update Your Payment Information", "Microsoft 365 Account Alert",
        "Netflix - Your Subscription Has Been Paused",
        "DHL - Your Package Could Not Be Delivered",
        "IRS - Tax Filing Notification", "LinkedIn - New Connection Request",
        "PayPal - Unusual Login Detected", "Amazon - Order Confirmation #ORD-99821",
        "Google Account Suspension Notice", "Dropbox - Shared Document",
        "Bank of America - Security Verification",
    ]
    malware_subjects = [
        "SWIFT Notification: Incoming Transfer", "Quarterly Report Q4 2024",
        "Meeting Minutes - Project Alpha", "Resume - Job Application",
        "Purchase Order #PO-78432", "Invoice Overdue Notice",
        "Legal Document for Review", "Employee Benefits Update",
        "System Update Required Immediately", "Conference Registration Confirmation",
        "Partnership Agreement Draft", "NDA - Please Sign Electronically",
        "Audit Report - Confidential", "Server Maintenance Schedule",
        "Zip file - Document Archive",
    ]
    clean_subjects = [
        "Weekly Team Standup Notes", "Lunch Order for Friday", "Office Holiday Schedule",
        "New Employee Onboarding", "IT Support Ticket #4582 Resolved",
        "Project Status Update - Q3", "Customer Feedback Summary",
        "Meeting Invitation: Strategy Session", "Expense Report Approved",
        "Welcome to the Team!", "Payroll Notification June 2024",
        "Company All-Hands Meeting Agenda", "Updated Privacy Policy",
        "Training Session Confirmation", "Office Supply Order Form",
    ]
    senders = {
        "spam": ["noreply@spammyads.com", "winner@lottery-intl.net", "offer@getrichquick.biz", "promo@discount-store.online", "alert@secure-bank-verify.com"],
        "phishing": ["security@paypaI-secure.com", "no-reply@amaz0n-update.net", "support@microsoft-verify.org", "billing@netfliix-account.com", "admin@bankofamerica-login.xyz"],
        "malware": ["hr@company.com", "finance@company.com", "ceo@company.com", "admin@company-update.net", "support@system-patch.com"],
        "clean": ["hr@company.com", "notifications@company.com", "support@company.com", "no-reply@internal.company", "team@workspace.com"],
    }
    clean_domains = ["majujaya.com", "suksesabadi.co.id", "teknodigital.id", "company.org"]

    existing_count = db.query(func.count(QuarantineEmail.id)).scalar() or 0

    all_mailboxes = []
    for comp in companies:
        c_org = db.query(Organization).filter(Organization.name == comp["name"]).first()
        if not c_org:
            c_org = Organization(name=comp["name"], config={"domain": comp["domain"]})
            db.add(c_org)
            db.flush()

        a_user = _upsert_seed_user(db, comp["admin"], comp["admin_password"], "admin", f"{comp['admin']}@{comp['domain']}")
        a_user.organization_id = c_org.id

        for mb_email in comp["mailboxes"]:
            mb_count = db.query(func.count(AdminMailbox.id)).filter(AdminMailbox.email == mb_email).scalar() or 0
            if mb_count == 0:
                mb = AdminMailbox(
                    email=mb_email, domain=comp["domain"],
                    password_hash=hash_password("mail123"),
                    sender_name=mb_email.split("@")[0].title(),
                    assigned_to=comp["admin"], created_by=comp["admin"],
                    is_active=True, storage_bytes=random.randint(100000, 5000000),
                )
                db.add(mb)
            all_mailboxes.append(mb_email)

        em = comp["emails_per_mailbox"]
        if existing_count < 2000:
            batch_size = 500
            now = datetime.utcnow()
            for mb_email in comp["mailboxes"]:
                for batch_start in range(0, em, batch_size):
                    batch_end = min(batch_start + batch_size, em)
                    emails_batch = []
                    for i in range(batch_start, batch_end):
                        r = random.random()
                        if r < 0.50:
                            label, cat = "CLEAN", "clean"
                            subject = random.choice(clean_subjects)
                            score = random.uniform(0.01, 0.25)
                            sender = random.choice(senders["clean"])
                            spf = random.choice(["pass", "pass", "pass", "neutral"])
                            dkim = random.choice(["pass", "pass", "pass", "fail"])
                            dmarc = random.choice(["pass", "pass", "pass", "fail"])
                        elif r < 0.70:
                            label, cat = "WARN", "spam"
                            subject = random.choice(spam_subjects)
                            score = random.uniform(0.30, 0.65)
                            sender = random.choice(senders["spam"])
                            spf, dkim, dmarc = "fail", "fail", "fail"
                        elif r < 0.90:
                            label, cat = "QUARANTINE", "phishing"
                            subject = random.choice(phishing_subjects)
                            score = random.uniform(0.70, 0.98)
                            sender = random.choice(senders["phishing"])
                            spf, dkim, dmarc = "fail", "none", "fail"
                        else:
                            label, cat = "QUARANTINE", "malware"
                            subject = random.choice(malware_subjects)
                            score = random.uniform(0.75, 0.99)
                            sender = random.choice(senders["malware"])
                            spf, dkim, dmarc = "pass", "fail", "none"

                        rid = f"seed-{comp['name'][:8]}-{mb_email.split('@')[0]}-{i}"
                        ts = (now - timedelta(hours=random.randint(0, 720), minutes=random.randint(0, 59))).isoformat()
                        fused = round(score, 4)
                        emails_batch.append({
                            "email_id": rid, "received_at": ts,
                            "label": label, "fused_score": fused,
                            "sa_score": round(min(score * 0.8 + random.uniform(-0.1, 0.1), 1.0), 4),
                            "ml_probability": round(min(score * 0.7 + random.uniform(-0.05, 0.05), 1.0), 4),
                            "anomaly_score": round(min(score * 0.3 + random.uniform(-0.1, 0.1), 1.0), 4),
                            "category": cat, "subject": subject[:200],
                            "sender": sender, "recipient_list": mb_email,
                            "model_version": "xgb_v3.2.0",
                            "organization_id": c_org.id,
                            "spf_result": spf, "dkim_result": dkim, "dmarc_result": dmarc,
                            "routing_reason": f"Fusion score {fused} - {cat.upper()} detection" if cat != "clean" else "Clean email - delivered",
                            "xai_summary": f"{'Threat' if cat != 'clean' else 'Safe'} - {cat.replace('_', ' ').title()} detected with {fused:.0%} confidence",
                            "created_at": now - timedelta(hours=random.randint(0, 720)),
                        })

                    db.execute(
                        QuarantineEmail.__table__.insert(),
                        emails_batch,
                    )
                    db.commit()

        existing_admin_logs = db.query(func.count(AuditLog.id)).filter(AuditLog.user == comp["admin"]).scalar() or 0
        if existing_admin_logs < 3:
            for i in range(10):
                log_entry = AuditLog(
                    user=comp["admin"], action=random.choice([
                        "login", "manage_users", "manage_mailboxes", "view_reports",
                        "update_settings", "login", "review_quarantine",
                    ]),
                    ip_address=random.choice(sample_ips),
                    details=f"Admin activity from {comp['admin']} - {random.choice(['web', 'api'])} client",
                    created_at=datetime.utcnow() - timedelta(hours=random.randint(0, 168)),
                )
                db.add(log_entry)

    seed_realistic_emails(db, all_mailboxes)
    db.commit()
    db.close()


def seed_realistic_emails(db, all_mailboxes=None):
    """Seed realistic emails from spam_emails/ folder - assigned to admin mailboxes."""
    existing_raw = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.raw_content != "",
        QuarantineEmail.raw_content.isnot(None),
    ).scalar() or 0
    if existing_raw > 0:
        return

    if not all_mailboxes:
        all_mailboxes = [r[0] for r in db.query(AdminMailbox.email).filter(AdminMailbox.is_active == True).all()]
    if not all_mailboxes:
        return

    import random
    now = datetime.utcnow()
    all_orgs = {o.id: o for o in db.query(Organization).all()}
    mb_org_map = {}
    for mb_email in all_mailboxes:
        domain = mb_email.split("@")[1] if "@" in mb_email else ""
        for oid, o in all_orgs.items():
            if (o.config or {}).get("domain") == domain or domain in str(o.name).lower():
                mb_org_map[mb_email] = oid
                break
        if mb_email not in mb_org_map:
            mb_org_map[mb_email] = list(all_orgs.keys())[0] if all_orgs else None

    import random
    email_data = []
    base_id = 0

    category_templates = {
        "clean": {"subjects": [
            "Weekly Team Standup Notes", "Lunch Order for Friday", "Office Holiday Schedule",
            "New Employee Onboarding", "IT Support Ticket Resolved",
            "Project Status Update", "Customer Feedback Summary",
            "Meeting Invitation: Strategy Session", "Expense Report Approved",
            "Welcome to the Team!", "Payroll Notification",
            "Company All-Hands Meeting Agenda", "Updated Privacy Policy",
            "Training Session Confirmation", "Office Supply Order Form",
        ], "senders": ["hr@company.com", "notifications@company.com", "support@company.com", "no-reply@internal.company", "team@workspace.com"],
           "label": "CLEAN", "score_range": (0.01, 0.25),
           "spf": ["pass", "pass", "pass", "neutral"],
           "dkim": ["pass", "pass", "pass", "fail"],
           "dmarc": ["pass", "pass", "pass", "fail"]},
        "spam": {"subjects": [
            "You won $10,000,000!!!", "Act Now! Limited Time Offer", "Work From Home - Earn $5000/week",
            "Congratulations! You are our Lucky Winner", "Your Account Has Been Compromised",
            "Secret Investment Opportunity", "Meet Singles in Your Area Tonight",
            "Get Rich Quick with Crypto", "Re: Your outstanding invoice",
            "You have been selected for a free iPhone", "Low interest loans approved",
            "Your Tax Refund is Ready",
        ], "senders": ["noreply@spammyads.com", "winner@lottery-intl.net", "offer@getrichquick.biz", "promo@discount-store.online", "alert@secure-bank-verify.com"],
           "label": "WARN", "score_range": (0.30, 0.65),
           "spf": ["fail"], "dkim": ["fail"], "dmarc": ["fail"]},
        "phishing": {"subjects": [
            "Urgent: Verify Your Account Now", "Security Alert: Suspicious Login",
            "Password Reset Request", "Your Invoice Overdue",
            "Update Your Payment Information", "Microsoft 365 Account Alert",
            "Netflix - Your Subscription Has Been Paused",
            "IRS - Tax Filing Notification", "LinkedIn - New Connection Request",
            "PayPal - Unusual Login Detected", "Google Account Suspension Notice",
            "Bank of America - Security Verification",
        ], "senders": ["security@paypaI-secure.com", "no-reply@amaz0n-update.net", "support@microsoft-verify.org", "billing@netfliix-account.com", "admin@bankofamerica-login.xyz"],
           "label": "QUARANTINE", "score_range": (0.70, 0.98),
           "spf": ["fail"], "dkim": ["none"], "dmarc": ["fail"]},
        "malware": {"subjects": [
            "SWIFT Notification: Incoming Transfer", "Quarterly Report Q4 2024",
            "Meeting Minutes - Project Alpha", "Purchase Order - Sign Required",
            "Invoice Overdue Notice", "Legal Document for Review",
            "System Update Required Immediately", "Audit Report - Confidential",
            "Server Maintenance Schedule", "Zip file - Document Archive",
        ], "senders": ["hr@company.com", "finance@company.com", "ceo@company.com", "admin@company-update.net", "support@system-patch.com"],
           "label": "QUARANTINE", "score_range": (0.75, 0.99),
           "spf": ["pass"], "dkim": ["fail"], "dmarc": ["none"]},
    }

    categories_order = ["clean", "spam", "phishing", "malware"]
    weights = [0.50, 0.20, 0.20, 0.10]  # 50% clean, 20% spam, 20% phish, 10% malware
    emails_per_mailbox = 10000

    for mb_email in all_mailboxes:
        org_id = mb_org_map.get(mb_email)
        for i in range(emails_per_mailbox):
            cat = random.choices(categories_order, weights=weights, k=1)[0]
            tmpl = category_templates[cat]
            subject = random.choice(tmpl["subjects"])
            sender = random.choice(tmpl["senders"])
            score = random.uniform(*tmpl["score_range"])
            fused = round(score, 4)
            spf = random.choice(tmpl["spf"])
            dkim = random.choice(tmpl["dkim"])
            dmarc = random.choice(tmpl["dmarc"])
            rid = f"seed-{mb_email.replace('@', '-').replace('.', '-')}-{i}"
            ts = (now - timedelta(hours=random.randint(0, 720), minutes=random.randint(0, 59))).isoformat()
            email_data.append({
                "email_id": rid, "received_at": ts,
                "label": tmpl["label"], "fused_score": fused,
                "sa_score": round(min(score * 0.8 + random.uniform(-0.1, 0.1), 1.0), 4),
                "ml_probability": round(min(score * 0.7 + random.uniform(-0.05, 0.05), 1.0), 4),
                "anomaly_score": round(min(score * 0.3 + random.uniform(-0.1, 0.1), 1.0), 4),
                "category": cat, "subject": subject[:200],
                "sender": sender, "recipient_list": mb_email,
                "model_version": "xgb_v3.2.0",
                "organization_id": org_id,
                "spf_result": spf, "dkim_result": dkim, "dmarc_result": dmarc,
                "routing_reason": f"Fusion score {fused} - {cat.upper()} detection" if cat != "clean" else "Clean email - delivered",
                "xai_summary": f"{'Threat' if cat != 'clean' else 'Safe'} - {cat.title()} detected with {fused:.0%} confidence",
                "created_at": now - timedelta(hours=random.randint(0, 720)),
                "status": "released" if cat == "clean" else "pending",
            })

    db.execute(QuarantineEmail.__table__.insert(), email_data)
    db.commit()


seed_admin()

# ─── Auth Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/auth/me")
async def auth_me(request: Request, db: Session = Depends(get_db)):
    # Priority 1: dashboard token (admin / superadmin / user)
    token = request.cookies.get("access_token")
    # Priority 2: mailbox token (webmail users)
    mailbox_token = request.cookies.get("mailbox_token")
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"auth_me: client={client_host} dashboard_token={bool(token)} mailbox_token={bool(mailbox_token)} url={request.url.path}")

    # --- Try dashboard token first ---
    if token:
        try:
            payload = decode_token(token)
            if payload.get("role") != "mailbox":
                # This is a real dashboard user (admin / superadmin / user)
                user = db.query(User).filter(User.username == payload.get("sub")).first()
                if user and user.is_active:
                    logger.info(f"auth_me: authenticated dashboard user={user.username} role={user.role}")
                    return JSONResponse({
                        "authenticated": True,
                        "user": {"username": user.username, "role": user.role}
                    })
        except Exception as e:
            logger.warning(f"auth_me: dashboard token decode failed: {e}")

    # --- Try mailbox token ---
    if mailbox_token:
        try:
            payload = decode_token(mailbox_token)
            if payload.get("role") == "mailbox":
                mailbox = resolve_active_mailbox(
                    db,
                    payload.get("mailbox_id"),
                    payload.get("mailbox_email"),
                    missing_status_code=401,
                    missing_detail="Mailbox is disabled or inactive",
                    inactive_detail="Mailbox is disabled or inactive",
                )
                return JSONResponse({
                    "authenticated": True,
                    "user": {
                        "username": mailbox.email.lower(),
                        "role": "mailbox",
                        "mailbox_id": str(mailbox.id),
                        "mailbox_email": mailbox.email.lower(),
                    }
                })
        except Exception as e:
            logger.warning(f"auth_me: mailbox token decode failed: {e}")

    logger.warning(f"auth_me: no valid session from {client_host}")
    return JSONResponse({"authenticated": False, "user": None})


@app.post("/api/auth/login")
@limiter.limit("20/minute")
async def auth_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
                     db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "Invalid username or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    token = create_access_token({"sub": user.username, "role": user.role})
    response = JSONResponse({
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
    })
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production",
        path="/",
    )
    return response


@app.post("/api/auth/logout")
async def auth_logout():
    # Clear only the dashboard session cookie.
    # The mailbox_token (webmail) is intentionally NOT cleared here.
    response = JSONResponse({"ok": True})
    response.delete_cookie("access_token")
    response.delete_cookie("access_token", path="/")
    return response


@app.post("/api/mailboxes/logout")
async def mailbox_logout():
    # Clear only the mailbox session cookie, leaving the dashboard session intact.
    response = JSONResponse({"ok": True})
    response.delete_cookie("mailbox_token")
    response.delete_cookie("mailbox_token", path="/")
    return response


# ─── Google OAuth ───────────────────────────────────────────────────────

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8082/auth/google/callback")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def get_redirect_uri(request=None):
    """Return configured redirect URI, or build dynamically from request."""
    env_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if env_uri:
        return env_uri
    if request:
        base = str(request.base_url).rstrip("/")
        return f"{base}/auth/google/callback"
    return "http://localhost:8412/auth/google/callback"


@app.get("/auth/google/login")
async def google_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        return JSONResponse({"error": "Google OAuth not configured"}, status_code=500)
    redirect_uri = get_redirect_uri(request)
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", error: str = "", db: Session = Depends(get_db)):
    if error:
        return RedirectResponse(url="/login?error=google_auth_failed")
    if not code:
        return RedirectResponse(url="/login?error=no_code")

    redirect_uri = get_redirect_uri(request)
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            return RedirectResponse(url="/login?error=token_exchange_failed")
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {access_token}"
        })
        if userinfo_resp.status_code != 200:
            return RedirectResponse(url="/login?error=userinfo_failed")
        userinfo = userinfo_resp.json()

    google_email = userinfo.get("email", "")
    google_name = userinfo.get("name", google_email.split("@")[0])

    if not google_email:
        return RedirectResponse(url="/login?error=no_email")

    user = db.query(User).filter(User.email == google_email).first()
    if not user:
        return RedirectResponse(url="/login?error=Akun+Google+ini+belum+terdaftar.+Hubungi+super+admin+untuk+persetujuan.")

    if not user.is_active:
        return RedirectResponse(url="/login?error=account_disabled")

    token = create_access_token({"sub": user.username, "role": user.role})
    if user.role == "superadmin":
        redirect_url = "/super-admin/dashboard"
    elif user.role == "admin":
        redirect_url = "/admin/dashboard"
    else:
        redirect_url = "/inbox"
    response = RedirectResponse(url=redirect_url)
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production",
        path="/",
    )
    return response


# ─── Profile Endpoints ─────────────────────────────────────────────────

@app.get("/api/auth/profile")
async def get_profile(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    if payload.get("role") == "mailbox":
        mailbox = resolve_active_mailbox(
            db,
            payload.get("mailbox_id"),
            payload.get("mailbox_email"),
        )
        return {
            "username": mailbox.email.lower(),
            "role": "mailbox",
            "is_active": mailbox.is_active,
            "created_at": str(mailbox.created_at) if mailbox.created_at else None,
            "mailbox_id": str(mailbox.id),
            "mailbox_email": mailbox.email.lower(),
            "domain": mailbox.domain,
            "sender_name": mailbox.sender_name or "",
        }
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": str(user.created_at) if user.created_at else None,
        "organization_id": user.organization_id,
    }


@app.post("/api/auth/change-password")
async def change_password(request: Request, data: dict, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")
    old_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")
    if not verify_password(old_pw, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(new_pw) < 4:
        raise HTTPException(400, "New password must be at least 4 characters")
    user.hashed_password = hash_password(new_pw)
    db.commit()
    log_audit(db, user.username, "change_password", details="Password changed")
    return {"ok": True, "message": "Password changed successfully"}


@app.put("/api/auth/profile")
async def update_profile(request: Request, data: dict, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")

    current_password = data.get("current_password", "")
    new_username = (data.get("username") or user.username).strip()
    new_password = data.get("new_password", "")

    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if not new_username:
        raise HTTPException(400, "Username is required")
    if new_username != user.username:
        existing = db.query(User).filter(User.username == new_username).first()
        if existing:
            raise HTTPException(400, "Username already exists")
    if new_password and len(new_password) < 4:
        raise HTTPException(400, "New password must be at least 4 characters")

    old_username = user.username
    user.username = new_username
    if new_password:
        user.hashed_password = hash_password(new_password)
    db.commit()
    log_audit(db, new_username, "update_profile", details=f"Profile updated for {old_username}")

    response = JSONResponse({"ok": True, "message": "Profile updated successfully", "username": new_username})
    if new_username != old_username:
        access_token = create_access_token({"sub": new_username, "role": user.role})
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    return response


@app.get("/api/auth/api-keys")
async def list_api_keys(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")
    keys = db.query(ApiKey).filter(
        ApiKey.organization_id == user.organization_id
    ).all() if user.organization_id else []
    return [
        {"id": k.id, "name": k.name, "is_active": k.is_active, "rate_limit": k.rate_limit, "created_at": str(k.created_at)}
        for k in keys
    ]


@app.post("/api/auth/api-keys")
async def create_api_key(request: Request, data: dict, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")
    name = data.get("name", "Untitled Key")
    import secrets, hashlib
    raw_key = f"cm_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = ApiKey(
        key_hash=key_hash, name=name,
        organization_id=user.organization_id,
        is_active=True, rate_limit=data.get("rate_limit", 100)
    )
    db.add(api_key)
    db.commit()
    log_audit(db, user.username, "create_api_key", details=f"Created API key: {name}")
    return {"ok": True, "key": raw_key, "name": name, "id": api_key.id}


@app.delete("/api/auth/api-keys/{key_id}")
async def delete_api_key(key_id: int, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(404, "API key not found")
    db.delete(api_key)
    db.commit()
    log_audit(db, user.username, "delete_api_key", details=f"Deleted API key ID: {key_id}")
    return {"ok": True, "message": "API key revoked"}


@app.get("/api/auth/activity")
async def get_activity(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")
    logs = db.query(AuditLog).filter(
        AuditLog.user == user.username
    ).order_by(AuditLog.created_at.desc()).limit(20).all()
    return [
        {"action": log.action, "details": log.details, "created_at": str(log.created_at), "ip_address": log.ip_address}
        for log in logs
    ]


# ─── API endpoints and static React SPA routing ─────────────────────────


@app.get("/api/feedback-export")
async def feedback_export(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    feedbacks = db.query(Feedback).all()
    return [
        {
            "id": f.id,
            "email_id": f.email_id,
            "feedback_type": f.feedback_type,
            "notes": f.notes,
            "created_at": str(f.created_at),
        }
        for f in feedbacks
    ]


@app.get("/.well-known/security.txt")
async def security_txt():
    return PlainTextResponse(
        "Contact: mailto:security@lodaya.id\n"
        "Preferred-Languages: en, id\n"
        "Canonical: https://lodaya.id/.well-known/security.txt\n"
        "Policy: https://lodaya.id/security-policy\n"
    )


@app.get("/api/health")
async def api_health(db: Session = Depends(get_db)):
    try:
        db.execute(func.count(QuarantineEmail.id))
        db_status = "connected"
    except Exception:
        db_status = "error"
    return {
        "status": "healthy",
        "version": "3.0.0",
        "database": db_status,
        "websocket_connections": len(manager.active_connections),
        "uptime": "N/A",
    }


@app.get("/api/stats")
async def api_stats(db: Session = Depends(get_db)):
    active_query = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
    total = active_query.count() or 0
    trash_count = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.status == "trash").scalar() or 0
    quarantine_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    ).scalar() or 0
    warn_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "WARN",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    ).scalar() or 0
    clean_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "CLEAN",
        QuarantineEmail.status != "trash",
    ).scalar() or 0
    avg_anomaly = db.query(func.avg(QuarantineEmail.anomaly_score)).scalar() or 0
    avg_fused = db.query(func.avg(QuarantineEmail.fused_score)).scalar() or 0
    # Per-category breakdown
    cat_rows = db.query(
        QuarantineEmail.category, func.count(QuarantineEmail.id)
    ).filter(
        QuarantineEmail.category != "",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    ).group_by(QuarantineEmail.category).all()
    categories = {row[0]: row[1] for row in cat_rows}
    return {
        "total": total,
        "trash": trash_count,
        "quarantine": quarantine_count,
        "warn": warn_count,
        "clean": clean_count,
        "avg_anomaly_score": round(float(avg_anomaly), 4),
        "avg_fused_score": round(float(avg_fused), 4),
        "categories": categories,
    }


# ─── New API Endpoints & SPA Routing ───────────────────────────────────────────

def get_authenticated_api_user(request: Request, db: Session = Depends(get_db)) -> dict:
    # Prefer the dashboard token; fall back to mailbox_token for webmail endpoints.
    token = request.cookies.get("access_token") or request.cookies.get("mailbox_token")
    if not token:
        logger.warning(f"get_authenticated_api_user: no cookie from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
        if payload.get("role") == "mailbox":
            mailbox = resolve_active_mailbox(
                db,
                payload.get("mailbox_id"),
                payload.get("mailbox_email"),
                missing_status_code=401,
                missing_detail="Mailbox is disabled or inactive",
                inactive_detail="Mailbox is disabled or inactive",
            )
            return {
                "username": mailbox.email.lower(),
                "role": "mailbox",
                "mailbox_id": str(mailbox.id),
                "mailbox_email": mailbox.email.lower(),
            }
        user = db.query(User).filter(User.username == payload.get("sub")).first()
        if not user or not user.is_active:
            logger.warning(f"get_authenticated_api_user: user {payload.get('sub')} not found or inactive")
            raise HTTPException(status_code=401, detail="Account is disabled or inactive")
        return {"username": user.username, "role": user.role}
    except HTTPException:
        raise
    except Exception:
        logger.warning(f"get_authenticated_api_user: token decode failed")
        raise HTTPException(status_code=401, detail="Token is invalid or expired")


class FalsePositiveRequest(BaseModel):
    notes: str = ""


CATEGORY_LABEL_MAP = {
    "transaction": "CLEAN",
    "customer_service": "CLEAN",
    "internal_document": "CLEAN",
    "b2b": "CLEAN",
    "spam": "QUARANTINE",
    "phishing": "QUARANTINE",
    "malware": "QUARANTINE",
}


def email_belongs_to_identity(email_record: QuarantineEmail, identity: str = "") -> bool:
    target = (identity or "").strip().lower()
    if not target:
        return False

    def _addresses(value: str) -> list[str]:
        return [addr.lower() for _, addr in getaddresses([value or ""]) if addr]

    return target in _addresses(email_record.recipient_list) or target in _addresses(email_record.sender)


def _mailbox_identity_filters(column, identity: str):
    target = (identity or "").strip().lower()
    if not target:
        return []
    variants = {
        target,
        f"{target},%",
        f"%, {target}",
        f"%, {target},%",
        f"{target};%",
        f"%; {target}",
        f"%; {target};%",
    }
    return [column.ilike(pattern) for pattern in variants]


def resolve_active_mailbox(
    db: Session,
    mailbox_id: str | int | None = None,
    mailbox_email: str | None = None,
    *,
    missing_status_code: int = 404,
    missing_detail: str = "Mailbox not found",
    inactive_detail: str = "Mailbox is disabled or inactive",
) -> AdminMailbox:
    mailbox_query = db.query(AdminMailbox).filter(AdminMailbox.is_active == True)
    normalized_email = (mailbox_email or "").strip().lower()
    mailbox_identifier = str(mailbox_id).strip().lower() if mailbox_id not in (None, "") else ""
    lookup_email = normalized_email

    if mailbox_identifier:
        try:
            mailbox_query = mailbox_query.filter(AdminMailbox.id == int(mailbox_identifier))
        except (TypeError, ValueError):
            lookup_email = lookup_email or mailbox_identifier

    if lookup_email:
        mailbox_query = mailbox_query.filter(AdminMailbox.email == lookup_email)

    mailbox = mailbox_query.first()
    if not mailbox:
        raise HTTPException(status_code=missing_status_code, detail=missing_detail)
    if lookup_email and mailbox.email.lower() != lookup_email:
        raise HTTPException(status_code=missing_status_code, detail=inactive_detail)
    return mailbox


def ensure_email_access(email_record: QuarantineEmail, user_info: dict):
    if user_info["role"] in ["superadmin", "admin"]:
        return
    if email_belongs_to_identity(email_record, user_info.get("mailbox_email") or user_info.get("username")):
        return
    raise HTTPException(status_code=403, detail="You do not have permission to access this email")

CATEGORY_ICONS = {
    "transaction": "receipt",
    "customer_service": "support",
    "internal_document": "folder",
    "b2b": "briefcase",
    "spam": "spam",
    "phishing": "phishing",
    "malware": "bug",
}


def display_category(email: QuarantineEmail) -> str:
    category = (email.category or "").lower()
    label = (email.label or "").upper()
    if label == "WARN":
        return "spam"
    if label == "QUARANTINE" and category not in {"spam", "phishing", "malware"}:
        return "spam"
    return category or label.lower()


def linkify_plain_text(content: str) -> str:
    escaped = html.escape(content or "")
    linked = re.sub(
        r"(https?://[^\s<]+)",
        r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
        escaped,
    )
    return linked.replace("\n", "<br>")


def plain_email_body(content: str = "") -> str:
    body = (content or "").replace("\r\n", "\n")
    if "\n\n" in body:
        first_block, rest = body.split("\n\n", 1)
        looks_like_header = any(
            re.match(r"^(from|to|subject|date|message-id|reply-to|cc|bcc|spf|dkim|dmarc):\s*", line.strip(), re.I)
            for line in first_block.split("\n")
            if line.strip()
        )
        if looks_like_header:
            body = rest
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return " ".join(html.unescape(body).split())


def append_thread_context(body: str, original: QuarantineEmail, action: str) -> str:
    if not original:
        return body
    marker = "---------- Forwarded message ---------" if action == "forward" else "---------- Original message ---------"
    if marker in (body or ""):
        return body
    return "\n".join([
        body or "",
        "",
        marker,
        f"Dari: {original.sender or '-'}",
        f"Tanggal: {original.received_at or '-'}",
        f"Subjek: {original.subject or '(tanpa subjek)'}",
        f"Kepada: {original.recipient_list or '-'}",
        "",
        plain_email_body(original.raw_content),
    ])


THREAD_PREFIX_RE = re.compile(r"^\s*(re|fw|fwd)\s*:\s*", re.I)
EMAIL_ADDRESS_RE = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", re.I)


def normalize_thread_subject(subject: str = "") -> str:
    value = (subject or "").strip()
    while True:
        next_value = THREAD_PREFIX_RE.sub("", value).strip()
        if next_value == value:
            return next_value.lower()
        value = next_value


def thread_participants(email_record: QuarantineEmail) -> set[str]:
    text = f"{email_record.sender or ''}, {email_record.recipient_list or ''}"
    return {match.lower() for match in EMAIL_ADDRESS_RE.findall(text)}


def thread_sort_value(email_record: QuarantineEmail) -> float:
    value = email_record.received_at or email_record.created_at
    if hasattr(value, "timestamp"):
        if getattr(value, "tzinfo", None) is None:
            value = value.replace(tzinfo=APP_TIMEZONE)
        return value.timestamp()
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=APP_TIMEZONE)
            return parsed.timestamp()
        except Exception:
            return 0.0
    return 0.0


def thread_message_payload(email_record: QuarantineEmail) -> dict:
    timestamp = email_record.received_at.isoformat() if hasattr(email_record.received_at, "isoformat") else str(email_record.received_at) if email_record.received_at else None
    label = (email_record.label or "").upper()
    return {
        "email_id": email_record.email_id,
        "sender": email_record.sender,
        "subject": email_record.subject,
        "label": email_record.label,
        "category": display_category(email_record),
        "status": email_record.status,
        "is_read": getattr(email_record, "is_read", False),
        "direction": "draft" if label == "DRAFT" else "sent" if label == "SENT" else "incoming",
        "received_at": timestamp,
        "raw_content": email_record.raw_content,
        "recipient_list": email_record.recipient_list,
        "attachments": attachment_summaries(email_record),
    }


def find_thread_messages(db: Session, email_record: QuarantineEmail) -> list[QuarantineEmail]:
    base_subject = normalize_thread_subject(email_record.subject)
    if not base_subject:
        return [email_record]
    participants = thread_participants(email_record)
    candidates = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
    ).all()
    messages = []
    seen = set()
    for candidate in candidates:
        if candidate.email_id in seen:
            continue
        if normalize_thread_subject(candidate.subject) != base_subject:
            continue
        candidate_participants = thread_participants(candidate)
        if participants and candidate_participants and not (participants & candidate_participants):
            continue
        seen.add(candidate.email_id)
        messages.append(candidate)
    if not messages:
        return [email_record]
    messages.sort(key=thread_sort_value)
    return messages


def delivery_failure_body(recipients: list[str], reason: str) -> str:
    recipient_text = ", ".join(recipients)
    safe_reason = reason or "Server tujuan menolak atau tidak dapat menerima pesan."
    return (
        "Alamat tidak dapat ditemukan\n\n"
        f"Pesan Anda tidak terkirim ke {recipient_text}.\n\n"
        "Kemungkinan penyebab:\n"
        "- alamat email salah ketik,\n"
        "- domain email tidak ditemukan,\n"
        "- mailbox tujuan tidak dapat menerima email,\n"
        "- atau server SMTP menolak pengiriman.\n\n"
        f"Tanggapan server:\n{safe_reason}"
    )


def save_delivery_failure(
    db: Session,
    sender_address: str,
    recipients: list[str],
    subject: str,
    body: str,
    reason: str,
    username: str,
    request: Request,
) -> str:
    failure_id = f"failed_{uuid.uuid4().hex[:12]}"
    failure_subject = f"Alamat tidak dapat ditemukan: {subject or '(tanpa subjek)'}"
    failure_content = delivery_failure_body(recipients, reason)
    failure_entry = QuarantineEmail(
        email_id=failure_id,
        received_at=app_now_iso(),
        label="CLEAN",
        fused_score=0.0,
        sa_score=0.0,
        ml_probability=0.0,
        anomaly_score=0.0,
        xai_summary="Outbound delivery failed",
        routing_reason=f"Delivery failed to {', '.join(recipients)}",
        raw_content=linkify_plain_text(failure_content),
        attachments_json="[]",
        status="pending",
        category="delivery_failed",
        subject=failure_subject,
        sender="mailer-daemon@cognimail.local",
        recipient_list=sender_address,
        spf_result="SYSTEM",
        dkim_result="SYSTEM",
        dmarc_result="SYSTEM",
        created_at=app_now(),
    )
    db.add(failure_entry)
    log_audit(
        db,
        username,
        "send_email_failed",
        failure_id,
        request.client.host if request.client else None,
        f"Failed to send to {', '.join(recipients)}: {reason}",
    )
    db.commit()
    return failure_id


def validate_recipient_domains(recipients: list[str]) -> None:
    try:
        import dns.resolver
        import dns.exception
    except Exception:
        return

    invalid_domains = []
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 5.0
    resolver.timeout = 3.0
    for recipient in recipients:
        domain = recipient.rsplit("@", 1)[-1]
        try:
            resolver.resolve(domain, "MX")
            continue
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
            try:
                resolver.resolve(domain, "A")
                continue
            except Exception:
                invalid_domains.append(domain)
        except Exception:
            continue
    if invalid_domains:
        unique_domains = sorted(set(invalid_domains))
        raise ValueError(f"Domain email tidak dapat ditemukan: {', '.join(unique_domains)}")


def attachment_summaries(email_record: QuarantineEmail) -> list[dict]:
    try:
        attachments = json.loads(email_record.attachments_json or "[]")
    except Exception:
        return []
    summaries = []
    for idx, item in enumerate(attachments):
        data = item.get("data") or item.get("content_base64") or ""
        summaries.append({
            "index": item.get("index", idx),
            "filename": item.get("filename", f"attachment-{idx + 1}"),
            "content_type": item.get("content_type", "application/octet-stream"),
            "size": item.get("size", 0),
            "stored": bool(item.get("stored", bool(data))),
        })
    return summaries


AUTH_RESULT_VALUES = ("pass", "fail", "softfail", "neutral", "none", "temperror", "permerror", "policy")


def _extract_email_domain(sender: str = "") -> str:
    match = re.search(r"@([A-Za-z0-9.-]+)", sender or "")
    return match.group(1).lower() if match else ""


def _is_local_test_email(sender: str = "", raw_content: str = "") -> bool:
    domain = _extract_email_domain(sender)
    if domain.endswith(".test") or domain in {"local.test", "localhost", "example.test"}:
        return True
    if "@local" in (sender or "").lower():
        return True
    return not re.search(r"(?im)^(from|to|subject|authentication-results|received-spf):", raw_content or "")


def _find_auth_result(source: str, key: str) -> str:
    match = re.search(
        rf"\b{re.escape(key)}\s*=\s*({'|'.join(AUTH_RESULT_VALUES)})\b",
        source or "",
        re.IGNORECASE,
    )
    return match.group(1).upper() if match else ""


def derive_auth_results(raw_content: str = "", sender: str = "") -> dict:
    try:
        msg = Parser(policy=policy.default).parsestr(raw_content or "")
        auth_headers = " ".join(msg.get_all("Authentication-Results", []) or [])
        received_spf = " ".join(msg.get_all("Received-SPF", []) or [])
        dkim_signature = bool(msg.get("DKIM-Signature"))
    except Exception:
        auth_headers = ""
        received_spf = ""
        dkim_signature = False

    combined = f"{auth_headers} {received_spf}"
    spf = _find_auth_result(combined, "spf") or _find_auth_result(received_spf, "receiver")
    dkim = _find_auth_result(auth_headers, "dkim")
    dmarc = _find_auth_result(auth_headers, "dmarc")

    if not spf and received_spf:
        lowered = received_spf.lower()
        spf = next((value.upper() for value in AUTH_RESULT_VALUES if value in lowered), "")
    if not dkim and dkim_signature:
        dkim = "SIGNED"

    fallback = "LOCAL TEST" if _is_local_test_email(sender, raw_content) else "N/A"
    return {
        "spf_result": spf or fallback,
        "dkim_result": dkim or fallback,
        "dmarc_result": dmarc or fallback,
    }


@app.get("/api/emails")
async def api_get_emails(
    request: Request,
    label: str = Query(None),
    category: str = Query(None),
    folder: str = Query(None),
    q: str = Query(None),
    mailbox: str = Query(None),
    mailbox_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    purge_expired_emails(db)
    db.commit()
    
    query = db.query(QuarantineEmail)
    mailbox = (mailbox or "").strip().lower()
    mailbox_id = (mailbox_id or "").strip()
    if user_info["role"] == "mailbox":
        mailbox = user_info["mailbox_email"]
        mailbox_id = user_info["mailbox_id"]
    elif user_info["role"] == "user" and not mailbox and not mailbox_id:
        user = db.query(User).filter(User.username == user_info["username"]).first()
        user_email = user.email if user and user.email else None
        if user_email:
            mb = db.query(AdminMailbox).filter(
                AdminMailbox.email == user_email.lower(),
                AdminMailbox.is_active == True,
            ).first()
            if mb:
                mailbox = mb.email
                mailbox_id = str(mb.id)
    
    if folder == "trash":
        query = query.filter(QuarantineEmail.status == "trash")
    else:
        query = query.filter(QuarantineEmail.status != "trash")
        if folder != "draft":
            query = query.filter(QuarantineEmail.label != "DRAFT")

    if mailbox:
        mailbox_record = resolve_active_mailbox(db, mailbox_id, mailbox, missing_status_code=404, missing_detail="Mailbox not found")
        query = query.filter(or_(
            *_mailbox_identity_filters(QuarantineEmail.recipient_list, mailbox_record.email),
            *_mailbox_identity_filters(QuarantineEmail.sender, mailbox_record.email),
        ))

    if folder == "all":
        query = query.filter(QuarantineEmail.label.notin_(["SENT", "DRAFT"]))
    elif folder == "draft":
        query = query.filter(QuarantineEmail.label == "DRAFT")
    elif category and category in CATEGORY_LABEL_MAP:
        mapped_label = CATEGORY_LABEL_MAP[category]
        if category == "phishing":
            query = query.filter(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "phishing")
        elif category == "spam":
            query = query.filter(or_(
                and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"),
                and_(
                    QuarantineEmail.label == "QUARANTINE",
                    or_(
                        QuarantineEmail.category == "",
                        QuarantineEmail.category.is_(None),
                        ~QuarantineEmail.category.in_(["spam", "phishing", "malware"]),
                    ),
                ),
                QuarantineEmail.label == "WARN",
            ))
        elif category == "malware":
            query = query.filter(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == category)
        else:
            query = query.filter(QuarantineEmail.label == mapped_label, QuarantineEmail.category == category)
        if category in ["spam", "phishing", "malware"]:
            query = query.filter(QuarantineEmail.status != "released")
    elif label:
        query = query.filter(QuarantineEmail.label == label)
        if label in ["WARN", "QUARANTINE"]:
            query = query.filter(QuarantineEmail.status != "released")
    elif not q and folder != "trash":
        query = query.filter(
            QuarantineEmail.label == "CLEAN",
            QuarantineEmail.status != "trash",
        )
    
    if q:
        terms = [term for term in re.split(r"\s+", q.strip()) if term]
        searchable_fields = [
            QuarantineEmail.email_id,
            QuarantineEmail.subject,
            QuarantineEmail.sender,
            QuarantineEmail.recipient_list,
            QuarantineEmail.raw_content,
            QuarantineEmail.category,
            QuarantineEmail.label,
            QuarantineEmail.status,
            QuarantineEmail.xai_summary,
            QuarantineEmail.routing_reason,
            QuarantineEmail.spf_result,
            QuarantineEmail.dkim_result,
            QuarantineEmail.dmarc_result,
            QuarantineEmail.attachments_json,
        ]
        for term in terms:
            pattern = f"%{term}%"
            query = query.filter(or_(*[field.ilike(pattern) for field in searchable_fields]))
    
    total = query.count()
    
    offset = (page - 1) * page_size
    emails = (
        query
        .order_by(QuarantineEmail.received_at.desc(), QuarantineEmail.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    
    emails_data = []
    for email in emails:
        cat = display_category(email)
        raw_text = email.raw_content or ""
        if "\n\n" in raw_text:
            raw_text = raw_text.split("\n\n", 1)[1]
        raw_text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw_text)
        raw_text = re.sub(r"(?s)<[^>]+>", " ", raw_text)
        body_preview = " ".join(html.unescape(raw_text).replace("\r", "\n").split())[:180]
        emails_data.append({
            "email_id": email.email_id,
            "sender": email.sender,
            "subject": email.subject,
            "body_preview": body_preview,
            "label": email.label,
            "category": cat,
            "status": email.status,
            "fused_score": email.fused_score,
            "ml_probability": 0.0 if user_info["role"] == "user" else email.ml_probability,
            "sa_score": 0.0 if user_info["role"] == "user" else email.sa_score,
            "anomaly_score": 0.0 if user_info["role"] == "user" else email.anomaly_score,
            "has_attachments": bool(email.attachments_json and email.attachments_json != "[]"),
            "received_at": email.received_at.isoformat() if hasattr(email.received_at, "isoformat") else str(email.received_at) if email.received_at else None,
            "recipient_list": email.recipient_list,
            "is_read": getattr(email, "is_read", False),
        })
    
    return {"emails": emails_data, "total": total}


@app.get("/api/emails/{email_id}")
async def api_get_email_detail(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")

    ensure_email_access(email_record, user_info)
    is_regular_user = (user_info["role"] == "user")

    xai_parts = email_record.xai_summary.split("; ") if email_record.xai_summary else []
    reasons = []
    for part in xai_parts:
        if ":" in part:
            key, val = part.split(":", 1)
            reasons.append({"key": key, "value": val})

    human_reasons = []
    reason_labels = {
        "SpamProb": "Probabilitas spam dari model supervised AI",
        "Urgency-Score": "Email mengandung kata-kata mendesak/darurat",
        "Lookalike-Domain": "Link mengarah ke domain yang mirip lodaya.id",
        "SPF": "Verifikasi identitas pengirim (SPF) gagal",
        "DKIM": "Tanda tangan digital email (DKIM) tidak valid",
        "Executable-Attachment": "Email memiliki lampiran berbahaya",
        "URL-Shortener": "Link dipersingkat (menyembunyikan tujuan asli)",
        "DisplayName-Mismatch": "Nama pengirim tidak cocok dengan alamat email",
        "HTML-Forms": "Email mengandung formulir input mencurigakan",
        "FusedScore": "Skor akhir gabungan ML + SA + Anomaly",
        "AnomalyScore": "Skor anomali dari deteksi unsupervised",
    }
    if email_record.anomaly_score and email_record.anomaly_score > 0.3:
        human_reasons.append("Pola email tidak biasa (terdeteksi unsupervised anomaly detection)")
    for part in xai_parts:
        if "=" in part:
            key = part.split("=")[0]
        elif ":" in part:
            key = part.split(":")[0]
        else:
            key = part
        if key in reason_labels:
            human_reasons.append(reason_labels[key])

    shap_data = None
    if email_record.shap_json:
        try:
            shap_data = json.loads(email_record.shap_json)
        except Exception:
            pass

    ecat = display_category(email_record)
    auth_results = {
        "spf_result": email_record.spf_result,
        "dkim_result": email_record.dkim_result,
        "dmarc_result": email_record.dmarc_result,
    }
    if not any(auth_results.values()):
        auth_results = derive_auth_results(email_record.raw_content, email_record.sender)
    thread_messages = find_thread_messages(db, email_record)
    return {
        "email_id": email_record.email_id,
        "sender": email_record.sender,
        "subject": email_record.subject,
        "label": email_record.label,
        "category": ecat,
        "status": email_record.status,
        "fused_score": email_record.fused_score,
        "ml_probability": 0.0 if is_regular_user else email_record.ml_probability,
        "sa_score": 0.0 if is_regular_user else email_record.sa_score,
        "anomaly_score": 0.0 if is_regular_user else email_record.anomaly_score,
        "model_version": email_record.model_version,
        "routing_reason": email_record.routing_reason,
        "received_at": email_record.received_at.isoformat() if hasattr(email_record.received_at, "isoformat") else str(email_record.received_at) if email_record.received_at else None,
        "reasons": [] if is_regular_user else reasons,
        "human_reasons": [] if is_regular_user else human_reasons,
        "shap_data": None if is_regular_user else shap_data,
        "raw_content": email_record.raw_content,
        "recipient_list": email_record.recipient_list,
        "is_read": getattr(email_record, "is_read", False),
        "attachments": attachment_summaries(email_record),
        "thread_root_id": thread_messages[0].email_id if thread_messages else email_record.email_id,
        "thread_messages": [thread_message_payload(message) for message in thread_messages],
        **auth_results,
    }

@app.put("/api/emails/{email_id}/read")
async def api_toggle_read(email_id: str, payload: dict, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(email_record, user_info)
    
    is_read = payload.get("is_read", True)
    email_record.is_read = bool(is_read)
    db.commit()
    return {"ok": True, "is_read": email_record.is_read}


@app.get("/api/emails/{email_id}/attachments/{attachment_index}")
async def api_download_attachment(
    email_id: str,
    attachment_index: int,
    request: Request,
    download: bool = Query(False),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(email_record, user_info)
    try:
        attachments = json.loads(email_record.attachments_json or "[]")
    except Exception:
        attachments = []
    match = next((a for idx, a in enumerate(attachments) if int(a.get("index", idx)) == attachment_index), None)
    if not match:
        raise HTTPException(status_code=404, detail="Attachment not found")
    encoded_data = match.get("data") or match.get("content_base64")
    if not match.get("stored", bool(encoded_data)) or not encoded_data:
        raise HTTPException(status_code=410, detail="Attachment is too large or not stored")
    data = base64.b64decode(encoded_data)
    filename = match.get("filename") or f"attachment-{attachment_index + 1}"
    content_type = match.get("content_type") or "application/octet-stream"
    disposition = "attachment" if download else "inline"
    return Response(
        data,
        media_type=content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@app.post("/api/emails/{email_id}/release")
async def api_release_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.RELEASE_EMAIL):
        raise HTTPException(status_code=403, detail="You do not have permission to manage quarantine")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    email_record.status = "released"
    email_record.label = "CLEAN"
    email_record.category = "clean"
    log_audit(db, user_info["username"], "release", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "released"}


@app.post("/api/emails/{email_id}/confirm-spam")
async def api_confirm_spam(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="You do not have permission to manage quarantine")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    email_record.status = "confirmed_spam"
    email_record.label = "QUARANTINE"
    email_record.category = "spam"
    log_audit(db, user_info["username"], "confirm_spam", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "confirmed_spam", "label": "QUARANTINE", "category": "spam"}


@app.post("/api/emails/{email_id}/report-false-positive")
async def api_report_false_positive(
    email_id: str,
    payload: FalsePositiveRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="You do not have permission to manage quarantine")
    feedback = Feedback(
        email_id=email_id,
        feedback_type="false_positive",
        notes=payload.notes,
    )
    db.add(feedback)
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if email_record:
        email_record.status = "released"
    log_audit(db, user_info["username"], "report_false_positive", email_id,
              request.client.host if request.client else None, payload.notes)
    db.commit()
    return {"ok": True, "status": "released"}


@app.delete("/api/emails/{email_id}")
async def api_delete_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    if email_record.label == "DRAFT":
        ensure_email_access(email_record, user_info)
        db.delete(email_record)
        log_audit(db, user_info["username"], "discard_draft", email_id,
                  request.client.host if request.client else None)
        db.commit()
        return {"ok": True, "status": "deleted"}
    ensure_email_access(email_record, user_info)
    if not has_permission_dict(user_info, Permission.DELETE_EMAIL):
        username_lower = user_info["username"].lower()
        recipients_lower = (email_record.recipient_list or "").lower()
        sender_lower = (email_record.sender or "").lower()
        if username_lower not in recipients_lower and not sender_lower.startswith(f"{username_lower}@"):
            raise HTTPException(status_code=403, detail="You do not have permission to delete this email")
    if email_record.status == "trash":
        db.delete(email_record)
        action = "delete_permanent"
        status = "deleted"
    else:
        email_record.status = "trash"
        email_record.deleted_at = app_now()
        action = "move_to_trash"
        status = "trash"
    log_audit(db, user_info["username"], action, email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": status}


@app.post("/api/emails/{email_id}/restore")
async def api_restore_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="You do not have permission to restore emails")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(email_record, user_info)
    email_record.status = "pending" if email_record.label == "QUARANTINE" else "released"
    email_record.deleted_at = None
    log_audit(db, user_info["username"], "restore", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": email_record.status}


class SendEmailRequest(BaseModel):
    to: str
    from_email: str = ""
    subject: str = ""
    body: str = ""
    reply_to_id: str = ""
    draft_id: str = ""
    action: str = "send"  # "send", "reply", "forward", "share"
    share_with: str = ""  # If share


class DraftEmailRequest(BaseModel):
    draft_id: str = ""
    to: str = ""
    from_email: str = ""
    subject: str = ""
    body: str = ""


@app.post("/api/emails/draft")
async def api_save_email_draft(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    uploaded_files = []
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        req = DraftEmailRequest(
            draft_id=str(form.get("draft_id", "")),
            to=str(form.get("to", "")),
            from_email=str(form.get("from_email", "")),
            subject=str(form.get("subject", "")),
            body=str(form.get("body", "")),
        )
        uploaded_files = [
            item for item in form.getlist("attachments")
            if hasattr(item, "filename") and hasattr(item, "read")
        ]
    else:
        req = DraftEmailRequest(**(await request.json()))

    if not any([req.to.strip(), req.subject.strip(), req.body.strip(), uploaded_files]):
        raise HTTPException(status_code=400, detail="Draft is empty")

    if req.from_email.strip():
        requested_sender = req.from_email.strip().lower()
        if user_info["role"] == "mailbox" and requested_sender != user_info["mailbox_email"]:
            raise HTTPException(status_code=403, detail="You can only send from the logged-in mailbox")
        mailbox = db.query(AdminMailbox).filter(
            AdminMailbox.email == requested_sender,
            AdminMailbox.is_active == True,
        ).first()
        if not mailbox:
            raise HTTPException(status_code=403, detail="Sender mailbox is not registered or inactive")

    sender_address = req.from_email.strip().lower() or user_info.get("mailbox_email") or f"{user_info['username']}@lodaya.id"
    stored_attachments = []
    for file_index, upload in enumerate(uploaded_files[:20]):
        data = await upload.read()
        stored_attachments.append({
            "index": file_index,
            "filename": upload.filename or f"attachment-{file_index + 1}",
            "content_type": upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "application/octet-stream",
            "size": len(data),
            "stored": True,
            "data": base64.b64encode(data).decode("ascii"),
        })

    draft_id = req.draft_id.strip()
    draft_entry = None
    if draft_id:
        draft_entry = db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id == draft_id,
            QuarantineEmail.label == "DRAFT",
        ).first()
    is_new_draft = False
    if not draft_entry:
        is_new_draft = True
        draft_id = f"draft_{uuid.uuid4().hex[:12]}"
        draft_entry = QuarantineEmail(
            email_id=draft_id,
            received_at=app_now_iso(),
            label="DRAFT",
            fused_score=0.0,
            sa_score=0.0,
            ml_probability=0.0,
            anomaly_score=0.0,
            xai_summary="Saved as draft",
            routing_reason="Unsent email draft",
            status="draft",
            category="draft",
            spf_result="DRAFT",
            dkim_result="DRAFT",
            dmarc_result="DRAFT",
        )
        db.add(draft_entry)

    draft_entry.raw_content = req.body
    if uploaded_files or is_new_draft:
        draft_entry.attachments_json = json.dumps(stored_attachments)
    draft_entry.subject = req.subject or "(tanpa subjek)"
    draft_entry.sender = sender_address
    draft_entry.recipient_list = req.to
    draft_entry.received_at = app_now_iso()
    draft_entry.created_at = app_now()
    draft_entry.deleted_at = None

    log_audit(db, user_info["username"], "save_email_draft", draft_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "email_id": draft_id}


@app.post("/api/emails/send")
async def api_send_email(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    uploaded_files = []
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        req = SendEmailRequest(
            to=str(form.get("to", "")),
            from_email=str(form.get("from_email", "")),
            subject=str(form.get("subject", "")),
            body=str(form.get("body", "")),
            reply_to_id=str(form.get("reply_to_id", "")),
            draft_id=str(form.get("draft_id", "")),
            action=str(form.get("action", "send")),
            share_with=str(form.get("share_with", "")),
        )
        uploaded_files = [
            item for item in form.getlist("attachments")
            if hasattr(item, "filename") and hasattr(item, "read")
        ]
    else:
        req = SendEmailRequest(**(await request.json()))

    def parse_recipients(value: str):
        recipients = [
            item.strip().lower()
            for item in re.split(r"[;,]", value or "")
            if item.strip()
        ]
        if not recipients:
            raise HTTPException(status_code=400, detail="Recipient email is required")
        invalid = [email for email in recipients if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email)]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid recipient email: {invalid[0]}")
        return recipients

    if req.from_email.strip():
        requested_sender = req.from_email.strip().lower()
        if user_info["role"] == "mailbox" and requested_sender != user_info["mailbox_email"]:
            raise HTTPException(status_code=403, detail="You can only send from the logged-in mailbox")
        mailbox = db.query(AdminMailbox).filter(
            AdminMailbox.email == requested_sender,
            AdminMailbox.is_active == True,
        ).first()
        if not mailbox:
            raise HTTPException(status_code=403, detail="Sender mailbox is not registered or inactive")
    
    # Construct sender address
    sender_address = req.from_email.strip().lower() or user_info.get("mailbox_email") or f"{user_info['username']}@lodaya.id"
    
    # Determine subject and body based on action
    final_subject = req.subject
    final_body = req.body
    
    if req.action == "share" and req.share_with:
        dest_recipients = parse_recipients(req.share_with)
        # Fetch original email
        orig = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == req.reply_to_id).first()
        if orig:
            final_subject = f"Shared Threat Intel: {orig.subject}"
            final_body = f"Analis {user_info['username']} membagikan email karantina ini kepada Anda.\n\n" \
                         f"Catatan Analis: {req.body}\n\n" \
                         f"--- Detail Email Karantina ---\n" \
                         f"Pengirim: {orig.sender}\n" \
                         f"Subjek: {orig.subject}\n" \
                         f"Skor Fused: {orig.fused_score:.2f}\n" \
                         f"Skor Anomali: {orig.anomaly_score:.2f}\n" \
                         f"Analisis XAI: {orig.xai_summary}\n\n" \
                         f"--- Konten Asli ---\n" \
                         f"{orig.raw_content}"
    else:
        dest_recipients = parse_recipients(req.to)

    if req.reply_to_id.strip() and req.action in {"reply", "forward"}:
        original_email = db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id == req.reply_to_id.strip()
        ).first()
        if original_email:
            final_body = append_thread_context(final_body, original_email, req.action)
        
    stored_attachments = []
    for file_index, upload in enumerate(uploaded_files[:20]):
        data = await upload.read()
        stored_attachments.append({
            "index": file_index,
            "filename": upload.filename or f"attachment-{file_index + 1}",
            "content_type": upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "application/octet-stream",
            "size": len(data),
            "stored": True,
            "data": base64.b64encode(data).decode("ascii"),
        })

    # Send email via SMTP first. Only mark as SENT after delivery is accepted.
    sent_id = f"sent_{uuid.uuid4().hex[:12]}"
    smtp_host = os.getenv("FORWARDER_SMTP_HOST", "")
    try:
        validate_recipient_domains(dest_recipients)
        if smtp_host:
            smtp_port = int(os.getenv("FORWARDER_SMTP_PORT", "587"))
            smtp_user = os.getenv("FORWARDER_SMTP_USER", "")
            smtp_pass = os.getenv("FORWARDER_SMTP_PASS", "")
            smtp_from = sender_address or os.getenv("FORWARDER_FROM", "cognimail@lodaya.id")
            smtp_starttls = os.getenv("FORWARDER_STARTTLS", "true").lower() in {"1", "true", "yes", "on"}

            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = ", ".join(dest_recipients)
            msg["Subject"] = final_subject
            msg.attach(MIMEText(final_body, "plain", "utf-8"))
            for attachment in stored_attachments:
                maintype, subtype = (attachment["content_type"].split("/", 1) + ["octet-stream"])[:2]
                part = MIMEBase(maintype, subtype)
                part.set_payload(base64.b64decode(attachment["data"]))
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=attachment["filename"])
                msg.attach(part)

            async with aiosmtplib.SMTP(
                hostname=smtp_host,
                port=smtp_port,
                use_tls=smtp_port == 465,
            ) as smtp:
                if smtp_port != 465 and smtp_starttls:
                    await smtp.starttls()
                if smtp_user and smtp_pass:
                    await smtp.login(smtp_user, smtp_pass)
                await smtp.send_message(msg)
            logger.info("Sent email via SMTP successfully")
    except Exception as e:
        reason = str(e)
        logger.error("Failed to send email: %s", reason)
        failure_id = save_delivery_failure(
            db,
            sender_address,
            dest_recipients,
            final_subject,
            final_body,
            reason,
            user_info["username"],
            request,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Email gagal terkirim. Notifikasi gagal kirim sudah masuk ke inbox.",
                "reason": reason,
                "failure_email_id": failure_id,
            },
        )

    sent_entry = QuarantineEmail(
        email_id=sent_id,
        received_at=app_now_iso(),
        label="SENT",
        fused_score=0.0,
        sa_score=0.0,
        ml_probability=0.0,
        anomaly_score=0.0,
        xai_summary=f"Sent via Dashboard ({req.action})",
        routing_reason=f"Sent email to {', '.join(dest_recipients)}",
        raw_content=linkify_plain_text(final_body),
        attachments_json=json.dumps(stored_attachments),
        status="released",
        category="sent",
        subject=final_subject,
        sender=sender_address,
        recipient_list=", ".join(dest_recipients),
        spf_result="OUTBOUND",
        dkim_result="OUTBOUND",
        dmarc_result="OUTBOUND",
        created_at=app_now(),
    )
    db.add(sent_entry)

    if req.draft_id.strip():
        db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id == req.draft_id.strip(),
            QuarantineEmail.label == "DRAFT",
        ).delete(synchronize_session=False)

    log_audit(db, user_info["username"], f"send_email_{req.action}", sent_id,
              request.client.host if request.client else None, f"Sent to {', '.join(dest_recipients)}")
    db.commit()

    return {"ok": True, "email_id": sent_id}


@app.get("/api/metrics")
async def api_get_metrics(
    request: Request,
    mailbox: str = Query(None),
    mailbox_id: str = Query(None),
    db: Session = Depends(get_db),
):
    mailbox = (mailbox or "").strip().lower()
    mailbox_id = (mailbox_id or "").strip()
    user_info = None
    try:
        user_info = get_authenticated_api_user(request, db)
    except HTTPException:
        if not mailbox:
            raise

    scope_label = "global"
    account_filters = []
    if mailbox:
        mailbox_record = resolve_active_mailbox(db, mailbox_id, mailbox, missing_status_code=404, missing_detail="Mailbox not found")
        scope_label = mailbox_record.email
        account_filters.append(or_(
            *_mailbox_identity_filters(QuarantineEmail.recipient_list, mailbox_record.email),
            *_mailbox_identity_filters(QuarantineEmail.sender, mailbox_record.email),
        ))
    elif user_info and user_info["role"] == "user":
        user = db.query(User).filter(User.username == user_info["username"]).first()
        identifiers = [user_info["username"].lower()]
        if user and user.email:
            identifiers.append(user.email.lower())
        scope_label = user.email or user_info["username"] if user else user_info["username"]
        account_filters.append(or_(*[
            or_(
                QuarantineEmail.recipient_list.ilike(f"%{identifier}%"),
                QuarantineEmail.sender.ilike(f"%{identifier}%"),
            )
            for identifier in identifiers
        ]))

    base_query = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.label.notin_(["DRAFT", "SENT"]),
    )
    for filter_expr in account_filters:
        base_query = base_query.filter(filter_expr)

    total = base_query.count() or 0
    quarantine_count = base_query.filter(QuarantineEmail.label == "QUARANTINE").count() or 0
    warn_count = base_query.filter(QuarantineEmail.label == "WARN").count() or 0
    clean_count = base_query.filter(QuarantineEmail.label == "CLEAN").count() or 0

    top_senders_db = base_query.with_entities(
        QuarantineEmail.sender, func.count(QuarantineEmail.id).label("count")
    ).group_by(QuarantineEmail.sender).order_by(
        func.count(QuarantineEmail.id).desc()
    ).limit(10).all()
    
    top_senders = [{"sender": s, "count": c} for s, c in top_senders_db]

    feedback_count = db.query(func.count(Feedback.id)).scalar() or 0

    daily_stats_db = base_query.with_entities(
        func.date(QuarantineEmail.created_at).label("day"),
        func.count(QuarantineEmail.id).label("total"),
        func.sum(case((QuarantineEmail.label == "QUARANTINE", 1), else_=0)).label("quarantines"),
    ).group_by(func.date(QuarantineEmail.created_at)).order_by(
        func.date(QuarantineEmail.created_at).desc()
    ).limit(14).all()
    
    daily_stats = []
    for day, tot, quar in reversed(daily_stats_db):
        daily_stats.append({
            "day": str(day),
            "total": tot,
            "quarantines": int(quar) if quar is not None else 0
        })

    return {
        "scope": scope_label,
        "total": total,
        "quarantine_count": quarantine_count,
        "warn_count": warn_count,
        "clean_count": clean_count,
        "top_senders": top_senders,
        "feedback_count": feedback_count,
        "daily_stats": daily_stats
    }


# ─── Audit Log ───────────────────────────────────────────────────────────────────

@app.get("/api/audit-log")
async def api_get_audit_log(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: str = Query(None),
    username: str = Query(None),
    db: Session = Depends(get_db),
):
    """Paginated audit log. Requires admin or above."""
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_AUDIT_LOG):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = db.query(AuditLog)
    if event_type:
        query = query.filter(AuditLog.action == event_type)
    if username:
        query = query.filter(AuditLog.user.ilike(f"%{username}%"))

    total = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [
            {
                "id": str(r.id),
                "username": r.username,
                "action": r.action,
                "email_id": r.email_id,
                "ip_address": r.ip_address,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
            }
            for r in records
        ],
    }


# ─── System Settings ─────────────────────────────────────────────────────────────

# In-memory settings store (persisted to .env file on save in prod; kept simple here)
_SYSTEM_SETTINGS = {
    "threshold_quarantine": float(os.getenv("THRESHOLD_WARN", "0.70")),
    "threshold_warn": float(os.getenv("THRESHOLD_CLEAN", "0.30")),
    "fusion_ml_weight": float(os.getenv("FUSION_ML_WEIGHT", "0.50")),
    "fusion_sa_weight": float(os.getenv("FUSION_SA_WEIGHT", "0.25")),
    "fusion_anomaly_weight": float(os.getenv("FUSION_ANOMALY_WEIGHT", "0.25")),
    "imap_host": os.getenv("IMAP_HOST", ""),
    "imap_port": int(os.getenv("IMAP_PORT", "993")),
    "imap_user": os.getenv("IMAP_USER", ""),
    "poll_interval_seconds": int(os.getenv("POLL_INTERVAL", "30")),
    "protected_domains": os.getenv("PROTECTED_DOMAINS", "lodaya.id,lodayatech.id,lodaya.co.id").split(","),
    "whitelist_senders": os.getenv("WHITELIST_SENDERS", "").split(",") if os.getenv("WHITELIST_SENDERS") else [],
    "admin_alert_email": os.getenv("ADMIN_ALERT_EMAIL", ""),
    "max_quarantine_days": int(os.getenv("MAX_QUARANTINE_DAYS", "30")),
}


@app.get("/api/settings")
async def api_get_settings(request: Request, db: Session = Depends(get_db)):
    """Get current system settings. Requires admin or above."""
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_GLOBAL_SETTINGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    # Return copy without IMAP password for security
    safe = dict(_SYSTEM_SETTINGS)
    return safe


class SettingsUpdatePayload(BaseModel):
    threshold_quarantine: float = None
    threshold_warn: float = None
    fusion_ml_weight: float = None
    fusion_sa_weight: float = None
    fusion_anomaly_weight: float = None
    imap_host: str = None
    imap_port: int = None
    imap_user: str = None
    poll_interval_seconds: int = None
    protected_domains: list = None
    whitelist_senders: list = None
    admin_alert_email: str = None
    max_quarantine_days: int = None


@app.post("/api/settings")
async def api_update_settings(
    payload: SettingsUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update system settings. Requires superadmin."""
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_GLOBAL_SETTINGS):
        raise HTTPException(status_code=403, detail="Only superadmin can change global settings")

    update_data = payload.model_dump(exclude_none=True)
    _SYSTEM_SETTINGS.update(update_data)

    log_audit(db, user_info["username"], "update_settings", None,
              request.client.host if request.client else None,
              f"Updated: {list(update_data.keys())}")
    db.commit()
    return {"ok": True, "updated": list(update_data.keys()), "settings": _SYSTEM_SETTINGS}


@app.post("/api/settings/test-imap")
async def api_test_imap(request: Request, db: Session = Depends(get_db)):
    """Test IMAP connection with current settings."""
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_GLOBAL_SETTINGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    host = _SYSTEM_SETTINGS.get("imap_host", "")
    if not host:
        return {"ok": False, "message": "IMAP host not configured"}

    import imaplib
    try:
        port = _SYSTEM_SETTINGS.get("imap_port", 993)
        conn = imaplib.IMAP4_SSL(host, port)
        conn.logout()
        return {"ok": True, "message": f"Connection to {host}:{port} successful"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─── CSV Export ───────────────────────────────────────────────────────────────────

@app.get("/api/emails/export-csv")
async def api_export_emails_csv(
    request: Request,
    label: str = Query(None),
    db: Session = Depends(get_db),
):
    """Export email log as CSV. Requires admin or above."""
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = db.query(QuarantineEmail)
    if label:
        query = query.filter(QuarantineEmail.label == label)
    records = query.order_by(QuarantineEmail.created_at.desc()).limit(5000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "email_id", "sender", "subject", "label", "status",
        "fused_score", "ml_probability", "sa_score", "anomaly_score",
        "model_version", "routing_reason", "received_at", "created_at"
    ])
    for r in records:
        writer.writerow([
            r.email_id, r.sender, r.subject, r.label, r.status,
            r.fused_score, r.ml_probability, r.sa_score, r.anomaly_score,
            r.model_version, r.routing_reason,
            r.received_at.isoformat() if hasattr(r.received_at, "isoformat") else str(r.received_at),
            r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
        ])

    output.seek(0)
    filename = f"cognimail_email_log_{app_now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─── Manual Email Analyzer ───────────────────────────────────────────────────────

class AnalyzeEmailRequest(BaseModel):
    raw_email: str


@app.post("/api/analyze")
async def api_analyze_email(
    payload: AnalyzeEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Manual single-email analysis.
    Calls the classifier service and returns full dual-detection result.
    """
    user_info = get_authenticated_api_user(request, db)

    classifier_url = os.getenv("CLASSIFIER_URL", "http://localhost:8001")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{classifier_url}/predict-dual",
                json={"raw_email": payload.raw_email},
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.ConnectError:
        # Fallback: use local classifier if running in same process
        try:
            from classifier.features import EmailParser, FeatureExtractor
            from decision_engine.xai import build_xai_header, human_readable_reasons

            parser = EmailParser()
            parsed = parser.parse(payload.raw_email)
            extractor = FeatureExtractor()
            features = extractor.extract(parsed)

            fallback_reasons = human_readable_reasons(features)

            result = {
                "email_id": f"manual-{app_now().strftime('%Y%m%d%H%M%S')}",
                "classification": "unknown",
                "confidence": 0.0,
                "spam_score": 0.0,
                "risk_level": "UNKNOWN",
                "reasons": fallback_reasons or ["Classifier service unavailable — running in fallback mode"],
                "url_analysis": [],
                "recommended_action": "manual_review",
                "processing_time_ms": 0,
                "subject": parsed.subject if hasattr(parsed, 'subject') else "",
                "sender": parsed.from_addr if hasattr(parsed, 'from_addr') else "",
                "ml_probability": 0.0,
                "sa_score": 0.0,
                "anomaly_score": 0.0,
                "fused_score": 0.0,
                "xai_summary": build_xai_header(features, 0.0, 0.0, "UNKNOWN"),
                "label": "UNKNOWN",
                "fallback_mode": True,
            }
        except Exception as fallback_err:
            raise HTTPException(
                status_code=503,
                detail=f"Classifier service unavailable: {str(fallback_err)}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    log_audit(db, user_info["username"], "manual_analyze", result.get("email_id"),
              request.client.host if request.client else None)
    db.commit()
    return result



# ─── User & Settings Management placeholders for Superadmin ──────────────────────

@app.get("/api/admin/users")
async def api_get_users(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        users = db.query(User).filter(User.role == "user").all()
    else:
        users = db.query(User).all()
    return [{"username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]


@app.post("/api/admin/users")
async def api_create_user(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role", "user")
    email = payload.get("email", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    # Enforce role restrictions
    org_id = None
    if user_info["role"] == "admin":
        role = "user"
        caller = db.query(User).filter(User.username == user_info["username"]).first()
        if caller:
            org_id = caller.organization_id
    elif user_info["role"] == "superadmin":
        if role not in ("admin", "user"):
            raise HTTPException(status_code=403, detail="Superadmin can only create admin or user role")
        # If creating a 'user', an admin_username must be provided to link the user
        if role == "user":
            admin_username = payload.get("admin_username", "").strip()
            if not admin_username:
                raise HTTPException(status_code=400, detail="Untuk membuat user, harus pilih admin sebagai penanggung jawab")
            admin_user = db.query(User).filter(
                User.username == admin_username,
                User.role == "admin",
                User.is_active == True
            ).first()
            if not admin_user:
                raise HTTPException(status_code=400, detail=f"Admin '{admin_username}' tidak ditemukan atau tidak aktif")
            org_id = admin_user.organization_id
            if not org_id:
                # Auto-create org for admin if not exists
                new_org = Organization(name=f"Org-{admin_username}", config={"admin": admin_username})
                db.add(new_org)
                db.flush()
                org_id = new_org.id
                admin_user.organization_id = org_id
            
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    if email:
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        username=username,
        email=email or None,
        hashed_password=hash_password(password),
        role=role,
        organization_id=org_id,
    )
    db.add(new_user)
    db.commit()
    return {"ok": True, "message": f"User {username} created", "organization_id": org_id}


@app.post("/api/admin/settings")
async def api_change_settings(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_GLOBAL_SETTINGS):
        raise HTTPException(status_code=403, detail="Only superadmin can change system settings")
    return {"ok": True, "message": "System settings updated successfully"}


@app.get("/api/admin/mailboxes")
async def api_get_admin_mailboxes(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and not has_permission_dict(user_info, Permission.MANAGE_ORG_MAILBOXES):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    query = db.query(AdminMailbox)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
        user = db.query(User).filter(User.username == user_info["username"]).first()
        if user and user.organization_id:
            query = query.filter(AdminMailbox.assigned_to.in_(
                db.query(User.username).filter(User.organization_id == user.organization_id)
            ))
    rows = query.order_by(AdminMailbox.is_active.desc(), AdminMailbox.email.asc()).all()
    return [
        {
            "id": row.id,
            "email": row.email,
            "domain": row.domain,
            "sender_name": row.sender_name or "",
            "forward_to": row.forward_to or "",
            "forward_enabled": bool(row.forward_enabled),
            "forward_keep_copy": bool(row.forward_keep_copy),
            "assigned_to": row.assigned_to or "",
            "storage_bytes": row.storage_bytes or 0,
            "is_active": bool(row.is_active),
            "created_by": row.created_by,
            "created_at": str(row.created_at),
        }
        for row in rows
    ]


@app.post("/api/admin/mailboxes")
@limiter.limit("10/minute")
async def api_create_admin_mailbox(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and not has_permission_dict(user_info, Permission.MANAGE_ORG_MAILBOXES):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    email = str(payload.get("email", "")).strip().lower()
    domain = str(payload.get("domain", "")).strip().lower().lstrip("@")
    password = str(payload.get("password", ""))
    sender_name = str(payload.get("sender_name", "")).strip()
    assigned_to = str(payload.get("assigned_to", "")).strip()
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status_code=400, detail="Invalid mailbox email")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mailbox password must be at least 8 characters")

    # Email harus di-assign ke user/admin yang valid
    if not assigned_to:
        raise HTTPException(status_code=400, detail="Email harus di-assign ke admin atau user")
    target_user = db.query(User).filter(User.username == assigned_to, User.is_active == True).first()
    if not target_user:
        raise HTTPException(status_code=400, detail=f"User/admin '{assigned_to}' tidak ditemukan atau tidak aktif")

    # Validasi count: 1 admin max 3 email
    existing_count = db.query(func.count(AdminMailbox.id)).filter(
        AdminMailbox.assigned_to == assigned_to,
        AdminMailbox.is_active == True
    ).scalar() or 0
    if existing_count >= 3:
        raise HTTPException(status_code=400, detail=f"User '{assigned_to}' sudah memiliki {existing_count} email (maksimal 3)")

    # Admin can only assign to users in their organization
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
        current_user_obj = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user_obj or not current_user_obj.organization_id:
            raise HTTPException(status_code=403, detail="Admin must belong to an organization")
        if target_user.organization_id != current_user_obj.organization_id:
            raise HTTPException(status_code=403, detail="Can only assign mailboxes to users in your organization")

    actual_domain = email.split("@", 1)[1]
    if domain and actual_domain != domain:
        raise HTTPException(status_code=400, detail=f"Mailbox must use @{domain}")
    existing = db.query(AdminMailbox).filter(AdminMailbox.email == email).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Mailbox already exists")
        existing.is_active = True
        existing.domain = actual_domain
        existing.created_by = user_info["username"]
        existing.password_hash = hash_password(password)
        existing.sender_name = sender_name
        existing.assigned_to = assigned_to
    else:
        db.add(AdminMailbox(
            email=email,
            domain=actual_domain,
            password_hash=hash_password(password),
            sender_name=sender_name,
            assigned_to=assigned_to,
            created_by=user_info["username"],
        ))
    log_audit(db, user_info["username"], "create_mailbox", None, request.client.host if request.client else None, email)
    db.commit()
    return {"ok": True, "email": email, "domain": actual_domain}


@app.post("/api/mailboxes/login")
@limiter.limit("20/minute")
async def api_login_mailbox(request: Request, payload: dict, db: Session = Depends(get_db)):
    mailbox_id = payload.get("mailbox_id")
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    mailbox = resolve_active_mailbox(db, mailbox_id, email, missing_status_code=401, missing_detail="Incorrect password or email address", inactive_detail="Incorrect password or email address")
    if not mailbox or (email and mailbox.email != email) or not verify_password(password, mailbox.password_hash or ""):
        raise HTTPException(status_code=401, detail="Incorrect password or email address")
    response = JSONResponse({
        "ok": True,
        "mailbox": {
            "id": mailbox.id,
            "email": mailbox.email,
            "domain": mailbox.domain,
            "sender_name": mailbox.sender_name or "",
        }
    })
    # Use a SEPARATE cookie (mailbox_token) so that the mailbox session
    # is independent from the dashboard session (access_token).
    # This allows mailbox logout without affecting the dashboard session.
    access_token = create_access_token({
        "sub": f"mailbox:{mailbox.id}",
        "role": "mailbox",
        "mailbox_id": str(mailbox.id),
        "mailbox_email": mailbox.email.lower(),
    })
    response.set_cookie(
        key="mailbox_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production",
        path="/",
    )
    return response


@app.delete("/api/admin/mailboxes/{mailbox_id}")
@limiter.limit("20/minute")
async def api_delete_admin_mailbox(mailbox_id: int, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and not has_permission_dict(user_info, Permission.MANAGE_ORG_MAILBOXES):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    # Admin can only delete mailboxes assigned to users in their org
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and mailbox.assigned_to:
        target_user = db.query(User).filter(User.username == mailbox.assigned_to).first()
        current_user_obj = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user_obj or not current_user_obj.organization_id or not target_user or target_user.organization_id != current_user_obj.organization_id:
            raise HTTPException(status_code=403, detail="Can only manage mailboxes in your organization")
    mailbox.is_active = False  # Soft delete
    log_audit(db, user_info["username"], "delete_mailbox", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {"ok": True}


@app.put("/api/admin/mailboxes/{mailbox_id}/forwarder")
@limiter.limit("20/minute")
async def api_update_admin_mailbox_forwarder(mailbox_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id, AdminMailbox.is_active == True).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    target = str(payload.get("target", "")).strip().lower()
    enabled = bool(payload.get("enabled", True))
    keep_copy = bool(payload.get("keep_copy", True))
    if enabled and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", target):
        raise HTTPException(status_code=400, detail="Invalid forwarder email")
    mailbox.forward_to = target if enabled else ""
    mailbox.forward_enabled = enabled and bool(target)
    mailbox.forward_keep_copy = keep_copy
    log_audit(db, user_info["username"], "update_mailbox_forwarder", None, request.client.host if request.client else None, f"{mailbox.email} -> {mailbox.forward_to}")
    db.commit()
    return {
        "ok": True,
        "forward_to": mailbox.forward_to,
        "forward_enabled": bool(mailbox.forward_enabled),
        "forward_keep_copy": bool(mailbox.forward_keep_copy),
    }


@app.put("/api/admin/mailboxes/{mailbox_id}")
@limiter.limit("20/minute")
async def api_update_admin_mailbox(mailbox_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and not has_permission_dict(user_info, Permission.MANAGE_ORG_MAILBOXES):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
        mailbox_user = db.query(User).filter(User.username == mailbox.assigned_to).first()
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        if not mailbox_user or mailbox_user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Can only manage mailboxes in your organization")
    if "email" in payload:
        new_email = str(payload["email"]).strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", new_email):
            raise HTTPException(status_code=400, detail="Invalid email")
        mailbox.email = new_email
        mailbox.domain = new_email.split("@", 1)[1]
    if "domain" in payload:
        mailbox.domain = str(payload["domain"]).strip().lower().lstrip("@")
    if "sender_name" in payload:
        mailbox.sender_name = str(payload["sender_name"]).strip()
    if "assigned_to" in payload:
        mailbox.assigned_to = str(payload["assigned_to"]).strip()
    if "is_active" in payload:
        mailbox.is_active = bool(payload["is_active"])
    log_audit(db, user_info["username"], "update_mailbox", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {
        "ok": True,
        "id": mailbox.id,
        "email": mailbox.email,
        "domain": mailbox.domain,
        "sender_name": mailbox.sender_name or "",
        "assigned_to": mailbox.assigned_to or "",
        "is_active": bool(mailbox.is_active),
    }


@app.put("/api/admin/mailboxes/{mailbox_id}/password")
@limiter.limit("10/minute")
async def api_update_admin_mailbox_password(mailbox_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    password = str(payload.get("password", ""))
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mailbox password must be at least 8 characters")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id, AdminMailbox.is_active == True).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    mailbox.password_hash = hash_password(password)
    log_audit(db, user_info["username"], "update_mailbox_password", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {"ok": True}


@app.put("/api/admin/users/{username}")
async def api_update_user(username: str, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Enforce update role checks
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        if user.role != "user":
            raise HTTPException(status_code=403, detail="Admin can only edit users with 'user' role")
        if "role" in payload and payload["role"] != "user":
            raise HTTPException(status_code=403, detail="Admin can only set user role to 'user'")
    else:
        if "role" in payload:
            if payload["role"] not in ("admin", "user"):
                raise HTTPException(status_code=403, detail="Superadmin can only set role to admin or user")
                
    if "role" in payload:
        user.role = payload["role"]
    if "email" in payload:
        user.email = payload["email"] or None
    if "is_active" in payload:
        user.is_active = payload["is_active"]
    if "password" in payload and payload["password"]:
        user.hashed_password = hash_password(payload["password"])
    db.commit()
    return {"ok": True, "message": f"User {username} updated"}


@app.delete("/api/admin/users/{username}")
async def api_delete_user(username: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Enforce delete restrictions
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        if user.role != "user":
            raise HTTPException(status_code=403, detail="Admin can only disable users with 'user' role")
            
    user.is_active = False
    db.commit()
    return {"ok": True, "message": f"User {username} disabled"}


@app.get("/api/admin/audit-logs")
async def api_get_audit_logs(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_AUDIT_LOG):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view audit logs")
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {"user": l.user, "action": l.action, "email_id": l.email_id, "details": l.details, "created_at": str(l.created_at)}
        for l in logs
    ]


@app.get("/api/admin/stats")
async def api_admin_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view stats")
    role = user_info.get("user", {}).get("role", "")
    is_super = role == "superadmin"
    if is_super:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
    else:
        org_id = user_info.get("user", {}).get("organization_id")
        admin_username = user_info.get("user", {}).get("username", "")
        scope_emails = set()
        if org_id:
            org_mboxes = db.query(AdminMailbox).filter(
                AdminMailbox.assigned_to == admin_username,
                AdminMailbox.is_active == True
            ).all()
            for mb in org_mboxes:
                scope_emails.add(mb.email.lower())
            if user_info.get("user", {}).get("email"):
                scope_emails.add(user_info["user"]["email"].lower())
        else:
            mboxes = db.query(AdminMailbox).filter(
                AdminMailbox.assigned_to == admin_username,
                AdminMailbox.is_active == True
            ).all()
            for mb in mboxes:
                scope_emails.add(mb.email.lower())
            if user_info.get("user", {}).get("email"):
                scope_emails.add(user_info["user"]["email"].lower())
        total_users = db.query(User).filter(
            User.organization_id == org_id, User.is_active == True
        ).count() if org_id else 0
        active_users = total_users
        base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
        if scope_emails:
            from sqlalchemy import or_
            filters = [QuarantineEmail.recipient_list.contains(e, autoescape=True) for e in scope_emails]
            base = base.filter(or_(*filters))
        else:
            base = base.filter(QuarantineEmail.organization_id == org_id) if org_id else base.filter(QuarantineEmail.id < 0)
    total_emails = base.count()
    clean_count = base.filter(
        QuarantineEmail.label == "CLEAN",
    ).count()
    warn_count = base.filter(
        QuarantineEmail.label == "WARN",
    ).count()
    quarantine_count = base.filter(
        QuarantineEmail.label == "QUARANTINE",
    ).count()
    audit_count = db.query(AuditLog).count()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_emails": total_emails,
        "clean": clean_count,
        "warn": warn_count,
        "quarantine": quarantine_count,
        "audit_logs": audit_count,
    }


@app.get("/api/admin/my-emails")
async def api_admin_my_emails(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Only admin can view their emails")
    username = user_info.get("user", {}).get("username", "")
    org_id = user_info.get("user", {}).get("organization_id")
    mboxes = db.query(AdminMailbox).filter(
        AdminMailbox.assigned_to == username,
        AdminMailbox.is_active == True
    ).all()
    scope_emails = set()
    admin_email = user_info.get("user", {}).get("email", "")
    if admin_email:
        scope_emails.add(admin_email.lower())
    for mb in mboxes:
        scope_emails.add(mb.email.lower())
    if org_id:
        user_rows = db.query(User).filter(
            User.organization_id == org_id,
            User.role == "user",
            User.is_active == True
        ).all()
        for u in user_rows:
            if u.email:
                scope_emails.add(u.email.lower())
    emails_data = []
    for email_addr in sorted(scope_emails):
        cat_base = db.query(QuarantineEmail).filter(
            QuarantineEmail.recipient_list.contains(email_addr, autoescape=True),
            QuarantineEmail.status != "trash",
        )
        total = cat_base.count() or 0
        spam = cat_base.filter(QuarantineEmail.category == "spam").count() or 0
        phishing = cat_base.filter(QuarantineEmail.category == "phishing").count() or 0
        malware = cat_base.filter(QuarantineEmail.category == "malware").count() or 0
        clean = cat_base.filter(QuarantineEmail.label == "CLEAN").count() or 0
        owner = "admin" if email_addr == admin_email.lower() or any(mb.email.lower() == email_addr for mb in mboxes) else "user"
        emails_data.append({
            "email": email_addr,
            "total": total,
            "spam": spam,
            "phishing": phishing,
            "malware": malware,
            "clean": clean,
            "owner": owner,
        })
    return {
        "username": username,
        "emails": emails_data,
    }


@app.get("/api/admin/quarantine")
async def api_admin_quarantine(
    request: Request,
    q: str = Query(None),
    category: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="Permission denied")
    user = db.query(User).filter(User.username == user_info["username"]).first()
    org_id = user.organization_id if user and user.role == "admin" else None

    query = db.query(QuarantineEmail)
    query = query.filter(QuarantineEmail.status.notin_(["trash", "released"]))
    query = query.filter(QuarantineEmail.label.in_(["QUARANTINE", "WARN"]))

    if org_id:
        query = query.filter(QuarantineEmail.organization_id == org_id)

    if category and category in {"spam", "phishing", "malware"}:
        if category == "spam":
            query = query.filter(or_(
                and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"),
                and_(QuarantineEmail.label == "QUARANTINE", or_(
                    QuarantineEmail.category == "",
                    QuarantineEmail.category.is_(None),
                    ~QuarantineEmail.category.in_(["spam", "phishing", "malware"]),
                )),
                QuarantineEmail.label == "WARN",
            ))
        else:
            query = query.filter(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == category)

    if q:
        terms = [term for term in re.split(r"\s+", q.strip()) if term]
        searchable_fields = [
            QuarantineEmail.subject,
            QuarantineEmail.sender,
            QuarantineEmail.recipient_list,
            QuarantineEmail.xai_summary,
            QuarantineEmail.routing_reason,
            QuarantineEmail.email_id,
        ]
        for term in terms:
            pattern = f"%{term}%"
            query = query.filter(or_(*[field.ilike(pattern) for field in searchable_fields]))

    total = query.count()
    offset = (page - 1) * page_size
    emails = (
        query
        .order_by(QuarantineEmail.received_at.desc(), QuarantineEmail.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    emails_data = []
    for email in emails:
        cat = display_category(email)
        raw_text = email.raw_content or ""
        if "\n\n" in raw_text:
            raw_text = raw_text.split("\n\n", 1)[1]
        raw_text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw_text)
        raw_text = re.sub(r"(?s)<[^>]+>", " ", raw_text)
        body_preview = " ".join(html.unescape(raw_text).replace("\r", "\n").split())[:180]

        xai_parts = email.xai_summary.split("; ") if email.xai_summary else []
        human_reasons = []
        reason_labels = {
            "SpamProb": "Probabilitas spam tinggi",
            "Urgency-Score": "Kata-kata mendesak/darurat",
            "Lookalike-Domain": "Domain mencurigakan mirip domain resmi",
            "SPF": "Verifikasi SPF gagal",
            "DKIM": "DKIM tidak valid",
            "Executable-Attachment": "Lampiran berbahaya",
            "URL-Shortener": "Link dipersingkat",
            "DisplayName-Mismatch": "Nama pengirim tidak cocok",
            "HTML-Forms": "Formulir mencurigakan",
            "FusedScore": "Skor gabungan tinggi",
            "AnomalyScore": "Deteksi anomali",
        }
        if email.anomaly_score and email.anomaly_score > 0.3:
            human_reasons.append("Pola email tidak biasa (anomali)")
        for part in xai_parts:
            key = part.split("=")[0] if "=" in part else part.split(":")[0] if ":" in part else part
            if key in reason_labels:
                human_reasons.append(reason_labels[key])

        emails_data.append({
            "email_id": email.email_id,
            "sender": email.sender,
            "subject": email.subject,
            "body_preview": body_preview,
            "label": email.label,
            "category": cat,
            "status": email.status,
            "fused_score": email.fused_score,
            "ml_probability": email.ml_probability,
            "sa_score": email.sa_score,
            "anomaly_score": email.anomaly_score,
            "xai_summary": email.xai_summary,
            "routing_reason": email.routing_reason,
            "detection_reasons": human_reasons,
            "has_attachments": bool(email.attachments_json and email.attachments_json != "[]"),
            "recipient_list": email.recipient_list,
            "received_at": email.received_at.isoformat() if hasattr(email.received_at, "isoformat") else str(email.received_at) if email.received_at else None,
        })

    return {"emails": emails_data, "total": total, "page": page, "page_size": page_size}


@app.get("/api/admin/detection-logs")
async def api_admin_detection_logs(
    request: Request,
    q: str = Query(None),
    label: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_AUDIT_LOG):
        raise HTTPException(status_code=403, detail="Permission denied")
    user = db.query(User).filter(User.username == user_info["username"]).first()
    org_id = user.organization_id if user and user.role == "admin" else None

    query = db.query(QuarantineEmail)
    query = query.filter(QuarantineEmail.status != "trash")

    if org_id:
        query = query.filter(QuarantineEmail.organization_id == org_id)
    if label and label.upper() in {"CLEAN", "WARN", "QUARANTINE"}:
        query = query.filter(QuarantineEmail.label == label.upper())

    if q:
        terms = [term for term in re.split(r"\s+", q.strip()) if term]
        searchable_fields = [
            QuarantineEmail.subject,
            QuarantineEmail.sender,
            QuarantineEmail.recipient_list,
            QuarantineEmail.email_id,
        ]
        for term in terms:
            pattern = f"%{term}%"
            query = query.filter(or_(*[field.ilike(pattern) for field in searchable_fields]))

    total = query.count()
    offset = (page - 1) * page_size
    emails = (
        query
        .order_by(QuarantineEmail.received_at.desc(), QuarantineEmail.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    email_ids = [e.email_id for e in emails]
    latest_actions = {}
    if email_ids:
        subq = (
            db.query(
                AuditLog.email_id,
                AuditLog.action,
                AuditLog.user,
                AuditLog.created_at,
                func.row_number().over(
                    partition_by=AuditLog.email_id,
                    order_by=AuditLog.created_at.desc()
                ).label("rn")
            )
            .filter(AuditLog.email_id.in_(email_ids))
            .subquery()
        )
        action_rows = db.query(subq).filter(subq.c.rn == 1).all()
        for row in action_rows:
            latest_actions[row.email_id] = {
                "action": row.action,
                "by": row.user,
                "at": str(row.created_at) if row.created_at else None,
            }

    logs_data = []
    for email in emails:
        action_info = latest_actions.get(email.email_id, {})
        logs_data.append({
            "email_id": email.email_id,
            "sender": email.sender,
            "subject": email.subject,
            "label": email.label,
            "category": email.category or "",
            "status": email.status,
            "fused_score": email.fused_score,
            "ml_probability": email.ml_probability,
            "received_at": email.received_at.isoformat() if hasattr(email.received_at, "isoformat") else str(email.received_at) if email.received_at else None,
            "action_taken": action_info.get("action"),
            "action_by": action_info.get("by"),
            "action_at": action_info.get("at"),
        })

    return {"logs": logs_data, "total": total, "page": page, "page_size": page_size}


@app.get("/api/user/dashboard")
async def api_user_dashboard(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("user", "admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.username == user_info["username"]).first()
    identifiers = [user_info["username"].lower()]
    if user and user.email:
        identifiers.append(user.email.lower())
    identity_filters = [
        or_(
            QuarantineEmail.recipient_list.ilike(f"%{identifier}%"),
            QuarantineEmail.sender.ilike(f"%{identifier}%"),
        )
        for identifier in identifiers
    ]
    base = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.label.notin_(["DRAFT", "SENT"]),
    )
    for f in identity_filters:
        base = base.filter(f)
    total_inbox = base.count() or 0
    safe = base.filter(QuarantineEmail.label == "CLEAN").count() or 0
    spam = base.filter(or_(
        and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"),
        and_(QuarantineEmail.label == "QUARANTINE", or_(
            QuarantineEmail.category == "",
            QuarantineEmail.category.is_(None),
            ~QuarantineEmail.category.in_(["spam", "phishing", "malware"]),
        )),
        QuarantineEmail.label == "WARN",
    )).count() or 0
    phishing = base.filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.category == "phishing",
    ).count() or 0
    quarantined = base.filter(QuarantineEmail.label == "QUARANTINE").count() or 0
    recent_alerts_data = base.filter(
        QuarantineEmail.label.in_(["QUARANTINE", "WARN"]),
    ).order_by(QuarantineEmail.created_at.desc()).limit(10).all()
    recent_alerts = [
        {
            "email_id": e.email_id,
            "sender": e.sender,
            "subject": e.subject,
            "label": e.label,
            "category": e.category or "",
            "fused_score": e.fused_score,
            "received_at": str(e.received_at) if e.received_at else None,
        }
        for e in recent_alerts_data
    ]
    mailbox_info = None
    mailbox_email = None
    if user and user.email:
        mailbox_email = user.email
    elif user_info["username"] and "@" in user_info["username"]:
        mailbox_email = user_info["username"]
    if mailbox_email:
        mailbox_record = db.query(AdminMailbox).filter(
            AdminMailbox.email == mailbox_email.lower(),
            AdminMailbox.is_active == True,
        ).first()
        if mailbox_record:
            mailbox_info = {
                "id": mailbox_record.id,
                "email": mailbox_record.email,
                "is_active": mailbox_record.is_active,
            }
    return {
        "total_inbox": total_inbox,
        "safe": safe,
        "spam": spam,
        "phishing": phishing,
        "quarantined": quarantined,
        "recent_alerts": recent_alerts,
        "mailbox": mailbox_info,
    }


@app.get("/api/user/mailbox")
async def api_user_mailbox(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("user", "admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.username == user_info["username"]).first()
    user_email = user.email if user and user.email else user_info["username"]
    if "@" not in user_email:
        return {"mailbox": None}
    mailbox_record = db.query(AdminMailbox).filter(
        AdminMailbox.email == user_email.lower(),
        AdminMailbox.is_active == True,
    ).first()
    if mailbox_record:
        return {
            "mailbox": {
                "id": mailbox_record.id,
                "email": mailbox_record.email,
                "is_active": mailbox_record.is_active,
            }
        }
    return {"mailbox": None}


# ─── User Preferences (role=user) ──────────────────────────────────────

_USER_PREFERENCES = {}

class UserSettingsPayload(BaseModel):
    notification_email: bool = None
    daily_summary: bool = None
    theme: str = None
    language: str = None

@app.get("/api/user/settings")
async def api_get_user_settings(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("user", "admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.username == user_info["username"]).first()
    prefs = _USER_PREFERENCES.get(user_info["username"], {})
    return {
        "username": user_info["username"],
        "email": user.email if user else None,
        "role": user_info["role"],
        "mailbox_email": user.email if user and user.email else user_info["username"],
        "notification_email": prefs.get("notification_email", True),
        "daily_summary": prefs.get("daily_summary", False),
        "theme": prefs.get("theme", "system"),
        "language": prefs.get("language", "id"),
    }

@app.put("/api/user/settings")
async def api_update_user_settings(
    payload: UserSettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("user", "admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Access denied")
    user_prefs = _USER_PREFERENCES.setdefault(user_info["username"], {})
    update_data = payload.model_dump(exclude_none=True)
    user_prefs.update(update_data)
    return {"ok": True, "updated": list(update_data.keys()), "settings": user_prefs}


# ─── Superadmin Company (Organization) CRUD ──────────────────────────

@app.get("/api/admin/organizations")
async def api_list_organizations(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage organizations")
    orgs = db.query(Organization).order_by(Organization.name).all()
    result = []
    for org in orgs:
        admin_count = db.query(func.count(User.id)).filter(
            User.organization_id == org.id, User.role == "admin", User.is_active == True
        ).scalar() or 0
        user_count = db.query(func.count(User.id)).filter(
            User.organization_id == org.id, User.role == "user", User.is_active == True
        ).scalar() or 0
        mbox_count = db.query(func.count(AdminMailbox.id)).filter(
            AdminMailbox.assigned_to == User.username,
            User.organization_id == org.id
        ).filter(User.is_active == True).scalar() or 0
        mbox_count = db.query(func.count(AdminMailbox.id)).filter(
            AdminMailbox.assigned_to.in_(
                db.query(User.username).filter(User.organization_id == org.id, User.is_active == True).subquery()
            )
        ).scalar() or 0
        email_count = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.organization_id == org.id
        ).scalar() or 0
        admins = db.query(User).filter(
            User.organization_id == org.id, User.role == "admin", User.is_active == True
        ).all()
        admins_data = [{"username": a.username, "email": a.email} for a in admins]
        result.append({
            "id": org.id,
            "name": org.name,
            "config": org.config or {},
            "admin_count": admin_count,
            "user_count": user_count,
            "mailbox_count": mbox_count,
            "email_count": email_count,
            "admins": admins_data,
            "created_at": str(org.created_at) if org.created_at else "",
        })
    return {"organizations": result}

class OrgCreatePayload(BaseModel):
    name: str
    domain: str = ""

@app.post("/api/admin/organizations")
async def api_create_organization(
    payload: OrgCreatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage organizations")
    existing = db.query(Organization).filter(Organization.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Organization '{payload.name}' already exists")
    org = Organization(
        name=payload.name,
        config={"domain": payload.domain} if payload.domain else {},
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return {"ok": True, "organization": {"id": org.id, "name": org.name}}

class OrgUpdatePayload(BaseModel):
    name: str = None
    domain: str = None

@app.put("/api/admin/organizations/{org_id}")
async def api_update_organization(
    org_id: int,
    payload: OrgUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage organizations")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if payload.name is not None:
        dup = db.query(Organization).filter(Organization.name == payload.name, Organization.id != org_id).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"Organization '{payload.name}' already exists")
        org.name = payload.name
    if payload.domain is not None:
        config = dict(org.config or {})
        config["domain"] = payload.domain
        org.config = config
    db.commit()
    db.refresh(org)
    return {"ok": True, "organization": {"id": org.id, "name": org.name}}

@app.delete("/api/admin/organizations/{org_id}")
async def api_delete_organization(
    org_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage organizations")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    users_in_org = db.query(func.count(User.id)).filter(User.organization_id == org_id).scalar() or 0
    if users_in_org > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete organization with {users_in_org} active users. Remove users first.")
    emails_in_org = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org_id).scalar() or 0
    if emails_in_org > 0:
        QuarantineEmail.__table__.update().where(QuarantineEmail.organization_id == org_id).values(organization_id=None).execute()
    db.delete(org)
    db.commit()
    return {"ok": True, "message": f"Organization '{org.name}' deleted"}

# ─── Admin Organization Settings (role=admin) ──────────────────────────

class AdminSettingsPayload(BaseModel):
    org_name: str = None
    max_quarantine_days: int = None
    quarantine_action: str = None
    notify_on_threat: bool = None
    allow_sender_override: bool = None
    default_mailbox_limit: int = None
    retention_days: int = None

@app.get("/api/admin/settings")
async def api_get_admin_settings(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    user = db.query(User).filter(User.username == user_info["username"]).first()
    org = None
    if user and user.organization_id:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        return {
            "org_name": "Default",
            "max_quarantine_days": _SYSTEM_SETTINGS.get("max_quarantine_days", 30),
            "quarantine_action": "quarantine",
            "notify_on_threat": True,
            "allow_sender_override": False,
            "default_mailbox_limit": 50,
            "retention_days": 90,
        }
    config = org.config or {}
    return {
        "org_name": org.name,
        "max_quarantine_days": config.get("max_quarantine_days", _SYSTEM_SETTINGS.get("max_quarantine_days", 30)),
        "quarantine_action": config.get("quarantine_action", "quarantine"),
        "notify_on_threat": config.get("notify_on_threat", True),
        "allow_sender_override": config.get("allow_sender_override", False),
        "default_mailbox_limit": config.get("default_mailbox_limit", 50),
        "retention_days": config.get("retention_days", 90),
    }

@app.put("/api/admin/settings")
async def api_update_admin_settings(
    payload: AdminSettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    user = db.query(User).filter(User.username == user_info["username"]).first()
    if not user or not user.organization_id:
        raise HTTPException(status_code=400, detail="No organization assigned")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    config = dict(org.config or {})
    update_data = payload.model_dump(exclude_none=True)
    config.update(update_data)
    org.config = config
    db.commit()
    return {"ok": True, "updated": list(update_data.keys()), "settings": config}


# ─── Superadmin Role Settings ──────────────────────────────────────────

class RoleSettingsPayload(BaseModel):
    allow_admin_user_management: bool = None
    allow_admin_mailbox_management: bool = None
    allow_admin_quarantine_review: bool = None
    self_registration: bool = None
    default_user_role: str = None
    session_timeout_minutes: int = None

@app.get("/api/superadmin/settings/roles")
async def api_get_role_settings(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin required")
    return {
        "allow_admin_user_management": True,
        "allow_admin_mailbox_management": True,
        "allow_admin_quarantine_review": True,
        "self_registration": False,
        "default_user_role": "user",
        "session_timeout_minutes": 60,
        "available_roles": ["user", "admin", "superadmin"],
    }

@app.put("/api/superadmin/settings/roles")
async def api_update_role_settings(
    payload: RoleSettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin required")
    update_data = payload.model_dump(exclude_none=True)
    # Store in system settings for now (in-memory)
    for k, v in update_data.items():
        _SYSTEM_SETTINGS[f"role_{k}"] = v
    log_audit(db, user_info["username"], "update_role_settings", None,
              request.client.host if request.client else None,
              f"Updated role settings: {list(update_data.keys())}")
    db.commit()
    return {"ok": True, "updated": list(update_data.keys())}


# ─── User Reports / Tickets ───────────────────────────────────────────

@app.post("/api/reports")
async def submit_report(request: Request, payload: dict, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload_data = decode_token(token)
    username = payload_data.get("sub", "unknown")
    category = payload.get("category", "other")
    priority = payload.get("priority", "normal")
    valid_categories = {"bug", "question", "access", "false_positive", "other"}
    valid_priorities = {"low", "normal", "high", "urgent"}
    if category not in valid_categories:
        category = "other"
    if priority not in valid_priorities:
        priority = "normal"
    report = Report(
        username=username,
        subject=payload.get("subject", ""),
        message=payload.get("message", ""),
        category=category,
        priority=priority,
        status="open",
    )
    db.add(report)
    db.commit()
    return {"ok": True, "id": report.id}


@app.get("/api/admin/reports")
async def get_reports(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Access denied")
    reports = db.query(Report).order_by(Report.created_at.desc()).limit(100).all()
    return [
        {"id": r.id, "username": r.username, "subject": r.subject, "message": r.message,
         "category": r.category, "priority": r.priority,
         "status": r.status, "admin_reply": r.admin_reply,
         "created_at": str(r.created_at), "resolved_at": str(r.resolved_at) if r.resolved_at else None}
        for r in reports
    ]


@app.put("/api/admin/reports/{report_id}")
async def update_report(report_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Access denied")
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if "status" in payload:
        report.status = payload["status"]
        if payload["status"] == "resolved":
            report.resolved_at = app_now()
    if "admin_reply" in payload and payload["admin_reply"] is not None:
        report.admin_reply = payload["admin_reply"]
        if report.status == "open":
            report.status = "in_progress"
    db.commit()
    return {"ok": True}


# ─── IP Reputation Helpers ────────────────────────────────────────────

KNOWN_BAD_IPS = {
    "185.220.101.0", "23.129.64.0", "45.33.32.0", "5.255.88.0",
    "192.168.1.1",
}

PRIVATE_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    "192.168.", "127.", "0.")

SUSPICIOUS_IP_RANGES = [
    ("185.", "Known threat range"),
    ("23.", "VPN/datacenter range"),
]


def check_ip_reputation(ip: str) -> dict:
    """Check IP safety. Returns {safe, reason, source}."""
    if not ip:
        return {"safe": True, "reason": "No IP", "source": "internal"}
    if ip in KNOWN_BAD_IPS:
        return {"safe": False, "reason": "Known malicious IP", "source": "blacklist"}
    if ip.startswith(PRIVATE_IP_PREFIXES):
        return {"safe": True, "reason": "Internal/private network", "source": "heuristic"}
    for prefix, label in SUSPICIOUS_IP_RANGES:
        if ip.startswith(prefix):
            return {"safe": False, "reason": label, "source": "heuristic"}
    return {"safe": True, "reason": "Clean IP", "source": "heuristic"}


# ─── Admin: Per-User Monitoring ────────────────────────────────────────

@app.get("/api/admin/user-stats")
async def api_user_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Access denied")

    users = db.query(User).filter(User.is_active == True).all()
    result = []
    for u in users:
        identifiers = [u.username.lower()]
        if u.email:
            identifiers.append(u.email.lower())
        email_filters = [
            or_(
                QuarantineEmail.recipient_list.ilike(f"%{identifier}%"),
                QuarantineEmail.sender.ilike(f"%{identifier}%"),
            )
            for identifier in identifiers
        ]
        total_emails = db.query(QuarantineEmail).filter(
            QuarantineEmail.status != "trash",
            or_(*email_filters),
        ).count()

        org_name = None
        if u.organization_id:
            org = db.query(Organization).filter(Organization.id == u.organization_id).first()
            org_name = org.name if org else None
        result.append({
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "organization_id": u.organization_id,
            "organization_name": org_name,
            "total_emails": total_emails,
            "is_active": u.is_active,
        })
    return result


@app.get("/api/admin/user-emails/{username}")
async def api_user_emails(username: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found")
    identifiers = [user.username.lower()]
    if user.email:
        identifiers.append(user.email.lower())
    email_filters = [
        or_(
            QuarantineEmail.recipient_list.ilike(f"%{identifier}%"),
            QuarantineEmail.sender.ilike(f"%{identifier}%"),
        )
        for identifier in identifiers
    ]
    emails = (
        db.query(QuarantineEmail)
        .filter(
            QuarantineEmail.status != "trash",
            or_(*email_filters),
        )
        .order_by(QuarantineEmail.created_at.desc())
        .limit(200)
        .all()
    )

    def extract_ip(content: str) -> str:
        """Extract plausible IP from raw content."""
        if not content:
            return ""
        for token in content.split():
            t = token.strip("[]<>()")
            parts = t.split(".")
            if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                return t
        return ""

    return [
        {
            "email_id": e.email_id,
            "subject": e.subject,
            "sender": e.sender,
            "recipient": e.recipient_list,
            "label": e.label,
            "status": e.status,
            "fused_score": e.fused_score,
            "sa_score": e.sa_score,
            "ml_probability": e.ml_probability,
            "anomaly_score": e.anomaly_score,
            "category": e.category,
            "received_at": e.received_at,
            "created_at": str(e.created_at) if e.created_at else "",
            "spf_result": e.spf_result or "",
            "dkim_result": e.dkim_result or "",
            "dmarc_result": e.dmarc_result or "",
            "sender_ip": extract_ip(e.raw_content or ""),
            "receiver_ip": "127.0.0.1",
            "sender_ip_safe": check_ip_reputation(extract_ip(e.raw_content or "")),
        }
        for e in emails
    ]


@app.get("/api/admin/track")
async def api_admin_track(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access tracking data")

    total_emails = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    total_clean = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "CLEAN").scalar() or 0
    total_warn = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0
    total_quarantine = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "QUARANTINE").scalar() or 0

    threat_ratio = (total_warn + total_quarantine) / max(total_emails, 1)
    if threat_ratio > 0.4:
        health_status = "critical"
        health_message = "High threat ratio detected. System may be compromised."
    elif threat_ratio > 0.2:
        health_status = "warning"
        health_message = "Elevated threat levels. Review recent emails and user activity."
    else:
        health_status = "healthy"
        health_message = "System is operating normally with low threat levels."

    organizations = []
    org_rows = db.query(Organization).order_by(Organization.name).all()
    for org in org_rows:
        org_total = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id).scalar() or 0
        org_threat = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.organization_id == org.id,
            QuarantineEmail.label.in_(["WARN", "QUARANTINE"])
        ).scalar() or 0
        organizations.append({
            "organization_id": org.id,
            "organization_name": org.name,
            "users": db.query(func.count(User.id)).filter(User.organization_id == org.id, User.role == UserRole.USER.value, User.is_active == True).scalar() or 0,
            "total_emails": org_total,
            "clean": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id, QuarantineEmail.label == "CLEAN").scalar() or 0,
            "warn": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id, QuarantineEmail.label == "WARN").scalar() or 0,
            "quarantine": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id, QuarantineEmail.label == "QUARANTINE").scalar() or 0,
            "threat_ratio": round(org_threat / max(org_total, 1), 3),
        })

    # --- Per-user stats with email counts ---
    all_users = db.query(User).filter(User.is_active == True).all()
    users_list = []
    for u in all_users:
        identifiers = [u.username.lower()]
        if u.email:
            identifiers.append(u.email.lower())
        email_filters = [
            or_(
                QuarantineEmail.recipient_list.ilike(f"%{identifier}%"),
                QuarantineEmail.sender.ilike(f"%{identifier}%"),
            )
            for identifier in identifiers
        ]
        user_emails = db.query(QuarantineEmail).filter(
            QuarantineEmail.status != "trash",
            or_(*email_filters),
        ).all()
        u_clean = sum(1 for e in user_emails if e.label == "CLEAN")
        u_warn = sum(1 for e in user_emails if e.label == "WARN")
        u_quar = sum(1 for e in user_emails if e.label == "QUARANTINE")
        u_total = len(user_emails)
        users_list.append({
            "username": u.username,
            "email": u.email or "",
            "role": u.role,
            "organization_id": u.organization_id,
            "organization_name": db.query(Organization.name).filter(Organization.id == u.organization_id).scalar() if u.organization_id else None,
            "total_emails": u_total,
            "clean": u_clean,
            "warn": u_warn,
            "quarantine": u_quar,
            "is_active": u.is_active,
        })

    admins = []
    admin_rows = db.query(User).filter(User.role.in_((UserRole.SUPERADMIN.value, UserRole.ADMIN.value))).all()
    for admin in admin_rows:
        org_name = None
        if admin.organization_id:
            org = db.query(Organization).filter(Organization.id == admin.organization_id).first()
            org_name = org.name if org else None
        admins.append({
            "username": admin.username,
            "email": admin.email,
            "role": admin.role,
            "organization_id": admin.organization_id,
            "organization_name": org_name,
            "active": admin.is_active,
            "recent_actions": [
                {
                    "action": a.action,
                    "details": a.details,
                    "ip_address": a.ip_address,
                    "created_at": str(a.created_at),
                }
                for a in db.query(AuditLog).filter(AuditLog.user == admin.username).order_by(AuditLog.created_at.desc()).limit(8).all()
            ],
            "suspicious_actions": [
                {
                    "action": a.action,
                    "details": a.details,
                    "ip_address": a.ip_address,
                    "created_at": str(a.created_at),
                }
                for a in db.query(AuditLog).filter(AuditLog.user == admin.username, AuditLog.ip_address != None).order_by(AuditLog.created_at.desc()).limit(5).all()
            ],
        })

    suspicious_activities = [
        {
            "user": a.user,
            "action": a.action,
            "details": a.details,
            "ip_address": a.ip_address,
            "created_at": str(a.created_at),
            "ip_safe": check_ip_reputation(a.ip_address),
        }
        for a in db.query(AuditLog).filter(AuditLog.ip_address != None).order_by(AuditLog.created_at.desc()).limit(40).all()
    ]

    return {
        "total_emails": total_emails,
        "total_clean": total_clean,
        "total_warn": total_warn,
        "total_quarantine": total_quarantine,
        "health_status": health_status,
        "health_message": health_message,
        "health_threat_ratio": round(threat_ratio, 3),
        "organizations": organizations,
        "users": users_list,
        "admins": admins,
        "suspicious_activities": suspicious_activities,
    }


# ─── Superadmin Email CRUD (from Tracking page) ──────────────────────────

@app.put("/api/admin/emails/{email_id}/release")
async def api_admin_release_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage emails")
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    email_record.status = "released"
    email_record.label = "CLEAN"
    email_record.category = "clean"
    log_audit(db, user_info["username"], "admin_release", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "released"}


@app.put("/api/admin/emails/{email_id}/confirm-spam")
async def api_admin_confirm_spam(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage emails")
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    email_record.status = "confirmed_spam"
    email_record.label = "QUARANTINE"
    email_record.category = "spam"
    log_audit(db, user_info["username"], "admin_confirm_spam", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "confirmed_spam", "label": "QUARANTINE", "category": "spam"}


@app.put("/api/admin/emails/{email_id}/update")
async def api_admin_update_email(email_id: str, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage emails")
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")

    allowed_fields = {"label", "category", "status", "subject", "sender", "fused_score"}
    updated = []
    for field in allowed_fields:
        if field in payload:
            setattr(email_record, field, payload[field])
            updated.append(field)

    log_audit(db, user_info["username"], "admin_update_email", email_id,
              request.client.host if request.client else None,
              f"Updated fields: {', '.join(updated)}")
    db.commit()
    return {"ok": True, "updated": updated}


@app.delete("/api/admin/emails/{email_id}")
async def api_admin_delete_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage emails")
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    db.delete(email_record)
    log_audit(db, user_info["username"], "admin_delete_email", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "deleted"}


@app.post("/api/admin/emails/batch")
async def api_admin_batch_emails(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can manage emails")

    email_ids = payload.get("email_ids", [])
    action = payload.get("action", "")  # delete, release, confirm_spam, update
    update_data = payload.get("update_data", {})

    if not email_ids or not action:
        raise HTTPException(status_code=400, detail="email_ids and action are required")

    results = {"success": 0, "failed": 0, "errors": []}
    for email_id in email_ids:
        email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
        if not email_record:
            results["failed"] += 1
            results["errors"].append(f"{email_id}: not found")
            continue
        try:
            if action == "delete":
                db.delete(email_record)
            elif action == "release":
                email_record.status = "released"
                email_record.label = "CLEAN"
                email_record.category = "clean"
            elif action == "confirm_spam":
                email_record.status = "confirmed_spam"
                email_record.label = "QUARANTINE"
                email_record.category = "spam"
            elif action == "update":
                for field, value in update_data.items():
                    if field in {"label", "category", "status", "subject", "sender", "fused_score"}:
                        setattr(email_record, field, value)
            else:
                results["failed"] += 1
                results["errors"].append(f"{email_id}: unknown action '{action}'")
                continue
            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{email_id}: {str(e)}")

    log_audit(db, user_info["username"], f"admin_batch_{action}", None,
              request.client.host if request.client else None,
              f"Batch {action}: {results['success']} success, {results['failed']} failed")
    db.commit()
    return {"ok": True, "results": results}


@app.get("/api/admin/system-health")
async def api_system_health(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access system health")

    services = {}

    # 1. PostgreSQL
    try:
        db.execute(func.count(QuarantineEmail.id))
        services["postgresql"] = {"status": "healthy", "detail": "Database connected"}
    except Exception as e:
        services["postgresql"] = {"status": "down", "detail": str(e)}

    # 2. Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")
        redis_client = aio_redis.from_url(redis_url)
        await redis_client.ping()
        await redis_client.aclose()
        services["redis"] = {"status": "healthy", "detail": "Connected and responding"}
    except Exception as e:
        services["redis"] = {"status": "down", "detail": str(e)}

    # 3. Classifier API
    try:
        classifier_url = os.getenv("CLASSIFIER_URL", "http://localhost:8001").rstrip("/")
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{classifier_url}/health")
            if r.status_code == 200:
                services["classifier_api"] = {"status": "healthy", "detail": "Responding on {0}".format(classifier_url)}
            else:
                services["classifier_api"] = {"status": "warning", "detail": "HTTP {0}".format(r.status_code)}
    except httpx.TimeoutException:
        services["classifier_api"] = {"status": "warning", "detail": "Connection timeout after 5s"}
    except Exception as e:
        services["classifier_api"] = {"status": "down", "detail": str(e)}

    # 4. SMTP Receiver
    try:
        smtp_host = os.getenv("SMTP_HOST", "localhost")
        smtp_port = int(os.getenv("SMTP_PUBLIC_PORT", os.getenv("SMTP_PORT", "2525")))
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(smtp_host, smtp_port), timeout=5
        )
        banner = await asyncio.wait_for(reader.readline(), timeout=3)
        writer.close()
        await writer.wait_closed()
        banner_text = banner.decode("utf-8", errors="replace").strip()
        services["smtp_receiver"] = {"status": "healthy", "detail": banner_text or "Connected"}
    except asyncio.TimeoutError:
        services["smtp_receiver"] = {"status": "warning", "detail": "Connection timeout"}
    except Exception as e:
        services["smtp_receiver"] = {"status": "down", "detail": str(e)}

    # 5. Worker Pipeline
    try:
        recent = db.query(PipelineMetrics).order_by(PipelineMetrics.created_at.desc()).first()
        if recent:
            services["worker_pipeline"] = {
                "status": "healthy",
                "detail": "Last run: {0}, processed: {1}".format(
                    recent.created_at.strftime("%Y-%m-%d %H:%M") if recent.created_at else "N/A",
                    recent.total_processed or 0
                )
            }
        else:
            services["worker_pipeline"] = {"status": "warning", "detail": "No pipeline metrics recorded yet"}
    except Exception as e:
        services["worker_pipeline"] = {"status": "down", "detail": str(e)}

    # 6. SpamAssassin
    try:
        sa_host = os.getenv("SPAMASSASSIN_HOST", "localhost")
        sa_port = int(os.getenv("SPAMASSASSIN_PORT", "783"))
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(sa_host, sa_port), timeout=5
        )
        writer.close()
        await writer.wait_closed()
        services["spamassassin"] = {"status": "healthy", "detail": "TCP connected on {0}:{1}".format(sa_host, sa_port)}
    except asyncio.TimeoutError:
        services["spamassassin"] = {"status": "warning", "detail": "Connection timeout"}
    except Exception as e:
        services["spamassassin"] = {"status": "down", "detail": str(e)}

    # 7. Dashboard Backend (self)
    ws_count = len(manager.active_connections)
    services["dashboard_backend"] = {
        "status": "healthy",
        "detail": "WebSocket connections: {0}, uptime: N/A".format(ws_count)
    }

    # 8. Docker Containers
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            containers = [c for c in result.stdout.strip().split("\n") if c]
            services["docker"] = {
                "status": "healthy" if containers else "warning",
                "detail": "{0} running container(s)".format(len(containers)),
                "containers": containers
            }
        else:
            services["docker"] = {"status": "warning", "detail": "Docker not accessible"}
    except FileNotFoundError:
        services["docker"] = {"status": "warning", "detail": "Docker CLI not found"}
    except subprocess.TimeoutExpired:
        services["docker"] = {"status": "warning", "detail": "Docker command timed out"}
    except Exception as e:
        services["docker"] = {"status": "warning", "detail": str(e)}

    # Overall status
    statuses = [s["status"] for s in services.values()]
    if "down" in statuses:
        overall = "down"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "healthy"

    return {
        "overall": overall,
        "services": services,
        "checked_at": app_now_iso(),
    }


# ─── Report Generation Endpoints ─────────────────────────────────────────────

def _get_scope_emails(db: Session, scope: str) -> set:
    emails = set()
    if scope == "admin":
        admin_users = db.query(User).filter(User.role == "admin", User.is_active == True).all()
        for adm in admin_users:
            if adm.email:
                emails.add(adm.email.lower())
            mboxes = db.query(AdminMailbox).filter(
                AdminMailbox.assigned_to == adm.username,
                AdminMailbox.is_active == True
            ).all()
            for mb in mboxes:
                emails.add(mb.email.lower())
        sa_users = db.query(User).filter(User.role == "superadmin", User.is_active == True).all()
        for sa in sa_users:
            if sa.email:
                emails.add(sa.email.lower())
    elif scope == "user":
        user_rows = db.query(User).filter(User.role == "user", User.is_active == True).all()
        for u in user_rows:
            if u.email:
                emails.add(u.email.lower())
        unassigned_mboxes = db.query(AdminMailbox).filter(
            AdminMailbox.is_active == True,
            AdminMailbox.assigned_to == ""
        ).all()
        for mb in unassigned_mboxes:
            emails.add(mb.email.lower())
    return emails


def _fmt_email_datetime(val):
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M")
    if val:
        try:
            return str(val)[:16]
        except Exception:
            return str(val)
    return "-"


def _build_html_row(cells, tag="td"):
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


@app.get("/api/admin/export-report/pdf")
async def api_export_report_pdf(request: Request, scope: str = "all", db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can generate reports")

    now = datetime.now(APP_TIMEZONE)
    today_str = now.strftime("%Y-%m-%d")
    month_name = now.strftime("%B")

    base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
    if scope in ("admin", "user"):
        target_emails = _get_scope_emails(db, scope)
        if target_emails:
            from sqlalchemy import or_
            filters = [QuarantineEmail.recipient_list.contains(e, autoescape=True) for e in target_emails]
            base = base.filter(or_(*filters))
        else:
            base = base.filter(QuarantineEmail.id < 0)
    total_emails = base.count() or 0
    total_clean = base.filter(QuarantineEmail.label == "CLEAN").count() or 0
    total_spam = base.filter(QuarantineEmail.category == "spam").count() or 0
    total_phishing = base.filter(QuarantineEmail.category == "phishing").count() or 0
    total_malware = base.filter(QuarantineEmail.category == "malware").count() or 0
    total_quarantine = base.filter(QuarantineEmail.label == "QUARANTINE").count() or 0
    total_warn = base.filter(QuarantineEmail.label == "WARN").count() or 0
    total_released = base.filter(QuarantineEmail.status == "released").count() or 0
    total_threats = total_quarantine + total_warn
    threat_pct = round(total_threats / max(total_emails, 1) * 100, 1)
    safe_pct = round(total_clean / max(total_emails, 1) * 100, 1)

    org_rows = db.query(Organization).order_by(Organization.name).all()
    org_stats = []
    for org in org_rows:
        oe = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id).scalar() or 0
        ou = db.query(func.count(User.id)).filter(User.organization_id == org.id, User.is_active == True).scalar() or 0
        o_threat = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.organization_id == org.id, QuarantineEmail.label.in_(["WARN", "QUARANTINE"])
        ).scalar() or 0
        org_stats.append({"name": org.name, "emails": oe, "users": ou, "threats": o_threat})

    all_users = db.query(User).filter(User.is_active == True).order_by(User.role, User.username).all()
    admins = [u for u in all_users if u.role in ("superadmin", "admin")]
    reg_users = [u for u in all_users if u.role == "user"]
    total_users_count = len(all_users)
    total_mailboxes = db.query(func.count(AdminMailbox.id)).filter(AdminMailbox.is_active == True).scalar() or 0

    all_emails = base.order_by(QuarantineEmail.created_at.desc()).limit(500).all()

    auth_emails = base.filter(QuarantineEmail.label.in_(["WARN", "QUARANTINE"])).limit(200).all()
    spf_pass = sum(1 for e in auth_emails if (e.spf_result or "").upper() == "PASS")
    dkim_pass = sum(1 for e in auth_emails if (e.dkim_result or "").upper() == "PASS")
    dmarc_pass = sum(1 for e in auth_emails if (e.dmarc_result or "").upper() == "PASS")
    spf_fail = sum(1 for e in auth_emails if (e.spf_result or "").upper() in ("FAIL", "SOFTFAIL"))
    dkim_fail = sum(1 for e in auth_emails if (e.dkim_result or "").upper() in ("FAIL", "SOFTFAIL"))
    dmarc_fail = sum(1 for e in auth_emails if (e.dmarc_result or "").upper() in ("FAIL", "SOFTFAIL"))
    auth_total = len(auth_emails) or 1

    top_senders = base.with_entities(
        QuarantineEmail.sender, func.count(QuarantineEmail.id).label("cnt")
    ).filter(QuarantineEmail.sender != "").group_by(QuarantineEmail.sender).order_by(func.count(QuarantineEmail.id).desc()).limit(20).all()

    recent_detections = base.filter(
        QuarantineEmail.label.in_(["QUARANTINE", "WARN"]),
        ~QuarantineEmail.status.in_(["trash", "released"]),
    ).order_by(QuarantineEmail.created_at.desc()).limit(50).all()

    reports = db.query(Report).order_by(Report.created_at.desc()).limit(30).all()

    from fpdf import FPDF

    class ReportPDF(FPDF):
        def header(self):
            if self.page_no() <= 2:
                return
            self.set_font("Helvetica", "I", 6)
            self.set_text_color(148, 163, 184)
            self.cell(0, 4, "CogniMail Security Report", align="L")
            self.cell(0, 4, f"Halaman {self.page_no() - 2}", align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(148, 163, 184)
            self.line(10, 12, 200, 12)
            self.ln(3)

        def footer(self):
            if self.page_no() <= 2:
                return
            self.set_y(-12)
            self.set_font("Helvetica", "I", 6)
            self.set_text_color(148, 163, 184)
            self.set_draw_color(148, 163, 184)
            self.line(10, 285, 200, 285)
            self.cell(0, 4, f"CONFIDENTIAL  |  Generated {now.strftime('%d %B %Y %H:%M')}", align="C")

        def section_title(self, num, title):
            self.ln(4)
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(26, 115, 232)
            self.cell(0, 7, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(26, 115, 232)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(3)

        def sub_title(self, text):
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(55, 65, 81)
            self.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

        def body_text(self, text):
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(107, 114, 128)
            self.multi_cell(0, 4, text)
            self.ln(2)

        def stat_card(self, value, label, sub, color_r, color_g, color_b):
            x = self.get_x()
            y = self.get_y()
            w = 44
            h = 22
            self.set_fill_color(248, 250, 252)
            self.set_draw_color(226, 232, 240)
            self.rect(x, y, w, h, style="DF")
            self.set_xy(x + 2, y + 3)
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(color_r, color_g, color_b)
            self.cell(w - 4, 7, str(value), align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_x(x + 2)
            self.set_font("Helvetica", "B", 5.5)
            self.set_text_color(100, 116, 139)
            self.cell(w - 4, 3.5, label, align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_x(x + 2)
            self.set_font("Helvetica", "", 5)
            self.set_text_color(148, 163, 184)
            self.cell(w - 4, 3.5, sub, align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_xy(x + w + 2, y)

        def bar_chart(self, label, pct, r, g, b):
            bar_w = 120
            self.set_font("Helvetica", "B", 7)
            self.set_text_color(r, g, b)
            self.cell(50, 5, label, new_x="LMARGIN", new_y="NEXT")
            self.set_fill_color(241, 245, 249)
            self.rect(60, self.get_y() + 0.5, bar_w, 4, style="F")
            fill_w = max(bar_w * pct / 100, 2)
            self.set_fill_color(r, g, b)
            self.rect(60, self.get_y() + 0.5, fill_w, 4, style="F")
            self.set_xy(60 + bar_w + 3, self.get_y())
            self.set_font("Helvetica", "B", 7)
            self.cell(20, 5, f"{pct}%")
            self.ln(7)

        def table_header(self, cols, widths=None):
            if widths is None:
                widths = [190 / len(cols)] * len(cols)
            self.set_fill_color(26, 115, 232)
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 6)
            for i, col in enumerate(cols):
                self.cell(widths[i], 6, col, border=1, fill=True, align="C")
            self.ln()
            self.set_text_color(31, 41, 55)
            self.set_font("Helvetica", "", 6.5)

        def table_row(self, cells, widths=None, aligns=None, fill=False):
            if widths is None:
                widths = [190 / len(cells)] * len(cells)
            if aligns is None:
                aligns = ["L"] * len(cells)
            if fill:
                self.set_fill_color(248, 250, 252)
            else:
                self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(cells):
                self.cell(widths[i], 4.5, str(cell), border=1, fill=True, align=aligns[i])
            self.ln()

        def check_page_break(self, h=20):
            if self.get_y() + h > 270:
                self.add_page()

    pdf = ReportPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=True, margin=18)

    # ── COVER PAGE ──
    pdf.add_page()
    pdf.ln(70)
    pdf.set_font("Helvetica", "", 40)
    pdf.set_text_color(26, 115, 232)
    pdf.cell(0, 15, "CogniMail Security Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(26, 115, 232)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 7, "Laporan Keamanan Email", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(55, 65, 81)
    for line in [
        f"Tanggal Laporan: {now.strftime('%d %B %Y')}",
        f"Waktu Generate: {now.strftime('%H:%M %Z')}",
        f"Periode: {today_str}",
        f"Total Email Diproses: {total_emails:,}",
        f"Total Pengguna Aktif: {total_users_count}",
    ]:
        pdf.cell(0, 6, line, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(26, 115, 232)
    pdf.set_draw_color(26, 115, 232)
    pdf.rect(65, pdf.get_y(), 80, 8, style="D")
    pdf.cell(0, 8, "RAHASIA - INTERNAL", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── TOC ──
    pdf.add_page()
    pdf.section_title("", "Daftar Isi")
    toc_items = [
        "Executive Summary", "Threat Breakdown", "Organizations Overview",
        "Per-User Email Analysis", "Authentication Metrics (SPF/DKIM/DMARC)",
        "Top Senders", "Recent Security Detections", "User Reports & Feedback",
        "Complete Email Log"
    ]
    for i, item in enumerate(toc_items, 1):
        pdf.set_draw_color(229, 231, 235)
        y = pdf.get_y()
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(26, 115, 232)
        pdf.cell(8, 6, str(i))
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(31, 41, 55)
        pdf.cell(0, 6, item, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(229, 231, 235)
        pdf.line(18, pdf.get_y() - 0.5, 200, pdf.get_y() - 0.5)

    # ── 1. EXECUTIVE SUMMARY ──
    pdf.add_page()
    pdf.section_title(1, "Executive Summary")
    pdf.body_text("Ringkasan keseluruhan status keamanan email pada platform CogniMail.")
    pdf.check_page_break(50)
    pos = pdf.get_y()
    pdf.stat_card(f"{total_emails:,}", "TOTAL EMAIL", "Semua organisasi", 26, 115, 232)
    pdf.stat_card(f"{total_clean:,}", "AMAN / CLEAN", f"{safe_pct}% dari total", 5, 150, 105)
    pdf.ln(24)
    pdf.set_x(10)
    pdf.stat_card(f"{total_warn:,}", "SPAM / WARN", "Mencurigakan", 217, 119, 6)
    pdf.stat_card(f"{total_threats:,}", "ANCAMAN", f"{threat_pct}% threat ratio", 220, 38, 38)
    pdf.ln(24)
    pdf.set_x(10)
    pdf.stat_card(f"{total_phishing:,}", "PHISHING", "Percobaan pencurian data", 124, 58, 237)
    pdf.stat_card(f"{total_malware:,}", "MALWARE", "Lampiran berbahaya", 197, 34, 31)
    pdf.ln(24)
    pdf.set_x(10)
    pdf.stat_card(f"{total_users_count}", "PENGGUNA AKTIF", f"{total_mailboxes} mailbox", 26, 115, 232)
    pdf.stat_card(f"{total_released:,}", "DIRILIS", "False positive", 5, 150, 105)
    pdf.ln(14)

    pdf.set_x(10)
    pdf.sub_title("Distribusi Keamanan")
    spam_warn_pct = round(total_warn / max(total_emails, 1) * 100, 1)
    phish_mal_pct = round((total_phishing + total_malware) / max(total_emails, 1) * 100, 1)
    pdf.bar_chart("Aman / Clean", safe_pct, 5, 150, 105)
    pdf.bar_chart("Spam / Warn", spam_warn_pct, 217, 119, 6)
    pdf.bar_chart("Phishing + Malware", phish_mal_pct, 220, 38, 38)

    # ── 2. THREAT BREAKDOWN ──
    pdf.check_page_break()
    pdf.section_title(2, "Threat Breakdown")
    pdf.body_text("Rincian email berdasarkan kategori ancaman.")
    cols = ["Kategori", "Jumlah", "Persentase", "Status"]
    widths = [60, 40, 45, 45]
    pdf.table_header(cols, widths)
    rows_data = [
        ("Clean - Email aman", f"{total_clean:,}", f"{round(total_clean/max(total_emails,1)*100,1)}%", "Aman"),
        ("Spam - Email spam/promosi", f"{total_spam:,}", f"{round(total_spam/max(total_emails,1)*100,1)}%", "Spam"),
        ("Phishing - Percobaan phishing", f"{total_phishing:,}", f"{round(total_phishing/max(total_emails,1)*100,1)}%", "Critical"),
        ("Malware - Lampiran berbahaya", f"{total_malware:,}", f"{round(total_malware/max(total_emails,1)*100,1)}%", "Critical"),
        ("Warn - Mencurigakan", f"{total_warn:,}", f"{round(total_warn/max(total_emails,1)*100,1)}%", "Warning"),
    ]
    for i, row in enumerate(rows_data):
        pdf.table_row(row, widths, fill=i % 2 == 1)

    # ── 3. ORGANIZATIONS ──
    pdf.check_page_break()
    pdf.section_title(3, "Organizations Overview")
    pdf.body_text("Statistik per organisasi yang terdaftar dalam platform.")
    widths3 = [60, 40, 40, 25, 25]
    pdf.table_header(["Organisasi", "Pengguna Aktif", "Email Diproses", "Ancaman", "Threat Ratio"], widths3)
    for i, org_s in enumerate(org_stats):
        o_tr = round(org_s["threats"] / max(org_s["emails"], 1) * 100, 1) if org_s["emails"] else 0
        pdf.table_row([org_s["name"], str(org_s["users"]), f"{org_s['emails']:,}", str(org_s["threats"]), f"{o_tr}%"], widths3, fill=i % 2 == 1)

    # ── 4. PER-USER EMAIL ANALYSIS ──
    pdf.check_page_break()
    pdf.section_title(4, "Per-User Email Analysis")
    pdf.body_text("Rincian email per pengguna termasuk admin dan user biasa.")
    pdf.sub_title("4.1 Admin & Superadmin")
    w4 = [30, 22, 40, 20, 20, 20, 38]
    pdf.table_header(["Username", "Role", "Email", "Total", "Clean", "Warn", "Quarantine"], w4)
    for i, u in enumerate(admins):
        identifiers = [u.username.lower()]
        if u.email:
            identifiers.append(u.email.lower())
        filters = [QuarantineEmail.recipient_list.ilike(f"%{idn}%") for idn in identifiers]
        filters += [QuarantineEmail.sender.ilike(f"%{idn}%") for idn in identifiers]
        u_base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash", or_(*filters))
        u_tot = u_base.count() or 0
        u_clean = u_base.filter(QuarantineEmail.label == "CLEAN").count() or 0
        u_warn = u_base.filter(QuarantineEmail.label == "WARN").count() or 0
        u_quar = u_base.filter(QuarantineEmail.label == "QUARANTINE").count() or 0
        pdf.table_row([u.username, u.role, (u.email or "-")[:20], str(u_tot), str(u_clean), str(u_warn), str(u_quar)], w4, fill=i % 2 == 1)

    pdf.check_page_break()
    pdf.sub_title("4.2 Regular Users")
    w4b = [26, 40, 20, 20, 20, 20, 20, 24]
    pdf.table_header(["Username", "Email", "Total", "Clean", "Spam", "Phish", "Malware", "Org"], w4b)
    org_cache = {}
    for i, u in enumerate(reg_users):
        identifiers = [u.username.lower()]
        if u.email:
            identifiers.append(u.email.lower())
        filters = [QuarantineEmail.recipient_list.ilike(f"%{idn}%") for idn in identifiers]
        filters += [QuarantineEmail.sender.ilike(f"%{idn}%") for idn in identifiers]
        u_base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash", or_(*filters))
        u_tot = u_base.count() or 0
        u_clean = u_base.filter(QuarantineEmail.label == "CLEAN").count() or 0
        u_spam = u_base.filter(QuarantineEmail.category == "spam").count() or 0
        u_phish = u_base.filter(QuarantineEmail.category == "phishing").count() or 0
        u_mal = u_base.filter(QuarantineEmail.category == "malware").count() or 0
        org_name = ""
        if u.organization_id:
            if u.organization_id not in org_cache:
                o = db.query(Organization).filter(Organization.id == u.organization_id).first()
                org_cache[u.organization_id] = o.name if o else ""
            org_name = org_cache[u.organization_id]
        pdf.table_row([u.username, (u.email or "-")[:22], str(u_tot), str(u_clean), str(u_spam), str(u_phish), str(u_mal), org_name[:12]], w4b, fill=i % 2 == 1)

    # ── 4.3 PER-EMAIL BREAKDOWN (ADMIN SCOPE) ──
    if scope == "admin":
        pdf.check_page_break()
        pdf.sub_title("4.3 Per-Email Breakdown (Admin Scope)")
        pdf.body_text("Breakdown email per alamat email dalam scope admin.")
        w43 = [50, 28, 28, 28, 28, 28]
        pdf.table_header(["Email Address", "Total", "Spam", "Phishing", "Malware", "Clean"], w43)
        target_emails_43 = _get_scope_emails(db, scope)
        email_rows_43 = []
        for eaddr in sorted(target_emails_43):
            eb = db.query(QuarantineEmail).filter(
                QuarantineEmail.recipient_list.contains(eaddr, autoescape=True),
                QuarantineEmail.status != "trash",
            )
            etot = eb.count() or 0
            espm = eb.filter(QuarantineEmail.category == "spam").count() or 0
            ephish = eb.filter(QuarantineEmail.category == "phishing").count() or 0
            emal = eb.filter(QuarantineEmail.category == "malware").count() or 0
            eclean = eb.filter(QuarantineEmail.label == "CLEAN").count() or 0
            email_rows_43.append((eaddr, etot, espm, ephish, emal, eclean))
        email_rows_43.sort(key=lambda x: -x[1])
        for i, (eaddr, etot, espm, ephish, emal, eclean) in enumerate(email_rows_43):
            pdf.table_row([eaddr[:30], str(etot), str(espm), str(ephish), str(emal), str(eclean)], w43, fill=i % 2 == 1)
        pdf.ln(4)

        # ── 4.4 DETAILED EMAIL RECORDS (ADMIN SCOPE) ──
        pdf.check_page_break()
        pdf.sub_title("4.4 Detailed Email Records")
        pdf.body_text("Daftar lengkap email dengan detail IP, sender, subject, score, tanggal.")
        w44 = [28, 36, 40, 14, 14, 14, 18, 16, 10]
        pdf.table_header(["ID", "Sender", "Subject", "Spam", "Phish", "Mal.", "Score", "Received", "SPF"], w44)
        detailed_records = base.order_by(QuarantineEmail.created_at.desc()).limit(200).all()
        for i, rec in enumerate(detailed_records):
            pdf.check_page_break(h=10)
            is_spam = "Y" if rec.category == "spam" else ""
            is_phish = "Y" if rec.category == "phishing" else ""
            is_mal = "Y" if rec.category == "malware" else ""
            pdf.table_row([
                (rec.email_id or "")[:12],
                (rec.sender or "")[:20],
                (rec.subject or "")[:26],
                is_spam, is_phish, is_mal,
                f"{rec.fused_score:.3f}" if rec.fused_score is not None else "",
                _fmt_email_datetime(rec.received_at),
                (rec.spf_result or "-")[:4],
            ], w44, fill=i % 2 == 1)
        pdf.ln(4)

    # ── 5. AUTH METRICS ──
    pdf.check_page_break()
    pdf.section_title(5, "Authentication Metrics (SPF / DKIM / DMARC)")
    pdf.body_text("Analisis hasil autentikasi email untuk email dalam kategori WARN dan QUARANTINE.")
    widths5 = [70, 40, 40, 40]
    pdf.table_header(["Metrik", "Pass", "Fail", "Pass Rate"], widths5)
    pdf.table_row(["SPF - Sender Policy Framework", str(spf_pass), str(spf_fail), f"{round(spf_pass/auth_total*100,1)}%"], widths5, fill=False)
    pdf.table_row(["DKIM - DomainKeys Identified Mail", str(dkim_pass), str(dkim_fail), f"{round(dkim_pass/auth_total*100,1)}%"], widths5, fill=True)
    pdf.table_row(["DMARC - Domain-based Message Auth.", str(dmarc_pass), str(dmarc_fail), f"{round(dmarc_pass/auth_total*100,1)}%"], widths5, fill=False)

    # ── 6. TOP SENDERS ──
    pdf.check_page_break()
    pdf.section_title(6, "Top Senders")
    pdf.body_text("20 pengirim email terbanyak dalam sistem.")
    widths6 = [15, 130, 45]
    pdf.table_header(["#", "Pengirim", "Jumlah Email"], widths6)
    for i, (sender, cnt) in enumerate(top_senders, 1):
        pdf.table_row([str(i), (sender or "-")[:45], str(cnt)], widths6, fill=i % 2 == 1)

    # ── 7. RECENT SECURITY DETECTIONS ──
    pdf.check_page_break()
    pdf.section_title(7, "Recent Security Detections")
    pdf.body_text("50 deteksi keamanan terbaru yang diblokir oleh sistem.")
    widths7 = [32, 42, 50, 24, 20, 22]
    pdf.table_header(["Email ID", "Sender", "Subject", "Label", "Score", "Received"], widths7)
    for i, e in enumerate(recent_detections):
        pdf.table_row([
            (e.email_id or "")[:16],
            (e.sender or "")[:20],
            (e.subject or "")[:28],
            e.label or "",
            f"{e.fused_score:.3f}" if e.fused_score is not None else "",
            _fmt_email_datetime(e.received_at),
        ], widths7, fill=i % 2 == 1)

    # ── 8. USER REPORTS ──
    if reports:
        pdf.check_page_break()
        pdf.section_title(8, "User Reports & Feedback")
        pdf.body_text("Laporan dan masukan yang dikirim oleh pengguna.")
        widths8 = [22, 40, 22, 22, 22, 32, 30]
        pdf.table_header(["User", "Subject", "Category", "Priority", "Status", "Date", "Email"], widths8)
        for i, r in enumerate(reports):
            pdf.table_row([
                r.username or "",
                (r.subject or "")[:24],
                r.category or "",
                r.priority or "",
                r.status or "",
                _fmt_email_datetime(r.created_at),
                (r.email or "")[:16],
            ], widths8, fill=i % 2 == 1)

    # ── 9. COMPLETE EMAIL LOG ──
    pdf.check_page_break()
    pdf.section_title(9, "Complete Email Log")
    pdf.body_text("Log lengkap seluruh email yang diproses oleh sistem (maksimal 500 baris).")
    widths9 = [28, 28, 28, 16, 16, 16, 14, 14, 14, 16]
    pdf.table_header(["ID", "Sender", "Subject", "Label", "Cat.", "Fused", "SPF", "DKIM", "DMARC", "Status"], widths9)
    for i, e in enumerate(all_emails[:500]):
        pdf.check_page_break(h=12)
        pdf.table_row([
            (e.email_id or "")[:12],
            (e.sender or "")[:16],
            (e.subject or "")[:18],
            e.label or "",
            (e.category or "-")[:6],
            f"{e.fused_score:.3f}" if e.fused_score is not None else "",
            (e.spf_result or "-")[:6],
            (e.dkim_result or "-")[:6],
            (e.dmarc_result or "-")[:6],
            e.status or "",
        ], widths9, fill=i % 2 == 1)

    pdf_bytes = pdf.output()
    filename = f"cognimail_report_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/admin/export-report/excel")
async def api_export_report_excel(request: Request, scope: str = "all", db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can generate reports")

    now = datetime.now(APP_TIMEZONE)
    base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
    if scope in ("admin", "user"):
        target_emails = _get_scope_emails(db, scope)
        if target_emails:
            from sqlalchemy import or_
            filters = [QuarantineEmail.recipient_list.contains(e, autoescape=True) for e in target_emails]
            base = base.filter(or_(*filters))
        else:
            base = base.filter(QuarantineEmail.id < 0)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== COGNIMAIL SECURITY REPORT ==="])
    writer.writerow([f"Generated: {now.strftime('%Y-%m-%d %H:%M %Z')}"])
    writer.writerow([])

    total_emails = base.count() or 0
    total_clean = base.filter(QuarantineEmail.label == "CLEAN").count() or 0
    total_spam = base.filter(QuarantineEmail.category == "spam").count() or 0
    total_phishing = base.filter(QuarantineEmail.category == "phishing").count() or 0
    total_malware = base.filter(QuarantineEmail.category == "malware").count() or 0
    total_quarantine = base.filter(QuarantineEmail.label == "QUARANTINE").count() or 0
    total_warn = base.filter(QuarantineEmail.label == "WARN").count() or 0
    total_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_mailboxes = db.query(func.count(AdminMailbox.id)).filter(AdminMailbox.is_active == True).scalar() or 0

    writer.writerow(["=== SUMMARY ==="])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Users", total_users])
    writer.writerow(["Active Mailboxes", total_mailboxes])
    writer.writerow(["Total Emails Processed", total_emails])
    writer.writerow(["Clean Emails", total_clean])
    writer.writerow(["Spam Detected", total_spam])
    writer.writerow(["Phishing Detected", total_phishing])
    writer.writerow(["Malware Detected", total_malware])
    writer.writerow(["Warn Flagged", total_warn])
    writer.writerow(["Quarantined", total_quarantine])
    writer.writerow([])

    writer.writerow(["=== PER-USER EMAIL BREAKDOWN ==="])
    writer.writerow(["Username", "Role", "Organization", "Total Emails", "Clean", "Warn", "Quarantine", "Spam", "Phishing", "Malware"])
    all_users = db.query(User).filter(User.is_active == True).order_by(User.role).all()
    for u in all_users:
        org_name = ""
        if u.organization_id:
            org = db.query(Organization).filter(Organization.id == u.organization_id).first()
            org_name = org.name if org else ""
        total_u = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.recipient_list.contains(u.email if u.email else u.username)).scalar() or 0
        clean_u = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.recipient_list.contains(u.email if u.email else u.username),
            QuarantineEmail.label == "CLEAN"
        ).scalar() or 0
        warn_u = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.recipient_list.contains(u.email if u.email else u.username),
            QuarantineEmail.label == "WARN"
        ).scalar() or 0
        quar_u = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.recipient_list.contains(u.email if u.email else u.username),
            QuarantineEmail.label == "QUARANTINE"
        ).scalar() or 0
        spam_u = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.recipient_list.contains(u.email if u.email else u.username),
            QuarantineEmail.category == "spam"
        ).scalar() or 0
        phish_u = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.recipient_list.contains(u.email if u.email else u.username),
            QuarantineEmail.category == "phishing"
        ).scalar() or 0
        mal_u = db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.recipient_list.contains(u.email if u.email else u.username),
            QuarantineEmail.category == "malware"
        ).scalar() or 0
        writer.writerow([u.username, u.role, org_name, total_u, clean_u, warn_u, quar_u, spam_u, phish_u, mal_u])
    writer.writerow([])

    if scope == "admin":
        writer.writerow(["=== PER-EMAIL BREAKDOWN (ADMIN SCOPE) ==="])
        writer.writerow(["Email Address", "Total", "Spam", "Phishing", "Malware", "Clean"])
        target_emails_43 = _get_scope_emails(db, scope)
        for eaddr in sorted(target_emails_43):
            eb = db.query(QuarantineEmail).filter(
                QuarantineEmail.recipient_list.contains(eaddr, autoescape=True),
                QuarantineEmail.status != "trash",
            )
            etot = eb.count() or 0
            espm = eb.filter(QuarantineEmail.category == "spam").count() or 0
            ephish = eb.filter(QuarantineEmail.category == "phishing").count() or 0
            emal = eb.filter(QuarantineEmail.category == "malware").count() or 0
            eclean = eb.filter(QuarantineEmail.label == "CLEAN").count() or 0
            writer.writerow([eaddr, etot, espm, ephish, emal, eclean])
        writer.writerow([])

        writer.writerow(["=== DETAILED EMAIL RECORDS (ADMIN SCOPE) ==="])
        writer.writerow([
            "Email ID", "Sender", "Subject", "Recipient(s)",
            "Label", "Category", "Spam", "Phishing", "Malware",
            "Fused Score", "ML Prob", "Anomaly Score",
            "SPF", "DKIM", "DMARC",
            "Received At", "Created At"
        ])
        detailed_records = base.order_by(QuarantineEmail.created_at.desc()).limit(1000).all()
        for rec in detailed_records:
            writer.writerow([
                rec.email_id or "",
                rec.sender or "",
                rec.subject or "",
                rec.recipient_list or "",
                rec.label or "",
                rec.category or "",
                "Y" if rec.category == "spam" else "",
                "Y" if rec.category == "phishing" else "",
                "Y" if rec.category == "malware" else "",
                f"{rec.fused_score:.4f}" if rec.fused_score is not None else "",
                f"{rec.ml_probability:.4f}" if rec.ml_probability is not None else "",
                f"{rec.anomaly_score:.4f}" if rec.anomaly_score is not None else "",
                rec.spf_result or "",
                rec.dkim_result or "",
                rec.dmarc_result or "",
                _fmt_email_datetime(rec.received_at),
                _fmt_email_datetime(rec.created_at),
            ])
        writer.writerow([])

    writer.writerow(["=== COMPLETE EMAIL DATA DUMP ==="])
    writer.writerow([
        "Email ID", "Sender", "Recipient(s)", "Subject", "Body Preview",
        "Label", "Category", "Status",
        "Fused Score", "ML Probability", "SA Score", "Anomaly Score",
        "SPF Result", "DKIM Result", "DMARC Result",
        "Organization ID", "Organization Name",
        "Received At", "Created At"
    ])
    all_emails_dump = base.order_by(QuarantineEmail.received_at.desc()).limit(5000).all()
    org_cache = {}
    for e in all_emails_dump:
        org_name = ""
        if e.organization_id:
            if e.organization_id not in org_cache:
                o = db.query(Organization).filter(Organization.id == e.organization_id).first()
                org_cache[e.organization_id] = o.name if o else ""
            org_name = org_cache[e.organization_id]
        body_preview = ""
        if e.raw_content:
            try:
                body_preview = e.raw_content[:200].replace("\n", " ").replace("\r", "")
            except Exception:
                body_preview = e.raw_content[:200]
        writer.writerow([
            e.email_id or "",
            e.sender or "",
            e.recipient_list or "",
            e.subject or "",
            body_preview,
            e.label or "",
            e.category or "",
            e.status or "",
            f"{e.fused_score:.4f}" if e.fused_score is not None else "",
            f"{e.ml_probability:.4f}" if e.ml_probability is not None else "",
            f"{e.sa_score:.4f}" if e.sa_score is not None else "",
            f"{e.anomaly_score:.4f}" if e.anomaly_score is not None else "",
            e.spf_result or "",
            e.dkim_result or "",
            e.dmarc_result or "",
            e.organization_id or "",
            org_name,
            _fmt_email_datetime(e.received_at),
            _fmt_email_datetime(e.created_at),
        ])

    output.seek(0)
    filename = f"cognimail_report_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/superadmin/spam-stats")
async def api_superadmin_spam_stats(
    request: Request,
    scope: str = "all",
    category: str = "all",
    limit: int = 50,
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access this endpoint")

    categories = {"spam", "phishing", "malware", "clean"}
    filter_cat = None if category == "all" or category not in categories else category

    base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
    if filter_cat:
        base = base.filter(QuarantineEmail.category == filter_cat)

    all_user_emails = set()
    all_admin_emails = set()
    admin_email_map = {}

    admin_users = db.query(User).filter(User.role == "admin", User.is_active == True).all()
    for adm in admin_users:
        if adm.email:
            all_admin_emails.add(adm.email.lower())
        admin_mboxes = db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == adm.username,
            AdminMailbox.is_active == True
        ).all()
        mbox_emails = []
        for mb in admin_mboxes:
            e = mb.email.lower()
            all_admin_emails.add(e)
            mbox_emails.append(e)
        admin_email_map[adm.username] = {
            "username": adm.username,
            "email": adm.email,
            "organization_id": adm.organization_id,
            "mailboxes": mbox_emails,
            "total_users": db.query(func.count(User.id)).filter(
                User.organization_id == adm.organization_id, User.role == "user", User.is_active == True
            ).scalar() or 0,
        }

    regular_users = db.query(User).filter(User.role == "user", User.is_active == True).all()
    user_email_map = {}
    for u in regular_users:
        if u.email:
            e = u.email.lower()
            all_user_emails.add(e)
            user_email_map[u.username] = {"username": u.username, "email": e, "organization_id": u.organization_id}

    mailbox_rows = db.query(AdminMailbox).filter(AdminMailbox.is_active == True).all()
    for mb in mailbox_rows:
        e = mb.email.lower()
        if not mb.assigned_to:
            all_user_emails.add(e)

    global_all = all_admin_emails | all_user_emails

    from sqlalchemy import func as sql_func, or_
    from sqlalchemy.types import String

    all_recipients_emails = db.query(QuarantineEmail.recipient_list).filter(
        QuarantineEmail.recipient_list != "",
        QuarantineEmail.status != "trash",
    ).all()

    recipient_counts = {}
    for (rlist,) in all_recipients_emails:
        parts = [p.strip().lower() for p in rlist.replace(";", ",").split(",") if p.strip()]
        for addr in parts:
            if scope == "admin" and addr not in all_admin_emails:
                continue
            if scope == "user" and addr not in all_user_emails:
                continue
            if scope == "all" and addr not in global_all:
                continue
            recipient_counts[addr] = recipient_counts.get(addr, 0) + 1

    sorted_recipients = sorted(recipient_counts.items(), key=lambda x: -x[1])[:limit]

    result_rows = []
    for addr, total_count in sorted_recipients:
        cat_base = db.query(QuarantineEmail).filter(
            QuarantineEmail.recipient_list.contains(addr, autoescape=True),
            QuarantineEmail.status != "trash",
        )
        spam_count = cat_base.filter(QuarantineEmail.category == "spam").count() or 0
        phish_count = cat_base.filter(QuarantineEmail.category == "phishing").count() or 0
        mal_count = cat_base.filter(QuarantineEmail.category == "malware").count() or 0
        clean_count = cat_base.filter(QuarantineEmail.label == "CLEAN").count() or 0

        owner_type = "admin" if addr in all_admin_emails else "user"
        owner_username = ""
        if owner_type == "admin":
            for uname, info in admin_email_map.items():
                if addr == info["email"] or addr in info["mailboxes"]:
                    owner_username = uname
                    break
        else:
            for uname, info in user_email_map.items():
                if addr == info["email"]:
                    owner_username = uname
                    break

        result_rows.append({
            "recipient": addr,
            "total": total_count,
            "spam": spam_count,
            "phishing": phish_count,
            "malware": mal_count,
            "clean": clean_count,
            "owner_type": owner_type,
            "owner_username": owner_username,
        })

    return {
        "scope": scope,
        "category": category,
        "total_recipients": len(result_rows),
        "admin_emails": list(all_admin_emails),
        "user_emails": list(all_user_emails),
        "admins": [
            {"username": k, "email": v["email"], "mailboxes": v["mailboxes"], "total_users": v["total_users"]}
            for k, v in admin_email_map.items()
        ],
        "results": result_rows,
    }


@app.get("/api/superadmin/admin-emails/{admin_username}")
async def api_superadmin_admin_emails(
    request: Request,
    admin_username: str,
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access this endpoint")

    admin_user = db.query(User).filter(
        User.username == admin_username,
        User.role == "admin",
        User.is_active == True
    ).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin not found")

    org_id = admin_user.organization_id

    mboxes = db.query(AdminMailbox).filter(
        AdminMailbox.assigned_to == admin_username,
        AdminMailbox.is_active == True
    ).all()

    user_rows = db.query(User).filter(
        User.organization_id == org_id,
        User.role == "user",
        User.is_active == True
    ).all() if org_id else []

    emails_data = []

    admin_emails = set()
    if admin_user.email:
        admin_emails.add(admin_user.email.lower())
    for mb in mboxes:
        admin_emails.add(mb.email.lower())

    user_emails_set = set()
    for u in user_rows:
        if u.email:
            user_emails_set.add(u.email.lower())

    all_scope_emails = admin_emails | user_emails_set

    for email_addr in sorted(all_scope_emails):
        cat_base = db.query(QuarantineEmail).filter(
            QuarantineEmail.recipient_list.contains(email_addr, autoescape=True),
            QuarantineEmail.status != "trash",
        )
        total = cat_base.count() or 0
        spam = cat_base.filter(QuarantineEmail.category == "spam").count() or 0
        phishing = cat_base.filter(QuarantineEmail.category == "phishing").count() or 0
        malware = cat_base.filter(QuarantineEmail.category == "malware").count() or 0
        clean = cat_base.filter(QuarantineEmail.label == "CLEAN").count() or 0
        owner = "admin" if email_addr in admin_emails else "user"
        emails_data.append({
            "email": email_addr,
            "total": total,
            "spam": spam,
            "phishing": phishing,
            "malware": malware,
            "clean": clean,
            "owner": owner,
        })

    return {
        "admin_username": admin_username,
        "admin_email": admin_user.email,
        "organization_id": org_id,
        "emails": emails_data,
    }


@app.get("/api/superadmin/admin-emails/{admin_username}/details")
async def api_superadmin_admin_email_details(
    request: Request,
    admin_username: str,
    email: str = "",
    limit: int = 100,
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access this endpoint")

    admin_user = db.query(User).filter(
        User.username == admin_username,
        User.role == "admin",
        User.is_active == True
    ).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin not found")

    org_id = admin_user.organization_id

    mboxes = db.query(AdminMailbox).filter(
        AdminMailbox.assigned_to == admin_username,
        AdminMailbox.is_active == True
    ).all()

    scope_emails = set()
    if admin_user.email:
        scope_emails.add(admin_user.email.lower())
    for mb in mboxes:
        scope_emails.add(mb.email.lower())

    user_rows = db.query(User).filter(
        User.organization_id == org_id,
        User.role == "user",
        User.is_active == True
    ).all() if org_id else []
    for u in user_rows:
        if u.email:
            scope_emails.add(u.email.lower())

    base = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
    )
    if email:
        base = base.filter(QuarantineEmail.recipient_list.contains(email, autoescape=True))
    else:
        from sqlalchemy import or_
        filters = [QuarantineEmail.recipient_list.contains(e, autoescape=True) for e in scope_emails]
        base = base.filter(or_(*filters))

    records = base.order_by(QuarantineEmail.created_at.desc()).limit(limit).all()

    results = []
    for r in records:
        results.append({
            "id": r.id,
            "email_id": r.email_id,
            "received_at": r.received_at,
            "sender": r.sender,
            "subject": r.subject,
            "recipient_list": r.recipient_list,
            "label": r.label,
            "category": r.category,
            "fused_score": r.fused_score,
            "sa_score": r.sa_score,
            "ml_probability": r.ml_probability,
            "anomaly_score": r.anomaly_score,
            "spf_result": r.spf_result,
            "dkim_result": r.dkim_result,
            "dmarc_result": r.dmarc_result,
            "routing_reason": r.routing_reason,
            "created_at": str(r.created_at) if r.created_at else "",
        })

    return {
        "admin_username": admin_username,
        "email_filter": email,
        "total": len(results),
        "records": results,
    }


@app.get("/api/admin/superadmin-dashboard")
async def api_superadmin_dashboard(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access this endpoint")

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_mailboxes = db.query(func.count(AdminMailbox.id)).filter(AdminMailbox.is_active == True).scalar() or 0
    total_admins = db.query(func.count(User.id)).filter(User.role == "admin", User.is_active == True).scalar() or 0

    base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
    total_emails = base.count() or 0
    total_spam = base.filter(QuarantineEmail.category == "spam").count() or 0
    total_phishing = base.filter(QuarantineEmail.category == "phishing").count() or 0
    total_malware = base.filter(QuarantineEmail.category == "malware").count() or 0
    total_quarantined = base.filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.status != "released",
    ).count() or 0
    total_warn = base.filter(
        QuarantineEmail.label == "WARN",
        QuarantineEmail.status != "released",
    ).count() or 0
    total_clean = base.filter(QuarantineEmail.label == "CLEAN").count() or 0

    system_health = {"status": "healthy", "database": "connected", "websocket_connections": len(manager.active_connections)}

    recent_activities = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(20).all()
    recent_security = db.query(QuarantineEmail).filter(
        QuarantineEmail.label.in_(["QUARANTINE", "WARN"]),
        ~QuarantineEmail.status.in_(["trash", "released"]),
    ).order_by(QuarantineEmail.created_at.desc()).limit(10).all()

    admin_rows = db.query(User).filter(User.role == "admin", User.is_active == True).all()
    admins_data = []
    for adm in admin_rows:
        org_id = adm.organization_id
        org_name = ""
        if org_id:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            org_name = org.name if org else ""
        sub_users = db.query(User).filter(
            User.organization_id == org_id, User.role == "user", User.is_active == True
        ).all() if org_id else []
        users_data = []
        for u in sub_users:
            u_email = u.email or f"{u.username}@unknown.com"
            u_total = db.query(func.count(QuarantineEmail.id)).filter(
                QuarantineEmail.recipient_list.contains(u_email)
            ).scalar() or 0
            u_clean = db.query(func.count(QuarantineEmail.id)).filter(
                QuarantineEmail.recipient_list.contains(u_email),
                QuarantineEmail.label == "CLEAN"
            ).scalar() or 0
            u_spam = db.query(func.count(QuarantineEmail.id)).filter(
                QuarantineEmail.recipient_list.contains(u_email),
                QuarantineEmail.category == "spam"
            ).scalar() or 0
            u_phish = db.query(func.count(QuarantineEmail.id)).filter(
                QuarantineEmail.recipient_list.contains(u_email),
                QuarantineEmail.category == "phishing"
            ).scalar() or 0
            u_mal = db.query(func.count(QuarantineEmail.id)).filter(
                QuarantineEmail.recipient_list.contains(u_email),
                QuarantineEmail.category == "malware"
            ).scalar() or 0
            users_data.append({
                "username": u.username, "email": u_email,
                "total_emails": u_total, "clean": u_clean,
                "spam": u_spam, "phishing": u_phish, "malware": u_mal,
                "is_active": u.is_active,
            })
        admins_data.append({
            "username": adm.username, "email": adm.email,
            "organization_name": org_name, "organization_id": org_id,
            "users": users_data, "total_users": len(sub_users),
        })

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_admins": total_admins,
        "total_mailboxes": total_mailboxes,
        "total_emails_processed": total_emails,
        "total_clean": total_clean,
        "total_spam": total_spam,
        "total_phishing": total_phishing,
        "total_malware": total_malware,
        "total_quarantined": total_quarantined,
        "total_warn": total_warn,
        "system_health": system_health,
        "admins": admins_data,
        "recent_activities": [
            {"user": a.user, "action": a.action, "details": a.details, "ip_address": a.ip_address, "created_at": str(a.created_at)}
            for a in recent_activities
        ],
        "recent_security_detections": [
            {"email_id": e.email_id, "sender": e.sender, "subject": e.subject, "label": e.label, "category": e.category, "fused_score": e.fused_score, "received_at": str(e.received_at)}
            for e in recent_security
        ],
    }


# Catch-all Route to serve React SPA
dist_dir = Path(__file__).parent / "static" / "dist"

@app.get("/{file_path:path}")
async def serve_react_app(request: Request, file_path: str):
    # Skip standard API, WS, and static/ templates endpoints
    if (
        file_path.startswith("api/") or 
        file_path == "ws" or 
        file_path == "docs" or 
        file_path == "openapi.json" or
        file_path.startswith("static/")
    ):
        raise HTTPException(status_code=404, detail="Not Found")
    
    # Check if requested path is a file in Vite build outputs
    local_file = dist_dir / file_path
    if file_path and local_file.is_file():
        return FileResponse(local_file)
    
    # Return index.html for SPA frontend routing
    index_file = dist_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    
    return PlainTextResponse("React frontend is not built yet. Please build it first.")

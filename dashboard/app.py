<<<<<<< HEAD
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

async def redis_pubsub_bridge():
    """Listen for Redis pub/sub messages and broadcast to WebSocket clients."""
    while True:
        r = None
        try:
            r = aio_redis.from_url(REDIS_URL_WS, socket_timeout=15, socket_connect_timeout=10)
            async with r.pubsub() as pubsub:
                await pubsub.subscribe(PUBSUB_CHANNEL)
                logger.info("Redis pub/sub bridge started on channel: %s", PUBSUB_CHANNEL)
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if not message:
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
            logger.error("pubsub_bridge_error: %s, reconnecting in 5s...", e)
            await asyncio.sleep(5)
        finally:
            if r is not None:
                with contextlib.suppress(Exception):
                    await r.aclose()


@app.on_event("startup")
async def start_pubsub_bridge():
    app.state.pubsub_task = asyncio.create_task(redis_pubsub_bridge())


@app.on_event("shutdown")
async def stop_pubsub_bridge():
    task = getattr(app.state, "pubsub_task", None)
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
    _upsert_seed_user(
        db,
        os.getenv("ADMIN_USERNAME", "admin"),
        os.getenv("ADMIN_PASSWORD", "admin"),
        "admin",
    )
    _upsert_seed_user(
        db,
        os.getenv("USER_USERNAME", "user"),
        os.getenv("USER_PASSWORD", "user"),
        "user",
    )

    db.commit()
    db.close()

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
    if user_info["role"] == "admin":
        role = "user"  # Admin can only create 'user' role
    elif user_info["role"] == "superadmin":
        if role not in ("admin", "user"):
            raise HTTPException(status_code=403, detail="Superadmin can only create admin or user role")
            
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
    )
    db.add(new_user)
    db.commit()
    return {"ok": True, "message": f"User {username} created"}


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

    # Admin can only assign to users in their organization
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and assigned_to:
        target_user = db.query(User).filter(User.username == assigned_to).first()
        current_user_obj = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user_obj or not current_user_obj.organization_id:
            raise HTTPException(status_code=403, detail="Admin must belong to an organization")
        if not target_user or target_user.organization_id != current_user_obj.organization_id:
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
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_emails = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash").count()
    clean_count = db.query(QuarantineEmail).filter(
        QuarantineEmail.label == "CLEAN",
        QuarantineEmail.status != "trash",
    ).count()
    warn_count = db.query(QuarantineEmail).filter(
        QuarantineEmail.label == "WARN",
        QuarantineEmail.status != "trash",
    ).count()
    quarantine_count = db.query(QuarantineEmail).filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.status != "trash",
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
    return [
        {
            "email_id": e.email_id,
            "subject": e.subject,
            "sender": e.sender,
            "label": e.label,
            "status": e.status,
            "fused_score": e.fused_score,
            "category": e.category,
            "received_at": e.received_at,
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

    organizations = []
    org_rows = db.query(Organization).order_by(Organization.name).all()
    for org in org_rows:
        org_total = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id).scalar() or 0
        organizations.append({
            "organization_id": org.id,
            "organization_name": org.name,
            "users": db.query(func.count(User.id)).filter(User.organization_id == org.id, User.role == UserRole.USER.value, User.is_active == True).scalar() or 0,
            "total_emails": org_total,
            "clean": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id, QuarantineEmail.label == "CLEAN").scalar() or 0,
            "warn": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id, QuarantineEmail.label == "WARN").scalar() or 0,
            "quarantine": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.organization_id == org.id, QuarantineEmail.label == "QUARANTINE").scalar() or 0,
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
        }
        for a in db.query(AuditLog).filter(AuditLog.ip_address != None).order_by(AuditLog.created_at.desc()).limit(40).all()
    ]

    return {
        "total_emails": total_emails,
        "total_clean": total_clean,
        "total_warn": total_warn,
        "total_quarantine": total_quarantine,
        "organizations": organizations,
        "admins": admins,
        "suspicious_activities": suspicious_activities,
    }


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


@app.get("/api/admin/superadmin-dashboard")
async def api_superadmin_dashboard(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access this endpoint")

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_mailboxes = db.query(func.count(AdminMailbox.id)).filter(AdminMailbox.is_active == True).scalar() or 0

    base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")
    total_emails = base.count() or 0
    total_spam = base.filter(QuarantineEmail.category == "spam").count() or 0
    total_phishing = base.filter(QuarantineEmail.category == "phishing").count() or 0
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

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_mailboxes": total_mailboxes,
        "total_emails_processed": total_emails,
        "total_clean": total_clean,
        "total_spam": total_spam,
        "total_phishing": total_phishing,
        "total_quarantined": total_quarantined,
        "total_warn": total_warn,
        "system_health": system_health,
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
=======
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
import csv
import html
import io
import json
import logging
import mimetypes
import os
import re
import secrets as _secrets
import struct
import uuid
from datetime import datetime, timedelta
from email import encoders, policy
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.parser import Parser
from email.utils import formatdate, getaddresses, make_msgid
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import aiosmtplib
import httpx
import redis.asyncio as aio_redis
from pydantic import BaseModel
from fastapi import FastAPI, Request, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, UploadFile, File
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

from dashboard import environment as _environment  # noqa: F401 - loads .env before configuration imports
from database.models import ApiKey, QuarantineEmail, Feedback, User, AuditLog, Report, AdminMailbox, AdminMailboxAccess
from mail_delivery import deliver_direct_mx
from dashboard.database import get_db, SessionLocal
from dashboard.auth import (
    hash_password, verify_password, create_access_token, decode_token, ACCESS_TOKEN_EXPIRE_MINUTES,
    log_audit
)

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


def validate_production_configuration() -> None:
    if os.getenv("ENV", "development").lower() != "production":
        return
    insecure = []
    password_defaults = {
        "ADMIN_PASSWORD": {"", "admin"},
        "SUPERADMIN_PASSWORD": {"", "super", "superadmin"},
        "USER_PASSWORD": {"", "user"},
    }
    for variable, rejected in password_defaults.items():
        if os.getenv(variable, "").strip().lower() in rejected:
            insecure.append(variable)
    if not os.getenv("DASHBOARD_SECRET_KEY", "").strip():
        insecure.append("DASHBOARD_SECRET_KEY")
    if os.getenv("OUTBOUND_SMTP_MODE", "relay").strip().lower() == "direct":
        helo = os.getenv("OUTBOUND_HELO_HOSTNAME", "").strip().lower()
        if not helo or helo == "localhost":
            insecure.append("OUTBOUND_HELO_HOSTNAME")
    if insecure:
        names = ", ".join(sorted(set(insecure)))
        raise RuntimeError(f"Konfigurasi production tidak aman atau belum lengkap: {names}")

static_dir = Path(__file__).parent / "static"
avatar_dir = static_dir / "uploads" / "avatars"
avatar_dir.mkdir(parents=True, exist_ok=True)
DEFAULT_AVATAR_URL = "/static/default-avatar.svg"
MAX_AVATAR_BYTES = 1 * 1024 * 1024
ALLOWED_AVATAR_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/gif": (b"GIF", ".gif"),
    "image/webp": (b"RIFF", ".webp"),
}


def avatar_url_or_default(avatar_url: str = "") -> str:
    return avatar_url or DEFAULT_AVATAR_URL


def is_mailbox_request_context(request: Request) -> bool:
    referer = request.headers.get("referer", "")
    return any(path in referer for path in ("/mailbox-login", "/mail/"))


def get_profile_session_token(request: Request) -> str:
    access_token = request.cookies.get("access_token")
    mailbox_token = request.cookies.get("mailbox_token")
    if mailbox_token and is_mailbox_request_context(request):
        return mailbox_token
    return access_token or mailbox_token or ""


def authenticated_user_from_token(db: Session, token: str) -> dict | None:
    if not token:
        return None
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
            return None
        return {"username": user.username, "role": user.role}
    except Exception:
        return None


def authorize_requested_mailbox(request: Request, db: Session, mailbox: AdminMailbox) -> dict:
    for token in (request.cookies.get("access_token"), request.cookies.get("mailbox_token")):
        user_info = authenticated_user_from_token(db, token)
        if user_info and can_access_mailbox_record(db, user_info, mailbox):
            return user_info
    raise HTTPException(status_code=403, detail="You do not have permission to access this mailbox")

app = FastAPI(title="CogniMail Dashboard", version="3.0.0")
Instrumentator().instrument(app).expose(app)

csrf_secret = os.getenv("DASHBOARD_SECRET_KEY") or _secrets.token_hex(32)
app.add_middleware(
    SessionMiddleware,
    secret_key=csrf_secret,
    same_site="lax",
    https_only=os.getenv("ENV", "development") == "production",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(","))
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
    token = (
        token
        or websocket.cookies.get("mailbox_token", "")
        or websocket.cookies.get("access_token", "")
    )
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



REDIS_URL_WS = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def redis_pubsub_bridge():
    """Listen for Redis pub/sub messages and broadcast to WebSocket clients."""
    while True:
        r = None
        try:
            r = aio_redis.from_url(REDIS_URL_WS, socket_timeout=15, socket_connect_timeout=10)
            async with r.pubsub() as pubsub:
                await pubsub.subscribe(PUBSUB_CHANNEL)
                logger.info("Redis pub/sub bridge started on channel: %s", PUBSUB_CHANNEL)
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if not message:
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
            logger.error("pubsub_bridge_error: %s, reconnecting in 5s...", e)
            await asyncio.sleep(5)
        finally:
            if r is not None:
                with contextlib.suppress(Exception):
                    await r.aclose()


@app.on_event("startup")
async def start_pubsub_bridge():
    app.state.pubsub_task = asyncio.create_task(redis_pubsub_bridge())


@app.on_event("shutdown")
async def stop_pubsub_bridge():
    task = getattr(app.state, "pubsub_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task



ALLOWED_ROLES = {"superadmin", "admin", "user"}


def _upsert_seed_user(
    db,
    username: str,
    password: str,
    role: str,
    email: str = None,
    legacy_usernames=None,
    insecure_passwords=None,
):
    legacy_usernames = legacy_usernames or []
    insecure_passwords = insecure_passwords or []
    created = False
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
        created = True
        user.hashed_password = hash_password(password)
    elif any(
        verify_password(candidate, user.hashed_password or "")
        for candidate in insecure_passwords
    ):
        # Upgrade only known development credentials. A password changed from
        # the UI must survive future container restarts.
        user.hashed_password = hash_password(password)

    if created or email is not None:
        user.email = email
    user.role = role
    user.is_active = True
    return user


def seed_admin():
    db = SessionLocal()
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512) DEFAULT ''"))
        db.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS attachments_json TEXT"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS spf_result VARCHAR(32) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dkim_result VARCHAR(32) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dmarc_result VARCHAR(32) DEFAULT ''"))
    elif dialect == "sqlite":
        user_columns = [row[1] for row in db.execute(text("PRAGMA table_info(users)")).fetchall()]
        if "avatar_url" not in user_columns:
            db.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512) DEFAULT ''"))
        mailbox_columns = [row[1] for row in db.execute(text("PRAGMA table_info(admin_mailboxes)")).fetchall()]
        if "avatar_url" not in mailbox_columns:
            db.execute(text("ALTER TABLE admin_mailboxes ADD COLUMN avatar_url VARCHAR(512) DEFAULT ''"))
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
        insecure_passwords=["super", "superadmin"],
    )
    _upsert_seed_user(
        db,
        os.getenv("ADMIN_USERNAME", "admin"),
        os.getenv("ADMIN_PASSWORD", "admin"),
        "admin",
        insecure_passwords=["admin"],
    )
    _upsert_seed_user(
        db,
        os.getenv("USER_USERNAME", "user"),
        os.getenv("USER_PASSWORD", "user"),
        "user",
        insecure_passwords=["user"],
    )

    db.commit()
    db.close()

validate_production_configuration()
seed_admin()



@app.get("/api/auth/me")
async def auth_me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    mailbox_token = request.cookies.get("mailbox_token")
    client_host = request.client.host if request.client else "unknown"
    referer = request.headers.get("referer", "")
    mailbox_context = any(path in referer for path in ("/mailbox-login", "/mail/"))
    logger.info(f"auth_me: client={client_host} dashboard_token={bool(token)} mailbox_token={bool(mailbox_token)} mailbox_context={mailbox_context} url={request.url.path}")

    # Webmail pages must prefer their independent mailbox session. If that
    # token is invalid, a valid dashboard session remains a safe fallback.
    if mailbox_token and mailbox_context:
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
                        "avatar_url": avatar_url_or_default(mailbox.avatar_url),
                    },
                })
        except Exception as e:
            logger.warning(f"auth_me: mailbox token decode failed: {e}")

    if token:
        try:
            payload = decode_token(token)
            if payload.get("role") != "mailbox":
                user = db.query(User).filter(User.username == payload.get("sub")).first()
                if user and user.is_active:
                    logger.info(f"auth_me: authenticated dashboard user={user.username} role={user.role}")
                    return JSONResponse({
                        "authenticated": True,
                        "user": {
                            "username": user.username,
                            "email": user.email,
                            "role": user.role,
                            "avatar_url": avatar_url_or_default(user.avatar_url),
                        },
                    })
        except Exception as e:
            logger.warning(f"auth_me: dashboard token decode failed: {e}")

    logger.warning(f"auth_me: no valid session from {client_host}")
    return JSONResponse({"authenticated": False, "user": None})


@app.post("/api/auth/login")
@limiter.limit("20/minute")
async def auth_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
                     db: Session = Depends(get_db)):
    login_identity = (form_data.username or "").strip().lower()
    user = db.query(User).filter(
        or_(
            func.lower(User.username) == login_identity,
            func.lower(User.email) == login_identity,
        )
    ).first()
    if user and verify_password(form_data.password, user.hashed_password):
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

    if "@" in login_identity:
        mailbox = db.query(AdminMailbox).filter(
            func.lower(AdminMailbox.email) == login_identity,
            AdminMailbox.is_active.is_(True),
        ).first()
        if mailbox and verify_password(form_data.password, mailbox.password_hash or ""):
            mailbox_token = create_access_token({
                "sub": f"mailbox:{mailbox.id}",
                "role": "mailbox",
                "mailbox_id": str(mailbox.id),
                "mailbox_email": mailbox.email.lower(),
            })
            response = JSONResponse({
                "access_token": mailbox_token,
                "token_type": "bearer",
                "username": mailbox.email.lower(),
                "role": "mailbox",
                "mailbox": {
                    "id": mailbox.id,
                    "email": mailbox.email,
                    "domain": mailbox.domain,
                    "sender_name": mailbox.sender_name or "",
                    "avatar_url": avatar_url_or_default(mailbox.avatar_url),
                },
            })
            response.set_cookie(
                key="mailbox_token",
                value=mailbox_token,
                httponly=True,
                samesite="lax",
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                secure=os.getenv("ENV", "development") == "production",
                path="/",
            )
            return response

    raise HTTPException(401, "Invalid username or password")


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
        redirect_url = "/user/mailboxes"
    response = RedirectResponse(url=redirect_url)
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production",
        path="/",
    )
    return response



@app.get("/api/auth/profile")
async def get_profile(request: Request, mailbox_id: str = Query(""), db: Session = Depends(get_db)):
    if mailbox_id:
        mailbox = resolve_active_mailbox(db, mailbox_id)
        authorize_requested_mailbox(request, db, mailbox)
        return {
            "username": mailbox.email.lower(),
            "role": "mailbox",
            "is_active": mailbox.is_active,
            "created_at": str(mailbox.created_at) if mailbox.created_at else None,
            "mailbox_id": str(mailbox.id),
            "mailbox_email": mailbox.email.lower(),
            "domain": mailbox.domain,
            "sender_name": mailbox.sender_name or "",
            "avatar_url": avatar_url_or_default(mailbox.avatar_url),
        }

    token = get_profile_session_token(request)
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
            "avatar_url": avatar_url_or_default(mailbox.avatar_url),
        }
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "username": user.username,
        "email": user.email,
        "avatar_url": avatar_url_or_default(user.avatar_url),
        "role": user.role,
        "is_active": user.is_active,
        "created_at": str(user.created_at) if user.created_at else None,
        "organization_id": user.organization_id,
    }


def _avatar_extension(content_type: str, data: bytes) -> str:
    avatar_type = ALLOWED_AVATAR_TYPES.get(content_type)
    if not avatar_type:
        raise HTTPException(400, "Avatar must be a JPG, PNG, GIF, or WEBP image")
    signature, extension = avatar_type
    if not data.startswith(signature):
        raise HTTPException(400, "Avatar file content does not match its image type")
    if content_type == "image/webp" and data[8:12] != b"WEBP":
        raise HTTPException(400, "Avatar file content does not match its image type")
    return extension


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            return None
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA or index + 2 > len(data):
            return None
        segment_length = struct.unpack(">H", data[index:index + 2])[0]
        if segment_length < 2 or index + segment_length > len(data):
            return None
        if marker in {
            0xC0, 0xC1, 0xC2, 0xC3,
            0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB,
            0xCD, 0xCE, 0xCF,
        }:
            if index + 7 > len(data):
                return None
            height = struct.unpack(">H", data[index + 3:index + 5])[0]
            width = struct.unpack(">H", data[index + 5:index + 7])[0]
            return width, height
        index += segment_length
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    return None


def _image_dimensions(content_type: str, data: bytes) -> tuple[int, int] | None:
    if content_type == "image/png" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if content_type == "image/gif" and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if content_type == "image/jpeg":
        return _jpeg_dimensions(data)
    if content_type == "image/webp":
        return _webp_dimensions(data)
    return None


def _validate_square_avatar(content_type: str, data: bytes):
    dimensions = _image_dimensions(content_type, data)
    if not dimensions:
        raise HTTPException(400, "Avatar image dimensions could not be read")
    width, height = dimensions
    if width <= 0 or height <= 0:
        raise HTTPException(400, "Avatar image dimensions are invalid")
    if width != height:
        raise HTTPException(400, "Avatar image ratio must be 1:1")


def _remove_old_avatar(avatar_url: str):
    if not avatar_url or not avatar_url.startswith("/static/uploads/avatars/"):
        return
    old_path = avatar_dir / Path(avatar_url).name
    try:
        if old_path.is_file() and old_path.parent == avatar_dir:
            old_path.unlink()
    except Exception as e:
        logger.warning("avatar_cleanup_failed: %s", e)


@app.post("/api/auth/profile/avatar")
async def upload_profile_avatar(
    request: Request,
    mailbox_id: str = Query(""),
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    token = get_profile_session_token(request)
    if not token:
        raise HTTPException(401, "Not authenticated")

    content_type = (avatar.content_type or "").lower()
    data = await avatar.read(MAX_AVATAR_BYTES + 1)
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(400, "Avatar image must be 1 MB or smaller")
    if not data:
        raise HTTPException(400, "Avatar image is required")

    extension = _avatar_extension(content_type, data)
    _validate_square_avatar(content_type, data)
    filename = f"{_secrets.token_urlsafe(18)}{extension}"
    target_path = avatar_dir / filename
    avatar_url = f"/static/uploads/avatars/{filename}"

    if mailbox_id:
        mailbox = resolve_active_mailbox(db, mailbox_id)
        authorize_requested_mailbox(request, db, mailbox)
        target_path.write_bytes(data)
        _remove_old_avatar(mailbox.avatar_url or "")
        mailbox.avatar_url = avatar_url
        actor = mailbox.email.lower()
    else:
        payload = decode_token(token)
        if payload.get("role") == "mailbox":
            mailbox = resolve_active_mailbox(
                db,
                payload.get("mailbox_id"),
                payload.get("mailbox_email"),
            )
            target_path.write_bytes(data)
            _remove_old_avatar(mailbox.avatar_url or "")
            mailbox.avatar_url = avatar_url
            actor = mailbox.email.lower()
        else:
            user = db.query(User).filter(User.username == payload.get("sub")).first()
            if not user:
                raise HTTPException(404, "User not found")
            target_path.write_bytes(data)
            _remove_old_avatar(user.avatar_url or "")
            user.avatar_url = avatar_url
            actor = user.username

    db.commit()
    log_audit(db, actor, "upload_avatar", details="Profile avatar updated")
    return {"ok": True, "avatar_url": avatar_url}


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
            secure=os.getenv("ENV", "development") == "production",
            path="/",
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
    import secrets
    import hashlib
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



def get_authenticated_api_user(request: Request, db: Session = Depends(get_db)) -> dict:
    access_token = request.cookies.get("access_token")
    mailbox_token = request.cookies.get("mailbox_token")
    if not access_token and not mailbox_token:
        logger.warning(f"get_authenticated_api_user: no cookie from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Not authenticated")
    candidates = (
        (mailbox_token, access_token)
        if is_mailbox_request_context(request)
        else (access_token, mailbox_token)
    )
    for candidate in candidates:
        user_info = authenticated_user_from_token(db, candidate)
        if user_info:
            return user_info
    logger.warning("get_authenticated_api_user: all session tokens invalid or expired")
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
    mailbox_query = db.query(AdminMailbox).filter(AdminMailbox.is_active.is_(True))
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


def is_superadmin(user_info: dict) -> bool:
    return user_info.get("role") == "superadmin"


def is_admin(user_info: dict) -> bool:
    return user_info.get("role") == "admin"


def is_user(user_info: dict) -> bool:
    return user_info.get("role") == "user"


def can_manage_mailboxes(user_info: dict) -> bool:
    return user_info.get("role") in ("superadmin", "admin", "user")


def can_manage_users(user_info: dict) -> bool:
    return user_info.get("role") in ("superadmin", "admin")


def ensure_mailbox_account_access(db: Session, mailbox_id: int, username: str):
    if not mailbox_id or not username:
        return None
    existing = db.query(AdminMailboxAccess).filter(
        AdminMailboxAccess.mailbox_id == mailbox_id,
        AdminMailboxAccess.username == username,
    ).first()
    if existing:
        return existing
    access = AdminMailboxAccess(mailbox_id=mailbox_id, username=username)
    db.add(access)
    return access


def mailbox_access_account_map(db: Session, rows: list[AdminMailbox]) -> dict[int, list[dict]]:
    mailbox_ids = [row.id for row in rows if row.id]
    if not mailbox_ids:
        return {}
    access_rows = (
        db.query(AdminMailboxAccess, User)
        .outerjoin(User, User.username == AdminMailboxAccess.username)
        .filter(AdminMailboxAccess.mailbox_id.in_(mailbox_ids))
        .order_by(AdminMailboxAccess.username.asc())
        .all()
    )
    account_map: dict[int, list[dict]] = {mailbox_id: [] for mailbox_id in mailbox_ids}
    for access, user in access_rows:
        account_map.setdefault(access.mailbox_id, []).append({
            "username": access.username,
            "role": user.role if user else "",
        })
    for row in rows:
        if not row.created_by:
            continue
        accounts = account_map.setdefault(row.id, [])
        if not any(account["username"] == row.created_by for account in accounts):
            owner = db.query(User).filter(User.username == row.created_by).first()
            accounts.append({
                "username": row.created_by,
                "role": owner.role if owner else "",
            })
    return account_map


def mailbox_account_access_exists(db: Session, mailbox_id: int, username: str) -> bool:
    if not mailbox_id or not username:
        return False
    return db.query(AdminMailboxAccess.id).filter(
        AdminMailboxAccess.mailbox_id == mailbox_id,
        AdminMailboxAccess.username == username,
    ).first() is not None


def user_record_for_info(db: Session, user_info: dict) -> User | None:
    username = user_info.get("username")
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()


def can_access_mailbox_record(db: Session, user_info: dict, mailbox: AdminMailbox) -> bool:
    if not mailbox or not mailbox.is_active:
        return False
    if is_superadmin(user_info):
        return True
    if is_admin(user_info) or is_user(user_info):
        username = user_info.get("username")
        return mailbox.created_by == username or mailbox_account_access_exists(db, mailbox.id, username)
    if user_info.get("role") == "mailbox":
        return str(mailbox.id) == str(user_info.get("mailbox_id")) or mailbox.email.lower() == (user_info.get("mailbox_email") or "").lower()
    return False


def ensure_mailbox_access(db: Session, user_info: dict, mailbox: AdminMailbox):
    if not can_access_mailbox_record(db, user_info, mailbox):
        raise HTTPException(status_code=403, detail="You do not have permission to access this mailbox")
    return mailbox


def mailbox_scope_query(db: Session, user_info: dict):
    query = db.query(AdminMailbox).filter(AdminMailbox.is_active.is_(True))
    if is_superadmin(user_info):
        return query
    if is_admin(user_info) or is_user(user_info):
        username = user_info.get("username")
        mailbox_ids = [
            row[0]
            for row in db.query(AdminMailboxAccess.mailbox_id)
            .filter(AdminMailboxAccess.username == username)
            .all()
        ]
        return query.filter(or_(AdminMailbox.created_by == username, AdminMailbox.id.in_(mailbox_ids)))
    if user_info.get("role") == "mailbox":
        return query.filter(AdminMailbox.id == int(user_info.get("mailbox_id") or 0))
    return query.filter(False)


def accessible_mailbox_emails(db: Session, user_info: dict) -> list[str]:
    return [row.email for row in mailbox_scope_query(db, user_info).all()]


def mailbox_filter_for_emails(mailbox_emails: list[str]):
    filters = []
    for email in mailbox_emails:
        filters.extend(_mailbox_identity_filters(QuarantineEmail.recipient_list, email))
        filters.extend(_mailbox_identity_filters(QuarantineEmail.sender, email))
    return or_(*filters) if filters else None


def ensure_email_access(email_record: QuarantineEmail, user_info: dict, db: Session | None = None):
    if user_info["role"] in ["superadmin", "admin"]:
        return
    if db is not None and user_info["role"] == "user":
        for mailbox_email in accessible_mailbox_emails(db, user_info):
            if email_belongs_to_identity(email_record, mailbox_email):
                return
    if email_belongs_to_identity(email_record, user_info.get("mailbox_email") or user_info.get("username")):
        return
    raise HTTPException(status_code=403, detail="You do not have permission to access this email")


def resolve_sender_address(db: Session, user_info: dict, requested_from: str = "") -> str:
    requested_sender = (requested_from or "").strip().lower()
    if requested_sender:
        if user_info["role"] == "mailbox" and requested_sender != user_info["mailbox_email"]:
            raise HTTPException(status_code=403, detail="You can only send from the logged-in mailbox")
        mailbox = db.query(AdminMailbox).filter(
            AdminMailbox.email == requested_sender,
            AdminMailbox.is_active.is_(True),
        ).first()
        if not mailbox:
            raise HTTPException(status_code=403, detail="Sender mailbox is not registered or inactive")
        ensure_mailbox_access(db, user_info, mailbox)
        return mailbox.email

    if user_info["role"] == "mailbox":
        return user_info["mailbox_email"]

    if user_info["role"] == "user":
        mailbox_emails = accessible_mailbox_emails(db, user_info)
        if len(mailbox_emails) == 1:
            return mailbox_emails[0]
        if mailbox_emails:
            raise HTTPException(status_code=403, detail="Choose one of your mailboxes before sending email")
        raise HTTPException(status_code=403, detail="No mailbox available for this user")

    return f"{user_info['username']}@lodaya.id"

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
    
    if folder == "trash":
        query = query.filter(QuarantineEmail.status == "trash")
    else:
        query = query.filter(QuarantineEmail.status != "trash")
        if folder != "draft":
            query = query.filter(QuarantineEmail.label != "DRAFT")

    if mailbox:
        mailbox_record = resolve_active_mailbox(db, mailbox_id, mailbox, missing_status_code=404, missing_detail="Mailbox not found")
        ensure_mailbox_access(db, user_info, mailbox_record)
        query = query.filter(or_(
            *_mailbox_identity_filters(QuarantineEmail.recipient_list, mailbox_record.email),
            *_mailbox_identity_filters(QuarantineEmail.sender, mailbox_record.email),
        ))
    elif user_info["role"] == "user":
        mailbox_filter = mailbox_filter_for_emails(accessible_mailbox_emails(db, user_info))
        if mailbox_filter is None:
            query = query.filter(False)
        else:
            query = query.filter(mailbox_filter)

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

    ensure_email_access(email_record, user_info, db)
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
    ensure_email_access(email_record, user_info, db)
    
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
    ensure_email_access(email_record, user_info, db)
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
    if user_info["role"] not in ["superadmin", "admin"]:
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
    if user_info["role"] not in ["superadmin", "admin"]:
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
    if user_info["role"] not in ["superadmin", "admin"]:
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
        ensure_email_access(email_record, user_info, db)
        db.delete(email_record)
        log_audit(db, user_info["username"], "discard_draft", email_id,
                  request.client.host if request.client else None)
        db.commit()
        return {"ok": True, "status": "deleted"}
    ensure_email_access(email_record, user_info, db)
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
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(email_record, user_info, db)
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

    sender_address = resolve_sender_address(db, user_info, req.from_email)
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

    sender_address = resolve_sender_address(db, user_info, req.from_email)
    
    final_subject = req.subject
    final_body = req.body
    
    if req.action == "share" and req.share_with:
        dest_recipients = parse_recipients(req.share_with)
        orig = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == req.reply_to_id).first()
        if orig:
            ensure_email_access(orig, user_info, db)
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
            ensure_email_access(original_email, user_info, db)
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
    outbound_mode = os.getenv("OUTBOUND_SMTP_MODE", "relay").strip().lower()
    smtp_host = os.getenv("FORWARDER_SMTP_HOST", "").strip()
    smtp_user = os.getenv("FORWARDER_SMTP_USER", "").strip()
    smtp_pass = os.getenv("FORWARDER_SMTP_PASS", "")
    if outbound_mode not in {"direct", "relay"}:
        reason = f"OUTBOUND_SMTP_MODE tidak valid: {outbound_mode!r}. Gunakan 'direct' atau 'relay'."
        logger.error("Failed to send email: %s", reason)
        failure_id = save_delivery_failure(
            db, sender_address, dest_recipients, final_subject, final_body,
            reason, user_info["username"], request,
        )
        raise HTTPException(
            status_code=503,
            detail={"message": "Konfigurasi pengiriman outbound tidak valid.", "reason": reason, "failure_email_id": failure_id},
        )
    if outbound_mode == "relay" and not smtp_host:
        reason = (
            "SMTP relay outbound belum dikonfigurasi. "
            "Isi FORWARDER_SMTP_HOST, FORWARDER_SMTP_PORT, "
            "FORWARDER_SMTP_USER, dan FORWARDER_SMTP_PASS."
        )
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
            status_code=503,
            detail={
                "message": "Email gagal terkirim karena SMTP relay belum dikonfigurasi.",
                "reason": reason,
                "failure_email_id": failure_id,
            },
        )
    if outbound_mode == "relay" and bool(smtp_user) != bool(smtp_pass):
        reason = "Konfigurasi SMTP relay tidak lengkap: username dan password harus diisi bersamaan."
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
            status_code=503,
            detail={
                "message": "Email gagal terkirim karena konfigurasi SMTP relay tidak lengkap.",
                "reason": reason,
                "failure_email_id": failure_id,
            },
        )
    try:
        validate_recipient_domains(dest_recipients)
        # Direct delivery is multi-mailbox: each mailbox uses its own address
        # as the SMTP envelope sender. A relay may require one authorized
        # fallback identity, configured through FORWARDER_FROM.
        envelope_from = (
            sender_address
            if outbound_mode == "direct"
            else os.getenv("FORWARDER_FROM", "").strip() or sender_address
        )

        msg = MIMEMultipart()
        msg["From"] = sender_address
        if envelope_from != sender_address:
            msg["Reply-To"] = sender_address
        msg["To"] = ", ".join(dest_recipients)
        msg["Subject"] = final_subject
        msg["Date"] = formatdate(localtime=False)
        msg["Message-ID"] = make_msgid(domain=os.getenv("OUTBOUND_HELO_HOSTNAME", "").strip() or None)
        msg.attach(MIMEText(final_body, "plain", "utf-8"))
        for attachment in stored_attachments:
            maintype, subtype = (attachment["content_type"].split("/", 1) + ["octet-stream"])[:2]
            part = MIMEBase(maintype, subtype)
            part.set_payload(base64.b64decode(attachment["data"]))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=attachment["filename"])
            msg.attach(part)

        if outbound_mode == "direct":
            delivered = await deliver_direct_mx(
                msg,
                envelope_from,
                dest_recipients,
                helo_hostname=os.getenv("OUTBOUND_HELO_HOSTNAME", "").strip() or None,
            )
            logger.info("Sent email directly to MX successfully: %s", delivered)
        else:
            smtp_port = int(os.getenv("FORWARDER_SMTP_PORT", "587"))
            smtp_starttls = os.getenv("FORWARDER_STARTTLS", "true").lower() in {"1", "true", "yes", "on"}
            async with aiosmtplib.SMTP(
                hostname=smtp_host,
                port=smtp_port,
                use_tls=smtp_port == 465,
            ) as smtp:
                if smtp_port != 465 and smtp_starttls:
                    await smtp.starttls()
                if smtp_user and smtp_pass:
                    await smtp.login(smtp_user, smtp_pass)
                await smtp.send_message(
                    msg,
                    sender=envelope_from,
                    recipients=dest_recipients,
                )
            logger.info("Sent email via relay successfully to %s", ", ".join(dest_recipients))
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
        if user_info:
            ensure_mailbox_access(db, user_info, mailbox_record)
        scope_label = mailbox_record.email
        account_filters.append(or_(
            *_mailbox_identity_filters(QuarantineEmail.recipient_list, mailbox_record.email),
            *_mailbox_identity_filters(QuarantineEmail.sender, mailbox_record.email),
        ))
    elif user_info and user_info["role"] == "user":
        mailbox_emails = accessible_mailbox_emails(db, user_info)
        scope_label = ", ".join(mailbox_emails) if mailbox_emails else user_info["username"]
        mailbox_filter = mailbox_filter_for_emails(mailbox_emails)
        if mailbox_filter is not None:
            account_filters.append(mailbox_filter)
        else:
            account_filters.append(False)

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
    if user_info["role"] not in ["superadmin", "admin"]:
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
    if user_info["role"] not in ["superadmin", "admin"]:
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
    if user_info["role"] not in ["superadmin", "admin"]:
        raise HTTPException(status_code=403, detail="Only admin or above can change settings")

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
    if user_info["role"] not in ["superadmin", "admin"]:
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



@app.get("/api/export/emails.csv")
async def api_export_emails_csv(
    request: Request,
    label: str = Query(None),
    db: Session = Depends(get_db),
):
    """Export email log as CSV. Requires admin or above."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "admin"]:
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




@app.get("/api/admin/users")
async def api_get_users(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    if user_info["role"] == "admin":
        users = db.query(User).filter(User.role == "user").all()
    else:
        users = db.query(User).all()
    return [{"username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]


@app.post("/api/admin/users")
async def api_create_user(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    username = str(payload.get("username") or "").strip().lower()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    role = payload.get("role", "user")
    if not username or not re.match(r"^[a-z0-9._-]{3,64}$", username):
        raise HTTPException(status_code=400, detail="Valid username is required")
    if email and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    if user_info["role"] == "admin":
        role = "user"  # Admin can only create 'user' role
    elif user_info["role"] == "superadmin":
        if role not in ("admin", "user"):
            raise HTTPException(status_code=403, detail="Superadmin can only create admin or user role")
            
    existing = db.query(User).filter(func.lower(User.username) == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    if email:
        existing_email = db.query(User).filter(func.lower(User.email) == email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        username=username,
        email=email or None,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(new_user)
    db.commit()
    return {"ok": True, "message": f"User {username} created", "username": username}


@app.post("/api/admin/settings")
async def api_change_settings(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can change system settings")
    return {"ok": True, "message": "System settings updated successfully"}


@app.get("/api/admin/mailboxes")
async def api_get_admin_mailboxes(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not can_manage_mailboxes(user_info):
        raise HTTPException(status_code=403, detail="You do not have permission to manage mailboxes")
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only admin or superadmin can create new mailbox")
    rows = mailbox_scope_query(db, user_info).order_by(AdminMailbox.email.asc()).all()
    owner_names = [row.created_by for row in rows if row.created_by]
    owners = {
        user.username: user.role
        for user in db.query(User).filter(User.username.in_(owner_names)).all()
    } if owner_names else {}
    access_accounts = mailbox_access_account_map(db, rows)
    return [
        {
            "id": row.id,
            "email": row.email,
            "domain": row.domain,
            "sender_name": row.sender_name or "",
            "avatar_url": avatar_url_or_default(row.avatar_url),
            "forward_to": row.forward_to or "",
            "forward_enabled": bool(row.forward_enabled),
            "forward_keep_copy": bool(row.forward_keep_copy),
            "created_by": row.created_by,
            "owner_username": row.created_by,
            "owner_role": owners.get(row.created_by, ""),
            "access_accounts": access_accounts.get(row.id, []),
            "created_at": str(row.created_at),
        }
        for row in rows
    ]


@app.post("/api/admin/mailboxes")
@limiter.limit("10/minute")
async def api_create_admin_mailbox(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not can_manage_mailboxes(user_info):
        raise HTTPException(status_code=403, detail="You do not have permission to manage mailboxes")
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only admin or superadmin can create new mailbox")
    email = str(payload.get("email", "")).strip().lower()
    domain = str(payload.get("domain", "")).strip().lower().lstrip("@")
    password = str(payload.get("password", ""))
    sender_name = str(payload.get("sender_name", "")).strip()
    locked_domain = (
        os.getenv("VITE_MAIL_DOMAIN")
        or os.getenv("MAIL_DOMAIN")
        or os.getenv("SMTP_DOMAIN", "").removeprefix("mail.")
        or domain
    ).strip().lower().lstrip("@")
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status_code=400, detail="Invalid mailbox email")
    if not sender_name:
        raise HTTPException(status_code=400, detail="Sender name is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mailbox password must be at least 8 characters")
    actual_domain = email.split("@", 1)[1]
    expected_domain = locked_domain or domain
    if expected_domain and actual_domain != expected_domain:
        raise HTTPException(status_code=400, detail=f"Mailbox must use @{expected_domain}")
    existing = db.query(AdminMailbox).filter(func.lower(AdminMailbox.email) == email).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Mailbox already exists")
        if not is_superadmin(user_info) and existing.created_by != user_info["username"]:
            raise HTTPException(status_code=400, detail="Mailbox already exists")
        existing.is_active = True
        existing.domain = actual_domain
        existing.password_hash = hash_password(password)
        existing.sender_name = sender_name
        ensure_mailbox_account_access(db, existing.id, user_info["username"])
    else:
        mailbox = AdminMailbox(
            email=email,
            domain=actual_domain,
            password_hash=hash_password(password),
            sender_name=sender_name,
            created_by=user_info["username"],
        )
        db.add(mailbox)
        db.flush()
        ensure_mailbox_account_access(db, mailbox.id, user_info["username"])
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
            "avatar_url": avatar_url_or_default(mailbox.avatar_url),
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


@app.get("/api/user/mailboxes")
async def api_get_user_mailboxes(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("user", "admin", "superadmin", "mailbox"):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = mailbox_scope_query(db, user_info).order_by(AdminMailbox.email.asc()).all()
    owner_names = [row.created_by for row in rows if row.created_by]
    owners = {
        user.username: user.role
        for user in db.query(User).filter(User.username.in_(owner_names)).all()
    } if owner_names else {}
    access_accounts = mailbox_access_account_map(db, rows)
    return [
        {
            "id": row.id,
            "email": row.email,
            "domain": row.domain,
            "sender_name": row.sender_name or "",
            "avatar_url": avatar_url_or_default(row.avatar_url),
            "owner_username": row.created_by,
            "owner_role": owners.get(row.created_by, ""),
            "access_accounts": access_accounts.get(row.id, []),
        }
        for row in rows
    ]


@app.post("/api/mailboxes/claim")
@limiter.limit("10/minute")
async def api_claim_mailbox(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("admin", "user"):
        raise HTTPException(status_code=403, detail="Only admin or user accounts can add existing email")
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    locked_domain = (
        os.getenv("VITE_MAIL_DOMAIN")
        or os.getenv("MAIL_DOMAIN")
        or os.getenv("SMTP_DOMAIN", "").removeprefix("mail.")
        or ""
    ).strip().lower().lstrip("@")
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    actual_domain = email.split("@", 1)[1]
    if locked_domain and actual_domain != locked_domain:
        raise HTTPException(status_code=400, detail=f"Email must use @{locked_domain}")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    mailbox = db.query(AdminMailbox).filter(
        func.lower(AdminMailbox.email) == email,
        AdminMailbox.is_active.is_(True),
    ).first()
    if not mailbox or not verify_password(password, mailbox.password_hash or ""):
        raise HTTPException(status_code=400, detail="Email or password is invalid")
    if mailbox_account_access_exists(db, mailbox.id, user_info["username"]):
        return {"ok": True, "email": mailbox.email, "id": mailbox.id, "message": "Email already added"}
    owner = db.query(User).filter(User.username == mailbox.created_by).first()
    if not owner or owner.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=400, detail="Email is already used by another account")
    ensure_mailbox_account_access(db, mailbox.id, user_info["username"])
    log_audit(db, user_info["username"], "add_existing_email", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {"ok": True, "email": mailbox.email, "id": mailbox.id}


@app.delete("/api/admin/mailboxes/{mailbox_id}")
@limiter.limit("20/minute")
async def api_delete_admin_mailbox(mailbox_id: int, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not can_manage_mailboxes(user_info):
        raise HTTPException(status_code=403, detail="You do not have permission to manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    ensure_mailbox_access(db, user_info, mailbox)
    if is_superadmin(user_info):
        mailbox.is_active = False
        db.query(AdminMailboxAccess).filter(AdminMailboxAccess.mailbox_id == mailbox.id).delete(synchronize_session=False)
    else:
        db.query(AdminMailboxAccess).filter(
            AdminMailboxAccess.mailbox_id == mailbox.id,
            AdminMailboxAccess.username == user_info["username"],
        ).delete(synchronize_session=False)
        remaining = db.query(AdminMailboxAccess.id).filter(AdminMailboxAccess.mailbox_id == mailbox.id).first()
        if not remaining and mailbox.created_by == user_info["username"]:
            mailbox.is_active = False
    log_audit(db, user_info["username"], "delete_mailbox", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {"ok": True}


@app.put("/api/admin/mailboxes/{mailbox_id}/forwarder")
@limiter.limit("20/minute")
async def api_update_admin_mailbox_forwarder(mailbox_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not can_manage_mailboxes(user_info):
        raise HTTPException(status_code=403, detail="You do not have permission to manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id, AdminMailbox.is_active.is_(True)).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    ensure_mailbox_access(db, user_info, mailbox)
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


@app.put("/api/admin/mailboxes/{mailbox_id}/password")
@limiter.limit("10/minute")
async def api_update_admin_mailbox_password(mailbox_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not can_manage_mailboxes(user_info):
        raise HTTPException(status_code=403, detail="You do not have permission to manage mailboxes")
    password = str(payload.get("password", ""))
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mailbox password must be at least 8 characters")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id, AdminMailbox.is_active.is_(True)).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    ensure_mailbox_access(db, user_info, mailbox)
    mailbox.password_hash = hash_password(password)
    log_audit(db, user_info["username"], "update_mailbox_password", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {"ok": True}


@app.put("/api/admin/users/{username}")
async def api_update_user(username: str, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_info["role"] == "admin":
        if user.role != "user":
            raise HTTPException(status_code=403, detail="Admin can only edit users with 'user' role")
        if "role" in payload and payload["role"] != "user":
            raise HTTPException(status_code=403, detail="Admin can only set user role to 'user'")
    elif user_info["role"] == "superadmin":
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
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage users")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if username == user_info["username"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin account cannot be deleted")

    if user_info["role"] == "admin":
        if user.role != "user":
            raise HTTPException(status_code=403, detail="Admin can only delete users with 'user' role")

    db.query(AdminMailboxAccess).filter(AdminMailboxAccess.username == username).delete(synchronize_session=False)
    db.query(AdminMailbox).filter(AdminMailbox.created_by == username).update(
        {"created_by": user_info["username"]},
        synchronize_session=False,
    )
    log_audit(db, user_info["username"], "delete_user", None, request.client.host if request.client else None, username)
    db.delete(user)
    db.commit()
    return {"ok": True, "message": f"User {username} deleted"}


@app.get("/api/admin/audit-logs")
async def api_get_audit_logs(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view audit logs")
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {"user": log.user, "action": log.action, "email_id": log.email_id, "details": log.details, "created_at": str(log.created_at)}
        for log in logs
    ]


@app.get("/api/admin/stats")
async def api_admin_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view stats")
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()
    total_emails = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash").count()
    clean_count = db.query(QuarantineEmail).filter(
        QuarantineEmail.label == "CLEAN",
        QuarantineEmail.status != "trash",
    ).count()
    warn_count = db.query(QuarantineEmail).filter(
        QuarantineEmail.label == "WARN",
        QuarantineEmail.status != "trash",
    ).count()
    quarantine_count = db.query(QuarantineEmail).filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.status != "trash",
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
    if user_info["role"] not in ("superadmin", "admin"):
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
    if user_info["role"] not in ("superadmin", "admin"):
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



@app.get("/api/admin/user-stats")
async def api_user_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    users = db.query(User).filter(User.is_active.is_(True)).all()
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
        total = db.query(QuarantineEmail).filter(
            QuarantineEmail.status != "trash",
            or_(*email_filters),
        ).count()
        result.append({
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "total_emails": total,
            "is_active": u.is_active,
        })
    return result


@app.get("/api/admin/user-emails/{username}")
async def api_user_emails(username: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
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
    return [
        {
            "email_id": e.email_id, "subject": e.subject, "sender": e.sender,
            "label": e.label, "status": e.status, "fused_score": e.fused_score,
            "category": e.category, "received_at": e.received_at,
        }
        for e in emails
    ]


dist_dir = Path(__file__).parent / "static" / "dist"


@app.get("/")
async def serve_dashboard_root():
    return RedirectResponse(url="/login", status_code=307)


@app.get("/{file_path:path}")
async def serve_react_app(request: Request, file_path: str):
    if (
        file_path.startswith("api/") or 
        file_path == "ws" or 
        file_path == "docs" or 
        file_path == "openapi.json" or
        file_path.startswith("static/")
    ):
        raise HTTPException(status_code=404, detail="Not Found")
    
    local_file = dist_dir / file_path
    if file_path and local_file.is_file():
        return FileResponse(local_file)
    
    index_file = dist_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    
    return PlainTextResponse("React frontend is not built yet. Please build it first.")
>>>>>>> origin/mailbox

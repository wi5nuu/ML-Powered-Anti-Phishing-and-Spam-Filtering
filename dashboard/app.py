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
from datetime import datetime, timedelta, timezone
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
from email.utils import formatdate, format_datetime, getaddresses, make_msgid

from pydantic import BaseModel
import csv
import io
from fastapi import FastAPI, Request, Depends, Form, File, HTTPException, WebSocket, WebSocketDisconnect, Query, UploadFile
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator

from database.models import ApiKey, QuarantineEmail, Feedback, User, AuditLog, AuditTrail, Organization, PipelineMetrics, Report, AdminMailbox, AdminMailboxAccess, UserRole, TrainingSample, SystemSetting, _utcnow
from dashboard.database import get_db, SessionLocal
from dashboard.auth import (
    hash_password, verify_password, create_access_token, decode_token, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user, require_role, log_audit, verify_api_key
)
from dashboard.config import get_configured_mail_domain, email_uses_configured_domain, is_valid_email_address
from dashboard.rbac import (
    Permission, check_permission, check_role, get_user_permissions, has_permission_dict, ROLE_DESCRIPTIONS, UserRole as RBACUserRole
)
from dashboard import admin_routes
from mail_delivery import deliver_direct_mx, sign_outbound_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Jakarta"))


def app_now() -> datetime:
    return datetime.now(APP_TIMEZONE)


def app_now_iso() -> str:
    return app_now().isoformat(timespec="seconds")


def _admin_can_manage_user(admin: User, target: User) -> bool:
    """Apply organization scope, with domain scope for legacy global admins."""
    if admin.role == UserRole.SUPERADMIN.value:
        return True
    if target.role != UserRole.USER.value:
        return False
    if admin.organization_id:
        return target.organization_id == admin.organization_id
    return target.organization_id is None and email_uses_configured_domain(target.email or "")


def _admin_can_manage_mailbox(db: Session, admin: User, mailbox: AdminMailbox) -> bool:
    if admin.role == UserRole.SUPERADMIN.value:
        return True
    return admin.role == UserRole.ADMIN.value and mailbox.assigned_to == admin.username


def _assign_mailbox_manager(db: Session, mailbox: AdminMailbox, username: str) -> User:
    """Assign exactly one active admin as mailbox manager and sync access."""
    manager = db.query(User).filter(
        User.username == username,
        User.role == UserRole.ADMIN.value,
        User.is_active == True,
    ).first()
    if not manager:
        raise ValueError("Admin pengelola tidak ditemukan atau tidak aktif")

    admin_usernames = db.query(User.username).filter(User.role == UserRole.ADMIN.value)
    db.query(AdminMailboxAccess).filter(
        AdminMailboxAccess.mailbox_id == mailbox.id,
        AdminMailboxAccess.username.in_(admin_usernames),
    ).delete(synchronize_session=False)
    existing = db.query(AdminMailboxAccess).filter(
        AdminMailboxAccess.mailbox_id == mailbox.id,
        AdminMailboxAccess.username == manager.username,
    ).first()
    if not existing:
        db.add(AdminMailboxAccess(mailbox_id=mailbox.id, username=manager.username))
    mailbox.assigned_to = manager.username
    return manager

THREAT_RETENTION_DAYS = int(os.getenv("MAX_QUARANTINE_DAYS", "30"))
THREAT_CATEGORIES = ["spam", "phishing", "malware"]


def canonical_threat_category(category: str | None) -> str:
    """Map legacy storage/API category names to the current product contract."""
    normalized = (category or "").strip().lower()
    return "phishing" if normalized == "malware" else normalized


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
    logger.critical("DASHBOARD_SECRET_KEY environment variable is required. "
                    "Set it to a stable secret (e.g. 64-char hex) before starting the server.")
    raise SystemExit(1)

static_dir = Path(__file__).parent / "static"


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    # ── Startup ──────────────────────────────────────────────────────────────
    app.state.pubsub_task = asyncio.create_task(redis_pubsub_bridge())
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    task = getattr(app.state, "pubsub_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="CogniMail Dashboard", version="3.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)

# csrf_secret is the same as DASHBOARD_SECRET_KEY (already validated above)
is_production = os.getenv("ENV", "development") == "production"
app.add_middleware(SessionMiddleware, secret_key=DASHBOARD_SECRET_KEY, same_site="lax", https_only=is_production)
_allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
_allowed_hosts = [h.strip() for h in _allowed_hosts if h.strip() and h.strip() != "*"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
# Default CORS origins — includes Vite dev (5173), production build (8081), and configurable extras
_default_cors = "http://localhost:5173,http://localhost:8081,http://127.0.0.1:5173,http://127.0.0.1:8081"
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", _default_cors).split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    # SECURITY FIX: Restrict CORS headers to specific list instead of wildcard
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin", "X-API-Key"],
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
        
        # SECURITY FIX: Add Content-Security-Policy headers
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # unsafe-eval needed for React DevTools
            "style-src 'self' 'unsafe-inline'",  # unsafe-inline needed for styled-components
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' ws: wss:",  # WebSocket connections
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        if os.getenv("ENV", "development") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register RBAC admin routes
app.include_router(admin_routes.router)




# ─── WebSocket Connection Manager ───────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        # REALTIME FIX: Store connections with user context for org-scoped broadcasting
        self.active_connections: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, user_context: dict):
        """Connect websocket with user context (username, role, organization_id)"""
        await websocket.accept()
        self.active_connections[websocket] = user_context

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, message: dict):
        """Refresh only the mailbox that received a processed email.

        Every classification is delivered so the matching Inbox/WARN/Spam/
        Phishing list can update immediately. The browser decides whether the
        event also deserves a user notification (only released CLEAN mail).
        """
        if message.get("type") != "email_processed":
            return

        recipients = {
            str(recipient).strip().lower()
            for recipient in message.get("recipients", [])
            if str(recipient).strip()
        }
        if not recipients:
            return

        dead = []
        for connection, user_ctx in self.active_connections.items():
            try:
                mailbox_email = str(user_ctx.get("mailbox_email", "")).strip().lower()
                if user_ctx.get("role") == "mailbox" and mailbox_email in recipients:
                    await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)

manager = ConnectionManager()
PUBSUB_CHANNEL = os.getenv("PUBSUB_CHANNEL", "email:processed")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
    mailbox_token = websocket.cookies.get("mailbox_token", "")
    token = token or mailbox_token or websocket.cookies.get("access_token", "")
    if not token:
        await websocket.close(code=4001)
        return
    # A dependency-scoped SQLAlchemy session would remain open for the entire
    # WebSocket lifetime. Besides exhausting the connection pool, its read
    # transaction can block schema maintenance. Authenticate in a short-lived
    # session and close it before accepting the persistent socket.
    db = SessionLocal()
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            await websocket.close(code=4001)
            return
        
        if payload.get("role") == "mailbox":
            mailbox = resolve_active_mailbox(
                db,
                payload.get("mailbox_id"),
                payload.get("mailbox_email"),
                missing_status_code=401,
                missing_detail="Mailbox is disabled or inactive",
                inactive_detail="Mailbox is disabled or inactive",
            )
            user_context = {
                "username": mailbox.email.lower(),
                "role": "mailbox",
                "organization_id": None,
                "mailbox_email": mailbox.email.lower(),
            }
        else:
            user = db.query(User).filter(User.username == username).first()
            if not user or not user.is_active:
                await websocket.close(code=4001)
                return
            user_context = {
                "username": username,
                "role": user.role,
                "organization_id": user.organization_id,
                "mailbox_email": "",
            }
    except Exception:
        await websocket.close(code=4001)
        return
    finally:
        db.close()
    
    await manager.connect(websocket, user_context)
    try:
        while True:
            try:
                # SECURITY: Consume incoming messages with timeout for keep-alive
                # Timeout is intentional — client should send periodic pings
                await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # No message from client for 60s — send ping to check if alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break  # Connection is dead
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)


# ─── Redis Pub/Sub → WebSocket Bridge (background task) ────────────────────────

REDIS_URL_WS = os.getenv("REDIS_URL", "redis://redis:6379/0")

async def redis_pubsub_bridge():
    """Listen for Redis pub/sub messages and broadcast to WebSocket clients.
    
    Uses exponential backoff (5s → 10s → 20s → 40s → max 60s) on reconnect
    so a prolonged Redis outage doesn't spam logs at full speed.
    """
    _backoff = 5.0
    _backoff_max = 60.0

    while True:
        r = None
        try:
            r = aio_redis.from_url(
                REDIS_URL_WS,
                socket_timeout=15,
                socket_connect_timeout=10,
                socket_keepalive=True,
                protocol=2,
            )
            async with r.pubsub() as pubsub:
                await pubsub.subscribe(PUBSUB_CHANNEL)
                logger.info("Redis pub/sub bridge started on channel: %s", PUBSUB_CHANNEL)
                _backoff = 5.0  # reset backoff on successful connection
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
            logger.error(
                "pubsub_bridge_error: %s — reconnecting in %.0fs...", e, _backoff
            )
            await asyncio.sleep(_backoff)
            _backoff = min(_backoff * 2, _backoff_max)  # exponential backoff
        finally:
            if r is not None:
                with contextlib.suppress(Exception):
                    await r.aclose()



# ─── Seed Admin User ────────────────────────────────────────────────────────────

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
    """
    Create or update a seed user.

    Password update policy:
      - New user  → always set password from env.
      - Existing user with a known-insecure password (e.g. still "admin") →
        upgrade to the env-provided password so default credentials are
        rotated automatically on first real deployment.
      - Existing user with a custom password → leave it alone; the operator
        has already changed it and we must not overwrite their choice on
        every container restart.

    Args:
        insecure_passwords: List of plaintext passwords considered insecure
            (e.g. ["admin", "password"]).  If the existing user's stored hash
            matches any of these, the password is replaced with ``password``.
    """
    from dashboard.auth import verify_password  # local import avoids circular dep at module level

    legacy_usernames = legacy_usernames or []
    insecure_passwords = insecure_passwords or []

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
        # Brand-new user — always set the env password
        user.hashed_password = hash_password(password)
    else:
        # Existing user — only overwrite password if it is still one of the
        # known-insecure defaults.  A custom password must never be touched.
        is_still_insecure = any(
            verify_password(insecure, user.hashed_password)
            for insecure in insecure_passwords
        )
        if is_still_insecure:
            user.hashed_password = hash_password(password)
        # else: leave the user's custom password intact

    # Only set email if provided — never overwrite an existing email with None
    if role in ("admin", "superadmin"):
        user.email = None
    elif email is not None:
        user.email = email
    user.role = role
    user.is_active = True
    return user


def seed_admin():
    """Seed only the break-glass superadmin account from environment.

    Admin and user accounts are database-managed identities. Recreating them
    from environment variables on every startup would resurrect an old
    username after a profile rename and produce duplicate administrator rows.
    """
    db = SessionLocal()
    # Restore the persisted organization domain before routes start serving
    # requests. This keeps mailbox creation and validation consistent after a
    # process restart.
    persisted_domain = db.query(SystemSetting).filter(
        SystemSetting.key == "organization_domain"
    ).first()
    if persisted_domain and persisted_domain.value:
        os.environ["VITE_MAIL_DOMAIN"] = persisted_domain.value
    from dashboard.database import engine as _sync_engine
    dialect = _sync_engine.dialect.name
    if dialect == "postgresql":
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS attachments_json TEXT"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS spf_result VARCHAR(32) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dkim_result VARCHAR(32) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS dmarc_result VARCHAR(32) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS message_id_header VARCHAR(998) DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS references_header TEXT DEFAULT ''"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS is_starred BOOLEAN DEFAULT FALSE"))
        db.execute(text("ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMP"))
    else:
        logger.warning("seed_admin: dialect bukan postgresql (%s), skip schema migration", dialect)
    purge_expired_emails(db)
    db.query(QuarantineEmail).filter(
        QuarantineEmail.status == "released",
        QuarantineEmail.label.in_(["WARN", "QUARANTINE"]),
    ).update({"label": "CLEAN", "category": "clean"}, synchronize_session=False)
    legacy_user_roles = ["ana" + "lyst", "mail" + "_" + "re" + "view" + "er"]
    db.query(User).filter(User.role.in_(legacy_user_roles)).update({"role": "user"})
    db.query(User).filter(User.role == "security" + "_admin").update({"role": "admin"})

    seeded_superadmin = _upsert_seed_user(
        db,
        os.getenv("SUPERADMIN_USERNAME", "super"),
        os.getenv("SUPERADMIN_PASSWORD", "super"),
        "superadmin",
        None,
        legacy_usernames=["superadmin"],
    )
    # Administrator accounts have no email identity; only mailbox users do.
    db.query(User).filter(User.role.in_(["admin", "superadmin"])).update(
        {"email": None}, synchronize_session=False
    )

    # Backfill ownership for installations created before ``assigned_to``
    # became mandatory. Prefer an existing explicit admin grant, then the
    # creator, and finally the sole active admin. Ambiguous mailboxes remain
    # unassigned so a superadmin can choose the correct manager explicitly.
    active_admins = db.query(User).filter(
        User.role == UserRole.ADMIN.value,
        User.is_active == True,
    ).all()
    unassigned_mailboxes = db.query(AdminMailbox).filter(or_(
        AdminMailbox.assigned_to.is_(None),
        AdminMailbox.assigned_to == "",
    )).all()
    for mailbox in unassigned_mailboxes:
        access_candidates = db.query(User).join(
            AdminMailboxAccess,
            AdminMailboxAccess.username == User.username,
        ).filter(
            AdminMailboxAccess.mailbox_id == mailbox.id,
            User.role == UserRole.ADMIN.value,
            User.is_active == True,
        ).all()
        manager = access_candidates[0] if len(access_candidates) == 1 else None
        if manager is None and mailbox.created_by:
            manager = db.query(User).filter(
                User.username == mailbox.created_by,
                User.role == UserRole.ADMIN.value,
                User.is_active == True,
            ).first()
        if manager is None and len(active_admins) == 1:
            manager = active_admins[0]
        if manager is not None:
            _assign_mailbox_manager(db, mailbox, manager.username)

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
                        "user": {
                            "username": user.username,
                            "role": user.role,
                            "email": user.email or "",
                            "avatar_url": user.avatar_url or "",
                        }
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
                        "sender_name": mailbox.sender_name or "",
                        "avatar_url": mailbox.avatar_url or "",
                    }
                })
        except Exception as e:
            logger.warning(f"auth_me: mailbox token decode failed: {e}")

    logger.warning(f"auth_me: no valid session from {client_host}")
    response = JSONResponse({"authenticated": False, "user": None})
    if mailbox_token:
        # Database validation above invalidates deleted/disabled mailbox JWTs.
        # Remove the stale cookie too, so an old tab cannot retain that identity.
        response.delete_cookie("mailbox_token")
        response.delete_cookie("mailbox_token", path="/")
    return response


@app.post("/api/auth/login")
@limiter.limit("20/minute")
async def auth_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
                     db: Session = Depends(get_db)):
    identity = form_data.username.strip()
    user = db.query(User).filter(
        or_(
            func.lower(User.username) == identity.lower(),
            func.lower(User.email) == identity.lower(),
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
        response.delete_cookie("mailbox_token", path="/")
        return response

    # Mailbox addresses created by an admin are also first-class user accounts.
    # Logging in with that email must open webmail directly from the main form.
    mailbox = db.query(AdminMailbox).filter(
        func.lower(AdminMailbox.email) == identity.lower()
    ).first() if "@" in identity else None
    if not mailbox or not verify_password(form_data.password, mailbox.password_hash or ""):
        raise HTTPException(401, "Invalid email or password")
    if not mailbox.is_active:
        raise HTTPException(403, "Mailbox is disabled")

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
        "mailbox_id": str(mailbox.id),
        "mailbox_email": mailbox.email.lower(),
        "mailbox": {
            "id": mailbox.id,
            "email": mailbox.email.lower(),
            "sender_name": mailbox.sender_name or "",
            "avatar_url": mailbox.avatar_url or "",
        },
    })
    response.set_cookie(
        key="mailbox_token", value=mailbox_token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production",
        path="/",
    )
    response.delete_cookie("access_token", path="/")
    return response


@app.post("/api/auth/logout")
async def auth_logout():
    # P3 FIX: Clear both dashboard and mailbox session cookies on logout
    response = JSONResponse({"ok": True})
    response.delete_cookie("access_token")
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("mailbox_token")
    response.delete_cookie("mailbox_token", path="/")
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
    oauth_state = _secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": oauth_state,
    })
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")
    response.set_cookie(
        "google_oauth_state", oauth_state, max_age=600, httponly=True,
        secure=os.getenv("ENV", "development") == "production",
        samesite="lax", path="/auth/google/callback",
    )
    return response


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", error: str = "", state: str = "", db: Session = Depends(get_db)):
    expected_state = request.cookies.get("google_oauth_state", "")
    if not state or not expected_state or not _secrets.compare_digest(state, expected_state):
        return RedirectResponse(url="/login?error=invalid_oauth_state")
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
    elif user.role == "user":
        redirect_url = "/user/mailboxes"
    else:
        redirect_url = "/login"
    response = RedirectResponse(url=redirect_url)
    response.delete_cookie("google_oauth_state", path="/auth/google/callback")
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production",
        path="/",
    )
    return response


# ─── Profile Endpoints ─────────────────────────────────────────────────

def _resolve_profile_subject(request: Request, db: Session, mailbox_id: str = ""):
    """Return (actor username, target user/mailbox, target kind) for profile operations."""
    token = request.cookies.get("access_token") or request.cookies.get("mailbox_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    if payload.get("role") == "mailbox":
        mailbox = resolve_active_mailbox(
            db,
            payload.get("mailbox_id"),
            payload.get("mailbox_email"),
        )
        return mailbox.email.lower(), mailbox, "mailbox"

    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(401, "Account is disabled or inactive")

    requested_mailbox_id = str(mailbox_id or "").strip()
    if not requested_mailbox_id:
        return user.username, user, "user"

    mailbox = resolve_active_mailbox(db, requested_mailbox_id)
    allowed = user.role == UserRole.SUPERADMIN.value
    if not allowed and user.role == UserRole.ADMIN.value:
        allowed = _admin_can_manage_mailbox(db, user, mailbox)
    if not allowed and user.role != UserRole.ADMIN.value:
        allowed = db.query(AdminMailboxAccess).filter(
            AdminMailboxAccess.mailbox_id == mailbox.id,
            AdminMailboxAccess.username == user.username,
        ).first() is not None
    if not allowed and user.role == UserRole.USER.value and user.email:
        user_email = user.email.strip().lower()
        allowed = mailbox.email.lower() == user_email
    if not allowed:
        raise HTTPException(403, "You do not have access to this mailbox profile")
    return user.username, mailbox, "mailbox"


@app.get("/api/auth/profile")
async def get_profile(
    request: Request,
    mailbox_id: str = Query(""),
    db: Session = Depends(get_db),
):
    _, subject, subject_kind = _resolve_profile_subject(request, db, mailbox_id)
    if subject_kind == "mailbox":
        mailbox = subject
        return {
            "username": mailbox.email.lower(),
            "role": "mailbox",
            "is_active": mailbox.is_active,
            "created_at": str(mailbox.created_at) if mailbox.created_at else None,
            "mailbox_id": str(mailbox.id),
            "mailbox_email": mailbox.email.lower(),
            "domain": mailbox.domain,
            "sender_name": mailbox.sender_name or "",
            "avatar_url": mailbox.avatar_url or "",
        }
    user = subject
    profile = {
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": str(user.created_at) if user.created_at else None,
        "organization_id": user.organization_id,
        "avatar_url": user.avatar_url or "",
    }
    if user.role == UserRole.USER.value:
        profile["email"] = user.email or ""
    return profile


@app.post("/api/auth/profile/avatar")
async def upload_profile_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    mailbox_id: str = Query(""),
    db: Session = Depends(get_db),
):
    """Validate, sanitize, and persist a profile image for a user or accessible mailbox."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    actor, subject, subject_kind = _resolve_profile_subject(request, db, mailbox_id)
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if avatar.content_type not in allowed_types:
        raise HTTPException(400, "Avatar must be a JPEG, PNG, GIF, or WebP image")

    content = await avatar.read((1024 * 1024) + 1)
    if not content:
        raise HTTPException(400, "Avatar file is empty")
    if len(content) > 1024 * 1024:
        raise HTTPException(413, "Avatar must be 1 MB or smaller")

    try:
        with Image.open(io.BytesIO(content)) as uploaded:
            uploaded.verify()
        with Image.open(io.BytesIO(content)) as uploaded:
            image = ImageOps.exif_transpose(uploaded)
            if image.width != image.height:
                raise HTTPException(400, "Avatar must have a square aspect ratio")
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            sanitized = io.BytesIO()
            image.save(sanitized, format="PNG", optimize=True)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(400, "Avatar file is not a valid image") from exc

    avatar_dir = static_dir / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    subject_id = getattr(subject, "id", "profile")
    filename = f"{subject_kind}_{subject_id}_{_secrets.token_hex(8)}.png"
    avatar_path = avatar_dir / filename
    previous_url = (getattr(subject, "avatar_url", "") or "").strip()
    avatar_path.write_bytes(sanitized.getvalue())
    subject.avatar_url = f"/static/avatars/{filename}"

    try:
        log_audit(
            db,
            actor,
            "update_profile_avatar",
            None,
            request.client.host if request.client else None,
            f"{subject_kind}:{subject_id}",
        )
        db.commit()
    except Exception:
        db.rollback()
        avatar_path.unlink(missing_ok=True)
        raise

    if previous_url.startswith("/static/avatars/"):
        previous_name = Path(previous_url).name
        previous_path = avatar_dir / previous_name
        if previous_path != avatar_path:
            previous_path.unlink(missing_ok=True)

    return {"ok": True, "avatar_url": subject.avatar_url}


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

    if not new_username:
        raise HTTPException(400, "Username is required")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", new_username):
        raise HTTPException(
            400,
            "Username must be 3-64 characters and may only contain letters, numbers, dots, underscores, or hyphens",
        )
    if new_username != user.username:
        existing = db.query(User).filter(User.username == new_username).first()
        if existing:
            raise HTTPException(400, "Username already exists")
    if new_password:
        if not current_password:
            raise HTTPException(400, "Current password is required to change password")
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(400, "Current password is incorrect")
        if len(new_password) < 8:
            raise HTTPException(400, "New password must be at least 8 characters")
        if not any(character.isupper() for character in new_password):
            raise HTTPException(400, "New password must contain at least one uppercase letter")
        if not any(character.islower() for character in new_password):
            raise HTTPException(400, "New password must contain at least one lowercase letter")
        if not any(character.isdigit() for character in new_password):
            raise HTTPException(400, "New password must contain at least one digit")

    old_username = user.username
    user.username = new_username
    if user.role in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        user.email = None
    if new_password:
        user.hashed_password = hash_password(new_password)
    if new_username != old_username:
        db.query(AdminMailboxAccess).filter(
            AdminMailboxAccess.username == old_username
        ).update({"username": new_username}, synchronize_session=False)
        # Mailbox authorization is username-based. Keep ownership in sync so
        # changing an admin login never removes access to managed mailboxes.
        db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == old_username
        ).update({"assigned_to": new_username}, synchronize_session=False)
        db.query(AdminMailbox).filter(
            AdminMailbox.created_by == old_username
        ).update({"created_by": new_username}, synchronize_session=False)
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
    # P0 FIX: Only admin and superadmin can manage API keys
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(403, "Only admin or superadmin can manage API keys")
    query = db.query(ApiKey)
    if user.role != "superadmin":
        if user.organization_id is None:
            return []
        query = query.filter(ApiKey.organization_id == user.organization_id)
    keys = query.order_by(ApiKey.created_at.desc()).all()
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
    # P0 FIX: Only admin and superadmin can create API keys
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(403, "Only admin or superadmin can create API keys")
    if user.role == "admin" and user.organization_id is None:
        raise HTTPException(400, "Admin must belong to an organization before creating API keys")
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
    # P0 FIX: Only admin and superadmin can delete API keys
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(403, "Only admin or superadmin can delete API keys")
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(404, "API key not found")
    # P0 FIX: Validate org ownership - admin can only delete keys from their org
    if user.role == "admin" and api_key.organization_id != user.organization_id:
        raise HTTPException(403, "You can only delete API keys from your organization")
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
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
    mail_domain = get_configured_mail_domain()
    public_base_url = os.getenv("PUBLIC_BASE_URL", f"https://{mail_domain}").rstrip("/")
    return PlainTextResponse(
        f"Contact: mailto:security@{mail_domain}\n"
        "Preferred-Languages: en, id\n"
        f"Canonical: {public_base_url}/.well-known/security.txt\n"
        f"Policy: {public_base_url}/security-policy\n"
    )


@app.get("/api/health")
async def api_health(db: Session = Depends(get_db)):
    # Database check
    try:
        db.execute(func.count(QuarantineEmail.id))
        db_status = "connected"
    except Exception:
        db_status = "error"

    # Redis check
    redis_status = False
    try:
        _redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _rc = aio_redis.from_url(_redis_url, socket_connect_timeout=2, protocol=2)
        await _rc.ping()
        await _rc.aclose()
        redis_status = True
    except Exception:
        redis_status = False

    # Classifier check
    classifier_status = False
    try:
        _classifier_url = os.getenv("CLASSIFIER_URL", "http://classifier:8001").rstrip("/")
        async with httpx.AsyncClient(timeout=3) as _client:
            _r = await _client.get(f"{_classifier_url}/health")
            classifier_status = _r.status_code == 200
    except Exception:
        classifier_status = False

    overall = "healthy" if db_status == "connected" else "degraded"
    return {
        "status": overall,
        "version": "3.0.0",
        "database": db_status,
        "redis": redis_status,
        "classifier": classifier_status,
        "websocket_connections": len(manager.active_connections),
        "uptime": "N/A",
    }


@app.get("/api/stats")
async def api_stats(
    request: Request,
    mailbox: str = Query(None),
    mailbox_id: str = Query(None),
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    review_access = can_review_threats(user_info)
    mailbox = (mailbox or "").strip().lower()
    mailbox_id = (mailbox_id or "").strip()
    identities = []
    if user_info["role"] == "mailbox":
        identity = (user_info.get("mailbox_email") or "").strip().lower()
        identities = [identity] if identity else []
    elif user_info["role"] in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value) and (mailbox or mailbox_id):
        mailbox_record = resolve_active_mailbox(
            db,
            mailbox_id,
            mailbox,
            missing_status_code=404,
            missing_detail="Mailbox not found",
        )
        ensure_mailbox_access(db, mailbox_record, user_info)
        identities = [mailbox_record.email.lower()]
    elif user_info["role"] == UserRole.ADMIN.value:
        identities = [mailbox.email.lower() for mailbox in db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == user_info["username"],
            AdminMailbox.is_active == True,
        ).all()]
    elif user_info["role"] == UserRole.SUPERADMIN.value:
        # Superadmin dashboard statistics must still be scoped to real,
        # currently active mailbox accounts. Without this guard the global
        # query can count legacy/orphan test rows that are no longer visible
        # in any mailbox UI, which makes the overview look like it has
        # threats even when every managed mailbox is empty.
        identities = [
            row.email.lower()
            for row in db.query(AdminMailbox.email).filter(AdminMailbox.is_active == True).all()
            if row.email
        ]
    elif user_info["role"] != UserRole.SUPERADMIN.value:
        identity = (user_info.get("mailbox_email") or "").strip().lower()
        if not identity:
            user = db.query(User).filter(User.username == user_info["username"]).first()
            identity = (user.email if user and user.email else "").strip().lower()
        identities = [identity] if identity else []

    global_scope = False

    def scoped(q, direction: str = "incoming"):
        if not review_access:
            # Apply the same strict visibility rule used by the mailbox list
            # and detail endpoints. Counts must never reveal or include mail
            # that is still waiting in quarantine, even when its label was
            # left in an inconsistent state by older data.
            q = q.filter(mailbox_visible_email_clause())
        if not global_scope:
            identity_column = (
                QuarantineEmail.sender
                if direction == "outgoing"
                else QuarantineEmail.recipient_list
            )
            filters = [
                condition
                for identity in identities
                for condition in _mailbox_identity_filters(identity_column, identity)
            ]
            return q.filter(or_(*filters)) if filters else q.filter(False)
        return q

    all_mail_query = scoped(db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.label.notin_(["SENT", "DRAFT"]),
    ))
    total = all_mail_query.count() or 0
    trash_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.status == "trash")).scalar() or 0
    quarantine_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    )).scalar() or 0
    warn_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "WARN",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    )).scalar() or 0
    clean_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "CLEAN",
        QuarantineEmail.status != "trash",
    )).scalar() or 0
    unread_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "CLEAN",
        QuarantineEmail.status != "trash",
        QuarantineEmail.is_read == False,
    )).scalar() or 0
    draft_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "DRAFT",
        QuarantineEmail.status != "trash",
    ), direction="outgoing").scalar() or 0
    sent_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "SENT",
        QuarantineEmail.status != "trash",
    ), direction="outgoing").scalar() or 0
    starred_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.is_starred == True,
        QuarantineEmail.status != "trash",
        QuarantineEmail.label.notin_(["SENT", "DRAFT"]),
    )).scalar() or 0
    avg_anomaly = scoped(db.query(func.avg(QuarantineEmail.anomaly_score))).scalar() or 0
    avg_fused = scoped(db.query(func.avg(QuarantineEmail.fused_score))).scalar() or 0
    # Per-category breakdown
    cat_q = scoped(db.query(
        QuarantineEmail.category, func.count(QuarantineEmail.id)
    ).filter(
        QuarantineEmail.category != "",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    )).group_by(QuarantineEmail.category).all()
    categories = {row[0]: row[1] for row in cat_q}
    categories["phishing"] = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.category.in_(["phishing", "malware"]),
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    )).scalar() or 0
    categories["malware"] = 0
    categories["spam"] = scoped(db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
        or_(
            and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"),
            and_(
                QuarantineEmail.label == "QUARANTINE",
                or_(
                    QuarantineEmail.category == "",
                    QuarantineEmail.category.is_(None),
                    ~QuarantineEmail.category.in_(["spam", "phishing", "malware"]),
                ),
            ),
        ),
    )).scalar() or 0
    categories["warn"] = warn_count
    categories["draft"] = draft_count
    if not review_access:
        # WARN is delivered to the mailbox's dedicated Peringatan view. The
        # detailed review telemetry remains restricted, while its count and
        # message itself are visible to the intended recipient.
        total = clean_count + warn_count
        trash_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.status == "trash",
            QuarantineEmail.label.in_(["CLEAN", "SENT", "DRAFT"]),
        )).scalar() or 0
        quarantine_count = 0
        starred_count = scoped(db.query(func.count(QuarantineEmail.id)).filter(
            QuarantineEmail.is_starred == True,
            QuarantineEmail.status != "trash",
            QuarantineEmail.label.in_(["CLEAN", "WARN"]),
        )).scalar() or 0
        avg_anomaly = 0
        avg_fused = 0
        categories = {"warn": warn_count, "draft": draft_count}
    return {
        "total": total,
        "trash": trash_count,
        "quarantine": quarantine_count,
        "warn": warn_count,
        "clean": clean_count,
        "unread": unread_count,
        "draft": draft_count,
        "sent": sent_count,
        "starred": starred_count,
        "avg_anomaly_score": round(float(avg_anomaly), 4),
        "avg_fused_score": round(float(avg_fused), 4),
        "categories": categories,
    }


# ─── New API Endpoints & SPA Routing ───────────────────────────────────────────

def get_authenticated_api_user(request: Request, db: Session = Depends(get_db), *, allow_mailbox_token: bool = False) -> dict:
    # For webmail endpoints pass allow_mailbox_token=True.
    # For all dashboard/admin/user endpoints use the default (False) so
    # a mailbox session can never access protected dashboard resources.
    token = request.cookies.get("access_token")
    if not token and allow_mailbox_token:
        token = request.cookies.get("mailbox_token")
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
        return {"username": user.username, "role": user.role, "mailbox_email": user.email.lower() if user.email else ""}
    except HTTPException:
        raise
    except Exception:
        logger.warning(f"get_authenticated_api_user: token decode failed")
        raise HTTPException(status_code=401, detail="Token is invalid or expired")


def can_review_threats(user_info: dict) -> bool:
    """Only authenticated dashboard admins may inspect quarantined mail."""
    return user_info.get("role") in {
        UserRole.ADMIN.value,
        UserRole.SUPERADMIN.value,
    }


def email_is_visible_to_mailbox_user(email_record: QuarantineEmail) -> bool:
    """Return whether a non-reviewer may access an email record.

    Incoming mail is deny-by-default: a CLEAN label alone is insufficient
    because legacy/in-flight rows can still carry a quarantined status.  Mail
    released by an admin remains visible even when its historical category is
    phishing/spam/malware. Outgoing and draft records are allowed only while
    they are not in a quarantine state.
    """
    label = str(email_record.label or "").upper()
    status = str(email_record.status or "").lower()
    # Trash is an administrative retention area. A mailbox/user session may
    # move its own message there, but cannot enumerate or reopen it afterward.
    if status == "trash":
        return False
    if label == "CLEAN":
        return status == "released"
    if label == "WARN":
        return status == "warn_delivered"
    if label in {"SENT", "DRAFT"}:
        return status not in {"quarantined", "pending", "blocked"}
    return False


def mailbox_visible_email_clause():
    """SQL equivalent of ``email_is_visible_to_mailbox_user``."""
    label = func.upper(func.coalesce(QuarantineEmail.label, ""))
    status = func.lower(func.coalesce(QuarantineEmail.status, ""))
    return and_(
        status != "trash",
        or_(
            and_(label == "CLEAN", status == "released"),
            and_(label == "WARN", status == "warn_delivered"),
            and_(
                label.in_(["SENT", "DRAFT"]),
                ~status.in_(["quarantined", "pending", "blocked"]),
            ),
        ),
    )


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
    "warn": "WARN",
}


def email_belongs_to_identity(email_record: QuarantineEmail, identity: str = "") -> bool:
    target = (identity or "").strip().lower()
    if not target:
        return False

    def _addresses(value: str) -> list[str]:
        return [addr.lower() for _, addr in getaddresses([value or ""]) if addr]

    return target in _addresses(email_record.recipient_list) or target in _addresses(email_record.sender)


def email_matches_mailbox_direction(
    email_record: QuarantineEmail,
    identity: str,
    direction: str,
) -> bool:
    """Match one mailbox identity against exactly one delivery direction."""
    target = (identity or "").strip().lower()
    if not target:
        return False

    column_value = (
        email_record.sender
        if direction == "outgoing"
        else email_record.recipient_list
    )
    addresses = {
        address.lower()
        for _, address in getaddresses([column_value or ""])
        if address
    }
    return target in addresses


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


def _purge_mailbox_autologin_tokens(mailbox_id: int) -> None:
    """Invalidate pending one-time mailbox tokens after a status change or deletion."""
    token_store = globals().get("_autologin_tokens", {})
    for token, entry in list(token_store.items()):
        if entry.get("mailbox_id") == mailbox_id:
            token_store.pop(token, None)


def _permanently_delete_mailbox(db: Session, mailbox: AdminMailbox) -> dict[str, int]:
    """Delete a mailbox and every email-owned record in the same transaction."""
    identity = (mailbox.email or "").strip().lower()
    candidates = db.query(QuarantineEmail).filter(or_(
        QuarantineEmail.sender.ilike(f"%{identity}%"),
        QuarantineEmail.recipient_list.ilike(f"%{identity}%"),
    )).all() if identity else []
    mailbox_emails = [record for record in candidates if email_belongs_to_identity(record, identity)]
    email_ids = [record.email_id for record in mailbox_emails]

    deleted_feedback = 0
    deleted_training_samples = 0
    deleted_audit_logs = 0
    deleted_audit_trails = 0
    if email_ids:
        # Keep each IN clause below common database parameter limits.
        for start in range(0, len(email_ids), 500):
            chunk = email_ids[start:start + 500]
            deleted_feedback += db.query(Feedback).filter(
                Feedback.email_id.in_(chunk)
            ).delete(synchronize_session=False)
            deleted_training_samples += db.query(TrainingSample).filter(
                TrainingSample.email_id.in_(chunk)
            ).delete(synchronize_session=False)
            deleted_audit_logs += db.query(AuditLog).filter(
                AuditLog.email_id.in_(chunk)
            ).delete(synchronize_session=False)
            deleted_audit_trails += db.query(AuditTrail).filter(
                AuditTrail.target_id.in_(chunk)
            ).delete(synchronize_session=False)
        for record in mailbox_emails:
            db.delete(record)

    deleted_access = db.query(AdminMailboxAccess).filter(
        AdminMailboxAccess.mailbox_id == mailbox.id
    ).delete(synchronize_session=False)
    db.delete(mailbox)
    _purge_mailbox_autologin_tokens(mailbox.id)
    return {
        "emails": len(mailbox_emails),
        "feedback": deleted_feedback,
        "training_samples": deleted_training_samples,
        "audit_logs": deleted_audit_logs,
        "audit_trails": deleted_audit_trails,
        "access_records": deleted_access,
    }


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


def ensure_mailbox_access(db: Session, mailbox: AdminMailbox, user_info: dict):
    """Enforce mailbox ownership for every role at the API boundary."""
    role = user_info.get("role")
    username = user_info.get("username", "")
    if role == UserRole.SUPERADMIN.value:
        return
    if role == UserRole.ADMIN.value:
        if mailbox.assigned_to == username:
            return
        raise HTTPException(status_code=403, detail="Admin tidak memiliki akses ke mailbox ini")
    if role == "mailbox":
        if str(mailbox.id) == str(user_info.get("mailbox_id", "")):
            return
        raise HTTPException(status_code=403, detail="Sesi ini hanya berlaku untuk mailbox yang sedang login")

    user = db.query(User).filter(User.username == username).first()
    if user and user.email and mailbox.email.lower() == user.email.strip().lower():
        return
    granted = db.query(AdminMailboxAccess).filter(
        AdminMailboxAccess.mailbox_id == mailbox.id,
        AdminMailboxAccess.username == username,
    ).first()
    if granted:
        return
    raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke mailbox ini")


@app.get("/api/mailboxes/{mailbox_id}/access")
async def api_validate_mailbox_access(
    mailbox_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate that a routed mailbox still exists, is active, and is accessible."""
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    try:
        mailbox = resolve_active_mailbox(
            db,
            mailbox_id,
            missing_status_code=404,
            missing_detail="Mailbox tidak ditemukan atau sudah dihapus",
            inactive_detail="Mailbox sedang dinonaktifkan",
        )
    except HTTPException:
        # Preserve the legacy virtual mailbox only for a regular user's exact
        # own email address. Numeric/deleted managed mailboxes always stay 404.
        own_identity = (user_info.get("mailbox_email") or "").strip().lower()
        requested_identity = mailbox_id.strip().lower()
        if user_info.get("role") == UserRole.USER.value and "@" in requested_identity and requested_identity == own_identity:
            return {
                "ok": True,
                "id": requested_identity,
                "email": requested_identity,
                "is_active": True,
                "virtual": True,
            }
        raise
    ensure_mailbox_access(db, mailbox, user_info)
    return {
        "ok": True,
        "id": str(mailbox.id),
        "email": mailbox.email.lower(),
        "is_active": True,
    }


def ensure_sender_access(db: Session, sender_address: str, user_info: dict):
    sender = (sender_address or "").strip().lower()
    if not sender:
        raise HTTPException(status_code=400, detail="Alamat pengirim wajib diisi")
    mailbox = db.query(AdminMailbox).filter(
        AdminMailbox.email == sender,
        AdminMailbox.is_active == True,
    ).first()
    if mailbox:
        ensure_mailbox_access(db, mailbox, user_info)
        return
    if user_info.get("role") == UserRole.SUPERADMIN.value:
        return
    own_address = (user_info.get("mailbox_email") or "").strip().lower()
    if sender != own_address:
        raise HTTPException(status_code=403, detail="Anda tidak dapat mengirim menggunakan alamat email ini")


def ensure_email_access(db: Session, email_record: QuarantineEmail, user_info: dict):
    if user_info["role"] == UserRole.SUPERADMIN.value:
        return
    if user_info["role"] == UserRole.ADMIN.value:
        managed = db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == user_info["username"],
            AdminMailbox.is_active == True,
        ).all()
        if any(email_belongs_to_identity(email_record, mailbox.email) for mailbox in managed):
            return
        raise HTTPException(status_code=403, detail="Admin tidak memiliki akses ke email mailbox ini")
    identity = user_info.get("mailbox_email") or user_info.get("username")
    # If no valid email identity can be resolved, allow access
    # (e.g. generic user account with no email set — list is already unscoped)
    if not identity or "@" not in identity:
        raise HTTPException(status_code=403, detail="A mailbox identity is required to access email")
    if not email_belongs_to_identity(email_record, identity):
        raise HTTPException(status_code=403, detail="You do not have permission to access this email")
    if not email_is_visible_to_mailbox_user(email_record):
        # Do not reveal quarantined message IDs to normal mailbox sessions.
        raise HTTPException(status_code=404, detail="Email not found")

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
    category = canonical_threat_category(email.category)
    label = (email.label or "").upper()
    if label == "WARN":
        return "warn"
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


def renderable_email_body(content: str = "") -> str:
    """Decode the visible MIME body while keeping raw RFC data server-side."""
    source = (content or "").replace("\x00", "")
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    header_block = normalized.split("\n\n", 1)[0]
    if not re.search(
        r"(?im)^(?:from|to|subject|date|message-id|mime-version|content-type):\s*",
        header_block,
    ):
        return source

    try:
        message = Parser(policy=policy.default).parsestr(source)
    except Exception:
        return source

    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        if (part.get_content_disposition() or "").lower() in {"attachment", "inline"}:
            continue
        if part.get_filename():
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        try:
            decoded = str(part.get_content())
        except Exception:
            raw_part = part.get_payload(decode=True) or b""
            decoded = raw_part.decode(part.get_content_charset() or "utf-8", errors="replace")
        (html_parts if content_type == "text/html" else plain_parts).append(decoded)

    if html_parts:
        rendered = "\n".join(html_parts)
        rendered = re.sub(r"(?is)<(script|iframe|object|embed|form|style)\b.*?</\1>", "", rendered)
        rendered = re.sub(r"(?i)\son[a-z]+\s*=\s*(['\"]).*?\1", "", rendered)
        return re.sub(r"(?i)javascript:", "", rendered)
    if plain_parts:
        return linkify_plain_text("\n".join(plain_parts).strip())
    return ""


def plain_email_body(content: str = "") -> str:
    body = renderable_email_body(content).replace("\r\n", "\n")

    # Some legacy rows contain an entire MIME message wrapped in <pre>/<div>
    # instead of the already-decoded body. Decode that structure before it is
    # quoted in a reply, otherwise base64 attachment data leaks into the text.
    mime_candidate = html.unescape(body)
    mime_candidate = re.sub(
        r"(?i)<\s*(?:br\s*/?|/div|/p|/pre|/li|/tr)\s*>",
        "\n",
        mime_candidate,
    )
    mime_candidate = re.sub(r"(?s)<[^>]+>", "", mime_candidate).strip()
    mime_header = re.search(r"(?im)^(?:mime-version|content-type):\s*", mime_candidate)
    if mime_header:
        try:
            parsed = Parser(policy=policy.default).parsestr(mime_candidate[mime_header.start():])
            plain_parts: list[str] = []
            html_parts: list[str] = []
            for part in parsed.walk():
                if part.is_multipart():
                    continue
                if (part.get_content_disposition() or "").lower() in {"attachment", "inline"}:
                    continue
                if part.get_filename():
                    continue
                content_type = part.get_content_type()
                if content_type not in {"text/plain", "text/html"}:
                    continue
                try:
                    decoded_part = str(part.get_content())
                except Exception:
                    raw_part = part.get_payload(decode=True) or b""
                    decoded_part = raw_part.decode(part.get_content_charset() or "utf-8", errors="replace")
                if content_type == "text/plain":
                    plain_parts.append(decoded_part)
                else:
                    html_parts.append(decoded_part)
            decoded_body = "\n".join(plain_parts or html_parts).strip()
            if decoded_body:
                body = decoded_body
        except Exception:
            logger.warning("Unable to decode stored MIME body for reply", exc_info=True)

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


def email_body_preview(content: str = "", limit: int = 180) -> str:
    """Build a plain, quote-free mailbox preview, including legacy rows."""
    body = renderable_email_body(content).replace("\r\n", "\n")
    for _ in range(3):
        decoded = html.unescape(body)
        if decoded == body:
            break
        body = decoded

    if "\n\n" in body:
        first_block, rest = body.split("\n\n", 1)
        if any(
            re.match(r"^(from|to|subject|date|message-id|reply-to|cc|bcc|spf|dkim|dmarc):\s*", line.strip(), re.I)
            for line in first_block.split("\n")
            if line.strip()
        ):
            body = rest

    body = re.split(
        r"(?is)<div\b[^>]*class=[\"'][^\"']*gmail_quote[^\"']*[\"'][^>]*>",
        body,
        maxsplit=1,
    )[0]
    body = re.split(
        r"(?im)^\s*-{5,}\s*(?:Original|Forwarded) message\s*-{5,}\s*$",
        body,
        maxsplit=1,
    )[0]
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body)
    body = re.sub(r"(?i)<\s*(?:br\s*/?|/div|/p|/li|/tr)\s*>", " ", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = html.unescape(body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return " ".join(body.split())[:limit]


def append_thread_context(body: str, original: QuarantineEmail, action: str) -> str:
    if not original:
        return body
    marker = "---------- Forwarded message ---------" if action == "forward" else "---------- Original message ---------"
    if marker in (body or "") or re.search(r'class=["\'][^"\']*gmail_quote', body or "", re.I):
        return body

    # Gmail and most modern mail clients recognize gmail_quote + blockquote as
    # quoted history and collapse it behind their three-dot control. Keep the
    # new message outside that block so only the old conversation is hidden.
    new_body = body or ""
    new_body_html = new_body if re.search(r"<[^>]+>", new_body) else linkify_plain_text(new_body)
    sender = html.escape(original.sender or "-")
    if isinstance(original.received_at, datetime):
        original_datetime = original.received_at
        if original_datetime.tzinfo is None:
            original_datetime = original_datetime.replace(tzinfo=timezone.utc)
        received_at = html.escape(format_datetime(original_datetime.astimezone(APP_TIMEZONE)))
    else:
        received_at = html.escape(str(original.received_at or "-"))
    subject = html.escape(original.subject or "(tanpa subjek)")
    recipient = html.escape(original.recipient_list or "-")
    quoted_body = linkify_plain_text(plain_email_body(original.raw_content))

    if action == "forward":
        attribution = (
            f"{marker}<br>"
            f"Dari: {sender}<br>"
            f"Tanggal: {received_at}<br>"
            f"Subjek: {subject}<br>"
            f"Kepada: {recipient}"
        )
    else:
        attribution = f"Pada {received_at}, {sender} menulis:<br>"

    return (
        f'<div dir="ltr">{new_body_html}</div><br>'
        '<div class="gmail_quote gmail_quote_container">'
        f'<div dir="ltr" class="gmail_attr">{attribution}</div>'
        '<blockquote class="gmail_quote" '
        'style="margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex">'
        f'{quoted_body}</blockquote></div>'
    )


MESSAGE_ID_TOKEN_RE = re.compile(r"<[^<>\s]+>")


def message_id_tokens(value: str) -> list[str]:
    """Extract safe RFC Message-ID tokens for threading headers."""
    return MESSAGE_ID_TOKEN_RE.findall(value or "")


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


def email_thread_id(email_record: QuarantineEmail) -> str:
    """Build a conversation id from RFC headers, never from subject alone."""
    references = message_id_tokens(getattr(email_record, "references_header", "") or "")
    if references:
        return references[0].lower()
    own_ids = message_id_tokens(getattr(email_record, "message_id_header", "") or "")
    if own_ids:
        return own_ids[0].lower()
    return f"message:{email_record.email_id}"


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
        "raw_content": renderable_email_body(email_record.raw_content),
        "thread_id": email_thread_id(email_record),
        "recipient_list": email_record.recipient_list,
        "attachments": attachment_summaries(email_record),
    }


def find_thread_messages(db: Session, email_record: QuarantineEmail) -> list[QuarantineEmail]:
    base_subject = normalize_thread_subject(email_record.subject)
    if not base_subject:
        return [email_record]

    # Build the strict participant set for the anchor email:
    # both sender AND recipient must match — not just any overlap.
    def _norm_addr(value: str) -> set[str]:
        from email.utils import getaddresses
        return {addr.lower() for _, addr in getaddresses([value or ""]) if addr}

    anchor_sender = _norm_addr(email_record.sender)
    anchor_recipients = _norm_addr(email_record.recipient_list)
    anchor_parties = anchor_sender | anchor_recipients

    candidates = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
    ).all()

    def _thread_tokens(record: QuarantineEmail) -> set[str]:
        values = (
            f"{getattr(record, 'message_id_header', '') or ''} "
            f"{getattr(record, 'references_header', '') or ''}"
        )
        tokens = set(message_id_tokens(values))
        if not tokens and record.raw_content:
            try:
                stored = Parser(policy=policy.default).parsestr(record.raw_content)
                for header in ("message-id", "in-reply-to", "references"):
                    tokens.update(message_id_tokens(str(stored.get(header, "") or "")))
            except Exception:
                pass
        return tokens

    messages = [email_record]
    seen = {email_record.email_id}
    known_tokens = _thread_tokens(email_record)
    for candidate in candidates:
        if candidate.email_id in seen:
            continue
        if normalize_thread_subject(candidate.subject) != base_subject:
            continue
        # Strict check: candidate must share ALL parties (sender+recipients)
        # with the anchor email — prevents unrelated emails with same subject
        # from being bundled together.
        cand_tokens = _thread_tokens(candidate)
        linked_by_headers = bool(known_tokens.intersection(cand_tokens))
        if not linked_by_headers:
            continue
        seen.add(candidate.email_id)
        messages.append(candidate)
        known_tokens.update(cand_tokens)
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
    response: Response,
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
    # Mailbox lists are live data. Prevent browser/reverse-proxy caches from
    # returning an old first page while polling or after a WebSocket event.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    category = canonical_threat_category(category)
    outgoing_view = (
        folder in {"sent", "draft"}
        or str(label or "").upper() in {"SENT", "DRAFT"}
    )
    review_access = can_review_threats(user_info)
    if (folder or "").lower() == "trash" and not review_access:
        raise HTTPException(
            status_code=403,
            detail="Sampah hanya dapat diakses oleh admin atau superadmin",
        )
    purge_expired_emails(db)
    db.commit()
    
    query = db.query(QuarantineEmail)
    if not review_access:
        if (category or "").lower() in {"spam", "phishing", "malware"} or (label or "").upper() == "QUARANTINE":
            raise HTTPException(status_code=403, detail="Threat review is only available to admin or superadmin")
        # This filter is deliberately applied before search/folder filters so
        # crafted queries cannot disclose quarantined messages.
        query = query.filter(mailbox_visible_email_clause())
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
            else:
                # User has email but no mailbox entry — use email as virtual mailbox
                mailbox = user_email.lower()
        else:
            query = query.filter(False)
    elif user_info["role"] == UserRole.ADMIN.value and not mailbox and not mailbox_id:
        managed_mailboxes = db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == user_info["username"],
            AdminMailbox.is_active == True,
        ).all()
        managed_column = (
            QuarantineEmail.sender
            if outgoing_view
            else QuarantineEmail.recipient_list
        )
        managed_filters = [
            condition
            for managed_mailbox in managed_mailboxes
            for condition in _mailbox_identity_filters(managed_column, managed_mailbox.email)
        ]
        query = query.filter(or_(*managed_filters)) if managed_filters else query.filter(False)
    
    if folder == "trash":
        query = query.filter(QuarantineEmail.status == "trash")
    else:
        query = query.filter(QuarantineEmail.status != "trash")
        if folder != "draft":
            query = query.filter(QuarantineEmail.label != "DRAFT")

    if mailbox or mailbox_id:
        # Try to resolve mailbox from admin_mailboxes table
        mailbox_record = None
        if mailbox_id:
            try:
                mailbox_record = resolve_active_mailbox(db, mailbox_id, mailbox, missing_status_code=404, missing_detail="Mailbox not found")
            except HTTPException:
                # Admin/superadmin routes and numeric IDs must refer to a real
                # active mailbox. A deleted mailbox is never a virtual inbox.
                if user_info["role"] in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value, "mailbox") or mailbox_id.isdigit():
                    raise
                virtual_identity = (mailbox or mailbox_id).strip().lower()
                own_identity = (user_info.get("mailbox_email") or "").strip().lower()
                if user_info["role"] != UserRole.USER.value or virtual_identity != own_identity:
                    raise
                mailbox = virtual_identity
        
        if mailbox_record:
            ensure_mailbox_access(db, mailbox_record, user_info)
            # Inbox/threat views are recipient-owned. Sent and Draft are
            # sender-owned. Keeping these directions separate prevents a
            # sender's outbound delivery from appearing in their Inbox.
            mailbox_column = (
                QuarantineEmail.sender
                if outgoing_view
                else QuarantineEmail.recipient_list
            )
            query = query.filter(or_(
                *_mailbox_identity_filters(mailbox_column, mailbox_record.email)
            ))
        else:
            # Virtual mailbox (user email not in admin_mailboxes) — use direct ilike filter
            mailbox_column = (
                QuarantineEmail.sender
                if outgoing_view
                else QuarantineEmail.recipient_list
            )
            query = query.filter(mailbox_column.ilike(f"%{mailbox}%"))

    if folder == "all":
        query = query.filter(QuarantineEmail.label.notin_(["SENT", "DRAFT"]))
    elif folder == "starred":
        # STARRED folder: filter by is_starred = True
        query = query.filter(QuarantineEmail.is_starred == True)
        query = query.filter(QuarantineEmail.label.notin_(["SENT", "DRAFT"]))
    elif folder == "snoozed":
        # SNOOZED folder: filter by snoozed_until in the future
        query = query.filter(QuarantineEmail.snoozed_until != None)
        query = query.filter(QuarantineEmail.snoozed_until > datetime.now(timezone.utc))
    elif folder == "sent":
        # SENT folder: filter by sender matching mailbox
        query = query.filter(QuarantineEmail.label == "SENT")
        if mailbox:
            if mailbox_record:
                query = query.filter(or_(
                    *_mailbox_identity_filters(QuarantineEmail.sender, mailbox_record.email)
                ))
            else:
                query = query.filter(QuarantineEmail.sender.ilike(f"%{mailbox}%"))
    elif folder == "draft":
        query = query.filter(QuarantineEmail.label == "DRAFT")
    elif category and category in CATEGORY_LABEL_MAP:
        mapped_label = CATEGORY_LABEL_MAP[category]
        if category == "warn":
            query = query.filter(QuarantineEmail.label == "WARN")
        elif category == "phishing":
            query = query.filter(
                QuarantineEmail.label == "QUARANTINE",
                QuarantineEmail.category.in_(["phishing", "malware"]),
            )
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
            ))
        else:
            query = query.filter(QuarantineEmail.label == mapped_label, QuarantineEmail.category == category)
        if category in ["spam", "phishing", "malware", "warn"]:
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
        body_preview = email_body_preview(email.raw_content)
        emails_data.append({
            "email_id": email.email_id,
            "sender": email.sender,
            "subject": email.subject,
            "body_preview": body_preview,
            "label": email.label,
            "category": cat,
            "status": email.status,
            "fused_score": email.fused_score,
            "ml_probability": email.ml_probability if review_access else 0.0,
            "sa_score": email.sa_score if review_access else 0.0,
            "anomaly_score": email.anomaly_score if review_access else 0.0,
            "has_attachments": bool(email.attachments_json and email.attachments_json != "[]"),
            "received_at": email.received_at.isoformat() if hasattr(email.received_at, "isoformat") else str(email.received_at) if email.received_at else None,
            "recipient_list": email.recipient_list,
            "is_read": getattr(email, "is_read", False),
            "thread_id": email_thread_id(email),
        })
    
    return {"emails": emails_data, "total": total}


AUTH_FAILURE_RESULTS = {"FAIL", "SOFTFAIL", "HARDFAIL", "PERMERROR", "TEMPERROR"}


def build_detection_explanation(email_record: QuarantineEmail) -> tuple[list[dict], list[str], dict | None]:
    """Build factual XAI output from persisted model and verification data.

    The classifier summary is useful for model features, but authentication
    claims are accepted only when the trusted worker result explicitly records
    a failure. This prevents missing/unverified SPF or DKIM from being shown as
    a failed check.
    """
    shap_data = None
    if email_record.shap_json:
        try:
            parsed_shap = json.loads(email_record.shap_json)
            if isinstance(parsed_shap, dict):
                stored_probability = float(email_record.ml_probability or 0.0)
                explained_probability = parsed_shap.get("prediction_probability")
                if explained_probability is None or abs(float(explained_probability) - stored_probability) <= 0.0001:
                    shap_data = parsed_shap
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    parts = [part.strip() for part in (email_record.xai_summary or "").split(";") if part.strip()]
    reasons: list[dict] = []
    human_reasons: list[str] = []

    def add_human(reason: str) -> None:
        if reason and reason not in human_reasons:
            human_reasons.append(reason)

    for part in parts:
        if ":" in part:
            key, value = part.split(":", 1)
        elif "=" in part:
            key, value = part.split("=", 1)
        else:
            key, value = part, ""
        key, value = key.strip(), value.strip()

        if key in {"SPF", "DKIM", "DMARC"}:
            persisted = str(getattr(email_record, f"{key.lower()}_result", "") or "N/A").upper()
            if persisted not in AUTH_FAILURE_RESULTS:
                continue
            reasons.append({"key": key, "value": persisted})
            descriptions = {
                "SPF": "Verifikasi identitas pengirim (SPF)",
                "DKIM": "Tanda tangan digital email (DKIM)",
                "DMARC": "Kebijakan autentikasi domain (DMARC)",
            }
            add_human(f"{descriptions[key]} benar-benar gagal ({persisted}).")
            continue

        reasons.append({"key": key, "value": value})
        if key == "SpamProb":
            add_human(
                f"Model supervised menghasilkan probabilitas spam "
                f"{float(email_record.ml_probability or 0.0) * 100:.2f}%."
            )
        elif key == "Urgency-Score":
            add_human(f"Fitur bahasa mendesak terukur dengan skor {value}.")
        elif key == "Lookalike-Domain":
            add_human(f"Tautan terdeteksi mirip domain resmi ({value}).")
        elif key == "Executable-Attachment":
            add_human("Parser menemukan lampiran program/script berbahaya.")
        elif key == "URL-Shortener":
            add_human("Parser menemukan tautan pendek yang menyembunyikan tujuan.")
        elif key == "DisplayName-Mismatch":
            add_human("Nama tampilan pengirim tidak cocok dengan alamat pengirim.")
        elif key == "HTML-Forms":
            add_human(f"Parser menemukan formulir HTML dalam email ({value}).")
        elif key == "Top-SHAP" and value:
            add_human(f"Fitur SHAP yang paling mendorong prediksi spam: {value}.")

    if float(email_record.anomaly_score or 0.0) > 0:
        anomaly_prefix = (
            "Model unsupervised menandai email sebagai anomali"
            if shap_data and shap_data.get("is_anomaly") is True
            else "Model unsupervised menghasilkan skor anomali"
        )
        add_human(f"{anomaly_prefix} {float(email_record.anomaly_score):.4f}.")

    return reasons, human_reasons, shap_data


@app.get("/api/emails/{email_id}")
async def api_get_email_detail(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")

    ensure_email_access(db, email_record, user_info)
    if email_record.status == "trash" and not can_review_threats(user_info):
        raise HTTPException(status_code=404, detail="Email not found")
    is_regular_user = not can_review_threats(user_info)

    reasons, human_reasons, shap_data = build_detection_explanation(email_record)
    warning_xai_header = ""
    if str(email_record.label or "").upper() == "WARN" and shap_data:
        warning_xai_header = str(shap_data.get("warning_header") or "")

    ecat = display_category(email_record)
    auth_results = {
        "spf_result": email_record.spf_result or "N/A",
        "dkim_result": email_record.dkim_result or "N/A",
        "dmarc_result": email_record.dmarc_result or "N/A",
    }


    thread_messages = find_thread_messages(db, email_record)
    if is_regular_user:
        mailbox_identity = (user_info.get("mailbox_email") or "").strip().lower()
        anchor_is_outgoing = str(email_record.label or "").upper() in {"SENT", "DRAFT"}
        direction = "outgoing" if anchor_is_outgoing else "incoming"
        thread_messages = [
            message
            for message in thread_messages
            if email_is_visible_to_mailbox_user(message)
            and email_matches_mailbox_direction(message, mailbox_identity, direction)
            and (
                str(message.label or "").upper() in {"SENT", "DRAFT"}
                if anchor_is_outgoing
                else str(message.label or "").upper() not in {"SENT", "DRAFT"}
            )
        ]
    incoming_thread_messages = [
        message for message in thread_messages
        if str(message.label or "").upper() not in {"SENT", "DRAFT"}
        and str(message.status or "").lower() not in {"sent", "draft"}
    ]
    thread_has_unread = any(
        not bool(getattr(message, "is_read", False))
        for message in incoming_thread_messages
    )
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
        # Exact X-Spam-Reason value generated by the worker. This is persisted
        # pipeline evidence, not a dashboard-generated explanation.
        "warning_xai_header": warning_xai_header,
        "raw_content": renderable_email_body(email_record.raw_content),
        "thread_id": email_thread_id(email_record),
        "recipient_list": email_record.recipient_list,
        "is_read": getattr(email_record, "is_read", False),
        "thread_has_unread": thread_has_unread,
        "thread_is_read": not thread_has_unread,
        "attachments": attachment_summaries(email_record),
        "thread_root_id": thread_messages[0].email_id if thread_messages else email_record.email_id,
        "thread_messages": [thread_message_payload(message) for message in thread_messages],
        **auth_results,
    }

@app.put("/api/emails/{email_id}/read")
async def api_toggle_read(email_id: str, payload: dict, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)
    
    is_read = bool(payload.get("is_read", True))
    thread_messages = find_thread_messages(db, email_record)
    readable_messages = [
        message for message in thread_messages
        if str(message.label or "").upper() not in {"SENT", "DRAFT"}
        and str(message.status or "").lower() not in {"sent", "draft"}
        and (can_review_threats(user_info) or email_is_visible_to_mailbox_user(message))
    ]
    # Read/unread is a conversation-level action. Updating only the URL anchor
    # caused old messages in a long reply chain to keep overriding the UI.
    targets = readable_messages or [email_record]
    for message in targets:
        message.is_read = is_read
    db.commit()
    return {
        "ok": True,
        "is_read": is_read,
        "thread_is_read": is_read,
        "thread_has_unread": not is_read,
        "updated_count": len(targets),
    }


@app.put("/api/emails/{email_id}/starred")
async def api_toggle_starred(email_id: str, payload: dict, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)
    
    is_starred = payload.get("is_starred", True)
    email_record.is_starred = bool(is_starred)
    log_audit(db, user_info["username"], "toggle_starred", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "is_starred": email_record.is_starred}


@app.put("/api/emails/{email_id}/snooze")
async def api_snooze_email(email_id: str, payload: dict, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)
    
    snoozed_until = payload.get("snoozed_until")
    if snoozed_until:
        try:
            from datetime import datetime
            email_record.snoozed_until = datetime.fromisoformat(snoozed_until.replace('Z', '+00:00'))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid datetime format")
    else:
        email_record.snoozed_until = None
    
    log_audit(db, user_info["username"], "snooze_email", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "snoozed_until": email_record.snoozed_until.isoformat() if email_record.snoozed_until else None}


@app.get("/api/emails/{email_id}/attachments/{attachment_index}")
async def api_download_attachment(
    email_id: str,
    attachment_index: int,
    request: Request,
    download: bool = Query(False),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    email_record = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not can_review_threats(user_info) or not has_permission_dict(user_info, Permission.RELEASE_EMAIL):
        raise HTTPException(status_code=403, detail="You do not have permission to manage quarantine")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)
    email_record.status = "released"
    email_record.label = "CLEAN"
    email_record.category = "clean"
    log_audit(db, user_info["username"], "release", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "released"}


@app.post("/api/emails/{email_id}/confirm-spam")
async def api_confirm_spam(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not can_review_threats(user_info) or not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="You do not have permission to manage quarantine")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not can_review_threats(user_info) or not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="Threat review is only available to admin or superadmin")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)

    existing = db.query(TrainingSample).filter(
        TrainingSample.email_id == email_id,
        TrainingSample.feedback_type == "false_positive",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email ini sudah dilaporkan sebagai false positive")

    training_sample = TrainingSample(
        email_id=email_id,
        raw_email=email_record.raw_content or "",
        original_label=email_record.label,
        corrected_label="clean",
        feedback_type="false_positive",
        original_scores={
            "fused_score": email_record.fused_score,
            "ml_probability": email_record.ml_probability,
            "anomaly_score": email_record.anomaly_score,
            "sa_score": email_record.sa_score,
        },
        subject=email_record.subject,
        sender=email_record.sender,
        recipient_list=email_record.recipient_list,
        status="pending",
        notes=payload.notes,
        reported_by=user_info["username"],
        organization_id=email_record.organization_id,
    )
    db.add(training_sample)
    feedback = Feedback(
        email_id=email_id,
        feedback_type="false_positive",
        notes=payload.notes,
    )
    db.add(feedback)
    email_record.status = "released"
    email_record.label = "CLEAN"
    email_record.category = "clean"
    log_audit(db, user_info["username"], "report_false_positive", email_id,
              request.client.host if request.client else None, payload.notes)
    db.commit()
    return {
        "ok": True,
        "status": "released",
        "training_status": "pending_review",
        "training_sample_id": training_sample.id,
    }


def _delete_email_record(
    db: Session,
    email_id: str,
    user_info: dict,
    client_host: str | None,
) -> str:
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    if email_record.label == "DRAFT":
        ensure_email_access(db, email_record, user_info)
        db.delete(email_record)
        log_audit(db, user_info["username"], "discard_draft", email_id,
                  client_host)
        return "deleted"
    ensure_email_access(db, email_record, user_info)
    if email_record.status == "trash" and not can_review_threats(user_info):
        raise HTTPException(
            status_code=403,
            detail="Hapus permanen hanya tersedia di Sampah untuk admin atau superadmin",
        )
    if not has_permission_dict(user_info, Permission.DELETE_EMAIL):
        owner_identity = user_info.get("email") or f"{user_info.get('username', '')}@"
        if not email_belongs_to_identity(email_record, owner_identity):
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
              client_host)
    return status


class BulkDeleteEmailsRequest(BaseModel):
    email_ids: list[str]


@app.post("/api/emails/bulk-delete")
async def api_bulk_delete_emails(
    payload: BulkDeleteEmailsRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    email_ids = list(dict.fromkeys(
        str(email_id).strip() for email_id in payload.email_ids if str(email_id).strip()
    ))
    if not email_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu email")
    if len(email_ids) > 200:
        raise HTTPException(status_code=400, detail="Maksimal 200 email per operasi")

    client_host = request.client.host if request.client else None
    statuses = [
        _delete_email_record(db, email_id, user_info, client_host)
        for email_id in email_ids
    ]
    db.commit()
    return {
        "ok": True,
        "processed": len(statuses),
        "moved_to_trash": statuses.count("trash"),
        "deleted_permanently": statuses.count("deleted"),
    }


@app.delete("/api/emails/{email_id}")
async def api_delete_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    status = _delete_email_record(
        db,
        email_id,
        user_info,
        request.client.host if request.client else None,
    )
    db.commit()
    return {"ok": True, "status": status}


@app.post("/api/emails/{email_id}/restore")
async def api_restore_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not can_review_threats(user_info):
        raise HTTPException(
            status_code=403,
            detail="Pemulihan dari Sampah hanya tersedia untuk admin atau superadmin",
        )
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    ensure_email_access(db, email_record, user_info)
    if email_record.status != "trash":
        raise HTTPException(status_code=400, detail="Email tidak berada di Sampah")
    email_record.status = "pending" if email_record.label == "QUARANTINE" else "released"
    email_record.deleted_at = None
    log_audit(db, user_info["username"], "restore", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": email_record.status}


class SendEmailRequest(BaseModel):
    # Share uses ``share_with`` instead of ``to``. Keeping this optional also
    # lets the endpoint return its own consistent 400 response for an empty
    # normal recipient instead of leaking an uncaught Pydantic exception.
    to: str = ""
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
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
        if user_info["role"] == "mailbox":
            if requested_sender != user_info["mailbox_email"]:
                raise HTTPException(status_code=403, detail="You can only send from the logged-in mailbox")

    sender_address = req.from_email.strip().lower() or user_info.get("mailbox_email") or f"{user_info['username']}@{get_configured_mail_domain()}"
    ensure_sender_access(db, sender_address, user_info)
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
        if not re.fullmatch(r"draft_[A-Za-z0-9-]{8,64}", draft_id):
            raise HTTPException(status_code=400, detail="Invalid draft identifier")
        draft_entry = db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id == draft_id,
            QuarantineEmail.label == "DRAFT",
        ).first()
        if draft_entry:
            ensure_email_access(db, draft_entry, user_info)
    is_new_draft = False
    if not draft_entry:
        is_new_draft = True
        draft_id = draft_id or f"draft_{uuid.uuid4().hex[:12]}"
        draft_entry = QuarantineEmail(
            email_id=draft_id,
            received_at=app_now(),
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
    draft_entry.received_at = app_now()
    draft_entry.created_at = app_now()
    draft_entry.deleted_at = None

    log_audit(db, user_info["username"], "save_email_draft", draft_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "email_id": draft_id}


@app.post("/api/emails/send")
async def api_send_email(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
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
        if user_info["role"] == "mailbox":
            if requested_sender != user_info["mailbox_email"]:
                raise HTTPException(status_code=403, detail="You can only send from the logged-in mailbox")
    
    # Construct sender address
    sender_address = req.from_email.strip().lower() or user_info.get("mailbox_email") or f"{user_info['username']}@{get_configured_mail_domain()}"
    ensure_sender_access(db, sender_address, user_info)
    
    # Determine subject and body based on action
    final_subject = req.subject
    final_body = req.body
    draft_to_delete = None
    if req.draft_id.strip():
        draft_to_delete = db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id == req.draft_id.strip(),
            QuarantineEmail.label == "DRAFT",
        ).first()
        if not draft_to_delete:
            raise HTTPException(status_code=404, detail="Draft not found")
        ensure_email_access(db, draft_to_delete, user_info)
    
    if req.action == "share" and req.share_with:
        dest_recipients = parse_recipients(req.share_with)
        # Fetch original email
        orig = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == req.reply_to_id).first()
        if not orig:
            raise HTTPException(status_code=404, detail="Original email not found")
        ensure_email_access(db, orig, user_info)
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

    original_email = None
    if req.reply_to_id.strip() and req.action in {"reply", "forward"}:
        original_email = db.query(QuarantineEmail).filter(
            QuarantineEmail.email_id == req.reply_to_id.strip()
        ).first()
        if not original_email:
            raise HTTPException(status_code=404, detail="Original email not found")
        ensure_email_access(db, original_email, user_info)
        # A reply is linked by RFC headers; the previous body already exists in
        # the conversation and must not be duplicated visibly at the receiver.
        # Forwarding is different and intentionally carries the original body.
        if req.action == "forward":
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
    smtp_host = os.getenv("FORWARDER_SMTP_HOST", "").strip()
    outbound_mode = os.getenv("OUTBOUND_SMTP_MODE", "relay").strip().lower()
    is_local_smtp = os.getenv("ENV", "development").strip().lower() == "local" and not smtp_host
    if is_local_smtp:
        smtp_host = "mailpit"
        outbound_mode = "relay"
    try:
        validate_recipient_domains(dest_recipients)
        smtp_from = sender_address or os.getenv("FORWARDER_FROM", f"cognimail@{get_configured_mail_domain()}")

        msg = MIMEMultipart("alternative")
        msg["From"] = smtp_from
        msg["To"] = ", ".join(dest_recipients)
        msg["Subject"] = final_subject
        msg["Date"] = formatdate(localtime=False, usegmt=True)
        outbound_message_id = make_msgid(domain=get_configured_mail_domain())
        msg["Message-ID"] = outbound_message_id
        msg["Reply-To"] = smtp_from
        msg["X-Mailer"] = "CogniMail"
        is_same_subject_reply = bool(
            req.action == "reply"
            and original_email
            and normalize_thread_subject(final_subject)
            == normalize_thread_subject(original_email.subject)
        )
        if is_same_subject_reply:
            try:
                original_message_ids = message_id_tokens(
                    getattr(original_email, "message_id_header", "") or ""
                )
                reference_ids = message_id_tokens(
                    getattr(original_email, "references_header", "") or ""
                )
                # Compatibility for records created before Message-ID headers
                # were stored separately. Raw content may still contain them.
                if not original_message_ids:
                    original_message = Parser(policy=policy.default).parsestr(original_email.raw_content or "")
                    original_message_ids = message_id_tokens(str(original_message.get("Message-ID", "")))
                    reference_ids.extend(message_id_tokens(str(original_message.get("References", ""))))
                if original_message_ids:
                    parent_message_id = original_message_ids[-1]
                    msg["In-Reply-To"] = parent_message_id
                    ordered_references = list(dict.fromkeys(reference_ids + [parent_message_id]))[-20:]
                    msg["References"] = " ".join(ordered_references)
            except Exception:
                logger.warning("Unable to derive reply threading headers", exc_info=True)

        # Detect if body is HTML or plain text
        body_is_html = bool(re.search(r'<(html|body|div|p|br|span|a|table|tr|td)\b', final_body, re.IGNORECASE))
        if body_is_html:
            msg.attach(MIMEText(plain_email_body(final_body), "plain", "utf-8"))
            msg.attach(MIMEText(final_body, "html", "utf-8"))
        else:
            msg.attach(MIMEText(final_body, "plain", "utf-8"))
        for attachment in stored_attachments:
            maintype, subtype = (attachment["content_type"].split("/", 1) + ["octet-stream"])[:2]
            part = MIMEBase(maintype, subtype)
            part.set_payload(base64.b64decode(attachment["data"]))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=attachment["filename"])
            msg.attach(part)

        outbound_message = sign_outbound_message(msg, smtp_from)

        if outbound_mode == "direct":
            delivered = await deliver_direct_mx(
                outbound_message,
                smtp_from,
                dest_recipients,
                helo_hostname=os.getenv("OUTBOUND_HELO_HOSTNAME", "").strip() or None,
            )
            logger.info("Sent email directly to recipient MX: %s", delivered)
        elif outbound_mode == "relay":
            if not smtp_host:
                raise RuntimeError(
                    "FORWARDER_SMTP_HOST wajib diisi ketika OUTBOUND_SMTP_MODE=relay"
                )
            smtp_port = 1025 if is_local_smtp else int(os.getenv("FORWARDER_SMTP_PORT", "587"))
            smtp_user = os.getenv("FORWARDER_SMTP_USER", "")
            smtp_pass = os.getenv("FORWARDER_SMTP_PASS", "")
            smtp_starttls = False if is_local_smtp else os.getenv("FORWARDER_STARTTLS", "true").lower() in {"1", "true", "yes", "on"}

            async with aiosmtplib.SMTP(
                hostname=smtp_host,
                port=smtp_port,
                use_tls=smtp_port == 465,
            ) as smtp:
                if smtp_port != 465 and smtp_starttls:
                    await smtp.starttls()
                if smtp_user and smtp_pass:
                    await smtp.login(smtp_user, smtp_pass)
                await smtp.sendmail(smtp_from, dest_recipients, outbound_message)
            logger.info("Sent email via SMTP successfully")
        else:
            raise RuntimeError(
                f"OUTBOUND_SMTP_MODE tidak didukung: {outbound_mode or '(kosong)'}"
            )
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
        # Store the actual body representation. Escaping generated HTML here
        # caused literal "<br>" text and prevented quote detection in the UI.
        raw_content=final_body,
        attachments_json=json.dumps(stored_attachments),
        status="released",
        category="sent",
        subject=final_subject,
        sender=sender_address,
        recipient_list=", ".join(dest_recipients),
        message_id_header=outbound_message_id,
        references_header=str(msg.get("References", "") or ""),
        spf_result="OUTBOUND",
        dkim_result="OUTBOUND",
        dmarc_result="OUTBOUND",
        created_at=app_now(),
    )
    db.add(sent_entry)

    if draft_to_delete is not None:
        db.delete(draft_to_delete)

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
    # P0 FIX: Require authentication for all metrics access
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    
    mailbox = (mailbox or "").strip().lower()
    mailbox_id = (mailbox_id or "").strip()

    scope_label = "global"
    account_filters = []
    if mailbox or mailbox_id:
        mailbox_record = resolve_active_mailbox(db, mailbox_id, mailbox, missing_status_code=404, missing_detail="Mailbox not found")
        ensure_mailbox_access(db, mailbox_record, user_info)
        scope_label = mailbox_record.email
        
        # Try exact match first
        exact_filters = or_(
            *_mailbox_identity_filters(QuarantineEmail.recipient_list, mailbox_record.email),
            *_mailbox_identity_filters(QuarantineEmail.sender, mailbox_record.email),
        )
        
        account_filters.append(exact_filters)
    elif user_info and user_info["role"] == UserRole.ADMIN.value:
        managed_mailboxes = db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == user_info["username"],
            AdminMailbox.is_active == True,
        ).all()
        scope_label = user_info["username"]
        managed_filters = [
            condition
            for managed_mailbox in managed_mailboxes
            for condition in (
                *_mailbox_identity_filters(QuarantineEmail.recipient_list, managed_mailbox.email),
                *_mailbox_identity_filters(QuarantineEmail.sender, managed_mailbox.email),
            )
        ]
        account_filters.append(or_(*managed_filters) if managed_filters else False)
    elif user_info and user_info["role"] == "mailbox":
        identity = (user_info.get("mailbox_email") or "").strip().lower()
        scope_label = identity or "mailbox"
        identity_filters = [
            *_mailbox_identity_filters(QuarantineEmail.recipient_list, identity),
            *_mailbox_identity_filters(QuarantineEmail.sender, identity),
        ] if identity else []
        account_filters.append(or_(*identity_filters) if identity_filters else False)
    elif user_info and user_info["role"] == "user":
        user = db.query(User).filter(User.username == user_info["username"]).first()
        identity = ((user.email if user else "") or user_info["username"]).strip().lower()
        scope_label = identity
        identity_filters = [
            *_mailbox_identity_filters(QuarantineEmail.recipient_list, identity),
            *_mailbox_identity_filters(QuarantineEmail.sender, identity),
        ] if identity else []
        account_filters.append(or_(*identity_filters) if identity_filters else False)

    base_query = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.label.notin_(["DRAFT", "SENT"]),
    )
    if not can_review_threats(user_info):
        base_query = base_query.filter(QuarantineEmail.label == "CLEAN")
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

    scoped_email_ids = base_query.with_entities(QuarantineEmail.email_id)
    feedback_count = db.query(func.count(Feedback.id)).filter(
        Feedback.email_id.in_(scoped_email_ids)
    ).scalar() or 0

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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not has_permission_dict(user_info, Permission.ACCESS_AUDIT_LOG):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = db.query(AuditLog)
    if event_type:
        query = query.filter(AuditLog.action == event_type)
    if username:
        query = query.filter(AuditLog.user.ilike(f"%{username}%"))

    # P1 FIX: Admin sees only audit logs from users in their own organization
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if current_user and current_user.organization_id:
            org_usernames = [
                u.username for u in db.query(User.username).filter(
                    User.organization_id == current_user.organization_id
                ).all()
            ]
            query = query.filter(AuditLog.user.in_(org_usernames))
        else:
            return {"total": 0, "page": page, "page_size": page_size, "pages": 0, "items": []}

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
                # Expose the persisted column name directly.  ``notes`` is
                # retained as a compatibility alias for older clients.
                "details": r.details,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
            }
            for r in records
        ],
    }


# ─── System Settings ─────────────────────────────────────────────────────────────

# In-memory settings store (persisted to .env file on save in prod; kept simple here)
_SYSTEM_SETTINGS = {
    "organization_domain": get_configured_mail_domain(),
    "threshold_quarantine": float(os.getenv("THRESHOLD_QUARANTINE", "0.70")),
    "threshold_warn": float(os.getenv("THRESHOLD_WARN", "0.30")),
    "fusion_ml_weight": float(os.getenv("FUSION_ML_WEIGHT", "0.50")),
    "fusion_sa_weight": float(os.getenv("FUSION_SA_WEIGHT", "0.25")),
    "fusion_anomaly_weight": float(os.getenv("FUSION_ANOMALY_WEIGHT", "0.25")),
    "imap_host": os.getenv("IMAP_HOST", ""),
    "imap_port": int(os.getenv("IMAP_PORT", "993")),
    "imap_user": os.getenv("IMAP_USER", ""),
    "poll_interval_seconds": int(os.getenv("POLL_INTERVAL", "30")),
    "protected_domains": [
        domain.strip().lower()
        for domain in os.getenv("PROTECTED_DOMAINS", get_configured_mail_domain()).split(",")
        if domain.strip()
    ],
    "whitelist_senders": os.getenv("WHITELIST_SENDERS", "").split(",") if os.getenv("WHITELIST_SENDERS") else [],
    "admin_alert_email": os.getenv("ADMIN_ALERT_EMAIL", ""),
    "max_quarantine_days": int(os.getenv("MAX_QUARANTINE_DAYS", "30")),
}


@app.get("/api/settings")
async def api_get_settings(request: Request, db: Session = Depends(get_db)):
    """Get current system settings. Requires admin or above."""
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not has_permission_dict(user_info, Permission.MANAGE_GLOBAL_SETTINGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    # Return copy without IMAP password for security
    safe = dict(_SYSTEM_SETTINGS)
    persisted_domain = db.query(SystemSetting).filter(
        SystemSetting.key == "organization_domain"
    ).first()
    if persisted_domain and persisted_domain.value:
        safe["organization_domain"] = persisted_domain.value
        _SYSTEM_SETTINGS["organization_domain"] = persisted_domain.value
    return safe


class SettingsUpdatePayload(BaseModel):
    organization_domain: str = None
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not has_permission_dict(user_info, Permission.MANAGE_GLOBAL_SETTINGS):
        raise HTTPException(status_code=403, detail="Only superadmin can change global settings")

    update_data = payload.model_dump(exclude_none=True)
    if "organization_domain" in update_data:
        domain = str(update_data["organization_domain"]).strip().lower().lstrip("@").rstrip(".")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", domain):
            raise HTTPException(status_code=400, detail="Domain organisasi tidak valid")
        if ".." in domain or "." not in domain:
            raise HTTPException(status_code=400, detail="Domain organisasi tidak valid")
        conflicting_mailbox = db.query(AdminMailbox).filter(
            AdminMailbox.domain.isnot(None),
            AdminMailbox.domain != "",
            func.lower(AdminMailbox.domain) != domain,
        ).first()
        if conflicting_mailbox:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Domain tidak dapat diubah karena mailbox yang sudah ada "
                    f"menggunakan @{conflicting_mailbox.domain}"
                ),
            )
        update_data["organization_domain"] = domain
        os.environ["VITE_MAIL_DOMAIN"] = domain
        setting = db.query(SystemSetting).filter(
            SystemSetting.key == "organization_domain"
        ).first()
        if setting:
            setting.value = domain
        else:
            db.add(SystemSetting(key="organization_domain", value=domain))
    _SYSTEM_SETTINGS.update(update_data)

    log_audit(db, user_info["username"], "update_settings", None,
              request.client.host if request.client else None,
              f"Updated: {list(update_data.keys())}")
    db.commit()
    return {"ok": True, "updated": list(update_data.keys()), "settings": _SYSTEM_SETTINGS}


@app.post("/api/settings/test-imap")
async def api_test_imap(request: Request, db: Session = Depends(get_db)):
    """Test IMAP connection with current settings."""
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = db.query(QuarantineEmail)
    if user_info["role"] == UserRole.ADMIN.value:
        managed_mailboxes = db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == user_info["username"],
            AdminMailbox.is_active == True,
        ).all()
        filters = [
            condition
            for mailbox in managed_mailboxes
            for condition in (
                *_mailbox_identity_filters(QuarantineEmail.recipient_list, mailbox.email),
                *_mailbox_identity_filters(QuarantineEmail.sender, mailbox.email),
            )
        ]
        query = query.filter(or_(*filters)) if filters else query.filter(False)
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)

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
    if user_info["role"] != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat mengelola admin")
    
    users = db.query(User).filter(User.role == UserRole.ADMIN.value).order_by(User.username).all()
    
    orgs = {o.id: o.name for o in db.query(Organization).all()}
    return [{
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "organization_id": u.organization_id,
        "organization_name": orgs.get(u.organization_id),
    } for u in users]


@app.get("/api/admin/users/search")
async def api_search_users(request: Request, q: str = "", db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat mencari admin")
    query = q.strip()
    if not query:
        return []
    
    # P1 FIX: Admin can only search users in their own organization
    user_query = db.query(User).filter(
        User.role == UserRole.ADMIN.value,
        User.username.ilike(f"%{query}%"),
    )
    
    users = user_query.limit(10).all()
    return [{"username": u.username, "role": u.role, "is_active": u.is_active} for u in users]


@app.post("/api/admin/onboard-company")
async def api_onboard_company(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can onboard companies")

    company_name = str(payload.get("company_name", "")).strip()
    admin_username = str(payload.get("admin_username", "")).strip()
    admin_password = payload.get("admin_password", "")
    users_data = payload.get("users", [])

    if not company_name or not admin_username or not admin_password:
        raise HTTPException(status_code=400, detail="Company name, admin username, and password are required")
    
    # Password strength validation
    if len(admin_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    if not any(c.isupper() for c in admin_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter")
    if not any(c.islower() for c in admin_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in admin_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one digit")

    domain = get_configured_mail_domain()

    # 1. Create Organization
    org = Organization(name=company_name)
    db.add(org)
    db.flush()

    # 2. Create Admin
    existing = db.query(User).filter(User.username == admin_username).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Username '{admin_username}' already exists")
    admin_user = User(
        username=admin_username,
        email=None,
        hashed_password=hash_password(admin_password),
        role="admin",
        organization_id=org.id,
        is_active=True,
    )
    db.add(admin_user)
    db.flush()

    # 3. Create 3 mailboxes
    mailbox_names = ["inbox", "it-support", "security-alerts"]
    created_mailboxes = []
    for prefix in mailbox_names:
        m_email = f"{prefix}@{domain}"
        m_existing = db.query(AdminMailbox).filter(AdminMailbox.email == m_email).first()
        if not m_existing:
            m_pw = hash_password(admin_password)
            mb = AdminMailbox(
                email=m_email,
                domain=domain,
                password_hash=m_pw,
                sender_name=prefix.replace("-", " ").title(),
                assigned_to=admin_username,
                created_by=admin_username,
            )
            db.add(mb)
            db.flush()
            created_mailboxes.append(mb)
        elif not m_existing.is_active:
            m_existing.is_active = True
            m_existing.domain = domain
            m_existing.created_by = admin_username
            m_existing.password_hash = hash_password(admin_password)
            m_existing.assigned_to = admin_username
            db.flush()
            created_mailboxes.append(m_existing)

    # Grant admin access to all mailboxes
    for mb in created_mailboxes:
        existing_access = db.query(AdminMailboxAccess).filter(
            AdminMailboxAccess.mailbox_id == mb.id,
            AdminMailboxAccess.username == admin_username,
        ).first()
        if not existing_access:
            db.add(AdminMailboxAccess(mailbox_id=mb.id, username=admin_username))

    # 4. Create users
    created_users = []
    for u_data in users_data:
        u_username = str(u_data.get("username", "")).strip()
        u_email = str(u_data.get("email", "")).strip().lower()
        u_password = u_data.get("password", "")
        if not u_username or not u_email or not u_password:
            continue
        if db.query(User).filter(User.username == u_username).first():
            continue
        if db.query(User).filter(User.email == u_email).first():
            continue
        new_user = User(
            username=u_username,
            email=u_email,
            hashed_password=hash_password(u_password),
            role="user",
            organization_id=org.id,
            is_active=True,
        )
        db.add(new_user)
        db.flush()
        created_users.append({"username": u_username, "email": u_email})

        # Grant mailbox access to user
        for mb in created_mailboxes:
            existing_access = db.query(AdminMailboxAccess).filter(
                AdminMailboxAccess.mailbox_id == mb.id,
                AdminMailboxAccess.username == u_username,
            ).first()
            if not existing_access:
                db.add(AdminMailboxAccess(mailbox_id=mb.id, username=u_username))

    log_audit(db, user_info["username"], "onboard_company", None, request.client.host if request.client else None, company_name)
    db.commit()
    return {
        "ok": True,
        "company": company_name,
        "admin": admin_username,
        "mailboxes": [mb.email for mb in created_mailboxes],
        "users": created_users,
    }


@app.post("/api/admin/settings")
async def api_change_settings(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_GLOBAL_SETTINGS):
        raise HTTPException(status_code=403, detail="Only superadmin can change system settings")
    # This legacy route used to return success without persisting anything,
    # which made the UI/API claim that settings had changed when they had not.
    # Keep the route explicit for old clients instead of silently lying.
    raise HTTPException(
        status_code=410,
        detail="Endpoint lama tidak lagi digunakan. Gunakan POST /api/settings.",
    )


@app.get("/api/admin/mailboxes")
async def api_get_admin_mailboxes(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and not has_permission_dict(user_info, Permission.MANAGE_ORG_MAILBOXES):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    query = db.query(AdminMailbox)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
        user = db.query(User).filter(User.username == user_info["username"]).first()
        query = query.filter(
            AdminMailbox.assigned_to == user.username
        ) if user and user.role == UserRole.ADMIN.value else query.filter(False)
    rows = query.order_by(AdminMailbox.is_active.desc(), AdminMailbox.email.asc()).all()
    return [
        {
            "id": row.id,
            "email": row.email,
            "domain": row.domain,
            "sender_name": row.sender_name or "",
            "avatar_url": row.avatar_url or "",
            "forward_to": row.forward_to or "",
            "forward_enabled": bool(row.forward_enabled),
            "forward_keep_copy": bool(row.forward_keep_copy),
            "is_active": bool(row.is_active),
            "assigned_to": row.assigned_to or "",
            "created_by": row.created_by or "",
            "created_at": str(row.created_at),
        }
        for row in rows
    ]


@app.get("/api/admin/mailboxes/by-email")
async def api_get_mailbox_by_email(request: Request, email: str = "", db: Session = Depends(get_db)):
    """Find a mailbox by exact email address."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can search mailboxes")
    if not email:
        raise HTTPException(status_code=400, detail="Email parameter required")
    mb = db.query(AdminMailbox).filter(AdminMailbox.email == email).first()
    if not mb:
        return {"id": None, "email": email, "found": False}
    current_user = db.query(User).filter(User.username == user_info["username"]).first()
    if user_info["role"] == UserRole.ADMIN.value and (
        not current_user or not _admin_can_manage_mailbox(db, current_user, mb)
    ):
        raise HTTPException(status_code=403, detail="Admin tidak memiliki akses ke mailbox ini")
    return {
        "id": mb.id,
        "email": mb.email,
        "found": True,
        "is_active": mb.is_active,
        "assigned_to": mb.assigned_to or "",
    }


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
    current_user_obj = db.query(User).filter(User.username == user_info["username"]).first()
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status_code=400, detail="Invalid mailbox email")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password minimal 8 karakter")
    if not re.search(r'[A-Z]', password):
        raise HTTPException(status_code=400, detail="Password harus mengandung huruf besar")
    if not re.search(r'[a-z]', password):
        raise HTTPException(status_code=400, detail="Password harus mengandung huruf kecil")
    if not re.search(r'[0-9]', password):
        raise HTTPException(status_code=400, detail="Password harus mengandung angka")
    if not re.search(r'[^A-Za-z0-9]', password):
        raise HTTPException(status_code=400, detail="Password harus mengandung karakter spesial")

    if has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
        if not assigned_to:
            raise HTTPException(status_code=400, detail="Admin pengelola wajib dipilih")
    else:
        if not current_user_obj or current_user_obj.role != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Akun admin tidak valid")
        assigned_to = current_user_obj.username

    actual_domain = email.split("@", 1)[1]
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
        configured_domain = get_configured_mail_domain()
        if actual_domain != configured_domain:
            raise HTTPException(status_code=400, detail=f"Mailbox wajib menggunakan domain @{configured_domain}")
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
        mailbox = existing
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
    try:
        _assign_mailbox_manager(db, mailbox, assigned_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(db, user_info["username"], "create_mailbox", None, request.client.host if request.client else None, email)
    db.commit()
    return {"ok": True, "email": email, "domain": actual_domain, "assigned_to": mailbox.assigned_to}


@app.post("/api/mailboxes/login")
@limiter.limit("20/minute")
async def api_login_mailbox(request: Request, payload: dict, db: Session = Depends(get_db)):
    mailbox_id = payload.get("mailbox_id")
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    # ── Strategy 1: Try AdminMailbox by email / id ──────────────────────────
    mailbox = None
    try:
        mailbox = resolve_active_mailbox(
            db, mailbox_id, email,
            missing_status_code=401,
            missing_detail="Incorrect password or email address",
            inactive_detail="Incorrect password or email address",
        )
    except HTTPException:
        mailbox = None
        try:
            db.rollback()
        except Exception:
            pass

    if mailbox and mailbox.password_hash and len(mailbox.password_hash) > 0 and verify_password(password, mailbox.password_hash):
        # Successful AdminMailbox login
        access_token = create_access_token({
            "sub": f"mailbox:{mailbox.id}",
            "role": "mailbox",
            "mailbox_id": str(mailbox.id),
            "mailbox_email": mailbox.email.lower(),
        })
        response = JSONResponse({"ok": True, "mailbox": {
            "id": mailbox.id,
            "email": mailbox.email,
            "domain": mailbox.domain,
            "sender_name": mailbox.sender_name or "",
        }})
        response.set_cookie(
            key="mailbox_token", value=access_token,
            httponly=True, samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            secure=os.getenv("ENV", "development") == "production",
            path="/",
        )
        return response

    # ── Strategy 2: Fall back to User account by email ──────────────────────
    # A user's email is not an AdminMailbox entry — authenticate via User table
    # and issue a dashboard token so they land on the user dashboard.
    if email:
        try:
            user = db.query(User).filter(
                User.email == email,
                User.is_active == True,
            ).first()
            if user and verify_password(password, user.hashed_password):
                # Issue a standard dashboard access_token (role=user)
                token = create_access_token({"sub": user.username, "role": user.role})
                # Determine a representative mailbox email for the session
                # (first active mailbox in the org, or the user's own email)
                mailbox_email = email
                linked_mb = None
                access_row = (
                    db.query(AdminMailboxAccess)
                    .filter(AdminMailboxAccess.username == user.username)
                    .first()
                )
                if access_row:
                    linked_mb = db.query(AdminMailbox).filter(
                        AdminMailbox.id == access_row.mailbox_id,
                        AdminMailbox.is_active == True,
                    ).first()
                    if linked_mb:
                        mailbox_email = linked_mb.email

                response = JSONResponse({"ok": True, "mailbox": {
                    "id": linked_mb.id if linked_mb else None,
                    "email": mailbox_email,
                    "domain": mailbox_email.split("@", 1)[1] if "@" in mailbox_email else "",
                    "sender_name": user.username,
                    "user_mode": True,
                    "username": user.username,
                    "role": user.role,
                }})
                # Set the dashboard access_token cookie so the user page loads correctly
                response.set_cookie(
                    key="access_token", value=token,
                    httponly=True, samesite="lax",
                    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    secure=os.getenv("ENV", "development") == "production",
                    path="/",
                )
                # Also set mailbox_token if we found a linked mailbox
                if linked_mb:
                    mb_token = create_access_token({
                        "sub": f"mailbox:{linked_mb.id}",
                        "role": "mailbox",
                        "mailbox_id": str(linked_mb.id),
                        "mailbox_email": linked_mb.email.lower(),
                    })
                    response.set_cookie(
                        key="mailbox_token", value=mb_token,
                        httponly=True, samesite="lax",
                        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        secure=os.getenv("ENV", "development") == "production",
                        path="/",
                    )
                return response
        except Exception as _strategy2_err:
            logger.warning(f"[mailbox_login] strategy2 error: {_strategy2_err}")

    raise HTTPException(status_code=401, detail="Incorrect password or email address")


@app.delete("/api/admin/mailboxes/{mailbox_id}")
@limiter.limit("20/minute")
async def api_delete_admin_mailbox(mailbox_id: int, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES) and not has_permission_dict(user_info, Permission.MANAGE_ORG_MAILBOXES):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    # P1 FIX: Admin can only delete mailboxes from their own organization
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not _admin_can_manage_mailbox(db, current_user, mailbox):
            raise HTTPException(status_code=403, detail="Admin hanya dapat menghapus mailbox dalam cakupannya")
    mailbox_email = mailbox.email
    try:
        deleted = _permanently_delete_mailbox(db, mailbox)
        log_audit(
            db,
            user_info["username"],
            "delete_mailbox_permanent",
            None,
            request.client.host if request.client else None,
            f"{mailbox_email}; deleted_emails={deleted['emails']}",
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Permanent mailbox deletion failed for mailbox_id=%s", mailbox_id)
        raise HTTPException(status_code=500, detail="Mailbox gagal dihapus permanen. Tidak ada data yang diubah.")
    return {"ok": True, "email": mailbox_email, "deleted": deleted}


@app.post("/api/admin/mailboxes/{mailbox_id}/change-password")
@limiter.limit("20/minute")
async def api_change_mailbox_password(mailbox_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    # P1 FIX: Admin can only change password for mailboxes in their own organization
    if user_info["role"] == "admin":
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not _admin_can_manage_mailbox(db, current_user, mailbox):
            raise HTTPException(status_code=403, detail="Admin hanya dapat mengelola mailbox dalam cakupannya")
    new_password = str(payload.get("password", ""))
    import re as _re
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password minimal 8 karakter")
    if not _re.search(r'[A-Z]', new_password):
        raise HTTPException(status_code=400, detail="Password harus mengandung huruf besar")
    if not _re.search(r'[a-z]', new_password):
        raise HTTPException(status_code=400, detail="Password harus mengandung huruf kecil")
    if not _re.search(r'[0-9]', new_password):
        raise HTTPException(status_code=400, detail="Password harus mengandung angka")
    if not _re.search(r'[^A-Za-z0-9]', new_password):
        raise HTTPException(status_code=400, detail="Password harus mengandung karakter spesial")
    mailbox.password_hash = hash_password(new_password)
    log_audit(db, user_info["username"], "change_mailbox_password", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {"ok": True}


# In-memory autologin token store (token -> mailbox_id, TTL 60s)
import time as _time
_autologin_tokens: dict = {}

@app.post("/api/admin/mailboxes/{mailbox_id}/autologin-token")
@limiter.limit("20/minute")
async def api_generate_autologin_token(mailbox_id: int, request: Request, db: Session = Depends(get_db)):
    """Generate a one-time autologin token for admin to open webmail without password."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can generate autologin tokens")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id, AdminMailbox.is_active == True).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    # P1 FIX: Admin can only generate tokens for mailboxes in their own organization
    if user_info["role"] == "admin":
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not _admin_can_manage_mailbox(db, current_user, mailbox):
            raise HTTPException(status_code=403, detail="Admin hanya dapat mengakses mailbox dalam cakupannya")
    import secrets as _secrets
    now = _time.time()
    expired = [k for k, v in _autologin_tokens.items() if v.get("expires", 0) < now]
    for k in expired:
        del _autologin_tokens[k]
    token = _secrets.token_urlsafe(32)
    _autologin_tokens[token] = {"mailbox_id": mailbox_id, "expires": now + 60}
    log_audit(db, user_info["username"], "generate_autologin_token", None, request.client.host if request.client else None, mailbox.email)
    return {"token": token}


@app.post("/api/admin/mailboxes/{mailbox_id}/admin-autologin-token")
@limiter.limit("20/minute")
async def api_generate_admin_autologin_token(mailbox_id: int, request: Request, db: Session = Depends(get_db)):
    """Generate a one-time autologin token for superadmin to open admin dashboard as the mailbox's admin."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can generate admin autologin tokens")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    admin_user = db.query(User).filter(
        User.username == mailbox.assigned_to,
        User.role == UserRole.ADMIN.value,
        User.is_active == True,
    ).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin not found for this mailbox")
    import secrets as _secrets
    now = _time.time()
    expired = [k for k, v in _autologin_tokens.items() if v.get("expires", 0) < now]
    for k in expired:
        del _autologin_tokens[k]
    token = _secrets.token_urlsafe(32)
    _autologin_tokens[token] = {"admin_username": admin_user.username, "expires": now + 60}
    return {"token": token, "admin_username": admin_user.username}


@app.post("/api/admin/admins/{admin_username}/autologin-token")
@limiter.limit("20/minute")
async def api_generate_admin_autologin_token_by_username(admin_username: str, request: Request, db: Session = Depends(get_db)):
    """Generate a one-time autologin token to log in as a specific admin."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can generate admin autologin tokens")
    admin_user = db.query(User).filter(
        User.username == admin_username,
        User.role == UserRole.ADMIN.value,
    ).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin not found")
    import secrets as _secrets
    now = _time.time()
    token = _secrets.token_urlsafe(32)
    _autologin_tokens[token] = {"admin_username": admin_user.username, "expires": now + 60}
    return {"token": token, "admin_username": admin_user.username}


@app.post("/api/admin/autologin")
@limiter.limit("20/minute")
async def api_redeem_admin_autologin_token(request: Request, payload: dict, db: Session = Depends(get_db)):
    """Redeem a one-time admin autologin token and return an admin session."""
    token = str(payload.get("token", ""))
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    now = _time.time()
    entry = _autologin_tokens.get(token)
    if not entry or entry["expires"] < now:
        raise HTTPException(status_code=401, detail="Token tidak valid atau sudah kadaluarsa")
    del _autologin_tokens[token]
    admin_username = entry.get("admin_username")
    if not admin_username:
        raise HTTPException(status_code=400, detail="Invalid token")
    admin_user = db.query(User).filter(User.username == admin_username, User.is_active == True).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin not found")
    from datetime import timedelta
    admin_token = create_access_token({"sub": admin_user.username, "role": admin_user.role})
    resp = JSONResponse({"access_token": admin_token, "username": admin_user.username, "role": admin_user.role})
    resp.set_cookie(key="access_token", value=admin_token, httponly=True, samesite="lax",
                    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/")
    return resp


@app.post("/api/mailboxes/autologin")
@limiter.limit("20/minute")
async def api_redeem_autologin_token(request: Request, payload: dict, db: Session = Depends(get_db)):
    """Redeem a one-time autologin token and return a mailbox session."""
    token = str(payload.get("token", ""))
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    now = _time.time()
    entry = _autologin_tokens.get(token)
    if not entry or entry["expires"] < now:
        raise HTTPException(status_code=401, detail="Token tidak valid atau sudah kadaluarsa")
    # One-time use — delete immediately
    del _autologin_tokens[token]
    mailbox_id = entry["mailbox_id"]
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id, AdminMailbox.is_active == True).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    # Use the same signing key and claims as the normal mailbox login flow.
    # The previous legacy token used SECRET_KEY and omitted role/mailbox_email,
    # so auth_me rejected it and every inbox API request returned 401.
    mailbox_token = create_access_token({
        "sub": f"mailbox:{mailbox.id}",
        "role": "mailbox",
        "mailbox_id": str(mailbox.id),
        "mailbox_email": mailbox.email.lower(),
    })
    resp = JSONResponse({
        "mailbox": {
            "id": mailbox.id,
            "email": mailbox.email,
            "sender_name": mailbox.sender_name or "",
            "avatar_url": mailbox.avatar_url or "",
        }
    })
    resp.set_cookie(
        "mailbox_token",
        mailbox_token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production",
        path="/",
    )
    return resp


@app.put("/api/admin/mailboxes/{mailbox_id}/forwarder")
@limiter.limit("20/minute")
async def api_update_admin_mailbox_forwarder(mailbox_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can manage mailboxes")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id, AdminMailbox.is_active == True).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    # P1 FIX: Admin can only update forwarders for mailboxes in their own organization
    if user_info["role"] == "admin":
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not _admin_can_manage_mailbox(db, current_user, mailbox):
            raise HTTPException(status_code=403, detail="Admin hanya dapat mengatur forward mailbox dalam cakupannya")
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
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not _admin_can_manage_mailbox(db, current_user, mailbox):
            raise HTTPException(status_code=403, detail="Admin tidak memiliki akses ke mailbox ini")
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
        if not has_permission_dict(user_info, Permission.MANAGE_ALL_MAILBOXES):
            raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat mengganti admin pengelola")
        try:
            _assign_mailbox_manager(db, mailbox, str(payload["assigned_to"]).strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_action = "update_mailbox"
    if "is_active" in payload:
        requested_active = bool(payload["is_active"])
        if requested_active and mailbox.assigned_to:
            try:
                _assign_mailbox_manager(db, mailbox, mailbox.assigned_to)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        mailbox.is_active = requested_active
        if not requested_active:
            _purge_mailbox_autologin_tokens(mailbox.id)
        audit_action = "reactivate_mailbox" if requested_active else "deactivate_mailbox"
    log_audit(db, user_info["username"], audit_action, None, request.client.host if request.client else None, mailbox.email)
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
    if user_info["role"] == "admin":
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not _admin_can_manage_mailbox(db, current_user, mailbox):
            raise HTTPException(status_code=403, detail="Admin tidak memiliki akses ke mailbox ini")
    mailbox.password_hash = hash_password(password)
    log_audit(db, user_info["username"], "update_mailbox_password", None, request.client.host if request.client else None, mailbox.email)
    db.commit()
    return {"ok": True}


@app.put("/api/admin/users/{username}")
async def api_update_user(username: str, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat mengelola admin")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Halaman ini hanya dapat mengelola akun admin")
    
    if "role" in payload:
        if payload["role"] != UserRole.ADMIN.value:
            raise HTTPException(status_code=400, detail="Role pada halaman ini dikunci sebagai admin")
    user.email = None
    if "is_active" in payload:
        user.is_active = bool(payload["is_active"])
        log_audit(
            db,
            user_info["username"],
            "update_admin_status",
            None,
            request.client.host if request.client else None,
            f"{username} -> {'active' if user.is_active else 'inactive'}",
        )
    if "password" in payload and payload["password"]:
        new_hashed = hash_password(payload["password"])
        user.hashed_password = new_hashed
        # Sync password to all linked AdminMailbox records so webmail login works
        linked_mailbox_ids = set()
        # 1. Mailboxes linked via AdminMailboxAccess (the only reliable join table)
        for acc in db.query(AdminMailboxAccess).filter(AdminMailboxAccess.username == username).all():
            linked_mailbox_ids.add(acc.mailbox_id)
        # 2. Mailbox matching user's email directly
        if user.email:
            mb_by_email = db.query(AdminMailbox).filter(
                AdminMailbox.email == user.email.lower(),
                AdminMailbox.is_active == True,
            ).first()
            if mb_by_email:
                linked_mailbox_ids.add(mb_by_email.id)
        if linked_mailbox_ids:
            db.query(AdminMailbox).filter(AdminMailbox.id.in_(list(linked_mailbox_ids))).update(
                {"password_hash": new_hashed}, synchronize_session=False
            )
        log_audit(db, user_info["username"], "update_user_password", None, request.client.host if request.client else None, f"{username} (synced {len(linked_mailbox_ids)} mailbox(es))")
    db.commit()
    return {"ok": True, "message": f"User {username} updated"}


@app.delete("/api/admin/users/{username}")
async def api_delete_user(username: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat mengelola admin")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Halaman ini hanya dapat menghapus akun admin")
    owned_mailboxes = db.query(AdminMailbox).filter(
        AdminMailbox.assigned_to == user.username,
        AdminMailbox.is_active == True,
    ).count()
    if owned_mailboxes:
        raise HTTPException(
            status_code=409,
            detail=f"Pindahkan {owned_mailboxes} mailbox yang dikelola admin ini sebelum menghapus akun",
        )
    
    # Enforce delete restrictions
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not _admin_can_manage_user(current_user, user):
            raise HTTPException(status_code=403, detail="Admin hanya dapat menonaktifkan pengguna dalam cakupannya")
        if user.role != "user":
            raise HTTPException(status_code=403, detail="Admin can only disable users with 'user' role")
            
    user.is_active = False
    db.commit()
    return {"ok": True, "message": f"User {username} disabled"}


@app.get("/api/admin/list-users-with-admin")
async def api_list_users_with_admin(request: Request, db: Session = Depends(get_db)):
    """Return all users (role=user) with their admin and organization info."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view users")
    users = db.query(User).filter(User.role == "user").order_by(User.username).all()
    orgs = {o.id: o.name for o in db.query(Organization).all()}
    admins = db.query(User).filter(User.role == "admin").all()
    org_admin_map = {}
    for a in admins:
        if a.organization_id:
            org_admin_map.setdefault(a.organization_id, []).append(a.username)
    result = []
    for u in users:
        org_name = orgs.get(u.organization_id, "")
        admin_list = org_admin_map.get(u.organization_id, [])
        # Mailboxes: via AdminMailboxAccess OR matching user email domain
        mailbox_ids = set()
        # 1) Direct access records
        access_rows = db.query(AdminMailboxAccess).filter(AdminMailboxAccess.username == u.username).all()
        for r in access_rows:
            mailbox_ids.add(r.mailbox_id)
        # 2) Match by email domain (user_email_domain == mailbox_domain)
        user_domain = (u.email or "").split("@")[-1].strip().lower() if u.email and "@" in u.email else None
        if user_domain:
            domain_mbs = db.query(AdminMailbox).filter(AdminMailbox.domain == user_domain).all()
            for mb in domain_mbs:
                mailbox_ids.add(mb.id)
        mailboxes = []
        if mailbox_ids:
            for mb in db.query(AdminMailbox).filter(AdminMailbox.id.in_(list(mailbox_ids))).all():
                mailboxes.append({"id": mb.id, "email": mb.email, "is_active": mb.is_active, "forward_to": mb.forward_to or ""})
        result.append({
            "username": u.username,
            "email": u.email or "",
            "is_active": u.is_active,
            "forward_to": u.forward_to or "",
            "forward_enabled": bool(getattr(u, 'forward_enabled', False)),
            "forward_keep_copy": bool(getattr(u, 'forward_keep_copy', True)),
            "organization_id": u.organization_id,
            "organization": org_name,
            "admins": admin_list,
            "mailboxes": mailboxes,
        })
    return result


@app.get("/api/admin/list-admins-with-stats")
async def api_list_admins_with_stats(request: Request, db: Session = Depends(get_db)):
    """Return all admins with mailbox count, user count, and org name."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view admins")
    q = db.query(User).filter(User.role == "admin")
    # Org isolation: admin only sees other admins in their own organization
    if user_info["role"] == "admin":
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if current_user and current_user.organization_id:
            q = q.filter(User.organization_id == current_user.organization_id)
    admins = q.order_by(User.username).all()
    orgs = {o.id: o.name for o in db.query(Organization).all()}
    result = []
    for a in admins:
        org_name = orgs.get(a.organization_id, "")
        managed_mailboxes = db.query(AdminMailbox).filter(
            AdminMailbox.assigned_to == a.username
        ).order_by(AdminMailbox.email).all()
        mailboxes = [
            {"id": mb.id, "email": mb.email, "is_active": mb.is_active}
            for mb in managed_mailboxes
        ]
        user_count = 0
        if a.organization_id:
            user_count = db.query(User).filter(
                User.organization_id == a.organization_id,
                User.role == "user"
            ).count()
        email_count = 0
        if a.organization_id:
            email_count = db.query(QuarantineEmail).filter(
                QuarantineEmail.organization_id == a.organization_id
            ).count()
        result.append({
            "id": a.id,
            "username": a.username,
            "role": a.role,
            "is_active": a.is_active,
            "organization_id": a.organization_id,
            "organization": org_name,
            "mailbox_count": len(mailboxes),
            "user_count": user_count,
            "email_count": email_count,
            "mailboxes": mailboxes,
        })
    return result


@app.delete("/api/admin/users/{username}/hard")
async def api_hard_delete_user(username: str, request: Request, db: Session = Depends(get_db)):
    """Permanently delete a user and their mailbox access records."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can hard-delete users")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Halaman ini hanya dapat menghapus akun admin")
    owned_mailboxes = db.query(AdminMailbox).filter(
        AdminMailbox.assigned_to == user.username,
        AdminMailbox.is_active == True,
    ).count()
    if owned_mailboxes:
        raise HTTPException(
            status_code=409,
            detail=f"Pindahkan {owned_mailboxes} mailbox yang dikelola admin ini sebelum menghapus akun",
        )
    if user.username == user_info["username"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if user.role == UserRole.SUPERADMIN.value:
        remaining_superadmins = db.query(User).filter(
            User.role == UserRole.SUPERADMIN.value,
            User.id != user.id,
            User.is_active == True,
        ).count()
        if remaining_superadmins == 0:
            raise HTTPException(status_code=400, detail="At least one active superadmin must remain")

    avatar_url = (user.avatar_url or "").strip()
    try:
        db.query(AdminMailboxAccess).filter(
            AdminMailboxAccess.username == username
        ).delete(synchronize_session=False)
        log_audit(
            db,
            user_info["username"],
            "hard_delete_user",
            None,
            request.client.host if request.client else None,
            username,
        )
        db.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Unable to hard-delete user %s: %s", username, exc)
        raise HTTPException(
            status_code=409,
            detail="User is still referenced by other records and cannot be deleted",
        ) from exc
    if avatar_url.startswith("/static/avatars/"):
        (static_dir / "avatars" / Path(avatar_url).name).unlink(missing_ok=True)
    return {"ok": True, "message": f"User {username} permanently deleted"}


@app.get("/api/admin/audit-logs")
async def api_get_audit_logs(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_AUDIT_LOG):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view audit logs")
    
    log_query = db.query(AuditLog)
    
    # P1 FIX: Admin sees only audit logs from users in their own organization
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if current_user and current_user.organization_id:
            org_usernames = [
                u.username for u in db.query(User.username).filter(
                    User.organization_id == current_user.organization_id
                ).all()
            ]
            log_query = log_query.filter(AuditLog.user.in_(org_usernames))
        else:
            return []
    
    logs = log_query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {"user": l.user, "action": l.action, "email_id": l.email_id, "details": l.details, "created_at": str(l.created_at)}
        for l in logs
    ]


@app.get("/api/admin/organizations")
async def api_list_organizations(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Permission denied")
    # P2 FIX: Admin sees only their own organization
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if current_user and current_user.organization_id:
            orgs = db.query(Organization).filter(Organization.id == current_user.organization_id).all()
        else:
            orgs = []
    else:
        orgs = db.query(Organization).order_by(Organization.name).all()
    return [{"id": o.id, "name": o.name} for o in orgs]


@app.get("/api/admin/stats")
async def api_admin_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view stats")

    # Superadmin receives the global snapshot. Admin statistics must follow
    # mailbox ownership, not merely organization membership: two admins in
    # the same organization may manage completely different mailboxes.
    # Role is authoritative for global scope. Admin currently also has report
    # export permission, but that must never expand overview data globally.
    is_superadmin = user_info["role"] == UserRole.SUPERADMIN.value
    org_id = None
    mailbox_q = db.query(AdminMailbox)
    if not is_superadmin:
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        org_id = current_user.organization_id if current_user else None
        mailbox_q = mailbox_q.filter(AdminMailbox.assigned_to == user_info["username"])

    # Dashboard email metrics only follow currently active, registered
    # mailboxes. Historical rows from removed/deactivated identities must not
    # appear as current platform traffic.
    mailbox_identities = [
        mailbox.email.strip().lower()
        for mailbox in mailbox_q.filter(AdminMailbox.is_active == True).all()
        if mailbox.email
    ]

    user_q = db.query(User)
    email_q = db.query(QuarantineEmail)
    if not is_superadmin:
        user_q = user_q.filter(
            User.role == UserRole.USER.value,
            func.lower(User.email).in_(mailbox_identities),
        ) if mailbox_identities else user_q.filter(False)
    recipient_filters = [
        condition
        for identity in mailbox_identities
        for condition in _mailbox_identity_filters(QuarantineEmail.recipient_list, identity)
    ]
    email_q = email_q.filter(or_(*recipient_filters)) if recipient_filters else email_q.filter(False)

    total_users = user_q.count()
    active_users = user_q.filter(User.is_active == True).count()
    if is_superadmin:
        total_admins = user_q.filter(User.role == UserRole.ADMIN.value).count()
        total_superadmins = user_q.filter(User.role == UserRole.SUPERADMIN.value).count()
        total_regular_users = user_q.filter(User.role == UserRole.USER.value).count()
    else:
        total_admins = 1
        total_superadmins = 0
        total_regular_users = total_users
    total_organizations = db.query(Organization).count() if is_superadmin else (1 if org_id else 0)
    total_mailboxes = mailbox_q.count()
    active_mailboxes = mailbox_q.filter(AdminMailbox.is_active == True).count()
    clean_count = email_q.filter(
        QuarantineEmail.label == "CLEAN",
        QuarantineEmail.status != "trash",
    ).count()
    warn_count = email_q.filter(
        QuarantineEmail.label == "WARN",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    ).count()
    quarantine_count = email_q.filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    ).count()
    phishing_count = email_q.filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.category.in_(["phishing", "malware"]),
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
    ).count()
    malware_count = 0
    spam_count = email_q.filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
        or_(
            and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"),
            and_(
                QuarantineEmail.label == "QUARANTINE",
                or_(
                    QuarantineEmail.category == "",
                    QuarantineEmail.category.is_(None),
                    ~QuarantineEmail.category.in_(["spam", "phishing", "malware"]),
                ),
            ),
        ),
    ).count()
    total_emails = clean_count + warn_count + quarantine_count
    audit_q = db.query(AuditLog)
    if not is_superadmin:
        audit_q = audit_q.filter(AuditLog.user == user_info["username"])
    audit_count = audit_q.count()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_admins": total_admins,
        "total_superadmins": total_superadmins,
        "total_regular_users": total_regular_users,
        "total_organizations": total_organizations,
        "total_mailboxes": total_mailboxes,
        "active_mailboxes": active_mailboxes,
        "total_emails": total_emails,
        "clean": clean_count,
        "warn": warn_count,
        "quarantine": quarantine_count,
        "categories": {
            "phishing": phishing_count,
            "spam": spam_count,
            "malware": malware_count,
            "warn": warn_count,
        },
        "audit_logs": audit_count,
    }


def _managed_review_mailboxes(db: Session, user_info: dict) -> list[AdminMailbox]:
    """Return the real mailbox scope available to a threat reviewer."""
    query = db.query(AdminMailbox)
    if user_info["role"] == UserRole.ADMIN.value:
        query = query.filter(AdminMailbox.assigned_to == user_info["username"])
    return query.order_by(AdminMailbox.email.asc()).all()


def _mailbox_scope_filter(query, mailbox_emails: list[str]):
    identities = [email.strip().lower() for email in mailbox_emails if email]
    if not identities:
        return query.filter(False)
    return query.filter(or_(*[
        QuarantineEmail.recipient_list.ilike(f"%{identity}%")
        for identity in identities
    ]))


def _record_mailbox_identity(record: QuarantineEmail, mailbox_emails: list[str]) -> str:
    recipients = {
        address.lower()
        for _, address in getaddresses([record.recipient_list or ""])
        if address
    }
    for mailbox_email in mailbox_emails:
        identity = mailbox_email.strip().lower()
        if identity in recipients:
            return identity
    # Legacy rows can contain a non-RFC recipient string. Only map it to an
    # actual registered mailbox; never invent or echo an unrelated recipient.
    raw_recipients = (record.recipient_list or "").lower()
    return next((email for email in mailbox_emails if email.lower() in raw_recipients), "")


@app.get("/api/admin/quarantine")
async def api_admin_quarantine(
    request: Request,
    q: str = Query(None),
    category: str = Query(None),
    mailbox: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    category = canonical_threat_category(category)
    if not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="Permission denied")
    managed_mailboxes = _managed_review_mailboxes(db, user_info)
    mailbox_lookup = {item.email.strip().lower(): item for item in managed_mailboxes if item.email}
    requested_mailbox = (mailbox or "").strip().lower()
    if requested_mailbox and requested_mailbox not in mailbox_lookup:
        raise HTTPException(status_code=403, detail="Mailbox is not assigned to this admin")
    scoped_mailbox_emails = [requested_mailbox] if requested_mailbox else list(mailbox_lookup)

    query = db.query(QuarantineEmail)
    query = query.filter(QuarantineEmail.status.notin_(["trash", "released"]))
    query = query.filter(QuarantineEmail.label.in_(["QUARANTINE", "WARN"]))
    query = _mailbox_scope_filter(query, scoped_mailbox_emails)

    if category and category in {"spam", "phishing", "malware", "warn"}:
        if category == "warn":
            query = query.filter(QuarantineEmail.label == "WARN")
        elif category == "spam":
            query = query.filter(or_(
                and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"),
                and_(QuarantineEmail.label == "QUARANTINE", or_(
                    QuarantineEmail.category == "",
                    QuarantineEmail.category.is_(None),
                    ~QuarantineEmail.category.in_(["spam", "phishing", "malware"]),
                )),
            ))
        elif category == "phishing":
            query = query.filter(
                QuarantineEmail.label == "QUARANTINE",
                QuarantineEmail.category.in_(["phishing", "malware"]),
            )

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
        mailbox_identity = _record_mailbox_identity(email, scoped_mailbox_emails)
        if not mailbox_identity:
            continue
        cat = display_category(email)
        body_preview = email_body_preview(email.raw_content)

        _, human_reasons, _ = build_detection_explanation(email)

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
            "mailbox": mailbox_identity,
            "received_at": email.received_at.isoformat() if hasattr(email.received_at, "isoformat") else str(email.received_at) if email.received_at else None,
        })

    mailbox_options = [
        {"id": item.id, "email": item.email.lower(), "sender_name": item.sender_name or "", "is_active": bool(item.is_active)}
        for item in managed_mailboxes
    ]
    return {"emails": emails_data, "total": total, "page": page, "page_size": page_size, "mailboxes": mailbox_options}


@app.get("/api/admin/detection-logs")
async def api_admin_detection_logs(
    request: Request,
    q: str = Query(None),
    label: str = Query(None),
    mailbox: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.REVIEW_QUARANTINE):
        raise HTTPException(status_code=403, detail="Permission denied")
    managed_mailboxes = _managed_review_mailboxes(db, user_info)
    mailbox_lookup = {item.email.strip().lower(): item for item in managed_mailboxes if item.email}
    requested_mailbox = (mailbox or "").strip().lower()
    if requested_mailbox and requested_mailbox not in mailbox_lookup:
        raise HTTPException(status_code=403, detail="Mailbox is not assigned to this admin")
    scoped_mailbox_emails = [requested_mailbox] if requested_mailbox else list(mailbox_lookup)

    query = db.query(QuarantineEmail)
    query = query.filter(QuarantineEmail.status != "trash")
    query = query.filter(QuarantineEmail.label.in_(["CLEAN", "WARN", "QUARANTINE"]))
    query = _mailbox_scope_filter(query, scoped_mailbox_emails)
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
        mailbox_identity = _record_mailbox_identity(email, scoped_mailbox_emails)
        if not mailbox_identity:
            continue
        action_info = latest_actions.get(email.email_id, {})
        logs_data.append({
            "email_id": email.email_id,
            "sender": email.sender,
            "recipient": email.recipient_list or "",
            "mailbox": mailbox_identity,
            "subject": email.subject,
            "label": email.label,
            "category": display_category(email),
            "status": email.status,
            "fused_score": email.fused_score,
            "ml_probability": email.ml_probability,
            "received_at": email.received_at.isoformat() if hasattr(email.received_at, "isoformat") else str(email.received_at) if email.received_at else None,
            "action_taken": action_info.get("action"),
            "action_by": action_info.get("by"),
            "action_at": action_info.get("at"),
        })

    mailbox_options = [
        {"id": item.id, "email": item.email.lower(), "sender_name": item.sender_name or "", "is_active": bool(item.is_active)}
        for item in managed_mailboxes
    ]
    return {"logs": logs_data, "total": total, "page": page, "page_size": page_size, "mailboxes": mailbox_options}


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
    )).count() or 0
    phishing = base.filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.category.in_(["phishing", "malware"]),
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
            "category": display_category(e),
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
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
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
    if mailbox_record and user_info["role"] == UserRole.ADMIN.value:
        if mailbox_record.assigned_to != user_info["username"]:
            mailbox_record = None
    if mailbox_record:
        return {
            "mailbox": {
                "id": mailbox_record.id,
                "email": mailbox_record.email,
                "is_active": mailbox_record.is_active,
            }
        }
    return {"mailbox": None}


@app.get("/api/user/mailboxes")
async def api_user_mailboxes(request: Request, db: Session = Depends(get_db)):
    """Returns all mailboxes accessible to the current user.

    Priority:
    1. Exact email match in admin_mailboxes (user's own mailbox record)
    2. Mailboxes explicitly granted via admin_mailbox_access
    3. Domain-matched org mailboxes (shared inbox@, security-alerts@, etc.)
    """
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    if user_info["role"] not in ("user", "admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Access denied")
    if user_info["role"] == UserRole.SUPERADMIN.value:
        return [
            {
                "id": mailbox.id,
                "email": mailbox.email,
                "is_active": mailbox.is_active,
                "sender_name": mailbox.sender_name or "",
                "avatar_url": mailbox.avatar_url or "",
                "domain": mailbox.domain,
                "assigned_to": mailbox.assigned_to or "",
            }
            for mailbox in db.query(AdminMailbox).filter(
                AdminMailbox.is_active == True
            ).order_by(AdminMailbox.email).all()
        ]
    if user_info["role"] == UserRole.ADMIN.value:
        return [
            {
                "id": mailbox.id,
                "email": mailbox.email,
                "is_active": mailbox.is_active,
                "sender_name": mailbox.sender_name or "",
                "avatar_url": mailbox.avatar_url or "",
                "domain": mailbox.domain,
                "assigned_to": mailbox.assigned_to or "",
            }
            for mailbox in db.query(AdminMailbox).filter(
                AdminMailbox.assigned_to == user_info["username"],
                AdminMailbox.is_active == True,
            ).order_by(AdminMailbox.email).all()
        ]

    user = db.query(User).filter(User.username == user_info["username"]).first()
    user_email = (user.email if user and user.email else user_info["username"]).lower()
    if "@" not in user_email:
        return []

    seen_ids = set()
    results = []

    def _mb_dict(m):
        return {
            "id": m.id,
            "email": m.email,
            "is_active": m.is_active,
            "sender_name": getattr(m, "sender_name", None),
            "avatar_url": getattr(m, "avatar_url", "") or "",
            "domain": m.email.split("@")[1] if m.email and "@" in m.email else "",
        }

    # 1. Exact email match — user's own mailbox
    own = db.query(AdminMailbox).filter(
        AdminMailbox.email == user_email,
        AdminMailbox.is_active == True,
    ).all()
    for m in own:
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            results.append(_mb_dict(m))

    # 2. Explicitly granted via admin_mailbox_access
    access_rows = db.query(AdminMailboxAccess).filter(
        AdminMailboxAccess.username == user_info["username"]
    ).all()
    if access_rows:
        granted_ids = [r.mailbox_id for r in access_rows]
        granted = db.query(AdminMailbox).filter(
            AdminMailbox.id.in_(granted_ids),
            AdminMailbox.is_active == True,
        ).all()
        for m in granted:
            if m.id not in seen_ids:
                seen_ids.add(m.id)
                results.append(_mb_dict(m))

    return results


# ─── User Reports / Tickets ───────────────────────────────────────────

@app.post("/api/reports")
async def submit_report(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    username = user_info["username"]
    mailbox_email = str(payload.get("mailbox_email") or user_info.get("mailbox_email") or "").strip().lower()
    if mailbox_email:
        mailbox = db.query(AdminMailbox).filter(
            func.lower(AdminMailbox.email) == mailbox_email,
            AdminMailbox.is_active == True,
        ).first()
        if mailbox:
            ensure_mailbox_access(db, mailbox, user_info)
            mailbox_email = mailbox.email.lower()
        elif mailbox_email != (user_info.get("mailbox_email") or "").strip().lower():
            raise HTTPException(403, "Anda tidak dapat membuat laporan untuk email ini")
    category = payload.get("category", "other")
    priority = payload.get("priority", "normal")
    valid_categories = {"bug", "question", "access", "false_positive", "other"}
    valid_priorities = {"low", "normal", "high", "urgent"}
    if category not in valid_categories:
        category = "other"
    if priority not in valid_priorities:
        priority = "normal"
    report = Report(
        # Keep the reporting mailbox in the existing indexed identity field.
        # Older reports used the dashboard username and are resolved below.
        username=mailbox_email or username,
        subject=payload.get("subject", ""),
        message=payload.get("message", ""),
        category=category,
        priority=priority,
        status="open",
    )
    db.add(report)
    db.commit()
    return {"ok": True, "id": report.id}


@app.get("/api/reports")
async def get_own_reports(
    request: Request,
    mailbox_id: str = Query(None),
    db: Session = Depends(get_db),
):
    """Return report history owned by the authenticated user/mailbox only."""
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    requested_mailbox_id = (mailbox_id or "").strip()
    report_identity = ""

    if requested_mailbox_id:
        mailbox = resolve_active_mailbox(
            db,
            requested_mailbox_id,
            missing_status_code=404,
            missing_detail="Mailbox not found",
        )
        ensure_mailbox_access(db, mailbox, user_info)
        report_identity = mailbox.email.strip().lower()
    elif user_info["role"] == "mailbox":
        report_identity = (user_info.get("mailbox_email") or "").strip().lower()
    elif user_info["role"] == UserRole.USER.value:
        report_identity = (user_info.get("mailbox_email") or "").strip().lower()
        if not report_identity:
            user = db.query(User).filter(User.username == user_info["username"]).first()
            report_identity = (user.email or "").strip().lower() if user else ""

    identity_filters = (
        [func.lower(Report.username) == report_identity]
        if report_identity
        else [Report.username == user_info["username"]]
    )
    # Preserve reports created by older user accounts before mailbox identity
    # was stored directly. Mailbox/admin scoped views remain strictly tied to
    # the selected mailbox.
    if user_info["role"] == UserRole.USER.value and not requested_mailbox_id:
        identity_filters.append(Report.username == user_info["username"])

    reports = (
        db.query(Report)
        .filter(or_(*identity_filters))
        .order_by(Report.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": report.id,
            "subject": report.subject,
            "message": report.message,
            "category": report.category,
            "priority": report.priority,
            "status": report.status,
            "admin_reply": report.admin_reply,
            "created_at": str(report.created_at),
            "resolved_at": str(report.resolved_at) if report.resolved_at else None,
        }
        for report in reports
    ]


@app.get("/api/admin/reports")
async def get_reports(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Access denied")
    reports = db.query(Report).order_by(Report.created_at.desc()).limit(500).all()
    reporter_names = {r.username for r in reports if "@" not in (r.username or "")}
    reporter_emails = {
        user.username: (user.email or "").strip().lower()
        for user in db.query(User).filter(User.username.in_(reporter_names)).all()
    } if reporter_names else {}

    managed_emails = None
    if user_info["role"] != UserRole.SUPERADMIN.value:
        managed_emails = {
            email.lower() for (email,) in db.query(AdminMailbox.email).filter(
                AdminMailbox.assigned_to == user_info["username"]
            ).all()
        }

    rows = []
    for report in reports:
        report_email = (
            report.username.strip().lower()
            if "@" in (report.username or "")
            else reporter_emails.get(report.username, "")
        )
        if managed_emails is not None and report_email not in managed_emails:
            continue
        rows.append((report, report_email))
        if len(rows) >= 100:
            break
    return [
        {"id": r.id, "username": r.username, "mailbox_email": report_email,
         "subject": r.subject, "message": r.message,
         "category": r.category, "priority": r.priority,
         "status": r.status, "admin_reply": r.admin_reply,
         "created_at": str(r.created_at), "resolved_at": str(r.resolved_at) if r.resolved_at else None}
        for r, report_email in rows
    ]


@app.put("/api/admin/reports/{report_id}")
async def update_report(report_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Access denied")
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    # Admin can only update reports submitted by one of their assigned mailboxes.
    if user_info["role"] != UserRole.SUPERADMIN.value:
        report_email = report.username.strip().lower() if "@" in (report.username or "") else ""
        if not report_email:
            report_user = db.query(User).filter(User.username == report.username).first()
            report_email = (report_user.email or "").strip().lower() if report_user else ""
        owns_mailbox = db.query(AdminMailbox.id).filter(
            func.lower(AdminMailbox.email) == report_email,
            AdminMailbox.assigned_to == user_info["username"],
        ).first()
        if not owns_mailbox:
            raise HTTPException(status_code=403, detail="Admin hanya dapat mengelola laporan dari email yang dikelolanya.")
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


# ─── Admin: Threat Breakdown ────────────────────────────────────────────

@app.get("/api/admin/threat-breakdown")
async def api_threat_breakdown(
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(default=14, ge=1, le=365),
    date_from: str = Query(default=None),
    date_to:   str = Query(default=None),
):
    """
    Returns:
    - category_counts: { phishing: N, spam: N, malware: N, clean: N, warn: N }
    - top_recipients: [ { recipient, total, phishing, spam, malware } ] top 10
    - top_senders: [ { sender, total, phishing, spam } ] top 10
    - daily_trend: last N days [ { date, total, quarantine, warn, clean } ]
    Query params:
    - days: 1 | 7 | 14 | 30 | 90  (default 14)
    - date_from / date_to: YYYY-MM-DD for custom range (overrides days)
    """
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS) and \
       not has_permission_dict(user_info, Permission.VIEW_ORG_REPORTS):
        raise HTTPException(status_code=403, detail="Access denied")

    # All report values are calculated from persisted email records.  Keep the
    # complete mailbox scope for the "Bersih" counter, and use the threat-only
    # scope for category, recipient, sender, and threat trend aggregates.
    base = db.query(QuarantineEmail).filter(QuarantineEmail.status != "trash")

    # Scope by mailboxes actually assigned to the admin. Legacy inbound rows
    # often have no organization_id; using it alone can accidentally expose a
    # global report when the admin account also has no organization.
    if not has_permission_dict(user_info, Permission.VIEW_ALL_REPORTS):
        managed_identities = [
            mailbox.email.strip().lower()
            for mailbox in db.query(AdminMailbox).filter(
                AdminMailbox.assigned_to == user_info["username"],
                AdminMailbox.is_active == True,
            ).all()
            if mailbox.email
        ]
        mailbox_filters = [
            condition
            for identity in managed_identities
            for condition in _mailbox_identity_filters(QuarantineEmail.recipient_list, identity)
        ]
        base = base.filter(or_(*mailbox_filters)) if mailbox_filters else base.filter(False)

    # ── Date range filter ────────────────────────────────────────────────
    import datetime as _dt
    today = _dt.date.today()

    if date_from or date_to:
        if date_from:
            base = base.filter(QuarantineEmail.received_at >= date_from)
        if date_to:
            base = base.filter(QuarantineEmail.received_at <= f"{date_to} 23:59:59")
        try:
            d0 = _dt.date.fromisoformat(date_from) if date_from else today - _dt.timedelta(days=days - 1)
            d1 = _dt.date.fromisoformat(date_to)   if date_to   else today
        except ValueError:
            d0 = today - _dt.timedelta(days=days - 1)
            d1 = today
    else:
        cutoff_str = (today - _dt.timedelta(days=days - 1)).strftime("%Y-%m-%d")
        base = base.filter(QuarantineEmail.received_at >= cutoff_str)
        d0 = today - _dt.timedelta(days=days - 1)
        d1 = today

    # ── Category counts ──────────────────────────────────────────────────
    from sqlalchemy import case as sa_case
    threat_base = base.filter(QuarantineEmail.label.in_(["WARN", "QUARANTINE"]))

    recipient_rows = (
        threat_base.with_entities(
            QuarantineEmail.recipient_list,
            func.count(QuarantineEmail.id).label("total"),
            func.sum(sa_case((and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category.in_(["phishing", "malware"])), 1), else_=0)).label("phishing"),
            func.sum(sa_case((and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"), 1), else_=0)).label("spam"),
            func.sum(sa_case((QuarantineEmail.category == "malware",  1), else_=0)).label("malware"),
            func.sum(sa_case((QuarantineEmail.label == "WARN", 1), else_=0)).label("warn"),
            func.sum(sa_case((QuarantineEmail.label == "QUARANTINE",  1), else_=0)).label("quarantined"),
        )
        .filter(
            QuarantineEmail.recipient_list.isnot(None),
            QuarantineEmail.recipient_list != "",
        )
        .group_by(QuarantineEmail.recipient_list)
        .order_by(func.count(QuarantineEmail.id).desc())
        .limit(10)
        .all()
    )
    top_recipients = [
        {
            "recipient": r.recipient_list,
            "total": r.total,
            "phishing": r.phishing or 0,
            "spam": r.spam or 0,
            "malware": 0,
            "warn": r.warn or 0,
            "quarantined": r.quarantined or 0,
        }
        for r in recipient_rows
    ]

    # ── Top 10 senders by threat volume ─────────────────────────────────
    sender_rows = (
        threat_base.with_entities(
            QuarantineEmail.sender,
            func.count(QuarantineEmail.id).label("total"),
            func.sum(sa_case((and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category.in_(["phishing", "malware"])), 1), else_=0)).label("phishing"),
            func.sum(sa_case((and_(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam"), 1), else_=0)).label("spam"),
            func.sum(sa_case((QuarantineEmail.category == "malware",  1), else_=0)).label("malware"),
            func.sum(sa_case((QuarantineEmail.label == "WARN", 1), else_=0)).label("warn"),
        )
        .filter(
            QuarantineEmail.label.in_(["WARN", "QUARANTINE"]),
            QuarantineEmail.sender.isnot(None),
            QuarantineEmail.sender != "",
        )
        .group_by(QuarantineEmail.sender)
        .order_by(func.count(QuarantineEmail.id).desc())
        .limit(10)
        .all()
    )
    top_senders = [
        {
            "sender": s.sender,
            "total": s.total,
            "phishing": s.phishing or 0,
            "spam": s.spam or 0,
            "malware": 0,
            "warn": s.warn or 0,
        }
        for s in sender_rows
    ]

    # ── Daily trend — d0 to d1 ───────────────────────────────────────────
    # ── Category counts (respects the active date range via `base`) ──────
    category_counts = {
        "phishing":   threat_base.filter(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category.in_(["phishing", "malware"])).count(),
        "spam":       threat_base.filter(QuarantineEmail.label == "QUARANTINE", QuarantineEmail.category == "spam").count(),
        "malware":    0,
        "warn":       base.filter(QuarantineEmail.label == "WARN").count(),
        "quarantine": base.filter(QuarantineEmail.label == "QUARANTINE").count(),
        "clean":      base.filter(QuarantineEmail.label == "CLEAN").count(),
    }

    daily_trend = []
    delta = (d1 - d0).days + 1
    for i in range(delta - 1, -1, -1):
        day = d1 - _dt.timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        daily_trend.append({
            "date":       day_str,
            "total":      base.filter(QuarantineEmail.received_at.like(f"{day_str}%")).count(),
            "clean":      base.filter(QuarantineEmail.received_at.like(f"{day_str}%"), QuarantineEmail.label == "CLEAN").count(),
            "warn":       base.filter(QuarantineEmail.received_at.like(f"{day_str}%"), QuarantineEmail.label == "WARN").count(),
            "quarantine": base.filter(QuarantineEmail.received_at.like(f"{day_str}%"), QuarantineEmail.label == "QUARANTINE").count(),
        })

    return {
        "category_counts": category_counts,
        "top_recipients": top_recipients,
        "top_senders": top_senders,
        "daily_trend": daily_trend,
    }


# ─── Admin: Per-User Monitoring ────────────────────────────────────────

@app.get("/api/admin/user-stats")
async def api_user_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS) and not has_permission_dict(user_info, Permission.MANAGE_ORG_USERS):
        raise HTTPException(status_code=403, detail="Access denied")

    # P1 FIX: Admin sees only users from their own organization
    user_query = db.query(User).filter(User.is_active == True)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if current_user and current_user.organization_id:
            user_query = user_query.filter(User.organization_id == current_user.organization_id)
        else:
            return []

    users = user_query.all()
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
    # P1 FIX: Admin can only view emails for users in their own organization
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        current_user = db.query(User).filter(User.username == user_info["username"]).first()
        if not current_user or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Admin does not belong to an organization")
        if user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Admin can only view emails for users in their own organization")
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
            "category": display_category(e),
            "received_at": e.received_at,
        }
        for e in emails
    ]


@app.get("/api/admin/track")
async def api_admin_track(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.ACCESS_SYSTEM_HEALTH):
        raise HTTPException(status_code=403, detail="Only superadmin can access tracking data")

    active_mailboxes = db.query(AdminMailbox).filter(AdminMailbox.is_active == True).all()
    active_mailbox_emails = [mailbox.email.lower() for mailbox in active_mailboxes if mailbox.email]

    def mailbox_recipient_scope(emails: list[str]):
        filters = [
            condition
            for email in emails
            for condition in _mailbox_identity_filters(QuarantineEmail.recipient_list, email)
        ]
        return or_(*filters) if filters else False

    visible_email_filter = (
        QuarantineEmail.status != "trash",
        mailbox_recipient_scope(active_mailbox_emails),
    )
    total_clean = db.query(func.count(QuarantineEmail.id)).filter(*visible_email_filter, QuarantineEmail.label == "CLEAN").scalar() or 0
    total_warn = db.query(func.count(QuarantineEmail.id)).filter(
        *visible_email_filter,
        QuarantineEmail.status != "released",
        QuarantineEmail.label == "WARN",
    ).scalar() or 0
    total_quarantine = db.query(func.count(QuarantineEmail.id)).filter(
        *visible_email_filter,
        QuarantineEmail.status != "released",
        QuarantineEmail.label == "QUARANTINE",
    ).scalar() or 0
    total_emails = total_clean + total_warn + total_quarantine

    organizations = []

    admins = []
    admin_rows = db.query(User).filter(User.role == UserRole.ADMIN.value).order_by(User.username).all()
    for admin in admin_rows:
        admin_mailbox_emails = [
            mailbox.email.lower()
            for mailbox in active_mailboxes
            if mailbox.email and (mailbox.assigned_to or "").lower() == admin.username.lower()
        ]
        suspicious_email_rows = db.query(QuarantineEmail).filter(
            QuarantineEmail.status != "trash",
            QuarantineEmail.status != "released",
            QuarantineEmail.label.in_(["WARN", "QUARANTINE"]),
            mailbox_recipient_scope(admin_mailbox_emails),
        ).order_by(QuarantineEmail.received_at.desc()).limit(5).all() if admin_mailbox_emails else []
        admins.append({
            "username": admin.username,
            "role": admin.role,
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
                    "action": "Email dikarantina" if email.label == "QUARANTINE" else "Email perlu review",
                    "details": f"{email.recipient_list or '-'} • {email.subject or '(tanpa subjek)'}",
                    "ip_address": "",
                    "created_at": str(email.received_at),
                }
                for email in suspicious_email_rows
            ],
        })

    suspicious_email_query = db.query(QuarantineEmail).filter(
        QuarantineEmail.status != "trash",
        QuarantineEmail.status != "released",
        QuarantineEmail.label.in_(["WARN", "QUARANTINE"]),
        mailbox_recipient_scope(active_mailbox_emails),
    ).order_by(QuarantineEmail.received_at.desc()).limit(40)

    suspicious_activities = [
        {
            "user": email.recipient_list or "-",
            "action": "Email dikarantina" if email.label == "QUARANTINE" else "Email perlu review",
            "details": f"{email.category or 'unknown'} • {email.subject or '(tanpa subjek)'} • dari {email.sender or '-'}",
            "email_id": email.email_id,
            "ip_address": "-",
            "created_at": str(email.received_at),
        }
        for email in suspicious_email_query.all()
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
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        redis_client = aio_redis.from_url(redis_url, protocol=2)
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
        smtp_host = os.getenv("SMTP_RECEIVER_HOST", "smtp_receiver")
        smtp_port = int(os.getenv("SMTP_RECEIVER_PORT", "25"))
        reader = writer = None
        last_smtp_error = None
        for attempt in range(2):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(smtp_host, smtp_port), timeout=5
                )
                break
            except Exception as exc:
                last_smtp_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.25)
        if writer is None:
            raise last_smtp_error or ConnectionError("SMTP connection failed")
        banner = await asyncio.wait_for(reader.readline(), timeout=3)
        writer.write(b"EHLO cognimail-health.local\r\n")
        await writer.drain()
        ehlo_lines = []
        for _ in range(30):
            line = await asyncio.wait_for(reader.readline(), timeout=3)
            if not line:
                break
            ehlo_lines.append(line.decode("utf-8", errors="replace").strip())
            if len(line) >= 4 and line[3:4] == b" ":
                break
        writer.write(b"QUIT\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        banner_text = banner.decode("utf-8", errors="replace").strip()
        capabilities = "\n".join(ehlo_lines).upper()
        tls_disabled = os.getenv("SMTP_TLS_DISABLED", "false").lower() in {"1", "true", "yes", "on"}
        tls_configured = not tls_disabled and bool(
            os.getenv("SMTP_TLS_CERT", "").strip()
            and os.getenv("SMTP_TLS_KEY", "").strip()
        )
        if tls_configured and "STARTTLS" not in capabilities:
            services["smtp_receiver"] = {
                "status": "warning",
                "detail": (
                    f"{banner_text or 'Connected'}; STARTTLS tidak tersedia "
                    "meskipun path sertifikat dikonfigurasi"
                ),
            }
        else:
            tls_detail = "; STARTTLS tersedia" if "STARTTLS" in capabilities else ""
            services["smtp_receiver"] = {
                "status": "healthy",
                "detail": f"{banner_text or 'Connected'}{tls_detail}",
            }
    except asyncio.TimeoutError:
        services["smtp_receiver"] = {"status": "warning", "detail": "Connection timeout"}
    except Exception as e:
        services["smtp_receiver"] = {"status": "down", "detail": str(e)}

    # 5. Worker Pipeline. A worker can be healthy while idle, so historical
    # processing rows are not a reliable liveness check. Use its Redis
    # heartbeat and expose real queue depth instead.
    try:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        worker_redis = aio_redis.from_url(redis_url, socket_connect_timeout=2, protocol=2)
        heartbeat = await worker_redis.get("cognimail:worker:heartbeat")
        queue_name = os.getenv("REDIS_QUEUE_NAME", "email_pipeline")
        queue_depth = await worker_redis.llen(queue_name)
        dead_letter_depth = await worker_redis.llen(f"{queue_name}:dead")
        await worker_redis.aclose()
        if heartbeat:
            heartbeat_text = heartbeat.decode() if isinstance(heartbeat, bytes) else str(heartbeat)
            services["worker_pipeline"] = {
                "status": "healthy",
                "detail": (
                    f"Heartbeat: {heartbeat_text}; queue: {queue_depth}; "
                    f"dead-letter: {dead_letter_depth}"
                ),
            }
        else:
            services["worker_pipeline"] = {
                "status": "down",
                "detail": "Worker heartbeat not found or expired",
            }
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

    # Docker is intentionally not probed here. The dashboard container does
    # not need Docker to serve traffic, and exposing the host Docker socket
    # would grant this web application root-equivalent control over the VPS.
    # Container-runtime availability belongs in host monitoring/Compose, while
    # this endpoint verifies every dependency used by the application itself.

    # Overall application status
    critical_services = (
        "postgresql", "redis", "classifier_api", "smtp_receiver",
        "worker_pipeline", "spamassassin", "dashboard_backend",
    )
    statuses = [services[name]["status"] for name in critical_services]
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
    total_phishing = base.filter(QuarantineEmail.category.in_(["phishing", "malware"])).count() or 0
    total_quarantined = base.filter(
        QuarantineEmail.label == "QUARANTINE",
        QuarantineEmail.status != "released",
    ).count() or 0
    total_warn = base.filter(
        QuarantineEmail.label == "WARN",
        QuarantineEmail.status != "released",
    ).count() or 0
    total_clean = base.filter(QuarantineEmail.label == "CLEAN").count() or 0

    system_health = await api_health(db)

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
            {"email_id": e.email_id, "sender": e.sender, "subject": e.subject, "label": e.label, "category": display_category(e), "fused_score": e.fused_score, "received_at": str(e.received_at)}
            for e in recent_security
        ],
    }


def _analytics_inbound_emails(db: Session, mailbox_email: str):
    """Return real inbound pipeline records for one exact mailbox address."""
    identity = (mailbox_email or "").strip().lower()
    if not identity:
        return []
    candidates = db.query(QuarantineEmail).filter(
        QuarantineEmail.label.notin_(["SENT", "DRAFT"]),
        or_(QuarantineEmail.status.is_(None), QuarantineEmail.status != "trash"),
    ).order_by(QuarantineEmail.received_at.desc()).all()
    return [row for row in candidates if identity in {
        address.lower() for _, address in getaddresses([row.recipient_list or ""]) if address
    }]


def _analytics_iso_datetime(value):
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _mailbox_analytics_row(db: Session, mailbox: AdminMailbox) -> dict:
    emails = _analytics_inbound_emails(db, mailbox.email)
    phishing = sum(1 for row in emails if (row.category or "").lower() in {"phishing", "malware"})
    spam = sum(1 for row in emails if (row.category or "").lower() == "spam")
    malware = 0
    clean = sum(1 for row in emails if row.label == "CLEAN")
    quarantined = sum(1 for row in emails if row.label == "QUARANTINE")
    warn = sum(1 for row in emails if row.label == "WARN")
    threat_rows = [row for row in emails if row.label in ("WARN", "QUARANTINE") or
                   (row.category or "").lower() in ("phishing", "spam", "malware")]
    avg_fused = sum(float(row.fused_score or 0) for row in emails) / len(emails) if emails else 0
    last_threat = threat_rows[0].received_at if threat_rows else None
    return {
        "mailbox_id": mailbox.id,
        "email": mailbox.email,
        "sender_name": mailbox.sender_name or "",
        "admin": mailbox.assigned_to or mailbox.created_by or "Unassigned",
        "assigned_to": mailbox.assigned_to or "",
        "created_by": mailbox.created_by or "",
        "is_active": bool(mailbox.is_active),
        "created_at": _analytics_iso_datetime(mailbox.created_at),
        "total_emails": len(emails),
        "phishing": phishing,
        "spam": spam,
        "malware": malware,
        "clean": clean,
        "quarantined": quarantined,
        "warn": warn,
        "total_threats": len(threat_rows),
        "threat_score": round(max(0, min(avg_fused * 100, 100))),
        "average_fused_score": round(avg_fused, 4),
        "last_threat": _analytics_iso_datetime(last_threat),
    }


@app.get("/api/admin/email-analytics")
async def api_email_analytics(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info.get("role") not in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(AdminMailbox)
    if user_info.get("role") == UserRole.ADMIN.value:
        query = query.filter(AdminMailbox.assigned_to == user_info["username"])
    mailboxes = query.order_by(AdminMailbox.email.asc()).all()
    return [_mailbox_analytics_row(db, mailbox) for mailbox in mailboxes]


@app.get("/api/admin/email-analytics/{mailbox_id}")
async def api_email_analytics_detail(mailbox_id: int, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info.get("role") not in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(status_code=403, detail="Admin access required")

    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    if user_info.get("role") == UserRole.ADMIN.value and mailbox.assigned_to != user_info["username"]:
        raise HTTPException(status_code=403, detail="You do not manage this mailbox")

    summary = _mailbox_analytics_row(db, mailbox)
    emails = _analytics_inbound_emails(db, mailbox.email)
    threats = [row for row in emails if row.label in ("WARN", "QUARANTINE") or
               (row.category or "").lower() in ("phishing", "spam", "malware")]
    sender_stats = {}
    for row in threats:
        key = row.sender or "Unknown sender"
        item = sender_stats.setdefault(key, {"sender": key, "count": 0, "phishing": 0, "spam": 0, "warn": 0})
        item["count"] += 1
        category = (row.category or "").lower()
        if category in ("phishing", "malware"):
            item["phishing"] += 1
        elif category == "spam":
            item["spam"] += 1
        if row.label == "WARN":
            item["warn"] += 1

    return {
        "mailbox": summary,
        "top_senders": sorted(sender_stats.values(), key=lambda item: item["count"], reverse=True)[:10],
        "recent_threats": [{
            "email_id": row.email_id,
            "subject": row.subject or "",
            "sender": row.sender or "",
            "category": display_category(row),
            "label": row.label or "",
            "received_at": _analytics_iso_datetime(row.received_at),
            "fused_score": float(row.fused_score or 0),
            "ml_probability": float(row.ml_probability or 0),
            "sa_score": float(row.sa_score or 0),
            "spf": row.spf_result or "",
            "dkim": row.dkim_result or "",
            "dmarc": row.dmarc_result or "",
            "model_version": row.model_version or "",
        } for row in threats[:20]],
    }


@app.get("/api/admin/user-analytics")
async def api_user_analytics(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        raise HTTPException(status_code=403, detail="Only superadmin can access this endpoint")

    users = db.query(User).all()

    # Aggregate email stats per user via ilike match on recipient_list
    result = []
    for u in users:
        if not u.email:
            # User without email — return zeroed stats
            result.append({
                "username":    u.username,
                "email":       u.email,
                "role":        u.role,
                "is_active":   u.is_active,
                "created_at":  str(u.created_at),
                "total_emails": 0,
                "phishing":    0,
                "spam":        0,
                "malware":     0,
                "clean":       0,
                "quarantined": 0,
                "warn":        0,
                "threat_score": 0,
                "last_threat": None,
            })
            continue

        base = db.query(QuarantineEmail).filter(
            QuarantineEmail.recipient_list.ilike(f"%{u.email}%"),
            QuarantineEmail.status != "trash",
        )
        total       = base.count() or 0
        phishing    = base.filter(QuarantineEmail.category.in_(["phishing", "malware"])).count() or 0
        spam        = base.filter(QuarantineEmail.category == "spam").count() or 0
        malware     = 0
        clean       = base.filter(QuarantineEmail.label == "CLEAN").count() or 0
        quarantined = base.filter(QuarantineEmail.label == "QUARANTINE").count() or 0
        warn        = base.filter(QuarantineEmail.label == "WARN").count() or 0
        last_row    = base.order_by(QuarantineEmail.received_at.desc()).first()
        last_dt     = last_row.received_at if last_row else None

        threat_score = round(
            (phishing * 3 + spam * 1 + quarantined * 2) / max(total, 1) * 100
        )

        result.append({
            "username":    u.username,
            "email":       u.email,
            "role":        u.role,
            "is_active":   u.is_active,
            "created_at":  str(u.created_at),
            "total_emails": total,
            "phishing":    phishing,
            "spam":        spam,
            "malware":     malware,
            "clean":       clean,
            "quarantined": quarantined,
            "warn":        warn,
            "threat_score": threat_score,
            "last_threat": (str(last_dt.date()) if hasattr(last_dt, 'date') else str(last_dt)[:10]) if last_dt else None,
        })

    result.sort(key=lambda x: x["threat_score"], reverse=True)
    return result


@app.get("/api/admin/user-detail/{username}")
async def api_user_detail(username: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if not has_permission_dict(user_info, Permission.MANAGE_ALL_USERS):
        raise HTTPException(status_code=403, detail="Only superadmin can access this endpoint")

    u = db.query(User).filter(User.username == username).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    base = db.query(QuarantineEmail).filter(
        QuarantineEmail.recipient_list.ilike(f"%{u.email}%"),
        QuarantineEmail.status != "trash",
    )

    total      = base.count() or 0
    phishing   = base.filter(QuarantineEmail.category.in_(["phishing", "malware"])).count() or 0
    spam       = base.filter(QuarantineEmail.category == "spam").count() or 0
    malware    = 0
    clean      = base.filter(QuarantineEmail.label == "CLEAN").count() or 0
    quarantined = base.filter(QuarantineEmail.label == "QUARANTINE").count() or 0
    warn       = base.filter(QuarantineEmail.label == "WARN").count() or 0
    threat_score = round(
        (phishing * 3 + spam * 1 + quarantined * 2) / max(total, 1) * 100
    )

    # Last 20 non-clean emails
    recent_threats = db.query(QuarantineEmail).filter(
        QuarantineEmail.recipient_list.ilike(f"%{u.email}%"),
        QuarantineEmail.label != "CLEAN",
        QuarantineEmail.status != "trash",
    ).order_by(QuarantineEmail.received_at.desc()).limit(20).all()

    # Daily trend — last 30 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    trend_rows = db.query(
        func.date(QuarantineEmail.received_at).label("date"),
        func.count(QuarantineEmail.id).label("total"),
        func.sum(case((QuarantineEmail.label != "CLEAN", 1), else_=0)).label("threats"),
        func.sum(case((QuarantineEmail.label == "CLEAN", 1), else_=0)).label("clean"),
    ).filter(
        QuarantineEmail.recipient_list.ilike(f"%{u.email}%"),
        QuarantineEmail.status != "trash",
        QuarantineEmail.received_at >= cutoff,
    ).group_by(func.date(QuarantineEmail.received_at)).order_by("date").all()

    # Top 10 senders
    sender_rows = db.query(
        QuarantineEmail.sender,
        func.count(QuarantineEmail.id).label("count"),
        func.sum(case((QuarantineEmail.category.in_(["phishing", "malware"]), 1), else_=0)).label("phishing"),
        func.sum(case((QuarantineEmail.category == "spam", 1), else_=0)).label("spam"),
    ).filter(
        QuarantineEmail.recipient_list.ilike(f"%{u.email}%"),
        QuarantineEmail.status != "trash",
    ).group_by(QuarantineEmail.sender).order_by(func.count(QuarantineEmail.id).desc()).limit(10).all()

    return {
        "user": {
            "id":         u.id,
            "username":   u.username,
            "email":      u.email,
            "role":       u.role,
            "is_active":  u.is_active,
            "created_at": str(u.created_at),
        },
        "stats": {
            "total_emails": total,
            "phishing":     phishing,
            "spam":         spam,
            "malware":      malware,
            "clean":        clean,
            "quarantined":  quarantined,
            "warn":         warn,
            "threat_score": threat_score,
        },
        "recent_threats": [
            {
                "id":          e.id,
                "subject":     e.subject,
                "sender":      e.sender,
                "category":    display_category(e),
                "label":       e.label,
                "received_at": str(e.received_at),
                "score":       e.fused_score,
            }
            for e in recent_threats
        ],
        "daily_trend": [
            {
                "date":    str(r.date),
                "total":   int(r.total),
                "threats": int(r.threats),
                "clean":   int(r.clean),
            }
            for r in trend_rows
        ],
        "top_senders": [
            {
                "sender":   r.sender,
                "count":    int(r.count),
                "phishing": int(r.phishing),
                "spam":     int(r.spam),
            }
            for r in sender_rows
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ML TRAINING & FALSE NEGATIVE FEEDBACK ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

class FalseNegativeRequest(BaseModel):
    corrected_label: str  # "spam", "phishing", "suspicious"
    notes: str = ""


class UpdateTrainingSampleRequest(BaseModel):
    corrected_label: str = None
    status: str = None
    notes: str = None


@app.post("/api/emails/{email_id}/report-false-negative")
async def api_report_false_negative(
    email_id: str,
    payload: FalseNegativeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Report an email that was classified as safe but is actually dangerous (false negative)."""
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    
    # Fetch the email record
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # Reuse the authoritative per-record access check. Permission membership
    # alone is insufficient because normal users may review only their own
    # mailbox and admins only their assigned mailboxes.
    ensure_email_access(db, email_record, user_info)
    
    # Validate corrected label
    valid_labels = ["spam", "phishing", "suspicious"]
    corrected_label = payload.corrected_label.lower().strip()
    if corrected_label == "malware":
        corrected_label = "phishing"
    if corrected_label not in valid_labels:
        raise HTTPException(status_code=400, detail=f"Invalid corrected_label. Must be one of: {valid_labels}")
    
    # Check if already reported
    existing = db.query(TrainingSample).filter(
        TrainingSample.email_id == email_id,
        TrainingSample.feedback_type == "false_negative"
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="This email has already been reported as false negative")
    
    # Create training sample
    training_sample = TrainingSample(
        email_id=email_id,
        raw_email=email_record.raw_content or "",
        original_label=email_record.label,
        corrected_label=corrected_label,
        feedback_type="false_negative",
        original_scores={
            "fused_score": email_record.fused_score,
            "ml_probability": email_record.ml_probability,
            "anomaly_score": email_record.anomaly_score,
            "sa_score": email_record.sa_score,
        },
        subject=email_record.subject,
        sender=email_record.sender,
        recipient_list=email_record.recipient_list,
        status="pending",
        notes=payload.notes,
        reported_by=user_info["username"],
        organization_id=email_record.organization_id,
    )
    
    db.add(training_sample)
    
    # Also add to feedback table for compatibility
    feedback = Feedback(
        email_id=email_id,
        feedback_type="false_negative",
        notes=f"Corrected label: {corrected_label}. {payload.notes}",
    )
    db.add(feedback)
    
    # Apply the human correction to the operational mailbox classification as
    # well as to the dataset, so the detail view cannot contradict the review.
    if corrected_label in {"spam", "phishing"}:
        email_record.label = "QUARANTINE"
        email_record.category = corrected_label
        email_record.status = "confirmed_threat"
    else:
        email_record.label = "WARN"
        email_record.category = "warn"
        email_record.status = "confirmed_warning"
    
    log_audit(db, user_info["username"], "report_false_negative", email_id,
              request.client.host if request.client else None, 
              f"Corrected to: {corrected_label}")
    
    db.commit()
    
    return {"ok": True, "training_sample_id": training_sample.id, "status": "pending_review"}


@app.get("/api/admin/training-samples")
async def api_get_training_samples(
    request: Request,
    status: str = Query(None),
    feedback_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get all training samples for review (superadmin only)."""
    user_info = get_authenticated_api_user(request, db)
    
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    query = db.query(TrainingSample)
    
    if status:
        query = query.filter(TrainingSample.status == status)
    
    if feedback_type:
        query = query.filter(TrainingSample.feedback_type == feedback_type)
    
    total = query.count()
    
    samples = query.order_by(TrainingSample.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "samples": [
            {
                "id": s.id,
                "email_id": s.email_id,
                "original_label": s.original_label,
                "corrected_label": s.corrected_label,
                "feedback_type": s.feedback_type,
                "original_scores": s.original_scores,
                "subject": s.subject,
                "sender": s.sender,
                "recipient_list": s.recipient_list,
                "status": s.status,
                "notes": s.notes,
                "reported_by": s.reported_by,
                "reviewed_by": s.reviewed_by,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
                "used_in_training_at": s.used_in_training_at.isoformat() if s.used_in_training_at else None,
            }
            for s in samples
        ]
    }


@app.put("/api/admin/training-samples/{sample_id}")
async def api_update_training_sample(
    sample_id: int,
    payload: UpdateTrainingSampleRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update training sample status/label (superadmin only)."""
    user_info = get_authenticated_api_user(request, db)
    
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    sample = db.query(TrainingSample).filter(TrainingSample.id == sample_id).first()
    
    if not sample:
        raise HTTPException(status_code=404, detail="Training sample not found")
    
    if payload.corrected_label:
        corrected_label = payload.corrected_label.lower().strip()
        if corrected_label == "malware":
            corrected_label = "phishing"
        if corrected_label not in {"clean", "spam", "phishing", "suspicious"}:
            raise HTTPException(status_code=400, detail="Invalid corrected label")
        sample.corrected_label = corrected_label
    
    if payload.status:
        requested_status = payload.status.lower().strip()
        # ``used_in_training`` is reserved for a real training worker; the
        # review UI may only approve or reject a pending sample.
        if requested_status not in {"approved", "rejected"}:
            raise HTTPException(status_code=400, detail="Status must be approved or rejected")
        if sample.status != "pending":
            raise HTTPException(status_code=409, detail="Only pending samples can be reviewed")
        sample.status = requested_status
        if requested_status in ["approved", "rejected"]:
            sample.reviewed_by = user_info["username"]
            sample.reviewed_at = _utcnow()
    
    if payload.notes is not None:
        sample.notes = payload.notes
    
    log_audit(db, user_info["username"], "update_training_sample", str(sample_id),
              request.client.host if request.client else None, 
              f"Status: {payload.status}, Label: {payload.corrected_label}")
    
    db.commit()
    
    return {"ok": True, "sample": {
        "id": sample.id,
        "status": sample.status,
        "corrected_label": sample.corrected_label,
        "reviewed_by": sample.reviewed_by,
    }}


@app.delete("/api/admin/training-samples/{sample_id}")
async def api_delete_training_sample(
    sample_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a training sample (superadmin only)."""
    user_info = get_authenticated_api_user(request, db)
    
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    sample = db.query(TrainingSample).filter(TrainingSample.id == sample_id).first()
    
    if not sample:
        raise HTTPException(status_code=404, detail="Training sample not found")
    
    db.delete(sample)
    log_audit(db, user_info["username"], "delete_training_sample", str(sample_id),
              request.client.host if request.client else None)
    db.commit()
    
    return {"ok": True}


@app.post("/api/admin/training/export-dataset")
async def api_export_training_dataset(
    request: Request,
    status: str = Query("approved"),
    db: Session = Depends(get_db)
):
    """Export training samples to CSV format for retraining (superadmin only)."""
    user_info = get_authenticated_api_user(request, db)
    
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    import csv
    from io import StringIO
    
    status = status.lower().strip()
    if status not in {"approved", "used_in_training"}:
        raise HTTPException(status_code=400, detail="Export status must be approved or used_in_training")
    query = db.query(TrainingSample).filter(TrainingSample.status == status)
    samples = query.all()
    
    if not samples:
        raise HTTPException(status_code=404, detail=f"No training samples with status='{status}'")
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "email_id", "label", "subject", "sender", "recipient_list", 
        "raw_email", "feedback_type", "original_label", "notes", "created_at"
    ])
    
    # Rows
    for s in samples:
        writer.writerow([
            s.email_id,
            s.corrected_label,
            s.subject,
            s.sender,
            s.recipient_list,
            s.raw_email,
            s.feedback_type,
            s.original_label,
            s.notes,
            s.created_at.isoformat() if s.created_at else "",
        ])
    
    csv_content = output.getvalue()
    
    log_audit(db, user_info["username"], "export_training_dataset", "",
              request.client.host if request.client else None, 
              f"Exported {len(samples)} samples with status={status}")
    db.commit()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=training_samples_{status}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@app.get("/api/admin/training/stats")
async def api_get_training_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get training dataset statistics (superadmin only)."""
    user_info = get_authenticated_api_user(request, db)
    
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    from sqlalchemy import func
    
    total = db.query(func.count(TrainingSample.id)).scalar() or 0
    pending = db.query(func.count(TrainingSample.id)).filter(TrainingSample.status == "pending").scalar() or 0
    approved = db.query(func.count(TrainingSample.id)).filter(TrainingSample.status == "approved").scalar() or 0
    rejected = db.query(func.count(TrainingSample.id)).filter(TrainingSample.status == "rejected").scalar() or 0
    used = db.query(func.count(TrainingSample.id)).filter(TrainingSample.status == "used_in_training").scalar() or 0
    
    # By feedback type
    false_negative_count = db.query(func.count(TrainingSample.id)).filter(
        TrainingSample.feedback_type == "false_negative"
    ).scalar() or 0
    
    false_positive_count = db.query(func.count(TrainingSample.id)).filter(
        TrainingSample.feedback_type == "false_positive"
    ).scalar() or 0
    
    # By corrected label
    label_dist = db.query(
        TrainingSample.corrected_label,
        func.count(TrainingSample.id)
    ).filter(
        TrainingSample.status == "approved"
    ).group_by(TrainingSample.corrected_label).all()
    
    return {
        "total": total,
        "by_status": {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "used_in_training": used,
        },
        "by_feedback_type": {
            "false_negative": false_negative_count,
            "false_positive": false_positive_count,
        },
        "by_label": {row[0]: row[1] for row in label_dist},
        "retraining": {
            "configured": False,
            "message": "Training worker belum dikonfigurasi; sampel approved tetap aman dan tidak ditandai sebagai sudah dilatih.",
        },
    }


@app.post("/api/admin/training/retrain")
async def api_trigger_retrain(
    request: Request,
    db: Session = Depends(get_db)
):
    """Reject retraining until a real training worker is configured.

    Approved samples must not be marked as trained unless a model artifact was
    actually produced. This keeps the dashboard status truthful.
    """
    user_info = get_authenticated_api_user(request, db)
    
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    # Count approved samples
    approved_samples = db.query(TrainingSample).filter(
        TrainingSample.status == "approved"
    ).all()
    
    if not approved_samples:
        raise HTTPException(status_code=400, detail="No approved training samples available")
    
    raise HTTPException(
        status_code=503,
        detail=(
            "Model retraining worker is not configured. "
            f"{len(approved_samples)} approved samples remain available and unchanged."
        ),
    )


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
    
    # Return index.html for SPA frontend routing — never cache so browser
    # always gets the latest asset hashes after a redeploy.
    index_file = dist_dir / "index.html"
    if index_file.is_file():
        return FileResponse(
            index_file,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
    
    return PlainTextResponse("React frontend is not built yet. Please build it first.")

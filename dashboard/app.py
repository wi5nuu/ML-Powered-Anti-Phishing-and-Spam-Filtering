"""
LTI Anti-Phishing Dashboard — Enterprise Edition.

Features:
  1. JWT authentication with RBAC (admin/analyst/viewer)
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
import json
import logging
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import secrets as _secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
import httpx
import redis.asyncio as aio_redis

from pydantic import BaseModel
import csv
import io
from fastapi import FastAPI, Request, Depends, Form, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator

from database.models import QuarantineEmail, Feedback, User, AuditLog, Organization, PipelineMetrics, Report
from dashboard.database import get_db, SessionLocal
from dashboard.auth import (
    hash_password, verify_password, create_access_token, decode_token, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user, require_role, log_audit, verify_api_key
)

logger = logging.getLogger(__name__)

DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY")
if not DASHBOARD_SECRET_KEY:
    DASHBOARD_SECRET_KEY = _secrets.token_hex(32)
    logger.warning("DASHBOARD_SECRET_KEY not set. Generated ephemeral key.")

static_dir = Path(__file__).parent / "static"

app = FastAPI(title="LTI Anti-Phishing Dashboard", version="3.0.0")
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
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if os.getenv("ENV", "development") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")




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
        try:
            r = await aio_redis.from_url(REDIS_URL_WS)
            async with r.pubsub() as pubsub:
                await pubsub.subscribe(PUBSUB_CHANNEL)
                logger.info("Redis pub/sub bridge started on channel: %s", PUBSUB_CHANNEL)
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await manager.broadcast(data)
                        except Exception as e:
                            logger.warning("pubsub_bridge_parse_error: %s", e)
        except Exception as e:
            logger.error("pubsub_bridge_error: %s, reconnecting in 5s...", e)
            await asyncio.sleep(5)


@app.on_event("startup")
async def start_pubsub_bridge():
    asyncio.create_task(redis_pubsub_bridge())


# ─── Seed Admin User ────────────────────────────────────────────────────────────

def seed_admin():
    db = SessionLocal()
    
    # 1. Super Admin
    superadmin_username = "superadmin"
    superadmin_password = os.getenv("SUPERADMIN_PASSWORD", "SuperAdminPassword123!")
    superadmin_email = os.getenv("SUPERADMIN_EMAIL", "saltiantiphishing@gmail.com")
    superadmin = db.query(User).filter(User.username == superadmin_username).first()
    if not superadmin:
        superadmin = User(
            username=superadmin_username,
            email=superadmin_email,
            hashed_password=hash_password(superadmin_password),
            role="superadmin",
        )
        db.add(superadmin)
        logger.info("Super admin user seeded.")
    else:
        superadmin.hashed_password = hash_password(superadmin_password)
        superadmin.role = "superadmin"
        superadmin.email = superadmin_email
        logger.info("Super admin user password/role updated.")
        
    # 2. Admin
    admin_username = "admin"
    admin_password = os.getenv("ADMIN_PASSWORD", "AdminPassword123!")
    admin = db.query(User).filter(User.username == admin_username).first()
    if not admin:
        admin = User(
            username=admin_username,
            hashed_password=hash_password(admin_password),
            role="admin",
        )
        db.add(admin)
        logger.info("Admin user seeded.")
    else:
        admin.hashed_password = hash_password(admin_password)
        admin.role = "admin"
        logger.info("Admin user password/role updated.")

    # 3. Analyst (reviewer)
    reviewer_username = "reviewer"
    reviewer_password = os.getenv("REVIEWER_PASSWORD", "ReviewerPassword123!")
    reviewer = db.query(User).filter(User.username == reviewer_username).first()
    if not reviewer:
        reviewer = User(
            username=reviewer_username,
            hashed_password=hash_password(reviewer_password),
            role="analyst",
        )
        db.add(reviewer)
        logger.info("Analyst user seeded.")
    else:
        reviewer.hashed_password = hash_password(reviewer_password)
        reviewer.role = "analyst"
        logger.info("Analyst user password/role updated.")

    db.commit()
    db.close()

seed_admin()


# ─── Auth Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/auth/me")
async def auth_me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"auth_me: client={client_host} cookie_present={bool(token)} url={request.url.path}")
    if not token:
        logger.warning(f"auth_me: no cookie from {client_host}")
        return JSONResponse({"authenticated": False, "user": None})
    try:
        payload = decode_token(token)
        user = db.query(User).filter(User.username == payload.get("sub")).first()
        if not user or not user.is_active:
            logger.warning(f"auth_me: user {payload.get('sub')} not found/inactive")
            return JSONResponse({"authenticated": False, "user": None})
        logger.info(f"auth_me: authenticated user={user.username} role={user.role}")
        return JSONResponse({
            "authenticated": True,
            "user": {"username": user.username, "role": user.role}
        })
    except Exception as e:
        logger.warning(f"auth_me: token decode failed: {e}")
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
    response = JSONResponse({"access_token": token, "token_type": "bearer", "role": user.role})
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
    response = JSONResponse({"ok": True})
    response.delete_cookie("access_token")
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
    redirect_url = "/admin" if user.role in ("superadmin", "admin") else "/inbox"
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
    if len(new_pw) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    user.hashed_password = hash_password(new_pw)
    db.commit()
    log_audit(db, user.username, "change_password", details="Password changed")
    return {"ok": True, "message": "Password changed successfully"}


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
    raw_key = f"lti_{secrets.token_hex(24)}"
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
async def feedback_export(db: Session = Depends(get_db)):
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
    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    quarantine_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE"
    ).scalar() or 0
    warn_count = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0
    clean_count = total - quarantine_count - warn_count
    avg_anomaly = db.query(func.avg(QuarantineEmail.anomaly_score)).scalar() or 0
    avg_fused = db.query(func.avg(QuarantineEmail.fused_score)).scalar() or 0
    # Per-category breakdown
    cat_rows = db.query(
        QuarantineEmail.category, func.count(QuarantineEmail.id)
    ).filter(
        QuarantineEmail.category != ""
    ).group_by(QuarantineEmail.category).all()
    categories = {row[0]: row[1] for row in cat_rows}
    return {
        "total": total,
        "quarantine": quarantine_count,
        "warn": warn_count,
        "clean": clean_count,
        "avg_anomaly_score": round(float(avg_anomaly), 4),
        "avg_fused_score": round(float(avg_fused), 4),
        "categories": categories,
    }


# ─── New API Endpoints & SPA Routing ───────────────────────────────────────────

def get_authenticated_api_user(request: Request, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        logger.warning(f"get_authenticated_api_user: no cookie from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
        user = db.query(User).filter(User.username == payload.get("sub")).first()
        if not user or not user.is_active:
            logger.warning(f"get_authenticated_api_user: user {payload.get('sub')} not found or inactive")
            raise HTTPException(status_code=401, detail="Account is disabled or inactive")
        return {"username": user.username, "role": user.role}
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

CATEGORY_ICONS = {
    "transaction": "receipt",
    "customer_service": "support",
    "internal_document": "folder",
    "b2b": "briefcase",
    "spam": "spam",
    "phishing": "phishing",
    "malware": "bug",
}


@app.get("/api/emails")
async def api_get_emails(
    request: Request,
    label: str = Query(None),
    category: str = Query(None),
    q: str = Query(None),
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    
    query = db.query(QuarantineEmail)
    
    if category and category in CATEGORY_LABEL_MAP:
        mapped_label = CATEGORY_LABEL_MAP[category]
        query = query.filter(QuarantineEmail.label == mapped_label, QuarantineEmail.category == category)
    elif label:
        query = query.filter(QuarantineEmail.label == label)
    
    if q:
        query = query.filter(
            QuarantineEmail.subject.ilike(f"%{q}%") | 
            QuarantineEmail.sender.ilike(f"%{q}%")
        )
    
    total = query.count()
    emails = query.order_by(QuarantineEmail.fused_score.desc()).limit(100).all()
    
    emails_data = []
    for email in emails:
        cat = email.category if hasattr(email, 'category') and email.category else email.label
        emails_data.append({
            "email_id": email.email_id,
            "sender": email.sender,
            "subject": email.subject,
            "label": email.label,
            "category": cat,
            "status": email.status,
            "fused_score": email.fused_score,
            "ml_probability": 0.0 if user_info["role"] == "user" else email.ml_probability,
            "sa_score": 0.0 if user_info["role"] == "user" else email.sa_score,
            "anomaly_score": 0.0 if user_info["role"] == "user" else email.anomaly_score,
            "received_at": email.received_at.isoformat() if hasattr(email.received_at, "isoformat") else str(email.received_at) if email.received_at else None,
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

    is_regular_user = (user_info["role"] == "user")
    if is_regular_user:
        username_lower = user_info["username"].lower()
        recipients_lower = (email_record.recipient_list or "").lower()
        if username_lower not in recipients_lower:
            raise HTTPException(status_code=403, detail="You do not have permission to view this email")

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

    ecat = email_record.category if hasattr(email_record, 'category') and email_record.category else email_record.label
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
    }


@app.post("/api/emails/{email_id}/release")
async def api_release_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "security_admin", "mail_reviewer"]:
        raise HTTPException(status_code=403, detail="You do not have permission to manage quarantine")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    email_record.status = "released"
    log_audit(db, user_info["username"], "release", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "released"}


@app.post("/api/emails/{email_id}/confirm-spam")
async def api_confirm_spam(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "security_admin", "mail_reviewer"]:
        raise HTTPException(status_code=403, detail="You do not have permission to manage quarantine")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    email_record.status = "confirmed_spam"
    log_audit(db, user_info["username"], "confirm_spam", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "confirmed_spam"}


@app.post("/api/emails/{email_id}/report-false-positive")
async def api_report_false_positive(
    email_id: str,
    payload: FalsePositiveRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "security_admin", "mail_reviewer"]:
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
    if user_info["role"] not in ["superadmin", "security_admin"]:
        raise HTTPException(status_code=403, detail="You do not have permission to delete emails")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    db.delete(email_record)
    log_audit(db, user_info["username"], "delete", email_id,
              request.client.host if request.client else None)
    db.commit()
    return {"ok": True, "status": "deleted"}


@app.get("/api/metrics")
async def api_get_metrics(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "security_admin", "mail_reviewer"]:
        raise HTTPException(status_code=403, detail="You do not have permission to view model reports")
    
    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    quarantine_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE"
    ).scalar() or 0
    warn_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "WARN"
    ).scalar() or 0
    clean_count = total - quarantine_count - warn_count

    top_senders_db = db.query(
        QuarantineEmail.sender, func.count(QuarantineEmail.id).label("count")
    ).group_by(QuarantineEmail.sender).order_by(
        func.count(QuarantineEmail.id).desc()
    ).limit(10).all()
    
    top_senders = [{"sender": s, "count": c} for s, c in top_senders_db]

    feedback_count = db.query(func.count(Feedback.id)).scalar() or 0

    daily_stats_db = db.query(
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
    """Paginated audit log. Requires security_admin or above."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "security_admin"]:
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
    """Get current system settings. Requires security_admin or above."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "security_admin"]:
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
    if user_info["role"] not in ["superadmin", "security_admin"]:
        raise HTTPException(status_code=403, detail="Only security_admin or above can change settings")

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
    if user_info["role"] not in ["superadmin", "security_admin"]:
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
    """Export email log as CSV. Requires security_admin or above."""
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ["superadmin", "security_admin", "mail_reviewer"]:
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
    filename = f"lti_email_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
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
            from decision_engine.fusion import fuse
            from decision_engine.xai import generate_reasons

            parser = EmailParser()
            parsed = parser.parse(payload.raw_email)
            extractor = FeatureExtractor()
            features = extractor.extract(parsed)

            result = {
                "email_id": f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "classification": "unknown",
                "confidence": 0.0,
                "spam_score": 0.0,
                "risk_level": "UNKNOWN",
                "reasons": ["Classifier service unavailable — running in fallback mode"],
                "url_analysis": [],
                "recommended_action": "manual_review",
                "processing_time_ms": 0,
                "subject": parsed.subject if hasattr(parsed, 'subject') else "",
                "sender": parsed.from_addr if hasattr(parsed, 'from_addr') else "",
                "ml_probability": 0.0,
                "sa_score": 0.0,
                "anomaly_score": 0.0,
                "fused_score": 0.0,
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
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can manage users")
    users = db.query(User).all()
    return [{"username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]


@app.post("/api/admin/users")
async def api_create_user(request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can manage users")
    username = payload.get("username")
    password = payload.get("password")
    role = payload.get("role", "user")
    email = payload.get("email", "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
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
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can change system settings")
    return {"ok": True, "message": "System settings updated successfully"}


@app.put("/api/admin/users/{username}")
async def api_update_user(username: str, request: Request, payload: dict, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can manage users")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
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
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can manage users")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    return {"ok": True, "message": f"User {username} disabled"}


@app.get("/api/admin/audit-logs")
async def api_get_audit_logs(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view audit logs")
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {"user": l.user, "action": l.action, "email_id": l.email_id, "details": l.details, "created_at": str(l.created_at)}
        for l in logs
    ]


@app.get("/api/admin/stats")
async def api_admin_stats(request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_api_user(request, db)
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Only superadmin/admin can view stats")
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_emails = db.query(QuarantineEmail).count()
    clean_count = db.query(QuarantineEmail).filter(QuarantineEmail.status == "CLEAN").count()
    warn_count = db.query(QuarantineEmail).filter(QuarantineEmail.status == "WARN").count()
    quarantine_count = db.query(QuarantineEmail).filter(QuarantineEmail.status == "QUARANTINE").count()
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
            report.resolved_at = datetime.utcnow()
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
    if user_info["role"] not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    users = db.query(User).filter(User.is_active == True).all()
    result = []
    for u in users:
        total = db.query(QuarantineEmail).count()
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
    emails = db.query(QuarantineEmail).order_by(QuarantineEmail.created_at.desc()).limit(200).all()
    return [
        {
            "email_id": e.email_id, "subject": e.subject, "sender": e.sender,
            "label": e.label, "status": e.status, "fused_score": e.fused_score,
            "category": e.category, "received_at": e.received_at,
        }
        for e in emails
    ]


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

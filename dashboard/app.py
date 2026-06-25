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
import secrets as _secrets
from datetime import datetime, timedelta
from pathlib import Path
import redis.asyncio as aio_redis

from fastapi import FastAPI, Request, Depends, Form, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

from database.models import QuarantineEmail, Feedback, User, AuditLog, Organization, PipelineMetrics
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

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

app = FastAPI(title="LTI Anti-Phishing Dashboard", version="3.0.0")
Instrumentator().instrument(app).expose(app)

csrf_secret = os.getenv("DASHBOARD_SECRET_KEY") or _secrets.token_hex(32)
app.add_middleware(SessionMiddleware, secret_key=csrf_secret, same_site="lax", https_only=False)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(","))
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8081").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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
templates = Jinja2Templates(directory=str(templates_dir))
templates.env.autoescape = True
templates.env.globals["max"] = max
templates.env.globals["min"] = min
templates.env.globals["zip"] = zip




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
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin_password = os.getenv("ADMIN_PASSWORD", "changeme")
        if admin_password == "changeme":
            logger.warning("ADMIN_PASSWORD is still the default 'changeme'. Set a strong password via env.")  # nosec
        admin = User(
            username=os.getenv("ADMIN_USERNAME", "admin"),
            hashed_password=hash_password(admin_password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        logger.info("Admin user seeded.")
    db.close()

seed_admin()


# ─── Auth Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/auth/me")
async def auth_me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return JSONResponse({"authenticated": False, "user": None})
    try:
        payload = decode_token(token)
        user = db.query(User).filter(User.username == payload.get("sub")).first()
        if not user or not user.is_active:
            return JSONResponse({"authenticated": False, "user": None})
        return JSONResponse({
            "authenticated": True,
            "user": {"username": user.username, "role": user.role}
        })
    except Exception:
        return JSONResponse({"authenticated": False, "user": None})


@app.post("/api/auth/login")
@limiter.limit("20/minute")
async def auth_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
                     db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "Invalid username or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    token = create_access_token({"sub": user.username, "role": user.role})
    response = JSONResponse({"access_token": token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=os.getenv("ENV", "development") == "production"
    )
    return response


@app.post("/api/auth/logout")
async def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("access_token")
    return response


# ─── Login Page ─────────────────────────────────────────────────────────────────

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


# ─── Dashboard Middleware ───────────────────────────────────────────────────────

def get_authenticated_user(request: Request, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise RedirectResponse(url="/login", status_code=303)
    try:
        payload = decode_token(token)
        user = db.query(User).filter(User.username == payload.get("sub")).first()
        if not user or not user.is_active:
            raise RedirectResponse(url="/login", status_code=303)
        return {"username": user.username, "role": user.role}
    except Exception:
        raise RedirectResponse(url="/login", status_code=303)


# ─── Main Pages ─────────────────────────────────────────────────────────────────

@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user_info = None
    if token:
        try:
            payload = decode_token(token)
            user = db.query(User).filter(User.username == payload.get("sub")).first()
            if user and user.is_active:
                user_info = {"username": user.username, "role": user.role}
        except Exception:
            pass

    emails = db.query(QuarantineEmail).order_by(
        QuarantineEmail.fused_score.desc()
    ).limit(100).all()

    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    quarantine_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE"
    ).scalar() or 0
    warn_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "WARN"
    ).scalar() or 0
    feedback_count = db.query(func.count(Feedback.id)).scalar() or 0

    return templates.TemplateResponse(request, "quarantine.html", {
        "emails": emails,
        "total": total,
        "quarantine_count": quarantine_count,
        "warn_count": warn_count,
        "feedback_count": feedback_count,
        "user": user_info,
    })


@app.get("/email/{email_id}")
async def email_detail(email_id: str, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user_info = None
    if token:
        try:
            payload = decode_token(token)
            user = db.query(User).filter(User.username == payload.get("sub")).first()
            if user and user.is_active:
                user_info = {"username": user.username, "role": user.role}
        except Exception:
            pass

    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(404, "Email not found")

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

    return templates.TemplateResponse(request, "email_detail.html", {
        "email": email_record,
        "reasons": reasons,
        "human_reasons": human_reasons,
        "shap_data": shap_data,
        "user": user_info,
    })


@app.post("/email/{email_id}/release")
async def release_email(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_user(request, db)
    if user_info["role"] == "viewer":
        raise HTTPException(403, "Viewers cannot release emails")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(404, "Email not found")
    email_record.status = "released"
    log_audit(db, user_info["username"], "release", email_id,
              request.client.host if request.client else None)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/email/{email_id}/confirm-spam")
async def confirm_spam(email_id: str, request: Request, db: Session = Depends(get_db)):
    user_info = get_authenticated_user(request, db)
    if user_info["role"] == "viewer":
        raise HTTPException(403, "Viewers cannot confirm spam")
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(404, "Email not found")
    email_record.status = "confirmed_spam"
    log_audit(db, user_info["username"], "confirm_spam", email_id,
              request.client.host if request.client else None)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/email/{email_id}/report-false-positive")
async def report_false_positive(email_id: str, request: Request,
                                 notes: str = Form(""), db: Session = Depends(get_db)):
    user_info = get_authenticated_user(request, db)
    feedback = Feedback(
        email_id=email_id,
        feedback_type="false_positive",
        notes=notes,
    )
    db.add(feedback)
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if email_record:
        email_record.status = "released"
    log_audit(db, user_info["username"], "report_false_positive", email_id,
              request.client.host if request.client else None, notes)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/help")
async def docs_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user_info = None
    if token:
        try:
            payload = decode_token(token)
            user = db.query(User).filter(User.username == payload.get("sub")).first()
            if user and user.is_active:
                user_info = {"username": user.username, "role": user.role}
        except Exception:
            pass
    return templates.TemplateResponse(request, "docs.html", {"user": user_info})


@app.get("/metrics-panel")
async def metrics_panel(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user_info = None
    if token:
        try:
            payload = decode_token(token)
            user = db.query(User).filter(User.username == payload.get("sub")).first()
            if user and user.is_active:
                user_info = {"username": user.username, "role": user.role}
        except Exception:
            pass

    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    quarantine_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE"
    ).scalar() or 0
    warn_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "WARN"
    ).scalar() or 0
    clean_count = total - quarantine_count - warn_count

    top_senders = db.query(
        QuarantineEmail.sender, func.count(QuarantineEmail.id).label("count")
    ).group_by(QuarantineEmail.sender).order_by(
        func.count(QuarantineEmail.id).desc()
    ).limit(10).all()

    feedback_count = db.query(func.count(Feedback.id)).scalar() or 0

    daily_stats = db.query(
        func.date(QuarantineEmail.created_at).label("day"),
        func.count(QuarantineEmail.id).label("total"),
        func.sum(case((QuarantineEmail.label == "QUARANTINE", 1), else_=0)).label("quarantines"),
    ).group_by(func.date(QuarantineEmail.created_at)).order_by(
        func.date(QuarantineEmail.created_at).desc()
    ).limit(14).all()
    daily_stats = list(reversed(daily_stats))

    return templates.TemplateResponse(request, "metrics.html", {
        "total": total,
        "quarantine_count": quarantine_count,
        "warn_count": warn_count,
        "clean_count": clean_count,
        "top_senders": top_senders,
        "feedback_count": feedback_count,
        "daily_stats": daily_stats,
        "user": user_info,
    })


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
    avg_anomaly = db.query(func.avg(QuarantineEmail.anomaly_score)).scalar() or 0
    avg_fused = db.query(func.avg(QuarantineEmail.fused_score)).scalar() or 0
    return {
        "total": total,
        "quarantine": quarantine_count,
        "warn": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0,
        "clean": total - quarantine_count - (
            db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0
        ),
        "avg_anomaly_score": round(float(avg_anomaly), 4),
        "avg_fused_score": round(float(avg_fused), 4),
    }

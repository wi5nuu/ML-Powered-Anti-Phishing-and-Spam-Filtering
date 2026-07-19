"""
Superadmin management endpoints — highest privilege tier.

SECURITY: All endpoints in this module require superadmin role.
Only users with role='superadmin' can access these endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.infrastructure.database.session import get_db
from src.infrastructure.auth.jwt import get_current_user, require_role
from src.domain.entities import User, QuarantineEmail, AdminMailbox, AuditLog, Organization
from src.domain.enums import UserRole
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


def _require_superadmin(current_user: User):
    """Verify the current user has superadmin role."""
    if current_user.role != UserRole.SUPERADMIN.value:
        logger.warning("Non-superadmin %s attempted superadmin endpoint", current_user.username)
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user


@router.get("/settings/roles")
def get_role_settings(current_user: User = Depends(get_current_user)):
    """Get all available roles and their descriptions."""
    _require_superadmin(current_user)
    from src.domain.enums import UserRole as UR, ROLE_DESCRIPTIONS
    return [{"role": r.value, "description": ROLE_DESCRIPTIONS.get(r, "")} for r in UR if r != UR.MAILBOX]


@router.put("/settings/roles")
def update_role_settings(data: dict, current_user: User = Depends(get_current_user)):
    """Update role settings (future: configurable permissions)."""
    _require_superadmin(current_user)
    # TODO: Implement persistent role configuration
    return {"ok": True, "message": "Role settings updated"}


@router.get("/spam-stats")
def get_spam_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get global spam/phishing/malware statistics."""
    _require_superadmin(current_user)
    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    spam = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.category == "spam").scalar() or 0
    phishing = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.category == "phishing").scalar() or 0
    malware = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.category == "malware").scalar() or 0
    clean = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.category == "clean").scalar() or 0
    daily = db.query(
        func.date(QuarantineEmail.created_at).label("date"),
        func.count(QuarantineEmail.id).label("count")
    ).group_by(func.date(QuarantineEmail.created_at)).order_by("date").limit(30).all()
    return {
        "total": total, "spam": spam, "phishing": phishing,
        "malware": malware, "clean": clean,
        "daily": [{"date": str(d.date), "count": d.count} for d in daily],
    }


@router.get("/system-health")
def system_health(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Check system health status (database connection, etc.)."""
    _require_superadmin(current_user)
    try:
        db.execute(func.now())
        db_status = "connected"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        db_status = "error"
    return {
        "database": db_status,
        "status": "healthy" if db_status == "connected" else "degraded",
        "websocket_connections": 0,
    }


@router.get("/track")
def get_tracking_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get global tracking data: users, emails, mailboxes."""
    _require_superadmin(current_user)
    users = db.query(func.count(User.id)).scalar() or 0
    emails = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    boxes = db.query(func.count(AdminMailbox.id)).filter(AdminMailbox.is_active == True).scalar() or 0
    return {"total_users": users, "total_emails": emails, "active_mailboxes": boxes}


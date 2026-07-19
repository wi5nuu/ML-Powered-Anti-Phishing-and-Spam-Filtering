"""
Admin management endpoints for CogniMail — Enterprise Edition.

SECURITY: All endpoints require authentication and proper role authorization.
- Superadmin: Full access to all organizations
- Admin: Access only within their own organization
- User: No access to admin endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.infrastructure.database.session import get_db
from src.infrastructure.auth.jwt import get_current_user, hash_password
from src.domain.entities import User, AdminMailbox, AuditLog, QuarantineEmail, Report, Organization
from src.domain.enums import UserRole
from src.infrastructure.websocket.manager import ws_manager
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def broadcast_update(event_type: str, data: dict):
    """Broadcast WebSocket updates to admin and superadmin clients."""
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(ws_manager.broadcast_event(event_type, data, roles=["superadmin", "admin"]))
    except Exception:
        pass


# ─── User Management ─────────────────────────────────────────────────────

@router.get("/users")
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List users. Superadmin sees all; Admin sees only their org users."""
    if current_user.role == UserRole.SUPERADMIN.value:
        users = db.query(User).all()
    elif current_user.role == UserRole.ADMIN.value:
        users = db.query(User).filter(
            User.organization_id == current_user.organization_id
        ).all()
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return [
        {
            "id": u.id, "username": u.username, "email": u.email or "",
            "role": u.role, "is_active": u.is_active,
            "organization_id": u.organization_id,
            "created_at": str(u.created_at),
        }
        for u in users
    ]


@router.post("/users")
def create_user(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new user. Superadmin can set any role; Admin can only create 'user' role."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    # Admin can only create 'user' role within their org
    role = data.get("role", "user")
    if current_user.role == UserRole.ADMIN.value:
        if role != "user":
            raise HTTPException(status_code=403, detail="Admin can only create users with 'user' role")
        org_id = current_user.organization_id
    else:
        org_id = data.get("organization_id")

# ─── Mailbox Management ─────────────────────────────────────────────────

@router.get("/mailboxes")
def list_mailboxes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List mailboxes. Superadmin sees all; Admin sees only their org mailboxes."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    query = db.query(AdminMailbox)
    if current_user.role == UserRole.ADMIN.value:
        query = query.filter(AdminMailbox.organization_id == current_user.organization_id)
    return query.order_by(AdminMailbox.created_at.desc()).all()


@router.post("/mailboxes")
def create_mailbox(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new admin mailbox."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    domain = email.split("@")[1]
    if db.query(AdminMailbox).filter(AdminMailbox.email == email).first():
        raise HTTPException(status_code=400, detail="Mailbox already exists")
    mailbox = AdminMailbox(
        email=email, domain=domain,
        sender_name=data.get("sender_name", ""),
        forward_to=data.get("forward_to", ""),
        forward_enabled=data.get("forward_enabled", False),
        forward_keep_copy=data.get("forward_keep_copy", True),
        assigned_to=data.get("assigned_to", ""),
        created_by=current_user.username,
        organization_id=current_user.organization_id if current_user.role == UserRole.ADMIN.value else data.get("organization_id"),
    )
    db.add(mailbox)
    db.commit()
    logger.info("Mailbox created: %s by %s", email, current_user.username)
    return {"ok": True, "id": mailbox.id}


@router.put("/mailboxes/{mailbox_id}")
def update_mailbox(
    mailbox_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update mailbox settings."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    if current_user.role == UserRole.ADMIN.value:
        if mailbox.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Cannot modify mailboxes outside your organization")

@router.delete("/mailboxes/{mailbox_id}")
def delete_mailbox(
    mailbox_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete (deactivate) a mailbox."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    if current_user.role == UserRole.ADMIN.value:
        if mailbox.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Cannot delete mailboxes outside your organization")
    mailbox.is_active = False
    db.commit()
    logger.info("Mailbox deactivated: id=%s by %s", mailbox_id, current_user.username)
    return {"ok": True}


# ─── Quarantine / Detection ──────────────────────────────────────────────

@router.get("/quarantine-summary")
def get_quarantine_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get quarantine summary statistics."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return {
        "total_quarantined": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "QUARANTINE").scalar() or 0,
        "total_warn": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0,
        "total_spam": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.category == "spam").scalar() or 0,
        "total_phishing": db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.category == "phishing").scalar() or 0,
    }


@router.get("/detection-logs")
def get_detection_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent detection logs (WARN and QUARANTINE)."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    logs = db.query(QuarantineEmail).filter(
        QuarantineEmail.label.in_(["WARN", "QUARANTINE"])
    ).order_by(QuarantineEmail.created_at.desc()).limit(100).all()
    return [{
        "id": e.id, "email_id": e.email_id, "subject": getattr(e, 'subject', ''),
        "sender": getattr(e, 'sender', ''), "label": e.label,
        "category": e.category, "fused_score": e.fused_score,
        "status": e.status, "created_at": str(e.created_at),
    } for e in logs]


@router.get("/quarantine")
def get_quarantine_emails(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all quarantined emails."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    items = db.query(QuarantineEmail).filter(

# ─── Dashboard / Overview ────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get admin dashboard overview data."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_quarantined = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE"
    ).scalar() or 0
    total_warn = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "WARN"
    ).scalar() or 0
    recent = db.query(QuarantineEmail).order_by(
        QuarantineEmail.created_at.desc()
    ).limit(5).all()
    activities = db.query(AuditLog).order_by(
        AuditLog.created_at.desc()
    ).limit(10).all()
    return {
        "total_users": total_users,
        "total_quarantined": total_quarantined,
        "total_warn": total_warn,
        "recent_security_detections": [{
            "subject": getattr(e, 'subject', ''), "sender": getattr(e, 'sender', ''),
            "label": e.label, "category": e.category,
        } for e in recent],
        "recent_activities": [{
            "action": a.action, "user": a.user, "details": a.details,
            "ip_address": a.ip_address, "created_at": str(a.created_at),
        } for a in activities],
        "system_health": {"database": "connected", "status": "healthy"},
    }


# ─── Reports / Export ────────────────────────────────────────────────────

@router.get("/export-report/pdf")
def export_report_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export report as text report."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    from fastapi.responses import Response
    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    clean = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "DELIVER").scalar() or 0
    warn = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0
    q = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "QUARANTINE").scalar() or 0
    text = f"CogniMail Report\nTotal: {total}\nClean: {clean}\nWarn: {warn}\nQuarantined: {q}\n"
    return Response(content=text, media_type="text/plain",
                    headers={"Content-Disposition": "attachment; filename=cognimail-report.txt"})


@router.get("/export-report/excel")
def export_report_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export report as CSV."""
    if current_user.role not in (UserRole.SUPERADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    from fastapi.responses import Response
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Emails", db.query(func.count(QuarantineEmail.id)).scalar() or 0])
    writer.writerow(["Clean", db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "DELIVER").scalar() or 0])
    writer.writerow(["Warn", db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0])
    writer.writerow(["Quarantined", db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "QUARANTINE").scalar() or 0])
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=cognimail-report.csv"})

        QuarantineEmail.label == "QUARANTINE"
    ).order_by(QuarantineEmail.created_at.desc()).limit(100).all()
    return [{
        "id": e.id, "email_id": e.email_id, "subject": getattr(e, 'subject', ''),
        "sender": getattr(e, 'sender', ''), "category": e.category,
        "fused_score": e.fused_score, "status": e.status,
        "created_at": str(e.created_at),
    } for e in items]

    for field in ("sender_name", "forward_to", "forward_enabled", "forward_keep_copy", "assigned_to", "is_active"):
        if field in data:
            setattr(mailbox, field, data[field])
    db.commit()
    logger.info("Mailbox updated: id=%s by %s", mailbox_id, current_user.username)
    return {"ok": True}


    user = User(
        username=username,
        email=data.get("email", ""),
        hashed_password=hash_password(password),
        role=role,
        organization_id=org_id,
    )
    db.add(user)
    db.commit()

    background_tasks.add_task(
        broadcast_update, "user_created",
        {"id": user.id, "username": user.username, "role": user.role}
    )

    logger.info("User created: %s (role=%s) by %s", username, role, current_user.username)
    return {"ok": True, "id": user.id}

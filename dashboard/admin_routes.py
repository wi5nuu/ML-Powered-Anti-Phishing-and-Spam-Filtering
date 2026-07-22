"""
Admin routes — RBAC-protected admin API endpoints.

Registered via app.include_router(admin_routes.router) in app.py.

Routes here are CRUD operations not covered (or covered with less validation)
by the @app.xxx routes in app.py. Specifically:
  - POST /users  — Pydantic-validated creation with proper role guards
  - PATCH /users/{user_id}  — partial update by numeric id
  - DELETE /users/{user_id}  — delete by numeric id (superadmin only)
  - PATCH /mailboxes/{mailbox_id}  — partial update
  - DELETE /mailboxes/{mailbox_id}  — delete (superadmin only, stricter than app.py)

Intentionally NOT duplicated here (app.py versions are richer):
  GET  /users      — org-scoped filtering
  GET  /mailboxes  — returns forward_to, assigned_to, storage_bytes, etc.
  POST /mailboxes  — rate-limited, handles password + assigned_to
  GET  /stats      — app.py version aggregates email/threat counts too
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import datetime
import csv
import io
import json

from database.models import User, UserRole, AdminMailbox, AuditLog, Organization, QuarantineEmail
from dashboard.database import get_db
from dashboard.auth import get_current_user_cookie, hash_password
from sqlalchemy import func, or_

# Import libraries for PDF and Excel export
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

router = APIRouter(prefix="/api/admin", tags=["admin-crud"])


# ── RBAC dependency classes ────────────────────────────────────────────────────
# FastAPI can inject Request directly into Depends() functions — the guard
# functions below receive both Request and Session via FastAPI's DI system.

def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: requires admin or superadmin role, authenticated via cookie."""
    user = get_current_user_cookie(request, db)
    if user.role not in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_superadmin(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: requires superadmin role, authenticated via cookie."""
    user = get_current_user_cookie(request, db)
    if user.role != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    role: str = "user"
    is_active: bool = True
    organization_id: Optional[int] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class MailboxUpdate(BaseModel):
    sender_name: Optional[str] = None
    is_active: Optional[bool] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _serialize_user(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": getattr(u, "email", "") or "",
        "role": u.role,
        "is_active": getattr(u, "is_active", True),
        "created_at": str(getattr(u, "created_at", "")),
    }


def _serialize_mailbox(m: AdminMailbox) -> dict:
    return {
        "id": m.id,
        "email": m.email,
        "domain": getattr(m, "domain", ""),
        "sender_name": getattr(m, "sender_name", ""),
        "created_by": getattr(m, "created_by", ""),
        "is_active": getattr(m, "is_active", True),
        "created_at": str(getattr(m, "created_at", "")),
    }


# ── User endpoints ─────────────────────────────────────────────────────────────

@router.post("/users", status_code=201)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a user. Admins can only create 'user' role; superadmins can create any role."""
    if current_user.role == UserRole.ADMIN.value and payload.role != UserRole.USER.value:
        raise HTTPException(status_code=403, detail="Admin hanya dapat membuat pengguna dengan role 'user'.")
    if payload.role not in (UserRole.USER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(status_code=400, detail="Role tidak valid.")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username sudah digunakan.")
    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email sudah digunakan.")
    
    # Enforce organization_id for admin-created users
    org_id = payload.organization_id
    if current_user.role == UserRole.ADMIN.value:
        if not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Admin tidak memiliki organisasi.")
        # Force the new user to be in the admin's organization
        org_id = current_user.organization_id
    
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        organization_id=org_id,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    if payload.role == UserRole.SUPERADMIN.value and current_user.role != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat menetapkan role superadmin.")
    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Tidak dapat menonaktifkan akun Anda sendiri.")
    # P2 FIX: Admin can only edit users within their own organization
    if current_user.role == UserRole.ADMIN.value:
        if not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Admin tidak memiliki organisasi.")
        if user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Admin hanya dapat mengedit pengguna dalam organisasi yang sama.")
        if user.role != UserRole.USER.value:
            raise HTTPException(status_code=403, detail="Admin hanya dapat mengedit pengguna dengan role 'user'.")
        if payload.role is not None and payload.role != UserRole.USER.value:
            raise HTTPException(status_code=403, detail="Admin hanya dapat menetapkan role 'user'.")
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun Anda sendiri.")
    db.delete(user)
    db.commit()


# ── Mailbox endpoints ──────────────────────────────────────────────────────────

@router.patch("/mailboxes/{mailbox_id}")
def update_mailbox(
    mailbox_id: int,
    payload: MailboxUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox tidak ditemukan.")
    # P2 FIX: Admin can only update mailboxes within their own organization
    if current_user.role == UserRole.ADMIN.value:
        if not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Admin tidak memiliki organisasi.")
        org_usernames = [
            u.username for u in db.query(User.username).filter(
                User.organization_id == current_user.organization_id
            ).all()
        ]
        if mailbox.created_by not in org_usernames:
            raise HTTPException(status_code=403, detail="Admin hanya dapat mengelola mailbox dalam organisasi yang sama.")
    if payload.sender_name is not None:
        mailbox.sender_name = payload.sender_name
    if payload.is_active is not None:
        mailbox.is_active = payload.is_active
    db.commit()
    db.refresh(mailbox)
    return _serialize_mailbox(mailbox)


@router.delete("/mailboxes/{mailbox_id}", status_code=204)
def delete_mailbox(
    mailbox_id: int,
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    """Delete a mailbox. Requires superadmin (stricter than app.py's admin-level delete)."""
    mailbox = db.query(AdminMailbox).filter(AdminMailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox tidak ditemukan.")
    db.delete(mailbox)
    db.commit()


# ── Audit Trail Export endpoint ────────────────────────────────────────────


def _generate_csv_export(audit_records):
    """Generate CSV export of audit log data."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["ID","Timestamp","User","Action","Email ID","Details"])
    for record in audit_records:
        writer.writerow([
            record.id,
            record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else "",
            record.user or "", record.action or "", record.email_id or "", record.details or ""
        ])
    output.seek(0)
    return output.getvalue()


def _generate_excel_export(audit_records):
    """Generate Excel export of audit log data."""
    if not OPENPYXL_AVAILABLE:
        raise HTTPException(status_code=500, detail="openpyxl library not installed. Run: pip install openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Audit Log"
    hdr_fill = PatternFill(start_color="1a73e8", end_color="1a73e8", fill_type="solid")
    hdr_font = Font(bold=True, color="FFFFFF")
    hdr_align = Alignment(horizontal="center", vertical="center")
    ws.append(["ID","Timestamp","User","Action","Email ID","Details"])
    for cell in ws[1]:
        cell.fill = hdr_fill; cell.font = hdr_font; cell.alignment = hdr_align
    for record in audit_records:
        ws.append([
            record.id,
            record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else "",
            record.user or "", record.action or "", record.email_id or "", record.details or ""
        ])
    for col in ws.columns:
        letter = col[0].column_letter
        mx = min(max((len(str(c.value)) for c in col if c.value), default=0) + 2, 50)
        ws.column_dimensions[letter].width = mx
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return out.getvalue()


def _generate_pdf_export(audit_records):
    """Generate PDF export of audit log data."""
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=500, detail="reportlab library not installed. Run: pip install reportlab")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    el = []
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T',parent=styles['Heading1'],fontSize=18,
                         textColor=colors.HexColor('#1a73e8'),spaceAfter=30,alignment=1)
    el.append(Paragraph("User Activity Tracking Report", ts))
    el.append(Paragraph(f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", styles['Normal']))
    el.append(Spacer(1,20))
    td = [["ID","Timestamp","User","Action","Email ID"]]
    for r in audit_records:
        td.append([str(r.id),
                   r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                   r.user or "", r.action or "",
                   str(r.email_id) if r.email_id else ""])
    t = Table(td, colWidths=[0.6*inch,1.5*inch,1.2*inch,1.2*inch,1*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a73e8')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),10),
        ('BOTTOMPADDING',(0,0),(-1,0),12),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('FONTSIZE',(0,1),(-1,-1),8),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ]))
    el.append(t)
    doc.build(el); buf.seek(0)
    return buf.getvalue()


@router.get("/track/export")
def export_audit_trail(
    format: str = Query("csv", description="Export format: csv, excel, or pdf"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Export audit log data (legacy)."""
    audit_records = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500).all()
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fl = format.lower()
    if fl == "csv":
        content = _generate_csv_export(audit_records)
        mt = "text/csv"; fn = f"audit_log_{ts}.csv"
    elif fl == "excel":
        content = _generate_excel_export(audit_records)
        mt = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"; fn = f"audit_log_{ts}.xlsx"
    elif fl == "pdf":
        content = _generate_pdf_export(audit_records)
        mt = "application/pdf"; fn = f"audit_log_{ts}.pdf"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use csv, excel, or pdf.")
    return StreamingResponse(iter([content]), media_type=mt,
                             headers={"Content-Disposition": f"attachment; filename={fn}"})


# ── Comprehensive Export (Report) ──────────────────────────────────────────


class ExportRequest(BaseModel):
    format: str = "pdf"
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    admin_ids: Optional[List[int]] = None
    include_users: bool = True
    include_emails: bool = True


def _parse_date(s: Optional[str]) -> Optional[datetime.datetime]:
    if not s: return None
    try:
        p = s.split("-")
        return datetime.datetime(int(p[0]), int(p[1]), int(p[2]))
    except: return None


def _gather_export_data(db: Session, req: ExportRequest, current_user: User) -> dict:
    dt_from = _parse_date(req.date_from)
    dt_to = _parse_date(req.date_to)

    restrict_org_id = None
    if current_user.role != UserRole.SUPERADMIN.value:
        restrict_org_id = current_user.organization_id

    email_q = db.query(QuarantineEmail)
    if restrict_org_id:
        email_q = email_q.filter(QuarantineEmail.organization_id == restrict_org_id)
    if dt_from:
        email_q = email_q.filter(QuarantineEmail.received_at >= dt_from.strftime("%Y-%m-%d"))
    if dt_to:
        email_q = email_q.filter(QuarantineEmail.received_at <= dt_to.strftime("%Y-%m-%d") + " 23:59:59")

    log_q = db.query(AuditLog)
    if dt_from:
        log_q = log_q.filter(AuditLog.created_at >= dt_from)
    if dt_to:
        log_q = log_q.filter(AuditLog.created_at <= dt_to + datetime.timedelta(days=1))

    admin_q = db.query(User).filter(User.role == UserRole.ADMIN.value)
    if restrict_org_id:
        admin_q = admin_q.filter(User.organization_id == restrict_org_id)
    if req.admin_ids:
        admin_q = admin_q.filter(User.id.in_(req.admin_ids))
    admins = admin_q.order_by(User.username).all()

    all_emails = email_q.order_by(QuarantineEmail.received_at.desc().nullslast()).all()
    total_email = len(all_emails)
    total_clean = sum(1 for e in all_emails if e.label == "CLEAN")
    total_warn = sum(1 for e in all_emails if e.label == "WARN")
    total_quarantine = sum(1 for e in all_emails if e.label == "QUARANTINE")

    summary = {
        "total_admins": len(admins),
        "total_users": db.query(User).filter(User.role == UserRole.USER.value).count(),
        "total_organizations": db.query(Organization).count(),
        "total_emails": total_email,
        "total_clean": total_clean,
        "total_warn": total_warn,
        "total_quarantine": total_quarantine,
        "date_from": req.date_from or "All time",
        "date_to": req.date_to or "Present",
    }

    admin_data = []
    mailbox_data = []
    for admin in admins:
        org_name = ""
        if admin.organization_id:
            org = db.query(Organization).filter(Organization.id == admin.organization_id).first()
            org_name = org.name if org else ""

        user_count = 0
        if admin.organization_id:
            user_count = db.query(User).filter(
                User.organization_id == admin.organization_id,
                User.role == UserRole.USER.value
            ).count()

        org_emails = [e for e in all_emails if e.organization_id == admin.organization_id]
        org_total = len(org_emails)
        org_clean = sum(1 for e in org_emails if e.label == "CLEAN")
        org_warn = sum(1 for e in org_emails if e.label == "WARN")
        org_quarantine = sum(1 for e in org_emails if e.label == "QUARANTINE")

        admin_logs = log_q.filter(AuditLog.user == admin.username
            ).order_by(AuditLog.created_at.desc()).limit(20).all()
        recent_actions = [{"action":log.action,"details":log.details or "",
                           "created_at":log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else ""}
                          for log in admin_logs]

        mailboxes = db.query(AdminMailbox).filter(AdminMailbox.created_by == admin.username).all()
        for mb in mailboxes:
            mb_emails = [e for e in org_emails if mb.email in (e.recipient_list or "")]
            mailbox_data.append({
                "admin": admin.username,
                "organization": org_name,
                "mailbox_email": mb.email,
                "domain": mb.domain,
                "is_active": mb.is_active,
                "created_at": mb.created_at.strftime("%Y-%m-%d") if mb.created_at else "",
                "email_stats": {
                    "total": len(mb_emails),
                    "clean": sum(1 for e in mb_emails if e.label == "CLEAN"),
                    "warn": sum(1 for e in mb_emails if e.label == "WARN"),
                    "quarantine": sum(1 for e in mb_emails if e.label == "QUARANTINE"),
                },
            })

        admin_data.append({
            "username": admin.username, "email": admin.email or "",
            "role": admin.role, "organization": org_name,
            "is_active": admin.is_active,
            "user_count": user_count, "mailbox_count": len(mailboxes),
            "email_stats": {"total":org_total,"clean":org_clean,"warn":org_warn,"quarantine":org_quarantine},
            "recent_actions": recent_actions,
            "organization_id": admin.organization_id,
        })

    user_data = []
    if req.include_users:
        for admin in admin_data:
            if not admin["organization_id"]: continue
            org_users = db.query(User).filter(
                User.organization_id == admin["organization_id"],
                User.role == UserRole.USER.value
            ).all()
            for u in org_users:
                uemails = [e for e in all_emails if e.organization_id == admin["organization_id"]]
                ue_total = len(uemails)
                ue_clean = sum(1 for e in uemails if e.label == "CLEAN")
                ue_warn = sum(1 for e in uemails if e.label == "WARN")
                ue_quarantine = sum(1 for e in uemails if e.label == "QUARANTINE")
                ulogs = log_q.filter(AuditLog.user == u.username
                    ).order_by(AuditLog.created_at.desc()).limit(10).all()
                urecent = [{"action":l.action,"details":l.details or "",
                            "created_at":l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else ""}
                           for l in ulogs]
                user_data.append({
                    "admin": admin["username"], "organization": admin["organization"],
                    "username": u.username, "email": u.email or "",
                    "is_active": u.is_active,
                    "email_stats": {"total":ue_total,"clean":ue_clean,"warn":ue_warn,"quarantine":ue_quarantine},
                    "recent_actions": urecent,
                })

    email_data = []
    if req.include_emails:
        for e in all_emails:
            org_name = ""
            if e.organization_id:
                org = db.query(Organization).filter(Organization.id == e.organization_id).first()
                org_name = org.name if org else ""
            attachments = []
            try:
                if e.attachments_json: attachments = json.loads(e.attachments_json)
            except: pass
            has_attach = len(attachments) > 0
            has_malware = any(
                att.get("filename","").lower().endswith((".exe",".zip",".rar",".js",".vbs",".scr",".bat",".msi"))
                for att in attachments
            ) if attachments else False
            reasons = []
            if e.label in ("WARN","QUARANTINE"):
                if e.spf_result and e.spf_result.lower() != "pass":
                    reasons.append(f"SPF:{e.spf_result}")
                if e.dkim_result and e.dkim_result.lower() != "pass":
                    reasons.append(f"DKIM:{e.dkim_result}")
                if e.dmarc_result and e.dmarc_result.lower() != "pass":
                    reasons.append(f"DMARC:{e.dmarc_result}")
                if e.sa_score and e.sa_score > 3:
                    reasons.append(f"SA:{e.sa_score:.1f}")
                if e.ml_probability and e.ml_probability > 0.7:
                    reasons.append(f"ML:{e.ml_probability:.2f}")
                if has_malware: reasons.append("MalwareExt")
                if e.category: reasons.append(e.category)
                if e.routing_reason: reasons.append(e.routing_reason)
            email_data.append({
                "email_id": e.email_id, "subject": e.subject or "",
                "sender": e.sender or "", "recipient": e.recipient_list or "",
                "label": e.label or "", "category": e.category or "",
                "organization": org_name, "received_at": e.received_at or "",
                "fused_score": e.fused_score or 0, "sa_score": e.sa_score or 0,
                "ml_probability": e.ml_probability or 0, "anomaly_score": e.anomaly_score or 0,
                "has_attachment": has_attach, "has_malware_extension": has_malware,
                "spf_result": e.spf_result or "", "dkim_result": e.dkim_result or "",
                "dmarc_result": e.dmarc_result or "", "reasons": reasons,
                "label_display": {"CLEAN":"Clean","WARN":"Suspicious","QUARANTINE":"Blocked"}.get(e.label, e.label or "Unknown"),
            })

    return {"summary": summary, "admins": admin_data, "users": user_data, "emails": email_data, "mailboxes": mailbox_data}


def _generate_pdf_report(data: dict):
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(status_code=500, detail="reportlab not installed")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    el = []; styles = getSampleStyleSheet()
    s = data["summary"]

    ts = ParagraphStyle('T',parent=styles['Heading1'],fontSize=20,
                         textColor=colors.HexColor('#1a73e8'),spaceAfter=6,alignment=1)
    ss = ParagraphStyle('S',parent=styles['Normal'],fontSize=9,
                         textColor=colors.grey,alignment=1,spaceAfter=20)

    el.append(Paragraph("CogniMail — Comprehensive Report", ts))
    el.append(Paragraph(f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC | Period: {s['date_from']} — {s['date_to']}", ss))

    # Summary table
    st = Table([["Metric","Value"],
                ["Total Admins",str(s["total_admins"])],
                ["Total Users",str(s["total_users"])],
                ["Total Organizations",str(s["total_organizations"])],
                ["Total Emails",str(s["total_emails"])],
                ["Clean (Safe)",str(s["total_clean"])],
                ["Suspicious (Warn)",str(s["total_warn"])],
                ["Blocked (Quarantine)",str(s["total_quarantine"])]],
               colWidths=[3*inch,2*inch])
    st.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a73e8')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),9),
        ('GRID',(0,0),(-1,-1),0.4,colors.grey),
        ('ALIGN',(1,0),(1,-1),'CENTER'),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    el.append(st); el.append(Spacer(1,16))

    h2 = ParagraphStyle('H2',parent=styles['Heading2'],fontSize=13,
                         textColor=colors.HexColor('#333'),spaceBefore=18,spaceAfter=8)
    h3 = ParagraphStyle('H3',parent=styles['Heading3'],fontSize=10,
                         textColor=colors.HexColor('#555'),spaceBefore=10,spaceAfter=4)
    cs = ParagraphStyle('C',parent=styles['Normal'],fontSize=7,leading=9)

    # Admins section
    el.append(Paragraph("Admin Details", h2))
    for a in data["admins"]:
        el.append(Paragraph(f"{a['username']} ({a['role']}) — {a['organization'] or 'Global'}", h3))
        el.append(Paragraph(
            f"Email: {a['email'] or '-'} | Status: {'Active' if a['is_active'] else 'Inactive'} | "
            f"Users: {a['user_count']} | Mailboxes: {a['mailbox_count']}", cs))
        es = a["email_stats"]
        at = Table([["Total","Clean","Suspicious","Blocked"],
                     [str(es["total"]),str(es["clean"]),str(es["warn"]),str(es["quarantine"])]],
                    colWidths=[1.1*inch]*4)
        at.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a73e8')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8),
            ('GRID',(0,0),(-1,-1),0.4,colors.grey),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ]))
        el.append(at)
        if a["recent_actions"]:
            el.append(Spacer(1,4))
            txt = "Recent: "+"; ".join(f"{x['action']}({x['created_at']})" for x in a["recent_actions"][:5])
            el.append(Paragraph(txt, cs))
        el.append(Spacer(1,10))

    # Users section
    if data["users"]:
        el.append(Paragraph("User Details", h2))
        ur = [["Admin","Org","Username","Email","Total","Clean","Warn","Blocked"]]
        for u in data["users"]:
            es = u["email_stats"]
            ur.append([u["admin"],u["organization"],u["username"],u["email"],
                       str(es["total"]),str(es["clean"]),str(es["warn"]),str(es["quarantine"])])
        if len(ur)>1:
            ut = Table(ur, colWidths=[0.9*inch,0.9*inch,0.8*inch,1.1*inch,0.5*inch,0.5*inch,0.6*inch,0.6*inch])
            ut.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a73e8')),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,-1),6),
                ('GRID',(0,0),(-1,-1),0.3,colors.grey),
                ('ALIGN',(4,0),(-1,-1),'CENTER'),
                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
            ]))
            el.append(ut)
        el.append(Spacer(1,12))

    # Mailboxes section
    if data.get("mailboxes"):
        el.append(Paragraph("Mailbox Details", h2))
        mr = [["Admin","Org","Mailbox","Active","Total","Clean","Warn","Blocked"]]
        for m in data["mailboxes"]:
            es = m["email_stats"]
            mr.append([m["admin"],m["organization"],m["mailbox_email"],
                       "Yes" if m["is_active"] else "No",
                       str(es["total"]),str(es["clean"]),str(es["warn"]),str(es["quarantine"])])
        if len(mr)>1:
            mt = Table(mr, colWidths=[0.8*inch,0.8*inch,1.2*inch,0.5*inch,0.5*inch,0.5*inch,0.6*inch,0.6*inch])
            mt.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a73e8')),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,-1),6),
                ('GRID',(0,0),(-1,-1),0.3,colors.grey),
                ('ALIGN',(3,0),(-1,-1),'CENTER'),
                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
            ]))
            el.append(mt)
        el.append(Spacer(1,12))

    # Emails section
    if data["emails"]:
        el.append(Paragraph("Email Details", h2))
        el.append(Paragraph(f"Total {len(data['emails'])} emails.", cs))
        el.append(Spacer(1,6))
        er = [["ID","Subject","Sender","Label","Category","Received","Score","Reasons"]]
        shown = 0
        for e in data["emails"]:
            if shown>=100: break
            rsn = "; ".join(e["reasons"][:2]) if e["reasons"] else "-"
            er.append([e["email_id"][:12]+".." if len(e["email_id"])>12 else e["email_id"],
                       (e["subject"][:40]+"..") if len(e["subject"])>40 else (e["subject"] or "-"),
                       (e["sender"][:25]+"..") if len(e["sender"])>25 else (e["sender"] or "-"),
                       e["label_display"], e["category"] or "-",
                       e["received_at"] or "-", f"{e['fused_score']:.2f}",
                       rsn[:50]])
            shown+=1
        if len(er)>1:
            et = Table(er, colWidths=[0.7*inch,1.1*inch,0.9*inch,0.5*inch,0.5*inch,0.7*inch,0.5*inch,1.1*inch])
            et.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a73e8')),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,-1),6),
                ('GRID',(0,0),(-1,-1),0.3,colors.grey),
                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
            ]))
            el.append(et)
            if len(data["emails"])>100:
                el.append(Paragraph(f"... and {len(data['emails'])-100} more emails", cs))

    doc.build(el); buf.seek(0)
    return buf.getvalue()


def _generate_excel_report(data: dict):
    if not OPENPYXL_AVAILABLE:
        raise HTTPException(status_code=500, detail="openpyxl not installed")
    wb = openpyxl.Workbook()
    hf = PatternFill(start_color="1a73e8", end_color="1a73e8", fill_type="solid")
    hfn = Font(bold=True, color="FFFFFF", size=10)
    ha = Alignment(horizontal="center", vertical="center", wrap_text=True)
    def sh(ws, n):
        for c in range(1,n+1):
            cell = ws.cell(row=1,column=c)
            cell.fill = hf; cell.font = hfn; cell.alignment = ha
    def aw(ws):
        for cc in ws.columns:
            letter = cc[0].column_letter
            mx = min(max((len(str(c.value)) for c in cc if c.value), default=0)+3, 50)
            ws.column_dimensions[letter].width = mx

    s = data["summary"]
    ws1 = wb.active; ws1.title = "Summary"
    for row in [("Metric","Value"),
                ("Total Admins",s["total_admins"]),
                ("Total Users",s["total_users"]),
                ("Total Organizations",s["total_organizations"]),
                ("Total Emails",s["total_emails"]),
                ("Clean (Safe)",s["total_clean"]),
                ("Suspicious (Warn)",s["total_warn"]),
                ("Blocked (Quarantine)",s["total_quarantine"]),
                ("Period From",s["date_from"]),
                ("Period To",s["date_to"]),
                ("Generated",datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))]:
        ws1.append(list(row))
    sh(ws1,2); aw(ws1)

    ws2 = wb.create_sheet("Admins")
    h2 = ["Username","Email","Role","Organization","Active","Users","Mailboxes",
          "Total Emails","Clean","Suspicious","Blocked","Recent Activity"]
    ws2.append(h2); sh(ws2,len(h2))
    for a in data["admins"]:
        recent = "; ".join(f"{x['action']}({x['created_at']})" for x in a["recent_actions"][:5])
        es = a["email_stats"]
        ws2.append([a["username"],a["email"],a["role"],a["organization"],
                    "Yes" if a["is_active"] else "No",
                    a["user_count"],a["mailbox_count"],
                    es["total"],es["clean"],es["warn"],es["quarantine"],recent])
    aw(ws2)

    if data["users"]:
        ws3 = wb.create_sheet("Users")
        h3 = ["Admin","Organization","Username","Email","Active",
              "Total Emails","Clean","Suspicious","Blocked","Recent Activity"]
        ws3.append(h3); sh(ws3,len(h3))
        for u in data["users"]:
            recent = "; ".join(f"{x['action']}({x['created_at']})" for x in u["recent_actions"][:3])
            es = u["email_stats"]
            ws3.append([u["admin"],u["organization"],u["username"],u["email"],
                        "Yes" if u["is_active"] else "No",
                        es["total"],es["clean"],es["warn"],es["quarantine"],recent])
        aw(ws3)

    if data.get("mailboxes"):
        wsm = wb.create_sheet("Mailboxes")
        hm = ["Admin","Organization","Mailbox","Domain","Active","Created",
              "Total Emails","Clean","Suspicious","Blocked"]
        wsm.append(hm); sh(wsm,len(hm))
        for m in data["mailboxes"]:
            es = m["email_stats"]
            wsm.append([m["admin"],m["organization"],m["mailbox_email"],m["domain"],
                        "Yes" if m["is_active"] else "No",m["created_at"],
                        es["total"],es["clean"],es["warn"],es["quarantine"]])
        aw(wsm)

    if data["emails"]:
        ws4 = wb.create_sheet("Emails")
        h4 = ["Email ID","Subject","Sender","Recipient","Label",
              "Category","Organization","Received At",
              "Fused Score","SA Score","ML Prob","Anomaly",
              "Has Attachment","Malware Extension",
              "SPF","DKIM","DMARC","Reasons"]
        ws4.append(h4); sh(ws4,len(h4))
        for e in data["emails"]:
            ws4.append([e["email_id"],e["subject"],e["sender"],e["recipient"],
                        e["label_display"],e["category"],e["organization"],
                        e["received_at"],
                        e["fused_score"],e["sa_score"],e["ml_probability"],e["anomaly_score"],
                        "Yes" if e["has_attachment"] else "No",
                        "Yes" if e["has_malware_extension"] else "No",
                        e["spf_result"],e["dkim_result"],e["dmarc_result"],
                        "; ".join(e["reasons"])])
        aw(ws4)

    out = io.BytesIO(); wb.save(out); out.seek(0)
    return out.getvalue()


@router.post("/export/generate")
def generate_export(
    req: ExportRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate comprehensive report (PDF/Excel) with filters."""
    data = _gather_export_data(db, req, current_user)
    fmt = req.format.lower()
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if fmt == "pdf":
        content = _generate_pdf_report(data)
        return StreamingResponse(iter([content]), media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=cognimail_report_{ts}.pdf"})
    elif fmt == "excel":
        content = _generate_excel_report(data)
        return StreamingResponse(iter([content]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=cognimail_report_{ts}.xlsx"})
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")


@router.get("/admins/list")
def list_admins_for_export(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return list of admins for export filter selection.
    Superadmin sees all admins; admin sees only those in their org (self).
    """
    q = db.query(User).filter(User.role == UserRole.ADMIN.value)
    if current_user.role != UserRole.SUPERADMIN.value and current_user.organization_id:
        q = q.filter(User.organization_id == current_user.organization_id)
    admins = q.order_by(User.username).all()
    return [{"id":a.id,"username":a.username,"email":a.email or "",
             "role":a.role,"organization_id":a.organization_id} for a in admins]


@router.get("/search")
async def api_global_search(
    q: str = Query("", min_length=1, max_length=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Unified global search across users, emails, and audit logs."""
    query = q.strip()
    if not query:
        return {"pages": [], "users": [], "emails": [], "logs": []}

    like = f"%{query}%"

    # P1 FIX: Admin sees only results from their own organization
    restrict_org_id = None
    if _admin.role == UserRole.ADMIN.value and _admin.organization_id:
        restrict_org_id = _admin.organization_id

    # Users
    user_q = db.query(User).filter(
        or_(User.username.ilike(like), User.email.ilike(like))
    )
    if restrict_org_id:
        user_q = user_q.filter(User.organization_id == restrict_org_id)
    user_rows = user_q.limit(5).all()
    users = [
        {"username": u.username, "email": u.email or "", "role": u.role}
        for u in user_rows
    ]

    # Emails (subject, sender) — scoped to org
    email_q = db.query(QuarantineEmail).filter(
        or_(QuarantineEmail.subject.ilike(like), QuarantineEmail.sender.ilike(like))
    )
    if restrict_org_id:
        email_q = email_q.filter(QuarantineEmail.organization_id == restrict_org_id)
    email_rows = email_q.order_by(QuarantineEmail.received_at.desc().nullslast()).limit(5).all()
    emails = [
        {
            "email_id": e.email_id,
            "subject": e.subject or "",
            "sender": e.sender or "",
            "label": e.label or "",
            "received_at": e.received_at or "",
        }
        for e in email_rows
    ]

    # Audit logs — scoped to org users
    log_q = db.query(AuditLog).filter(
        or_(AuditLog.user.ilike(like), AuditLog.action.ilike(like), AuditLog.details.ilike(like))
    )
    if restrict_org_id:
        org_usernames = [u.username for u in user_rows] or ["__no_match__"]
        log_q = log_q.filter(AuditLog.user.in_(org_usernames))
    log_rows = log_q.order_by(AuditLog.created_at.desc().nullslast()).limit(5).all()
    logs = [
        {
            "id": l.id,
            "user": l.user or "",
            "action": l.action or "",
            "details": l.details or "",
            "created_at": l.created_at.isoformat() if l.created_at else "",
        }
        for l in log_rows
    ]

    return {"users": users, "emails": emails, "logs": logs}

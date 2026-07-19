from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.infrastructure.database.session import get_db
from src.infrastructure.auth.jwt import get_current_user
from src.domain.entities import User, QuarantineEmail, AuditLog, Feedback

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
def list_emails(request: Request, db: Session = Depends(get_db)):
    category = request.query_params.get("category", "")
    label = request.query_params.get("label", "")
    q = db.query(QuarantineEmail)
    if category:
        q = q.filter(QuarantineEmail.category == category)
    if label:
        q = q.filter(QuarantineEmail.label == label)
    emails = q.order_by(QuarantineEmail.created_at.desc()).limit(100).all()
    return [
        {
            "id": e.id, "email_id": e.email_id, "subject": e.subject, "sender": e.sender,
            "label": e.label, "category": e.category, "status": e.status,
            "fused_score": e.fused_score, "is_read": e.is_read,
            "created_at": str(e.created_at), "received_at": e.received_at,
        }
        for e in emails
    ]


@router.get("/{email_id}")
def get_email(email_id: str, db: Session = Depends(get_db)):
    email = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return {
        "id": email.id, "email_id": email.email_id, "subject": email.subject,
        "sender": email.sender, "recipient_list": email.recipient_list,
        "label": email.label, "category": email.category, "status": email.status,
        "fused_score": email.fused_score, "sa_score": email.sa_score,
        "ml_probability": email.ml_probability, "anomaly_score": email.anomaly_score,
        "xai_summary": email.xai_summary, "routing_reason": email.routing_reason,
        "spf_result": email.spf_result, "dkim_result": email.dkim_result,
        "dmarc_result": email.dmarc_result,
        "created_at": str(email.created_at), "received_at": email.received_at,
        "is_read": email.is_read,
    }


@router.put("/{email_id}/read")
def toggle_read(email_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    email = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email.is_read = not email.is_read
    db.commit()
    return {"ok": True, "is_read": email.is_read}


@router.post("/{email_id}/release")
def release_email(email_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    email = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email.status = "released"
    audit = AuditLog(user=current_user.username, action="release", email_id=email_id)
    db.add(audit)
    db.commit()
    return {"ok": True}


@router.post("/{email_id}/confirm-spam")
def confirm_spam(email_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    email = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email.status = "confirmed_spam"
    email.category = "spam"
    audit = AuditLog(user=current_user.username, action="confirm_spam", email_id=email_id)
    db.add(audit)
    db.commit()
    return {"ok": True}


@router.post("/{email_id}/report-false-positive")
def report_false_positive(email_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fb = Feedback(email_id=email_id, feedback_type="false_positive", notes="Reported as false positive")
    db.add(fb)
    db.commit()
    return {"ok": True}


@router.delete("/{email_id}")
def delete_email(email_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime
    email = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email.status = "trash"
    email.deleted_at = datetime.utcnow()
    audit = AuditLog(user=current_user.username, action="delete", email_id=email_id)
    db.add(audit)
    db.commit()
    return {"ok": True}


@router.post("/{email_id}/restore")
def restore_email(email_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    email = db.query(QuarantineEmail).filter(QuarantineEmail.email_id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email.status = "pending"
    email.deleted_at = None
    db.commit()
    return {"ok": True}


@router.get("/export-csv")
def export_emails_csv(db: Session = Depends(get_db)):
    from fastapi.responses import Response
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Subject", "Sender", "Label", "Category", "Score", "Date"])
    emails = db.query(QuarantineEmail).order_by(QuarantineEmail.created_at.desc()).limit(1000).all()
    for e in emails:
        writer.writerow([e.id, e.subject, e.sender, e.label, e.category, e.fused_score, str(e.created_at)])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=cognimail-emails.csv"})

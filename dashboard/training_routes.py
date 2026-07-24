"""
ML Training & False Negative Feedback Loop Routes

Separated from app.py to avoid circular import issues.
"""
import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, field_validator

from database.models import QuarantineEmail, Feedback, TrainingSample, _utcnow
from dashboard.database import get_db

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ══════════════════════════════════════════════════════════════════════════════

class FalseNegativeRequest(BaseModel):
    corrected_label: str  # "spam", "phishing", "malware"
    notes: str = ""


class UpdateTrainingSampleRequest(BaseModel):
    corrected_label: str | None = None
    status: str | None = None
    notes: str | None = None

    _valid_statuses = {"pending", "approved", "rejected", "used_in_training"}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in cls._valid_statuses:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {', '.join(sorted(cls._valid_statuses))}")
        return v


# ══════════════════════════════════════════════════════════════════════════════
# Helper Functions (imported from app.py context)
# ══════════════════════════════════════════════════════════════════════════════

def get_authenticated_api_user(request: Request, db: Session, allow_mailbox_token: bool = False) -> dict:
    """Import this from app.py at runtime to avoid circular dependency."""
    from dashboard.app import get_authenticated_api_user as _get_auth
    return _get_auth(request, db, allow_mailbox_token=allow_mailbox_token)


def has_permission_dict(user_info: dict, permission) -> bool:
    """Import from app.py at runtime."""
    from dashboard.app import has_permission_dict as _has_perm
    return _has_perm(user_info, permission)


def email_belongs_to_identity(email_record, identity: str) -> bool:
    """Import from app.py at runtime."""
    from dashboard.app import email_belongs_to_identity as _belongs
    return _belongs(email_record, identity)


def log_audit(db: Session, username: str, action: str, target: str, ip: str | None, details: str = ""):
    """Import from app.py at runtime."""
    from dashboard.app import log_audit as _log
    return _log(db, username, action, target, ip, details)


# Import Permission enum at runtime
def get_permission():
    from dashboard.rbac import Permission
    return Permission


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/api/emails/{email_id}/report-false-negative")
async def api_report_false_negative(
    email_id: str,
    payload: FalseNegativeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Report an email that was classified as safe but is actually dangerous (false negative)."""
    user_info = get_authenticated_api_user(request, db, allow_mailbox_token=True)
    Permission = get_permission()
    
    # Fetch the email record
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    
    if not email_record:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # Check if user has permission (admins/superadmins can report any, users only their own)
    is_privileged = has_permission_dict(user_info, Permission.REVIEW_QUARANTINE)
    if not is_privileged:
        owner = user_info.get("email") or f"{user_info.get('username', '')}@"
        if not email_belongs_to_identity(email_record, owner):
            raise HTTPException(status_code=403, detail="You do not have permission to report this email")
    
    # Validate corrected label
    valid_labels = ["spam", "phishing", "malware", "suspicious"]
    if payload.corrected_label.lower() not in valid_labels:
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
        corrected_label=payload.corrected_label.lower(),
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
        notes=f"Corrected label: {payload.corrected_label}. {payload.notes}",
    )
    db.add(feedback)
    
    # Mark the email as confirmed spam/phishing
    email_record.status = "confirmed_spam"
    
    log_audit(db, user_info["username"], "report_false_negative", email_id,
              request.client.host if request.client else None, 
              f"Corrected to: {payload.corrected_label}")
    
    db.commit()
    
    return {"ok": True, "training_sample_id": training_sample.id, "status": "pending_review"}


@router.get("/api/admin/training-samples")
async def api_get_training_samples(
    request: Request,
    status: str | None = Query(None),
    feedback_type: str | None = Query(None),
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


@router.put("/api/admin/training-samples/{sample_id}")
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
        sample.corrected_label = payload.corrected_label.lower()
    
    if payload.status:
        sample.status = payload.status
        if payload.status in ["approved", "rejected"]:
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


@router.delete("/api/admin/training-samples/{sample_id}")
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


@router.post("/api/admin/training/export-dataset")
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
            "Content-Disposition": f"attachment; filename=training_samples_{status}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@router.get("/api/admin/training/stats")
async def api_get_training_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get training dataset statistics (superadmin only)."""
    user_info = get_authenticated_api_user(request, db)
    
    if user_info["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
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
    }


@router.post("/api/admin/training/retrain")
async def api_trigger_retrain(
    request: Request,
    db: Session = Depends(get_db)
):
    """Trigger model retraining with approved samples (superadmin only).
    
    NOTE: This endpoint currently returns a placeholder. In production, this should:
    1. Export approved training samples to a training dataset
    2. Trigger a background job (Celery, RQ, or Kubernetes Job) to retrain the model
    3. Return a job ID for status tracking
    
    For now, it marks approved samples as 'used_in_training' and returns success.
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
    
    # Mark samples as used
    for sample in approved_samples:
        sample.status = "used_in_training"
        sample.used_in_training_at = _utcnow()
    
    log_audit(db, user_info["username"], "trigger_retrain", "",
              request.client.host if request.client else None, 
              f"Retraining triggered with {len(approved_samples)} samples")
    db.commit()
    
    try:
        # Generate a unique job ID for tracking
        job_id = f"retrain-{int(datetime.datetime.now().timestamp())}"
        
        # In a real production system without Celery, we use FastAPI background tasks
        # but since we want to return the job ID immediately, we just mock the submission
        # In the future, you can implement a dedicated Redis Queue worker for retraining
        
        return {
            "ok": True,
            "job_id": job_id,
            "samples_count": len(approved_samples),
            "message": f"Retraining job {job_id} registered with {len(approved_samples)} samples. (Placeholder execution)"
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Failed to submit retraining task")
        return {
            "ok": True,
            "samples_count": len(approved_samples),
            "note": "Samples marked as 'used_in_training' but task registration failed.",
            "error": str(e)
        }

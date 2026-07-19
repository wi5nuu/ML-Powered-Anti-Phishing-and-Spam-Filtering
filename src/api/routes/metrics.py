from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.infrastructure.database.session import get_db
from src.domain.entities import QuarantineEmail

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    clean = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "DELIVER").scalar() or 0
    warn = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "WARN").scalar() or 0
    quarantine = db.query(func.count(QuarantineEmail.id)).filter(QuarantineEmail.label == "QUARANTINE").scalar() or 0
    return {"total_emails": total, "clean": clean, "warn": warn, "quarantine": quarantine}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    return get_metrics(db)


@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "CogniMail API"}

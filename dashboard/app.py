"""
Admin Dashboard — FastAPI + Jinja2.

Fitur:
  1. Tabel email karantina + WARN, sortir by score DESC
  2. Detail email dengan XAI explanation dalam bahasa manusia
  3. Aksi: Lepaskan ke Inbox, Konfirmasi Spam, Laporkan False Positive
  4. Metrics panel: statistik mingguan, distribusi label
  5. Feedback loop: false positive untuk retraining
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from prometheus_fastapi_instrumentator import Instrumentator

from database.models import Base, QuarantineEmail, Feedback

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DB_URL", "sqlite:///./lti_antiphishing.db")
DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "insecure-dev-key")

engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

app = FastAPI(title="LTI Anti-Phishing Dashboard", version="1.0.0")
Instrumentator().instrument(app).expose(app)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))
templates.env.globals["max"] = max


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
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
    })


@app.get("/email/{email_id}")
async def email_detail(email_id: str, request: Request, db: Session = Depends(get_db)):
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

    return templates.TemplateResponse(request, "email_detail.html", {
        "email": email_record,
        "reasons": reasons,
        "human_reasons": human_reasons,
    })


@app.post("/email/{email_id}/release")
async def release_email(email_id: str, db: Session = Depends(get_db)):
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(404, "Email not found")
    email_record.status = "released"
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/email/{email_id}/confirm-spam")
async def confirm_spam(email_id: str, db: Session = Depends(get_db)):
    email_record = db.query(QuarantineEmail).filter(
        QuarantineEmail.email_id == email_id
    ).first()
    if not email_record:
        raise HTTPException(404, "Email not found")
    email_record.status = "confirmed_spam"
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/email/{email_id}/report-false-positive")
async def report_false_positive(email_id: str, notes: str = Form(""),
                                 db: Session = Depends(get_db)):
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
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/metrics-panel")
async def metrics_panel(request: Request, db: Session = Depends(get_db)):
    total = db.query(func.count(QuarantineEmail.id)).scalar() or 0
    quarantine_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "QUARANTINE"
    ).scalar() or 0
    warn_count = db.query(func.count(QuarantineEmail.id)).filter(
        QuarantineEmail.label == "WARN"
    ).scalar() or 0

    top_senders = db.query(
        QuarantineEmail.sender, func.count(QuarantineEmail.id).label("count")
    ).group_by(QuarantineEmail.sender).order_by(
        func.count(QuarantineEmail.id).desc()
    ).limit(10).all()

    feedback_count = db.query(func.count(Feedback.id)).scalar() or 0

    return templates.TemplateResponse(request, "metrics.html", {
        "total": total,
        "quarantine_count": quarantine_count,
        "warn_count": warn_count,
        "top_senders": top_senders,
        "feedback_count": feedback_count,
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

"""
SQLAlchemy models untuk LTI Anti-Phishing.

Tabel:
  - quarantine_emails: email yang dikarantina atau masuk kategori WARN
  - feedback: false positive reports dari admin dashboard
  - pipeline_metrics: ringkasan metrik harian (opsional, bisa dari Prometheus)
"""

import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum as SAEnum
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    RELEASED = "released"
    CONFIRMED_SPAM = "confirmed_spam"


class QuarantineEmail(Base):
    __tablename__ = "quarantine_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(64), unique=True, nullable=False, index=True)
    received_at = Column(String(32), nullable=False)
    label = Column(String(16), nullable=False)
    fused_score = Column(Float, nullable=False)
    sa_score = Column(Float, default=0.0)
    ml_probability = Column(Float, default=0.0)
    xai_summary = Column(Text, default="")
    routing_reason = Column(Text, default="")
    raw_content_hash = Column(String(64), default="")
    status = Column(String(16), default=EmailStatus.PENDING.value)
    subject = Column(String(512), default="")
    sender = Column(String(256), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(64), nullable=False, index=True)
    feedback_type = Column(String(32), nullable=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class PipelineMetrics(Base):
    __tablename__ = "pipeline_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(16), nullable=False)
    total_processed = Column(Integer, default=0)
    total_clean = Column(Integer, default=0)
    total_warn = Column(Integer, default=0)
    total_quarantine = Column(Integer, default=0)
    false_positive_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

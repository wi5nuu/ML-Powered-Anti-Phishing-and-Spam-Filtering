"""
SQLAlchemy models untuk LTI Anti-Phishing — Enterprise Edition.
"""

import datetime
import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine

Base = declarative_base()


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    RELEASED = "released"
    CONFIRMED_SPAM = "confirmed_spam"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    role = Column(String(16), default=UserRole.VIEWER.value)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(64), nullable=False)
    action = Column(String(32), nullable=False)
    email_id = Column(String(64), nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class QuarantineEmail(Base):
    __tablename__ = "quarantine_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(64), unique=True, nullable=False, index=True)
    received_at = Column(String(32), nullable=False)
    label = Column(String(16), nullable=False)
    fused_score = Column(Float, nullable=False)
    sa_score = Column(Float, default=0.0)
    ml_probability = Column(Float, default=0.0)
    anomaly_score = Column(Float, default=0.0)
    shap_json = Column(Text, default="")
    xai_summary = Column(Text, default="")
    routing_reason = Column(Text, default="")
    raw_content_hash = Column(String(64), default="")
    raw_content = Column(Text, default="")          # Raw email content (for forensics)
    status = Column(String(16), default=EmailStatus.PENDING.value)
    subject = Column(String(512), default="")
    sender = Column(String(256), default="")
    recipient_list = Column(Text, default="")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    model_version = Column(String(32), default="")
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
    avg_latency_ms = Column(Float, default=0.0)
    model_version = Column(String(32), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(128), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    rate_limit = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db(db_url: str = "sqlite:///./lti_antiphishing.db"):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine

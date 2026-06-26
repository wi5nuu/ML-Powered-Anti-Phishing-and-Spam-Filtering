"""
SQLAlchemy models untuk LTI Anti-Phishing — Enterprise Edition.
"""

import datetime
import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum as SAEnum, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import create_engine

Base = declarative_base()


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    RELEASED = "released"
    CONFIRMED_SPAM = "confirmed_spam"


class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    SECURITY_ADMIN = "security_admin"
    ANALYST = "analyst"
    MAIL_REVIEWER = "mail_reviewer"
    USER = "user"


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
    email = Column(String(255), unique=True, nullable=True, index=True)
    hashed_password = Column(String(128), nullable=False)
    role = Column(String(16), default=UserRole.ANALYST.value)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(64), nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)
    email_id = Column(String(64), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    @hybrid_property
    def username(self):
        return self.user

    @username.setter
    def username(self, value):
        self.user = value

    @hybrid_property
    def notes(self):
        return self.details

    @notes.setter
    def notes(self, value):
        self.details = value


class QuarantineEmail(Base):
    __tablename__ = "quarantine_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(64), unique=True, nullable=False, index=True)
    received_at = Column(String(32), nullable=False)
    label = Column(String(16), nullable=False, index=True)
    fused_score = Column(Float, nullable=False)
    sa_score = Column(Float, default=0.0)
    ml_probability = Column(Float, default=0.0)
    anomaly_score = Column(Float, default=0.0)
    shap_json = Column(Text, default="")
    xai_summary = Column(Text, default="")
    routing_reason = Column(Text, default="")
    raw_content_hash = Column(String(64), default="")
    raw_content = Column(Text, default="")          # Raw email content (for forensics)
    status = Column(String(16), default=EmailStatus.PENDING.value, index=True)
    category = Column(String(32), default="", index=True)
    subject = Column(String(512), default="")
    sender = Column(String(256), default="", index=True)
    recipient_list = Column(Text, default="")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    model_version = Column(String(32), default="", index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(64), nullable=False, index=True)
    feedback_type = Column(String(32), nullable=False, index=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class PipelineMetrics(Base):
    __tablename__ = "pipeline_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(16), nullable=False, index=True)
    total_processed = Column(Integer, default=0)
    total_clean = Column(Integer, default=0)
    total_warn = Column(Integer, default=0)
    total_quarantine = Column(Integer, default=0)
    false_positive_count = Column(Integer, default=0)
    avg_latency_ms = Column(Float, default=0.0)
    model_version = Column(String(32), default="", index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(32), default="other", index=True)
    priority = Column(String(16), default="normal", index=True)
    status = Column(String(16), default="open", index=True)
    admin_reply = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(128), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    rate_limit = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(32), unique=True, nullable=False, index=True)
    model_type = Column(String(32), nullable=False, index=True)  # e.g., "xgboost", "isolation_forest", "one_class_svm"
    filepath = Column(String(255), nullable=True)
    metrics = Column(JSON, default=dict)  # accuracy, f1_score, precision, recall, confusion_matrix, etc.
    is_active = Column(Boolean, default=False, index=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    actor = Column(String(64), nullable=False, index=True)  # user or system/worker
    action = Column(String(64), nullable=False, index=True)  # e.g., "train", "inference", "quarantine", "settings_change"
    target_type = Column(String(64), nullable=True, index=True)  # e.g., "email", "model", "settings"
    target_id = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False)  # "SUCCESS", "FAILURE"
    changes = Column(JSON, nullable=True)  # JSON diff or changes details
    ip_address = Column(String(45), nullable=True)
    description = Column(Text, nullable=True)


def init_db(db_url: str = "sqlite:///./lti_antiphishing.db"):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine

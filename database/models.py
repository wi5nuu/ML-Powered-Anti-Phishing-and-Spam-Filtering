"""
SQLAlchemy models untuk CogniMail — Enterprise Edition.
"""

import datetime
import enum
from datetime import timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine


def _utcnow():
    return datetime.datetime.now(timezone.utc)

Base = declarative_base()


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    RELEASED = "released"
    CONFIRMED_SPAM = "confirmed_spam"
    TRASH = "trash"


class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    avatar_url = Column(String(512), default="")
    hashed_password = Column(String(128), nullable=False)
    role = Column(String(16), default=UserRole.USER.value)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    forward_to = Column(String(255), default="")
    forward_enabled = Column(Boolean, default=False)
    forward_keep_copy = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class AdminMailbox(Base):
    __tablename__ = "admin_mailboxes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(128), default="")
    sender_name = Column(String(255), default="")
    avatar_url = Column(String(512), default="")
    forward_to = Column(String(255), default="")
    forward_enabled = Column(Boolean, default=False)
    forward_keep_copy = Column(Boolean, default=True)
    assigned_to = Column(String(64), default="", index=True)
    created_by = Column(String(64), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class AdminMailboxAccess(Base):
    __tablename__ = "admin_mailbox_access"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mailbox_id = Column(Integer, ForeignKey("admin_mailboxes.id"), nullable=False, index=True)
    username = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("mailbox_id", "username", name="uq_mailbox_access_mailbox_user"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(64), nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)
    email_id = Column(String(64), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

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
    received_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    label = Column(String(16), nullable=False, index=True)
    fused_score = Column(Float, nullable=False)
    message_id = Column(String(255), default="", index=True)
    sa_score = Column(Float, default=0.0)
    ml_probability = Column(Float, default=0.0)
    anomaly_score = Column(Float, default=0.0)
    shap_json = Column(Text, default="")
    xai_summary = Column(Text, default="")
    routing_reason = Column(Text, default="")
    raw_content_hash = Column(String(64), default="")
    raw_content = Column(Text, default="")          # Raw email content (for forensics)
    attachments_json = Column(Text, default="")
    spf_result = Column(String(32), default="")
    dkim_result = Column(String(32), default="")
    dmarc_result = Column(String(32), default="")
    status = Column(String(16), default=EmailStatus.PENDING.value, index=True)
    is_read = Column(Boolean, default=False, index=True)
    is_starred = Column(Boolean, default=False, index=True)
    snoozed_until = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    category = Column(String(32), default="", index=True)
    subject = Column(String(512), default="")
    sender = Column(String(256), default="", index=True)
    recipient_list = Column(Text, default="")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    model_version = Column(String(32), default="", index=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(64), nullable=False, index=True)
    feedback_type = Column(String(32), nullable=False, index=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


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
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


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
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(128), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    rate_limit = Column(Integer, default=100)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(32), unique=True, nullable=False, index=True)
    model_type = Column(String(32), nullable=False, index=True)  # e.g., "xgboost", "isolation_forest", "one_class_svm"
    filepath = Column(String(255), nullable=True)
    metrics = Column(JSON, default=dict)  # accuracy, f1_score, precision, recall, confusion_matrix, etc.
    is_active = Column(Boolean, default=False, index=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)


class TrainingSample(Base):
    __tablename__ = "training_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(64), nullable=False, index=True)
    raw_email = Column(Text, nullable=False)  # Full email content for retraining
    original_label = Column(String(32), nullable=False, index=True)  # Original classification (CLEAN, WARN, QUARANTINE)
    corrected_label = Column(String(32), nullable=False, index=True)  # Corrected label (spam, phishing, clean)
    feedback_type = Column(String(32), nullable=False, index=True)  # false_negative, false_positive, relabel
    original_scores = Column(JSON, default=dict)  # Original fused_score, ml_probability, anomaly_score, sa_score
    subject = Column(String(512), default="")
    sender = Column(String(256), default="", index=True)
    recipient_list = Column(Text, default="")
    status = Column(String(32), default="pending", index=True)  # pending, approved, rejected, used_in_training
    notes = Column(Text, default="")  # Admin notes or reasoning
    reported_by = Column(String(64), nullable=False, index=True)  # Username who reported
    reviewed_by = Column(String(64), nullable=True)  # Admin who reviewed
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    used_in_training_at = Column(DateTime(timezone=True), nullable=True, index=True)


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False, index=True)
    actor = Column(String(64), nullable=False, index=True)  # user or system/worker
    action = Column(String(64), nullable=False, index=True)  # e.g., "train", "inference", "quarantine", "settings_change"
    target_type = Column(String(64), nullable=True, index=True)  # e.g., "email", "model", "settings"
    target_id = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False)  # "SUCCESS", "FAILURE"
    changes = Column(JSON, nullable=True)  # JSON diff or changes details
    ip_address = Column(String(45), nullable=True)
    description = Column(Text, nullable=True)


def init_db(db_url: str = None):
    """
    Inisialisasi database engine dan buat semua tabel.
    db_url harus PostgreSQL (postgresql+psycopg://...).
    Ambil dari env var DB_SYNC_URL, DASHBOARD_DB_URL, atau DB_URL.
    """
    import os
    if db_url is None:
        db_url = (
            os.getenv("DB_SYNC_URL")
            or os.getenv("DASHBOARD_DB_URL")
            or os.getenv("DB_URL")
        )
    if not db_url:
        raise RuntimeError(
            "Database URL tidak ditemukan. "
            "Set env var DB_SYNC_URL atau DASHBOARD_DB_URL dengan PostgreSQL URL. "
            "Contoh: postgresql+psycopg://cogniuser:password@postgres:5432/cognimail"
        )
    if "sqlite" in db_url.lower():
        raise RuntimeError(
            "SQLite tidak didukung di production. "
            "Gunakan PostgreSQL: postgresql+psycopg://cogniuser:password@postgres:5432/cognimail"
        )
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine

import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Float, Boolean, DateTime, Text, JSON, ForeignKey
from src.infrastructure.database.session import Base


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
    role = Column(String(16), default="user")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AdminMailbox(Base):
    __tablename__ = "admin_mailboxes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(128), default="")
    sender_name = Column(String(255), default="")
    forward_to = Column(String(255), default="")
    forward_enabled = Column(Boolean, default=False)
    forward_keep_copy = Column(Boolean, default=True)
    assigned_to = Column(String(255), default="")
    storage_bytes = Column(BigInteger, default=0)
    created_by = Column(String(64), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(64), nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)
    email_id = Column(String(64), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


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
    raw_content = Column(Text, default="")
    attachments_json = Column(Text, default="")
    spf_result = Column(String(32), default="")
    dkim_result = Column(String(32), default="")
    dmarc_result = Column(String(32), default="")
    status = Column(String(16), default="pending", index=True)
    is_read = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
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
    model_type = Column(String(32), nullable=False, index=True)
    filepath = Column(String(255), nullable=True)
    metrics = Column(JSON, default=dict)
    is_active = Column(Boolean, default=False, index=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    actor = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=True, index=True)
    target_id = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False)
    changes = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    description = Column(Text, nullable=True)

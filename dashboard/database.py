"""
Shared database session dependency.

Avoids circular imports between app.py and auth.py.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from database.models import AdminMailbox, AdminMailboxAccess, AuditLog, Base

# Use absolute path to project root so worker & dashboard share the same DB.
# For production, prefer DASHBOARD_DB_URL/DB_SYNC_URL because the worker uses
# an async SQLAlchemy URL while this dashboard session is synchronous.
_project_root = Path(__file__).parent.parent
_default_db = f"sqlite:///{_project_root / 'cognimail.db'}"
DB_URL = (
    os.getenv("DASHBOARD_DB_URL")
    or os.getenv("DB_SYNC_URL")
    or os.getenv("DB_URL")
    or _default_db
)
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)


def _ensure_schema_compatibility():
    inspector = inspect(engine)
    Base.metadata.create_all(engine)
    table_names = inspector.get_table_names()
    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "avatar_url" not in user_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512) DEFAULT ''"))
    if "quarantine_emails" in table_names:
        email_columns = {column["name"] for column in inspector.get_columns("quarantine_emails")}
        email_statements = []
        if "is_read" not in email_columns:
            email_statements.append("ALTER TABLE quarantine_emails ADD COLUMN is_read BOOLEAN DEFAULT FALSE")
        if "deleted_at" not in email_columns:
            email_statements.append("ALTER TABLE quarantine_emails ADD COLUMN deleted_at TIMESTAMP")
        if "attachments_json" not in email_columns:
            email_statements.append("ALTER TABLE quarantine_emails ADD COLUMN attachments_json TEXT")
        if "spf_result" not in email_columns:
            email_statements.append("ALTER TABLE quarantine_emails ADD COLUMN spf_result VARCHAR(32) DEFAULT ''")
        if "dkim_result" not in email_columns:
            email_statements.append("ALTER TABLE quarantine_emails ADD COLUMN dkim_result VARCHAR(32) DEFAULT ''")
        if "dmarc_result" not in email_columns:
            email_statements.append("ALTER TABLE quarantine_emails ADD COLUMN dmarc_result VARCHAR(32) DEFAULT ''")
        if email_statements:
            with engine.begin() as conn:
                for statement in email_statements:
                    conn.execute(text(statement))
    if "admin_mailboxes" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("admin_mailboxes")}
    statements = []
    if "password_hash" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN password_hash VARCHAR(128) DEFAULT ''")
    if "sender_name" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN sender_name VARCHAR(255) DEFAULT ''")
    if "avatar_url" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN avatar_url VARCHAR(512) DEFAULT ''")
    if "forward_to" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_to VARCHAR(255) DEFAULT ''")
    if "forward_enabled" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_enabled BOOLEAN DEFAULT FALSE")
    if "forward_keep_copy" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_keep_copy BOOLEAN DEFAULT TRUE")
    if "assigned_to" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN assigned_to VARCHAR(255) DEFAULT ''")
    if "storage_bytes" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN storage_bytes BIGINT DEFAULT 0")
    if not statements:
        return
    with engine.begin() as conn:
      for statement in statements:
          conn.execute(text(statement))


def _seed_mailbox_access():
    with Session(engine) as db:
        rows = db.query(AdminMailbox).all()
        changed = False

        def add_access(mailbox_id, username):
            nonlocal changed
            if not mailbox_id or not username:
                return
            existing = db.query(AdminMailboxAccess).filter(
                AdminMailboxAccess.mailbox_id == mailbox_id,
                AdminMailboxAccess.username == username,
            ).first()
            if existing:
                return
            db.add(AdminMailboxAccess(mailbox_id=mailbox_id, username=username))
            changed = True

        for mailbox in rows:
            if not mailbox.created_by:
                continue
            add_access(mailbox.id, mailbox.created_by)

        mailbox_by_email = {mailbox.email.lower(): mailbox for mailbox in rows if mailbox.email}
        logs = db.query(AuditLog).filter(
            AuditLog.action.in_(("create_mailbox", "add_existing_email"))
        ).all()
        for log in logs:
            email = (log.details or "").strip().lower()
            mailbox = mailbox_by_email.get(email)
            if not mailbox:
                continue
            add_access(mailbox.id, log.user)

        if changed:
            db.commit()


_ensure_schema_compatibility()
_seed_mailbox_access()
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

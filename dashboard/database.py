"""
Shared database session dependency.

Avoids circular imports between app.py and auth.py.
Production: hanya PostgreSQL. SQLite tidak didukung.
Testing: set ENV=testing to allow SQLite in-memory databases.
"""
import logging
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

log = logging.getLogger(__name__)

from database.models import AdminMailbox, AdminMailboxAccess, AuditLog, Base

# WORKER_DB_URL uses asyncpg driver — convert to sync psycopg for dashboard
_worker_url = os.getenv("WORKER_DB_URL", "")
_worker_sync = (
    _worker_url
    .replace("postgresql+asyncpg://", "postgresql+psycopg://")
    if _worker_url else ""
)

DB_URL = (
    os.getenv("DASHBOARD_DB_URL")
    or os.getenv("DB_SYNC_URL")
    or os.getenv("DB_URL")
    or _worker_sync
)

_ENV = os.getenv("ENV", "production").lower()
_is_testing = _ENV in ("testing", "test")

if not DB_URL:
    raise RuntimeError(
        "Database URL tidak ditemukan. "
        "Set DASHBOARD_DB_URL atau DB_SYNC_URL di environment. "
        "Contoh: postgresql+psycopg://cogniuser:password@postgres:5432/cognimail"
    )

if "sqlite" in DB_URL.lower() and not _is_testing:
    raise RuntimeError(
        "SQLite tidak didukung di production. "
        "Gunakan PostgreSQL: postgresql+psycopg://cogniuser:password@postgres:5432/cognimail"
    )

# SQLite needs check_same_thread=False for multi-threaded test runners
_connect_args = {"check_same_thread": False} if "sqlite" in DB_URL.lower() else {}
_engine_kwargs = {"connect_args": _connect_args}
if "sqlite" not in DB_URL.lower():
    try:
        _pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
    except (ValueError, TypeError):
        log.warning("Invalid DB_POOL_SIZE=%r, using default 10", os.getenv("DB_POOL_SIZE"))
        _pool_size = 10
    try:
        _max_overflow = int(os.getenv("DB_POOL_OVERFLOW", "20"))
    except (ValueError, TypeError):
        log.warning("Invalid DB_POOL_OVERFLOW=%r, using default 20", os.getenv("DB_POOL_OVERFLOW"))
        _max_overflow = 20
    try:
        _pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    except (ValueError, TypeError):
        log.warning("Invalid DB_POOL_TIMEOUT=%r, using default 30", os.getenv("DB_POOL_TIMEOUT"))
        _pool_timeout = 30
    _engine_kwargs.update(
        pool_size=_pool_size,
        max_overflow=_max_overflow,
        pool_timeout=_pool_timeout,
        pool_pre_ping=True,
    )
engine = create_engine(DB_URL, **_engine_kwargs)


def _ensure_schema_compatibility():
    # Single authoritative create_all — called once below after all helpers
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    is_postgres = "postgresql" in DB_URL.lower() or "postgres" in DB_URL.lower()

    if "users" in table_names:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        missing = []
        if "avatar_url" not in user_columns:
            missing.append("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512) DEFAULT ''")
        if "forward_to" not in user_columns:
            missing.append("ALTER TABLE users ADD COLUMN forward_to VARCHAR(255) DEFAULT ''")
        if "forward_enabled" not in user_columns:
            missing.append("ALTER TABLE users ADD COLUMN forward_enabled BOOLEAN DEFAULT FALSE")
        if "forward_keep_copy" not in user_columns:
            missing.append("ALTER TABLE users ADD COLUMN forward_keep_copy BOOLEAN DEFAULT TRUE")
        for stmt in missing:
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(text(stmt.replace("ADD COLUMN ", "ADD COLUMN IF NOT EXISTS ")))
                    else:
                        conn.execute(text(stmt))
                log.info("migration: ran: %s", stmt)
            except Exception as exc:
                log.warning("migration: failed (%s): %s", stmt, exc)
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
        if "message_id" not in email_columns:
            email_statements.append("ALTER TABLE quarantine_emails ADD COLUMN message_id VARCHAR(255) DEFAULT ''")
        for stmt in email_statements:
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(text(stmt.replace("ADD COLUMN ", "ADD COLUMN IF NOT EXISTS ")))
                    else:
                        conn.execute(text(stmt))
                log.info("migration: ran: %s", stmt)
            except Exception as exc:
                log.warning("migration: failed (%s): %s", stmt, exc)
    if "admin_mailboxes" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("admin_mailboxes")}
    mb_statements = []
    if "password_hash" not in columns:
        mb_statements.append("ALTER TABLE admin_mailboxes ADD COLUMN password_hash VARCHAR(128) DEFAULT ''")
    if "sender_name" not in columns:
        mb_statements.append("ALTER TABLE admin_mailboxes ADD COLUMN sender_name VARCHAR(255) DEFAULT ''")
    if "avatar_url" not in columns:
        mb_statements.append("ALTER TABLE admin_mailboxes ADD COLUMN avatar_url VARCHAR(512) DEFAULT ''")
    if "forward_to" not in columns:
        mb_statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_to VARCHAR(255) DEFAULT ''")
    if "forward_enabled" not in columns:
        mb_statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_enabled BOOLEAN DEFAULT FALSE")
    if "forward_keep_copy" not in columns:
        mb_statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_keep_copy BOOLEAN DEFAULT TRUE")
    if "assigned_to" not in columns:
        mb_statements.append("ALTER TABLE admin_mailboxes ADD COLUMN assigned_to VARCHAR(64) DEFAULT ''")
    for stmt in mb_statements:
        try:
            with engine.begin() as conn:
                if is_postgres:
                    conn.execute(text(stmt.replace("ADD COLUMN ", "ADD COLUMN IF NOT EXISTS ")))
                else:
                    conn.execute(text(stmt))
            log.info("migration: ran: %s", stmt)
        except Exception as exc:
            log.warning("migration: failed (%s): %s", stmt, exc)


def _seed_mailbox_access():
    with Session(engine) as db:
        rows = db.query(AdminMailbox).limit(5000).all()
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
        for audit_entry in logs:
            email = (audit_entry.details or "").strip().lower()
            mailbox = mailbox_by_email.get(email)
            if not mailbox:
                continue
            add_access(mailbox.id, audit_entry.user)

        if changed:
            db.commit()


# Schema compatibility and seeding now handled on-demand in routes or startup
# NOT at module import to avoid blocking
SessionLocal = sessionmaker(bind=engine)

# Re-enable these functions but call them explicitly during app startup, not module import
def init_database_schema():
    """Call this during app startup, not module import."""
    _ensure_schema_compatibility()
    _seed_mailbox_access()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

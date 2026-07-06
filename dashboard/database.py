"""
Shared database session dependency.

Avoids circular imports between app.py and auth.py.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from database.models import Base

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
    if "admin_mailboxes" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("admin_mailboxes")}
    statements = []
    if "password_hash" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN password_hash VARCHAR(128) DEFAULT ''")
    if "sender_name" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN sender_name VARCHAR(255) DEFAULT ''")
    if "forward_to" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_to VARCHAR(255) DEFAULT ''")
    if "forward_enabled" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_enabled BOOLEAN DEFAULT FALSE")
    if "forward_keep_copy" not in columns:
        statements.append("ALTER TABLE admin_mailboxes ADD COLUMN forward_keep_copy BOOLEAN DEFAULT TRUE")
    if not statements:
        return
    with engine.begin() as conn:
      for statement in statements:
          conn.execute(text(statement))


_ensure_schema_compatibility()
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

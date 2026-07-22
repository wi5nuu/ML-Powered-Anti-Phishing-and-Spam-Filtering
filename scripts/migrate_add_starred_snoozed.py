"""
Migration script to add is_starred and snoozed_until fields to quarantine_emails table.

Dijalankan sekali untuk update schema PostgreSQL yang sudah ada.

Usage:
    # Dari dalam container atau dengan env var tersedia:
    python scripts/migrate_add_starred_snoozed.py

    # Atau via Docker:
    docker compose exec dashboard python /app/scripts/migrate_add_starred_snoozed.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

from sqlalchemy import create_engine, text


def get_db_url() -> str:
    """Ambil PostgreSQL sync URL dari environment."""
    worker_url = os.getenv("WORKER_DB_URL", "")
    sync_from_worker = worker_url.replace("postgresql+asyncpg://", "postgresql+psycopg://") if worker_url else ""
    url = (
        os.getenv("DASHBOARD_DB_URL")
        or os.getenv("DB_SYNC_URL")
        or os.getenv("DB_URL")
        or sync_from_worker
    )
    if not url:
        raise RuntimeError(
            "Database URL tidak ditemukan. "
            "Set DASHBOARD_DB_URL atau WORKER_DB_URL di .env"
        )
    if "sqlite" in url.lower():
        raise RuntimeError("SQLite tidak didukung. Gunakan PostgreSQL.")
    return url


def migrate_database():
    """Add is_starred and snoozed_until columns to quarantine_emails table (PostgreSQL)."""
    db_url = get_db_url()
    print(f"Connecting to database...\n")
    engine = create_engine(db_url)

    try:
        with engine.begin() as conn:
            # PostgreSQL: ADD COLUMN IF NOT EXISTS
            print("Adding is_starred column (if not exists)...")
            conn.execute(text(
                "ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS is_starred BOOLEAN DEFAULT FALSE"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_quarantine_emails_is_starred ON quarantine_emails(is_starred)"
            ))
            print("[OK] is_starred done")

            print("Adding snoozed_until column (if not exists)...")
            conn.execute(text(
                "ALTER TABLE quarantine_emails ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMP"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_quarantine_emails_snoozed_until ON quarantine_emails(snoozed_until)"
            ))
            print("[OK] snoozed_until done")

        print("\n[SUCCESS] Migration completed successfully!")

    except Exception as e:
        # Re-raise with explicit type so callers can distinguish migration
        # failures from other RuntimeError subclasses.
        print(f"[ERROR] Migration failed: {type(e).__name__}: {e}")
        raise RuntimeError(f"Migration failed: {e}") from e
    finally:
        engine.dispose()


if __name__ == "__main__":
    migrate_database()

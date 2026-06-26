"""Add category column to quarantine_emails and update existing data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import QuarantineEmail
from dashboard.database import SessionLocal, engine
import sqlalchemy as sa

db = SessionLocal()
inspector = sa.inspect(engine)
cols = [c["name"] for c in inspector.get_columns("quarantine_emails")]

if "category" not in cols:
    db.execute(sa.text("ALTER TABLE quarantine_emails ADD COLUMN category VARCHAR(32) DEFAULT ''"))
    db.commit()
    print("Added category column to quarantine_emails")
else:
    print("category column already exists")

CAT_MAP = {"CLEAN": "internal_document", "WARN": "spam", "QUARANTINE": "spam"}
for lbl, cat in CAT_MAP.items():
    result = db.query(QuarantineEmail).filter(QuarantineEmail.label == lbl).update(
        {"category": cat}, synchronize_session=False
    )
    if result:
        print(f"Updated {result} emails: label={lbl} -> category={cat}")

db.commit()
db.close()
print("Done")

"""
Shared database session dependency.

Avoids circular imports between app.py and auth.py.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database.models import Base

# Use absolute path to project root so worker & dashboard share the same DB
_project_root = Path(__file__).parent.parent
_default_db = f"sqlite:///{_project_root / 'lti_antiphishing.db'}"
DB_URL = os.getenv("DB_URL", _default_db)
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

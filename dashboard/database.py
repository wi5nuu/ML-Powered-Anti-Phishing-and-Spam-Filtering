"""
Shared database session dependency.

Avoids circular imports between app.py and auth.py.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database.models import Base

DB_URL = os.getenv("DB_URL", "sqlite:///./lti_antiphishing.db")
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

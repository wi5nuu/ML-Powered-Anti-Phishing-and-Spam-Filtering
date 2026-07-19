import logging
import os
from sqlalchemy.orm import Session
from src.infrastructure.database.session import SessionLocal
from src.infrastructure.auth.jwt import hash_password
from src.domain.entities import User
from src.config.settings import settings

logger = logging.getLogger(__name__)


def seed_initial_data():
    # SECURITY: Validate default credentials in production
    if os.getenv("ENVIRONMENT") == "production":
        if settings.ADMIN_PASSWORD == "changeme" or settings.SUPERADMIN_PASSWORD == "super":
            raise ValueError(
                "Default credentials detected in production! "
                "Please set ADMIN_PASSWORD and SUPERADMIN_PASSWORD environment variables."
            )
    
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.ADMIN_USERNAME,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            logger.info(f"Seeded admin user: {settings.ADMIN_USERNAME}")

        superadmin = db.query(User).filter(User.username == settings.SUPERADMIN_USERNAME).first()
        if not superadmin:
            superadmin = User(
                username=settings.SUPERADMIN_USERNAME,
                hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
                role="superadmin",
                is_active=True,
            )
            db.add(superadmin)
            logger.info(f"Seeded superadmin user: {settings.SUPERADMIN_USERNAME}")

        db.commit()
    except Exception as e:
        logger.error(f"Seed error: {e}")
        db.rollback()
    finally:
        db.close()

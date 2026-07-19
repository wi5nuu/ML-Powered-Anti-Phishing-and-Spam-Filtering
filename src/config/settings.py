"""
Global configuration for CogniMail — Enterprise Edition.

WARNING: Never commit sensitive default values to production.
All secrets MUST be set via environment variables in production.
"""
import os
import secrets
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings:
    # ── General ──────────────────────────────────────────────────────────────
    APP_NAME: str = "CogniMail"
    VERSION: str = "3.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ── Database ─────────────────────────────────────────────────────────────
    DB_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'cognimail.db'}")

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── JWT / Auth ───────────────────────────────────────────────────────────
    # SECURITY: In production, ALWAYS set JWT_SECRET via environment variable.
    # If not set, a random key is generated (tokens invalidated on restart).
    @property
    def JWT_SECRET(self) -> str:
        secret = os.getenv("JWT_SECRET", "")
        if not secret:
            env = os.getenv("ENVIRONMENT", "development")
            if env == "production":
                raise ValueError(
                    "CRITICAL: JWT_SECRET environment variable is REQUIRED in production. "
                    "Generate one with: python -c 'import secrets; print(secrets.token_hex(64))'"
                )
            logger.warning(
                "⚠  JWT_SECRET not set! Using random key — ALL tokens will be "
                "invalidated on server restart. Set JWT_SECRET in .env file."
            )
            secret = secrets.token_hex(64)
        return secret

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    MAILBOX_TOKEN_EXPIRY_HOURS: int = int(os.getenv("MAILBOX_TOKEN_EXPIRY_HOURS", "2"))

    # ── Seed Credentials ─────────────────────────────────────────────────────
    # SECURITY: In production, ALWAYS override these via environment variables.
    @property
    def ADMIN_USERNAME(self) -> str:
        return os.getenv("ADMIN_USERNAME", "admin")

    @property
    def ADMIN_PASSWORD(self) -> str:
        pw = os.getenv("ADMIN_PASSWORD", "")
        if not pw and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("CRITICAL: ADMIN_PASSWORD must be set in production!")
        return pw or "changeme"  # Only used in dev

    @property
    def SUPERADMIN_USERNAME(self) -> str:
        return os.getenv("SUPERADMIN_USERNAME", "superadmin")

    @property
    def SUPERADMIN_PASSWORD(self) -> str:
        pw = os.getenv("SUPERADMIN_PASSWORD", "")
        if not pw and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("CRITICAL: SUPERADMIN_PASSWORD must be set in production!")
        return pw or "superadmin123"  # Only used in dev

    # ── OAuth / Google ───────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # ── SMTP ─────────────────────────────────────────────────────────────────
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # ── IMAP ─────────────────────────────────────────────────────────────────
    IMAP_HOST: str = os.getenv("IMAP_HOST", "localhost")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))

    # ── SpamAssassin ─────────────────────────────────────────────────────────
    SPAMASSASSIN_HOST: str = os.getenv("SPAMASSASSIN_HOST", "localhost")
    SPAMASSASSIN_PORT: int = int(os.getenv("SPAMASSASSIN_PORT", "783"))

    # ── Rate Limiting ────────────────────────────────────────────────────────
    RATE_LIMIT: str = os.getenv("RATE_LIMIT", "20/minute")
    ADMIN_RATE_LIMIT: str = os.getenv("ADMIN_RATE_LIMIT", "60/minute")

    # ── CORS ─────────────────────────────────────────────────────────────────
    @property
    def CORS_ORIGINS(self) -> list[str]:
        origins_str = os.getenv("CORS_ORIGINS", "")
        if origins_str:
            return [o.strip() for o in origins_str.split(",")]
        if os.getenv("ENVIRONMENT") == "production":
            # SECURITY: Replace with your actual production domain
            return ["https://cognimail.yourdomain.com"]
        return ["*"]

    # ── Paths ────────────────────────────────────────────────────────────────
    STATIC_DIR: Path = ROOT_DIR / "frontend" / "static"
    DIST_DIR: Path = STATIC_DIR / "dist"

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(ROOT_DIR / "logs" / "cognimail.log"))

    # ── ML / Model ───────────────────────────────────────────────────────────
    MODEL_DIR: Path = ROOT_DIR / "classifier" / "models"
    AUTO_RETRAIN_INTERVAL_HOURS: int = int(os.getenv("AUTO_RETRAIN_INTERVAL_HOURS", "168"))  # 7 days
    ANOMALY_THRESHOLD: float = float(os.getenv("ANOMALY_THRESHOLD", "0.7"))
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))


settings = Settings()


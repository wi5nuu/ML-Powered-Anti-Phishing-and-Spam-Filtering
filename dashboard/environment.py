"""
Load the project environment before dashboard configuration is evaluated.

Also validates critical security-sensitive env vars early so misconfiguration
is caught at startup rather than silently degrading security at request time.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── JWT secret key strength check ──────────────────────────────────────────
_secret = os.getenv("DASHBOARD_SECRET_KEY", "")
_env = os.getenv("ENV", "production").lower()

if _env not in ("testing", "test", "development", "dev"):
    # Enforce minimum 32-character secret in non-dev environments.
    # A short or default secret makes HS256 tokens trivially brute-forceable.
    if len(_secret) < 32:
        print(
            "[CRITICAL] DASHBOARD_SECRET_KEY is missing or too short "
            f"(got {len(_secret)} chars, need ≥32). "
            "Set a cryptographically random value in .env before starting "
            "the dashboard in production.\n"
            "Generate one with:  python -c \"import secrets; print(secrets.token_hex(32))\"",
            file=sys.stderr,
        )
        sys.exit(1)

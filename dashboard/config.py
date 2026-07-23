"""Runtime configuration helpers shared by dashboard routes."""

import os
import re


def get_configured_mail_domain() -> str:
    """Return the canonical mail domain configured by the deployment.

    ``VITE_MAIL_DOMAIN`` is used by the frontend build and is therefore the
    primary source. The remaining variables keep local/test deployments
    compatible with the SMTP configuration.
    """
    candidates = (
        os.getenv("VITE_MAIL_DOMAIN", ""),
        os.getenv("ACCEPTED_MAIL_DOMAINS", "").split(",", 1)[0],
        os.getenv("SMTP_DOMAIN", ""),
    )
    for value in candidates:
        domain = str(value or "").strip().lower().lstrip("@").rstrip(".")
        if re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", domain or ""):
            return domain
    return "zenime.my.id"


def email_uses_configured_domain(email: str) -> bool:
    value = str(email or "").strip().lower()
    return "@" in value and value.rsplit("@", 1)[1] == get_configured_mail_domain()


def is_valid_email_address(email: str) -> bool:
    value = str(email or "").strip().lower()
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))

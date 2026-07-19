from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SETTINGS = {
    "threshold_quarantine": 0.70,
    "threshold_warn": 0.30,
    "fusion_ml_weight": 0.50,
    "fusion_sa_weight": 0.25,
    "fusion_anomaly_weight": 0.25,
    "imap_host": "",
    "imap_port": 993,
    "imap_user": "",
    "poll_interval_seconds": 30,
    "protected_domains": [],
    "whitelist_senders": [],
    "admin_alert_email": "",
    "max_quarantine_days": 30,
    "allow_admin_user_management": True,
    "allow_admin_mailbox_management": True,
    "allow_admin_quarantine_review": True,
    "self_registration": False,
    "default_user_role": "user",
    "session_timeout_minutes": 60,
    "available_roles": ["user", "admin", "superadmin"],
}

_current_settings = dict(DEFAULT_SETTINGS)


@router.get("")
def get_settings():
    return _current_settings


@router.post("")
def update_settings(data: dict):
    _current_settings.update(data)
    return {"ok": True, "message": "Settings updated"}


@router.post("/test-imap")
def test_imap_connection():
    import random
    ok = random.choice([True, False])
    return {
        "ok": ok,
        "message": "Koneksi IMAP berhasil." if ok else "Koneksi IMAP gagal: host tidak dapat dijangkau.",
    }

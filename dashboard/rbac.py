"""
RBAC — Role-Based Access Control for CogniMail Dashboard.

Defines permissions per role and helper functions used by app.py.
"""

from enum import Enum
from database.models import UserRole


class Permission(str, Enum):
    # Email actions
    RELEASE_EMAIL = "release_email"
    DELETE_EMAIL = "delete_email"
    REVIEW_QUARANTINE = "review_quarantine"

    # Audit & reports
    ACCESS_AUDIT_LOG = "access_audit_log"
    VIEW_ALL_REPORTS = "view_all_reports"
    VIEW_ORG_REPORTS = "view_org_reports"
    VIEW_OWN_REPORTS = "view_own_reports"  # user: submit & view own reports only

    # User management
    MANAGE_ALL_USERS = "manage_all_users"
    MANAGE_ORG_USERS = "manage_org_users"

    # Mailbox management
    MANAGE_ALL_MAILBOXES = "manage_all_mailboxes"
    MANAGE_ORG_MAILBOXES = "manage_org_mailboxes"

    # Settings
    MANAGE_GLOBAL_SETTINGS = "manage_global_settings"

    # System
    ACCESS_SYSTEM_HEALTH = "access_system_health"


# Permissions granted to each role
_ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    UserRole.SUPERADMIN.value: {p for p in Permission},  # all permissions
    UserRole.ADMIN.value: {
        Permission.RELEASE_EMAIL,
        Permission.DELETE_EMAIL,
        Permission.REVIEW_QUARANTINE,
        Permission.ACCESS_AUDIT_LOG,
        Permission.VIEW_ALL_REPORTS,
        Permission.VIEW_ORG_REPORTS,
        Permission.MANAGE_ORG_USERS,
        Permission.MANAGE_ORG_MAILBOXES,
    },
    UserRole.USER.value: {
        Permission.RELEASE_EMAIL,         # User can release their own emails
        Permission.DELETE_EMAIL,          # User can delete their own emails
        Permission.REVIEW_QUARANTINE,     # User can view their own quarantine
        Permission.VIEW_OWN_REPORTS,      # User can submit/view own reports only
    },
    "mailbox": set(),
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    UserRole.SUPERADMIN.value: "Superadmin — akses penuh ke semua fitur sistem.",
    UserRole.ADMIN.value: "Admin — mengelola pengguna, mailbox, dan karantina dalam organisasi.",
    UserRole.USER.value: "User — akses terbatas ke mailbox dan laporan organisasi.",
    "mailbox": "Mailbox — hanya akses ke mailbox sendiri.",
}


def get_user_permissions(role: str) -> set[Permission]:
    """Return the set of permissions for a given role string."""
    return _ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in get_user_permissions(role)


def has_permission_dict(user_info: dict, permission: Permission) -> bool:
    """Check permission using a user_info dict (as used throughout app.py)."""
    role = user_info.get("role", "")
    return permission in get_user_permissions(role)


def check_permission(role: str, permission: Permission) -> bool:
    return has_permission(role, permission)


def check_role(user_info: dict, *roles: str) -> bool:
    """Return True if user's role is in the given roles."""
    return user_info.get("role", "") in roles


def get_user_permissions_list(role: str) -> list[str]:
    return [p.value for p in get_user_permissions(role)]

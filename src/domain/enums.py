"""
CogniMail Role-Based Access Control (RBAC) — Enum Definitions.

This module defines all enums used across the system:
- UserRole: The three-tier role hierarchy
- Permission: Granular permissions for fine-grained access control
- EmailStatus / EmailLabel / EmailCategory: Email classification states
- TicketStatus / TicketPriority / TicketCategory: Support ticket states

ROLE HIERARCHY:
┌─────────────────────────────────────────────────┐
│  SUPERADMIN  (full system access)               │
│  ├── Can manage all users, mailboxes, orgs      │
│  ├── Can view all analytics and audit logs      │
│  └── Can manage system settings and roles       │
├─────────────────────────────────────────────────┤
│  ADMIN  (organization-level access)              │
│  ├── Can manage users within their org          │
│  ├── Can manage mailboxes within their org      │
│  └── Can view org-level analytics               │
├─────────────────────────────────────────────────┤
│  USER  (personal access only)                    │
│  ├── Can access personal mailbox                │
│  ├── Can report spam/phishing                   │
│  └── Can view personal quarantine               │
└─────────────────────────────────────────────────┘

EXTENSIBILITY:
Adding a new role? Simply add it to UserRole enum,
define its permissions in ROLE_PERMISSIONS,
and add a description in ROLE_DESCRIPTIONS.
"""
from enum import Enum as PyEnum


class UserRole(str, PyEnum):
    """
    User roles for the CogniMail RBAC system.
    
    Values are stored as strings in the database.
    NEW ROLES can be added here without breaking existing data.
    """
    SUPERADMIN = "superadmin"  # Full system access
    ADMIN = "admin"            # Organization-level management
    USER = "user"              # Personal mailbox access
    MAILBOX = "mailbox"        # Email mailbox account (non-dashboard)


class Permission(str, PyEnum):
    """
    Granular permissions for fine-grained access control.
    
    Used by the RBAC system in dashboard/rbac.py.
    NEW PERMISSIONS can be added here without breaking existing code.
    """
    # ── User Management ──────────────────────────────────────────────
    VIEW_USERS = "view_users"
    CREATE_USERS = "create_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    
    # ── Mailbox Management ───────────────────────────────────────────
    VIEW_MAILBOXES = "view_mailboxes"
    CREATE_MAILBOXES = "create_mailboxes"
    EDIT_MAILBOXES = "edit_mailboxes"
    DELETE_MAILBOXES = "delete_mailboxes"
    
    # ── Email Operations ─────────────────────────────────────────────
    VIEW_QUARANTINE = "view_quarantine"
    RELEASE_EMAIL = "release_email"
    VIEW_ANALYTICS = "view_analytics"
    VIEW_DETECTION_LOGS = "view_detection_logs"
    REPORT_SPAM = "report_spam"
    
    # ── System Management ────────────────────────────────────────────
    VIEW_AUDIT = "view_audit"
    EDIT_SETTINGS = "edit_settings"
    MANAGE_COMPANIES = "manage_companies"
    VIEW_SYSTEM_HEALTH = "view_system_health"
    MANAGE_ROLES = "manage_roles"


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.SUPERADMIN: {
        Permission.VIEW_USERS, Permission.CREATE_USERS, 
        Permission.EDIT_USERS, Permission.DELETE_USERS,
        Permission.VIEW_MAILBOXES, Permission.CREATE_MAILBOXES, 
        Permission.EDIT_MAILBOXES, Permission.DELETE_MAILBOXES,
        Permission.VIEW_QUARANTINE, Permission.RELEASE_EMAIL,
        Permission.VIEW_ANALYTICS, Permission.VIEW_AUDIT,
        Permission.EDIT_SETTINGS, Permission.MANAGE_COMPANIES,
        Permission.VIEW_SYSTEM_HEALTH, Permission.MANAGE_ROLES,
        Permission.REPORT_SPAM, Permission.VIEW_DETECTION_LOGS,
    },
    UserRole.ADMIN: {
        Permission.VIEW_USERS, Permission.CREATE_USERS, Permission.EDIT_USERS,
        Permission.VIEW_MAILBOXES, Permission.CREATE_MAILBOXES, Permission.EDIT_MAILBOXES,
        Permission.VIEW_QUARANTINE, Permission.RELEASE_EMAIL,
        Permission.VIEW_ANALYTICS, Permission.VIEW_AUDIT,
        Permission.EDIT_SETTINGS, Permission.VIEW_DETECTION_LOGS,
        Permission.REPORT_SPAM,
    },
    UserRole.USER: {
        Permission.VIEW_QUARANTINE, Permission.REPORT_SPAM,
    },
    UserRole.MAILBOX: {
        Permission.REPORT_SPAM,
    },
}


ROLE_DESCRIPTIONS: dict[UserRole, str] = {
    UserRole.SUPERADMIN: "Full access to all platform features — system-wide management",
    UserRole.ADMIN: "Administrator with organization-level access and management",
    UserRole.USER: "Standard dashboard user with personal mailbox and reporting access",
    UserRole.MAILBOX: "Email mailbox account user (programmatic access only)",
}


# ── Email Classification States ─────────────────────────────────────────

class EmailStatus(str, PyEnum):
    """Email processing status in the pipeline."""
    CLEAN = "clean"
    WARN = "warn"
    QUARANTINE = "quarantine"
    CONFIRMED_SPAM = "confirmed_spam"


class EmailLabel(str, PyEnum):
    """Final delivery decision labels."""
    DELIVER = "DELIVER"
    WARN = "WARN"
    QUARANTINE = "QUARANTINE"


class EmailCategory(str, PyEnum):
    """Email classification categories.
    
    NEW CATEGORIES can be added here as new threat types emerge.
    The ML pipeline can be retrained to recognize new categories.
    """
    CLEAN = "clean"
    SPAM = "spam"
    PHISHING = "phishing"
    MALWARE = "malware"


# ── Support Ticket States ───────────────────────────────────────────────

class TicketStatus(str, PyEnum):
    """Support ticket status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class TicketPriority(str, PyEnum):
    """Support ticket priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, PyEnum):
    """Support ticket categories."""
    BUG = "bug"
    QUESTION = "question"
    ACCESS = "access"
    FALSE_POSITIVE = "false_positive"
    OTHER = "other"

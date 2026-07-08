"""
Role-Based Access Control (RBAC) module for CogniMail.

Defines roles and their permissions:
- SUPERADMIN: Full system access
- ADMIN: Organization-level management
- USER: Personal mailbox access
"""

import logging
from enum import Enum
from functools import wraps
from typing import List, Optional
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from database.models import User, UserRole, Organization
from dashboard.database import get_db
from dashboard.auth import get_current_user

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """System permissions"""
    # User Management
    MANAGE_ALL_USERS = "manage_all_users"  # Superadmin only
    MANAGE_ORG_USERS = "manage_org_users"  # Superadmin, Admin
    VIEW_USER_PROFILE = "view_user_profile"  # All authenticated users
    EDIT_OWN_PROFILE = "edit_own_profile"  # All authenticated users
    
    # Mailbox Management
    MANAGE_ALL_MAILBOXES = "manage_all_mailboxes"  # Superadmin only
    MANAGE_ORG_MAILBOXES = "manage_org_mailboxes"  # Superadmin, Admin
    ACCESS_OWN_MAILBOX = "access_own_mailbox"  # All authenticated users
    
    # Email Operations
    REVIEW_QUARANTINE = "review_quarantine"  # Superadmin, Admin
    RELEASE_EMAIL = "release_email"  # Superadmin, Admin (and users on their own emails)
    DELETE_EMAIL = "delete_email"  # Superadmin, Admin
    REPORT_SPAM = "report_spam"  # All authenticated users
    
    # Reports & Analytics
    VIEW_ALL_REPORTS = "view_all_reports"  # Superadmin only
    VIEW_ORG_REPORTS = "view_org_reports"  # Superadmin, Admin
    VIEW_OWN_REPORTS = "view_own_reports"  # All authenticated users
    
    # System Management
    ACCESS_SYSTEM_HEALTH = "access_system_health"  # Superadmin only
    MANAGE_GLOBAL_SETTINGS = "manage_global_settings"  # Superadmin only
    ACCESS_AUDIT_LOG = "access_audit_log"  # Superadmin, Admin
    
    # API Keys
    CREATE_API_KEY = "create_api_key"  # Superadmin, Admin
    DELETE_API_KEY = "delete_api_key"  # Superadmin, Admin


# Role to Permissions mapping
ROLE_PERMISSIONS = {
    UserRole.SUPERADMIN.value: {
        Permission.MANAGE_ALL_USERS,
        Permission.MANAGE_ORG_USERS,
        Permission.VIEW_USER_PROFILE,
        Permission.EDIT_OWN_PROFILE,
        Permission.MANAGE_ALL_MAILBOXES,
        Permission.MANAGE_ORG_MAILBOXES,
        Permission.ACCESS_OWN_MAILBOX,
        Permission.REVIEW_QUARANTINE,
        Permission.RELEASE_EMAIL,
        Permission.DELETE_EMAIL,
        Permission.REPORT_SPAM,
        Permission.VIEW_ALL_REPORTS,
        Permission.VIEW_ORG_REPORTS,
        Permission.VIEW_OWN_REPORTS,
        Permission.ACCESS_SYSTEM_HEALTH,
        Permission.MANAGE_GLOBAL_SETTINGS,
        Permission.ACCESS_AUDIT_LOG,
        Permission.CREATE_API_KEY,
        Permission.DELETE_API_KEY,
    },
    UserRole.ADMIN.value: {
        Permission.MANAGE_ORG_USERS,
        Permission.VIEW_USER_PROFILE,
        Permission.EDIT_OWN_PROFILE,
        Permission.MANAGE_ORG_MAILBOXES,
        Permission.ACCESS_OWN_MAILBOX,
        Permission.REVIEW_QUARANTINE,
        Permission.RELEASE_EMAIL,
        Permission.DELETE_EMAIL,
        Permission.REPORT_SPAM,
        Permission.VIEW_ORG_REPORTS,
        Permission.VIEW_OWN_REPORTS,
        Permission.ACCESS_AUDIT_LOG,
        Permission.CREATE_API_KEY,
        Permission.DELETE_API_KEY,
    },
    UserRole.USER.value: {
        Permission.VIEW_USER_PROFILE,
        Permission.EDIT_OWN_PROFILE,
        Permission.ACCESS_OWN_MAILBOX,
        Permission.REPORT_SPAM,
        Permission.VIEW_OWN_REPORTS,
    },
}


def get_user_permissions(user: User) -> set:
    """Get all permissions for a user based on their role"""
    return ROLE_PERMISSIONS.get(user.role, set())


def has_permission(user: User, permission: Permission) -> bool:
    """Check if user has a specific permission"""
    user_perms = get_user_permissions(user)
    return permission in user_perms


def has_permission_dict(user_info: dict, permission: Permission) -> bool:
    """Check if user (from cookie auth dict) has a specific permission"""
    user_perms = ROLE_PERMISSIONS.get(user_info.get("role", ""), set())
    return permission in user_perms


async def check_permission(
    permission: Permission,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to check if user has specific permission.
    
    Usage:
        @app.get("/admin/users")
        async def get_users(user: User = Depends(check_permission(Permission.MANAGE_ALL_USERS))):
            ...
    """
    if not has_permission(current_user, permission):
        logger.warning(
            f"Permission denied for user {current_user.username}: {permission}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission}"
        )
    return current_user


async def check_role(
    required_roles: List[UserRole],
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to check if user has one of the required roles.
    
    Usage:
        @app.get("/admin/dashboard")
        async def admin_dashboard(user: User = Depends(check_role([UserRole.ADMIN, UserRole.SUPERADMIN]))):
            ...
    """
    user_role = UserRole(current_user.role)
    if user_role not in required_roles:
        logger.warning(
            f"Role denied for user {current_user.username}: required {required_roles}, got {user_role}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This endpoint requires roles: {[r.value for r in required_roles]}"
        )
    return current_user


def require_permission(permission: Permission):
    """
    Decorator for checking permission on an endpoint.
    
    Usage:
        @app.get("/admin/users")
        @require_permission(Permission.MANAGE_ALL_USERS)
        async def get_users(current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: User = None, **kwargs):
            if current_user is None:
                raise HTTPException(status_code=401, detail="Not authenticated")
            if not has_permission(current_user, permission):
                logger.warning(
                    f"Permission denied for user {current_user.username}: {permission}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


def require_role(required_roles: List[UserRole]):
    """
    Decorator for checking role on an endpoint.
    
    Usage:
        @app.get("/admin/dashboard")
        @require_role([UserRole.ADMIN, UserRole.SUPERADMIN])
        async def admin_dashboard(current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: User = None, **kwargs):
            if current_user is None:
                raise HTTPException(status_code=401, detail="Not authenticated")
            user_role = UserRole(current_user.role)
            if user_role not in required_roles:
                logger.warning(
                    f"Role denied for user {current_user.username}: required {required_roles}, got {user_role}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This endpoint requires roles: {[r.value for r in required_roles]}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


async def assert_user_in_org(
    user: User,
    org_id: int,
    db: Session = Depends(get_db)
) -> bool:
    """
    Check if user belongs to organization.
    Used for Admin-level checks.
    """
    if user.role == UserRole.SUPERADMIN.value:
        return True  # Superadmin can access any org
    
    if user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this organization"
        )
    return True


# Role Descriptions (for documentation/UI)
ROLE_DESCRIPTIONS = {
    UserRole.SUPERADMIN.value: {
        "name": "Superadmin",
        "description": "Full system access. Can manage everything.",
        "capabilities": [
            "Manage all users across all organizations",
            "Manage all mailboxes",
            "View all reports and analytics",
            "Access system health and metrics",
            "Manage global settings and configurations",
            "Access complete audit logs",
        ]
    },
    UserRole.ADMIN.value: {
        "name": "Admin",
        "description": "Organization-level management.",
        "capabilities": [
            "Manage users within their organization",
            "Manage mailboxes within their organization",
            "Review and manage quarantined emails",
            "Release or delete suspicious emails",
            "View organization security reports",
            "Access organization audit logs",
            "Create and manage API keys",
        ]
    },
    UserRole.USER.value: {
        "name": "User",
        "description": "Personal mailbox and email access.",
        "capabilities": [
            "Access personal mailbox",
            "Send and receive emails",
            "Report suspicious emails",
            "View personal quarantine and email status",
            "Edit own profile",
            "View personal activity reports",
        ]
    },
}

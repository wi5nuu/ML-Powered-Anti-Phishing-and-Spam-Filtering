"""
Admin management endpoints for RBAC system.
Handles user and mailbox management for different roles.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from database.models import User, AdminMailbox, Organization, UserRole, AuditLog
from dashboard.database import get_db
from dashboard.auth import get_current_user, hash_password, log_audit
from dashboard.rbac import (
    check_permission,
    check_role,
    assert_user_in_org,
    Permission,
    get_user_permissions,
    ROLE_DESCRIPTIONS,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ==================== Pydantic Models ====================

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str  # "superadmin", "admin", "user"
    organization_id: Optional[int] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    organization_id: Optional[int]

    class Config:
        from_attributes = True


class AdminMailboxCreate(BaseModel):
    name: str
    email: str
    organization_id: Optional[int] = None
    config: Optional[dict] = None


class AdminMailboxResponse(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    organization_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class RoleInfo(BaseModel):
    role: str
    name: str
    description: str
    capabilities: List[str]
    permissions: List[str]


class UserPermissionsResponse(BaseModel):
    username: str
    role: str
    permissions: List[str]


# ==================== User Management Endpoints ====================
# NOTE: All /users routes (GET, POST, PUT, DELETE) are intentionally handled
# in app.py using cookie-based authentication (get_authenticated_api_user).
# The routes that were here used OAuth2 Bearer token auth (Depends(get_current_user))
# which conflicts with the frontend's cookie-based session and caused 401 errors.
# Do NOT re-add them here.


# ==================== Mailbox Management Endpoints ====================
# NOTE: GET /mailboxes and POST /mailboxes routes are intentionally handled
# in app.py using cookie-based authentication (get_authenticated_api_user).
# The routes here used OAuth2 Bearer token auth which conflicted with the
# frontend's cookie-based session. Do NOT re-add them here.


# ==================== Role Information ====================

@router.get("/roles", response_model=List[RoleInfo])
async def get_roles(
    current_user: User = Depends(get_current_user),
):
    """
    Get information about all roles and their capabilities.
    """
    roles = []
    for role_name, role_desc in ROLE_DESCRIPTIONS.items():
        permissions = [p.value for p in get_user_permissions(
            type('User', (), {'role': role_name})()
        )]
        roles.append(RoleInfo(
            role=role_name,
            name=role_desc["name"],
            description=role_desc["description"],
            capabilities=role_desc["capabilities"],
            permissions=permissions,
        ))
    return roles


@router.get("/roles/{role_name}", response_model=RoleInfo)
async def get_role_info(
    role_name: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific role.
    """
    if role_name not in ROLE_DESCRIPTIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Role '{role_name}' not found"
        )
    
    role_desc = ROLE_DESCRIPTIONS[role_name]
    permissions = [p.value for p in get_user_permissions(
        type('User', (), {'role': role_name})()
    )]
    
    return RoleInfo(
        role=role_name,
        name=role_desc["name"],
        description=role_desc["description"],
        capabilities=role_desc["capabilities"],
        permissions=permissions,
    )

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

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List users. Superadmin sees all users, Admin sees organization users.
    """
    if current_user.role == UserRole.SUPERADMIN.value:
        # Superadmin sees all users
        users = db.query(User).offset(skip).limit(limit).all()
    elif current_user.role == UserRole.ADMIN.value:
        # Admin sees only users in their organization
        users = db.query(User).filter(
            User.organization_id == current_user.organization_id
        ).offset(skip).limit(limit).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin and admin can list users"
        )
    
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get user details. User can only see their own profile.
    Admin/Superadmin can see organization/all users respectively.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Permission checks
    if current_user.id == user_id:
        # Users can always see their own profile
        return user
    elif current_user.role == UserRole.SUPERADMIN.value:
        # Superadmin can see anyone
        return user
    elif current_user.role == UserRole.ADMIN.value:
        # Admin can see users in their org
        if user.organization_id == current_user.organization_id:
            return user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permission denied"
    )


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create new user. Only Superadmin can create superadmin/admin.
    Admin can create users within their organization.
    """
    # Permission check
    if current_user.role == UserRole.SUPERADMIN.value:
        # Superadmin can create any role
        can_create = True
    elif current_user.role == UserRole.ADMIN.value:
        # Admin can only create users (not admin/superadmin)
        can_create = user_data.role == UserRole.USER.value
    else:
        can_create = False
    
    if not can_create:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied to create this role"
        )
    
    # Check if username already exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Set organization_id
    if user_data.role == UserRole.SUPERADMIN.value:
        org_id = None  # Superadmin not bound to org
    elif user_data.role == UserRole.ADMIN.value:
        org_id = user_data.organization_id
    else:  # USER
        org_id = user_data.organization_id or current_user.organization_id
    
    # Create user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        organization_id=org_id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Log audit
    log_audit(
        db=db,
        user=current_user.username,
        action="USER_CREATED",
        details=f"Created user {new_user.username} with role {new_user.role}"
    )
    
    return new_user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update user. User can only update their own profile.
    Admin/Superadmin can update org/all users respectively.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Permission checks for role change
    if user_data.role and user_data.role != user.role:
        # Role change requires higher permission
        if current_user.role == UserRole.SUPERADMIN.value:
            # Superadmin can change any role
            pass
        elif current_user.role == UserRole.ADMIN.value and current_user.id == user_id:
            # Admin cannot change their own role
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change your own role"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied to change role"
            )
    
    # Standard permission check
    if current_user.id != user_id and current_user.role != UserRole.SUPERADMIN.value:
        if current_user.role != UserRole.ADMIN.value or user.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
    
    # Update fields
    if user_data.email:
        user.email = user_data.email
    if user_data.role:
        user.role = user_data.role
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    db.commit()
    db.refresh(user)
    
    # Log audit
    log_audit(
        db=db,
        user=current_user.username,
        action="USER_UPDATED",
        details=f"Updated user {user.username}"
    )
    
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete/deactivate user. Only Superadmin can delete users.
    """
    if current_user.role != UserRole.SUPERADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin can delete users"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Soft delete (deactivate)
    user.is_active = False
    db.commit()
    
    # Log audit
    log_audit(
        db=db,
        user=current_user.username,
        action="USER_DELETED",
        details=f"Deleted user {user.username}"
    )
    
    return {"message": "User deleted"}


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
async def get_user_permissions_endpoint(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get user's permissions. User can only see their own permissions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user.id != user_id and current_user.role != UserRole.SUPERADMIN.value:
        if current_user.role != UserRole.ADMIN.value or user.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
    
    permissions = get_user_permissions(user)
    return {
        "username": user.username,
        "role": user.role,
        "permissions": [p.value for p in permissions],
    }


# ==================== Mailbox Management Endpoints ====================

@router.get("/mailboxes", response_model=List[AdminMailboxResponse])
async def list_mailboxes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List mailboxes. Superadmin sees all, Admin sees organization mailboxes.
    """
    if current_user.role == UserRole.SUPERADMIN.value:
        mailboxes = db.query(AdminMailbox).offset(skip).limit(limit).all()
    elif current_user.role == UserRole.ADMIN.value:
        mailboxes = db.query(AdminMailbox).filter(
            AdminMailbox.organization_id == current_user.organization_id
        ).offset(skip).limit(limit).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin and admin can list mailboxes"
        )
    
    return mailboxes


@router.post("/mailboxes", response_model=AdminMailboxResponse)
async def create_mailbox(
    mailbox_data: AdminMailboxCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create new mailbox. Only Superadmin/Admin can create mailboxes.
    """
    if current_user.role not in [UserRole.SUPERADMIN.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )
    
    # For Admin: set their organization
    org_id = mailbox_data.organization_id
    if current_user.role == UserRole.ADMIN.value:
        org_id = current_user.organization_id
    
    new_mailbox = AdminMailbox(
        name=mailbox_data.name,
        email=mailbox_data.email,
        organization_id=org_id,
        config=mailbox_data.config or {},
        is_active=True,
    )
    db.add(new_mailbox)
    db.commit()
    db.refresh(new_mailbox)
    
    # Log audit
    log_audit(
        db=db,
        user=current_user.username,
        action="MAILBOX_CREATED",
        details=f"Created mailbox {new_mailbox.email}"
    )
    
    return new_mailbox


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

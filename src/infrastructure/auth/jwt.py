"""
JWT authentication module for CogniMail — Enterprise Edition.

Provides:
- Password hashing and verification (bcrypt)
- JWT token creation and decoding
- Current user extraction from token
- API key verification
- Role-based access control helpers
"""
import os
import secrets
import logging
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from src.config.settings import settings
from src.infrastructure.database.session import get_db
from src.domain.entities import User, ApiKey
from src.domain.enums import UserRole

logger = logging.getLogger(__name__)

# ── Security Configuration ───────────────────────────────────────────────

SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("CRITICAL: DASHBOARD_SECRET_KEY must be set in production environment")
    logger.warning(
        "⚠  DASHBOARD_SECRET_KEY not set! Using random key (tokens will be invalidated on restart). "
        "Set DASHBOARD_SECRET_KEY in .env file."
    )
    SECRET_KEY = secrets.token_hex(32)

ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain text password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)



def create_access_token(data: dict) -> str:
    """Create a JWT access token with expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises 401 on invalid/expired token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning("Token decode failed: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from a JWT token.
    
    Returns the User object or raises 401.
    """
    try:
        payload = decode_token(token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    username = payload.get("sub")
    if username is None:
        logger.warning("Token missing 'sub' claim")
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.warning("User from token not found: %s", username)
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.is_active:
        logger.warning("Inactive user attempted access: %s", username)
        raise HTTPException(status_code=401, detail="User account is disabled")

    return user


def require_role(required_roles: list[str]):
    """
    Dependency factory: require the current user to have one of specified roles.
    
    Usage:
        @router.get("/admin/users")
        def list_users(current_user: User = Depends(require_role(["superadmin", "admin"]))):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles:
            logger.warning(
                "Access denied for %s (role=%s): required=%s",
                current_user.username, current_user.role, required_roles
            )
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {', '.join(required_roles)}"
            )
        return current_user
    return role_checker


def verify_api_key(key: str, db: Session) -> ApiKey:
    """Verify an API key against stored hashes."""
    if not key:
        raise HTTPException(status_code=401, detail="API key is required")
    import hashlib
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    ).first()
    if not api_key:
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

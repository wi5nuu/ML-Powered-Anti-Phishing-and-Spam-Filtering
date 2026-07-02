"""
Authentication & Authorization module — JWT-based with RBAC.
"""

import os
import logging
import secrets
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from datetime import datetime, timedelta

# Workaround for bcrypt >= 4.1.0 compatibility with passlib in Python 3.13
import bcrypt
if not hasattr(bcrypt, "__about__"):
    class About:
        __version__ = getattr(bcrypt, "__version__", "4.0.0")
    bcrypt.__about__ = About()

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session

from database.models import User, UserRole, AuditLog, ApiKey
from dashboard.database import get_db

logger = logging.getLogger(__name__)

_sk = os.getenv("DASHBOARD_SECRET_KEY")
if not _sk:
    _sk = secrets.token_hex(32)
    logger.warning("=" * 60)
    logger.warning("DASHBOARD_SECRET_KEY tidak disetel! Menggunakan kunci sementara.")
    logger.warning("Set DASHBOARD_SECRET_KEY di .env agar sesi tetap valid")
    logger.warning("setelah server restart. Contoh: DASHBOARD_SECRET_KEY=my-secure-key-123")
    logger.warning("=" * 60)
SECRET_KEY = _sk
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_role(role: UserRole):
    def checker(user: User = None):
        if user.role not in (role.value, UserRole.SUPERADMIN.value):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def verify_api_key(key: str, db: Session) -> ApiKey:
    if not key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    import hashlib
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    ).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def log_audit(db: Session, user: str, action: str, email_id: str = None,
              ip_address: str = None, details: str = ""):
    entry = AuditLog(
        user=user,
        action=action,
        email_id=email_id,
        ip_address=ip_address,
        details=details,
    )
    db.add(entry)
    db.commit()

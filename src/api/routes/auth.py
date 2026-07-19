from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from src.infrastructure.database.session import get_db
from src.infrastructure.auth.jwt import hash_password, verify_password, create_access_token, decode_token, get_current_user
from src.domain.entities import User, AuditLog, ApiKey

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    token = create_access_token({"sub": user.username, "role": user.role})
    audit = AuditLog(user=user.username, action="login", details="Dashboard login")
    db.add(audit)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": {"username": user.username, "role": user.role}}


@router.post("/logout")
def logout():
    return {"ok": True}


@router.get("/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token", "")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        return {"authenticated": False}
    try:
        payload = decode_token(token)
        user = db.query(User).filter(User.username == payload.get("sub")).first()
        if not user or not user.is_active:
            return {"authenticated": False}
        return {"authenticated": True, "user": {"username": user.username, "role": user.role, "email": user.email or ""}}
    except Exception:
        return {"authenticated": False}


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email or "", "role": current_user.role}


@router.post("/change-password")
def change_password(data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.get("current_password", ""), current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(data["new_password"])
    db.commit()
    return {"ok": True}


@router.get("/api-keys")
def list_api_keys(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = db.query(ApiKey).filter(ApiKey.organization_id == current_user.organization_id).all()
    return [{"id": k.id, "name": k.name, "is_active": k.is_active, "created_at": str(k.created_at)} for k in keys]


@router.post("/api-keys")
def create_api_key(data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import secrets, hashlib
    raw = secrets.token_hex(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key = ApiKey(name=data.get("name", "default"), key_hash=key_hash, organization_id=current_user.organization_id)
    db.add(key)
    db.commit()
    return {"id": key.id, "name": key.name, "key": raw, "message": "Save this key - it won't be shown again"}


@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    # Authorization check: user can only delete their own API keys (or superadmin can delete any)
    if key.organization_id != current_user.organization_id and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this API key")
    db.delete(key)
    db.commit()
    return {"ok": True}


@router.get("/activity")
def get_activity(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).filter(AuditLog.user == current_user.username).order_by(AuditLog.created_at.desc()).limit(20).all()
    return [{"action": l.action, "details": l.details, "created_at": str(l.created_at)} for l in logs]

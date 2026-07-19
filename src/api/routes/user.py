from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.infrastructure.database.session import get_db
from src.infrastructure.auth.jwt import get_current_user
from src.domain.entities import User

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/dashboard")
def user_dashboard(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role}


@router.get("/mailbox")
def user_mailbox(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email or ""}


@router.get("/settings")
def user_settings(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email or ""}


@router.put("/settings")
def update_user_settings(data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if "email" in data:
        current_user.email = data["email"]
    db.commit()
    return {"ok": True}

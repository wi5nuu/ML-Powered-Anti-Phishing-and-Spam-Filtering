from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from src.infrastructure.database.session import get_db
from src.infrastructure.auth.jwt import verify_password, create_access_token, hash_password
from src.domain.entities import AdminMailbox

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])


@router.post("/login")
def mailbox_login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "")
    password = data.get("password", "")
    box = db.query(AdminMailbox).filter(AdminMailbox.email == email, AdminMailbox.is_active == True).first()
    if not box or not verify_password(password, box.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": email, "role": "mailbox", "mailbox_id": str(box.id)})
    return {"access_token": token, "token_type": "bearer", "mailbox": {"id": box.id, "email": box.email}}


@router.post("/logout")
def mailbox_logout():
    return {"ok": True}

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from src.config.settings import settings

SESSION_COOKIE_NAME = "access_token"


def get_token_from_request(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


def get_user_from_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


async def cookie_or_bearer_auth(request: Request, call_next):
    if request.url.path.startswith(("/api/", "/ws")):
        token = get_token_from_request(request)
        if token:
            user = get_user_from_token(token)
            if user:
                request.state.user = user
    response = await call_next(request)
    return response

"""
CogniMail API — Enterprise ML-Powered Anti-Phishing & Spam Filtering
Clean Architecture entry point.
"""
import os
import sys
from pathlib import Path

# Ensure the project root is in sys.path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.config.settings import settings
from src.config.logging import configure_logging
from src.infrastructure.database.session import engine, Base
from src.infrastructure.monitoring.prometheus import instrumentator
from src.api.middleware.security import security_headers
from src.api.routes import auth_router, email_router, admin_router, superadmin_router, user_router, metrics_router, mailbox_router, settings_router, websocket_router

configure_logging()

Base.metadata.create_all(bind=engine)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(security_headers)

app.include_router(auth_router)
app.include_router(email_router)
app.include_router(admin_router)
app.include_router(superadmin_router)
app.include_router(user_router)
app.include_router(metrics_router)
app.include_router(mailbox_router)
app.include_router(settings_router)
app.include_router(websocket_router)

instrumentator.instrument(app).expose(app)

STATIC_DIR = settings.STATIC_DIR
DIST_DIR = settings.DIST_DIR

if DIST_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = DIST_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"detail": "Not Found"}, status_code=404)
else:
    @app.get("/")
    async def root():
        return {"status": "running", "service": settings.APP_NAME, "version": settings.VERSION}


@app.on_event("startup")
async def startup():
    from src.infrastructure.database.seed import seed_initial_data
    seed_initial_data()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)

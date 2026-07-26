"""
Local dev launcher — sets PYTHONPATH so 'database.models' resolves correctly,
then starts uvicorn programmatically (no subprocess needed).

Requires PostgreSQL running via Docker:
    docker compose up postgres redis -d

Env vars diambil dari .env di project root.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path so 'database.models' resolves to
# <root>/database/models.py instead of being shadowed by dashboard/database.py
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load .env dari project root
load_dotenv(project_root / ".env")

# Pastikan DASHBOARD_DB_URL pakai PostgreSQL (dari WORKER_DB_URL jika perlu)
if not os.getenv("DASHBOARD_DB_URL") and not os.getenv("DB_SYNC_URL"):
    worker_url = os.getenv("WORKER_DB_URL", "")
    if worker_url:
        sync_url = worker_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        os.environ["DASHBOARD_DB_URL"] = sync_url

os.environ.setdefault("ENV", "development")

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("DASHBOARD_PORT", "8081")),
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )

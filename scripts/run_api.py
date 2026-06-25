"""
Start LTI Anti-Phishing API Server.
Gunakan port 8006 untuk menghindari konflik.
"""

import sys
import os
from pathlib import Path

# Set PYTHONPATH
root = Path(__file__).resolve().parent.parent
os.environ["PYTHONPATH"] = str(root)
os.chdir(str(root))

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  LTI ANTI-PHISHING CLASSIFIER API")
    print("=" * 60)
    print(f"  Port : 8006")
    print(f"  Root : {root}")
    print(f"  Warmup akan memakan waktu ~10-20 detik...")
    print(f"  {'-' * 50}")
    print(f"  Server siap di: http://localhost:8006")
    print(f"  Health check : http://localhost:8006/health")
    print(f"  Test email   : python scripts/test_email.py")
    print(f"{'=' * 60}\n")

    uvicorn.run(
        "classifier.predict:app",
        host="0.0.0.0",
        port=8006,
        log_level="info",
        workers=2,
    )

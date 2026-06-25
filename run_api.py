"""
START API SERVER
================
Jalankan di terminal PowerShell/CMD sendiri.
Tunggu sampai muncul "Application startup complete".
"""

import sys, os
from pathlib import Path

root = Path(__file__).resolve().parent.parent
os.chdir(str(root))
os.environ["PYTHONPATH"] = str(root)
sys.path.insert(0, str(root))

import uvicorn

print("=" * 60)
print("  LTI ANTI-PHISHING CLASSIFIER API")
print("=" * 60)
print(f"  Port  : 8006")
print(f"  URL   : http://localhost:8006")
print(f"  Health: http://localhost:8006/health")
print(f"\n  Loading model + warmup... (10-20 detik)")
print(f"  {'=' * 50}")
print(f"  SETELAH INI, BUKA TERMINAL KEDUA dan jalankan:")
print(f"  python scripts/test_email.py")
print(f"{'=' * 60}\n")

uvicorn.run(
    "classifier.predict:app",
    host="0.0.0.0",
    port=8006,
    log_level="info",
)

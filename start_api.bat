@echo off
cd /d "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
set PYTHONPATH=%CD%
echo ============================================================
echo   LTI ANTI-PHISHING CLASSIFIER API
echo ============================================================
echo.
echo  Loading model... (20-30 detik)
echo.
echo  Setelah muncul "Application startup complete",
echo  buka terminal KEDUA dan jalankan:
echo    python scripts/test_email.py
echo.
python -m uvicorn classifier.predict:app --host 0.0.0.0 --port 8006 --log-level info
pause

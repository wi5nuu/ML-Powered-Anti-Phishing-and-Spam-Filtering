@echo off
cd /d "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
set PYTHONPATH=%CD%
echo ============================================================
echo   LTI ANTI-PHISHING SYSTEM - LIVE DEMO
echo   Dual-Layer ML (XGBoost + Anomaly) + SHAP XAI
echo ============================================================
echo.
echo  Memuat model + warmup... (20-30 detik)
echo.
python demo.py
pause

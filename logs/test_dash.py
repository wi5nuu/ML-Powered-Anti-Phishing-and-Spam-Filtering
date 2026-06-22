import sys, os
sys.path.insert(0, r"D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing")
os.chdir(r"D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing")
import uvicorn
uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8002, log_level="debug")

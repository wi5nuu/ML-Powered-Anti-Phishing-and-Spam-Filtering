Set WshShell = CreateObject("WScript.Shell")
Set env = WshShell.Environment("PROCESS")
env("PYTHONPATH") = "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
WshShell.CurrentDirectory = "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
cmd = "cmd /c ""python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8081 --log-level info > logs\dashboard.log 2>&1"""
WshShell.Run cmd, 0, False

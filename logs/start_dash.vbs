Set WshShell = CreateObject("WScript.Shell")
Set env = WshShell.Environment("PROCESS")
env("PYTHONPATH") = "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
WshShell.CurrentDirectory = "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
WshShell.Run "python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8001 --log-level info", 0, False

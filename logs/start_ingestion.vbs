Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
WshShell.Run "cmd /c python scripts\run_ingestion.py >> logs\ingestion.log 2>&1", 0, False

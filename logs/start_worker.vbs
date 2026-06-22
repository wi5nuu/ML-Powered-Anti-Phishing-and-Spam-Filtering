Set WshShell = CreateObject("WScript.Shell")
Set env = WshShell.Environment("PROCESS")
env("PYTHONPATH") = "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
WshShell.CurrentDirectory = "D:\ML-Powered Anti-Phishing and Spam Filtering\lti-antiphishing"
WshShell.Run "python -m worker.pipeline_worker", 0, False

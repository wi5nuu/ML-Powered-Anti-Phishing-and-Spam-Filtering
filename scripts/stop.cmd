@echo off
setlocal

set PROFILE=%1
if "%PROFILE%"=="" set PROFILE=local

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" -Profile "%PROFILE%"
exit /b %ERRORLEVEL%

@echo off
setlocal

set PROFILE=%1
set BUILD_ARG=

if "%PROFILE%"=="" set PROFILE=local
if /I "%2"=="build" set BUILD_ARG=-Build
if /I "%2"=="--build" set BUILD_ARG=-Build

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -Profile "%PROFILE%" %BUILD_ARG%
exit /b %ERRORLEVEL%

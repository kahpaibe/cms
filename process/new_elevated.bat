@echo off
REM This script runs only the linking commands and must be run as administrator
setlocal
set "NEWFOLDER=%1"

REM Check for admin rights, relaunch as admin if needed
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -ArgumentList '%NEWFOLDER%' -Verb RunAs"
    exit /b
)

REM Link content
mklink /H "%~dp0%NEWFOLDER%\cms_lib.py" "%~dp0..\cms_lib.py"
mklink /H "%~dp0%NEWFOLDER%\cms_skip.py" "%~dp0..\cms_skip.py"
mklink /J "%~dp0%NEWFOLDER%\kahscrape" "%~dp0..\kahscrape"

endlocal

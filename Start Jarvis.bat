@echo off
title Jarvis
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Jarvis isn't installed yet - running install.bat first...
    call install.bat
)
".venv\Scripts\python.exe" jarvis.py %*
pause

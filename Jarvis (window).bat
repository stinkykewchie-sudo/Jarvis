@echo off
rem Opens the Jarvis window (no terminal). Double-click this, or use the Desktop/Start-menu shortcut.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Jarvis isn't installed yet - running install.bat first...
    call install.bat
)
start "" ".venv\Scripts\pythonw.exe" gui.py %*

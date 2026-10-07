@echo off
rem Sets up Jarvis on Windows: a virtual environment, the Python packages, and Desktop/Start menu shortcuts.
cd /d "%~dp0"

where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (
    echo Python 3.10 or newer is required. Get it from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Creating virtual environment...
%PY% -m venv .venv || (pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)

echo.
echo Creating Desktop and Start menu shortcuts...
choice /c YN /m "Start Jarvis automatically when you log in"
if errorlevel 2 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0shortcuts.ps1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0shortcuts.ps1" -Startup
)

echo.
echo Done! Start Jarvis from the Jarvis icon on your Desktop or in the Start menu.
echo Optional: install Ollama from https://ollama.com, then run these so Jarvis can chat and code:
echo     ollama pull qwen3:1.7b
echo     ollama pull qwen2.5-coder:3b
pause

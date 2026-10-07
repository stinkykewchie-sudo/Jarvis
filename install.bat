@echo off
rem Sets up Jarvis on Windows: creates a virtual environment and installs the Python packages.
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
echo Done! Double-click "Start Jarvis.bat" to run Jarvis.
echo Optional: install Ollama from https://ollama.com and run "ollama pull qwen3:1.7b" so Jarvis can chat.
pause

@echo off
rem Removes Jarvis from this PC: shortcuts, autostart, the virtual environment and downloaded models.
cd /d "%~dp0"

echo This will remove Jarvis's shortcuts, autostart, virtual environment and downloaded models.
choice /c YN /m "Continue"
if errorlevel 2 ( echo Cancelled. & pause & exit /b )

echo Removing shortcuts and autostart...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0shortcuts.ps1" -Remove

set "OLLAMA=ollama"
where ollama >nul 2>nul || set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%OLLAMA%" (
    choice /c YN /m "Also remove the Ollama models (qwen3:1.7b and qwen2.5-coder:3b)"
    if not errorlevel 2 (
        "%OLLAMA%" rm qwen3:1.7b
        "%OLLAMA%" rm qwen2.5-coder:3b
    )
)

echo Removing the virtual environment and downloaded models...
rmdir /s /q ".venv"  2>nul
rmdir /s /q "models" 2>nul
rmdir /s /q "voices" 2>nul
rmdir /s /q "ollama-models" 2>nul
del /q "jarvis.log" "jarvis.log.1" "jarvis_memory.json" 2>nul

echo.
echo Done. To finish, delete this folder:
echo    "%~dp0"
echo Your code is kept in: "%USERPROFILE%\Jarvis Projects"
echo Ollama itself is left installed - remove it from Settings ^> Apps if you want it gone.
pause

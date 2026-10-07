@echo off
rem Opens Jarvis. With no arguments it opens the WINDOW (GUI). Flags give the terminal versions:
rem   Start Jarvis.bat              -> window (GUI)
rem   Start Jarvis.bat --terminal   -> voice, in a terminal
rem   Start Jarvis.bat --type       -> typed, in a terminal
rem   Start Jarvis.bat --no-wake    -> voice without the wake word, in a terminal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Jarvis isn't installed yet - running install.bat first...
    call install.bat
)

if "%~1"=="" goto gui
if /i "%~1"=="--gui" goto gui
if /i "%~1"=="--terminal" (
    ".venv\Scripts\python.exe" jarvis.py
    goto done
)
".venv\Scripts\python.exe" jarvis.py %*
:done
pause
exit /b

:gui
start "" ".venv\Scripts\pythonw.exe" gui.py

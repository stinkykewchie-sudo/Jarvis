#!/usr/bin/env bash
# Opens the Jarvis window on Linux. Pass --tray to start hidden in the system tray.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    echo "Jarvis isn't installed yet - running install.sh first..."
    bash install.sh
fi
exec .venv/bin/python gui.py "$@"

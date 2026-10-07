#!/usr/bin/env bash
# Starts Jarvis on Linux.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    echo "Jarvis isn't installed yet - running install.sh first..."
    bash install.sh
fi
exec .venv/bin/python jarvis.py "$@"

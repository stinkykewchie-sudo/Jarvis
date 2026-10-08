#!/usr/bin/env bash
# EXPERIMENTAL - build a single-file Jarvis.AppImage for Linux (x86_64).
#
# An AppImage bundles Python and Jarvis's Python packages so it runs on most Linux machines without
# installing anything. It does NOT bundle Ollama, PortAudio or the speech models - see the notes at the end.
# This must be run ON a Linux machine (ideally an older one, for the widest compatibility). It cannot be
# built or tested from Windows, so treat it as a starting point and expect to iterate.
#
# Usage:   ./build-appimage.sh
set -e
cd "$(dirname "$0")"
here="$(pwd)"
work="$here/build-appimage.tmp"
python="python3.12"   # the Python the AppImage ships with

command -v "$python" >/dev/null || { echo "Need $python installed to build. Try: sudo apt install $python $python-venv"; exit 1; }

echo "1/5  Preparing a clean build dir..."
rm -rf "$work"; mkdir -p "$work"
cd "$work"

echo "2/5  Downloading the base Python AppImage tooling (python-appimage)..."
"$python" -m pip install --quiet --target ./tools python-appimage

echo "3/5  Collecting Jarvis and its Python dependencies..."
mkdir -p app
cp "$here"/*.py app/
# the entry point the AppImage runs
cat > app/entrypoint.py <<'PY'
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import gui
gui.main()
PY
cp "$here/requirements.txt" app/

echo "4/5  Building the AppImage (this bundles CPython + pip packages)..."
# python-appimage builds an AppImage around a requirements.txt and an entrypoint
PYTHONPATH=./tools "$python" -m python_appimage build app \
    --name Jarvis \
    --python-version 3.12 \
    --requirements app/requirements.txt \
    --entrypoint app/entrypoint.py || {
        echo
        echo "The python-appimage invocation above may differ by version - check 'python -m python_appimage --help'."
        echo "The pieces you need: ship Python 3.12, install requirements.txt, run gui.main() as the entrypoint."
        exit 1
    }

mv ./*.AppImage "$here/Jarvis-x86_64.AppImage" 2>/dev/null || true
chmod +x "$here/Jarvis-x86_64.AppImage" 2>/dev/null || true
cd "$here"; rm -rf "$work"

cat <<'NOTES'

5/5  Done (if the build step succeeded). Jarvis-x86_64.AppImage is in this folder.

Important, because an AppImage can't bundle everything:

  * System audio library: PortAudio (libportaudio2) must be present on the host for the microphone.
    Most desktops have it; if not, `sudo apt install libportaudio2`. (Tk is bundled with the Python.)

  * Ollama (for chat and coding) is a separate program - the AppImage does not contain it. Either install
    it on the host (https://ollama.com), or carry its binary and turn on portable mode (see make-portable.py
    and the README "Portable / USB" section) so Jarvis runs its own server from a folder next to the AppImage.

  * The speech model and voice download on first run into ~/.cache or next to the AppImage.

For a truly no-install USB, pair this AppImage with a portable Ollama folder on the same stick.
NOTES

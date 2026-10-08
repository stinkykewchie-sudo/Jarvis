#!/usr/bin/env bash
# Build a single-file Jarvis.AppImage for Linux (x86_64). RUN THIS ON A LINUX MACHINE.
#
# How it works: it downloads a portable Python (as an AppImage from the python-appimage project),
# unpacks it into an AppDir, installs Jarvis's Python packages into that Python, copies Jarvis's code
# in, adds a launcher + icon, and repackages the whole thing with appimagetool.
#
# What it does NOT contain (and why): Ollama (a separate program - install it on the host, or use
# portable mode), and PortAudio (the microphone library, loaded from the host at runtime). The speech
# model and voice download on first run. See the notes printed at the end.
#
# Needs: a Linux x86_64 machine with curl and tar. No root needed. FUSE is not required
# (we use APPIMAGE_EXTRACT_AND_RUN). If anything fails, send me the output and I'll fix it.
set -euo pipefail
cd "$(dirname "$0")"
here="$(pwd)"
PYMM="3.12"            # bundled Python major.minor
PYTAG="cp312"
work="$here/build-appimage.tmp"
appdir="$work/Jarvis.AppDir"
export APPIMAGE_EXTRACT_AND_RUN=1   # let AppImages run without FUSE

echo "1/6  Clean build dir..."
rm -rf "$work"; mkdir -p "$work"; cd "$work"

echo "2/6  Finding a portable Python $PYMM AppImage..."
api="https://api.github.com/repos/niess/python-appimage/releases/tags/python${PYMM}"
pyurl="$(curl -fsSL "$api" \
  | grep -oE "https://[^\"]*${PYTAG}-${PYTAG}-manylinux2014_x86_64\.AppImage" | head -1)"
[ -n "$pyurl" ] || { echo "Couldn't find a Python $PYMM AppImage URL. Check: $api"; exit 1; }
echo "     $pyurl"
curl -fsSL -o python.AppImage "$pyurl"
chmod +x python.AppImage

echo "3/6  Unpacking it into the AppDir..."
./python.AppImage --appimage-extract >/dev/null
mv squashfs-root "$appdir"
# find the real python binary (the folder may be opt/python3.12 or a patch-versioned one)
py="$(find "$appdir/opt" -maxdepth 2 -type f -name 'python3.[0-9]*' 2>/dev/null \
      | grep -E '/python3\.[0-9]+$' | head -1)"
[ -n "$py" ] && [ -x "$py" ] || { echo "Bundled python not found under $appdir/opt"; find "$appdir/opt" -maxdepth 2 -name 'python3*'; exit 1; }
echo "     using $py"

echo "4/6  Installing Jarvis's Python packages into the bundle (this is the slow part)..."
"$py" -m pip install --no-warn-script-location -r "$here/requirements.txt"

echo "5/6  Adding Jarvis's code, launcher and icon..."
mkdir -p "$appdir/opt/jarvis"
cp "$here"/*.py "$appdir/opt/jarvis/"
[ -f "$here/jarvis.png" ] || "$py" "$here/make_icon.py" || true
cp "$here/jarvis.png" "$appdir/jarvis.png" 2>/dev/null || true
cp "$here/jarvis.png" "$appdir/opt/jarvis/jarvis.png" 2>/dev/null || true

# AppRun finds the bundled python at runtime and sets its environment, so it doesn't depend on the exact
# folder/version name inside the base image.
cat > "$appdir/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="$HERE"
PYBIN=""
for c in "$HERE"/opt/python*/bin/python3.[0-9][0-9] "$HERE"/opt/python*/bin/python3.[0-9] "$HERE"/opt/python*/bin/python3; do
    [ -x "$c" ] && PYBIN="$c" && break
done
if [ -z "$PYBIN" ]; then echo "Jarvis: bundled Python not found in the AppImage" >&2; exit 1; fi
PYROOT="$(dirname "$(dirname "$PYBIN")")"
export PYTHONHOME="$PYROOT"
export LD_LIBRARY_PATH="$PYROOT/lib:$HERE/usr/lib:$LD_LIBRARY_PATH"
export PATH="$PYROOT/bin:$PATH"
export PYTHONPATH="$HERE/opt/jarvis:$PYTHONPATH"
exec "$PYBIN" "$HERE/opt/jarvis/gui.py" "$@"
APPRUN
chmod +x "$appdir/AppRun"

cat > "$appdir/jarvis.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=Jarvis
Comment=Offline personal assistant
Exec=AppRun
Icon=jarvis
Categories=Utility;
Terminal=false
DESK

echo "6/6  Packaging with appimagetool..."
tool="$work/appimagetool.AppImage"
curl -fsSL -o "$tool" \
  "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
chmod +x "$tool"
# --no-appstream skips the strict metadata validation (the cid-* errors); not needed for a personal app
ARCH=x86_64 "$tool" --no-appstream "$appdir" "$here/Jarvis-x86_64.AppImage"

cd "$here"; rm -rf "$work"
echo
echo "Done:  $here/Jarvis-x86_64.AppImage"
cat <<'NOTES'

Run it:   ./Jarvis-x86_64.AppImage
(or make it clickable in your file manager: Properties -> Permissions -> Allow executing as program.)

If you get "AppImages require FUSE to run": Ubuntu 22.04+ doesn't ship FUSE 2 by default. Either run it
without FUSE:   ./Jarvis-x86_64.AppImage --appimage-extract-and-run
or install the library once:   sudo apt install libfuse2    (on Ubuntu 24.04: sudo apt install libfuse2t64)

Before it fully works on a given machine:
  * Microphone needs PortAudio on the host:   sudo apt install libportaudio2   (dnf: portaudio, pacman: portaudio)
  * The window needs Tk. The bundled Python usually includes it; if the window won't open, run the AppImage
    from a terminal to see the error and tell me.
  * Chat and coding need Ollama: install it on the host (https://ollama.com) and pull the models, OR carry a
    portable Ollama folder next to the AppImage and turn on portable mode (see make-portable.py / README).

If any step above errors, paste the terminal output and I'll adjust this script.
NOTES

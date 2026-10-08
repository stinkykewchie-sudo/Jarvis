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
rm -rf "$work"; mkdir -p "$work"
rm -f "$here/Jarvis-x86_64.AppImage"   # remove any old build so a stale one can't be mistaken for success
cd "$work"

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
py="$(find "$appdir/opt" -maxdepth 3 -type f -name 'python3.[0-9]*' 2>/dev/null \
      | grep -E '/python3\.[0-9]+$' | head -1)"
[ -n "$py" ] && [ -x "$py" ] || { echo "Bundled python not found under $appdir/opt"; find "$appdir/opt" -maxdepth 2 -name 'python3*'; exit 1; }
echo "     using $py"

echo "4/6  Installing Jarvis's Python packages into the bundle (this is the slow part)..."
"$py" -m pip install --no-warn-script-location -r "$here/requirements.txt"

echo "5/6  Adding Jarvis's code, launcher, icon and audio library..."
mkdir -p "$appdir/opt/jarvis"
cp "$here"/*.py "$appdir/opt/jarvis/"

# Bundle PortAudio (and espeak-ng) so the microphone and voice work without installing anything on the host.
mkdir -p "$appdir/usr/lib"
copied_audio=""
for lib in libportaudio.so.2 libespeak-ng.so.1; do
    src="$(ldconfig -p 2>/dev/null | grep -oE "/[^ ]*${lib//./\\.}" | head -1)"
    if [ -n "$src" ] && [ -e "$src" ]; then
        cp -Lv "$src" "$appdir/usr/lib/" && copied_audio="yes"
    fi
done
if [ -z "$copied_audio" ]; then
    echo "     note: libportaudio wasn't found on this build machine, so voice won't work until the host has it."
    echo "           install it first (sudo apt install libportaudio2 espeak-ng) and re-run for a self-contained build."
fi
# espeak-ng's data (for the fallback voice), if present
espeak_data="$(dirname "$(find /usr -maxdepth 4 -type d -name 'espeak-ng-data' 2>/dev/null | head -1)" 2>/dev/null)"
[ -d "$espeak_data/espeak-ng-data" ] && cp -r "$espeak_data/espeak-ng-data" "$appdir/usr/share/" 2>/dev/null || true
[ -f "$here/jarvis.png" ] || "$py" "$here/make_icon.py" || true
cp "$here/jarvis.png" "$appdir/jarvis.png" 2>/dev/null || true
cp "$here/jarvis.png" "$appdir/opt/jarvis/jarvis.png" 2>/dev/null || true

# AppRun finds the bundled Python and Tcl/Tk at runtime (layout varies by base image), sets up their
# environment, and - crucially for a windowed app with no terminal - shows any startup error in a popup
# and writes it to ~/jarvis-appimage.log, so you can read what went wrong without a console.
# The base image ships AppRun as a symlink into usr/bin, so delete it first - otherwise "cat >" would write
# through the link and our launcher would resolve its own location to the wrong folder.
rm -f "$appdir/AppRun"
cat > "$appdir/AppRun" <<'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="$HERE"
export JARVIS_APPIMAGE=1   # tells Jarvis to keep its data in ~/.local/share/Jarvis, not this temp folder
LOG="$HOME/jarvis-appimage.log"

show_error() {
    local msg="$1"
    if command -v zenity >/dev/null 2>&1; then zenity --error --no-wrap --title="Jarvis" --text="$msg"
    elif command -v kdialog >/dev/null 2>&1; then kdialog --title "Jarvis" --error "$msg"
    elif command -v xmessage >/dev/null 2>&1; then xmessage -center "$msg"
    else printf '%s\n' "$msg" >&2; fi
}

PYBIN=""
for c in "$HERE"/opt/python*/bin/python3.[0-9][0-9] "$HERE"/opt/python*/bin/python3.[0-9] "$HERE"/opt/python*/bin/python3; do
    [ -x "$c" ] && PYBIN="$c" && break
done
if [ -z "$PYBIN" ]; then show_error "Jarvis: the bundled Python was not found in the AppImage."; exit 1; fi

PYROOT="$(dirname "$(dirname "$PYBIN")")"
export PYTHONHOME="$PYROOT"
export LD_LIBRARY_PATH="$PYROOT/lib:$HERE/usr/lib:$HERE/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
export PATH="$PYROOT/bin:$PATH"
export PYTHONPATH="$HERE/opt/jarvis:$PYTHONPATH"

# Tk needs its data files found explicitly, or the window fails to open
TCLDIR="$(find "$HERE" -maxdepth 6 -type d -name 'tcl8.*' 2>/dev/null | head -1)"
TKDIR="$(find "$HERE" -maxdepth 6 -type d -name 'tk8.*' 2>/dev/null | head -1)"
[ -n "$TCLDIR" ] && export TCL_LIBRARY="$TCLDIR"
[ -n "$TKDIR" ] && export TK_LIBRARY="$TKDIR"

# HTTPS certificates, so first-run model/voice downloads can verify (the bundled Python has no CA path)
for ca in /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt /etc/ssl/cert.pem; do
    [ -f "$ca" ] && export SSL_CERT_FILE="$ca" REQUESTS_CA_BUNDLE="$ca" && break
done
[ -d /etc/ssl/certs ] && export SSL_CERT_DIR=/etc/ssl/certs
if [ -z "${SSL_CERT_FILE:-}" ]; then  # fall back to the bundled certifi CA bundle
    caf="$("$PYBIN" -c 'import certifi; print(certifi.where())' 2>/dev/null)"
    [ -n "$caf" ] && export SSL_CERT_FILE="$caf" REQUESTS_CA_BUNDLE="$caf"
fi

if [ "${1:-}" = "--selftest" ]; then  # used by build-appimage.sh to verify the bundle; prints one line
    "$PYBIN" -c "import tkinter; r=tkinter.Tk(); r.destroy(); print('SELFTEST_OK: the window toolkit works')" \
        || echo "SELFTEST_TK_FAIL (see the error just above)"
    exit 0
fi

"$PYBIN" "$HERE/opt/jarvis/gui.py" "$@" 2>"$LOG" && exit 0
show_error "Jarvis couldn't start. Details saved to $LOG

$(tail -n 20 "$LOG")"
exit 1
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
chmod +x "$here/Jarvis-x86_64.AppImage"

echo
echo "Verifying the bundle (this runs the AppImage's own launcher once)..."
verdict="$("$here/Jarvis-x86_64.AppImage" --appimage-extract-and-run --selftest 2>&1 | grep -E 'SELFTEST' | tail -1)"
[ -n "$verdict" ] || verdict="SELFTEST produced no result - run ./Jarvis-x86_64.AppImage --appimage-extract-and-run to see what happens"
echo "=================================================================="
echo "  RESULT: ${verdict}"
echo "=================================================================="
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
  * The window needs Tk (included in the bundled Python; the launcher points it at the bundled Tcl/Tk data).
    If anything goes wrong at startup, a popup shows the error and it's saved to ~/jarvis-appimage.log -
    no terminal needed.
  * Chat and coding need Ollama: install it on the host (https://ollama.com) and pull the models, OR carry a
    portable Ollama folder next to the AppImage and turn on portable mode (see make-portable.py / README).

If any step above errors, paste the terminal output and I'll adjust this script.
NOTES

#!/usr/bin/env bash
# Sets up Jarvis on Linux: system audio libraries, a virtual environment and the Python packages.
set -e
cd "$(dirname "$0")"

echo "Installing system packages (you may be asked for your password)..."
if command -v apt-get >/dev/null; then
    sudo apt-get install -y python3-venv python3-pip python3-tk libportaudio2 playerctl xdotool espeak-ng
elif command -v dnf >/dev/null; then
    sudo dnf install -y python3 python3-pip python3-tkinter portaudio playerctl xdotool espeak-ng
elif command -v pacman >/dev/null; then
    sudo pacman -S --needed --noconfirm python python-pip tk portaudio playerctl xdotool espeak-ng
elif command -v zypper >/dev/null; then
    sudo zypper install -y python3 python3-pip python3-tk portaudio playerctl xdotool espeak-ng
else
    echo "Unknown package manager. Please install: Python 3.10+, Tk (python3-tk), PortAudio, playerctl, xdotool and espeak-ng."
fi

echo "Creating virtual environment..."
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

chmod +x start.sh start-gui.sh

echo "Adding Jarvis to your app menu..."
[ -f jarvis.png ] || .venv/bin/python make_icon.py >/dev/null
here="$(pwd)"
apps="$HOME/.local/share/applications"
mkdir -p "$apps"
# $1 name, $2 Exec command, $3 Terminal (true/false)
desktop_entry() {
    cat <<ENTRY
[Desktop Entry]
Type=Application
Name=$1
Comment=Offline personal assistant
Exec=$2
Path=$here
Icon=$here/jarvis.png
Terminal=$3
Categories=Utility;
ENTRY
}
desktop_entry "Jarvis" "\"$here/start-gui.sh\"" "false" > "$apps/jarvis.desktop"
desktop_entry "Jarvis (type commands)" "\"$here/start.sh\" --type" "true" > "$apps/jarvis-typed.desktop"

read -r -p "Start Jarvis automatically when you log in? [y/N] " answer || answer=n
if [[ "$answer" =~ ^[Yy] ]]; then
    mkdir -p "$HOME/.config/autostart"
    desktop_entry "Jarvis" "\"$here/start-gui.sh\" --tray" "false" > "$HOME/.config/autostart/jarvis.desktop"
    echo "Jarvis will start when you log in. To stop that, delete ~/.config/autostart/jarvis.desktop"
fi

echo
echo "Done! Open Jarvis from your app menu, or run ./start-gui.sh for the window (./start.sh for the terminal)."
echo "Optional: install Ollama (curl -fsSL https://ollama.com/install.sh | sh), then run these so Jarvis can chat and code:"
echo "    ollama pull qwen3:1.7b"
echo "    ollama pull qwen2.5-coder:3b"

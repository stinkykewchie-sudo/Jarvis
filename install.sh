#!/usr/bin/env bash
# Sets up Jarvis on Linux: system audio libraries, a virtual environment and the Python packages.
set -e
cd "$(dirname "$0")"

echo "Installing system packages (you may be asked for your password)..."
if command -v apt-get >/dev/null; then
    sudo apt-get install -y python3-venv python3-pip libportaudio2 playerctl xdotool espeak-ng
elif command -v dnf >/dev/null; then
    sudo dnf install -y python3 python3-pip portaudio playerctl xdotool espeak-ng
elif command -v pacman >/dev/null; then
    sudo pacman -S --needed --noconfirm python python-pip portaudio playerctl xdotool espeak-ng
elif command -v zypper >/dev/null; then
    sudo zypper install -y python3 python3-pip portaudio playerctl xdotool espeak-ng
else
    echo "Unknown package manager. Please install: Python 3.10+, PortAudio, playerctl, xdotool and espeak-ng."
fi

echo "Creating virtual environment..."
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

chmod +x start.sh

echo "Adding Jarvis to your app menu..."
[ -f jarvis.png ] || .venv/bin/python make_icon.py >/dev/null
here="$(pwd)"
apps="$HOME/.local/share/applications"
mkdir -p "$apps"
desktop_entry() {  # name, arguments
    cat <<ENTRY
[Desktop Entry]
Type=Application
Name=$1
Comment=Offline voice assistant
Exec="$here/start.sh" $2
Path=$here
Icon=$here/jarvis.png
Terminal=true
Categories=Utility;
ENTRY
}
desktop_entry "Jarvis" "" > "$apps/jarvis.desktop"
desktop_entry "Jarvis (type commands)" "--type" > "$apps/jarvis-typed.desktop"

read -r -p "Start Jarvis automatically when you log in? [y/N] " answer || answer=n
if [[ "$answer" =~ ^[Yy] ]]; then
    mkdir -p "$HOME/.config/autostart"
    desktop_entry "Jarvis" "" > "$HOME/.config/autostart/jarvis.desktop"
    echo "Jarvis will start when you log in. To stop that, delete ~/.config/autostart/jarvis.desktop"
fi

echo
echo "Done! Open Jarvis from your app menu, or run ./start.sh"
echo "Optional: install Ollama (curl -fsSL https://ollama.com/install.sh | sh), then run these so Jarvis can chat and code:"
echo "    ollama pull qwen3:1.7b"
echo "    ollama pull qwen2.5-coder:3b"

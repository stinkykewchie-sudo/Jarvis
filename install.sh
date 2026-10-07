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
echo
echo "Done! Run ./start.sh to start Jarvis."
echo "Optional: install Ollama (curl -fsSL https://ollama.com/install.sh | sh) and run 'ollama pull qwen3:1.7b' so Jarvis can chat."

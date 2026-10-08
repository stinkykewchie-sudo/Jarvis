#!/usr/bin/env bash
# Removes Jarvis from a Linux machine: app-menu entries, autostart, the virtual environment,
# downloaded models, and (if you choose) the whole folder and the Ollama models.
cd "$(dirname "$0")"
here="$(pwd)"

echo "This will remove Jarvis's menu entries, autostart, virtual environment and downloaded models."
read -r -p "Continue? [y/N] " a || a=n
[[ "$a" =~ ^[Yy] ]] || { echo "Cancelled."; exit 0; }

rm -f "$HOME/.config/autostart/jarvis.desktop"
rm -f "$HOME/.local/share/applications/jarvis.desktop" "$HOME/.local/share/applications/jarvis-typed.desktop"
echo "Removed menu and autostart entries."

if command -v ollama >/dev/null; then
    read -r -p "Also remove the Ollama models (qwen3:1.7b and qwen2.5-coder:3b)? [y/N] " m || m=n
    if [[ "$m" =~ ^[Yy] ]]; then
        ollama rm qwen3:1.7b 2>/dev/null || true
        ollama rm qwen2.5-coder:3b 2>/dev/null || true
        echo "Removed the Ollama models."
    fi
fi

read -r -p "Delete the whole Jarvis folder, including your notes and the code it wrote? [y/N] " d || d=n
if [[ "$d" =~ ^[Yy] ]]; then
    cd "$HOME"
    rm -rf "$here" "$HOME/Jarvis Projects"
    echo "Jarvis is fully removed."
else
    rm -rf "$here/.venv" "$here/models" "$here/voices" "$here/ollama-models"
    rm -f "$here/jarvis.log" "$here/jarvis.log.1" "$here/jarvis_memory.json"
    echo "Removed the environment and downloaded models. Your files are kept in $here"
    echo "(delete that folder yourself to finish removing Jarvis)."
fi
echo "Done. Ollama itself is left installed - uninstall it separately if you want it gone."

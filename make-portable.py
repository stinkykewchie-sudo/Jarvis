"""Turn this Jarvis folder into a portable one: switch on PORTABLE in config.py and download the Ollama
models into ollama-models/ inside the folder, so everything (code, speech model, voice, AI models) lives
here and can be copied to a USB stick.

Run from the Jarvis folder:   python make-portable.py
Then copy the whole folder to your USB. On each machine, run install.sh / install.bat once (to build the
environment and system libraries), then start Jarvis - it runs its own Ollama server from this folder.

You still need the `ollama` program on each machine (or drop its binary in an 'ollama' folder next to this
script so it travels too).
"""

import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402


def enable_portable_in_config() -> None:
    cfg = HERE / "config.py"
    text = cfg.read_text(encoding="utf-8")
    if re.search(r"^PORTABLE\s*=\s*True", text, re.M):
        print("PORTABLE is already on in config.py.")
        return
    text = re.sub(r"^PORTABLE\s*=\s*False", "PORTABLE = True", text, count=1, flags=re.M)
    cfg.write_text(text, encoding="utf-8")
    print("Turned on PORTABLE in config.py.")


def ollama_binary() -> str | None:
    import shutil
    bundled = HERE / "ollama" / ("ollama.exe" if sys.platform == "win32" else "ollama")
    if bundled.exists():
        return str(bundled)
    found = shutil.which("ollama")
    if found:
        return found
    if sys.platform == "win32":
        guess = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        return str(guess) if guess.exists() else None
    return next((p for p in ("/usr/local/bin/ollama", "/usr/bin/ollama") if Path(p).exists()), None)


def main() -> None:
    binary = ollama_binary()
    if not binary:
        print("Couldn't find the 'ollama' program. Install it from https://ollama.com first,\n"
              "or put its binary in an 'ollama' folder next to this script.")
        sys.exit(1)

    enable_portable_in_config()
    models_dir = HERE / "ollama-models"
    models_dir.mkdir(exist_ok=True)
    port = config.PORTABLE_OLLAMA_PORT
    host = f"127.0.0.1:{port}"
    env = {**os.environ, "OLLAMA_HOST": host, "OLLAMA_MODELS": str(models_dir)}

    print(f"Starting a temporary Ollama server on {host}, storing models in {models_dir} ...")
    kw = {"env": env, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    server = subprocess.Popen([binary, "serve"], **kw)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://{host}", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        for model in (config.OLLAMA_MODEL, config.CODER_MODEL):
            print(f"\nDownloading {model} into the Jarvis folder (this is the big one)...")
            subprocess.run([binary, "pull", model], env=env)
    finally:
        server.terminate()

    size = sum(f.stat().st_size for f in models_dir.rglob("*") if f.is_file())
    print(f"\nDone. The models are in {models_dir} ({size / 1e9:.1f} GB).")
    print("Copy the whole Jarvis folder to your USB. On each machine run install.sh / install.bat once,")
    print("then start Jarvis - it will use these models from the folder.")


if __name__ == "__main__":
    main()

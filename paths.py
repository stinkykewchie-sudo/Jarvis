"""Where Jarvis reads and writes its files.

Normally everything lives in the Jarvis folder (the Windows install, a cloned repo, a USB copy). But inside
an AppImage the program folder is read-only, so notes, memory, the log and downloaded models must go somewhere
writable. This picks the right place automatically:

  - if the Jarvis folder is writable (normal installs) -> use it, so nothing changes
  - otherwise (AppImage) -> use ~/.local/share/Jarvis  (or $JARVIS_DATA if you set it)

Models and the voice are read from the program folder if they were bundled there, else downloaded into the
writable data folder on first run.
"""

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


if os.environ.get("JARVIS_DATA"):
    DATA_DIR = Path(os.environ["JARVIS_DATA"]).expanduser()
elif _writable(APP_DIR):
    DATA_DIR = APP_DIR
else:
    DATA_DIR = Path.home() / ".local" / "share" / "Jarvis"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def data_file(name: str) -> Path:
    """A writable file for notes, memory, the log, etc."""
    return DATA_DIR / name


def model_dir(name: str) -> Path:
    """A folder of models/voices: the bundled one in the program folder if it has files, else a writable one."""
    bundled = APP_DIR / name
    try:
        if bundled.is_dir() and any(bundled.iterdir()):
            return bundled
    except OSError:
        pass
    writable = DATA_DIR / name
    writable.mkdir(parents=True, exist_ok=True)
    return writable

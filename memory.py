"""Things you teach Jarvis: your own voice commands and named websites.

Saved in jarvis_memory.json next to this file, which you can also edit by hand:
{
  "commands": {
    "study time": "open canvas.instructure.com",        <- runs another command
    "check my ip": {"shell": "ipconfig"},                <- runs a terminal command
    "photo renamer": {"script": "C:/Users/me/Jarvis Projects/rename_photos.py"}
  },
  "sites": {"school": "https://canvas.instructure.com"}
}
"""

import json
import re

import paths
from pathlib import Path

FILE = paths.data_file("jarvis_memory.json")

_data: dict | None = None


def _load() -> dict:
    global _data
    if _data is None:
        try:
            _data = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _data = {}
        _data.setdefault("commands", {})
        _data.setdefault("sites", {})
    return _data


def _save() -> None:
    FILE.write_text(json.dumps(_load(), indent=2), encoding="utf-8")


def _key(phrase: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", phrase.lower())).strip()


def to_url(spoken: str) -> str | None:
    """'canvas dot instructure dot com' -> 'https://canvas.instructure.com'. None if it isn't a web address."""
    s = spoken.lower().strip(" .")
    s = re.sub(r"\s+dot\s+", ".", s)
    s = re.sub(r"\s+slash\s+", "/", s)
    s = s.replace(" ", "")
    if not re.fullmatch(r"(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?", s):
        return None
    return s if s.startswith("http") else "https://" + s


# --- commands -------------------------------------------------------------
def teach(phrase: str, action) -> None:
    _load()["commands"][_key(phrase)] = action
    _save()


def command_for(text: str):
    """The action taught for this exact phrase (also with "run" in front), or None."""
    commands = _load()["commands"]
    key = _key(text)
    return commands.get(key) or commands.get(re.sub(r"^(run|do|start) ", "", key))


# --- sites ----------------------------------------------------------------
def remember_site(name: str, url: str) -> None:
    _load()["sites"][_key(name)] = url
    _save()


def site(name: str) -> str | None:
    sites = _load()["sites"]
    key = _key(name)
    return sites.get(key) or sites.get(re.sub(r"^(my|the) ", "", key))


# --- both -----------------------------------------------------------------
def forget(phrase: str) -> bool:
    data, key = _load(), _key(phrase)
    found = data["commands"].pop(key, None) is not None
    found = data["sites"].pop(key, None) is not None or found
    if found:
        _save()
    return found


def describe() -> str:
    data = _load()
    if not data["commands"] and not data["sites"]:
        return ("You haven't taught me anything yet. Try saying: when I say study time, open your school website. "
                "Or: remember my school website is canvas dot com.")
    parts = []
    if data["commands"]:
        parts.append("Your commands are: " + ", ".join(data["commands"]) + ".")
    if data["sites"]:
        parts.append("Your saved websites are: " + ", ".join(data["sites"]) + ".")
    return " ".join(parts)

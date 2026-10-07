"""Everything that talks to the operating system, for Windows and Linux.

Linux support uses common desktop tools when they're installed:
  playerctl (media keys), wpctl / pactl / amixer (volume), loginctl (lock screen),
  gnome-screenshot / spectacle / grim / scrot (screenshots), espeak-ng (fallback voice).
"""

import configparser
import glob
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psutil

WINDOWS = sys.platform == "win32"
LINUX = sys.platform.startswith("linux")


def squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _run(*cmd: str) -> bool:
    """Run a command quietly; True if it exists and succeeded."""
    if not shutil.which(cmd[0]):
        return False
    try:
        return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _spawn(cmd: list[str]) -> bool:
    """Start a program in the background, detached from Jarvis."""
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except OSError:
        return False


def _first_available(candidates: list[str]) -> str | None:
    return next((c for c in candidates if shutil.which(c)), None)


# ---------------------------------------------------------------------------
# Opening apps
# ---------------------------------------------------------------------------
SKIP_WORDS = ("uninstall", "readme", "help", "documentation", "website", "release notes")

WINDOWS_ALIASES = {
    "notepad": "notepad", "text editor": "notepad", "calculator": "calc", "calc": "calc", "paint": "mspaint",
    "file explorer": "explorer", "explorer": "explorer", "files": "explorer", "my files": "explorer",
    "task manager": "taskmgr", "system monitor": "taskmgr", "command prompt": "cmd", "terminal": "wt",
    "powershell": "powershell", "settings": "ms-settings:", "camera": "microsoft.windows.camera:",
    "clock": "ms-clock:", "alarms": "ms-clock:", "microsoft store": "ms-windows-store:", "store": "ms-windows-store:",
    "edge": "msedge", "microsoft edge": "msedge", "chrome": "chrome", "google chrome": "chrome",
    "firefox": "firefox", "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "vs code": "code", "visual studio code": "code", "snipping tool": "ms-screenclip:", "photos": "ms-photos:",
    "control panel": "control",
}

LINUX_ALIASES = {
    "calculator": ["gnome-calculator", "kcalc", "galculator", "qalculate-gtk"],
    "terminal": ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"],
    "command prompt": ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"],
    "settings": ["gnome-control-center", "systemsettings", "xfce4-settings-manager"],
    "notepad": ["gnome-text-editor", "gedit", "kate", "mousepad", "xed", "pluma"],
    "text editor": ["gnome-text-editor", "gedit", "kate", "mousepad", "xed", "pluma"],
    "task manager": ["gnome-system-monitor", "plasma-systemmonitor", "ksysguard", "xfce4-taskmanager"],
    "system monitor": ["gnome-system-monitor", "plasma-systemmonitor", "ksysguard", "xfce4-taskmanager"],
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "google chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "edge": ["microsoft-edge", "microsoft-edge-stable"],
    "vs code": ["code", "codium"], "visual studio code": ["code", "codium"],
}

DESKTOP_DIRS = [
    "/usr/share/applications", "/usr/local/share/applications", "~/.local/share/applications",
    "/var/lib/flatpak/exports/share/applications", "~/.local/share/flatpak/exports/share/applications",
    "/var/lib/snapd/desktop/applications",
]


_start_apps: list[tuple[str, str]] | None = None


def windows_start_apps() -> list[tuple[str, str]]:
    """(name, AppID) for every app in the Start menu, including Microsoft Store apps. Cached after the first call."""
    global _start_apps
    if _start_apps is None:
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-StartApps | ForEach-Object { $_.Name + \"`t\" + $_.AppID }"],
                capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
            ).stdout
            _start_apps = [tuple(line.split("\t", 1)) for line in out.splitlines() if "\t" in line
                           and not line.split("\t", 1)[1].startswith("http")]
        except (OSError, subprocess.TimeoutExpired):
            _start_apps = []
    return _start_apps


def _best_match(wanted: str, items):
    """Pick the item whose squashed title equals `wanted`, else the shortest title containing it."""
    best = None
    for title, value in items:
        if any(w in title.lower() for w in SKIP_WORDS):
            continue
        t = squash(title)
        if t == wanted:
            return title, value
        if wanted in t and (best is None or len(t) < len(squash(best[0]))):
            best = (title, value)
    return best


def _windows_find_shortcut(name: str) -> str | None:
    wanted = squash(name)
    best = None
    for folder in (os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
                   os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs")):
        for lnk in glob.glob(os.path.join(folder, "**", "*.lnk"), recursive=True):
            stem = Path(lnk).stem.lower()
            if any(w in stem for w in SKIP_WORDS):
                continue
            title = squash(stem)
            if title == wanted:
                return lnk
            if wanted in title and (best is None or len(title) < len(best[0])):
                best = (title, lnk)
    return best[1] if best else None


def _linux_desktop_entries() -> list[tuple[str, str, str]]:
    """(display name, desktop id, path) for every visible app in the menu."""
    entries = []
    for folder in DESKTOP_DIRS:
        for path in glob.glob(os.path.join(os.path.expanduser(folder), "**", "*.desktop"), recursive=True):
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
            except (configparser.Error, KeyError, UnicodeDecodeError):
                continue
            if entry.get("NoDisplay", "false").lower() == "true" or entry.get("Type", "Application") != "Application":
                continue
            entries.append((entry.get("Name", Path(path).stem), Path(path).name, path))
    return entries


def _linux_launch_desktop(desktop_id: str, path: str) -> bool:
    if shutil.which("gtk-launch") and _spawn(["gtk-launch", desktop_id]):
        return True
    if shutil.which("gio") and _spawn(["gio", "launch", path]):
        return True
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read(path, encoding="utf-8")
    exec_line = re.sub(r"%[a-zA-Z]", "", parser["Desktop Entry"].get("Exec", "")).strip()
    return bool(exec_line) and _spawn(shlex.split(exec_line))


def open_app(name: str) -> str | None:
    """Open an installed app by its everyday name. Returns the name it opened, or None."""
    key = name.lower().strip()
    wanted = squash(key)
    if not wanted:
        return None

    if WINDOWS:
        match = _best_match(wanted, windows_start_apps())
        if match and _spawn(["explorer.exe", f"shell:AppsFolder\\{match[1]}"]):
            return match[0]
        shortcut = _windows_find_shortcut(key)
        targets = [shortcut] if shortcut else []
        targets += [WINDOWS_ALIASES[key]] if key in WINDOWS_ALIASES else []
        for target in targets:
            try:
                os.startfile(target)
                return Path(target).stem if target == shortcut else name
            except OSError:
                continue
        return None

    # Linux: the app menu first, then known command names, then a command with that name
    best = None
    for display, desktop_id, path in _linux_desktop_entries():
        title = squash(display)
        if title == wanted or squash(Path(desktop_id).stem.split(".")[-1]) == wanted:
            best = (0, display, desktop_id, path)
            break
        if wanted in title and (best is None or len(title) < best[0]):
            best = (len(title), display, desktop_id, path)
    if best and _linux_launch_desktop(best[2], best[3]):
        return best[1]
    command = _first_available(LINUX_ALIASES.get(key, []) + [key.replace(" ", "-"), key.replace(" ", "")])
    if command and _spawn([command]):
        return name
    if key in ("files", "file explorer", "explorer", "my files", "file manager"):
        return name if _spawn(["xdg-open", str(Path.home())]) else None
    return None


def open_path(path: str) -> None:
    if WINDOWS:
        os.startfile(path)
    else:
        _spawn(["xdg-open", path])


# ---------------------------------------------------------------------------
# Closing apps
# ---------------------------------------------------------------------------
PROTECTED = {
    # Windows
    "explorer", "svchost", "csrss", "winlogon", "wininit", "lsass", "services", "system", "smss", "dwm",
    "conhost", "cmd", "powershell", "pwsh", "windowsterminal",
    # Linux
    "systemd", "init", "xorg", "xwayland", "gnome-shell", "kwin_x11", "kwin_wayland", "plasmashell",
    "pipewire", "pulseaudio", "wireplumber", "dbus-daemon", "gdm", "sddm", "lightdm", "bash", "sh", "zsh", "sshd",
    # Jarvis itself
    "python", "pythonw", "python3", "ollama",
}


def close_app(name: str) -> int:
    """Politely close every running process whose name starts with `name`. Returns how many were asked to close."""
    wanted = squash(name)
    if len(wanted) < 3:  # too vague - "close s" must not close half the system
        return 0
    me = os.getpid()
    victims = []
    for proc in psutil.process_iter(["pid", "name"]):
        pname = (proc.info["name"] or "")
        stem = Path(pname).stem.lower()
        if proc.info["pid"] != me and stem not in PROTECTED and squash(stem).startswith(wanted):
            victims.append(proc)
    if WINDOWS:  # taskkill without /f sends a normal close request, so apps can ask to save
        for exe in {Path(p.info["name"]).name for p in victims}:
            subprocess.run(["taskkill", "/im", exe], capture_output=True)
    else:
        for proc in victims:
            try:
                proc.terminate()  # SIGTERM: a polite request to quit
            except psutil.Error:
                pass
    return len(victims)


# ---------------------------------------------------------------------------
# Media and volume
# ---------------------------------------------------------------------------
VK = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "mute": 0xAD, "down": 0xAE, "up": 0xAF}
NO_AUDIO_TOOL = "I need wpctl, pactl or amixer to change the volume on this system."


def _press(vk: int, times: int = 1) -> None:
    import ctypes

    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def media(action: str) -> str | None:
    """action: play_pause | next | previous. Returns an error message, or None on success."""
    if WINDOWS:
        _press(VK[action])
        return None
    player_cmd = {"play_pause": "play-pause", "next": "next", "previous": "previous"}[action]
    if _run("playerctl", player_cmd):
        return None
    xdo_key = {"play_pause": "XF86AudioPlay", "next": "XF86AudioNext", "previous": "XF86AudioPrev"}[action]
    if _run("xdotool", "key", xdo_key):
        return None
    return "I couldn't find a media player to control. Installing playerctl usually fixes that."


def volume_change(percent: int) -> str | None:
    """Raise (positive) or lower (negative) the volume by roughly `percent`."""
    if WINDOWS:
        _press(VK["up" if percent > 0 else "down"], max(1, abs(percent) // 2))
        return None
    sign = "+" if percent > 0 else "-"
    p = abs(percent)
    if (_run("wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"{p}%{sign}")
            or _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{sign}{p}%")
            or _run("amixer", "-q", "-D", "pulse", "sset", "Master", f"{p}%{sign}")
            or _run("amixer", "-q", "sset", "Master", f"{p}%{sign}")):
        return None
    return NO_AUDIO_TOOL


def volume_set(level: int) -> str | None:
    level = max(0, min(level, 100))
    if WINDOWS:  # media keys have no absolute level: drop to zero, then step up (each step is 2%)
        _press(VK["down"], 50)
        _press(VK["up"], round(level / 2))
        return None
    if (_run("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{level / 100:.2f}")
            or _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%")
            or _run("amixer", "-q", "-D", "pulse", "sset", "Master", f"{level}%")
            or _run("amixer", "-q", "sset", "Master", f"{level}%")):
        return None
    return NO_AUDIO_TOOL


def mute_toggle() -> str | None:
    if WINDOWS:
        _press(VK["mute"])
        return None
    if (_run("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")
            or _run("pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle")
            or _run("amixer", "-q", "-D", "pulse", "sset", "Master", "toggle")
            or _run("amixer", "-q", "sset", "Master", "toggle")):
        return None
    return NO_AUDIO_TOOL


# ---------------------------------------------------------------------------
# Screen, battery
# ---------------------------------------------------------------------------
def lock_screen() -> bool:
    if WINDOWS:
        import ctypes

        return bool(ctypes.windll.user32.LockWorkStation())
    return (_run("loginctl", "lock-session") or _run("xdg-screensaver", "lock")
            or _run("dm-tool", "lock") or _run("gnome-screensaver-command", "-l"))


def screenshot() -> str:
    if WINDOWS:  # Windows + Print Screen saves to Pictures\Screenshots
        import ctypes

        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
        _press(0x2C)
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
        return "Screenshot saved to your Pictures, in the Screenshots folder."
    folder = Path.home() / "Pictures" / "Screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    out = str(folder / f"jarvis-{datetime.now():%Y-%m-%d-%H%M%S}.png")
    for cmd in (["gnome-screenshot", "-f", out], ["spectacle", "-b", "-n", "-o", out], ["grim", out],
                ["scrot", out], ["xfce4-screenshooter", "-f", "-s", out], ["import", "-window", "root", out]):
        if _run(*cmd) and Path(out).exists():
            return "Screenshot saved to your Pictures, in the Screenshots folder."
    return "I couldn't take a screenshot. Installing gnome-screenshot, grim or scrot fixes that."


def battery() -> str:
    b = psutil.sensors_battery()
    if b is None:
        return "This computer doesn't seem to have a battery."
    state = "and charging" if b.power_plugged else "on battery power"
    return f"The battery is at {round(b.percent)} percent, {state}."

"""Read-only checks of the OS layer (nothing is opened or closed)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import system  # noqa: E402


def test_linux_desktop_parsing():
    """The Linux app-menu reader works on any OS, so test it with fake .desktop files."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "org.gnome.Calculator.desktop").write_text(
            "[Desktop Entry]\nName=Calculator\nExec=gnome-calculator %U\nType=Application\n", encoding="utf-8")
        (Path(d) / "hidden.desktop").write_text(
            "[Desktop Entry]\nName=Hidden Thing\nExec=hidden\nNoDisplay=true\n", encoding="utf-8")
        (Path(d) / "broken.desktop").write_text("not an ini file", encoding="utf-8")
        old = system.DESKTOP_DIRS
        system.DESKTOP_DIRS = [d]
        try:
            entries = system._linux_desktop_entries()
        finally:
            system.DESKTOP_DIRS = old
    names = [e[0] for e in entries]
    print("desktop entries:", names)
    assert names == ["Calculator"]


def test_battery_reads():
    print("battery:", system.battery())


def test_windows_shortcuts():
    if system.WINDOWS:
        apps = system.windows_start_apps()
        print(f"{len(apps)} start-menu apps")
        for name in ("notepad", "calculator", "steam"):
            print(f"{name:10} ->", system._best_match(name, apps))
        assert system._best_match("calculator", apps) is not None
        print("notepad ->", system._windows_find_shortcut("notepad"))
        print("fake    ->", system._windows_find_shortcut("zzzfakeapp"))
        assert system._windows_find_shortcut("zzzfakeapp") is None


if __name__ == "__main__":
    test_linux_desktop_parsing()
    test_battery_reads()
    test_windows_shortcuts()
    print("\nAll checks passed.")

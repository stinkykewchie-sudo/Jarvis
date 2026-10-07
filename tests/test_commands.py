"""Checks how Jarvis understands commands, without opening, closing or pressing anything.

Run:  python tests/test_commands.py      (or: python -m pytest tests)
"""

import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jarvis  # noqa: E402
import skills  # noqa: E402

calls: list[tuple] = []


def recorder(name, result=None):
    def fn(*args):
        calls.append((name, *args))
        return result(*args) if callable(result) else result
    return fn


# Replace every side effect with a recorder
skills.system = types.SimpleNamespace(
    open_app=recorder("open_app", lambda n: n.title() if n in ("spotify", "notepad", "steam") else None),
    close_app=recorder("close_app", 1), media=recorder("media"), volume_change=recorder("volume_change"),
    volume_set=recorder("volume_set"), mute_toggle=recorder("mute"), lock_screen=recorder("lock", True),
    screenshot=recorder("screenshot", "Screenshot saved."), battery=recorder("battery", "The battery is at 80 percent."),
)
skills.webbrowser = types.SimpleNamespace(open=recorder("browser"))
skills.NOTES_FILE = Path(tempfile.gettempdir()) / "jarvis_test_notes.txt"
skills.NOTES_FILE.unlink(missing_ok=True)
skills.config.HOME_CITY = ""
skills.announce = lambda text: None

# (what you say, expected start of the reply or None for "not a command", expected first side effect)
CASES = [
    ("Hello Jarvis.", "Good ", None),
    ("What can you do?", "I can open apps", None),
    ("What time is it?", "It's ", None),
    ("What's the date today?", "Today is ", None),
    ("Set a timer for 10 minutes for the pasta.", "Timer set for 10 minutes for the pasta.", None),
    ("Remind me to call mom in 2 hours", "Timer set for 2 hours for call mom.", None),
    ("Set a timer for half an hour", "Timer set for 30 minutes.", None),
    ("Can you set a timer for 1 minute and 30 seconds please", "Timer set for 1 minute and 30 seconds.", None),
    ("Cancel all timers", "Cancelled 4 timers.", None),
    ("Take a note: buy milk", "Got it", None),
    ("Add eggs to my shopping list", "Got it", None),
    ("Read my notes", "You have 2 notes. buy milk. eggs.", None),
    ("Clear my notes", "All your notes are cleared.", None),
    ("Turn the volume up a lot", "Turning it up.", ("volume_change", 30)),
    ("Volume down a little", "Turning it down.", ("volume_change", -6)),
    ("Set the volume to 40 percent", "Volume set to 40 percent.", ("volume_set", 40)),
    ("Mute", "", ("mute",)),
    ("Pause the music.", "", ("media", "play_pause")),
    ("Next song", "", ("media", "next")),
    ("Previous track", "", ("media", "previous")),
    ("Play Bohemian Rhapsody on YouTube", "Here's bohemian rhapsody on YouTube.", ("browser",)),
    ("Search for best pizza near me", "Here are the results for best pizza near me.", ("browser",)),
    ("Open Spotify", "Opening Spotify.", ("open_app", "spotify")),
    ("Open the notepad app", "Opening Notepad.", ("open_app", "notepad")),
    ("Open YouTube", "Opening youtube in your browser.", ("open_app", "youtube")),
    ("Go to github.com", "Opening github.com.", ("browser",)),
    ("Open zzzfakeapp", "I couldn't find anything called zzzfakeapp", ("open_app", "zzzfakeapp")),
    ("Close Notepad", "Closing notepad.", ("close_app", "notepad")),
    ("Lock the computer", "Locking the computer.", ("lock",)),
    ("How much battery do I have?", "The battery is at 80 percent.", ("battery",)),
    ("Take a screenshot", "Screenshot saved.", ("screenshot",)),
    ("What's 15 times 23?", "That's 345.", None),
    ("What is 20 percent of 85?", "That's 17.", None),
    ("What is the square root of 144?", "That's 12.", None),
    ("Calculate 100 divided by 8", "That's 12.5.", None),
    ("Tell me a joke", "", None),
    ("What's the weather?", "Which city?", None),
    ("Who was the first president of the United States?", None, None),  # goes to the local AI
]

WAKE_CASES = [
    ("Jarvis, open Spotify.", "open Spotify."),
    ("Hey Jarvis what time is it?", "what time is it?"),
    ("Open Spotify, Jarvis.", "Open Spotify,"),
    ("Jarvis.", ""),
    ("I was talking to Steve.", None),
]


def test_commands():
    failures = 0
    for said, expected, effect in CASES:
        calls.clear()
        reply = skills.handle(said)
        ok = (reply is None) if expected is None else (reply is not None and reply.startswith(expected))
        if effect is not None:
            ok = ok and bool(calls) and calls[0][:len(effect)] == effect
        failures += not ok
        print(f"{'ok ' if ok else 'FAIL'} {said!r:55} -> {reply!r} {calls[:1] if calls else ''}")
    for t in skills.timers:
        t.cancel()
    assert failures == 0, f"{failures} command(s) misunderstood"


def test_wake_word():
    for said, expected in WAKE_CASES:
        m = jarvis.WAKE_WORD.search(said)
        got = (said[m.end():].strip() or said[:m.start()].strip()) if m else None
        print(f"{'ok ' if got == expected else 'FAIL'} {said!r:30} -> {got!r}")
        assert got == expected


def test_exit_phrases():
    assert jarvis.is_exit("Goodbye.") and jarvis.is_exit("Go to sleep")
    assert not jarvis.is_exit("shut down my computer")


if __name__ == "__main__":
    test_commands()
    test_wake_word()
    test_exit_phrases()
    print("\nAll checks passed.")

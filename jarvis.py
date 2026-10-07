"""
Jarvis - an offline, open-source voice assistant for Windows and Linux.

Say "Jarvis" followed by a command:
    "Jarvis, open Spotify"                      "Jarvis, set a timer for 10 minutes"
    "Jarvis, open YouTube in a new tab"         "Jarvis, close the YouTube tab"
    "Jarvis, write a Python script that..."     "Jarvis, use the terminal to find my IP address"
    "Jarvis, when I say study time, open canvas dot com"

Options:
    --type      type commands instead of speaking
    --no-wake   respond to everything you say, without needing "Jarvis"
"""

import argparse
import logging
import re
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import brain
import config
import dialog
import skills
import system
from console import status, warn, you_line
from mouth import Mouth

WAKE_WORD = re.compile(r"\b(?:hey\s+|ok\s+|okay\s+)?(?:jarvis|jarvas|jervis|javis|travis|charvis)\b[\s,.!?]*", re.I)
EXIT_PHRASES = {"goodbye", "good bye", "bye jarvis", "go to sleep", "shut down", "shutdown", "exit",
                "that's all", "turn off", "stop listening", "shut down jarvis"}


# In the few seconds after Jarvis answers you can carry on without saying "Jarvis", but only with something
# that sounds like a request or a question - so song lyrics or a video playing nearby don't set it off.
FOLLOW_UP = re.compile(
    r"^(?:and |also |now |then |ok |okay |oh )?(?:what|what's|who|who's|why|how|when|where|which|is|are|can|could|"
    r"would|will|do|does|did|should|tell|explain|open|close|play|pause|stop|resume|next|previous|skip|turn|set|make|"
    r"write|create|build|run|use|search|google|look|show|find|switch|go|new tab|reopen|refresh|take|add|read|"
    r"remember|save|forget|lock|mute|unmute|volume|change|fix|update|thanks|thank|cancel|start|launch|put|"
    r"i want|i'd like|i need|let's|louder|quieter|again|yes|no)\b", re.I)

log = logging.getLogger("jarvis")


def setup_log() -> None:
    """Keep a small log of what Jarvis heard and did, in jarvis.log next to this file (stays on your PC)."""
    handler = RotatingFileHandler(Path(__file__).with_name("jarvis.log"), maxBytes=500_000, backupCount=1,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def is_exit(text: str) -> bool:
    return skills.normalise(text) in EXIT_PHRASES


def respond(command: str) -> None:
    """Handle one command and speak/show the result. Output goes through `dialog`, so this works the
    same in typed, voice and GUI mode."""
    started = time.time()
    ai = brain.get()
    try:
        reply = skills.handle(command)
        route = "command"
        if reply is None and ai.ready:  # loosely worded? let the AI pick the matching command
            dialog.status("Thinking...")
            picked = ai.pick_command(command)
            if picked:
                reply, route = skills.handle(picked), f"AI picked: {picked}"
    except Exception as e:  # one broken command shouldn't crash Jarvis
        warn(f"(command error: {e})")
        log.exception("command error")
        reply, route = "Sorry, something went wrong with that command.", "error"
    if reply is not None:
        log.info("%s -> %s | %r (%.1fs)", command, route, reply, time.time() - started)
        dialog.say(reply)
        return
    if not ai.ready:
        log.info("%s -> no command, AI off", command)
        dialog.say("I don't know that one yet. Say what can you do to hear my commands.")
        return
    dialog.status("Thinking...")
    try:
        answer = ai.ask(command, speak=lambda sentence: dialog.say(sentence, wait=False),
                        show_code=dialog.stream_code)
        log.info("%s -> AI chat | %r (%.1fs)", command, answer, time.time() - started)
        dialog.wait()
    except Exception as e:
        warn(f"(local AI error: {e})")
        log.exception("AI error")
        dialog.say("My local AI isn't responding. Make sure Ollama is running.")


def run_typed(mouth: Mouth) -> None:
    from console import GREEN, RESET

    while True:
        try:
            command = input(f"{GREEN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not command:
            continue
        if is_exit(command):
            break
        respond(command)
    mouth.say("Goodbye.")


def run_voice(mouth: Mouth, no_wake: bool) -> None:
    from ears import Ears

    ears = Ears()
    ears.calibrate()
    dialog.setup(mouth, ears)
    mouth.say("Jarvis online." + ("" if no_wake else " Say my name when you need me."))
    awake_until = 0.0

    while True:
        try:
            listening = no_wake or time.time() < awake_until
            status("Listening..." if listening else "Waiting for 'Jarvis'...")
            heard = ears.listen(wake_check=None if listening else WAKE_WORD.search)
            if not heard:
                continue

            match = WAKE_WORD.search(heard)
            if match:
                command = heard[match.end():].strip() or heard[:match.start()].strip()
            elif no_wake or (time.time() < awake_until and FOLLOW_UP.match(skills.normalise(heard))):
                command = heard
            else:
                status(f"(heard: {heard})")
                continue
            you_line(heard)

            if not command:  # just "Jarvis" on its own
                mouth.say("Yes?")
                command = ears.listen(wait_seconds=6) or ""
                if not command:
                    continue
                you_line(command)

            if is_exit(command):
                mouth.say("Goodbye. I'll be here if you need me.")
                break

            respond(command)
            awake_until = time.time() + config.FOLLOW_UP_SECONDS
        except KeyboardInterrupt:
            mouth.say("Shutting down.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis - offline voice assistant")
    parser.add_argument("--type", action="store_true", help="type commands instead of speaking")
    parser.add_argument("--no-wake", action="store_true", help="respond without needing the word 'Jarvis'")
    args = parser.parse_args()

    setup_log()
    log.info("--- Jarvis started (%s mode) ---", "typed" if args.type else "voice")
    status("Starting Jarvis...")
    if system.WINDOWS:  # warm the app list so the first "open ..." is instant
        threading.Thread(target=system.windows_start_apps, daemon=True).start()
    mouth = Mouth()
    skills.announce = lambda text: mouth.say(text, wait=False)
    dialog.setup(mouth)
    brain.get()  # checks whether the local AI is available

    hello = f"Hello{', ' + config.YOUR_NAME if config.YOUR_NAME else ''}."
    if args.type:
        mouth.say(f"{hello} Jarvis online. Type a command, or goodbye to quit.")
        run_typed(mouth)
    else:
        mouth.say(hello, wait=False)
        run_voice(mouth, args.no_wake)


if __name__ == "__main__":
    main()

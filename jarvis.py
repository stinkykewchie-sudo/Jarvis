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
import re
import threading
import time

import brain
import config
import dialog
import skills
import system
from console import CODE, RESET, status, warn, you_line
from mouth import Mouth

WAKE_WORD = re.compile(r"\b(?:hey\s+|ok\s+|okay\s+)?(?:jarvis|jarvas|jervis|javis|travis|charvis)\b[\s,.!?]*", re.I)
EXIT_PHRASES = {"goodbye", "good bye", "bye jarvis", "go to sleep", "shut down", "shutdown", "exit",
                "that's all", "turn off", "stop listening", "shut down jarvis"}


def is_exit(text: str) -> bool:
    return skills.normalise(text) in EXIT_PHRASES


def respond(command: str, mouth: Mouth) -> None:
    try:
        reply = skills.handle(command)
    except Exception as e:  # one broken command shouldn't crash Jarvis
        warn(f"(command error: {e})")
        reply = "Sorry, something went wrong with that command."
    if reply is not None:
        mouth.say(reply)
        return
    ai = brain.get()
    if not ai.ready:
        mouth.say("I don't know that one yet. Say what can you do to hear my commands.")
        return
    status("Thinking...")
    try:
        ai.ask(command, speak=lambda sentence: mouth.say(sentence, wait=False),
               show_code=lambda code: print(f"{CODE}{code}{RESET}", end="", flush=True))
        mouth.wait()
    except Exception as e:
        warn(f"(local AI error: {e})")
        mouth.say("My local AI isn't responding. Make sure Ollama is running.")


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
        respond(command, mouth)
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
            heard = ears.listen()
            if not heard:
                continue

            match = WAKE_WORD.search(heard)
            if match:
                command = heard[match.end():].strip() or heard[:match.start()].strip()
            elif no_wake or time.time() < awake_until:
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

            respond(command, mouth)
            awake_until = time.time() + config.FOLLOW_UP_SECONDS
        except KeyboardInterrupt:
            mouth.say("Shutting down.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis - offline voice assistant")
    parser.add_argument("--type", action="store_true", help="type commands instead of speaking")
    parser.add_argument("--no-wake", action="store_true", help="respond without needing the word 'Jarvis'")
    args = parser.parse_args()

    status("Starting Jarvis...")
    if system.WINDOWS:  # warm the app list so the first "open ..." is instant
        threading.Thread(target=system.windows_start_apps, daemon=True).start()
    mouth = Mouth()
    skills.announce = lambda text: mouth.say(text, wait=False)
    dialog.setup(mouth)
    brain.get()  # checks for the local AI and loads it in the background

    hello = f"Hello{', ' + config.YOUR_NAME if config.YOUR_NAME else ''}."
    if args.type:
        mouth.say(f"{hello} Jarvis online. Type a command, or goodbye to quit.")
        run_typed(mouth)
    else:
        mouth.say(hello, wait=False)
        run_voice(mouth, args.no_wake)


if __name__ == "__main__":
    main()

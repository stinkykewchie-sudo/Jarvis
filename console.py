"""Coloured console output."""

import os

if os.name == "nt":
    os.system("")  # enables ANSI colours in the Windows console
CYAN, GREEN, YELLOW, DIM, RESET = "\033[96m", "\033[92m", "\033[93m", "\033[2m", "\033[0m"


def status(msg: str) -> None:
    print(f"{DIM}{msg}{RESET}", flush=True)


def say_line(text: str) -> None:
    print(f"{CYAN}Jarvis:{RESET} {text}", flush=True)


def you_line(text: str) -> None:
    print(f"{GREEN}You:{RESET} {text}", flush=True)


def warn(msg: str) -> None:
    print(f"{YELLOW}{msg}{RESET}", flush=True)

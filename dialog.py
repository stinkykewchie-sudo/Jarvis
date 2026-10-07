"""How Jarvis talks with you in the middle of a task: speaking, asking yes/no questions,
and showing commands, code and output on screen. Works in both voice and typed mode."""

import re

from console import CODE, DIM, RESET, YELLOW, status, you_line

YES = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|do it|go ahead|run it|please do|affirmative|absolutely|"
                 r"of course|go for it|correct|right|install it|fix it|try it)\b", re.I)
NO = re.compile(r"\b(no|nope|nah|cancel|don't|do not|stop|never ?mind|negative|leave it|skip)\b", re.I)

_mouth = None
_ears = None  # None means typed mode


def setup(mouth, ears=None) -> None:
    global _mouth, _ears
    _mouth, _ears = mouth, ears


def say(text: str, wait: bool = True) -> None:
    if _mouth:
        _mouth.say(text, wait=wait)
    else:
        print(f"Jarvis: {text}", flush=True)


def ask(question: str, wait_seconds: float = 8) -> str | None:
    """Say a question and return the answer (spoken or typed), or None if there was none."""
    say(question)
    if _ears is not None:
        answer = _ears.listen(wait_seconds=wait_seconds)
        if answer:
            you_line(answer)
        return answer
    try:
        return input(f"{DIM}   > {RESET}").strip() or None
    except EOFError:
        return None


def confirm(question: str) -> bool:
    """Ask a yes/no question. Anything unclear counts as no after one retry."""
    for attempt in range(2):
        answer = ask(question if attempt == 0 else "Sorry, was that a yes or a no?")
        if answer is None:
            return False
        if NO.search(answer):
            return False
        if YES.search(answer):
            return True
    return False


def show_command(command: str) -> None:
    print(f"{YELLOW}   $ {command}{RESET}", flush=True)


def show_output(output: str, limit: int = 4000) -> None:
    output = output.rstrip()
    if not output:
        return
    if len(output) > limit:
        output = output[:limit] + f"\n... ({len(output) - limit} more characters)"
    for line in output.splitlines():
        print(f"{DIM}   | {line}{RESET}")


def stream_code(chunk: str) -> None:
    """Print code as the AI writes it, so you can watch it appear."""
    print(CODE + chunk, end=RESET if chunk.endswith("\n") else "", flush=True)


__all__ = ["setup", "say", "ask", "confirm", "show_command", "show_output", "stream_code", "status"]

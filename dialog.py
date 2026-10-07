"""How Jarvis talks with you in the middle of a task: speaking, asking yes/no questions,
and showing commands, code and output. Works in three front-ends:
  - typed mode  (console input/output)
  - voice mode  (microphone + speech)
  - GUI mode    (a window, via a "sink" the GUI registers with set_sink)
The rest of Jarvis only ever calls these functions, so it doesn't care which front-end is active."""

import re

from console import CODE, DIM, RESET, YELLOW, status as _console_status, you_line

YES = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|do it|go ahead|run it|please do|affirmative|absolutely|"
                 r"of course|go for it|correct|right|install it|fix it|try it)\b", re.I)
NO = re.compile(r"\b(no|nope|nah|cancel|don't|do not|stop|never ?mind|negative|leave it|skip)\b", re.I)

_mouth = None
_ears = None   # None means typed mode (no microphone)
_sink = None   # a GUI front-end, or None for console/voice


def setup(mouth, ears=None) -> None:
    global _mouth, _ears
    _mouth, _ears = mouth, ears


def set_sink(sink) -> None:
    """Register a GUI front-end. It must provide: jarvis(text), status(text), output(text, code=False),
    ask(question)->str|None, confirm(question)->bool."""
    global _sink
    _sink = sink


def say(text: str, wait: bool = True) -> None:
    if not text.strip():
        return
    if _sink:
        _sink.jarvis(text)
        if _mouth:
            _mouth.say(text, wait=wait, show=False)  # speak, but the window already shows it
    elif _mouth:
        _mouth.say(text, wait=wait)
    else:
        print(f"Jarvis: {text}", flush=True)


def wait() -> None:
    if _mouth:
        _mouth.wait()


def ask(question: str, wait_seconds: float = 8) -> str | None:
    """Ask a question and return the answer, or None if there was none."""
    if _sink:
        return _sink.ask(question)
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
    """Ask a yes/no question once. Silence or anything unclear counts as no."""
    if _sink:
        return _sink.confirm(question)
    answer = ask(question)
    return bool(answer) and not NO.search(answer) and bool(YES.search(answer))


def status(message: str) -> None:
    if _sink:
        _sink.status(message)
    else:
        _console_status(message)


def show_command(command: str) -> None:
    if _sink:
        _sink.output("$ " + command, code=True)
    else:
        print(f"{YELLOW}   $ {command}{RESET}", flush=True)


def show_output(output: str, limit: int = 4000) -> None:
    output = output.rstrip()
    if not output:
        return
    if len(output) > limit:
        output = output[:limit] + f"\n... ({len(output) - limit} more characters)"
    if _sink:
        _sink.output(output)
    else:
        for line in output.splitlines():
            print(f"{DIM}   | {line}{RESET}")


def stream_code(chunk: str) -> None:
    """Show code as the AI writes it, so you can watch it appear."""
    if _sink:
        _sink.output(chunk, code=True, stream=True)
    else:
        print(CODE + chunk, end=RESET if chunk.endswith("\n") else "", flush=True)


__all__ = ["setup", "set_sink", "say", "wait", "ask", "confirm", "status",
           "show_command", "show_output", "stream_code"]

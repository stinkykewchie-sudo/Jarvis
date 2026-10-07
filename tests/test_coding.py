"""Checks how coding requests are understood and routed, without calling the AI or writing files.

Run:  python tests/test_coding.py
"""

import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import coder  # noqa: E402

# Record what code_request would do, instead of actually writing or running code
events = []
coder.write_code = lambda request: events.append(("build", request)) or "building"
coder.brain = types.SimpleNamespace(get=lambda: types.SimpleNamespace(ready=True))
_answer = [""]  # what the user "says" when Jarvis asks what to build
coder.dialog = types.SimpleNamespace(
    say=lambda *a, **k: None,
    ask=lambda q, **k: events.append(("ask",)) or _answer[0],
    NO=re.compile(r"\b(no|nope|nah|never ?mind|cancel|don't)\b", re.I),
)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", s.lower())).strip()


def route(text, answer=""):
    events.clear()
    _answer[0] = answer
    reply = coder.code_request(text, norm(text))
    return reply, list(events)


# Concrete requests: build immediately, no questions
BUILD_NOW = [
    "write a python script that renames my photos by date",
    "make a snake game",
    "write a weather app",
    "build me a website for my bakery",
    "I want a program that gets crypto prices continuously",
    "can you build me a discord bot that welcomes new members",
    "I need a tool to back up my documents folder",
    "create a calculator in python",
    "write a script to rename files",
    "make me a to-do list app",
    "build a dashboard that shows my system stats",
]

# Vague: should ask exactly once, then build from the answer
VAGUE = [
    "code for me", "can you code for me", "help me code", "can you help me code",
    "let's code", "start coding", "write some code", "i want to code", "do some programming",
    "can you program", "help me write some code",
]

# Not coding at all: must return None so chat / other commands handle it
NOT_CODING = [
    "how do i reverse a list in python",   # a question -> coding AI chat, not a build
    "what is python",
    "make me a sandwich",
    "set a timer for five minutes",
    "take a note to call the bank",
    "play some music",
    "what's the weather",
    "open spotify",
    "how are you",
]


def test_build_now():
    for text in BUILD_NOW:
        reply, ev = route(text)
        kinds = [e[0] for e in ev]
        print(f"{'ok ' if kinds == ['build'] else 'FAIL'}  build-now: {text!r} -> {kinds}")
        assert kinds == ["build"], f"{text!r} should build immediately, did {kinds}"
        assert ev[0][1] == text, "should build from the original request text"


def test_vague_asks_once_then_builds():
    for text in VAGUE:
        reply, ev = route(text, answer="a program that sorts my downloads")
        kinds = [e[0] for e in ev]
        print(f"{'ok ' if kinds == ['ask', 'build'] else 'FAIL'}  vague: {text!r} -> {kinds}")
        assert kinds == ["ask", "build"], f"{text!r} should ask once then build, did {kinds}"


def test_vague_then_declined():
    reply, ev = route("help me code", answer="no thanks")
    print(f"{'ok ' if [e[0] for e in ev] == ['ask'] else 'FAIL'}  declined -> {[e[0] for e in ev]}")
    assert [e[0] for e in ev] == ["ask"] and "tell me what to build" in reply.lower()


def test_example_builds_demo_without_asking():
    for text in ["give me an example project and start coding", "show me an example program", "write an example script"]:
        reply, ev = route(text)
        kinds = [e[0] for e in ev]
        print(f"{'ok ' if kinds == ['build'] else 'FAIL'}  example: {text!r} -> {kinds}")
        assert kinds == ["build"], f"{text!r} should build a demo without asking, did {kinds}"


def test_not_coding_returns_none():
    for text in NOT_CODING:
        reply, ev = route(text)
        print(f"{'ok ' if reply is None else 'FAIL'}  not-coding: {text!r} -> {reply!r}")
        assert reply is None, f"{text!r} should not be treated as a build request"


if __name__ == "__main__":
    test_build_now()
    test_vague_asks_once_then_builds()
    test_vague_then_declined()
    test_example_builds_demo_without_asking()
    test_not_coding_returns_none()
    print("\nAll checks passed.")

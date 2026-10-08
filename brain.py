"""Local AI, via Ollama (https://ollama.com). Nothing leaves your PC.

Two models: a small, quick one for conversation (config.OLLAMA_MODEL) and a coding model for
programming questions, terminal commands and writing code (config.CODER_MODEL).
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import config
from console import status

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
CODE_TOPIC = re.compile(  # questions that go to the coding model (kept narrow, because it's slower)
    r"\b(python|javascript|typescript|java|rust|golang|html|css|sql|regex|json|coding|programming|source code|code|"
    r"powershell|bash|terminal|command line|github|git|pip|npm|compile|compiler|debug|debugging|syntax|"
    r"list comprehension|for loop|while loop|data structure|algorithm)\b", re.I)
KEEP_ALIVE = "5m"  # free a model's memory after this long unused (an 8 GB laptop can't hold both at once)

# Requests that sound like the user wants something done go through pick_command before plain chat
ACTION_HINT = re.compile(r"\b(i want|i'd like|i wanna|i need|let's|put on|get me|show me|bring up|turn|can you|"
                         r"could you|would you|will you|please|start|stop|make it|go to|take me|listen|watch|hear)\b",
                         re.I)
ROUTABLE = re.compile(r"^(play|pause|resume|next|previous|volume|turn|mute|unmute|open|new tab|search|set a timer|"
                      r"what time|what's the weather|take a note|read my notes|tell me a joke|take a screenshot|"
                      r"how much battery|close this tab|close the \w+ tab|switch to|refresh)\b", re.I)
PICK_COMMAND_PROMPT = """You turn what the user said into ONE short command for a voice assistant. Commands look like:
play <song, artist, genre or video>
pause / resume / next song / previous song
turn the volume up / turn the volume down / set the volume to <number> percent / mute
open <app or website> / open a new tab to <website> / close this tab / close the <name> tab
search for <query> / set a timer for <number> minutes / what's the weather / take a note <text>
tell me a joke / take a screenshot / how much battery

Examples:
I'd like to hear some jazz -> play jazz
put on something relaxing for studying -> play relaxing study music
I want to watch funny cat videos -> play funny cat videos
I need to wake up in twenty minutes -> set a timer for 20 minutes
can you pull up my email -> open gmail
show me what's happening in the world -> open news.google.com
it's way too loud -> turn the volume down
let me write down that the rent is due friday -> take a note the rent is due friday
why is the sky blue -> NONE
how are you today -> NONE

Reply with only the command, or NONE if it's a question or chat rather than something to do."""

OS_NAME = "Windows" if sys.platform == "win32" else "Linux"
SHELL = "PowerShell" if sys.platform == "win32" else "bash"


def _tag(model: str) -> str:
    return model if ":" in model else model + ":latest"


# Which Ollama server to talk to. In portable mode Jarvis runs its OWN server on its own port, with the
# models kept inside the Jarvis folder (ollama-models/), so the whole folder works from a USB stick.
_PROJECT = Path(__file__).parent
if config.PORTABLE:
    os.environ.setdefault("OLLAMA_MODELS", str(_PROJECT / "ollama-models"))
    OLLAMA_HOST = f"http://127.0.0.1:{config.PORTABLE_OLLAMA_PORT}"
else:
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
    if not OLLAMA_HOST.startswith("http"):
        OLLAMA_HOST = "http://" + OLLAMA_HOST

_client = None


def _oll():
    """The Ollama client, pointed at the right server (cached)."""
    global _client
    if _client is None:
        import ollama
        _client = ollama.Client(host=OLLAMA_HOST)
    return _client


def _ollama_binary() -> str | None:
    import shutil
    bundled = _PROJECT / "ollama" / ("ollama.exe" if sys.platform == "win32" else "ollama")
    if bundled.exists():
        return str(bundled)
    found = shutil.which("ollama")
    if found:
        return found
    if sys.platform == "win32":
        guess = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        return str(guess) if guess.exists() else None
    return next((p for p in ("/usr/local/bin/ollama", "/usr/bin/ollama") if Path(p).exists()), None)


def _reachable() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(OLLAMA_HOST, timeout=1)
        return True
    except Exception:
        return False


def ensure_portable_server() -> None:
    """Portable mode only: start a private Ollama server (if one isn't already answering) that reads the
    models kept inside the Jarvis folder. Does nothing in normal mode."""
    if not config.PORTABLE or _reachable():
        return
    binary = _ollama_binary()
    if not binary:
        status("Portable mode: couldn't find the 'ollama' program. Put it in an 'ollama' folder next to Jarvis.")
        return
    import subprocess
    env = {**os.environ, "OLLAMA_HOST": f"127.0.0.1:{config.PORTABLE_OLLAMA_PORT}",
           "OLLAMA_MODELS": str(_PROJECT / "ollama-models")}
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "env": env}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen([binary, "serve"], **kw)
    except OSError as e:
        status(f"Portable mode: couldn't start the ollama server: {e}")
        return
    for _ in range(40):
        if _reachable():
            status("Portable Ollama server started (models from the Jarvis folder).")
            return
        time.sleep(0.5)
    status("Portable mode: the ollama server didn't come up in time.")


class Brain:
    MAX_TURNS = 8  # remembered back-and-forths

    RECHECK_SECONDS = 15  # how often to look for Ollama again if it wasn't running

    def __init__(self) -> None:
        self.history: list[dict] = []
        self.models: set[str] = set()
        self._checked_at = 0.0
        ensure_portable_server()
        if not self._find_models():
            status("Ollama isn't running - chat and coding are off for now, built-in commands still work. "
                   "(Jarvis will check again when you ask something.)")
            return
        self._announce()

    def _find_models(self) -> bool:
        self._checked_at = time.time()
        try:

            self.models = {m.model for m in _oll().list().models}
        except Exception:
            self.models = set()
        return bool(self.models)

    def _announce(self) -> None:
        for label, model in (("Chat", config.OLLAMA_MODEL), ("Coding", config.CODER_MODEL)):
            if _tag(model) in self.models:
                status(f"{label} AI ready ({model}).")
            else:
                status(f"{label} AI model isn't downloaded. Run:  ollama pull {model}")

    @property
    def ready(self) -> bool:
        # Ollama may start after Jarvis (for example when both start at login), so look again now and then
        if not self.models and time.time() - self._checked_at > self.RECHECK_SECONDS and self._find_models():
            self._announce()
        return _tag(config.OLLAMA_MODEL) in self.models or self.coder_ready

    @property
    def coder_ready(self) -> bool:
        return _tag(config.CODER_MODEL) in self.models

    @property
    def chat_model(self) -> str:
        return config.OLLAMA_MODEL if _tag(config.OLLAMA_MODEL) in self.models else config.CODER_MODEL

    @property
    def code_model(self) -> str:
        return config.CODER_MODEL if self.coder_ready else config.OLLAMA_MODEL

    _loaded: str | None = None

    def _use(self, model: str) -> str:
        """Unload any other model before using this one, so two never sit in memory together."""

        if self._loaded != model:
            try:
                for running in _oll().ps().models:
                    if running.model != _tag(model):
                        _oll().generate(model=running.model, prompt="", keep_alive=0)
            except Exception:
                pass
        self._loaded = model
        return model

    @staticmethod
    def _extra(model: str) -> dict:
        return {"think": False} if model.startswith(("qwen3", "deepseek-r1")) else {}

    # ------------------------------------------------------------------ chat
    def system_prompt(self, coding: bool) -> str:
        who = f" The user's name is {config.YOUR_NAME}." if config.YOUR_NAME else ""
        base = (
            "You are Jarvis, a calm, capable and quietly witty personal assistant, like Tony Stark's J.A.R.V.I.S."
            f"{who} Today is {datetime.now():%A, %B %d, %Y}, and the time is {datetime.now():%I:%M %p}. "
            f"The user's computer runs {OS_NAME}.\n"
        )
        if coding:
            return base + (
                "You are also an expert programmer and teacher. Your words are spoken aloud, but code is shown on "
                "screen. Explain in one to three short spoken sentences, then put any code or commands in a fenced "
                "code block. Never read code aloud, and don't use markdown outside code blocks."
            )
        return base + (
            "Your replies are spoken aloud, so answer in one to three short sentences, in plain conversational "
            "English, with no lists, markdown, emoji or links. You run offline, so you don't know recent news or "
            "live information; say so briefly if asked. If you aren't sure of a fact, say you're not sure."
        )

    def ask(self, text: str, speak: Callable[[str], None], show_code: Callable[[str], None]) -> str:
        """Stream an answer. Prose goes to `speak` a sentence at a time; code blocks go to `show_code`."""

        coding = bool(CODE_TOPIC.search(text))
        model = self._use(self.code_model if coding else self.chat_model)
        messages = [{"role": "system", "content": self.system_prompt(coding)}, *self.history,
                    {"role": "user", "content": text}]
        splitter = _ProseCodeSplitter(speak, show_code)
        for chunk in _oll().chat(model=model, messages=messages, stream=True, keep_alive=KEEP_ALIVE,
                                 options={"num_predict": 900 if coding else 220, "num_ctx": 4096},
                                 **self._extra(model)):
            splitter.feed(chunk.message.content or "")
        reply = splitter.finish()
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        self.history = self.history[-self.MAX_TURNS * 2:]
        return reply

    def summarize(self, request: str, output: str) -> str:
        """Turn command output into a short spoken answer to what the user asked."""

        prompt = (f"The user asked: {request}\nA command was run and printed:\n{output[:3000]}\n\n"
                  "Answer the user's request in one or two short spoken sentences, based only on that output. "
                  "No markdown.")
        model = self._use(self._loaded or self.chat_model)  # whichever is already in memory, to avoid a reload
        r = _oll().chat(model=model, messages=[{"role": "user", "content": prompt}], keep_alive=KEEP_ALIVE,
                        options={"num_predict": 120, "num_ctx": 4096}, **self._extra(model))
        return clean(r.message.content or "") or "Done. The output is on screen."

    def pick_command(self, text: str) -> str | None:
        """Map a loosely worded request ("I want to hear some jazz") onto a built-in command, or None."""

        if not ACTION_HINT.search(text):
            return None
        model = self._use(self.chat_model)
        r = _oll().chat(model=model, keep_alive=KEEP_ALIVE,
                        messages=[{"role": "system", "content": PICK_COMMAND_PROMPT},
                                  {"role": "user", "content": text + " ->"}],
                        options={"temperature": 0, "num_predict": 30}, **self._extra(model))
        command = clean(r.message.content or "").splitlines()[0] if (r.message.content or "").strip() else ""
        command = re.split(r"\s*(?:\||/|->)\s*", command)[0].strip(" '\".,").lower()
        if not command or "<" in command or command == "none" or not ROUTABLE.match(command):
            return None
        return command

    # -------------------------------------------------------------- terminal
    def make_command(self, request: str) -> tuple[str, str]:
        """Translate a request into one shell command. Returns (command, short explanation)."""

        system = (
            f"You turn requests into a single {SHELL} command for {OS_NAME}. Commands run in the user's home "
            f"folder ({Path.home()}). Use only built-in commands and tools that ship with {OS_NAME}. Prefer safe, "
            "read-only commands when the request allows. Never delete, format or shut down anything unless the "
            "request explicitly asks for it. The explanation is one short sentence saying what the command does."
        )
        schema = {"type": "object", "required": ["command", "explanation"],
                  "properties": {"command": {"type": "string"}, "explanation": {"type": "string"}}}
        r = _oll().chat(model=self._use(self.code_model), format=schema, keep_alive=KEEP_ALIVE,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": request}],
                        options={"temperature": 0.1, "num_predict": 300}, **self._extra(self.code_model))
        data = json.loads(r.message.content)
        return data["command"].strip(), clean(data["explanation"])

    # ---------------------------------------------------------------- coding
    def _code(self, messages: list[dict], on_text: Callable[[str], None]) -> str:

        text = ""
        stream = _oll().chat(model=self._use(self.code_model), messages=messages, stream=True, keep_alive=KEEP_ALIVE,
                             options={"num_predict": 3000, "num_ctx": 8192, "temperature": 0.2},
                             **self._extra(self.code_model))
        for chunk in stream:
            piece = chunk.message.content or ""
            text += piece
            on_text(piece)
            if re.search(r"```[^\n]*\n.*?\n```", text, re.S):
                break  # the code is complete; skip any explanation the model adds after it
        on_text("\n")
        return extract_code(text)

    def _code_system(self, language: str) -> str:
        return (f"You are an expert {language} programmer. The code will run on {OS_NAME} with Python "
                f"{sys.version_info.major}.{sys.version_info.minor}. Write complete, working, well-commented code in "
                "a single file. Use only the standard library unless the task really needs a package. "
                "Reply with exactly one fenced code block and nothing else.")

    def write_code(self, request: str, language: str, on_text: Callable[[str], None]) -> str:
        return self._code([{"role": "system", "content": self._code_system(language)},
                           {"role": "user", "content": f"Write a {language} program: {request}"}], on_text)

    def edit_code(self, code: str, language: str, instruction: str, on_text: Callable[[str], None]) -> str:
        return self._code([{"role": "system", "content": self._code_system(language)},
                           {"role": "user", "content": f"Here is my program:\n```\n{code}\n```\n\n"
                                                       f"Change it like this: {instruction}\n"
                                                       "Reply with the complete updated program."}], on_text)

    def fix_code(self, code: str, language: str, error: str, on_text: Callable[[str], None]) -> str:
        return self._code([{"role": "system", "content": self._code_system(language)},
                           {"role": "user", "content": f"This program:\n```\n{code}\n```\n\nfails with this error:\n"
                                                       f"```\n{error[-3000:]}\n```\n"
                                                       "Fix the bug. Reply with the complete corrected program."}],
                          on_text)


class _ProseCodeSplitter:
    """Splits a streamed answer into spoken sentences and on-screen code blocks."""

    def __init__(self, speak: Callable[[str], None], show_code: Callable[[str], None]) -> None:
        self.speak, self.show_code = speak, show_code
        self.pending, self.in_code, self.spoken = "", False, []

    def _say(self, text: str) -> None:
        text = clean(text)
        if text:
            self.speak(text)
            self.spoken.append(text)

    def feed(self, piece: str) -> None:
        self.pending += piece
        while True:
            if self.in_code:
                end = self.pending.find("```")
                if end == -1:  # print whole lines, keep a possible partial fence
                    cut = self.pending.rfind("\n") + 1
                    if cut:
                        self.show_code(self.pending[:cut])
                        self.pending = self.pending[cut:]
                    return
                self.show_code(self.pending[:end] + "\n")
                self.pending = self.pending[end + 3:].lstrip("\n")
                self.in_code = False
            else:
                start = self.pending.find("```")
                if start == -1:
                    *done, rest = SENTENCE_END.split(self.pending)
                    for sentence in done:
                        self._say(sentence)
                    self.pending = rest
                    return
                newline = self.pending.find("\n", start)
                if newline == -1:
                    return  # wait for the rest of the ```language line
                self._say(self.pending[:start])
                self.pending = self.pending[newline + 1:]
                self.in_code = True
                self.show_code("\n")

    def finish(self) -> str:
        if self.in_code:
            self.show_code(self.pending + "\n")
        else:
            self._say(self.pending)
        return " ".join(self.spoken)


def extract_code(text: str) -> str:
    """The contents of the first fenced code block, or the whole text if there isn't one."""
    m = re.search(r"```[\w+#.-]*[^\n]*\n(.*?)```", text, re.S)
    if m:
        return m.group(1).rstrip() + "\n"
    m = re.search(r"```[\w+#.-]*[^\n]*\n(.*)$", text, re.S)  # cut off before the closing fence
    return (m.group(1) if m else text).strip() + "\n"


def clean(text: str) -> str:
    """Strip markdown and leftover reasoning tags so the voice doesn't read symbols aloud."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"[*#_`>~|]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


_brain: Brain | None = None


def get() -> Brain:
    """The shared Brain, created on first use."""
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain

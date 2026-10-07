"""Local AI, via Ollama (https://ollama.com). Nothing leaves your PC.

Two models: a small, quick one for conversation (config.OLLAMA_MODEL) and a coding model for
programming questions, terminal commands and writing code (config.CODER_MODEL).
"""

import json
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

import config
from console import status

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
CODE_TOPIC = re.compile(
    r"\b(python|code|coding|program|programming|script|function|variable|loop|bug|error|exception|terminal|"
    r"command line|powershell|bash|shell|javascript|typescript|html|css|sql|git|github|api|class|syntax|compile|"
    r"debug|regex|json|list comprehension|dictionary|array|string|integer|library|module|pip|npm|linux command)\b", re.I)

OS_NAME = "Windows" if sys.platform == "win32" else "Linux"
SHELL = "PowerShell" if sys.platform == "win32" else "bash"


def _tag(model: str) -> str:
    return model if ":" in model else model + ":latest"


class Brain:
    MAX_TURNS = 8  # remembered back-and-forths

    def __init__(self) -> None:
        self.history: list[dict] = []
        self.models: set[str] = set()
        try:
            import ollama

            self.models = {m.model for m in ollama.list().models}
        except Exception:
            status("Ollama not found - chat and coding are off, built-in commands still work. (https://ollama.com)")
            return
        for label, model in (("Chat", config.OLLAMA_MODEL), ("Coding", config.CODER_MODEL)):
            if _tag(model) in self.models:
                status(f"{label} AI ready ({model}).")
            else:
                status(f"{label} AI model isn't downloaded. Run:  ollama pull {model}")
        if self.ready:  # load the chat model into memory now, so the first question doesn't wait for it
            threading.Thread(target=self._warm_up, daemon=True).start()

    @property
    def ready(self) -> bool:
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

    def _warm_up(self) -> None:
        import ollama

        try:
            ollama.generate(model=self.chat_model, prompt="", keep_alive="30m")
        except Exception:
            pass

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
        import ollama

        coding = bool(CODE_TOPIC.search(text))
        model = self.code_model if coding else self.chat_model
        messages = [{"role": "system", "content": self.system_prompt(coding)}, *self.history,
                    {"role": "user", "content": text}]
        splitter = _ProseCodeSplitter(speak, show_code)
        for chunk in ollama.chat(model=model, messages=messages, stream=True, keep_alive="30m",
                                 options={"num_predict": 900 if coding else 220, "num_ctx": 4096},
                                 **self._extra(model)):
            splitter.feed(chunk.message.content or "")
        reply = splitter.finish()
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        self.history = self.history[-self.MAX_TURNS * 2:]
        return reply

    def summarize(self, request: str, output: str) -> str:
        """Turn command output into a short spoken answer to what the user asked."""
        import ollama

        prompt = (f"The user asked: {request}\nA command was run and printed:\n{output[:3000]}\n\n"
                  "Answer the user's request in one or two short spoken sentences, based only on that output. "
                  "No markdown.")
        r = ollama.chat(model=self.chat_model, messages=[{"role": "user", "content": prompt}], keep_alive="30m",
                        options={"num_predict": 120, "num_ctx": 4096}, **self._extra(self.chat_model))
        return clean(r.message.content or "") or "Done. The output is on screen."

    # -------------------------------------------------------------- terminal
    def make_command(self, request: str) -> tuple[str, str]:
        """Translate a request into one shell command. Returns (command, short explanation)."""
        import ollama

        system = (
            f"You turn requests into a single {SHELL} command for {OS_NAME}. Commands run in the user's home "
            f"folder ({Path.home()}). Use only built-in commands and tools that ship with {OS_NAME}. Prefer safe, "
            "read-only commands when the request allows. Never delete, format or shut down anything unless the "
            "request explicitly asks for it. The explanation is one short sentence saying what the command does."
        )
        schema = {"type": "object", "required": ["command", "explanation"],
                  "properties": {"command": {"type": "string"}, "explanation": {"type": "string"}}}
        r = ollama.chat(model=self.code_model, format=schema, keep_alive="30m",
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": request}],
                        options={"temperature": 0.1, "num_predict": 300}, **self._extra(self.code_model))
        data = json.loads(r.message.content)
        return data["command"].strip(), clean(data["explanation"])

    # ---------------------------------------------------------------- coding
    def _code(self, messages: list[dict], on_text: Callable[[str], None]) -> str:
        import ollama

        text = ""
        stream = ollama.chat(model=self.code_model, messages=messages, stream=True, keep_alive="30m",
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

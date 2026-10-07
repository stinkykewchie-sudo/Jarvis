"""Optional local AI for open-ended questions, via Ollama (https://ollama.com). Nothing leaves your PC."""

import re
import threading
from datetime import datetime
from typing import Callable

import config
from console import status

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class Brain:
    MAX_TURNS = 8  # remembered back-and-forths

    def __init__(self) -> None:
        self.history: list[dict] = []
        self.ready = False
        try:
            import ollama

            names = {m.model for m in ollama.list().models}
            wanted = config.OLLAMA_MODEL if ":" in config.OLLAMA_MODEL else config.OLLAMA_MODEL + ":latest"
            if wanted in names:
                self.ready = True
                status(f"Local AI ready ({config.OLLAMA_MODEL}).")
                # Load the model into memory now, so the first question doesn't wait for it
                threading.Thread(target=lambda: ollama.generate(model=config.OLLAMA_MODEL, prompt="", keep_alive="30m"),
                                 daemon=True).start()
            else:
                status(f"Ollama is running but the model isn't downloaded yet. Run:  ollama pull {config.OLLAMA_MODEL}")
        except Exception:
            status("Ollama not found - chat is off, built-in commands still work. (Install from https://ollama.com)")

    def system_prompt(self) -> str:
        who = f" The user's name is {config.YOUR_NAME}." if config.YOUR_NAME else ""
        return (
            "You are Jarvis, a calm, capable and quietly witty personal assistant, like Tony Stark's J.A.R.V.I.S."
            f"{who} Today is {datetime.now():%A, %B %d, %Y}, and the time is {datetime.now():%I:%M %p}.\n"
            "Your replies are spoken aloud, so answer in one to three short sentences, in plain conversational "
            "English, with no lists, markdown, emoji or links. You run offline, so you don't know recent news or "
            "live information; say so briefly if asked. If you aren't sure of a fact, say you're not sure."
        )

    def ask(self, text: str, speak: Callable[[str], None]) -> str:
        """Stream an answer, handing each finished sentence to `speak` so talking starts sooner."""
        import ollama

        messages = [{"role": "system", "content": self.system_prompt()}, *self.history,
                    {"role": "user", "content": text}]
        extra = {"think": False} if config.OLLAMA_MODEL.startswith(("qwen3", "deepseek-r1")) else {}
        buffer, spoken = "", []
        for chunk in ollama.chat(model=config.OLLAMA_MODEL, messages=messages, stream=True,
                                 keep_alive="30m", options={"num_predict": 220, "num_ctx": 2048}, **extra):
            buffer += chunk.message.content or ""
            *done, buffer = SENTENCE_END.split(buffer)
            for sentence in done:
                sentence = clean(sentence)
                if sentence:
                    speak(sentence)
                    spoken.append(sentence)
        if clean(buffer):
            speak(clean(buffer))
            spoken.append(clean(buffer))

        reply = " ".join(spoken)
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        self.history = self.history[-self.MAX_TURNS * 2:]
        return reply


def clean(text: str) -> str:
    """Strip markdown and leftover reasoning tags so the voice doesn't read symbols aloud."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"[*#_`>~|]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()

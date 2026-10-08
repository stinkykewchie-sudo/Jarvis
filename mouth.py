"""Jarvis's voice: Piper neural TTS (offline), falling back to the system voice (Windows SAPI / espeak-ng)."""

import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np

import config
from console import say_line, status

try:
    import sounddevice as sd  # needs PortAudio; without it Piper playback is off and we use the system voice
except Exception as e:  # OSError if the PortAudio library is missing, ImportError if the package isn't there
    sd = None
    status(f"(audio output library not available, using the system voice: {e})")

VOICES_DIR = Path(__file__).with_name("voices")


def ensure_piper_voice() -> Path | None:
    """Return the voice model path, downloading it (about 60 MB) the first time."""
    model = VOICES_DIR / f"{config.PIPER_VOICE}.onnx"
    if model.exists() and Path(f"{model}.json").exists():
        return model
    try:
        from piper.download_voices import download_voice

        status(f"Downloading voice '{config.PIPER_VOICE}' (one time, about 60 MB)...")
        VOICES_DIR.mkdir(exist_ok=True)
        download_voice(config.PIPER_VOICE, VOICES_DIR)
        return model if model.exists() else None
    except Exception as e:
        status(f"(couldn't download the Piper voice, using the system voice instead: {e})")
        return None


class Mouth:
    """Speaks on a background thread so timers can talk and long answers can stream."""

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._speak = self._load_engine()
        threading.Thread(target=self._run, daemon=True).start()

    def _load_engine(self):
        if sd is None:  # no audio playback library -> use the system voice (espeak-ng / SAPI)
            return None
        model = ensure_piper_voice()
        if model:
            try:
                from piper import PiperVoice, SynthesisConfig

                voice = PiperVoice.load(model)
                syn = SynthesisConfig(length_scale=1.0 / max(config.SPEAKING_RATE, 0.1))

                def speak_piper(text: str) -> None:
                    chunks = [c.audio_int16_array for c in voice.synthesize(text, syn)]
                    if chunks:
                        sd.play(np.concatenate(chunks), voice.config.sample_rate)
                        sd.wait()

                return speak_piper
            except Exception as e:
                status(f"(Piper voice failed to load, using the system voice: {e})")
        return None  # fall back to the system voice, created on the speech thread

    @staticmethod
    def _system_voice():
        if sys.platform == "win32":  # Windows SAPI (COM objects belong to the thread that made them)
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            sapi = win32com.client.Dispatch("SAPI.SpVoice")
            sapi.Rate = round((config.SPEAKING_RATE - 1.0) * 10)
            return sapi.Speak
        engine = shutil.which("espeak-ng") or shutil.which("espeak")
        if engine:
            wpm = str(round(170 * config.SPEAKING_RATE))
            return lambda text: subprocess.run([engine, "-s", wpm, text], stderr=subprocess.DEVNULL)
        if shutil.which("spd-say"):
            return lambda text: subprocess.run(["spd-say", "--wait", text])
        status("(no voice available - install espeak-ng, or check the Piper voice download)")
        return lambda text: None

    def _run(self) -> None:
        speak = self._speak or self._system_voice()
        while True:
            text = self._q.get()
            try:
                speak(text)
            except Exception as e:  # a speech glitch should never take Jarvis down
                status(f"(speech error: {e})")
            finally:
                self._q.task_done()

    def say(self, text: str, wait: bool = True, show: bool = True) -> None:
        if not text.strip():
            return
        if show:
            say_line(text)
        self._q.put(text)
        if wait:
            self.wait()

    def wait(self) -> None:
        """Block until everything queued has been spoken."""
        self._q.join()

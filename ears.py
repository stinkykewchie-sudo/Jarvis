"""Jarvis's hearing: microphone capture + faster-whisper speech recognition (offline)."""

import time
from pathlib import Path

import numpy as np
import sounddevice as sd

import config
from console import status

import paths

MODELS_DIR = paths.model_dir("models")

# Phrases Whisper tends to "hear" in background noise
HALLUCINATIONS = {"you", "thank you", "thanks for watching", "thank you for watching", "bye", "okay", "so", ""}


def input_device():
    """Pick a real microphone. When several audio backends exist (ALSA/OSS/PulseAudio), PortAudio can default
    to a silent ALSA device, so prefer the PulseAudio/PipeWire input other apps use. Returns an index or None."""
    try:
        apis = sd.query_hostapis()
        for want in ("pulse", "pipewire"):
            for api in apis:
                idx = api.get("default_input_device", -1)
                if want in api["name"].lower() and idx is not None and idx >= 0:
                    return idx
        # otherwise the first device that actually has input channels
        default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else sd.default.device
        if isinstance(default_in, int) and default_in >= 0 and sd.query_devices(default_in).get("max_input_channels", 0) > 0:
            return default_in
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                return i
    except Exception:
        pass
    return None


class Ears:
    RATE = 16000
    BLOCK = 480  # 30 ms

    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        status(f"Loading speech recognition ({config.WHISPER_MODEL}); the first run downloads it...")
        self.model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                                  download_root=str(MODELS_DIR))
        self.threshold = 400.0
        self.device = input_device()
        if self.device is not None:
            try:
                status(f"Microphone: {sd.query_devices(self.device)['name']}")
            except Exception:
                pass

    @staticmethod
    def _rms(block: np.ndarray) -> float:
        return float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))

    def _stream(self):
        return sd.InputStream(samplerate=self.RATE, channels=1, dtype="int16", blocksize=self.BLOCK,
                              device=self.device)

    def calibrate(self, seconds: float = 1.5) -> None:
        status("Calibrating microphone - stay quiet for a moment...")
        with self._stream() as stream:
            levels = [self._rms(stream.read(self.BLOCK)[0]) for _ in range(int(seconds * self.RATE / self.BLOCK))]
        ambient = float(np.percentile(levels, 90))
        self.threshold = max(ambient * 2.5, 250.0)
        status(f"Mic ready (noise level {ambient:.0f}, trigger level {self.threshold:.0f}).")

    def record(self, wait_seconds: float | None = None, silence_seconds: float = 1.2,
               max_seconds: float = 15) -> np.ndarray | None:
        """Wait for speech, then record until a pause. Returns 16 kHz int16 audio, or None."""
        per_sec = self.RATE / self.BLOCK
        preroll: list[np.ndarray] = []
        frames: list[np.ndarray] = []
        quiet = 0
        started = time.time()
        with self._stream() as stream:
            while True:
                block = stream.read(self.BLOCK)[0].copy()
                loud = self._rms(block) > self.threshold
                if not frames:
                    preroll = (preroll + [block])[-10:]  # keep ~0.3 s from just before speech starts
                    if loud:
                        frames = preroll[:]
                    elif wait_seconds is not None and time.time() - started > wait_seconds:
                        return None
                    continue
                frames.append(block)
                quiet = 0 if loud else quiet + 1
                if quiet > silence_seconds * per_sec or len(frames) > max_seconds * per_sec:
                    break
        if len(frames) < 0.4 * per_sec:  # too short to be words (a click or a cough)
            return None
        return np.concatenate(frames).flatten()

    def transcribe(self, audio: np.ndarray) -> str | None:
        segments, _ = self.model.transcribe(
            audio.astype(np.float32) / 32768.0,
            language="en",
            beam_size=1,
            condition_on_previous_text=False,
            hotwords="Jarvis",  # teaches Whisper how to spell the wake word
        )
        text = " ".join(s.text for s in segments if s.no_speech_prob < 0.6).strip()
        if text.lower().strip(" .!?,") in HALLUCINATIONS:
            return None
        return text

    def listen(self, wait_seconds: float | None = None, wake_check=None) -> str | None:
        """Record and transcribe one utterance.

        With `wake_check` (a function that says whether text contains the wake word), only the first few
        seconds are transcribed at first. Long sounds without "Jarvis" near the start - music, a video, a
        conversation in the room - are then skipped cheaply instead of keeping the CPU busy.
        """
        audio = self.record(wait_seconds)
        if audio is None:
            return None
        head = 4 * self.RATE
        if wake_check is not None and len(audio) > head + self.RATE:
            start = self.transcribe(audio[:head])
            if not start or not wake_check(start):
                return start
        return self.transcribe(audio)

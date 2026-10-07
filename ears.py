"""Jarvis's hearing: microphone capture + faster-whisper speech recognition (offline)."""

import time
from pathlib import Path

import numpy as np
import sounddevice as sd

import config
from console import status

MODELS_DIR = Path(__file__).with_name("models")

# Phrases Whisper tends to "hear" in background noise
HALLUCINATIONS = {"you", "thank you", "thanks for watching", "thank you for watching", "bye", "okay", "so", ""}


class Ears:
    RATE = 16000
    BLOCK = 480  # 30 ms

    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        status(f"Loading speech recognition ({config.WHISPER_MODEL}); the first run downloads it...")
        self.model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                                  download_root=str(MODELS_DIR))
        self.threshold = 400.0

    @staticmethod
    def _rms(block: np.ndarray) -> float:
        return float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))

    def _stream(self):
        return sd.InputStream(samplerate=self.RATE, channels=1, dtype="int16", blocksize=self.BLOCK)

    def calibrate(self, seconds: float = 1.5) -> None:
        status("Calibrating microphone - stay quiet for a moment...")
        with self._stream() as stream:
            levels = [self._rms(stream.read(self.BLOCK)[0]) for _ in range(int(seconds * self.RATE / self.BLOCK))]
        ambient = float(np.percentile(levels, 90))
        self.threshold = max(ambient * 2.5, 250.0)
        status(f"Mic ready (noise level {ambient:.0f}, trigger level {self.threshold:.0f}).")

    def record(self, wait_seconds: float | None = None, silence_seconds: float = 0.9,
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

    def listen(self, wait_seconds: float | None = None) -> str | None:
        audio = self.record(wait_seconds)
        return None if audio is None else self.transcribe(audio)

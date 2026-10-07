"""Speech loop-back test: Piper says a command, Whisper transcribes it, Jarvis interprets it.

Needs the voice and speech models (downloaded on first run). Plays audio through your speakers.
Run:  python tests/test_speech.py
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jarvis  # noqa: E402
from mouth import ensure_piper_voice  # noqa: E402

PHRASES = [
    "Jarvis, set a timer for five minutes.",
    "Hey Jarvis, what time is it?",
    "Jarvis, open the calculator.",
    "Jarvis, turn the volume down a little.",
]


def main() -> None:
    from piper import PiperVoice
    import sounddevice as sd
    from ears import Ears

    voice = PiperVoice.load(ensure_piper_voice())
    ears = Ears.__new__(Ears)  # skip the microphone; just load the recogniser
    from faster_whisper import WhisperModel
    import config
    ears.model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                              download_root=str(Path(__file__).resolve().parent.parent / "models"))

    for phrase in PHRASES:
        t = time.time()
        audio = np.concatenate([c.audio_int16_array for c in voice.synthesize(phrase)])
        synth_s = time.time() - t
        sd.play(audio, voice.config.sample_rate)
        sd.wait()
        # Piper speaks at 22.05 kHz; Whisper wants 16 kHz
        n = int(len(audio) * 16000 / voice.config.sample_rate)
        audio16 = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.int16)
        t = time.time()
        heard = ears.transcribe(audio16)
        stt_s = time.time() - t
        m = jarvis.WAKE_WORD.search(heard or "")
        command = (heard[m.end():].strip() or heard[:m.start()].strip()) if m else None
        print(f"said:  {phrase}\nheard: {heard}   (voice {synth_s:.1f}s, recognition {stt_s:.1f}s)\n"
              f"wake word: {'yes' if m else 'NO'}  command: {command!r}\n")


if __name__ == "__main__":
    main()

"""Microphone check: lists input devices, records 3 seconds from the one Jarvis would use, and prints the
level it heard. Run it to see whether Jarvis can actually hear you.

  python mictest.py            (from the Jarvis folder)
  ./Jarvis-x86_64.AppImage --appimage-extract-and-run --mictest   (from the AppImage)
"""

import sys

import numpy as np
import sounddevice as sd

from ears import input_device


def main() -> None:
    print("Audio backends:", ", ".join(h["name"] for h in sd.query_hostapis()))
    inputs = [(i, d["name"]) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]
    print("Input devices:")
    for i, name in inputs:
        print(f"   [{i}] {name}")
    if not inputs:
        print("RESULT: NO input devices found - the mic isn't reaching this program.")
        return

    dev = input_device()
    name = sd.query_devices(dev)["name"] if dev is not None else "system default"
    print(f"Jarvis would use: [{dev}] {name}")
    print("Recording 3 seconds - say something now...")
    rate = 16000
    audio = sd.rec(int(3 * rate), samplerate=rate, channels=1, dtype="int16", device=dev)
    sd.wait()
    peak = int(np.abs(audio).max())
    rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    print(f"peak level: {peak} of 32767    average: {rms:.0f}")
    if peak < 300:
        print("RESULT: SILENT - Jarvis isn't getting audio from this device (try a different input).")
    else:
        print("RESULT: HEARD YOU - the microphone works for Jarvis.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"RESULT: ERROR - {type(e).__name__}: {e}")
        sys.exit(1)

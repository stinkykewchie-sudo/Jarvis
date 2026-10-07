"""Jarvis settings - edit these to personalise your assistant."""

# About you
YOUR_NAME = ""                 # e.g. "Angel" - Jarvis greets you by name
HOME_CITY = ""                 # e.g. "Chicago" - used when you ask about the weather
TEMPERATURE_UNIT = "fahrenheit"  # "fahrenheit" or "celsius"

# Speech recognition (faster-whisper, runs on your CPU)
# tiny.en = fastest, base.en = balanced, small.en = most accurate but slower
WHISPER_MODEL = "base.en"

# Voice (Piper). Browse voices at https://rhasspy.github.io/piper-samples/
# If the voice can't be loaded, Jarvis falls back to the system voice (Windows SAPI or espeak-ng on Linux).
PIPER_VOICE = "en_GB-alan-medium"
SPEAKING_RATE = 1.0            # 1.0 = normal, 1.2 = faster, 0.8 = slower

# Local AI chat (optional, needs Ollama: https://ollama.com).
# Without it, Jarvis still runs every built-in command - it just can't chat.
OLLAMA_MODEL = "qwen3:1.7b"    # small enough for a laptop; try "qwen3:4b" on a faster PC

# Behaviour
FOLLOW_UP_SECONDS = 8          # after Jarvis answers, keep talking without saying "Jarvis"
WEATHER_ONLINE = True          # the weather command uses the free Open-Meteo service; set False to stay fully offline

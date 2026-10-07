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

# Local AI (optional, needs Ollama: https://ollama.com).
# Without it, Jarvis still runs every built-in command - it just can't chat or code.
OLLAMA_MODEL = "qwen3:1.7b"        # conversation; small enough for a laptop. Try "qwen3:4b" on a faster PC
CODER_MODEL = "qwen2.5-coder:3b"   # code and terminal commands. Try "qwen2.5-coder:7b" with 16 GB of RAM

# Coding and terminal commands
PROJECTS_DIR = "~/Jarvis Projects"  # where the code Jarvis writes is saved
# Look-up commands (like ipconfig) and programs Jarvis writes run straight away. Commands that change things,
# and programs that delete files, always ask first; dangerous commands are always refused.
ALWAYS_ASK_BEFORE_RUNNING = False   # True = ask before every command and program

# Music: what "play some music" puts on (a YouTube search - the top video plays)
DEFAULT_MUSIC = "popular music mix"

# Behaviour
FOLLOW_UP_SECONDS = 8          # after Jarvis answers, keep talking without saying "Jarvis"
WEATHER_ONLINE = True          # the weather command uses the free Open-Meteo service; set False to stay fully offline

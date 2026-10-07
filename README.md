# Jarvis

An open-source voice assistant for **Windows and Linux** that runs on your own computer.
Say "Jarvis", then a command. Speech recognition, the voice, and the optional AI chat all run locally,
with no accounts, no API keys and no cloud AI.

```
You:    Jarvis, open Spotify.
Jarvis: Opening Spotify.
You:    Jarvis, set a timer for 10 minutes for the pasta.
Jarvis: Timer set for 10 minutes for the pasta.
You:    Jarvis, what's 15 percent of 80?
Jarvis: That's 12.
```

## What it can do

| Say something like | What happens |
|---|---|
| "open Spotify", "launch Steam", "open notepad", "go to github.com" | Opens apps (from your Start menu or app menu) and websites |
| "close Discord" | Asks the app to close, so it can still prompt you to save |
| "play lo-fi beats on YouTube", "search for pizza near me" | Opens YouTube or Google results in your browser |
| "pause", "next song", "previous track", "mute" | Controls whatever music or video is playing |
| "turn the volume up a lot", "set the volume to 40 percent" | Changes the system volume |
| "set a timer for 10 minutes", "remind me to call mom in 2 hours", "cancel timers" | Timers that Jarvis announces out loud |
| "take a note: buy milk", "add eggs to my shopping list", "read my notes", "clear my notes" | Notes saved to `jarvis_notes.txt` |
| "what's the weather", "will it rain tomorrow in Paris" | Weather from Open-Meteo (the only feature that uses the internet; can be turned off) |
| "what's 15 times 23", "square root of 144", "20 percent of 85" | Maths |
| "what time is it", "what's the date", "how much battery do I have" | Quick facts |
| "lock the computer", "take a screenshot" | System actions |
| "tell me a joke", "what can you do" | Small talk and help |
| Anything else ("why is the sky blue?") | Answered by a local AI model, if you install Ollama (optional) |

After Jarvis answers you have 8 seconds to follow up without saying "Jarvis" again.
Say "goodbye" to quit.

## How it works

Everything is open source:

| Part | Project | License |
|---|---|---|
| Speech recognition | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) running OpenAI's [Whisper](https://github.com/openai/whisper) model | MIT |
| Voice | [Piper](https://github.com/OHF-Voice/piper1-gpl) neural text-to-speech | GPL-3.0 |
| Local AI chat (optional) | [Ollama](https://github.com/ollama/ollama) running [Qwen3](https://github.com/QwenLM/Qwen3) | MIT / Apache-2.0 |
| Microphone and audio | [python-sounddevice](https://github.com/spatialaudio/python-sounddevice) | MIT |
| Weather (optional) | [Open-Meteo](https://github.com/open-meteo/open-meteo) | AGPL-3.0 (data CC BY 4.0) |

The first time you start Jarvis it downloads the speech model (about 145 MB) and the voice (about 60 MB).
After that it works offline.

## Install

You need **Python 3.10 or newer** and a microphone.

### Windows

1. Install Python from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
2. Download this repository (green **Code** button, then **Download ZIP**) and unzip it, or `git clone` it.
3. Double-click **`install.bat`**.
4. Double-click **`Start Jarvis.bat`**.

### Linux

```bash
git clone https://github.com/stinkykewchie-sudo/Jarvis.git
cd Jarvis
./install.sh     # installs PortAudio, playerctl and espeak-ng, then the Python packages
./start.sh
```

`install.sh` supports apt (Ubuntu, Debian, Mint), dnf (Fedora), pacman (Arch) and zypper (openSUSE).
Volume control uses `wpctl`, `pactl` or `amixer`, and screenshots use `gnome-screenshot`, `spectacle`, `grim` or `scrot`.
Most desktops already have one of each.

### Optional: local AI chat

Built-in commands work without this. To let Jarvis answer general questions:

1. Install Ollama from https://ollama.com (on Linux: `curl -fsSL https://ollama.com/install.sh | sh`).
2. Download a model: `ollama pull qwen3:1.7b` (about 1.4 GB).
3. Restart Jarvis. It prints "Local AI ready" when it finds the model.

`qwen3:1.7b` runs on most laptops. If your PC has 16 GB of RAM or a good graphics card, `qwen3:4b` or `qwen3:8b` give
better answers. Set `OLLAMA_MODEL` in `config.py` to match.

## Options

```
Start Jarvis.bat --type       (Linux: ./start.sh --type)      type commands instead of speaking
Start Jarvis.bat --no-wake    (Linux: ./start.sh --no-wake)   respond without needing to say "Jarvis"
```

## Settings

Edit `config.py`:

| Setting | What it does |
|---|---|
| `YOUR_NAME` | Jarvis greets you by name |
| `HOME_CITY`, `TEMPERATURE_UNIT` | Default place and unit for weather |
| `WHISPER_MODEL` | `tiny.en` (fastest), `base.en` (default), `small.en` (most accurate) |
| `PIPER_VOICE` | Any voice from the [Piper samples page](https://rhasspy.github.io/piper-samples/), e.g. `en_US-lessac-medium` |
| `SPEAKING_RATE` | Talking speed |
| `OLLAMA_MODEL` | Which local AI model to chat with |
| `FOLLOW_UP_SECONDS` | How long Jarvis keeps listening after answering |
| `WEATHER_ONLINE` | Set to `False` to keep Jarvis fully offline |

## Troubleshooting

- **Jarvis doesn't react when I talk.** Stay quiet during "Calibrating microphone" at startup. Check that the right
  microphone is the system default. In a noisy room, try `--no-wake` or a headset.
- **It mishears me.** Set `WHISPER_MODEL = "small.en"` in `config.py`. It's more accurate but slower.
- **Linux: `OSError: PortAudio library not found`.** Install PortAudio: `sudo apt install libportaudio2`.
- **Linux: music controls do nothing.** Install `playerctl`.

## Adding your own commands

Commands live in `skills.py`, in the `handle()` function. Each one is a regular expression plus a reply, for example:

```python
if re.search(r"\bflip a coin\b", t):
    return random.choice(["Heads.", "Tails."])
```

Anything that touches the operating system goes in `system.py`, which has a Windows and a Linux version of each action.
Run the tests with `python tests/test_commands.py` and `python tests/test_system.py`. They don't open or close anything.

## Privacy

Audio is processed on your computer and never recorded to disk. Only the weather command contacts the internet,
and only when you ask for the weather. Weather data is provided by [Open-Meteo.com](https://open-meteo.com/).

## License

MIT. See [LICENSE](LICENSE). The libraries Jarvis uses keep their own licenses, listed above.

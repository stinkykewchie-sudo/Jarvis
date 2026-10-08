# Jarvis

An open-source voice assistant for **Windows and Linux** that runs on your own computer.
Say "Jarvis", then a command. It controls your apps and browser tabs, answers questions, runs terminal commands,
and writes and fixes code for you. Speech recognition, the voice and the AI all run locally,
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
| "open a new tab to YouTube", "open reddit.com in a new tab", "new tab" | Opens browser tabs |
| "close this tab", "close the YouTube tab", "close the last 3 tabs", "reopen the last closed tab" | Closes tabs, including by name |
| "switch to the Gmail tab", "next tab", "refresh the page", "go back" | Moves around your tabs |
| "play some music", "play Drake", "I want to listen to jazz", "put on lo-fi beats" | Finds the top YouTube video and plays it |
| "search for pizza near me", "search YouTube for guitar lessons" | Opens Google or YouTube results |
| "pause", "resume", "next song", "previous track", "mute", "it's too loud" | Controls whatever music or video is playing |
| "turn the volume up a lot", "set the volume to 40 percent" | Changes the system volume |
| "set a timer for 10 minutes", "remind me to call mom in 2 hours", "cancel timers" | Timers that Jarvis announces out loud |
| "take a note: buy milk", "add eggs to my shopping list", "read my notes", "clear my notes" | Notes saved to `jarvis_notes.txt` |
| "what's the weather", "will it rain tomorrow in Paris" | Weather from Open-Meteo (the only feature that uses the internet; can be turned off) |
| "what's 15 times 23", "square root of 144", "20 percent of 85" | Maths |
| "what time is it", "what's the date", "how much battery do I have" | Quick facts |
| "lock the computer", "take a screenshot" | System actions |
| "tell me a joke", "what can you do" | Small talk and help |
| "write a Python script that renames my photos by date", "make a snake game in Python" | Writes the code, saves it, opens it, and runs it if you say yes |
| "make the game faster", "fix it", "run it again" | Changes, fixes or re-runs the last program |
| "use the terminal to find my IP address", "show my disk space in the terminal" | Works out the command, shows it, asks, runs it and tells you the answer |
| "how do I reverse a list in Python?" | Explains out loud and puts the code on screen |
| "when I say study time, open my school website", "remember my school website is canvas dot com", "save that as check my IP" | Teaches Jarvis your own commands and sites |
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
| Local coding AI (optional) | [Qwen2.5-Coder](https://github.com/QwenLM/Qwen2.5-Coder) through Ollama | Apache-2.0 |
| Microphone and audio | [python-sounddevice](https://github.com/spatialaudio/python-sounddevice) | MIT |
| Weather (optional) | [Open-Meteo](https://github.com/open-meteo/open-meteo) | AGPL-3.0 (data CC BY 4.0) |

The first time you start Jarvis it downloads the speech model (about 145 MB) and the voice (about 60 MB).
After that it works offline.

## Install

You need **Python 3.10 or newer** and a microphone.

### Windows

1. Install Python from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
2. Download this repository (green **Code** button, then **Download ZIP**) and unzip it, or `git clone` it.
3. Double-click **`install.bat`**. It installs everything, adds **Jarvis** to your Desktop and Start menu,
   and asks whether Jarvis should start when you log in.
4. Click the **Jarvis** icon. It opens the window; click **Listen** to talk, or type a command.

### Linux

```bash
git clone https://github.com/stinkykewchie-sudo/Jarvis.git
cd Jarvis
./install.sh     # installs PortAudio, playerctl, xdotool and espeak-ng, then the Python packages
./start.sh
```

`install.sh` also adds **Jarvis** and **Jarvis (type commands)** to your app menu, and asks whether Jarvis should
start when you log in.

`install.sh` supports apt (Ubuntu, Debian, Mint), dnf (Fedora), pacman (Arch) and zypper (openSUSE).
Volume control uses `wpctl`, `pactl` or `amixer`, and screenshots use `gnome-screenshot`, `spectacle`, `grim` or `scrot`.
Most desktops already have one of each. Browser tab control uses `xdotool`, which only works in X11 sessions, not Wayland.
Opening tabs works everywhere.

### Optional: local AI for chat and coding

Built-in commands work without this. To let Jarvis answer questions, write code and run terminal commands:

1. Install Ollama from https://ollama.com (on Linux: `curl -fsSL https://ollama.com/install.sh | sh`).
2. Download the models:
   ```
   ollama pull qwen3:1.7b          # conversation, about 1.4 GB
   ollama pull qwen2.5-coder:3b    # code and terminal commands, about 1.9 GB
   ```
3. Restart Jarvis. It prints "Chat AI ready" and "Coding AI ready" when it finds them.

These models run on an ordinary laptop: chat answers take a few seconds, and a short program takes a minute or two.
They handle small scripts and everyday commands well, but they're far less capable than big cloud AIs, so check the
code before running anything important. With 16 GB of RAM or a good graphics card, `qwen3:4b` and
`qwen2.5-coder:7b` are noticeably smarter. Set `OLLAMA_MODEL` and `CODER_MODEL` in `config.py` to match.

## Coding and terminal commands

- Code Jarvis writes is saved in a **Jarvis Projects** folder in your home folder and opened in VS Code (or Notepad).
  Say "open my projects folder" to see everything.
- Jarvis runs a new program straight away. If it crashes, Jarvis reads the error and fixes it, up to two times.
  If it needs a Python package, it asks before installing it.
- Programs that wait for typing, draw windows, or run forever (games, `input()`, tkinter, servers) open in their own
  terminal window.
- Typed mode (`--type`) is handy for longer coding requests.

### Safety

- Jarvis shows every terminal command on screen. Commands that only look things up (like `ipconfig` or `df -h`) run
  straight away; anything that changes something asks first. Set `ALWAYS_ASK_BEFORE_RUNNING = True` in `config.py`
  to be asked every time.
- **It never deletes files by voice.** Commands that delete files, format disks, shut down, change system settings
  or accounts, use `sudo`, or download-and-run scripts are refused even if you say yes. They're shown on screen so
  you can run them yourself if you really mean to.
- Programs that delete or move files get an extra warning before they run.
- The AI can still make mistakes, so read the command or code before you say yes.

## Teaching Jarvis

| Say | What it learns |
|---|---|
| "when I say study time, open my school website" | A new phrase that runs any other command |
| "remember my school website is canvas dot instructure dot com" | A name for a website ("open my school website", "open school in a new tab") |
| "save that as check my IP" (after a command or program ran) | A phrase that runs that exact command or program again, without asking |
| "what have you learned?" / "forget study time" | Lists or removes what you taught it |

Everything you teach is saved in `jarvis_memory.json`, which you can also edit by hand.

### Window or terminal

Clicking the **Jarvis** icon opens a window (dark chat view, a text box, a 🎤 Listen button, and a system-tray
icon). It's the same assistant as the terminal version - every command, the coding and the voice all work the same.

- **Window:** the Desktop / Start-menu icon, or `Jarvis (window).bat` on Windows, `./start-gui.sh` on Linux.
- **Terminal:** `Start Jarvis.bat` on Windows, `./start.sh` on Linux (Start menu also has "Jarvis (voice terminal)"
  and "Jarvis (type commands)").

Closing the window hides Jarvis to the system tray, where you can reopen or quit it. Click **Listen** to talk, or
just type in the box.

### Starting Jarvis when you log in

If you said yes during install, Jarvis starts in the system tray each time you log in and listens for its name.
It's fine if Ollama starts a little later: Jarvis checks again when you first ask it something.

- **Windows:** turn it on or off with
  `powershell -ExecutionPolicy Bypass -File shortcuts.ps1 -Startup` or `-NoStartup`,
  or in Task Manager under **Startup apps**. `-Remove` removes every Jarvis shortcut.
- **Linux:** delete `~/.config/autostart/jarvis.desktop` to turn it off, or run `./install.sh` again to turn it on.

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
| `OLLAMA_MODEL`, `CODER_MODEL` | Which local AI models to chat and code with |
| `PROJECTS_DIR` | Where the code Jarvis writes is saved |
| `ALWAYS_ASK_BEFORE_RUNNING` | Ask before every command and program, not just ones that change things |
| `DEFAULT_MUSIC` | What "play some music" puts on |
| `FOLLOW_UP_SECONDS` | How long Jarvis keeps listening after answering |
| `WEATHER_ONLINE` | Set to `False` to keep Jarvis fully offline |

## Troubleshooting

- **Jarvis doesn't react when I talk.** Stay quiet during "Calibrating microphone" at startup. Check that the right
  microphone is the system default. In a noisy room, try `--no-wake` or a headset.
- **It mishears me.** Set `WHISPER_MODEL = "small.en"` in `config.py`. It's more accurate but slower.
- **Linux: `OSError: PortAudio library not found`.** Install PortAudio: `sudo apt install libportaudio2`.
- **Linux: music controls do nothing.** Install `playerctl`.
- **Tab commands say there's no browser window.** Make sure a browser is open (Chrome, Edge, Firefox, Brave, Opera
  or Vivaldi). On Linux, install `xdotool` and use an X11 session.
- **Chat or coding says the AI isn't responding.** Make sure Ollama is running: open it from the Start menu (Windows)
  or run `ollama serve` (Linux).
- **A YouTube video opens but doesn't start playing (Firefox).** Firefox blocks videos with sound from starting by
  themselves. On YouTube, click the icon at the left of the address bar, and set **Autoplay** to
  **Allow Audio and Video**.
- **Jarvis did something odd.** `jarvis.log` lists what it heard, which command it chose, and how long it took.

## Adding your own commands

Commands live in `skills.py`, in the `handle()` function. Each one is a regular expression plus a reply, for example:

```python
if re.search(r"\bflip a coin\b", t):
    return random.choice(["Heads.", "Tails."])
```

Anything that touches the operating system goes in `system.py`, which has a Windows and a Linux version of each action.
Browser tabs are in `browser.py`, coding and terminal commands in `coder.py`, and the AI prompts in `brain.py`.

Run the tests with `python tests/test_commands.py`, `python tests/test_safety.py` and `python tests/test_system.py`.
They don't open, close or run anything.

## Portable (run from a USB)

Jarvis can live on a USB stick so its big files travel with it. The Jarvis code, the Whisper speech model and the
Piper voice already sit inside the folder; portable mode also keeps the Ollama AI models here instead of in your
home folder, and runs a private Ollama server (on port 11435) just for Jarvis.

1. Install Jarvis onto the USB (clone or copy the folder there), and install Ollama.
2. From the Jarvis folder, run:
   ```
   python make-portable.py
   ```
   This turns on `PORTABLE` in `config.py` and downloads the models into `ollama-models/` inside the folder (~3.3 GB).
3. Copy the whole folder to the USB if you didn't already.

On each computer you plug into, run `install.sh` (Linux) or `install.bat` (Windows) **once** - that rebuilds the Python
environment and installs a few shared libraries on that machine. Then start Jarvis; it uses the models from the folder.

What travels and what doesn't:

- **Travels on the USB:** the code, the speech model, the voice, the Ollama models, your notes and settings.
- **Rebuilt per machine:** the Python environment (`.venv`) and a few system libraries (PortAudio, Tk, espeak-ng),
  because those are tied to each machine's OS and Python. The `ollama` program is installed per machine too, unless you
  drop its binary in an `ollama` folder next to Jarvis so it travels as well.
- **Format the USB as ext4** if you'll use it on Linux (exFAT/FAT32 can't store the Python environment properly).

For a true plug-in-and-run stick with nothing installed on the host, `build-appimage.sh` builds a single-file Linux
**AppImage** that bundles Python and the packages. It's experimental and must be built on a Linux machine; pair it with
a portable Ollama folder on the same stick for chat and coding.

## Uninstalling

- **Windows:** double-click `uninstall.bat`. It removes the shortcuts, the virtual environment and the downloaded
  models, and offers to remove the Ollama models, then tells you to delete the folder.
- **Linux:** run `./uninstall.sh`. It removes the menu entries, autostart, the environment and models, and offers to
  delete the whole folder and the Ollama models.

Both leave the Ollama program itself installed - remove it separately (Windows: Settings → Apps; Linux: see the
Ollama docs) if you want it gone too.

## Privacy

Audio is processed on your computer and never recorded to disk. Your notes, the things you teach Jarvis, and
`jarvis.log` (the text of what you asked and what Jarvis did) stay in local files. Jarvis only contacts the internet
when you ask for the weather (from [Open-Meteo.com](https://open-meteo.com/)) or ask it to play something (it looks up
the top YouTube result).

## License

MIT. See [LICENSE](LICENSE). The libraries Jarvis uses keep their own licenses, listed above.

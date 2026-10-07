"""Terminal commands and coding with the local AI.

Safety rules:
  - Every terminal command and program is shown on screen.
  - Commands that only look things up run straight away; anything else asks first
    (or everything asks, with ALWAYS_ASK_BEFORE_RUNNING = True).
  - Programs Jarvis writes run straight away, unless they delete or move files - then it asks.
  - Commands that could wipe files or the system are never run by voice, whatever you answer.
"""

import re
import shlex
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import brain
import config
import dialog
import system

PROJECTS = Path(config.PROJECTS_DIR).expanduser()
RUN_TIMEOUT = 60  # seconds a captured command or program may run

# Things Jarvis refuses to run by voice, even if you say yes. Deleting files is never done by voice:
# a misheard word or a wrong guess by a small AI model could wipe something that can't be recovered.
_CMD = r"(?:^|[\s;|&(`{]|\$\()"  # start of a command inside a pipeline or script block
DANGEROUS = [re.compile(p, re.I) for p in (
    # deleting or emptying files and folders
    _CMD + r"(?:rm|del|erase|rd|rmdir|ri|unlink|shred|truncate|srm)(?:\.exe)?(?=\s|$)",
    r"\bremove-item\b", r"\bclear-(?:content|item|recyclebin|disk)\b", r"\bremove-(?:partition|volume|itemproperty)\b",
    r"-delete\b", r"\bexec\s+rm\b", r"::delete\b", r"\b(?:rmtree|os\.remove|os\.unlink|unlink\(|rmdir\()",
    r"\bgit\s+(?:clean|reset\s+--hard|push\s+.*--force|branch\s+-D)\b", r">\s*/dev/sd", r"\bmv\s+.*\s/dev/null\b",
    # disks, boot and power
    _CMD + r"format(?:\.com)?\s+[a-z]:", r"\bformat-volume\b", r"\bmkfs", r"\bdiskpart\b", r"\bfdisk\b", r"\bparted\b", r"\bdd\s+.*\bof=", r"\bwipefs\b",
    r"\binitialize-disk\b", r"\bshutdown\b", r"\b(?:stop|restart)-computer\b", r"\breboot\b", r"\bpoweroff\b",
    r"\bhalt\b", r"\bbcdedit\b", r"\bbootrec\b", r"\bvssadmin\b", r"\bcipher\s+/w",
    # system settings, accounts and permissions
    r"\breg(?:\.exe)?\s+(?:delete|add)\b", r"\b(?:remove|set|new)-itemproperty\b.*hk(?:lm|cu)", r"\bch(?:mod|own)\s+-R",
    r"\btakeown\b", r"\bicacls\b", r"\bnet\s+(?:user|localgroup)\b", r"\b(?:set|new|remove)-localuser\b",
    r"\bset-executionpolicy\b", r"\bsudo\b", r"\brunas\b", r"\bsu\s+-?\s*$",
    # running code fetched from the internet, fork bombs
    r"\b(?:invoke-expression|iex)\b", r"\b(?:curl|wget|iwr|irm|invoke-webrequest|invoke-restmethod)\b.*\|\s*(?:ba|z)?sh\b",
    r":\(\)\s*\{",
)]

# Commands made only of these just look things up, so they run without asking
READ_ONLY = {
    # Windows
    "ipconfig", "ping", "hostname", "whoami", "systeminfo", "tasklist", "findstr", "dir", "type", "echo",
    "nslookup", "netstat", "tracert", "getmac", "ver", "tree", "where", "date", "time", "vol", "driverquery",
    "sort-object", "where-object", "select-object", "measure-object", "group-object", "out-string",
    "write-output", "write-host", "resolve-dnsname", "test-connection", "test-path", "test-netconnection",
    # Linux and macOS
    "ls", "cat", "df", "du", "free", "uname", "uptime", "ip", "ifconfig", "lsblk", "lscpu", "lsusb", "lspci",
    "ps", "grep", "head", "tail", "wc", "sort", "uniq", "cut", "pwd", "which", "nproc", "sensors", "ss",
    "cal", "id", "groups", "file", "stat", "whereis", "hostnamectl", "timedatectl", "lsb_release", "dig",
}
READ_ONLY_PREFIXES = ("get-", "format-", "select-", "measure-", "test-", "resolve-")


def is_read_only(command: str) -> bool:
    """True when every part of a pipeline is a command that only reads information."""
    if re.search(r"[>`]|\$\(|\b(?:-exec|-delete|-ok)\b", command):
        return False  # redirection, sub-commands and find actions can change things
    for part in re.split(r"\|\||&&|[|;]", command):
        words = part.strip().split()
        if not words:
            continue
        name = words[0].lower().removesuffix(".exe")
        if name not in READ_ONLY and not name.startswith(READ_ONLY_PREFIXES):
            return False
    return True


# Programs the AI writes are checked for these before running, and you get an extra warning
DELETES_FILES = re.compile(r"os\.remove|os\.unlink|os\.rmdir|shutil\.rmtree|shutil\.move|\.unlink\(|\.rmdir\(|"
                           r"send2trash|Remove-Item|\brm\s+-|\bdel\s+/|fs\.(?:unlink|rm|rmdir)", re.I)

# Programs that need their own window (they wait for typing, draw graphics, or run forever)
INTERACTIVE = re.compile(r"\binput\(|\bpygame\b|\btkinter\b|\bturtle\b|\bcurses\b|\barcade\b|\bpyglet\b|\bkivy\b|"
                         r"while\s+True|app\.run\(|serve_forever|time\.sleep\(|\bflask\b|\bpynput\b|\bkeyboard\b|"
                         r"\bRead-Host\b|\bread\s+-p\b|\bmainloop\(")

LANGUAGES = [  # (words in the request, language name, file extension)
    (r"\b(html|website|web ?page|webpage|landing page)\b", "HTML, CSS and JavaScript in one HTML file", ".html"),
    (r"\b(javascript|node|js)\b", "JavaScript (Node.js)", ".js"),
    (r"\b(powershell)\b", "PowerShell", ".ps1"),
    (r"\b(bash|shell script)\b", "Bash", ".sh"),
    (r"\b(batch file|bat file)\b", "Windows batch", ".bat"),
]

PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow", "bs4": "beautifulsoup4", "yaml": "pyyaml",
             "sklearn": "scikit-learn", "dateutil": "python-dateutil", "win32api": "pywin32", "dotenv": "python-dotenv"}

last_command: str | None = None
last_script: Path | None = None
last_was_script = False

NEED_AI = "I need the local AI for that. Install Ollama and run: ollama pull " + config.CODER_MODEL


def is_dangerous(command: str) -> bool:
    return any(p.search(command) for p in DANGEROUS)


def _speakable(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def _last_line(output: str) -> str:
    """Python puts the actual error on the last line of a traceback."""
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    return lines[-1] if lines else "an unknown error"


def _first_line(output: str) -> str:
    """Shells put the actual error message first, and details after it."""
    lines = [l.strip() for l in output.splitlines() if l.strip() and not l.strip().startswith(("+", "At line"))]
    return lines[0] if lines else "an unknown error"


# ---------------------------------------------------------------------------
# Terminal commands
# ---------------------------------------------------------------------------
def run_shell(command: str) -> tuple[int, str]:
    shell = (["powershell", "-NoProfile", "-NonInteractive", "-Command", command] if system.WINDOWS
             else ["bash", "-lc", command])
    try:
        p = subprocess.run(shell, capture_output=True, text=True, errors="replace", timeout=RUN_TIMEOUT,
                           cwd=Path.home(), stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 1, f"The command was still running after {RUN_TIMEOUT} seconds, so I stopped it."
    except OSError as e:
        return 1, str(e)


def terminal(request: str) -> str:
    """Work out a command for a spoken request, show it, ask, run it and report back."""
    b = brain.get()
    if not b.ready:
        return NEED_AI
    dialog.status("Working out the command...")
    try:
        command, explanation = b.make_command(request)
    except Exception as e:
        dialog.status(f"(AI error: {e})")
        return "Sorry, I couldn't work out a command for that."
    return offer_command(command, explanation, request)


def offer_command(command: str, explanation: str = "", request: str | None = None, ask: bool = True) -> str:
    global last_command, last_was_script
    if not command:
        return "Sorry, I couldn't work out a command for that."
    dialog.show_command(command)
    if is_dangerous(command):
        return ("That command could delete files or change your system, so I won't run it. "
                "It's on screen if you want to check it and run it yourself.")
    if ask and (config.ALWAYS_ASK_BEFORE_RUNNING or not is_read_only(command)):
        if not dialog.confirm(f"{explanation} This one changes things on your computer. Should I run it?".strip()):
            return "Okay, I won't run it."
    code, output = run_shell(command)
    last_command, last_was_script = command, False
    dialog.show_output(output)
    if code != 0:
        return "That command didn't work. It said: " + _speakable(_first_line(output))
    if not output.strip():
        return "Done."
    if request and brain.get().ready:
        try:
            return brain.get().summarize(request, output)
        except Exception:
            pass
    return "Done. The output is on screen."


# ---------------------------------------------------------------------------
# Writing and running code
# ---------------------------------------------------------------------------
def _language(request: str) -> tuple[str, str]:
    for pattern, name, ext in LANGUAGES:
        if re.search(pattern, request, re.I):
            return name, ext
    return "Python", ".py"


def _language_for(path: Path) -> str:
    return next((name for _, name, ext in LANGUAGES if ext == path.suffix), "Python")


STOP_WORDS = {"a", "an", "the", "that", "which", "to", "for", "me", "my", "and", "of", "in", "with", "on", "it",
              "write", "create", "make", "build", "code", "generate", "program", "script", "python", "simple",
              "small", "quick", "little", "basic", "can", "you", "please", "some", "app", "will", "is", "from"}


def _new_path(request: str, ext: str) -> Path:
    words = [w for w in re.findall(r"[a-z0-9]+", request.lower()) if w not in STOP_WORDS][:4]
    stem = "_".join(words) or "jarvis_program"
    PROJECTS.mkdir(parents=True, exist_ok=True)
    path, n = PROJECTS / f"{stem}{ext}", 2
    while path.exists():
        path, n = PROJECTS / f"{stem}_{n}{ext}", n + 1
    return path


def open_in_editor(path: Path) -> None:
    code = shutil.which("code")
    if code:
        system._spawn([code, str(path)])
    elif system.WINDOWS:
        system._spawn(["notepad.exe", str(path)])
    else:
        system.open_path(str(path))


def _spoken_name(path: Path) -> str:
    return path.stem.replace("_", " ")


def write_code(request: str) -> str:
    global last_script, last_was_script
    b = brain.get()
    if not b.ready:
        return NEED_AI
    language, ext = _language(request)
    dialog.say("On it. Writing code takes a minute or two on this computer, so watch it appear on screen.", wait=False)
    try:
        code = b.write_code(request, language, dialog.stream_code)
    except Exception as e:
        dialog.status(f"\n(AI error: {e})")
        return "Sorry, something went wrong while writing the code."
    print(flush=True)
    if not code.strip():
        return "Sorry, I couldn't write that one."
    path = _new_path(request, ext)
    path.write_text(code, encoding="utf-8")
    last_script, last_was_script = path, True
    dialog.status(f"Saved to {path}")
    open_in_editor(path)
    return _offer_run(path, f"I've written {_spoken_name(path)} and opened it for you.")


def edit_code(instruction: str) -> str:
    global last_was_script
    if not last_script or not last_script.exists():
        return "There's no program to change yet. Ask me to write one first."
    b = brain.get()
    if not b.ready:
        return NEED_AI
    dialog.say("Updating the code.", wait=False)
    try:
        code = b.edit_code(last_script.read_text(encoding="utf-8"), _language_for(last_script), instruction,
                           dialog.stream_code)
    except Exception as e:
        dialog.status(f"\n(AI error: {e})")
        return "Sorry, something went wrong while changing the code."
    print(flush=True)
    if not code.strip():
        return "Sorry, I couldn't make that change."
    last_script.write_text(code, encoding="utf-8")
    last_was_script = True
    return _offer_run(last_script, "I've updated the code.")


def _offer_run(path: Path, message: str) -> str:
    if path.suffix == ".html":
        webbrowser.open(path.as_uri())
        return message + " It's open in your browser too."
    code = path.read_text(encoding="utf-8", errors="replace")
    if DELETES_FILES.search(code):
        question = (message + " Warning: this program deletes or moves files. Check the code on screen first. "
                    "Do you still want me to run it?")
    elif config.ALWAYS_ASK_BEFORE_RUNNING:
        question = message + " Want me to run it?"
    else:
        dialog.say(message + " Running it now.", wait=False)
        return run_script(path, checked=True)
    if dialog.confirm(question):
        return run_script(path, checked=True)
    return "Okay. Say run it whenever you're ready."


def _interpreter(path: Path) -> list[str] | None:
    return {
        ".py": [sys.executable, str(path)],
        ".js": ["node", str(path)] if shutil.which("node") else None,
        ".ps1": ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
        ".sh": ["bash", str(path)],
        ".bat": ["cmd", "/c", str(path)],
    }.get(path.suffix)


def open_in_terminal(cmd: list[str], cwd: Path) -> bool:
    """Run a program in its own terminal window, which stays open afterwards."""
    if system.WINDOWS:
        try:  # "call" first, so cmd.exe doesn't mangle the quotes around paths
            subprocess.Popen(["cmd", "/k", "call", *cmd], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True
        except OSError:
            return False
    script = shlex.join(cmd) + '; echo; read -p "Press Enter to close..."'
    for term, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"), ("konsole", "-e"),
                       ("xfce4-terminal", "-x"), ("kitty", ""), ("alacritty", "-e"), ("xterm", "-e")):
        if shutil.which(term):
            args = [term] + ([flag] if flag else []) + ["bash", "-c", script]
            return system._spawn(args)
    return False


def run_script(path: Path | None = None, checked: bool = False) -> str:
    global last_script, last_was_script
    path = path or last_script
    if not path or not path.exists():
        return "There's no program to run yet. Ask me to write one first."
    last_script, last_was_script = path, True
    if path.suffix == ".html":
        webbrowser.open(path.as_uri())
        return "It's open in your browser."
    cmd = _interpreter(path)
    if cmd is None:
        return f"I don't know how to run {path.suffix} files on this computer."
    code = path.read_text(encoding="utf-8", errors="replace")
    if not checked and DELETES_FILES.search(code) and not dialog.confirm(
            "Warning: this program deletes or moves files. Do you still want me to run it?"):
        return "Okay, I won't run it."
    if INTERACTIVE.search(code):
        return ("It's running in a new window." if open_in_terminal(cmd, path.parent)
                else "I couldn't open a terminal window to run it.")

    for attempt in range(3):
        dialog.status(f"Running {path.name}...")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=RUN_TIMEOUT,
                               cwd=path.parent, stdin=subprocess.DEVNULL)
            rc, output = p.returncode, p.stdout + p.stderr
        except subprocess.TimeoutExpired:
            return f"It was still running after {RUN_TIMEOUT} seconds, so I stopped it."
        dialog.show_output(output)
        if rc == 0:
            return "It ran successfully." + (" The output is on screen." if output.strip() else "")

        missing = re.search(r"No module named '([\w]+)", output)
        if missing and path.suffix == ".py":
            package = PIP_NAMES.get(missing.group(1), missing.group(1))
            if not dialog.confirm(f"It needs the {package} package. Should I install it?"):
                return "Okay, I won't install it."
            dialog.status(f"Installing {package}...")
            subprocess.run([sys.executable, "-m", "pip", "install", package], capture_output=True)
            continue

        if attempt == 2 or not brain.get().ready:
            break
        dialog.say(f"It crashed with {_speakable(_last_line(output), 90)}. Fixing it.", wait=False)
        try:
            code = brain.get().fix_code(code, _language_for(path), output, dialog.stream_code)
        except Exception as e:
            dialog.status(f"\n(AI error: {e})")
            break
        print(flush=True)
        path.write_text(code, encoding="utf-8")
        if DELETES_FILES.search(code) and not dialog.confirm(
                "Warning: the fixed version deletes or moves files. Check it on screen. Run it anyway?"):
            return "Okay, I won't run it."
        time.sleep(0.2)
    return "I couldn't get it working. The latest error is on screen."


def save_last(name: str) -> dict | None:
    """What 'save that as ...' should remember: the last command or program."""
    if last_was_script and last_script:
        return {"script": str(last_script)}
    if last_command:
        return {"shell": last_command}
    return None


def open_projects() -> str:
    PROJECTS.mkdir(parents=True, exist_ok=True)
    system.open_path(str(PROJECTS))
    return "Here's your projects folder."

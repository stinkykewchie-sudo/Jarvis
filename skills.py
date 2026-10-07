"""Built-in commands. Everything here runs instantly and offline (except the optional weather)."""

import ast
import json
import operator
import random
import re
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus
from urllib.request import urlopen

import browser
import coder
import config
import dialog
import memory
import system

NOTES_FILE = Path(__file__).with_name("jarvis_notes.txt")

# Set by jarvis.py so timers can speak when they finish
announce: Callable[[str], None] = print


# ---------------------------------------------------------------------------
# Durations: "10 minutes and 30 seconds", "half an hour", "two hours"
# ---------------------------------------------------------------------------
NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90,
}
UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
DURATION = re.compile(
    r"\b(\d+(?:\.\d+)?|half an?|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")\s*"
    r"(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b"
)


def parse_duration(text: str) -> tuple[float, str] | None:
    """'10 minutes and 30 seconds for pasta' -> (630.0, 'pasta')."""
    total, last_end = 0.0, None
    for m in DURATION.finditer(text):
        amount, unit = m.group(1), m.group(2)
        value = 0.5 if amount.startswith("half") else float(NUMBER_WORDS.get(amount, amount))
        total += value * UNIT_SECONDS[unit[0]]
        last_end = m.end()
    if not total:
        return None
    label = ""
    after = re.search(r"\b(?:for|to|about|that)\s+(.+)$", text[last_end:])
    before = re.search(r"\b(?:remind me to|timer for)\s+(.+?)\s+(?:in|for)\s+[\w.]+\s+(?:hours?|minutes?|seconds?)", text)
    if after:
        label = after.group(1)
    elif before:
        label = before.group(1)
    return total, label.strip(" .")


def describe_seconds(seconds: float) -> str:
    seconds = int(round(seconds))
    parts = []
    for name, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        n, seconds = divmod(seconds, size)
        if n:
            parts.append(f"{n} {name}{'s' if n != 1 else ''}")
    return " and ".join(parts) or "0 seconds"


# ---------------------------------------------------------------------------
# Apps and websites
# ---------------------------------------------------------------------------
WEBSITES = {
    "youtube": "youtube.com", "google": "google.com", "gmail": "mail.google.com", "netflix": "netflix.com",
    "reddit": "reddit.com", "github": "github.com", "twitter": "x.com", "x": "x.com",
    "facebook": "facebook.com", "instagram": "instagram.com", "amazon": "amazon.com",
    "wikipedia": "wikipedia.org", "twitch": "twitch.tv", "tiktok": "tiktok.com", "linkedin": "linkedin.com",
    "google maps": "maps.google.com", "maps": "maps.google.com", "google drive": "drive.google.com",
    "spotify": "open.spotify.com", "discord": "discord.com/app", "whatsapp": "web.whatsapp.com",
    "outlook": "outlook.live.com", "pinterest": "pinterest.com", "ebay": "ebay.com", "hulu": "hulu.com",
    "disney plus": "disneyplus.com", "chatgpt": "chatgpt.com", "roblox": "roblox.com",
}
SITE_LIKE = re.compile(r"\.(com|org|net|io|gov|edu|tv|co|uk|dev|ai|app|me)\b")


def resolve_site(name: str) -> str | None:
    """A URL for a saved site, a well-known site, or a spoken web address. None if it isn't a website."""
    name = re.sub(r"^(the|my)\s+", "", name.strip(" ."))
    name = re.sub(r"\s+(website|site|page|web page|homepage)$", "", name)
    return memory.site(name) or memory.to_url(name) or (("https://" + WEBSITES[name]) if name in WEBSITES else None)


def open_thing(name: str) -> str:
    name = re.sub(r"^(the|my|up)\s+", "", name.strip(" ."))
    saved = memory.site(re.sub(r"\s+(website|site|page|web page|homepage)$", "", name))
    if saved:
        webbrowser.open(saved)
        return f"Opening {name}."
    name = re.sub(r"\s+(app|application|program|website|site|page)$", "", name)
    url = memory.to_url(name) if SITE_LIKE.search(re.sub(r"\s+dot\s+", ".", name)) else None
    if url:
        webbrowser.open(url)
        return f"Opening {name}."
    opened = system.open_app(name)
    if opened:
        return f"Opening {opened}."
    if name in WEBSITES:
        webbrowser.open("https://" + WEBSITES[name])
        return f"Opening {name} in your browser."
    return f"I couldn't find anything called {name} on this computer."


def close_app(name: str) -> str:
    name = re.sub(r"^(the|my)\s+", "", name.strip(" ."))
    name = re.sub(r"\s+(app|application|program|window)$", "", name)
    if system.close_app(name):
        return f"Closing {name}."
    return f"{name.capitalize()} doesn't seem to be running."


# ---------------------------------------------------------------------------
# Timers and notes
# ---------------------------------------------------------------------------
timers: list[threading.Timer] = []


def set_timer(text: str) -> str:
    parsed = parse_duration(text)
    if not parsed:
        return "How long should the timer be? For example, say set a timer for 10 minutes."
    seconds, label = parsed

    def ring() -> None:
        announce(f"Time's up{': ' + label if label else ''}." + (" " if label else "") + "Your timer is done.")

    t = threading.Timer(seconds, ring)
    t.daemon = True
    t.start()
    timers.append(t)
    return f"Timer set for {describe_seconds(seconds)}{' for ' + label if label else ''}."


def cancel_timers() -> str:
    active = [t for t in timers if t.is_alive()]
    for t in active:
        t.cancel()
    timers.clear()
    return f"Cancelled {len(active)} timer{'s' if len(active) != 1 else ''}." if active else "There are no timers running."


def save_note(text: str) -> str:
    if not text:
        return "What should the note say?"
    with NOTES_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {text}\n")
    return "Got it, I've written that down."


def read_notes() -> str:
    lines = NOTES_FILE.read_text(encoding="utf-8").splitlines() if NOTES_FILE.exists() else []
    if not lines:
        return "You don't have any notes yet."
    notes = [re.sub(r"^\[.*?\]\s*", "", line) for line in lines[-10:]]
    return f"You have {len(lines)} note{'s' if len(lines) != 1 else ''}. " + ". ".join(notes) + "."


def clear_notes() -> str:
    NOTES_FILE.write_text("", encoding="utf-8")
    return "All your notes are cleared."


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------
def volume(text: str) -> str:
    target = re.search(r"\b(?:to|at)\s+(\d{1,3})\s*(?:%|percent)?", text)
    if target:
        level = min(int(target.group(1)), 100)
        return system.volume_set(level) or f"Volume set to {level} percent."
    if re.search(r"\b(max|maximum|full|all the way up)\b", text):
        return system.volume_set(100) or "Volume at maximum."
    amount = 30 if re.search(r"\b(a lot|way|much|loads)\b", text) else 6 if re.search(r"\b(little|bit|slightly)\b", text) else 12
    if re.search(r"\b(down|lower|quieter|softer|decrease|reduce)\b", text):
        return system.volume_change(-amount) or "Turning it down."
    return system.volume_change(amount) or "Turning it up."


# ---------------------------------------------------------------------------
# Weather (optional, uses the free Open-Meteo service - no account needed)
# ---------------------------------------------------------------------------
WEATHER_CODES = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "rain showers", 82: "heavy rain showers", 85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=8) as r:
        return json.load(r)


def weather(text: str) -> str:
    if not config.WEATHER_ONLINE:
        return "Weather is switched off, because I'm set to stay fully offline."
    m = re.search(r"\b(?:in|for|at)\s+([a-z][a-z .'-]+?)(?:\s+(?:today|tomorrow|right now|now|this week))?$", text)
    city = m.group(1).strip() if m else config.HOME_CITY
    if not city:
        return "Which city? You can also set your home city in the config file."
    try:
        geo = _get_json(f"https://geocoding-api.open-meteo.com/v1/search?count=1&name={quote_plus(city)}")
        if not geo.get("results"):
            return f"I couldn't find a place called {city}."
        place = geo["results"][0]
        unit = "fahrenheit" if config.TEMPERATURE_UNIT.lower().startswith("f") else "celsius"
        wx = _get_json(
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={place['latitude']}&longitude={place['longitude']}"
            "&current=temperature_2m,weather_code,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            f"&temperature_unit={unit}&wind_speed_unit={'mph' if unit == 'fahrenheit' else 'kmh'}"
            "&forecast_days=2&timezone=auto"
        )
    except OSError:
        return "I can't reach the weather service right now. Check your internet connection."
    d = wx["daily"]
    if "tomorrow" in text:
        return (f"Tomorrow in {place['name']}: {WEATHER_CODES.get(d['weather_code'][1], 'mixed weather')}, "
                f"a high of {round(d['temperature_2m_max'][1])} and a low of {round(d['temperature_2m_min'][1])} degrees, "
                f"with a {d['precipitation_probability_max'][1]} percent chance of rain.")
    c = wx["current"]
    return (f"It's {round(c['temperature_2m'])} degrees and {WEATHER_CODES.get(c['weather_code'], 'mixed weather')} "
            f"in {place['name']}. Today's high is {round(d['temperature_2m_max'][0])} with a low of "
            f"{round(d['temperature_2m_min'][0])}, and a {d['precipitation_probability_max'][0]} percent chance of rain.")


# ---------------------------------------------------------------------------
# Maths: "what is 15 times 23", "what's 20 percent of 85"
# ---------------------------------------------------------------------------
MATH_WORDS = [
    (r"\bto the power of\b", "**"), (r"\bsquared\b", "**2"), (r"\bcubed\b", "**3"),
    (r"\bmultiplied by\b|\btimes\b|(?<=\d)\s*x\s*(?=\d)", "*"), (r"\bdivided by\b|\bover\b", "/"),
    (r"\bplus\b|\band\b", "+"), (r"\bminus\b|\btake away\b", "-"), (r"\bpercent of\b|% of\b", "/100*"),
]
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 100:
            raise ValueError("exponent too large")
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported")


def calculate(expr: str) -> str | None:
    e = expr.replace(",", "")
    m = re.search(r"(?:the )?square root of\s*(\d+(?:\.\d+)?)", e)
    if m:
        e = e.replace(m.group(0), f"({m.group(1)})**0.5")
    for pattern, symbol in MATH_WORDS:
        e = re.sub(pattern, symbol, e)
    e = re.sub(r"(?<=\d)\s*%", "/100", e)
    if not re.fullmatch(r"[\d\s.+\-*/()]+", e) or not re.search(r"\d", e):
        return None
    try:
        value = _eval(ast.parse(e.strip(), mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError, OverflowError):
        return None
    value = round(value, 4)
    return f"That's {int(value) if value == int(value) else value}."


# ---------------------------------------------------------------------------
# Small talk (instant, works without the AI)
# ---------------------------------------------------------------------------
JOKES = [
    "I told my computer I needed a break. It said, no problem, it'll go to sleep.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a UDP joke, but you might not get it.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "Parallel lines have so much in common. It's a shame they'll never meet.",
    "I'm reading a book about anti-gravity. It's impossible to put down.",
    "Why don't skeletons fight each other? They don't have the guts.",
    "There are ten kinds of people in the world. Those who understand binary, and those who don't.",
]

HELP = ("I can open apps and websites, open and close browser tabs, control music and volume, set timers, take notes, "
        "check the weather, do maths, and lock the computer. I can also write and run code, answer programming "
        "questions, and run terminal commands for you. You can teach me new commands, like: when I say study time, "
        "open my school website. Say goodbye to shut me down.")

# ---------------------------------------------------------------------------
# Coding, terminal and teaching phrases
# ---------------------------------------------------------------------------
CODE_NOUN = r"(?:script|program|code|function|app|application|game|bot|website|web ?page|webpage|tool|class|calculator|cli)"
WRITE_CODE = re.compile(
    rf"^(?:write|create|make|build|code|generate|program|develop)(?: me| us)?(?: a| an| some| another| the following)\b.*\b{CODE_NOUN}\b"
    r"|^(?:write|generate) (?:some |me some )?(?:python |javascript |html |bash |powershell )?code\b"
    r"|^(?:write|create|make|build|code)\b.*\bin (?:python|javascript|html|bash|powershell)$")
EDIT_CODE = re.compile(
    rf"^(?:change|update|modify|edit|fix|improve|rewrite|refactor|add|remove|make)\b.*\b(?:the|my|that|this) {CODE_NOUN}\b"
    r"|^(?:change|update|modify|edit|fix|improve|rewrite|refactor|clean up)\s+it\b")
LAST_PROGRAM = r"(?:it|that|the script|the program|the code|the game|the app|my script|my program|my code)"
TERMINAL = re.compile(
    r"^(?:use the terminal to|use (?:powershell|bash|the command line|command prompt|a command) to|in the terminal|"
    r"terminal|run a (?:terminal |shell )?command (?:to|that)|execute a command (?:to|that))\s+(.+)$"
    r"|^(.+?) (?:in|using|with|from) (?:the )?(?:terminal|command line|powershell|bash|command prompt)$")
TEACH_COMMAND = re.compile(
    r"^when i say (.+?) (?:you should |please |just |then )?((?:open|go to|search|play|run|close|turn|set|take|lock|"
    r"tell|read|start|launch|show|use|write|new tab|pause|mute|google|look up)\b.*)$")
TEACH_SITE = re.compile(
    r"^(?:remember|save|learn|note) (?:that )?(?:my |the )?(.+?) (?:website |site |page |link |url |address )?is (?:at )?(.+)$")


def run_custom(action, depth: int) -> str | None:
    if isinstance(action, str):
        return handle(action, depth + 1) if depth < 3 else None
    if "shell" in action:
        return coder.offer_command(action["shell"], ask=False)
    if "script" in action:
        return coder.run_script(Path(action["script"]))
    return None


def browser_commands(t: str) -> str | None:
    m = (re.fullmatch(r"(?:open |make |create |start )?(?:a )?new tab(?: (?:to|for|with|on|at|and go to|and open) (.+))?", t)
         or re.fullmatch(r"(?:open|go to|load|pull up) (.+?) in (?:a )?new tab", t))
    if m:
        target = m.group(1)
        if not target:
            return browser.new_tab()
        return browser.new_tab(resolve_site(target) or "https://www.google.com/search?q=" + quote_plus(target))
    if re.fullmatch(r"close (?:this |the |current |that |my )?(?:browser )?tab", t):
        return browser.close_tabs(1)
    if re.fullmatch(r"close (?:all |all of |all the |all my |every )(?:the |my )?(?:browser )?tabs|close (?:the |my )?browser window", t):
        if dialog.confirm("That closes every tab in the browser window. Are you sure?"):
            return browser.close_window()
        return "Okay, I'll leave them open."
    m = re.fullmatch(r"close (?:the )?(?:last )?(\d+|" + "|".join(NUMBER_WORDS) + r") tabs", t)
    if m:
        n = m.group(1)
        return browser.close_tabs(int(n) if n.isdigit() else NUMBER_WORDS[n])
    m = re.fullmatch(r"close (?:the |my )?(.+?) tab", t)
    if m:
        return browser.close_tab_named(m.group(1))
    if re.search(r"\b(reopen|restore|bring back|undo close)(?: the| my)?(?: last| closed| last closed)? tab\b"
                 r"|\bopen (?:the |my )?(?:last )?closed tab\b", t):
        return browser.reopen_tab()
    if re.fullmatch(r"(?:next|switch to the next|go to the next) tab", t):
        return browser.next_tab()
    if re.fullmatch(r"(?:previous|last|switch to the previous|go to the previous) tab", t):
        return browser.previous_tab()
    m = re.fullmatch(r"(?:switch|go|change|jump) (?:back )?to (?:the |my )?(.+?) tab", t)
    if m:
        return browser.switch_to_tab(m.group(1))
    if re.fullmatch(r"(?:refresh|reload)(?: the| this)?(?: page| tab| website)?", t):
        return browser.refresh()
    if re.fullmatch(r"go back(?: a page| one page)?|(?:go to the )?previous page", t):
        return browser.back()
    if re.fullmatch(r"go forward(?: a page| one page)?", t):
        return browser.forward()
    return None


# ---------------------------------------------------------------------------
# The command router
# ---------------------------------------------------------------------------
FILLER = re.compile(
    r"^(?:(?:please|can you|could you|would you|will you|i want you to|i'd like you to|"
    r"go ahead and|i need you to|kindly|just)\s+)+|\s+(?:please|for me|now|thanks|thank you)$"
)


def normalise(text: str) -> str:
    t = text.lower().replace("’", "'")
    t = re.sub(r"[!?,;\"]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" .")
    for _ in range(2):
        t = FILLER.sub("", t).strip(" .")
    return t


def handle(text: str, depth: int = 0) -> str | None:
    """Run a built-in command. Returns what Jarvis should say ("" = nothing), or None if no command matched."""
    t = normalise(text)
    if not t:
        return None

    # --- commands you've taught me ---
    action = memory.command_for(t)
    if action is not None:
        return run_custom(action, depth)

    # --- coding (checked early, so "write a weather app" isn't a weather question) ---
    if WRITE_CODE.search(t):
        return coder.write_code(text.strip())
    if coder.last_script and EDIT_CODE.search(t):
        return coder.edit_code(text.strip())
    if re.fullmatch(rf"(?:run|start|execute|test|try|launch) {LAST_PROGRAM}(?: again)?", t):
        return coder.run_script()
    if re.fullmatch(r"(?:open|show me) (?:the|my|that) (?:script|code|program)", t) and coder.last_script:
        coder.open_in_editor(coder.last_script)
        return "Here's the code."
    if re.search(r"\b(?:open|show)(?: me)? (?:my )?(?:jarvis )?(?:projects|coding projects|code)(?: folder)?$", t):
        return coder.open_projects()
    m = TERMINAL.search(t)
    if m:
        return coder.terminal(text.strip())

    # --- teaching ---
    m = TEACH_COMMAND.fullmatch(t)
    if m:
        memory.teach(m.group(1), m.group(2))
        return f"Got it. When you say {m.group(1)}, I'll {m.group(2)}."
    m = re.fullmatch(r"(?:save|remember|call) (?:that|this|it)(?: command| script| program)? as (.+)", t)
    if m:
        saved = coder.save_last(m.group(1))
        if not saved:
            return "There's nothing to save yet. Run a command or a program first."
        memory.teach(m.group(1), saved)
        return f"Saved. Just say {m.group(1)} to run it again."
    m = TEACH_SITE.fullmatch(t)
    if m and memory.to_url(m.group(2)):
        name = re.sub(r"\s+(website|site|page)$", "", m.group(1))
        memory.remember_site(name, memory.to_url(m.group(2)))
        return f"Got it. Say open my {name} website, or open {name} in a new tab."
    m = re.fullmatch(r"forget (?:about )?(?:the |my )?(?:command |site |website )?(.+)", t)
    if m:
        return "Forgotten." if memory.forget(m.group(1)) else f"I don't have anything saved called {m.group(1)}."
    if re.search(r"\b(what have you learned|what have i taught you|what do you remember|list (?:my )?(?:custom |saved )?commands"
                 r"|what are my (?:custom |saved )?commands|show (?:me )?my commands|my saved (?:sites|websites))\b", t):
        return memory.describe()

    # --- browser tabs ---
    reply = browser_commands(t)
    if reply is not None:
        return reply

    # --- small talk ---
    if re.fullmatch(r"(hi|hello|hey|yo|good (morning|afternoon|evening)|hello there)( jarvis)?", t):
        hour = datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        return f"Good {part}{', ' + config.YOUR_NAME if config.YOUR_NAME else ''}. How can I help?"
    if re.fullmatch(r"(thanks|thank you|thank you very much|cheers|nice|great|perfect|awesome)( jarvis)?", t):
        return random.choice(["You're welcome.", "Any time.", "Happy to help."])
    if re.search(r"\b(what can you do|what are your (commands|abilities)|help me out|^help$|list (your )?commands)\b", t):
        return HELP
    if re.search(r"\b(who are you|what('s| is) your name|introduce yourself)\b", t):
        return "I'm Jarvis, your personal assistant. I run entirely on this computer."
    if re.search(r"\bhow are you\b", t):
        return "All systems running smoothly. Thanks for asking."
    if re.search(r"\b(tell me )?(a |another )?joke\b", t):
        return random.choice(JOKES)

    # --- time and date ---
    if re.search(r"\b(what time|the time|time is it|current time)\b", t):
        return datetime.now().strftime("It's %I:%M %p.").replace(" 0", " ")
    if re.search(r"\b(what day|what's the date|what is the date|today's date|what date|date today)\b", t):
        return datetime.now().strftime("Today is %A, %B %d, %Y.").replace(" 0", " ")

    # --- timers ---
    if re.search(r"\b(cancel|stop|clear|delete) (the |my |all )*(timers?|reminders?)\b", t):
        return cancel_timers()
    if re.search(r"\b(timer|remind me|countdown|alarm in|wake me (up )?in)\b", t):
        return set_timer(t)

    # --- notes ---
    if re.search(r"\b(read|show|list|what are|what's in|what is in|check)( me)? (my |the )?notes\b", t):
        return read_notes()
    if re.search(r"\b(clear|delete|erase|wipe)( all)? (of )?(my |the )?notes\b", t):
        return clear_notes()
    m = re.search(r"^(?:take|make|write|add) a note(?: that| saying| to)?\s*:?\s*(.*)$|"
                  r"^(?:note|write down|jot down|remember)(?: that| to)?\s+(.+)$|"
                  r"^add (.+?) to (?:my |the )?(?:notes|to-?do list|list|shopping list)$", t)
    if m:
        return save_note(next(g for g in m.groups() if g is not None).strip())

    # --- weather ---
    if re.search(r"\b(weather|temperature outside|forecast|is it (going to )?(rain|snow)|will it (rain|snow))\b", t):
        return weather(t)

    # --- media and volume ---
    if re.search(r"\b(volume|louder|quieter|softer|turn it (up|down)|turn (the sound|the music) (up|down))\b", t):
        return volume(t)
    if re.fullmatch(r"(un)?mute( the)?( sound| audio| volume| computer| music)?", t):
        return system.mute_toggle() or ""
    if re.fullmatch(r"(next|skip)( this)?( song| track| video| one)?|skip( it| this)?", t):
        return system.media("next") or ""
    if re.fullmatch(r"(previous|last|go back( to the)?( previous| last)?)( song| track| video)|play the (previous|last) (song|track)", t):
        return system.media("previous") or ""
    if re.fullmatch(r"(pause|resume|stop|unpause|play|continue|keep playing)( the| my)?( music| song| video| playback| it| spotify)?|play (some )?music", t):
        return system.media("play_pause") or ""

    # --- YouTube and search ---
    m = re.fullmatch(r"(?:search youtube for|search on youtube for|youtube search(?: for)?|find (.+?) on youtube)\s*(.*)", t)
    if m:
        q = m.group(1) or m.group(2)
        webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(q))
        return f"Searching YouTube for {q}."
    m = re.fullmatch(r"play (.+?)(?: on youtube| from youtube| video)?", t)
    if m:
        webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(m.group(1)))
        return f"Here's {m.group(1)} on YouTube."
    m = re.fullmatch(r"(?:search(?: the web| google| online| the internet)?(?: for)?|google|look up|look for) (.+)", t)
    if m:
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(m.group(1)))
        return f"Here are the results for {m.group(1)}."

    # --- system ---
    if re.search(r"\block (the |my )?(computer|pc|screen|laptop|workstation)\b", t):
        return "Locking the computer." if system.lock_screen() else "I couldn't lock the screen on this system."
    if re.search(r"\b(take a |grab a )?screen ?shot\b", t):
        return system.screenshot()
    if re.search(r"\b(battery|charge level|how much charge)\b", t):
        return system.battery()

    # --- open / close ---
    m = re.fullmatch(r"(?:close|quit|exit|kill|shut) (?:down )?(.+)", t)
    if m and not re.fullmatch(r"(down|yourself|jarvis)", m.group(1)):
        return close_app(m.group(1))
    m = re.fullmatch(r"(?:open|launch|start|go to|load|bring up|pull up|show me|open up) (.+)", t)
    if m:
        return open_thing(m.group(1))
    m = re.fullmatch(r"(?:run|execute) (.+)", t)
    if m:  # "run spotify" opens an app; anything else is treated as a terminal request
        opened = system.open_app(m.group(1))
        return f"Opening {opened}." if opened else coder.terminal(text.strip())

    # --- maths ---
    m = re.fullmatch(r"(?:what(?:'s| is)|calculate|how much is|compute|work out)\s+(.+)", t)
    if m:
        answer = calculate(m.group(1))
        if answer:
            return answer

    return None

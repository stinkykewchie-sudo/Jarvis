"""Browser tab control: new tabs, closing tabs (including by name), switching and reopening.

Works with Chrome, Edge, Firefox, Brave, Opera and Vivaldi by pressing their standard keyboard
shortcuts. Before every keypress Jarvis checks that a browser window is in front, so a shortcut
like Ctrl+W can never land in another app. On Linux this needs xdotool and an X11 session.
"""

import time
import webbrowser

import system

MAX_TABS = 50  # how many tabs to look through when finding a tab by name
NO_BROWSER = "I couldn't find an open browser window."


def _browser_in_front() -> bool:
    win = system.active_window()
    return bool(win) and system.is_browser(win[2])


def focus_browser() -> bool:
    """Bring a browser window to the front if one isn't already. True if a browser is now in front."""
    if _browser_in_front():
        return True
    wid = system.find_browser_window()
    if wid is None:
        return False
    system.activate_window(wid)
    time.sleep(0.3)
    return _browser_in_front()


def _press(*keys: str) -> bool:
    """Press a shortcut, but only if a browser is the window in front."""
    if not _browser_in_front():
        return False
    system.hotkey(*keys)
    time.sleep(0.2)
    return True


def _title() -> str:
    win = system.active_window()
    return win[1] if win else ""


def new_tab(url: str | None = None) -> str:
    if url:
        webbrowser.open_new_tab(url)
        return "Opened it in a new tab."
    if focus_browser() and _press("ctrl", "t"):
        return "New tab open."
    webbrowser.open_new_tab("https://www.google.com")
    return "Opened your browser."


def close_tabs(count: int = 1) -> str:
    if not focus_browser():
        return NO_BROWSER
    closed = 0
    for _ in range(max(1, min(count, 20))):
        if not _press("ctrl", "w"):
            break
        closed += 1
    if closed == 0:
        return NO_BROWSER
    return "Closed the tab." if closed == 1 else f"Closed {closed} tabs."


def close_window() -> str:
    if not focus_browser():
        return NO_BROWSER
    return "Closed all the tabs in that window." if _press("ctrl", "shift", "w") else NO_BROWSER


def _find_tab(name: str) -> bool:
    """Step through tabs until the active one's title mentions `name`. Leaves that tab selected."""
    wanted = system.squash(name)
    first = None
    for i in range(MAX_TABS):
        title = _title()
        if wanted and wanted in system.squash(title):
            return True
        if i > 0 and title == first:
            return False  # we've gone all the way round
        first = first if i > 0 else title
        if not _press("ctrl", "pagedown"):
            return False
        time.sleep(0.1)
    return False


def close_tab_named(name: str) -> str:
    if not focus_browser():
        return NO_BROWSER
    if _find_tab(name) and _press("ctrl", "w"):
        return f"Closed the {name} tab."
    return f"I couldn't find a tab with {name} in its title."


def switch_to_tab(name: str) -> str:
    if not focus_browser():
        return NO_BROWSER
    return f"Here's {name}." if _find_tab(name) else f"I couldn't find a tab with {name} in its title."


def next_tab() -> str:
    return "" if focus_browser() and _press("ctrl", "pagedown") else NO_BROWSER


def previous_tab() -> str:
    return "" if focus_browser() and _press("ctrl", "pageup") else NO_BROWSER


def reopen_tab() -> str:
    return "Reopened your last closed tab." if focus_browser() and _press("ctrl", "shift", "t") else NO_BROWSER


def refresh() -> str:
    return "" if focus_browser() and _press("f5") else NO_BROWSER


def back() -> str:
    return "" if focus_browser() and _press("alt", "left") else NO_BROWSER


def forward() -> str:
    return "" if focus_browser() and _press("alt", "right") else NO_BROWSER

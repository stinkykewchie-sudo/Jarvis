"""Jarvis desktop window: a chat-style GUI front-end for the same assistant, with an Iron Man / J.A.R.V.I.S. look.

It reuses everything else unchanged - it registers itself as a `dialog` sink, so every spoken line, question,
command and piece of code flows into the window, and runs jarvis.respond() on a worker thread so the window
never freezes while the model thinks. An optional system-tray icon (pystray) keeps it running in the background.

Run:  pythonw gui.py           (Windows, no console)
      python gui.py --listen   (start listening for "Jarvis" straight away)
      python gui.py --tray      (start hidden in the system tray)
"""

import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext

import brain
import config
import dialog
import jarvis
import skills
from mouth import Mouth

# --- Iron Man / arc-reactor palette ---
BG = "#060a10"          # deep HUD black-blue
PANEL = "#0c131d"       # slightly lighter panel
PANEL2 = "#0f1826"      # input / raised
EDGE = "#163043"        # hairline cyan-grey border
CYAN = "#48d6ff"        # arc-reactor cyan
CYAN_DIM = "#2a6f8a"
GOLD = "#f6b53c"        # repulsor gold
FG = "#cfe9f6"          # main text
MUTED = "#5f8198"       # dim labels
YOU = GOLD
JARVIS = CYAN
SYS = "#5f8198"
CODE_FG = "#8ef0c6"


class JarvisGUI:
    def __init__(self, start_hidden: bool = False, auto_listen: bool = False) -> None:
        self.inputs: queue.Queue = queue.Queue()
        self.busy = False
        self.listening = False
        self.pending_question = False
        self._answer: str | None = None
        self._answered = threading.Event()
        self._stop = False
        self._pulse = 0

        self._build_window()
        self.mouth = Mouth()
        dialog.setup(self.mouth, ears=None)
        dialog.set_sink(self)
        jarvis.setup_log()
        jarvis.log.info("--- Jarvis started (GUI mode) ---")

        threading.Thread(target=self._worker, daemon=True).start()
        self._try_tray()
        self._boot()
        if start_hidden and self.tray:
            self.root.withdraw()
        if auto_listen or getattr(config, "HANDS_FREE", False):
            self.root.after(600, self.toggle_listen)

    # ---- window -----------------------------------------------------------
    def _build_window(self) -> None:
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S.")
        self.root.geometry("760x640")
        self.root.minsize(480, 420)
        self.root.configure(bg=BG)
        try:
            self.root.iconphoto(True, tk.PhotoImage(file=str(_asset("jarvis.png"))))
        except Exception:
            pass

        # one outer frame that fills the window; grid weights make the transcript take all spare height,
        # so the layout stays correct even when maximized (this fixes the "only the bottom shows" bug).
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        root = tk.Frame(self.root, bg=BG)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)   # the transcript row grows

        # --- header: arc reactor + wordmark + status ---
        header = tk.Frame(root, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        header.columnconfigure(1, weight=1)

        self.reactor = tk.Canvas(header, width=34, height=34, bg=BG, highlightthickness=0)
        self.reactor.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        self._draw_reactor(CYAN_DIM)

        wordmark = tkfont.Font(family="Consolas", size=17, weight="bold")
        tk.Label(header, text="J A R V I S", bg=BG, fg=CYAN, font=wordmark).grid(row=0, column=1, sticky="w")
        tk.Label(header, text="Just A Rather Very Intelligent System", bg=BG, fg=MUTED,
                 font=tkfont.Font(family="Consolas", size=8)).grid(row=1, column=1, sticky="w")
        self.status_label = tk.Label(header, text="BOOTING", bg=BG, fg=GOLD,
                                     font=tkfont.Font(family="Consolas", size=9, weight="bold"))
        self.status_label.grid(row=0, column=2, rowspan=2, sticky="e")

        tk.Frame(root, bg=EDGE, height=1).grid(row=1, column=0, sticky="ew", padx=12)  # hairline under header

        # --- transcript ---
        body = tkfont.Font(family="Segoe UI", size=11)
        mono = tkfont.Font(family="Consolas", size=10)
        self.transcript = scrolledtext.ScrolledText(
            root, bg=PANEL, fg=FG, insertbackground=CYAN, relief="flat", wrap="word",
            font=body, padx=14, pady=12, state="disabled", borderwidth=0, highlightthickness=1,
            highlightbackground=EDGE, highlightcolor=EDGE)
        self.transcript.grid(row=2, column=0, sticky="nsew", padx=14, pady=10)
        self.transcript.tag_config("you", foreground=YOU,
                                   font=tkfont.Font(family="Segoe UI", size=11, weight="bold"))
        self.transcript.tag_config("jarvis", foreground=JARVIS)
        self.transcript.tag_config("sys", foreground=SYS, font=tkfont.Font(family="Consolas", size=9))
        self.transcript.tag_config("code", foreground=CODE_FG, font=mono)

        # --- input bar ---
        bar = tk.Frame(root, bg=BG)
        bar.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 14))
        bar.columnconfigure(1, weight=1)
        self.mic_btn = tk.Button(bar, text="◉  LISTEN", command=self.toggle_listen, bg=PANEL2, fg=CYAN,
                                 activebackground=CYAN, activeforeground=BG, relief="flat",
                                 font=tkfont.Font(family="Consolas", size=10, weight="bold"),
                                 width=11, cursor="hand2", borderwidth=0, padx=6, pady=6)
        self.mic_btn.grid(row=0, column=0, padx=(0, 8))
        self.entry = tk.Entry(bar, bg=PANEL2, fg=FG, insertbackground=CYAN, relief="flat", font=body,
                              highlightthickness=1, highlightbackground=EDGE, highlightcolor=CYAN)
        self.entry.grid(row=0, column=1, sticky="ew", ipady=7)
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.entry.focus_set()
        tk.Button(bar, text="SEND", command=self._submit, bg=GOLD, fg=BG, activebackground="#ffcf6b",
                  activeforeground=BG, relief="flat", font=tkfont.Font(family="Consolas", size=10, weight="bold"),
                  width=7, cursor="hand2", borderwidth=0, padx=6, pady=6).grid(row=0, column=2, padx=(8, 0))

        self.root.protocol("WM_DELETE_WINDOW", self._hide_or_quit)

    def _draw_reactor(self, glow: str) -> None:
        c = self.reactor
        c.delete("all")
        c.create_oval(2, 2, 32, 32, outline=EDGE, width=1)
        c.create_oval(6, 6, 28, 28, outline=glow, width=2)
        c.create_oval(12, 12, 22, 22, outline=glow, width=1)
        c.create_oval(15, 15, 19, 19, fill=glow, outline=glow)

    # ---- dialog sink (called from the worker thread) ----------------------
    def jarvis(self, text: str) -> None:
        self._append("JARVIS", text + "\n", "jarvis")

    def you(self, text: str) -> None:
        self._append("YOU", text + "\n", "you")

    def status(self, message: str) -> None:
        self.root.after(0, lambda: self.status_label.config(text=message.upper()[:28]))

    def output(self, text: str, code: bool = False, stream: bool = False) -> None:
        end = "" if stream else "\n"
        self.root.after(0, lambda: self._write(text + end, "code" if code else "sys"))

    def ask(self, question: str) -> str | None:
        self.jarvis(question)
        self._answer = None
        self.pending_question = True
        self._answered.clear()
        self.status("awaiting your answer")
        self._answered.wait()
        self.pending_question = False
        return self._answer

    def confirm(self, question: str) -> bool:
        answer = self.ask(question + "  (yes / no)")
        return bool(answer) and not dialog.NO.search(answer) and bool(dialog.YES.search(answer))

    # ---- transcript helpers (main thread) ---------------------------------
    def _append(self, who: str, text: str, tag: str) -> None:
        self.root.after(0, lambda: self._write_line(who, text, tag))

    def _write_line(self, who: str, text: str, tag: str) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{who}  ", (tag,))
        self.transcript.insert("end", text, (tag,) if tag != "you" else ())
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _write(self, text: str, tag: str) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", text, (tag,))
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    # ---- input ------------------------------------------------------------
    def _submit(self) -> None:
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._feed(text, typed=True)

    def _feed(self, text: str, typed: bool) -> None:
        if self.pending_question:
            if typed:
                self.you(text)
            self._answer = text
            self._answered.set()
            return
        self.you(text)
        self.inputs.put(text)

    def _worker(self) -> None:
        while not self._stop:
            try:
                command = self.inputs.get(timeout=0.2)
            except queue.Empty:
                continue
            if command is None:
                break
            if jarvis.is_exit(command):
                dialog.say("Goodbye.")
                self.root.after(400, self._quit)
                break
            self.busy = True
            try:
                jarvis.respond(command)
            except Exception as e:
                jarvis.log.exception("gui respond error")
                self.jarvis(f"Something went wrong: {e}")
            finally:
                self.busy = False
                self.status("listening" if self.listening else "ready")

    def _boot(self) -> None:
        name = f", {config.YOUR_NAME}" if config.YOUR_NAME else ""
        self.jarvis(f"Good day{name}. All systems online. Type a command, or press Listen and say “Jarvis”.")
        threading.Thread(target=self._check_ai, daemon=True).start()
        self.status("ready")

    def _check_ai(self) -> None:
        ai = brain.get()
        if not ai.ready:
            self.output("Chat and coding are offline - start Ollama to enable them. Built-in commands still work.")

    # ---- voice (hands-free, wake word) ------------------------------------
    def toggle_listen(self) -> None:
        self.listening = not self.listening
        if self.listening:
            self.mic_btn.config(text="◉ LISTENING", fg=GOLD)
            self._draw_reactor(CYAN)
            self._pulse_reactor()
            self.status("starting microphone")
            threading.Thread(target=self._voice_loop, daemon=True).start()
        else:
            self.mic_btn.config(text="◉  LISTEN", fg=CYAN)
            self._draw_reactor(CYAN_DIM)
            self.status("ready")

    def _pulse_reactor(self) -> None:
        if not self.listening:
            self._draw_reactor(CYAN_DIM)
            return
        self._pulse = (self._pulse + 1) % 2
        self._draw_reactor(CYAN if self._pulse else "#8be8ff")
        self.root.after(600, self._pulse_reactor)

    def _voice_loop(self) -> None:
        try:
            from ears import Ears
            ears = Ears()
            ears.calibrate()
        except Exception as e:
            self.jarvis(f"I couldn't start the microphone: {e}")
            self.listening = False
            self.root.after(0, lambda: self.mic_btn.config(text="◉  LISTEN", fg=CYAN))
            return
        self.root.after(0, lambda: self.jarvis('Listening. Say "Jarvis" and your command.'))
        self.status("listening")
        awake_until = 0.0
        while self.listening:
            if self.busy:
                time.sleep(0.15)
                continue
            awake = self.pending_question or time.time() < awake_until
            heard = ears.listen(wake_check=None if awake else jarvis.WAKE_WORD.search)
            if not heard or not self.listening:
                continue
            if self.pending_question:
                self.root.after(0, lambda h=heard: (self.you(h), self._set_answer(h)))
                continue
            match = jarvis.WAKE_WORD.search(heard)
            if match:
                command = heard[match.end():].strip() or heard[:match.start()].strip()
            elif time.time() < awake_until and jarvis.FOLLOW_UP.match(skills.normalise(heard)):
                command = heard
            else:
                self.status(f"heard: {heard}")
                continue
            if command:
                self.root.after(0, lambda c=command: self._feed(c, typed=False))
                awake_until = time.time() + config.FOLLOW_UP_SECONDS

    def _set_answer(self, text: str) -> None:
        self._answer = text
        self._answered.set()

    # ---- tray + lifecycle -------------------------------------------------
    def _try_tray(self) -> None:
        self.tray = None
        try:
            import pystray
            from PIL import Image

            image = Image.open(str(_asset("jarvis.png")))
            menu = pystray.Menu(
                pystray.MenuItem("Show Jarvis", lambda: self.root.after(0, self._show), default=True),
                pystray.MenuItem("Listen on/off", lambda: self.root.after(0, self.toggle_listen)),
                pystray.MenuItem("Hide", lambda: self.root.after(0, self.root.withdraw)),
                pystray.MenuItem("Quit", lambda: self.root.after(0, self._quit)),
            )
            tray = pystray.Icon("jarvis", image, "Jarvis", menu)

            def run_tray():
                try:
                    tray.run()
                except Exception:
                    self.tray = None

            self.tray = tray
            threading.Thread(target=run_tray, daemon=True).start()
        except Exception:
            self.tray = None

    def _show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.entry.focus_set()

    def _hide_or_quit(self) -> None:
        if self.tray:
            self.root.withdraw()
        else:
            self._quit()

    def _quit(self) -> None:
        self._stop = True
        self.listening = False
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def _asset(name: str):
    from pathlib import Path
    return Path(__file__).with_name(name)


def main() -> None:
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    JarvisGUI(start_hidden="--tray" in sys.argv, auto_listen="--listen" in sys.argv).run()


if __name__ == "__main__":
    main()

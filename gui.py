"""Jarvis desktop window: a chat-style GUI front-end for the same assistant.

It reuses everything else unchanged - it registers itself as a `dialog` sink, so every spoken line,
question, command and piece of code flows into the window, and runs jarvis.respond() on a worker
thread so the window never freezes while the model thinks. Optional system-tray icon (pystray).

Run:  pythonw gui.py      (no console window on Windows)
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

# Dark theme
BG, PANEL, FG, MUTED = "#0e1117", "#161b22", "#e6edf3", "#8b949e"
YOU, JARVIS, SYS, CODE_FG, ACCENT = "#7ee787", "#79c0ff", "#8b949e", "#d2a8ff", "#1f6feb"


class JarvisGUI:
    def __init__(self, start_hidden: bool = False) -> None:
        self.inputs: queue.Queue = queue.Queue()
        self.busy = False
        self.listening = False
        self.pending_question = False
        self._answer: str | None = None
        self._answered = threading.Event()
        self._stop = False
        self._voice_thread: threading.Thread | None = None

        self._build_window()
        self.mouth = Mouth()
        dialog.setup(self.mouth, ears=None)  # the window handles voice itself; dialog.ask uses this sink
        dialog.set_sink(self)
        jarvis.setup_log()
        jarvis.log.info("--- Jarvis started (GUI mode) ---")

        threading.Thread(target=self._worker, daemon=True).start()
        self._try_tray()
        self._boot()
        if start_hidden and self.tray:  # launched at login: live quietly in the tray
            self.root.withdraw()

    # ---- window -----------------------------------------------------------
    def _build_window(self) -> None:
        self.root = tk.Tk()
        self.root.title("Jarvis")
        self.root.geometry("680x600")
        self.root.minsize(460, 400)
        self.root.configure(bg=BG)
        try:
            self.root.iconphoto(True, tk.PhotoImage(file=str(_asset("jarvis.png"))))
        except Exception:
            pass

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(header, text="JARVIS", bg=BG, fg=JARVIS,
                 font=tkfont.Font(family="Segoe UI Semibold", size=16, weight="bold")).pack(side="left")
        self.status_label = tk.Label(header, text="Starting...", bg=BG, fg=MUTED,
                                     font=tkfont.Font(family="Segoe UI", size=10))
        self.status_label.pack(side="right")

        mono = tkfont.Font(family="Consolas", size=10)
        body = tkfont.Font(family="Segoe UI", size=11)
        self.transcript = scrolledtext.ScrolledText(
            self.root, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", wrap="word",
            font=body, padx=12, pady=10, state="disabled", borderwidth=0)
        self.transcript.pack(fill="both", expand=True, padx=16, pady=6)
        self.transcript.tag_config("you", foreground=YOU, font=tkfont.Font(family="Segoe UI", size=11, weight="bold"))
        self.transcript.tag_config("jarvis", foreground=JARVIS)
        self.transcript.tag_config("sys", foreground=SYS, font=tkfont.Font(family="Segoe UI", size=9, slant="italic"))
        self.transcript.tag_config("code", foreground=CODE_FG, font=mono)

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=16, pady=(6, 14))
        self.mic_btn = tk.Button(bar, text="🎤 Listen", command=self.toggle_listen, bg=PANEL, fg=FG,
                                 activebackground=ACCENT, activeforeground="white", relief="flat",
                                 font=body, width=10, cursor="hand2")
        self.mic_btn.pack(side="left")
        self.entry = tk.Entry(bar, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", font=body)
        self.entry.pack(side="left", fill="x", expand=True, padx=8, ipady=6)
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.entry.focus_set()
        tk.Button(bar, text="Send", command=self._submit, bg=ACCENT, fg="white", activebackground="#388bfd",
                  activeforeground="white", relief="flat", font=body, width=7, cursor="hand2").pack(side="left")

        self.root.protocol("WM_DELETE_WINDOW", self._hide_or_quit)

    # ---- dialog sink (called from the worker thread) ----------------------
    def jarvis(self, text: str) -> None:
        self._append("Jarvis", text + "\n", "jarvis")

    def you(self, text: str) -> None:
        self._append("You", text + "\n", "you")

    def status(self, message: str) -> None:
        self.root.after(0, lambda: self.status_label.config(text=message))

    def output(self, text: str, code: bool = False, stream: bool = False) -> None:
        end = "" if stream else "\n"
        self.root.after(0, lambda: self._write(text + end, "code" if code else "sys"))

    def ask(self, question: str) -> str | None:
        self.jarvis(question)
        self._answer = None
        self.pending_question = True
        self._answered.clear()
        self.status("Waiting for your answer...")
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
        if self.pending_question:  # this answers Jarvis's question instead of starting a new command
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
                self.status("Listening..." if self.listening else "Ready.")

    def _boot(self) -> None:
        name = f", {config.YOUR_NAME}" if config.YOUR_NAME else ""
        self.jarvis(f"Hello{name}. Type a command below, or click Listen to talk.")
        threading.Thread(target=self._check_ai, daemon=True).start()
        self.status("Ready.")

    def _check_ai(self) -> None:
        ai = brain.get()
        if not ai.ready:
            self.output("Chat and coding are off - start Ollama to enable them. Built-in commands still work.")

    # ---- voice ------------------------------------------------------------
    def toggle_listen(self) -> None:
        self.listening = not self.listening
        if self.listening:
            self.mic_btn.config(text="🛑 Stop", fg=YOU)
            self.status("Starting microphone...")
            self._voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
            self._voice_thread.start()
        else:
            self.mic_btn.config(text="🎤 Listen", fg=FG)
            self.status("Ready.")

    def _voice_loop(self) -> None:
        try:
            from ears import Ears
            ears = Ears()
            ears.calibrate()
        except Exception as e:
            self.jarvis(f"I couldn't start the microphone: {e}")
            self.listening = False
            self.root.after(0, lambda: self.mic_btn.config(text="🎤 Listen", fg=FG))
            return
        self.status("Listening...")
        awake_until = 0.0
        while self.listening:
            if self.busy:  # don't record while Jarvis is working or speaking
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
                self.status(f"(heard: {heard})")
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
                pystray.MenuItem("Hide", lambda: self.root.after(0, self.root.withdraw)),
                pystray.MenuItem("Quit", lambda: self.root.after(0, self._quit)),
            )
            self.tray = pystray.Icon("jarvis", image, "Jarvis", menu)
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception:
            self.tray = None  # no tray available; the window's close button will quit instead

    def _show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.entry.focus_set()

    def _hide_or_quit(self) -> None:
        if self.tray:
            self.root.withdraw()  # keep running in the tray
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
        try:  # crisp text on high-DPI screens
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    JarvisGUI(start_hidden="--tray" in sys.argv).run()


if __name__ == "__main__":
    main()

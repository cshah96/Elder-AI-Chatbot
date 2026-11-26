"""
Elder AI Chatbot - a simple desktop chat window backed by a local Gemma 4 model.

The assistant is called Pip. Its animated face sits at the top of the window,
and the chat sits underneath it.

The model is served locally by Ollama (https://ollama.com). Nothing is sent to
the internet: every message goes to the Ollama server running on this machine.

Run:
    python chatbot.py
"""

import json
import math
import os
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import scrolledtext

import requests

# ---------------------------------------------------------------------------
# Configuration (can be overridden with environment variables)
# ---------------------------------------------------------------------------
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("ELDER_AI_MODEL", "gemma4:e2b")

SYSTEM_PROMPT = (
    "Your name is Pip. You are a kind, patient and friendly assistant for older adults. "
    "Use simple, clear language and short sentences. Avoid jargon. "
    "Be warm and encouraging. If a question is about health, medicine or "
    "an emergency, give helpful general information and gently remind the "
    "user to contact their doctor, a family member, or emergency services."
)

# Look and feel
BG_COLOR = "#000000"
FG_COLOR = "#FFFFFF"
INPUT_BG = "#1a1a1a"
BUTTON_BG = "#333333"
FONT = ("Helvetica", 14)
FONT_BOLD = ("Helvetica", 14, "bold")

# Pip's face
FACE_SIZE = 200          # diameter of the face in pixels
FACE_COLOR = "#FFFFFF"
FACE_OUTLINE = "#E8E8E8"
FEATURE_COLOR = "#2B2B2B"  # eyes and mouth
CHEEK_COLOR = "#FFC9D6"
MOUTH_INSIDE = "#5A2A2A"
FRAME_MS = 33            # about 30 frames per second
BLINK_SECONDS = 0.18     # how long one blink takes


class OllamaChat:
    """Keeps the conversation history and talks to the local Ollama server."""

    def __init__(self, model: str, base_url: str, system_prompt: str):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.messages = [{"role": "system", "content": system_prompt}]

    def stream_reply(self, user_text: str):
        """Send the user's message and yield the reply piece by piece."""
        self.messages.append({"role": "user", "content": user_text})
        payload = {"model": self.model, "messages": self.messages, "stream": True}

        reply_parts = []
        with requests.post(
            f"{self.base_url}/api/chat", json=payload, stream=True, timeout=300
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise RuntimeError(chunk["error"])
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    reply_parts.append(piece)
                    yield piece
                if chunk.get("done"):
                    break

        self.messages.append({"role": "assistant", "content": "".join(reply_parts)})

    def reset(self):
        self.messages = self.messages[:1]  # keep only the system prompt


class PipFace:
    """A round, friendly animated face drawn on a Tkinter canvas.

    It gently floats up and down, blinks every few seconds, smiles while
    idle, and moves its mouth while Pip is talking.
    """

    def __init__(self, parent: tk.Widget, size: int = FACE_SIZE):
        self.size = size
        self.canvas = tk.Canvas(
            parent, height=size + 40, bg=BG_COLOR, highlightthickness=0
        )
        self.talking = False
        self.blink_started = None
        self.next_blink = time.monotonic() + random.uniform(1.5, 3.5)
        self.animate()

    def eye_openness(self, now: float) -> float:
        """1.0 = eyes fully open, 0.0 = closed. Handles the blink timing."""
        if self.blink_started is None and now >= self.next_blink:
            self.blink_started = now
        if self.blink_started is None:
            return 1.0
        t = (now - self.blink_started) / BLINK_SECONDS
        if t >= 1.0:
            self.blink_started = None
            # Sometimes do a quick double blink, which looks more natural.
            gap = 0.25 if random.random() < 0.2 else random.uniform(2.5, 5.5)
            self.next_blink = now + gap
            return 1.0
        return abs(1.0 - 2.0 * t)  # close, then open again

    def animate(self):
        self.draw(time.monotonic())
        self.canvas.after(FRAME_MS, self.animate)

    def draw(self, now: float):
        c = self.canvas
        c.delete("all")
        width = c.winfo_width() or 800
        height = int(c["height"])
        r = self.size / 2
        cx = width / 2
        cy = height / 2 + 4 * math.sin(now * 2 * math.pi / 3.0)  # gentle float

        # Head
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=FACE_COLOR, outline=FACE_OUTLINE, width=3)

        # Rosy cheeks
        for side in (-1, 1):
            x = cx + side * r * 0.58
            y = cy + r * 0.18
            c.create_oval(x - r * 0.14, y - r * 0.08, x + r * 0.14, y + r * 0.08,
                          fill=CHEEK_COLOR, outline=CHEEK_COLOR)

        # Eyes (with a little sparkle when open)
        openness = self.eye_openness(now)
        ew = r * 0.12
        eh = max(r * 0.19 * openness, 2)
        ey = cy - r * 0.18
        for side in (-1, 1):
            ex = cx + side * r * 0.36
            c.create_oval(ex - ew, ey - eh, ex + ew, ey + eh,
                          fill=FEATURE_COLOR, outline=FEATURE_COLOR)
            if openness > 0.6:
                hx, hy, hr = ex - ew * 0.3, ey - eh * 0.4, ew * 0.35
                c.create_oval(hx - hr, hy - hr, hx + hr, hy + hr,
                              fill=FACE_COLOR, outline=FACE_COLOR)

        # Mouth
        if self.talking:
            # Open and close the mouth like speaking.
            open_amount = (math.sin(now * 14) + 1) / 2
            mw = r * 0.30
            depth = r * (0.10 + 0.18 * open_amount)
            top = cy + r * 0.28
            c.create_arc(cx - mw, top - depth, cx + mw, top + depth,
                         start=180, extent=180, style=tk.PIESLICE,
                         fill=MOUTH_INSIDE, outline=FEATURE_COLOR, width=3)
        else:
            # A big, warm smile.
            c.create_arc(cx - r * 0.45, cy - r * 0.25, cx + r * 0.45, cy + r * 0.50,
                         start=200, extent=140, style=tk.ARC,
                         outline=FEATURE_COLOR, width=6)


class ChatWindow:
    """Pip's face on top, the current conversation turn below, input at the bottom."""

    def __init__(self, root: tk.Tk, chat: OllamaChat):
        self.root = root
        self.chat = chat
        self.events = queue.Queue()  # messages from the worker thread to the UI
        self.busy = False

        root.title(f"Pip - Elder AI Assistant ({chat.model})")
        root.geometry("800x750")
        root.configure(bg=BG_COLOR)

        # Pip's animated face
        self.face = PipFace(root)
        self.face.canvas.pack(fill=tk.X, padx=10, pady=(10, 0))

        # Input row (packed before the chat so it always stays visible)
        input_frame = tk.Frame(root, bg=BG_COLOR)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 10))

        self.entry = tk.Entry(
            input_frame,
            bg=INPUT_BG,
            fg=FG_COLOR,
            insertbackground=FG_COLOR,
            font=FONT,
            relief=tk.FLAT,
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 5))
        self.entry.bind("<Return>", lambda _e: self.send())
        self.entry.focus_set()

        button_style = dict(
            bg=BUTTON_BG,
            fg=FG_COLOR,
            activebackground="#555555",
            activeforeground=FG_COLOR,
            font=FONT,
            relief=tk.FLAT,
            padx=12,
        )
        self.send_button = tk.Button(input_frame, text="Send", command=self.send, **button_style)
        self.send_button.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(input_frame, text="Clear", command=self.clear, **button_style).pack(side=tk.LEFT)

        # Conversation area. It holds the whole conversation, but each new turn
        # is scrolled to the top so only the current one shows. Scroll up to
        # see earlier messages.
        self.history = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            bg=BG_COLOR,
            fg=FG_COLOR,
            insertbackground=FG_COLOR,
            font=FONT,
            state=tk.DISABLED,
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10,
        )
        self.history.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.history.tag_configure("speaker", font=FONT_BOLD, foreground=FG_COLOR)
        self.history.tag_configure("text", font=FONT, foreground=FG_COLOR)
        self.history.bind("<Configure>", self.resize_spacer)
        self.reset_history()

        self.start_turn()
        self.append("Pip", "Hello! I am Pip. How can I help you today?\n\n")
        self.root.after(50, self.process_events)

    # --- Conversation area helpers ---------------------------------------
    # An invisible "spacer" line sits at the very end of the text, about as tall
    # as the chat area. It lets the newest turn scroll all the way to the top
    # even when it is short, so the previous turn is hidden above it.
    def reset_history(self):
        self.history.configure(state=tk.NORMAL)
        self.history.delete("1.0", tk.END)
        self.history.insert(tk.END, "\n", "spacer_nl")
        self.history.insert(tk.END, "​", "spacer")
        self.history.configure(state=tk.DISABLED)

    def resize_spacer(self, event=None):
        height = self.history.winfo_height()
        self.history.tag_configure("spacer", spacing3=max(height - 40, 0))

    def start_turn(self):
        """Remember where the current turn starts so it can be shown at the top."""
        self.history.mark_set("turn_start", "spacer_nl.first")
        self.history.mark_gravity("turn_start", tk.LEFT)

    def show_current_turn(self):
        self.history.update_idletasks()
        self.history.yview("turn_start")

    def append(self, speaker: str | None, text: str):
        self.history.configure(state=tk.NORMAL)
        if speaker:
            self.history.insert("spacer_nl.first", f"{speaker}: ", "speaker")
        self.history.insert("spacer_nl.first", text, "text")
        self.history.configure(state=tk.DISABLED)

    def follow_reply(self):
        """Keep the newest words visible if the reply is longer than the window."""
        self.history.see("spacer_nl.first")

    def set_busy(self, busy: bool):
        self.busy = busy
        self.send_button.configure(state=tk.DISABLED if busy else tk.NORMAL)
        if not busy:
            self.face.talking = False

    # --- Actions ----------------------------------------------------------
    def send(self):
        text = self.entry.get().strip()
        if not text or self.busy:
            return
        self.entry.delete(0, tk.END)
        self.start_turn()
        self.append("You", text + "\n\n")
        self.append("Pip", "")
        self.show_current_turn()
        self.set_busy(True)
        threading.Thread(target=self.worker, args=(text,), daemon=True).start()

    def clear(self):
        if self.busy:
            return
        self.chat.reset()
        self.reset_history()
        self.start_turn()
        self.append("Pip", "Let's start fresh. How can I help you?\n\n")
        self.show_current_turn()

    def worker(self, text: str):
        """Runs in a background thread so the window never freezes."""
        try:
            for piece in self.chat.stream_reply(text):
                self.events.put(("text", piece))
        except requests.exceptions.ConnectionError:
            self.chat.messages.pop()  # drop the unanswered user message
            self.events.put((
                "text",
                "[Could not reach the local model. Is Ollama running? "
                "Try `ollama serve` in a terminal.]",
            ))
        except Exception as exc:  # show any other problem in the chat window
            if self.chat.messages[-1]["role"] == "user":
                self.chat.messages.pop()
            self.events.put(("text", f"[Error: {exc}]"))
        finally:
            self.events.put(("done", None))

    def process_events(self):
        """Move text from the worker thread into the window (Tk is not thread-safe)."""
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "text":
                    self.face.talking = True
                    self.append(None, value)
                    self.follow_reply()
                elif kind == "done":
                    self.append(None, "\n\n")
                    self.set_busy(False)
        except queue.Empty:
            pass
        self.root.after(50, self.process_events)


def main():
    root = tk.Tk()
    ChatWindow(root, OllamaChat(MODEL_NAME, OLLAMA_URL, SYSTEM_PROMPT))
    root.mainloop()


if __name__ == "__main__":
    main()

"""
Elder AI Chatbot - a simple desktop chat window backed by a local Gemma 4 model.

The model is served locally by Ollama (https://ollama.com). Nothing is sent to
the internet: every message goes to the Ollama server running on this machine.

Run:
    python chatbot.py
"""

import json
import os
import queue
import threading
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


class ChatWindow:
    """Tkinter chat window: black background, white text."""

    def __init__(self, root: tk.Tk, chat: OllamaChat):
        self.root = root
        self.chat = chat
        self.events = queue.Queue()  # messages from the worker thread to the UI
        self.busy = False

        root.title(f"Pip - Elder AI Assistant ({chat.model})")
        root.geometry("800x600")
        root.configure(bg=BG_COLOR)

        # Conversation area
        self.history = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            bg=BG_COLOR,
            fg=FG_COLOR,
            insertbackground=FG_COLOR,
            font=FONT,
            state=tk.DISABLED,
            borderwidth=0,
            padx=10,
            pady=10,
        )
        self.history.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        self.history.tag_configure("speaker", font=FONT_BOLD, foreground=FG_COLOR)
        self.history.tag_configure("text", font=FONT, foreground=FG_COLOR)

        # Input row
        input_frame = tk.Frame(root, bg=BG_COLOR)
        input_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

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

        self.append("Pip", "Hello! I am Pip. How can I help you today?\n")
        self.root.after(50, self.process_events)

    # --- UI helpers -------------------------------------------------------
    def append(self, speaker: str | None, text: str):
        self.history.configure(state=tk.NORMAL)
        if speaker:
            self.history.insert(tk.END, f"{speaker}: ", "speaker")
        self.history.insert(tk.END, text, "text")
        self.history.configure(state=tk.DISABLED)
        self.history.see(tk.END)

    def set_busy(self, busy: bool):
        self.busy = busy
        self.send_button.configure(state=tk.DISABLED if busy else tk.NORMAL)

    # --- Actions ----------------------------------------------------------
    def send(self):
        text = self.entry.get().strip()
        if not text or self.busy:
            return
        self.entry.delete(0, tk.END)
        self.append("You", text + "\n\n")
        self.append("Pip", "")
        self.set_busy(True)
        threading.Thread(target=self.worker, args=(text,), daemon=True).start()

    def clear(self):
        if self.busy:
            return
        self.chat.reset()
        self.history.configure(state=tk.NORMAL)
        self.history.delete("1.0", tk.END)
        self.history.configure(state=tk.DISABLED)
        self.append("Pip", "Let's start fresh. How can I help you?\n")

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
                    self.append(None, value)
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

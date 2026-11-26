# Elder AI Chatbot

### Custom Senior AI Chat bot for Support and Care

The goal of this project is an AI assistant built for older adults. It will help
with daily activities and more. The project is being built up one step at a time.
This README lists what is done so far.

---

## What is done so far

### Step 1: Basic local chatbot (`chatbot.py`)

The assistant is called **Pip** for now.

- A desktop chat window (built with Tkinter) with a **black background and white text**.
- Type a question, press **Enter** or click **Send**, and the reply shows up as it is written.
- Uses **Gemma 4 (`gemma4:e2b`)** running **locally** through [Ollama](https://ollama.com).
  Conversations stay on your computer.
- Remembers the conversation, so you can ask follow-up questions.
- A **Clear** button starts a new conversation.
- A system prompt tells the model to be patient and friendly, to use simple language,
  and to point people to a doctor, family member or emergency services for health
  or emergency questions.
- The window stays responsive while the model is thinking, because the model runs
  in a background thread.

### Step 2: Pip's animated face

- A round, white, friendly face for Pip at the top of the window, drawn with a Tkinter
  canvas (no image files or extra packages needed).
- Pip **blinks** every few seconds (sometimes a quick double blink), **floats** gently
  up and down, has rosy cheeks, and wears a **warm smile** when idle.
- While Pip is replying, its **mouth moves** as if talking, then goes back to smiling.
- The chat area under the face shows only the **current exchange** (your question and
  Pip's reply). **Scroll up** to see earlier messages.
- The text box and Send/Clear buttons are at the bottom for replying to Pip.

---

## Requirements

- Python 3.10 or newer, with Tkinter (on Ubuntu/Debian: `sudo apt install python3-tk`)
- [Ollama](https://ollama.com) installed and running
- The Gemma 4 model pulled into Ollama
- The Python packages in `requirements.txt`

## Setup

```bash
# 1. Get the model (one-time)
ollama pull gemma4:e2b

# 2. (Optional) create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python packages
pip install -r requirements.txt
```

## Running

Make sure Ollama is running (it usually starts on its own; if not, run `ollama serve`), then:

```bash
python chatbot.py
```

### Configuration

You can change these with environment variables:

| Variable         | Default                  | Meaning                     |
|------------------|--------------------------|-----------------------------|
| `ELDER_AI_MODEL` | `gemma4:e2b`             | Which Ollama model to use   |
| `OLLAMA_URL`     | `http://localhost:11434` | Where the Ollama server is  |

Example: `ELDER_AI_MODEL=gemma4:e4b python chatbot.py`

---

## Project structure

```
Elder-AI-Chatbot/
├── chatbot.py        # Chat window, Pip's animated face, and the local Gemma 4 connection
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Roadmap (planned)

- Larger text and accessibility options
- Voice input and spoken replies
- Medication and appointment reminders
- Help with daily activities and routines
- Emergency contacts and alerts

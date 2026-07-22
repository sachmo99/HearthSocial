# Role-Play App

A local, fully offline AI role-playing chat app. Runs entirely on-device: a llama.cpp (Vulkan) server for inference, a FastAPI backend, and a React frontend. No data leaves your machine.

Characters are persistent personas with their own memory, mood, and evolving relationship state — a structured JSON summary (location, mood, appearance, memory, affection, closeness, relationship stage) is maintained across the conversation and periodically re-derived by the model itself, and injected back into every prompt as plain-language behavioral instructions. Vector search (RAG) recalls specific facts from earlier in the conversation even after they've scrolled out of the immediate context window.

For the full build history, design decisions, and known gaps, see [PROGRESS.md](PROGRESS.md).

## Features

- Character cards with persona, opening scene, sampling personality, and starting relationship stats — create/edit them directly in the UI.
- Click a character to auto-generate an opening scene in character (via a hidden system trigger you never see).
- Structured memory: affection, closeness, relationship stage, mood, location, and durable facts, updated by the model every 10 messages (configurable), merged rather than overwritten.
- RAG-backed recall of specific facts from anywhere earlier in the conversation, scoped per-session.
- Per-message sampling override popup (temperature/top_p/top_k/min_p) — no server restart needed.
- Live stats bar (❤️ affection, 🤝 closeness, 🎭 mood, relationship-stage badge) plus a "messages until next summary" counter and a summarizing-in-progress indicator.
- Session history: browse and view past (cleared) conversations read-only.
- Regenerate button to redo the last reply; in-flight generation is properly aborted when you switch characters or clear the chat, so it doesn't keep the single inference slot tied up.
- Dialogue/action/internal-monologue visually distinguished in the chat, including recovery for models that don't perfectly follow the formatting convention.
- Collapsible debug panel (lazy-loaded) showing the live structured summary state and the exact RAG hits used for the current turn.

## Stack

- **Backend**: Python / FastAPI, reusing the venv at the repo root (`c:\Users\sachm\Downloads\mistral-12b`).
- **Frontend**: Vite + React.
- **Inference**: [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server`, Vulkan build, serving an OpenAI-compatible HTTP API.
- **Storage**: SQLite + the [`sqlite-vec`](https://github.com/asg017/sqlite-vec) extension for vector search — one file, no external services.
- **Embeddings**: `BAAI/bge-small-en-v1.5` (384-dim), run fully offline once cached.

## Prerequisites

- A working `llama-server` build with Vulkan support (this project was built against one at `C:\Softwares\llama-cpp-vulkan\llama-server.exe`).
- A GGUF model file.
- Python 3.12+ with `fastapi`, `httpx`, `uvicorn`, `sentence-transformers`, `sqlite-vec` installed (all already present in the root venv for this project).
- Node.js / npm (for the frontend).

## Running it

Three processes, each in its own terminal — all are long-running, so start them yourself and leave them open.

**1. llama-server** (single slot, deliberately — see [PROGRESS.md](PROGRESS.md) for why):

```powershell
& "C:\Softwares\llama-cpp-vulkan\llama-server.exe" -m "C:\Users\sachm\Downloads\mistral-12b\gemma-4-E4B-it-uncensored-Q4_K_M.gguf" -c 16384 -np 1 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 --host 127.0.0.1 --port 8080
```

**2. Backend**:

```powershell
cd roleplay_app\backend
..\..\Scripts\python.exe -m uvicorn main:app --port 8000 --host 127.0.0.1
```

Must run as a single uvicorn worker — the background summarizer's concurrency guard is in-process memory, not shared across workers.

**3. Frontend**:

```powershell
cd roleplay_app\frontend
npm install   # first time only
npm run dev
```

Then open the URL Vite prints (usually `http://localhost:5173`).

## Creating a character

Either use the "+ New Character" tile in the UI, or hand-author a JSON file in `backend/characters/` (restart the backend to pick up hand-authored files — the UI's create/edit flow updates the database immediately, without needing a restart). Shape:

```json
{
  "name": "Character Name",
  "persona": "System-prompt-style description of who they are.",
  "opening_trigger_template": "[SYSTEM: instruction for the model to set the opening scene in character.]",
  "sampling_preset": "calm | balanced | chaotic",
  "initial_state": {
    "location": "",
    "time_of_day": "",
    "character_mood": "",
    "character_appearance": "",
    "character_memory": "",
    "character_affection": 20,
    "character_closeness": 10,
    "relationship_stage": "stranger",
    "notable_facts": [],
    "last_updated_seq": 0
  }
}
```

`relationship_stage` must be one of `stranger`, `acquaintance`, `friend`, `confidant`, `partner`, `spouse`, `family` — the summarizer is constrained to only ever pick from this set going forward.

## Configuration

Key knobs live in `backend/config.py`:

| Setting | Current value | Meaning |
|---|---|---|
| `CONTEXT_WINDOW_TOKENS` | 16384 | Must match llama-server's `-c` |
| `GENERATION_HEADROOM_TOKENS` | 1024 | Reserved for the reply, subtracted from the prompt budget |
| `RECENT_MESSAGE_CAP` | 20 | Max raw messages kept verbatim in the prompt |
| `SUMMARIZE_EVERY_N_MESSAGES` | 10 | How often the structured memory state gets re-derived |
| `RAG_TOP_K` / `RAG_OVERFETCH_K` | 5 / 50 | RAG result count / candidate pool size |
| `SAMPLING_PRESETS` | calm / balanced / chaotic | Base temperature/top_p/top_k/min_p per personality preset |

## Known limitations

- Single llama-server slot: switching characters or background summarization both compete for the same inference slot, so there's a real (not corruption, just latency) cost to interleaving them — see the KV-cache discussion in [PROGRESS.md](PROGRESS.md).
- No avatar images — character portraits are generated gradients, by design choice so far.
- Local/quantized models won't always perfectly honor formatting or grounding instructions (e.g. occasionally contradicting a recalled fact) — prompting reduces this but doesn't eliminate it.

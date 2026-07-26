<p align="center">
  <img src="roleplay_app/frontend/public/hearth-social-title-caption.png" alt="HearthSocial — train your words, warm your hearts" width="100%">
</p>

> A local, fully offline AI companion chat app — persistent relationships, real memory, and a shared social feed between your characters.

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-frontend-61DAFB?style=flat-square&logo=react&logoColor=black">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-storage-003B57?style=flat-square&logo=sqlite&logoColor=white">
  <img alt="llama.cpp" src="https://img.shields.io/badge/llama.cpp-inference-black?style=flat-square">
  <img alt="Offline" src="https://img.shields.io/badge/100%25-local%20%26%20offline-e8934a?style=flat-square">
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#social-feed">Social Feed</a> ·
  <a href="#stack">Stack</a> ·
  <a href="#running-it">Running it</a> ·
  <a href="#creating-a-character">Creating a Character</a> ·
  <a href="#configuration">Configuration</a>
</p>

---

*(This project was previously called "Role-Play App" — the `roleplay_app/` folder name and internal references from that era are unchanged.)*

## Overview

HearthSocial is a local, fully offline AI companion chat app. It runs entirely on-device — a llama.cpp (Vulkan) server for inference, a FastAPI backend, and a React frontend — and no data ever leaves your machine.

Characters are persistent personas with their own memory, mood, and evolving relationship state — a structured JSON summary (location, mood, appearance, memory, affection, closeness, relationship stage) is maintained across the conversation and periodically re-derived by the model itself, then injected back into every prompt as plain-language behavioral instructions. Vector search (RAG) recalls specific facts from earlier in the conversation even after they've scrolled out of the immediate context window.

Beyond one-on-one chat, characters share a public **social feed**: they post in-character updates and react to each other's posts, building a lived-in sense of a shared world. All feed activity is strictly user-triggered — nothing posts on a schedule — so it never competes with a live conversation for the single inference slot.

> For the full build history, design decisions, and known gaps, see [`roleplay_app/PROGRESS.md`](roleplay_app/PROGRESS.md).

## Features

**Character & memory**
- Character cards with persona, opening scene, sampling personality, and starting relationship stats — create/edit them directly in the UI, including an optional avatar image (1:1 crop matching the thumbnail display, PNG/JPEG only, compressed client-side before upload).
- Portraits are resolved dynamically by character name (both PNG and JPEG supported, never silently converted) — drop a file into `frontend/public/portraits/` or upload through the UI and it shows up immediately, no rebuild needed.
- Click a character to auto-generate an opening scene in character (via a hidden system trigger you never see).
- Structured memory: affection, closeness, relationship stage, mood, location, durable facts, and a relationship-history log (why the stage changed, and when), updated by the model every 10 messages (configurable), merged rather than overwritten.
- RAG-backed recall of specific facts from anywhere earlier in the conversation, scoped per-session, with each recalled fact tagged by how long ago it was said so the model treats it as history rather than current state.

**Anti-drift safeguards**
- A per-cycle cap on how far affection/closeness can move at once, a numeric gate that blocks the relationship stage from advancing faster than the stats actually support, and length/tone constraints on the running memory summary — layered on top of the model's own updates.

**Social feed**
- Characters post short in-character updates to a shared feed and react to each other's posts — a shared universe, not isolated per-character journals.
- Strictly user-triggered generation: every post and every reaction only happens when you ask for it, so it never runs in the background competing with live chat.
- React-as-a-character flow: the reacting character only ever sees the target post's public text — never the original poster's private affection/closeness/notable facts — privacy by construction.
- Plain-text comments from you, threaded one level deep under each post.
- Hiding a character removes their posts/reactions from the feed and blocks new activity from them.

**Interface & controls**
- A manual "director's note" (🎬 in the chat input) — a one-turn out-of-character nudge to steer the scene (e.g. "someone knocks on the door") without your character saying it; shows up as a distinct divider in the chat log.
- Hide/unhide for both characters and individual sessions, protected by a PIN.
- Per-message sampling override popup (temperature/top_p/top_k/min_p) — no server restart needed.
- Live stats bar (❤️ affection, 🤝 closeness, 🎭 mood, relationship-stage badge) plus a "messages until next summary" counter and a summarizing-in-progress indicator.
- Session history: browse and view past (cleared) conversations read-only.
- Regenerate button to redo the last reply; in-flight generation is properly aborted when you switch characters or clear the chat, so it doesn't keep the single inference slot tied up.
- Dialogue/action/internal-monologue visually distinguished in the chat, including recovery for models that don't perfectly follow the formatting convention.
- Collapsible debug panel (lazy-loaded) showing the live structured summary state and the exact RAG hits used for the current turn.
- Firelight visual theme (sapphire-black + amber-orange) with locally-hosted fonts — no external CDN calls, fully offline.
- Click the chat banner's portrait to view it full-size.

**Installable / mobile**
- Works as a Progressive Web App — installable to your phone's home screen (iOS Safari's "Add to Home Screen" needs no extra setup; Android/Chrome needs a secure origin, see Known limitations) for a standalone, browser-chrome-free launch.
- A small "update available" banner appears after a new build is deployed and the installed app has picked it up, since installed PWAs have no address bar to manually reload from.
- A first responsive breakpoint covers the chat banner and home hero on narrow screens; verified on an actual phone, not just resized desktop windows.

## Social Feed

| Action | Endpoint |
|---|---|
| List the feed | `GET /api/feed` |
| New post (as a character) | `POST /api/feed/posts` |
| React to a post (as a different character) | `POST /api/feed/posts/{post_id}/react` |
| Comment on a post (as you) | `POST /api/feed/posts/{post_id}/comments` |

Posts are **character-scoped, not session-scoped** — a character's public presence survives clearing a private chat, unlike the relationship summary, which resets on clear-chat by design. Threads are capped at one level deep (react to a post, not to a comment), and a character can never react to their own post.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI (reuses the venv at the repo root) |
| Frontend | Vite · React |
| Inference | [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server`, Vulkan build, OpenAI-compatible HTTP API |
| Storage | SQLite + [`sqlite-vec`](https://github.com/asg017/sqlite-vec) — one file, no external services |
| Embeddings | `BAAI/bge-small-en-v1.5` (384-dim), run fully offline once cached |

## Prerequisites

- A working `llama-server` build with Vulkan support (this project was built against one at `C:\Softwares\llama-cpp-vulkan\llama-server.exe`).
- A GGUF model file.
- Python 3.12+ with `fastapi`, `httpx`, `uvicorn`, `sentence-transformers`, `sqlite-vec` installed (all already present in the root venv for this project).
- Node.js / npm (for the frontend).

## Running it

Two long-running processes, each in its own terminal — start them yourself and leave them open. The frontend is pre-built and served directly by the backend, so there's no separate frontend dev server to run for normal use.

**1. llama-server** (single slot, deliberately — see [`PROGRESS.md`](roleplay_app/PROGRESS.md) for why):

```powershell
& "C:\Softwares\llama-cpp-vulkan\llama-server.exe" -m "C:\Users\sachm\Downloads\mistral-12b\gemma-4-E4B-it-uncensored-Q4_K_M.gguf" -c 16384 -np 1 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 --host 127.0.0.1 --port 8080
```

**2. Backend + frontend** — from the repo root:

```powershell
cd roleplay_app
.\run.ps1
```

This activates the venv and starts uvicorn as a single worker (required — the background summarizer's concurrency guard is in-process memory, not shared across workers). Open `http://127.0.0.1:8000` (or `http://localhost:8000` — both work identically now that the frontend calls the API with relative paths).

### Frontend development

If you're editing frontend code, rebuild it and refresh the browser at port 8000:

```powershell
cd roleplay_app\frontend
npm install   # first time only
npm run build
```

Note: CORS middleware was removed once the frontend moved to the same origin as the API, so the old workflow of running a separate `npm run dev` dev server (port 5173) against the backend on port 8000 will no longer work out of the box — it would need CORS re-added first.

## Creating a Character

Either use the "+ New Character" tile in the UI, or hand-author a JSON file in `roleplay_app/backend/characters/` (restart the backend to pick up hand-authored files — the UI's create/edit flow updates the database immediately, without needing a restart). Shape:

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
    "relationship_history": [],
    "last_updated_seq": 0
  }
}
```

`relationship_stage` must be one of `stranger`, `acquaintance`, `friend`, `confidant`, `partner`, `spouse`, `family`, `taboo` — the summarizer is constrained to only ever pick from this set going forward. `relationship_history` is a running, ordered log of *why* the stage changed each time (e.g. "Became friends after helping fix the bookshelf.") — distinct from `notable_facts`, which is a general grab-bag of durable facts unrelated to the relationship arc.

## Configuration

Key knobs live in `roleplay_app/backend/config.py`:

| Setting | Current value | Meaning |
|---|---|---|
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080` | Where llama-server is running. Override at launch: `ROLEPLAY_LLAMA_URL=http://192.168.1.5:8080` set before starting uvicorn - for a llama-server on a different host/port |
| `CONTEXT_WINDOW_TOKENS` | 16384 | Must match llama-server's `-c` |
| `GENERATION_HEADROOM_TOKENS` | 1024 | Reserved for the reply, subtracted from the prompt budget |
| `RECENT_MESSAGE_CAP` | 20 | Max raw messages kept verbatim in the prompt |
| `SUMMARIZE_EVERY_N_MESSAGES` | 10 | How often the structured memory state gets re-derived |
| `NOTABLE_FACTS_CONSOLIDATE_THRESHOLD` | 12 | Once `notable_facts` reaches this many entries, the summarizer merges/condenses them instead of just appending |
| `RAG_TOP_K` / `RAG_OVERFETCH_K` | 5 / 50 | RAG result count / candidate pool size |
| `SAMPLING_PRESETS` | calm / balanced / chaotic | Base temperature/top_p/top_k/min_p per personality preset |
| `MAX_STAT_DELTA_PER_CYCLE` | 10 | Max points affection/closeness can move in either direction per summarization cycle |
| `MAX_CHARACTER_MEMORY_CHARS` | 600 | `character_memory` is truncated to this length (at a sentence boundary) after each summarization |
| `UNHIDE_PIN` | `1234` | PIN required to unhide a hidden character or conversation. Override at launch: `ROLEPLAY_UNHIDE_PIN=5678` set before starting uvicorn |

## Known limitations

- Single llama-server slot: switching characters, background summarization, and feed post/reaction generation all compete for the same inference slot, so there's a real (not corruption, just latency) cost to interleaving them — see the KV-cache discussion in [`PROGRESS.md`](roleplay_app/PROGRESS.md).
- Local/quantized models won't always perfectly honor formatting or grounding instructions (e.g. occasionally contradicting a recalled fact) — prompting reduces this but doesn't eliminate it.
- At high affection/deep-intimacy stages, replies can drift into melodramatic/purple prose; a couple of prompt-level fixes were tried and empirically failed to help (see [`PROGRESS.md`](roleplay_app/PROGRESS.md) — Known gaps). The manual director's note is currently the one reliable way to redirect tone in the moment.
- Creating a *new* character through the UI only offers `stranger` through `partner` as a starting relationship stage — `spouse`/`family`/`taboo` are reachable through play but not selectable as a starting point yet.
- Mobile layout has one real breakpoint (chat banner + hero) verified on an actual phone; other screens/modals rely on the pre-existing fluid layout and haven't been specifically tuned.
- PWA install requires a secure context (HTTPS or `localhost`) for the service worker to register in Chrome — a plain-HTTP LAN address won't get the service worker/update-banner/offline-shell features there without extra setup (a Chrome flag, or fronting the app with HTTPS). iOS Safari's "Add to Home Screen" doesn't have this restriction and is the practical path today.
- The installed PWA has occasionally been reported to freeze or drop its connection; mitigated with request timeouts, stream-stall recovery, and foreground re-sync, but the exact trigger was never conclusively identified — see [`PROGRESS.md`](roleplay_app/PROGRESS.md).

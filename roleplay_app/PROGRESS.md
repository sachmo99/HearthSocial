# Role-Play App — Progress Tracker

Local AI role-playing chat app per `DESIGN.md`, built in this `roleplay_app/` folder (the rest of the parent directory is an unrelated older prototype — untouched). Full architecture/design rationale lives in the approved plan at `C:\Users\sachm\.claude\plans\tranquil-swimming-sphinx.md`; this file tracks build status and decisions made since.

## Stack

- **Backend**: Python/FastAPI (`roleplay_app/backend/`), reusing the root venv at `c:\Users\sachm\Downloads\mistral-12b`.
- **Frontend**: Vite + React (`roleplay_app/frontend/`).
- **Inference**: `llama-server.exe` (`C:\Softwares\llama-cpp-vulkan\`) over its OpenAI-compatible HTTP API, model `gemma-4-E4B-it-uncensored-Q4_K_M.gguf`.
  - Launch: `-c 16384 -np 1 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 --host 127.0.0.1 --port 8080`
  - Single slot deliberately, not two: measured ~15.7GB total RAM, only ~1.86GB free with the model loaded, so summarization shares the chat slot rather than running on a genuinely concurrent second one (see Decisions below).
- **Storage**: SQLite + `sqlite-vec` extension (`roleplay_app/backend/data/app.db`).
- **Embeddings**: `BAAI/bge-small-en-v1.5` (384-dim), loaded fully offline (`HF_HUB_OFFLINE=1`) once cached.

## Backend (`roleplay_app/backend/`)

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app, all 15 routes |
| `config.py` | paths, token-budget constants, sampling presets |
| `db.py` | sqlite3 connection, schema, `sqlite-vec` load |
| `llama_client.py` | async httpx wrapper — `chat_completion()` (streaming + non-streaming), `tokenize()`, `health()`; splits `content` vs `reasoning_content` |
| `context_builder.py` | assembles the per-turn prompt within the token budget |
| `character_state.py` | behavior directives (affection/closeness/stage/mood → plain-language instructions), sampling nudges, global response-style directive |
| `rag.py` | `embed_and_store()`, `retrieve_top_k()` — vector-only, session-scoped |
| `embeddings.py` | `bge-small-en-v1.5` singleton |
| `summarizer.py` | every-N-messages merge into structured JSON state, ephemeral in-process concurrency guard |
| `characters/example_character.json` | Aria — librarian, stranger-start dynamic |
| `characters/ursula.json` | Ursula — traditional/guarded personality, husband-wife (`spouse`) dynamic |

**Current tuned config** (`config.py`, adjusted from initial defaults): `GENERATION_HEADROOM_TOKENS=1024`, `SUMMARIZE_EVERY_N_MESSAGES=10`.

### API routes
`GET/POST /api/characters`, `GET/PUT/DELETE /api/characters/{id}`, `POST /api/characters/{id}/start`, `POST /api/characters/{id}/clear`, `GET /api/characters/{id}/sessions`, `GET /api/sessions/{id}/state`, `GET /api/sessions/{id}/messages`, `POST /api/chat/{id}` (SSE streaming).

## Frontend (`roleplay_app/frontend/src/`)

Every visible entity is its own component (no inlined JSX blocks):

- **Shell**: `App.jsx`, `AppHeader`, `BackButton`, `Modal`
- **Home screen**: `CharacterGrid` → `CharacterCard` (+ edit button) / `NewCharacterTile`, `CharacterForm` (shared create/edit)
- **Chat**: `ChatView` (orchestrator) → `ChatBanner`/`PastSessionBanner`, `ChatStatsBar`, `MessageList` → `MessageBubble` → `FormattedMessage`/`ThinkingBlock`/`TypingIndicator`, `ChatInput`, `ChatSettings`, `SessionHistoryPanel`
- **Helpers**: `api.js` (fetch + SSE parsing), `theme.js` (per-character portrait gradient), `formatting.js` (dialogue/action/monologue parsing)

## Features implemented

- Character cards (persona, opening scene trigger, sampling preset, starting stats) — hand-authored JSON or created/edited through the UI (full CRUD, edit button on every card).
- Click a card → hidden trigger message auto-generates the opening scene (never shown to the user, but present in the model's context).
- Structured JSON state per session (location, mood, appearance, memory, affection, closeness, relationship stage, notable facts), updated by the summarizer every 10 messages — an LLM merge, not a scoring formula, with defensive parsing (bad output leaves prior state untouched).
- Two-lever behavior control: plain-language directives (dominant) + small sampling nudges (secondary), both derived from the same state.
- Clear-chat archives the old session and starts a new one seeded from the character's own `initial_state` (not hardcoded zeros) — RAG is a clean slate per session, no cross-session leakage.
- Session history: collapsible panel lists past (archived) sessions; clicking one shows it read-only with a back-to-current button.
- RAG: session-scoped vector search (`sqlite-vec`, query syntax empirically verified — no `JOIN` in the KNN query, that breaks the LIMIT constraint).
- Per-session sampling parameter override popup (temperature/top_p/top_k/min_p), auto-shown on entering a chat, no server restart needed since these are per-request fields.
- Live stats bar (❤️ affection, 🤝 closeness, 🎭 mood, relationship-stage badge).
- Reasoning/thinking block display (collapsible, live-stream only — deliberately **not** persisted to the DB).
- Typing indicator (3 dots) while waiting for the first token, scoped precisely to the in-flight message.
- Dialogue/action/internal-monologue visually distinguished (`*action*` italic, `(monologue)` italic in a dedicated muted tone, plain dialogue normal) — plus a strengthened prompt directive (with a worked example) to stop the model putting dialogue inside asterisks.
- Cream/warm visual-novel-style theme throughout.

## Decisions & constraints worth remembering

- Single llama-server slot — summarization is "non-blocking" in the sense that the triggering turn's response is never delayed, but the very next message can queue briefly behind a summarization call. A second slot is a possible future option if memory headroom is ever confirmed comfortable.
- RAG uses a single upgraded embedding model (`bge-small-en-v1.5`) rather than a hybrid vector+keyword approach — a deliberate simplification after review.
- Declined to author one specific character concept (incest-themed backstory); Ursula was built instead with a husband-wife framing at the user's correction.
- `character_state.py` relationship stages now include user-added `spouse` and `family` (beyond the original stranger/acquaintance/friend/confidant/partner).

## Known gaps

- `CharacterForm.jsx`'s relationship-stage dropdown and `ChatStatsBar.jsx`'s `STAGE_LABELS` haven't been synced with the newer `spouse`/`family` stages yet (flagged, not yet fixed).
- No avatar images — text/gradient portraits only, deliberately out of scope so far.
- Must run uvicorn as a single worker (the summarizer's in-memory concurrency guard is process-local).
- Behavior-directive band thresholds are a starting point, not tuned against real play.

## Verified so far

- llama-server loads and responds correctly at the configured flags (health check, `/v1/models`, `/tokenize`).
- Backend imports cleanly and all 15 routes register (checked after every backend change this session).
- `sqlite-vec` KNN query syntax confirmed empirically (both the working form and the exact `JOIN`-breaks-it bug that shipped once and was fixed).
- Embedding model loads fully offline once cached (timed, no network calls).
- Character creation, opening-scene generation, chat streaming, clear-chat archiving all exercised at least once end-to-end by the user.

## Not yet fully verified

- Full click-through of the newest features (session history panel, settings popup, reasoning display, message formatting) hasn't been confirmed end-to-end by the user in-browser since being built.
- Long-run behavior of the affection/closeness mechanic over many real messages (only spot-checked, not observed across a full extended conversation).

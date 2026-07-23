# Role-Play App — Progress Tracker

Local AI role-playing chat app per `DESIGN.md`, built in this `roleplay_app/` folder (the rest of the parent directory is an unrelated older prototype — untouched). Full architecture/design rationale lives in the approved plan at `C:\Users\sachm\.claude\plans\tranquil-swimming-sphinx.md`; this file tracks build status and decisions made since.

## Stack

- **Backend**: Python/FastAPI (`roleplay_app/backend/`), reusing the root venv at `c:\Users\sachm\Downloads\mistral-12b`.
- **Frontend**: Vite + React (`roleplay_app/frontend/`), built and served directly by the backend — one port, no separate dev server needed in normal use (see "Running it" in `README.md`).
- **Inference**: `llama-server.exe` (`C:\Softwares\llama-cpp-vulkan\`) over its OpenAI-compatible HTTP API, model `gemma-4-E4B-it-uncensored-Q4_K_M.gguf`.
  - Launch: `-c 16384 -np 1 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 --host 127.0.0.1 --port 8080`
  - Single slot deliberately, not two: measured ~15.7GB total RAM, only ~1.86GB free with the model loaded, so summarization shares the chat slot rather than running on a genuinely concurrent second one (see Decisions below).
- **Storage**: SQLite + `sqlite-vec` extension (`roleplay_app/backend/data/app.db`).
- **Embeddings**: `BAAI/bge-small-en-v1.5` (384-dim), loaded fully offline (`HF_HUB_OFFLINE=1`) once cached.
- **Fonts**: Manrope + Cormorant Garamond, downloaded and served as local `.ttf` files (`frontend/public/fonts/`) — no Google Fonts CDN dependency, fully offline.

## Backend (`roleplay_app/backend/`)

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app, all routes (characters, sessions, chat, hide/unhide, avatar upload, debug); mounts the built frontend as static files + SPA catch-all when `frontend/dist/` exists |
| `config.py` | paths, token-budget constants, sampling presets, anti-drift knobs, `UNHIDE_PIN` |
| `db.py` | sqlite3 connection, schema, `sqlite-vec` load, `hidden` columns on sessions |
| `llama_client.py` | async httpx wrapper — `chat_completion()` (streaming + non-streaming), `tokenize()`, `health()`; splits `content` vs `reasoning_content` |
| `context_builder.py` | assembles the per-turn prompt within the token budget; RAG facts tagged with recency ("N messages ago"); director's-note turns get OOC framing applied only at generation time, not in storage |
| `character_state.py` | behavior directives (affection/closeness/stage/mood → plain-language instructions), sampling nudges, global response-style directive, stage-threshold gating |
| `rag.py` | `embed_and_store()`, `retrieve_top_k()` — vector-only, session-scoped |
| `embeddings.py` | `bge-small-en-v1.5` singleton |
| `summarizer.py` | every-N-messages merge into structured JSON state; enforces per-cycle delta cap, numeric stage gate, `character_memory` length truncation post-parse (doesn't trust the model to self-limit) |
| `characters/*.json` | Aria (stranger-start), Ursula (spouse dynamic), Kiara, Rohan (friend dynamic), Professor Sharma |

**Current tuned config** (`config.py`): `GENERATION_HEADROOM_TOKENS=1024`, `SUMMARIZE_EVERY_N_MESSAGES=10`, `MAX_STAT_DELTA_PER_CYCLE=10`, `MAX_CHARACTER_MEMORY_CHARS=600`, `NOTABLE_FACTS_CONSOLIDATE_THRESHOLD=12`.

### API routes (`main.py`)
Characters: `GET/POST /api/characters`, `GET/PUT/DELETE /api/characters/{id}`, `POST /api/characters/{id}/start`, `POST /api/characters/{id}/clear`, `POST /api/avatar`.
Hide/unhide: `POST /api/characters/{id}/hide`, `GET /api/hidden/characters`, `POST /api/hidden/characters/{id}/unhide`, `POST /api/sessions/{id}/hide`, `GET /api/hidden/sessions/{character_id}`, `POST /api/hidden/sessions/{id}/unhide`.
Sessions/chat: `GET /api/characters/{id}/sessions`, `GET /api/sessions/{id}/state`, `GET /api/sessions/{id}/messages`, `GET /api/sessions/{id}/debug`, `POST /api/chat/{id}` (SSE streaming, accepts an optional `director_note`), `POST /api/chat/{id}/regenerate`.
Frontend: catch-all `GET /{path}` serving the built SPA when `frontend/dist/` exists.

## Frontend (`roleplay_app/frontend/src/`)

Every visible entity is its own component (no inlined JSX blocks):

- **Shell**: `App.jsx`, `BackButton`, `Modal`, `LoadingOverlay`
- **Home screen**: `Hero`, `FeaturedRow`, `CharacterGrid` → `CharacterCard` (+ edit/hide buttons) / `NewCharacterTile`, `CharacterForm` (shared create/edit, includes avatar upload via `AvatarCropModal`), `HiddenCharactersPanel` → `PinModal`
- **Chat**: `ChatView` (orchestrator) → `ChatBanner`/`PastSessionBanner`, `ChatStatsBar`, `MessageList` → `MessageBubble` (with per-character avatar, fallback to gradient+initial) / `DirectorNoteDivider` for out-of-character cut markers, `FormattedMessage`/`ThinkingBlock`/`TypingIndicator`, `ChatInput` (message box + director's-note toggle), `ChatSettings`, `SessionHistoryPanel` (past + hidden sessions, PIN-gated unhide), `DebugPanel`
- **Helpers**: `api.js` (fetch + SSE parsing, relative `API_BASE` so it works same-origin regardless of hostname), `theme.js` (per-character portrait gradient/image, stage labels), `formatting.js` (dialogue/action/monologue parsing), `fonts.css` (local `@font-face` declarations)

## Features implemented

- Character cards (persona, opening scene trigger, sampling preset, starting stats) — hand-authored JSON or created/edited through the UI (full CRUD, edit button on every card), with optional avatar image upload + crop.
- Click a card → hidden trigger message auto-generates the opening scene (never shown to the user, but present in the model's context).
- Structured JSON state per session (location, mood, appearance, memory, affection, closeness, relationship stage, notable facts, relationship history), updated by the summarizer every 10 messages — an LLM merge, not a scoring formula, with defensive parsing (bad output leaves prior state untouched) plus code-level enforcement layered on top (see Anti-drift below).
- **Anti-model-drift enforcement** (added after observing unbounded affection/closeness escalation in real play): per-cycle delta cap (±`MAX_STAT_DELTA_PER_CYCLE`) so metrics can't jump in one summarization pass; a numeric stage gate that blocks/reverts a `relationship_stage` advance unless affection/closeness already clear that stage's threshold; `character_memory` truncated at `MAX_CHARACTER_MEMORY_CHARS` on sentence boundaries; affection/closeness clamped to 0–100 post-parse. All enforced in code, not trusted to the model — a tone-ban instruction ("avoid sacred/profound/destiny") was tried first and empirically failed (see Known gaps).
- `relationship_history`: ordered log of *why* the relationship stage changed, appended by the summarizer only on an actual (gate-approved) stage transition.
- Two-lever behavior control: plain-language directives (dominant) + small sampling nudges (secondary), both derived from the same state.
- Clear-chat archives the old session and starts a new one seeded from the character's own `initial_state` (not hardcoded zeros) — RAG is a clean slate per session, no cross-session leakage.
- **Hide/unhide**: both characters and individual sessions can be hidden from their respective lists and restored via a PIN-gated modal (`UNHIDE_PIN`, overridable via `ROLEPLAY_UNHIDE_PIN` env var).
- Session history: collapsible panel lists past (archived) sessions plus a separate hidden-sessions sub-list; clicking one shows it read-only with a back-to-current button.
- RAG: session-scoped vector search (`sqlite-vec`, query syntax empirically verified — no `JOIN` in the KNN query, that breaks the LIMIT constraint). Each retrieved fact is tagged with how long ago it was said (recomputed fresh every turn from the seq gap, not a stored/stale label), and the surrounding prompt text explicitly tells the model these are historical and shouldn't override the live `Current state` block.
- **Director's note**: a manual, one-turn out-of-character steering nudge (🎬 toggle in the chat input). Stored as a real message (`hidden_trigger` role, `visible=1` — distinct from the invisible opening-scene trigger which uses `visible=0`) so it renders as a divider in the chat log and gives the model a concrete turn boundary to react to; the OOC framing ("not something the character says or hears") is applied only when building the model's input, not in what's stored/displayed. Works with or without an accompanying user message.
- Per-session sampling parameter override popup (temperature/top_p/top_k/min_p), auto-shown on entering a chat, no server restart needed since these are per-request fields.
- Live stats bar (❤️ affection, 🤝 closeness, 🎭 mood, relationship-stage badge).
- Reasoning/thinking block display (collapsible, live-stream only — deliberately **not** persisted to the DB).
- Typing indicator (3 dots) while waiting for the first token, scoped precisely to the in-flight message.
- Dialogue/action/internal-monologue visually distinguished (`*action*` italic, `(monologue)` italic in a dedicated muted tone, plain dialogue normal) — plus a strengthened prompt directive (with a worked example) to stop the model putting dialogue inside asterisks.
- Regenerate button to redo the last reply; in-flight generation is properly aborted when switching characters or clearing chat.
- Collapsible debug panel showing the live structured summary state and the exact RAG hits used for the current turn.
- **Firelight design system**: sapphire-black + amber-orange theme (oklch color tokens), three font roles (Manrope sans, Cormorant Garamond serif for headings, Georgia for body text), hero + featured-row + roster home-screen layout, all fonts served locally rather than from a CDN.
- **Frontend served by the backend**: `npm run build` produces `frontend/dist/`, which FastAPI mounts directly (`/assets` static files + SPA catch-all route) — one port (8000) for both API and UI, no CORS configuration needed, works identically whether accessed via `localhost` or `127.0.0.1`. `roleplay_app/run.ps1` activates the venv and starts uvicorn in one step.

## Decisions & constraints worth remembering

- Single llama-server slot — summarization is "non-blocking" in the sense that the triggering turn's response is never delayed, but the very next message can queue briefly behind a summarization call. A second slot is a possible future option if memory headroom is ever confirmed comfortable.
- RAG uses a single upgraded embedding model (`bge-small-en-v1.5`) rather than a hybrid vector+keyword approach — a deliberate simplification after review.
- Declined to author one specific character concept (incest-themed backstory); Ursula was built instead with a husband-wife framing at the user's correction.
- `character_state.py` relationship stages now include user-added `spouse`, `family`, and `taboo` (beyond the original stranger/acquaintance/friend/confidant/partner), each with its own numeric gate threshold in `_STAGE_THRESHOLDS`.
- Tone/melodrama drift at high affection is treated as an **imitation problem, not an instruction-following problem**: the model tends to copy the register already present in its context (persona voice, accumulated `character_memory` prose, verbatim RAG quotes from its own past replies) more reliably than it obeys an abstract "don't use superlatives" instruction. Confirmed empirically twice — the summarizer's tone-ban and a targeted `character_state.py` directive tweak were both tested side-by-side against Kiara's real session state and produced no meaningful difference in output register. No fix has landed yet (see Known gaps); the one mechanism that reliably works for steering tone in the moment is the manual director's note, precisely because it's concrete and singular rather than one more abstract rule competing in an already-stacked prompt.
- CORS middleware was removed entirely once the frontend was consolidated onto the same origin as the API — this means the old dev workflow (separate `npm run dev` on port 5173 talking to the backend on 8000) no longer works without re-adding CORS; for frontend changes, rebuild (`npm run build`) and refresh against port 8000 instead.

## Known gaps

- `CharacterForm.jsx`'s `STAGES` constant (used for the "starting relationship stage" dropdown) still only lists `stranger/acquaintance/friend/confidant/partner` — `spouse`, `family`, and `taboo` can't be picked as a *starting* stage from the UI (they're only reachable via the summarizer advancing into them over time). `theme.js`'s `STAGE_LABELS` is missing a `taboo` entry too (falls back to showing the raw string, not broken, just unstyled). Neither has been fixed yet.
- Melodrama/purple-prose drift at high affection/spouse-tier: confirmed real via side-by-side generation testing, no working fix landed (tone-ban instruction and directive-tweak both failed empirically). Next candidates to try: a few-shot example embedded in the prompt (imitation-based, not instruction-based), or reversing the sampling nudge that currently *increases* `top_p` at affection≥70.
- Mobile responsiveness: no `@media` queries anywhere in `App.css`. Layout is fluid enough (max-width containers, `vw`-capped modals, an auto-fill grid) that it likely doesn't break outright, but it hasn't been visually verified on an actual phone/narrow viewport. Fixed-px Hero title sizing (50px/34px) is a likely rough edge.
- Must run uvicorn as a single worker (the summarizer's in-memory concurrency guard is process-local).
- Behavior-directive band thresholds are a starting point, not tuned against real play.

## Verified so far

- llama-server loads and responds correctly at the configured flags (health check, `/v1/models`, `/tokenize`).
- `sqlite-vec` KNN query syntax confirmed empirically (both the working form and the exact `JOIN`-breaks-it bug that shipped once and was fixed).
- Embedding model loads fully offline once cached (timed, no network calls).
- Character creation, opening-scene generation, chat streaming, clear-chat archiving, avatar upload/crop, hide/unhide (both characters and sessions, including a fixed refresh bug where unhidden sessions didn't reappear until reload), and the director's note (including a fixed bug where a note-only submission with no message silently did nothing) have all been exercised end-to-end.
- Anti-drift enforcement observed directly on Kiara's real session: a summarization cycle showed closeness moving exactly +10 (the delta cap engaging, not an unbounded jump) and affection correctly clamped at the 0–100 ceiling.
- The affection-directive tweak for reducing melodrama was tested via a real side-by-side generation comparison against Kiara's actual state (same test message, old vs. new directive text) — confirmed to make no meaningful difference, ruling it out rather than shipping it on faith.

## Not yet fully verified

- Long-run behavior of the affection/closeness mechanic over many real messages beyond what's been spot-checked so far.
- Mobile/narrow-viewport rendering — not yet checked in an actual mobile browser or emulator.
- Whether reversing the high-affection `top_p` sampling nudge actually reduces melodramatic word choice — flagged as a next experiment, not yet run.

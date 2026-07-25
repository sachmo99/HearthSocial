import asyncio
import json
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import character_state
import config
import context_builder
import db
import llama_client
import rag
import summarizer
from llama_client import LlamaServerUnavailable

app = FastAPI()
# CORS middleware removed since frontend is served from same origin


@app.exception_handler(LlamaServerUnavailable)
async def llama_unavailable_handler(request: Request, exc: LlamaServerUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": "The AI model server is unavailable - make sure llama-server is running."},
    )


@app.on_event("startup")
def startup() -> None:
    conn = db.get_db()
    db.sync_characters_from_disk(conn)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "character"


def _avatar_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


MAX_AVATAR_BYTES = 5 * 1024 * 1024


class CharacterIn(BaseModel):
    name: str
    persona: str
    opening_trigger_template: str
    sampling_preset: str = "balanced"
    character_appearance: str = ""
    default_location: str = ""
    character_affection: int = 20
    character_closeness: int = 10
    relationship_stage: str = "stranger"


class ChatIn(BaseModel):
    message: str
    director_note: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None


class RegenerateIn(BaseModel):
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None


class FeedPostIn(BaseModel):
    character_id: str


class FeedReactIn(BaseModel):
    character_id: str


class FeedCommentIn(BaseModel):
    content: str


def _card_to_initial_state(card: CharacterIn) -> dict:
    return {
        "location": card.default_location,
        "time_of_day": "",
        "character_mood": "neutral",
        "character_appearance": card.character_appearance,
        "character_memory": "",
        "character_affection": card.character_affection,
        "character_closeness": card.character_closeness,
        "relationship_stage": card.relationship_stage,
        "notable_facts": [],
        "relationship_history": [],
        "last_updated_seq": 0,
    }


def _write_character_file(character_id: str, card: CharacterIn, hidden: bool = False) -> Path:
    data = {
        "name": card.name,
        "persona": card.persona,
        "opening_trigger_template": card.opening_trigger_template,
        "sampling_preset": card.sampling_preset,
        "initial_state": _card_to_initial_state(card),
        "hidden": hidden,
    }
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _load_character(character_id: str) -> dict:
    conn = db.get_db()
    row = conn.execute("SELECT file_path FROM characters WHERE id = ?", (character_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="character not found")
    return json.loads(Path(row["file_path"]).read_text(encoding="utf-8"))


def _character_to_form_shape(character: dict) -> dict:
    state = character.get("initial_state", {})
    return {
        "name": character["name"],
        "persona": character["persona"],
        "opening_trigger_template": character["opening_trigger_template"],
        "sampling_preset": character.get("sampling_preset", "balanced"),
        "character_appearance": state.get("character_appearance", ""),
        "default_location": state.get("location", ""),
        "character_affection": state.get("character_affection", 20),
        "character_closeness": state.get("character_closeness", 10),
        "relationship_stage": state.get("relationship_stage", "stranger"),
    }


def _get_summary(conn, session_id: str) -> dict:
    row = conn.execute("SELECT summary_json FROM summaries WHERE session_id = ?", (session_id,)).fetchone()
    return json.loads(row["summary_json"])


def _get_current_state(conn, character_id: str) -> dict:
    active = conn.execute(
        "SELECT id FROM sessions WHERE character_id = ? AND status = 'active'", (character_id,)
    ).fetchone()
    if active:
        return _get_summary(conn, active["id"])
    return _load_character(character_id)["initial_state"]


def _hidden_character_ids(conn) -> set[str]:
    rows = conn.execute("SELECT id, file_path FROM characters").fetchall()
    return {
        r["id"]
        for r in rows
        if json.loads(Path(r["file_path"]).read_text(encoding="utf-8")).get("hidden")
    }


def _build_feed_post_messages(character: dict, state: dict) -> list[dict]:
    directive = character_state.build_behavior_directive(state)
    facts = state.get("notable_facts", [])[:3]
    grounding = f"Current location: {state.get('location') or 'unknown'}."
    if facts:
        grounding += " Recent notable facts: " + "; ".join(facts) + "."
    system_text = (
        f"{character['persona']}\n\n{character_state.FEED_POST_STYLE_DIRECTIVE}\n\n{directive}\n\n{grounding}"
    )
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": "Write a new social media post now."},
    ]


def _build_feed_reaction_messages(character: dict, state: dict, author_name: str, post_content: str) -> list[dict]:
    directive = character_state.build_behavior_directive(state)
    system_text = f"{character['persona']}\n\n{character_state.FEED_POST_STYLE_DIRECTIVE}\n\n{directive}"
    user_text = (
        f'Here is a post by {author_name}: "{post_content}"\n\n'
        "Write a brief in-character reaction/comment to this post (1-2 sentences)."
    )
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_text},
    ]


def _insert_message(conn, session_id: str, role: str, content: str, visible: int, token_count: int | None = None) -> tuple[int, int]:
    seq_row = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()
    seq = seq_row["max_seq"] + 1
    cur = conn.execute(
        "INSERT INTO messages (session_id, seq, role, content, visible, token_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, seq, role, content, visible, token_count, db.now_iso()),
    )
    conn.commit()
    return cur.lastrowid, seq


async def _generate_turn(conn, session: dict, character: dict, summary: dict) -> dict:
    messages = await context_builder.build(conn, session, character, summary)
    sampling_params = character_state.compute_sampling_params(character["sampling_preset"], summary)
    return await llama_client.chat_completion(messages, sampling_params, stream=False)


def _apply_overrides(sampling_params: dict, overrides) -> dict:
    if overrides.temperature is not None:
        sampling_params["temperature"] = overrides.temperature
    if overrides.top_p is not None:
        sampling_params["top_p"] = overrides.top_p
    if overrides.top_k is not None:
        sampling_params["top_k"] = overrides.top_k
    if overrides.min_p is not None:
        sampling_params["min_p"] = overrides.min_p
    return sampling_params


def _stream_assistant_reply(conn, session_id: str, messages: list[dict], sampling_params: dict) -> StreamingResponse:
    async def event_stream():
        content_parts = []
        try:
            async for chunk in llama_client.chat_completion(messages, sampling_params, stream=True):
                if chunk["type"] == "content":
                    content_parts.append(chunk["text"])
                yield f"data: {json.dumps({'type': chunk['type'], 'delta': chunk['text']})}\n\n"
        except LlamaServerUnavailable:
            # Headers are already sent at this point, so we can't switch to a 503 - end the
            # SSE stream cleanly instead of letting the connection error propagate unhandled.
            yield f"data: {json.dumps({'type': 'error', 'delta': ' [Connection to the model server was lost.]'})}\n\n"
            if not content_parts:
                yield "data: [DONE]\n\n"
                return

        reply = "".join(content_parts)
        try:
            reply_tokens = await llama_client.tokenize(reply)
        except LlamaServerUnavailable:
            reply_tokens = None
        reply_id, reply_seq = _insert_message(conn, session_id, "assistant", reply, visible=1, token_count=reply_tokens)
        rag.embed_and_store(conn, reply_id, session_id, reply)

        if summarizer.should_trigger(conn, session_id, reply_seq):
            asyncio.create_task(summarizer.run(session_id))

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/stages")
def list_stages():
    return character_state.stage_options()


@app.get("/api/health")
async def health_check():
    ok = await llama_client.health()
    return {"llama_server": ok}


@app.get("/api/characters")
def list_characters():
    conn = db.get_db()
    rows = conn.execute("SELECT id, name, file_path FROM characters ORDER BY name").fetchall()
    result = []
    for r in rows:
        card = json.loads(Path(r["file_path"]).read_text(encoding="utf-8"))
        if card.get("hidden"):
            continue
        state = card.get("initial_state", {})
        result.append({
            "id": r["id"],
            "name": r["name"],
            "persona": card.get("persona", ""),
            "relationship_stage": state.get("relationship_stage", "stranger"),
        })
    return result


@app.get("/api/hidden/characters")
def list_hidden_characters():
    conn = db.get_db()
    rows = conn.execute("SELECT id, name, file_path FROM characters ORDER BY name").fetchall()
    result = []
    for r in rows:
        card = json.loads(Path(r["file_path"]).read_text(encoding="utf-8"))
        if card.get("hidden"):
            result.append({"id": r["id"], "name": r["name"]})
    return result


class UnhideIn(BaseModel):
    pin: str


@app.post("/api/characters/{character_id}/hide")
def hide_character(character_id: str):
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="character not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hidden"] = True
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True}


@app.post("/api/hidden/characters/{character_id}/unhide")
def unhide_character(character_id: str, body: UnhideIn):
    if body.pin != config.UNHIDE_PIN:
        raise HTTPException(status_code=403, detail="incorrect PIN")
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="character not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hidden"] = False
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True}


@app.get("/api/characters/{character_id}")
def get_character(character_id: str):
    return _character_to_form_shape(_load_character(character_id))


@app.post("/api/characters")
def create_character(card: CharacterIn):
    conn = db.get_db()
    character_id = _slugify(card.name)
    base_id = character_id
    i = 2
    while (config.CHARACTERS_DIR / f"{character_id}.json").exists():
        character_id = f"{base_id}-{i}"
        i += 1
    path = _write_character_file(character_id, card)
    db.upsert_character(conn, character_id, card.name, str(path))
    return {"id": character_id}


@app.put("/api/characters/{character_id}")
def update_character(character_id: str, card: CharacterIn):
    conn = db.get_db()
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="character not found")
    existing_hidden = json.loads(path.read_text(encoding="utf-8")).get("hidden", False)
    _write_character_file(character_id, card, hidden=existing_hidden)
    db.upsert_character(conn, character_id, card.name, str(path))
    return {"id": character_id}


@app.delete("/api/characters/{character_id}")
def delete_character(character_id: str):
    conn = db.get_db()
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM sessions WHERE character_id = ?", (character_id,)
    ).fetchone()["n"]
    if count > 0:
        raise HTTPException(status_code=409, detail="character has existing sessions; cannot delete")
    feed_count = conn.execute(
        "SELECT COUNT(*) AS n FROM feed_posts WHERE character_id = ?", (character_id,)
    ).fetchone()["n"]
    if feed_count > 0:
        raise HTTPException(status_code=409, detail="character has existing feed posts; cannot delete")
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if path.exists():
        path.unlink()
    conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
    conn.commit()
    return {"ok": True}


@app.post("/api/avatar")
async def upload_avatar(name: str = Form(...), file: UploadFile = File(...)):
    if file.content_type != "image/png":
        raise HTTPException(status_code=400, detail="avatar must be a PNG image")
    data = await file.read()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="image too large")
    slug = _avatar_slug(name)
    if not slug:
        raise HTTPException(status_code=400, detail="invalid character name")
    config.PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    (config.PORTRAITS_DIR / f"{slug}.png").write_bytes(data)
    return {"ok": True}


@app.post("/api/characters/{character_id}/start")
async def start_character(character_id: str):
    conn = db.get_db()
    character = _load_character(character_id)

    active = conn.execute(
        "SELECT id FROM sessions WHERE character_id = ? AND status = 'active'", (character_id,)
    ).fetchone()
    if active:
        return {"session_id": active["id"]}

    session_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (id, character_id, status, created_at) VALUES (?, ?, 'active', ?)",
        (session_id, character_id, db.now_iso()),
    )
    conn.execute(
        "INSERT INTO summaries (session_id, summary_json, last_summarized_seq, updated_at) VALUES (?, ?, 0, ?)",
        (session_id, json.dumps(character["initial_state"]), db.now_iso()),
    )
    conn.commit()

    session = {"id": session_id}
    trigger_text = character["opening_trigger_template"]
    trigger_tokens = await llama_client.tokenize(trigger_text)
    message_id, _ = _insert_message(conn, session_id, "hidden_trigger", trigger_text, visible=0, token_count=trigger_tokens)
    rag.embed_and_store(conn, message_id, session_id, trigger_text)

    summary = _get_summary(conn, session_id)
    result = await _generate_turn(conn, session, character, summary)
    reply = result["content"]
    reply_tokens = await llama_client.tokenize(reply)
    reply_id, _ = _insert_message(conn, session_id, "assistant", reply, visible=1, token_count=reply_tokens)
    rag.embed_and_store(conn, reply_id, session_id, reply)

    return {"session_id": session_id}


@app.get("/api/characters/{character_id}/sessions")
def list_sessions(character_id: str):
    conn = db.get_db()
    rows = conn.execute(
        """
        SELECT s.id, s.status, s.created_at, s.archived_at,
               (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id AND m.visible = 1) AS message_count
        FROM sessions s
        WHERE s.character_id = ? AND s.hidden = 0
        ORDER BY s.created_at DESC
        """,
        (character_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "status": r["status"],
            "created_at": r["created_at"],
            "archived_at": r["archived_at"],
            "message_count": r["message_count"],
        }
        for r in rows
    ]


@app.get("/api/hidden/sessions/{character_id}")
def list_hidden_sessions(character_id: str):
    conn = db.get_db()
    rows = conn.execute(
        """
        SELECT s.id, s.status, s.created_at, s.archived_at,
               (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id AND m.visible = 1) AS message_count
        FROM sessions s
        WHERE s.character_id = ? AND s.hidden = 1
        ORDER BY s.created_at DESC
        """,
        (character_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "status": r["status"],
            "created_at": r["created_at"],
            "archived_at": r["archived_at"],
            "message_count": r["message_count"],
        }
        for r in rows
    ]


@app.post("/api/sessions/{session_id}/hide")
def hide_session(session_id: str):
    conn = db.get_db()
    row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    conn.execute("UPDATE sessions SET hidden = 1 WHERE id = ?", (session_id,))
    conn.commit()
    return {"ok": True}


@app.post("/api/hidden/sessions/{session_id}/unhide")
def unhide_session(session_id: str, body: UnhideIn):
    if body.pin != config.UNHIDE_PIN:
        raise HTTPException(status_code=403, detail="incorrect PIN")
    conn = db.get_db()
    row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    conn.execute("UPDATE sessions SET hidden = 0 WHERE id = ?", (session_id,))
    conn.commit()
    return {"ok": True}


@app.post("/api/characters/{character_id}/clear")
def clear_chat(character_id: str):
    conn = db.get_db()
    active = conn.execute(
        "SELECT id FROM sessions WHERE character_id = ? AND status = 'active'", (character_id,)
    ).fetchone()
    if active:
        conn.execute(
            "UPDATE sessions SET status = 'archived', archived_at = ? WHERE id = ?",
            (db.now_iso(), active["id"]),
        )
        conn.commit()
    return {"ok": True}


@app.get("/api/feed")
def list_feed():
    conn = db.get_db()
    hidden_ids = _hidden_character_ids(conn)
    rows = conn.execute(
        """
        SELECT f.id, f.character_id, c.name AS character_name, f.parent_id, f.author_type, f.content, f.created_at
        FROM feed_posts f
        LEFT JOIN characters c ON c.id = f.character_id
        ORDER BY f.created_at
        """
    ).fetchall()
    return [
        {
            "id": r["id"],
            "character_id": r["character_id"],
            "character_name": r["character_name"],
            "parent_id": r["parent_id"],
            "author_type": r["author_type"],
            "content": r["content"],
            "created_at": r["created_at"],
        }
        for r in rows
        if r["character_id"] not in hidden_ids
    ]


@app.post("/api/feed/posts")
async def create_feed_post(body: FeedPostIn):
    conn = db.get_db()
    if body.character_id in _hidden_character_ids(conn):
        raise HTTPException(status_code=404, detail="character not found")
    character = _load_character(body.character_id)
    state = _get_current_state(conn, body.character_id)
    messages = _build_feed_post_messages(character, state)
    sampling_params = character_state.compute_sampling_params(character["sampling_preset"], state)
    result = await llama_client.chat_completion(messages, sampling_params, stream=False, timeout=300.0)
    content = result["content"].strip()
    cur = conn.execute(
        "INSERT INTO feed_posts (character_id, parent_id, author_type, content, created_at) VALUES (?, NULL, 'character', ?, ?)",
        (body.character_id, content, db.now_iso()),
    )
    conn.commit()
    return {"id": cur.lastrowid, "content": content}


@app.post("/api/feed/posts/{post_id}/react")
async def react_to_feed_post(post_id: int, body: FeedReactIn):
    conn = db.get_db()
    post = conn.execute(
        """
        SELECT f.id, f.parent_id, f.author_type, f.character_id, f.content, c.name AS character_name
        FROM feed_posts f LEFT JOIN characters c ON c.id = f.character_id
        WHERE f.id = ?
        """,
        (post_id,),
    ).fetchone()
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    if post["parent_id"] is not None:
        raise HTTPException(status_code=400, detail="cannot react to a comment")
    if body.character_id == post["character_id"]:
        raise HTTPException(status_code=400, detail="a character cannot react to their own post")
    if body.character_id in _hidden_character_ids(conn):
        raise HTTPException(status_code=404, detail="character not found")

    character = _load_character(body.character_id)
    state = _get_current_state(conn, body.character_id)
    messages = _build_feed_reaction_messages(character, state, post["character_name"], post["content"])
    sampling_params = character_state.compute_sampling_params(character["sampling_preset"], state)
    result = await llama_client.chat_completion(messages, sampling_params, stream=False, timeout=300.0)
    content = result["content"].strip()
    cur = conn.execute(
        "INSERT INTO feed_posts (character_id, parent_id, author_type, content, created_at) VALUES (?, ?, 'character', ?, ?)",
        (body.character_id, post_id, content, db.now_iso()),
    )
    conn.commit()
    return {"id": cur.lastrowid, "content": content}


@app.post("/api/feed/posts/{post_id}/comments")
def comment_on_feed_post(post_id: int, body: FeedCommentIn):
    conn = db.get_db()
    post = conn.execute("SELECT id, parent_id FROM feed_posts WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    if post["parent_id"] is not None:
        raise HTTPException(status_code=400, detail="cannot comment on a comment")
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    cur = conn.execute(
        "INSERT INTO feed_posts (character_id, parent_id, author_type, content, created_at) VALUES (NULL, ?, 'user', ?, ?)",
        (post_id, content, db.now_iso()),
    )
    conn.commit()
    return {"id": cur.lastrowid}


@app.get("/api/sessions/{session_id}/debug")
def get_session_debug(session_id: str):
    conn = db.get_db()
    session_row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")

    summary = _get_summary(conn, session_id)

    all_rows = conn.execute(
        "SELECT seq, content FROM messages WHERE session_id = ? ORDER BY seq DESC", (session_id,)
    ).fetchall()
    if not all_rows:
        return {"summary": summary, "rag_hits": []}

    query_text = all_rows[0]["content"]
    recent_seqs = {r["seq"] for r in all_rows[: config.RECENT_MESSAGE_CAP]}
    rag_hits = rag.retrieve_top_k(conn, session_id, query_text, exclude_seqs=recent_seqs)

    return {"summary": summary, "rag_hits": rag_hits}


@app.get("/api/sessions/{session_id}/state")
def get_session_state(session_id: str):
    conn = db.get_db()
    session_row = conn.execute(
        "SELECT character_id FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    character = _load_character(session_row["character_id"])
    summary = _get_summary(conn, session_id)

    last_summarized_seq = conn.execute(
        "SELECT last_summarized_seq FROM summaries WHERE session_id = ?", (session_id,)
    ).fetchone()["last_summarized_seq"]
    latest_seq = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()["max_seq"]
    messages_until_summary = max(0, config.SUMMARIZE_EVERY_N_MESSAGES - (latest_seq - last_summarized_seq))

    return {
        "character_affection": summary.get("character_affection", 0),
        "character_closeness": summary.get("character_closeness", 0),
        "character_mood": summary.get("character_mood", ""),
        "relationship_stage": summary.get("relationship_stage", "stranger"),
        "sampling_params": character_state.compute_sampling_params(character["sampling_preset"], summary),
        "messages_until_summary": messages_until_summary,
        "summarizing": session_id in summarizer.RUNNING,
    }


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT role, content, seq FROM messages WHERE session_id = ? AND visible = 1 ORDER BY seq", (session_id,)
    ).fetchall()
    return [{"role": r["role"], "content": r["content"], "seq": r["seq"]} for r in rows]


@app.post("/api/chat/{session_id}")
async def chat(session_id: str, body: ChatIn):
    conn = db.get_db()
    session_row = conn.execute(
        "SELECT id, character_id, status FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session_row["status"] != "active":
        raise HTTPException(status_code=409, detail="session is archived")

    character = _load_character(session_row["character_id"])
    session = {"id": session_id}

    if body.message.strip():
        user_tokens = await llama_client.tokenize(body.message)
        user_msg_id, _ = _insert_message(conn, session_id, "user", body.message, visible=1, token_count=user_tokens)
        rag.embed_and_store(conn, user_msg_id, session_id, body.message)

    note = (body.director_note or "").strip()
    if note:
        note_tokens = await llama_client.tokenize(note)
        _insert_message(conn, session_id, "hidden_trigger", note, visible=1, token_count=note_tokens)

    summary = _get_summary(conn, session_id)
    messages = await context_builder.build(conn, session, character, summary)
    sampling_params = _apply_overrides(character_state.compute_sampling_params(character["sampling_preset"], summary), body)

    return _stream_assistant_reply(conn, session_id, messages, sampling_params)


@app.post("/api/chat/{session_id}/regenerate")
async def regenerate(session_id: str, body: RegenerateIn):
    conn = db.get_db()
    session_row = conn.execute(
        "SELECT id, character_id, status FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session_row["status"] != "active":
        raise HTTPException(status_code=409, detail="session is archived")

    character = _load_character(session_row["character_id"])
    session = {"id": session_id}

    last_row = conn.execute(
        "SELECT id, role FROM messages WHERE session_id = ? ORDER BY seq DESC LIMIT 1", (session_id,)
    ).fetchone()
    if last_row is None:
        raise HTTPException(status_code=409, detail="no messages to regenerate a reply for")
    if last_row["role"] == "assistant":
        conn.execute("DELETE FROM message_vectors WHERE message_id = ?", (last_row["id"],))
        conn.execute("DELETE FROM messages WHERE id = ?", (last_row["id"],))
        conn.commit()

    summary = _get_summary(conn, session_id)
    messages = await context_builder.build(conn, session, character, summary)
    sampling_params = _apply_overrides(character_state.compute_sampling_params(character["sampling_preset"], summary), body)

    return _stream_assistant_reply(conn, session_id, messages, sampling_params)


# Serve built frontend static files
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Serve index.html for all routes except /api and /assets
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        file_path = frontend_dist / path if path else frontend_dist / "index.html"
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")

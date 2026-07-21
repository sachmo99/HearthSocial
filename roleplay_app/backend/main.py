import asyncio
import json
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import character_state
import config
import context_builder
import db
import llama_client
import rag
import summarizer

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    conn = db.get_db()
    db.sync_characters_from_disk(conn)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "character"


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
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None


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
        "last_updated_seq": 0,
    }


def _write_character_file(character_id: str, card: CharacterIn) -> Path:
    data = {
        "name": card.name,
        "persona": card.persona,
        "opening_trigger_template": card.opening_trigger_template,
        "sampling_preset": card.sampling_preset,
        "initial_state": _card_to_initial_state(card),
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


@app.get("/api/characters")
def list_characters():
    conn = db.get_db()
    rows = conn.execute("SELECT id, name FROM characters ORDER BY name").fetchall()
    return [{"id": r["id"], "name": r["name"]} for r in rows]


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
    _write_character_file(character_id, card)
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
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if path.exists():
        path.unlink()
    conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))
    conn.commit()
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
        WHERE s.character_id = ?
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

    user_tokens = await llama_client.tokenize(body.message)
    user_msg_id, _ = _insert_message(conn, session_id, "user", body.message, visible=1, token_count=user_tokens)
    rag.embed_and_store(conn, user_msg_id, session_id, body.message)

    summary = _get_summary(conn, session_id)
    messages = await context_builder.build(conn, session, character, summary)
    sampling_params = character_state.compute_sampling_params(character["sampling_preset"], summary)
    if body.temperature is not None:
        sampling_params["temperature"] = body.temperature
    if body.top_p is not None:
        sampling_params["top_p"] = body.top_p
    if body.top_k is not None:
        sampling_params["top_k"] = body.top_k
    if body.min_p is not None:
        sampling_params["min_p"] = body.min_p

    async def event_stream():
        content_parts = []
        async for chunk in llama_client.chat_completion(messages, sampling_params, stream=True):
            if chunk["type"] == "content":
                content_parts.append(chunk["text"])
            yield f"data: {json.dumps({'type': chunk['type'], 'delta': chunk['text']})}\n\n"

        reply = "".join(content_parts)
        reply_tokens = await llama_client.tokenize(reply)
        reply_id, reply_seq = _insert_message(conn, session_id, "assistant", reply, visible=1, token_count=reply_tokens)
        rag.embed_and_store(conn, reply_id, session_id, reply)

        if summarizer.should_trigger(conn, session_id, reply_seq):
            asyncio.create_task(summarizer.run(session_id))

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

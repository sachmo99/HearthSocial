import json
import uuid

from fastapi import APIRouter, HTTPException

import character_state
import config
import context_builder
import db
import llama_client
import rag
import shared
import summarizer

router = APIRouter(prefix="/api")


async def _generate_turn(conn, session: dict, character: dict, summary: dict) -> dict:
    messages = await context_builder.build(conn, session, character, summary)
    sampling_params = character_state.compute_sampling_params(character["sampling_preset"], summary)
    return await llama_client.chat_completion(messages, sampling_params, stream=False)


@router.post("/characters/{character_id}/start")
async def start_character(character_id: str):
    conn = db.get_db()
    character = shared.load_character(character_id)

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
    message_id, _ = shared.insert_message(conn, session_id, "hidden_trigger", trigger_text, visible=0, token_count=trigger_tokens)
    rag.embed_and_store(conn, message_id, session_id, trigger_text)

    summary = shared.get_summary(conn, session_id)
    result = await _generate_turn(conn, session, character, summary)
    reply = result["content"]
    reply_tokens = await llama_client.tokenize(reply)
    reply_id, _ = shared.insert_message(conn, session_id, "assistant", reply, visible=1, token_count=reply_tokens)
    rag.embed_and_store(conn, reply_id, session_id, reply)

    return {"session_id": session_id}


@router.get("/characters/{character_id}/sessions")
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


@router.get("/hidden/sessions/{character_id}")
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


@router.post("/sessions/{session_id}/hide")
def hide_session(session_id: str):
    conn = db.get_db()
    row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    conn.execute("UPDATE sessions SET hidden = 1 WHERE id = ?", (session_id,))
    conn.commit()
    return {"ok": True}


@router.post("/hidden/sessions/{session_id}/unhide")
def unhide_session(session_id: str, body: shared.UnhideIn):
    if body.pin != config.UNHIDE_PIN:
        raise HTTPException(status_code=403, detail="incorrect PIN")
    conn = db.get_db()
    row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    conn.execute("UPDATE sessions SET hidden = 0 WHERE id = ?", (session_id,))
    conn.commit()
    return {"ok": True}


@router.post("/characters/{character_id}/clear")
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


@router.get("/sessions/{session_id}/debug")
def get_session_debug(session_id: str):
    conn = db.get_db()
    session_row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")

    summary = shared.get_summary(conn, session_id)

    all_rows = conn.execute(
        "SELECT seq, content FROM messages WHERE session_id = ? ORDER BY seq DESC", (session_id,)
    ).fetchall()
    if not all_rows:
        return {"summary": summary, "rag_hits": []}

    query_text = all_rows[0]["content"]
    recent_seqs = {r["seq"] for r in all_rows[: config.RECENT_MESSAGE_CAP]}
    rag_hits = rag.retrieve_top_k(conn, session_id, query_text, exclude_seqs=recent_seqs)

    return {"summary": summary, "rag_hits": rag_hits}


@router.get("/sessions/{session_id}/state")
def get_session_state(session_id: str):
    conn = db.get_db()
    session_row = conn.execute(
        "SELECT character_id FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    character = shared.load_character(session_row["character_id"])
    summary = shared.get_summary(conn, session_id)

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


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str):
    conn = db.get_db()
    rows = conn.execute(
        "SELECT role, content, seq FROM messages WHERE session_id = ? AND visible = 1 ORDER BY seq", (session_id,)
    ).fetchall()
    return [{"role": r["role"], "content": r["content"], "seq": r["seq"]} for r in rows]

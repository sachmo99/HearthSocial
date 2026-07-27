import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import character_state
import context_builder
import db
import llama_client
import rag
import shared
import summarizer
from llama_client import LlamaServerUnavailable

router = APIRouter(prefix="/api")


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
        reply_id, reply_seq = shared.insert_message(conn, session_id, "assistant", reply, visible=1, token_count=reply_tokens)
        rag.embed_and_store(conn, reply_id, session_id, reply)

        if summarizer.should_trigger(conn, session_id, reply_seq):
            asyncio.create_task(summarizer.run(session_id))

        # The client's optimistic placeholder message has no real id until this point - hand it
        # back directly instead of making the frontend refetch the whole message list to learn it.
        yield f"data: {json.dumps({'type': 'message_id', 'message_id': reply_id})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chat/{session_id}")
async def chat(session_id: str, body: ChatIn):
    conn = db.get_db()
    session_row = conn.execute(
        "SELECT id, character_id, status FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session_row["status"] != "active":
        raise HTTPException(status_code=409, detail="session is archived")

    character = shared.load_character(session_row["character_id"])
    session = {"id": session_id}

    if body.message.strip():
        user_tokens = await llama_client.tokenize(body.message)
        user_msg_id, _ = shared.insert_message(conn, session_id, "user", body.message, visible=1, token_count=user_tokens)
        rag.embed_and_store(conn, user_msg_id, session_id, body.message)

    note = (body.director_note or "").strip()
    if note:
        note_tokens = await llama_client.tokenize(note)
        shared.insert_message(conn, session_id, "hidden_trigger", note, visible=1, token_count=note_tokens)

    summary = shared.get_summary(conn, session_id)
    messages = await context_builder.build(conn, session, character, summary)
    sampling_params = _apply_overrides(character_state.compute_sampling_params(character["sampling_preset"], summary), body)

    return _stream_assistant_reply(conn, session_id, messages, sampling_params)


_SUGGEST_REPLY_SAMPLING = {"temperature": 0.8, "top_p": 0.95, "top_k": 60, "min_p": 0.05}


@router.post("/sessions/{session_id}/suggest-reply")
async def suggest_reply(session_id: str):
    """Suggests what the *user* (not the character) might say next, read from the last 10
    visible messages - fills the input box for review, never sent automatically."""
    conn = db.get_db()
    session_row = conn.execute("SELECT id, character_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")

    character = shared.load_character(session_row["character_id"])
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? AND visible = 1 ORDER BY seq DESC LIMIT 10",
        (session_id,),
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=409, detail="no conversation yet to suggest a reply from")
    rows = list(reversed(rows))

    transcript = "\n".join(f"{'User' if r['role'] == 'user' else character['name']}: {r['content']}" for r in rows)
    # Reuses the exact same *action*/dialogue/(monologue) convention as character_state's
    # RESPONSE_STYLE_DIRECTIVE, so the suggested user line matches the register the rest of the
    # conversation is already written in, instead of a flat one-line message with no emotional weight.
    system_text = (
        f"[System: Based on the recent exchange below between the user and {character['name']}, write a strong, "
        f"emotionally engaged next message for the USER to send - in first person, as if the user is typing it "
        f"themselves, reacting genuinely to what {character['name']} just said or did. "
        "Use the same formatting convention as the rest of this roleplay: *asterisks* for physical actions/"
        "narration, plain text for spoken dialogue, and (parentheses) for internal monologue - combine at least "
        "two of these (e.g. an action plus dialogue, or dialogue plus a monologue aside) so the reply carries "
        "real emotional weight rather than being a flat, generic line. Keep it to 2-4 sentences total. "
        "Output only the suggested message text, nothing else - no quotes around the whole thing, no labels, "
        "no explanation.]"
    )
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": transcript},
    ]
    result = await llama_client.chat_completion(messages, _SUGGEST_REPLY_SAMPLING, stream=False)
    return {"suggestion": result["content"].strip()}


@router.post("/chat/{session_id}/regenerate")
async def regenerate(session_id: str, body: RegenerateIn):
    conn = db.get_db()
    session_row = conn.execute(
        "SELECT id, character_id, status FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session_row["status"] != "active":
        raise HTTPException(status_code=409, detail="session is archived")

    character = shared.load_character(session_row["character_id"])
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

    summary = shared.get_summary(conn, session_id)
    messages = await context_builder.build(conn, session, character, summary)
    sampling_params = _apply_overrides(character_state.compute_sampling_params(character["sampling_preset"], summary), body)

    return _stream_assistant_reply(conn, session_id, messages, sampling_params)

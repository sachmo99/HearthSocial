import json
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

import db


class UnhideIn(BaseModel):
    pin: str


def load_character(character_id: str) -> dict:
    conn = db.get_db()
    row = conn.execute("SELECT file_path FROM characters WHERE id = ?", (character_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="character not found")
    return json.loads(Path(row["file_path"]).read_text(encoding="utf-8"))


def get_summary(conn, session_id: str) -> dict:
    row = conn.execute("SELECT summary_json FROM summaries WHERE session_id = ?", (session_id,)).fetchone()
    return json.loads(row["summary_json"])


def get_current_state(conn, character_id: str) -> dict:
    active = conn.execute(
        "SELECT id FROM sessions WHERE character_id = ? AND status = 'active'", (character_id,)
    ).fetchone()
    if active:
        return get_summary(conn, active["id"])
    return load_character(character_id)["initial_state"]


def hidden_character_ids(conn) -> set[str]:
    rows = conn.execute("SELECT id, file_path FROM characters").fetchall()
    return {
        r["id"]
        for r in rows
        if json.loads(Path(r["file_path"]).read_text(encoding="utf-8")).get("hidden")
    }


def insert_message(conn, session_id: str, role: str, content: str, visible: int, token_count: int | None = None) -> tuple[int, int]:
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

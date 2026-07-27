import json
import re
from pathlib import Path

from fastapi import HTTPException
from PIL import Image
from pydantic import BaseModel

import config
import db


class UnhideIn(BaseModel):
    pin: str


def avatar_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


PORTRAIT_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
SMALL_PORTRAIT_SUFFIX = "-sm"
SMALL_PORTRAIT_WIDTH = 500


def resolve_portrait_path(slug: str) -> Path | None:
    for ext in PORTRAIT_EXTENSIONS:
        path = config.PORTRAITS_DIR / f"{slug}.{ext}"
        if path.is_file():
            return path
    # No dedicated small variant (e.g. an older upload, or a character whose source
    # image was never larger than the small size to begin with) - the base image
    # doubles as its own 1x version.
    if slug.endswith(SMALL_PORTRAIT_SUFFIX):
        return resolve_portrait_path(slug[: -len(SMALL_PORTRAIT_SUFFIX)])
    return None


def write_small_portrait(slug: str, ext: str) -> None:
    base_path = config.PORTRAITS_DIR / f"{slug}.{ext}"
    with Image.open(base_path) as im:
        if im.width <= SMALL_PORTRAIT_WIDTH:
            # Base image is already small enough - the resolve_portrait_path fallback
            # will serve it for the 1x request too, no separate file needed.
            return
        new_height = round(im.height * SMALL_PORTRAIT_WIDTH / im.width)
        im = im.convert("RGB").resize((SMALL_PORTRAIT_WIDTH, new_height), Image.LANCZOS)
        im.save(config.PORTRAITS_DIR / f"{slug}{SMALL_PORTRAIT_SUFFIX}.jpg", "JPEG", quality=88)


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

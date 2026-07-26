import json
import re
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

import character_state
import config
import db
import shared

router = APIRouter(prefix="/api")

MAX_AVATAR_BYTES = 5 * 1024 * 1024
AVATAR_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg"}


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


@router.get("/stages")
def list_stages():
    return character_state.stage_options()


@router.get("/characters")
def list_characters():
    conn = db.get_db()
    rows = conn.execute(
        """
        SELECT c.id, c.name, c.file_path, COUNT(m.id) AS message_count
        FROM characters c
        LEFT JOIN sessions s ON s.character_id = c.id
        LEFT JOIN messages m ON m.session_id = s.id
        GROUP BY c.id
        ORDER BY c.name
        """
    ).fetchall()
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
            "message_count": r["message_count"],
        })
    return result


@router.get("/hidden/characters")
def list_hidden_characters():
    conn = db.get_db()
    rows = conn.execute("SELECT id, name, file_path FROM characters ORDER BY name").fetchall()
    result = []
    for r in rows:
        card = json.loads(Path(r["file_path"]).read_text(encoding="utf-8"))
        if card.get("hidden"):
            result.append({"id": r["id"], "name": r["name"]})
    return result


@router.post("/characters/{character_id}/hide")
def hide_character(character_id: str):
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="character not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hidden"] = True
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True}


@router.post("/hidden/characters/{character_id}/unhide")
def unhide_character(character_id: str, body: shared.UnhideIn):
    if body.pin != config.UNHIDE_PIN:
        raise HTTPException(status_code=403, detail="incorrect PIN")
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="character not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hidden"] = False
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True}


@router.get("/characters/{character_id}")
def get_character(character_id: str):
    return _character_to_form_shape(shared.load_character(character_id))


@router.post("/characters")
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


@router.put("/characters/{character_id}")
def update_character(character_id: str, card: CharacterIn):
    conn = db.get_db()
    path = config.CHARACTERS_DIR / f"{character_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="character not found")
    existing_hidden = json.loads(path.read_text(encoding="utf-8")).get("hidden", False)
    _write_character_file(character_id, card, hidden=existing_hidden)
    db.upsert_character(conn, character_id, card.name, str(path))
    return {"id": character_id}


@router.delete("/characters/{character_id}")
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


@router.post("/avatar")
async def upload_avatar(name: str = Form(...), file: UploadFile = File(...)):
    ext = AVATAR_EXTENSIONS.get(file.content_type)
    if not ext:
        raise HTTPException(status_code=400, detail="avatar must be a PNG or JPEG image")
    data = await file.read()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="image too large")
    slug = shared.avatar_slug(name)
    if not slug:
        raise HTTPException(status_code=400, detail="invalid character name")
    config.PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    (config.PORTRAITS_DIR / f"{slug}.{ext}").write_bytes(data)
    return {"ok": True}

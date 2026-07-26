from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import character_state
import config
import db
import image_client
import llama_client
import shared

router = APIRouter()

_MODERATION_SYSTEM_PROMPT = (
    "[System: Rewrite the following image-generation prompt so it contains no nudity or exposed intimate "
    "body parts, and no depiction of explicit sexual acts. Swimwear, bikinis, and other attire are allowed "
    "and should be kept exactly as described - do not sanitize clothing, suggestive mood, or romantic "
    "tension. Only remove or rephrase content describing nudity or explicit sexual activity, while "
    "preserving everything else - setting, character description, mood, and visual composition - as "
    "closely as possible. Output only the rewritten prompt text, nothing else.]"
)
_MODERATION_SAMPLING_PARAMS = {"temperature": 0.3, "top_p": 0.9, "top_k": 40, "min_p": 0.05}


async def _neutralize_prompt(prompt: str) -> str:
    if not config.IMAGE_MODERATION_ENABLED:
        return prompt
    messages = [
        {"role": "system", "content": _MODERATION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    result = await llama_client.chat_completion(messages, _MODERATION_SAMPLING_PARAMS, stream=False)
    return result["content"].strip() or prompt


def _save_and_record(conn, character_id: str, message_id, feed_post_id, filename: str, prompt: str, data: bytes) -> str:
    config.GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.GENERATED_IMAGES_DIR / filename
    path.write_bytes(data)

    if message_id is not None:
        conn.execute("DELETE FROM generated_images WHERE message_id = ?", (message_id,))
    else:
        conn.execute("DELETE FROM generated_images WHERE feed_post_id = ?", (feed_post_id,))
    conn.execute(
        "INSERT INTO generated_images (character_id, message_id, feed_post_id, prompt, file_path, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (character_id, message_id, feed_post_id, prompt, str(path), db.now_iso()),
    )
    conn.commit()
    return f"/generated/{filename}"


def _portrait_for(character: dict):
    return shared.resolve_portrait_path(shared.avatar_slug(character["name"]))


@router.post("/api/messages/{message_id}/image")
async def generate_message_image(message_id: int):
    conn = db.get_db()
    row = conn.execute(
        """
        SELECT m.id, m.content, s.id AS session_id, s.character_id
        FROM messages m JOIN sessions s ON s.id = m.session_id
        WHERE m.id = ?
        """,
        (message_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="message not found")

    character = shared.load_character(row["character_id"])
    state = shared.get_summary(conn, row["session_id"])
    prompt = character_state.build_image_prompt(character, state, scene_text=row["content"])
    prompt = await _neutralize_prompt(prompt)
    data = await image_client.generate_image(prompt, reference_image_path=_portrait_for(character))

    image_path = _save_and_record(conn, row["character_id"], message_id, None, f"msg-{message_id}.jpg", prompt, data)
    return {"image_path": image_path, "prompt": prompt}


@router.post("/api/feed/posts/{post_id}/image")
async def generate_feed_post_image(post_id: int):
    conn = db.get_db()
    row = conn.execute(
        "SELECT id, character_id, parent_id, content FROM feed_posts WHERE id = ?", (post_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="post not found")
    if row["parent_id"] is not None:
        raise HTTPException(status_code=400, detail="cannot generate an image for a comment/reaction")

    character = shared.load_character(row["character_id"])
    state = shared.get_current_state(conn, row["character_id"])
    prompt = character_state.build_image_prompt(character, state, scene_text=row["content"])
    prompt = await _neutralize_prompt(prompt)
    data = await image_client.generate_image(prompt, reference_image_path=_portrait_for(character))

    image_path = _save_and_record(conn, row["character_id"], None, post_id, f"post-{post_id}.jpg", prompt, data)
    return {"image_path": image_path, "prompt": prompt}


@router.get("/generated/{filename}")
def get_generated_image(filename: str):
    path = config.GENERATED_IMAGES_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="image not found")
    return FileResponse(path, headers={"Cache-Control": "no-cache"})

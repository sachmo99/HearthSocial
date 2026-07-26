from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import character_state
import db
import llama_client
import shared

router = APIRouter(prefix="/api")


class FeedPostIn(BaseModel):
    character_id: str


class FeedReactIn(BaseModel):
    character_id: str


class FeedCommentIn(BaseModel):
    content: str


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


@router.get("/feed")
def list_feed():
    conn = db.get_db()
    hidden_ids = shared.hidden_character_ids(conn)
    rows = conn.execute(
        """
        SELECT f.id, f.character_id, c.name AS character_name, f.parent_id, f.author_type, f.content, f.created_at,
               gi.file_path AS image_file_path
        FROM feed_posts f
        LEFT JOIN characters c ON c.id = f.character_id
        LEFT JOIN generated_images gi ON gi.feed_post_id = f.id
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
            "image_path": f"/generated/{Path(r['image_file_path']).name}" if r["image_file_path"] else None,
        }
        for r in rows
        if r["character_id"] not in hidden_ids
    ]


@router.post("/feed/posts")
async def create_feed_post(body: FeedPostIn):
    conn = db.get_db()
    if body.character_id in shared.hidden_character_ids(conn):
        raise HTTPException(status_code=404, detail="character not found")
    character = shared.load_character(body.character_id)
    state = shared.get_current_state(conn, body.character_id)
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


@router.post("/feed/posts/{post_id}/react")
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
    if body.character_id in shared.hidden_character_ids(conn):
        raise HTTPException(status_code=404, detail="character not found")

    character = shared.load_character(body.character_id)
    state = shared.get_current_state(conn, body.character_id)
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


@router.post("/feed/posts/{post_id}/comments")
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

import json

import character_state
import config
import llama_client
import rag


async def build(conn, session: dict, character: dict, summary: dict) -> list[dict]:
    persona = character["persona"]
    directive = character_state.build_behavior_directive(summary)
    # character_memory_raw (summarizer.py's pre-rewrite text, kept only for debugging) must never
    # reach the model - dumping it here would put the exact melodrama _plainify() removes right
    # back into context for the model to imitate.
    summary_for_prompt = {k: v for k, v in summary.items() if k != "character_memory_raw"}
    summary_text = json.dumps(summary_for_prompt)

    all_rows = conn.execute(
        "SELECT seq, role, content, token_count, visible FROM messages WHERE session_id = ? ORDER BY seq DESC",
        (session["id"],),
    ).fetchall()
    if not all_rows:
        raise ValueError("context_builder.build called with no messages in session")

    query_text = all_rows[0]["content"]
    latest_seq = all_rows[0]["seq"]
    recent_seqs = {row["seq"] for row in all_rows[: config.RECENT_MESSAGE_CAP]}
    rag_hits = [h for h in rag.retrieve_top_k(conn, session["id"], query_text) if h["seq"] not in recent_seqs]

    rag_block = ""
    if rag_hits:
        bullets = "\n".join(f"- ({latest_seq - h['seq']} messages ago) {h['content']}" for h in rag_hits)
        rag_block = (
            "\n\nEstablished facts from earlier in this conversation, each tagged with how long ago it was said. "
            "These actually happened and are true, but they are historical - the relationship and character's "
            "state have likely moved on since. Weigh older entries as past context, not as the character's "
            "current stance, and never let them override the Current state above. If the user asks about "
            "something covered here, answer using these exact details rather than making up new ones:\n"
            f"{bullets}"
        )

    fixed_text = (
        f"{persona}\n\n{character_state.RESPONSE_STYLE_DIRECTIVE}\n\n{character_state.SCENE_PROGRESSION_DIRECTIVE}"
        f"\n\n{directive}\n\nCurrent state: {summary_text}{rag_block}"
    )
    fixed_tokens = await llama_client.tokenize(fixed_text)
    remaining_budget = config.CONTEXT_WINDOW_TOKENS - fixed_tokens - config.GENERATION_HEADROOM_TOKENS

    recent_rows = []
    used_tokens = 0
    for row in all_rows:
        if len(recent_rows) >= config.RECENT_MESSAGE_CAP:
            break
        row_tokens = row["token_count"] or 0
        if used_tokens + row_tokens > remaining_budget and recent_rows:
            break
        recent_rows.append(row)
        used_tokens += row_tokens
    recent_rows.reverse()

    messages = [{"role": "system", "content": fixed_text}]
    for row in recent_rows:
        if row["role"] == "hidden_trigger" and row["visible"]:
            # Director's-note cut: stored as plain text for a clean chat-log display,
            # wrapped here only for the model so it reads as out-of-character guidance.
            content = (
                "[Director's note - out-of-character guidance, not something the character says or hears as "
                f"dialogue. Use it to shape what happens next: {row['content']}]"
            )
        else:
            content = row["content"]
        role = "assistant" if row["role"] == "assistant" else "user"
        messages.append({"role": role, "content": content})
    return messages

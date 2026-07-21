import json

import config
import db
import llama_client

RUNNING: set[str] = set()

_SUMMARIZER_SAMPLING = {"temperature": 0.3, "top_p": 0.9, "top_k": 40, "min_p": 0.05}


def should_trigger(conn, session_id: str, latest_seq: int) -> bool:
    if session_id in RUNNING:
        return False
    row = conn.execute("SELECT last_summarized_seq FROM summaries WHERE session_id = ?", (session_id,)).fetchone()
    last_summarized_seq = row["last_summarized_seq"] if row else 0
    return latest_seq - last_summarized_seq >= config.SUMMARIZE_EVERY_N_MESSAGES


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in summarizer response")
    return text[start : end + 1]


async def run(session_id: str) -> None:
    if session_id in RUNNING:
        return
    RUNNING.add(session_id)
    try:
        conn = db.get_db()
        row = conn.execute(
            "SELECT summary_json, last_summarized_seq FROM summaries WHERE session_id = ?", (session_id,)
        ).fetchone()
        previous_summary = row["summary_json"]
        last_summarized_seq = row["last_summarized_seq"]

        transcript_rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? AND seq > ? ORDER BY seq",
            (session_id, last_summarized_seq),
        ).fetchall()
        if not transcript_rows:
            return
        transcript = "\n".join(f"{r['role']}: {r['content']}" for r in transcript_rows)
        new_last_seq = conn.execute(
            "SELECT MAX(seq) AS max_seq FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()["max_seq"]

        prompt = (
            "You maintain a running structured JSON state for a role-play character. "
            "Merge/update the JSON state below using the new transcript. "
            "Preserve every existing field unless the transcript explicitly changes it — never null out or omit prior memory. "
            "Adjust character_affection and character_closeness incrementally (small integer steps) based on how the user "
            "treated the character in this transcript (kind/vulnerable -> nudge up; dismissive/cruel -> nudge down; "
            "neutral -> unchanged). Only advance relationship_stage if the transcript clearly earns it. "
            "Append new durable facts to notable_facts rather than replacing the list. "
            "Respond with ONLY the updated JSON object, no other text.\n\n"
            f"Previous state:\n{previous_summary}\n\n"
            f"New transcript:\n{transcript}"
        )
        result = await llama_client.chat_completion(
            [{"role": "user", "content": prompt}], _SUMMARIZER_SAMPLING, stream=False
        )

        try:
            merged = json.loads(_extract_json(result["content"]))
        except (json.JSONDecodeError, ValueError):
            return

        merged["last_updated_seq"] = new_last_seq
        conn.execute(
            "UPDATE summaries SET summary_json = ?, last_summarized_seq = ?, updated_at = ? WHERE session_id = ?",
            (json.dumps(merged), new_last_seq, db.now_iso(), session_id),
        )
        conn.commit()
    finally:
        RUNNING.discard(session_id)

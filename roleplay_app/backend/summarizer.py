import json

import character_state
import config
import db
import llama_client
import shared

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
        previous_state = json.loads(previous_summary)

        character_id = conn.execute(
            "SELECT character_id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()["character_id"]
        character = shared.load_character(character_id)

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

        stage_list = ", ".join(character_state.VALID_STAGES)
        if len(previous_state.get("notable_facts", [])) >= config.NOTABLE_FACTS_CONSOLIDATE_THRESHOLD:
            facts_instruction = (
                "notable_facts has grown long. Consolidate it now: merge overlapping or related facts into "
                "fewer, denser statements. Preserve every distinct piece of information - never delete a fact, "
                "only merge and rephrase for concision. Return a shorter, well-organized list."
            )
        else:
            facts_instruction = "Append new durable facts to notable_facts rather than replacing the list."

        prompt = (
            "You maintain a running structured JSON state for a role-play character. "
            f"Character background: {character['persona']}\n\n"
            "Merge/update the JSON state below using the new transcript. "
            "Preserve every existing field unless the transcript explicitly changes it - never null out or omit prior memory. "
            f"Adjust character_affection and character_closeness incrementally based on how the user treated the "
            f"character in this transcript (kind/vulnerable -> nudge up; dismissive/cruel -> nudge down; neutral -> "
            f"unchanged). Move by at most {config.MAX_STAT_DELTA_PER_CYCLE} points in either direction this cycle, "
            "even for a dramatic transcript - large shifts happen gradually across multiple cycles, not in one jump. "
            f"relationship_stage must be set to exactly one of these values, with no extra words added: {stage_list}. "
            "Only advance it if the transcript clearly earns it AND affection/closeness are already high enough to "
            "support that stage - a numeric gate will reject an unsupported jump and revert it, so do not advance "
            "preemptively expecting affection to catch up later. "
            "Choosing between the high-intimacy stages requires reading the character background above, not just "
            "the transcript: use 'partner' or 'spouse' only when nothing about the character's established "
            "relationship to the user (per the background) makes a romantic bond forbidden - e.g. two unrelated, "
            "unattached adults growing closer, then marrying. If the background establishes a relationship to the "
            "user that would normally be forbidden - a blood/family relation, a stark power-imbalance role, OR "
            "the character already being married/committed to someone else (an affair) - and things have turned "
            "romantic or intimate, use 'taboo' instead of 'partner'/'spouse'. This applies even if the two are not "
            "married to each other, since 'unmarried' does not make a forbidden relationship a normal one - and it "
            "applies even if the character's stray spouse/partner never appears in the transcript directly, as "
            "long as the background establishes they exist. Use 'family' only for a close familial bond that has "
            "stayed non-romantic/non-sexual. "
            "If relationship_stage changes from its previous value, append exactly one short entry to "
            "relationship_history describing what happened and why the relationship advanced (e.g. 'Became "
            "friends after helping fix the bookshelf.'). If relationship_stage does not change, leave "
            "relationship_history exactly as it was - never rewrite or remove past entries. "
            "character_mood must be a short phrase or clause (a few words, never a full sentence) describing the "
            "character's current emotional state, e.g. 'quietly pleased' or 'a little on edge'. "
            "character_appearance must be actively re-checked against the transcript every cycle, not left untouched "
            "by default - update it if the transcript describes a change in clothing, physical state, setting-driven "
            "appearance detail, or a prop/object associated with the character (e.g. an animal leaving, an item picked "
            "up or set down). Keep it a concise phrase or two, not a paragraph. "
            "character_memory must stay concise (2-3 sentences) and describe the relationship dynamic plainly and "
            "factually - avoid superlative or escalating language (e.g. 'sacred', 'destiny', 'profound', "
            "'transcendent'); state what is actually happening, not how monumental it feels. "
            f"{facts_instruction} "
            "Respond with ONLY the updated JSON object, no other text.\n\n"
            f"Previous state:\n{previous_summary}\n\n"
            f"New transcript:\n{transcript}"
        )
        try:
            # Generous timeout: this is background, fire-and-forget work with no UX deadline,
            # and the single llama-server slot may be busy serving the live chat.
            result = await llama_client.chat_completion(
                [{"role": "user", "content": prompt}], _SUMMARIZER_SAMPLING, stream=False, timeout=300.0
            )
        except Exception as e:
            print(f"[summarizer] LLM call failed for session {session_id}: {e!r}")
            return

        try:
            merged = json.loads(_extract_json(result["content"]))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[summarizer] failed to parse JSON for session {session_id}: {e!r}")
            print(f"[summarizer] raw response was: {result['content']!r}")
            return

        if merged.get("relationship_stage") not in character_state.VALID_STAGES:
            previous_stage = previous_state.get("relationship_stage")
            merged["relationship_stage"] = previous_stage if previous_stage in character_state.VALID_STAGES else "acquaintance"

        facts = merged.get("notable_facts")
        if not isinstance(facts, list):
            print(f"[summarizer] session {session_id}: model returned non-list notable_facts ({facts!r}), wrapping as a single entry")
            merged["notable_facts"] = [facts] if facts else []

        if not merged["notable_facts"] and previous_state.get("notable_facts"):
            print(f"[summarizer] session {session_id}: model returned empty notable_facts, keeping previous list")
            merged["notable_facts"] = previous_state["notable_facts"]

        history = merged.get("relationship_history")
        if not isinstance(history, list):
            print(f"[summarizer] session {session_id}: model returned non-list relationship_history ({history!r}), wrapping as a single entry")
            merged["relationship_history"] = [history] if history else []

        if not merged["relationship_history"] and previous_state.get("relationship_history"):
            print(f"[summarizer] session {session_id}: model returned empty relationship_history, keeping previous list")
            merged["relationship_history"] = previous_state["relationship_history"]

        def _clamp_stat(value, previous):
            previous = max(0, min(100, previous))
            try:
                value = max(0, min(100, int(value)))
            except (TypeError, ValueError):
                return previous
            delta = value - previous
            if delta > config.MAX_STAT_DELTA_PER_CYCLE:
                return previous + config.MAX_STAT_DELTA_PER_CYCLE
            if delta < -config.MAX_STAT_DELTA_PER_CYCLE:
                return previous - config.MAX_STAT_DELTA_PER_CYCLE
            return value

        merged["character_affection"] = _clamp_stat(merged.get("character_affection"), previous_state.get("character_affection", 0))
        merged["character_closeness"] = _clamp_stat(merged.get("character_closeness"), previous_state.get("character_closeness", 0))

        previous_stage = previous_state.get("relationship_stage", "stranger")
        if previous_stage not in character_state.VALID_STAGES:
            previous_stage = "stranger"
        new_stage = merged["relationship_stage"]
        if character_state.stage_rank(new_stage) > character_state.stage_rank(previous_stage):
            min_affection, min_closeness = character_state.stage_thresholds(new_stage)
            if merged["character_affection"] < min_affection or merged["character_closeness"] < min_closeness:
                print(
                    f"[summarizer] session {session_id}: blocked stage advance {previous_stage} -> {new_stage} "
                    f"(affection={merged['character_affection']}, closeness={merged['character_closeness']}, "
                    f"needs >= {min_affection}/{min_closeness}); reverting to {previous_stage}"
                )
                merged["relationship_stage"] = previous_stage
                merged["relationship_history"] = previous_state.get("relationship_history", merged["relationship_history"])

        memory = merged.get("character_memory", "")
        if isinstance(memory, str) and len(memory) > config.MAX_CHARACTER_MEMORY_CHARS:
            truncated = memory[: config.MAX_CHARACTER_MEMORY_CHARS]
            last_stop = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
            merged["character_memory"] = truncated[: last_stop + 1] if last_stop > 0 else truncated.rstrip()

        merged["last_updated_seq"] = new_last_seq
        conn.execute(
            "UPDATE summaries SET summary_json = ?, last_summarized_seq = ?, updated_at = ? WHERE session_id = ?",
            (json.dumps(merged), new_last_seq, db.now_iso(), session_id),
        )
        conn.commit()
        print(f"[summarizer] session {session_id} updated successfully, last_summarized_seq={new_last_seq}")
    finally:
        RUNNING.discard(session_id)

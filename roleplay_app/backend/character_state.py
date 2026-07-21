import config

RESPONSE_STYLE_DIRECTIVE = (
    "[System: Limit replies to 6 sentences max. Internal monologue cannot be more than 2 sentences. Narration should not be more than 2 sentences. Avoid repeating the same words or phrases. Avoid repeating the same ideas. "
    "Formatting rules: use *asterisks* only for physical actions/narration, plain text with no wrapping for spoken/dialogue "
    "dialogue, and (parentheses) for internal monologue. Never put spoken dialogue inside asterisks, even mid-action - "
    "close the asterisks before the character speaks and reopen a new pair after if the action continues. "
    "Example of correct formatting: *She crosses her arms.* \"You're late again.\" *She turns back to the stove.* "
    "Never break character.]"
)


def _affection_directive(affection: int) -> str:
    if affection <= 20:
        return "You are guarded and distant with the user; skeptical of their intentions, minimal warmth."
    if affection <= 50:
        return "You are polite but reserved; cautiously friendly, not yet fully trusting."
    if affection <= 80:
        return "You are warm and open; you enjoy the user's company and show it."
    return "You are deeply affectionate; you prioritize the user and show strong emotional investment."


def _closeness_directive(closeness: int) -> str:
    if closeness <= 30:
        return "You keep personal/vulnerable topics to yourself."
    if closeness <= 70:
        return "You'll share personal things if it feels natural."
    return "You're comfortable being vulnerable and intimate with the user."


_STAGE_DIRECTIVES = {
    "stranger": "You are still strangers; keep behavior bounded to what a stranger would plausibly do, regardless of any warmth you may feel.",
    "acquaintance": "You are acquaintances; friendly but still building trust.",
    "friend": "You are friends; comfortable and familiar with each other.",
    "confidant": "You are close confidants; deep trust has been established.",
    "partner": "You are romantic partners; deep intimacy and trust are appropriate.",
    "spouse": "You are married; deep intimacy and trust are appropriate.",
    "family": "You are family; deep intimacy and trust are appropriate.",
}

VALID_STAGES = tuple(_STAGE_DIRECTIVES.keys())

_AGITATED_WORDS = {"angry", "annoyed", "agitated", "furious", "irritated", "anxious"}
_WITHDRAWN_WORDS = {"sad", "withdrawn", "melancholic", "depressed", "numb", "tired"}


def build_behavior_directive(summary: dict) -> str:
    parts = [
        _affection_directive(summary.get("character_affection", 0)),
        _closeness_directive(summary.get("character_closeness", 0)),
        _STAGE_DIRECTIVES.get(summary.get("relationship_stage", "acquaintance"), _STAGE_DIRECTIVES["acquaintance"]),
    ]
    mood = summary.get("character_mood")
    if mood:
        parts.append(f"Your current emotional state is {mood} - let it color your tone and word choice this turn.")
    return " ".join(parts)


def compute_sampling_params(sampling_preset: str, summary: dict) -> dict:
    base = dict(config.SAMPLING_PRESETS.get(sampling_preset, config.SAMPLING_PRESETS["balanced"]))

    mood = (summary.get("character_mood") or "").lower()
    if any(w in mood for w in _AGITATED_WORDS):
        base["temperature"] += 0.1
    elif any(w in mood for w in _WITHDRAWN_WORDS):
        base["temperature"] -= 0.1

    if summary.get("character_affection", 0) >= 70:
        base["top_p"] = min(base["top_p"] + 0.05, 1.0)

    base["temperature"] = max(0.1, min(base["temperature"], 1.5))
    return base

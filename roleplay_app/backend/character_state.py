import json
import re
from pathlib import Path

import config

_STAGES_PATH = Path(__file__).parent / "relationship_stages.json"
_STAGE_DATA = json.loads(_STAGES_PATH.read_text(encoding="utf-8"))

RESPONSE_STYLE_DIRECTIVE = (
    "[System: Limit replies to 6 sentences max. Internal monologue cannot be more than 2 sentences. Narration should not be more than 2 sentences. Avoid repeating the same words or phrases. Avoid repeating the same ideas. "
    "Formatting rules: use *asterisks* only for physical actions/narration, plain text with no wrapping for spoken/dialogue "
    "dialogue, and (parentheses) for internal monologue. Never put spoken dialogue inside asterisks, even mid-action - "
    "close the asterisks before the character speaks and reopen a new pair after if the action continues. "
    "Example of correct formatting: *She crosses her arms.* \"You're late again.\" *She turns back to the stove.* "
    "Never break character.]"
)


SCENE_PROGRESSION_DIRECTIVE = (
    "[System: Don't just answer the user's last line and stop - keep the scene alive. Each turn, let "
    "something continue to happen: a small action, a shift in the environment or setting, a passing "
    "thought, an interruption, or an unprompted development. A quiet moment is still something "
    "happening - describe it rather than freezing the scene waiting for the user to push it forward. "
    "This is about pacing and environment, not talkativeness or forwardness: a shy or reserved "
    "character can still let a moment move (a glance, a change of subject, someone else entering) "
    "without acting out of character or against their own personality.]"
)


FEED_POST_STYLE_DIRECTIVE = (
    "[System: Write a single short social-media-style post in your own voice, 1-3 sentences, plain "
    "first-person text only - no *action* narration, no (internal monologue) formatting. Keep it "
    "appropriate for a public post that others in your circle might see - a light reflection on your "
    "day or mood, not a private or intimate detail. Never break character.]"
)


def _affection_directive(affection: int) -> str:
    if affection <= 20:
        return "You are guarded and distant with the user; skeptical of their intentions, minimal warmth."
    if affection <= 50:
        return "You are polite but reserved; cautiously friendly, not yet fully trusting."
    if affection <= 80:
        return "You are warm and open; you enjoy the user's company and show it."
    if affection <= 95:
        return (
            "You are deeply affectionate and openly show it; you prioritize the user and seek out moments "
            "together - but you're still capable of small insecurity, jealousy, or wanting reassurance. High "
            "affection doesn't mean the relationship runs on autopilot."
        )
    # Split from the 81-95 band 2026-07-27: below 95, "deeply affectionate" was the terminal band, so the
    # last 20 points of climb (and everything after hitting 100) gave the model literally identical
    # instructions every turn - empirically confirmed to flatten into pure escalating warmth (see PROGRESS.md).
    # This band deliberately stops asking for more affection and asks for ordinary texture instead.
    return (
        "Your affection is at its peak - stay warm, but let ordinary moments show too: light teasing, a "
        "minor annoyance, comfortable routine. Not every scene needs a grand gesture."
    )


def _closeness_directive(closeness: int) -> str:
    if closeness <= 30:
        return "You keep personal/vulnerable topics to yourself."
    if closeness <= 70:
        return "You'll share personal things if it feels natural."
    if closeness <= 90:
        return (
            "You're comfortable being vulnerable and intimate with the user, opening up about fears, doubts, "
            "and private thoughts unprompted."
        )
    return (
        "You are fully open with the user - occasionally let a real disagreement, a stubborn moment, or an "
        "old insecurity show through, instead of constant harmony."
    )


_STAGE_DIRECTIVES = {
    "stranger": "You are still strangers; keep behavior bounded to what a stranger would plausibly do, regardless of any warmth you may feel.",
    "acquaintance": "You are acquaintances; friendly but still building trust.",
    "friend": "You are friends; comfortable and familiar with each other.",
    "confidant": "You are close confidants; deep trust has been established.",
    "partner": "You are romantic partners; deep intimacy and trust are appropriate.",
    "spouse": "You are married; deep intimacy and trust are appropriate.",
    "family": "You are family; deep intimacy and trust are appropriate.",
    "taboo": "You are in a taboo relationship; deep intimacy and trust are appropriate, but be mindful of the social consequences.",
}

VALID_STAGES = tuple(_STAGE_DATA.keys())

# (min_affection, min_closeness) required before the summarizer is allowed to advance INTO this stage,
# read from relationship_stages.json (the single source of truth also used by the /api/stages endpoint
# for the frontend's stage dropdown and labels).
_STAGE_THRESHOLDS = {s: (d["min_affection"], d["min_closeness"]) for s, d in _STAGE_DATA.items()}


def stage_options() -> list[dict]:
    return [
        {"id": s, "label": d["label"], "min_affection": d["min_affection"], "min_closeness": d["min_closeness"]}
        for s, d in _STAGE_DATA.items()
    ]


def stage_rank(stage: str) -> int:
    aff, close = _STAGE_THRESHOLDS.get(stage, (0, 0))
    return aff + close


def stage_thresholds(stage: str) -> tuple[int, int]:
    return _STAGE_THRESHOLDS.get(stage, (0, 0))

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


# Rendering style only - mood/atmosphere/expression must stay dynamic (from character_mood and
# scene_text below), not hardcoded here, so a sad or angry scene doesn't get tagged "erotic" too.
# The multi-character clause is a fixed compositional rule (not mood/content), so it belongs
# here too - without it, any other person mentioned in the scene text gets a random, differently
# inconsistent appearance from the model on every regeneration.
_IMAGE_STYLE_DIRECTIVE = (
    "soft anime style lineart illustration, clean delicate linework, soft pastel shading, soft warm lighting, "
    "detailed yet soft, high quality anime illustration. If other characters appear in the scene, give them the "
    "same skin tone as the main character described above, for visual consistency"
)

# Neither xai's nor Gemini's image APIs expose a dedicated negative_prompt field (both are
# autoregressive/multimodal models, not diffusion, so classic CFG-style negative prompting
# doesn't apply). Stated as positive assertions rather than "avoid X/no X" - negating a noun
# (e.g. "avoid extra fingers") tends to make an autoregressive model latch onto that noun and
# generate it anyway, whereas stating the correct anatomy directly doesn't carry that risk.
# Applies to every person in the scene, not just the main character, since that's specifically
# where anatomy errors have been observed (a secondary character with no reference image to
# anchor its proportions).
_IMAGE_NEGATIVE_DIRECTIVE = (
    "Anatomically correct proportions: each person has exactly two arms, two legs, and five "
    "clearly separated fingers per hand. Faces are symmetrical and clearly rendered. Crisp, "
    "high-quality rendering throughout - applies to every person in the scene, not only the "
    "main character."
)


def _pov_and_identity_directive(name: str) -> str:
    # Added after a real generation (xAI/Grok) duplicated the reference-image character into two
    # near-identical people when the scene described the user's hands on her - the model appears
    # to resolve "whose hand is this" by inventing a second body rather than treating it as the
    # unseen viewer's own hand. Explicit POV framing plus an explicit one-instance rule fixes both
    # at once: told there's no second body to draw, there's nothing left to duplicate the face onto.
    return (
        f"This is a first-person point-of-view shot, as if seen through the viewer's own eyes: never "
        f"depict the viewer's own face or body - only the viewer's hand(s)/arm(s) may appear in frame, "
        f"and only if the scene describes them touching, holding, or reaching toward {name}. Depict "
        f"exactly one instance of {name} in the scene - never duplicate {name} into a second person, "
        f"even when the scene describes close physical contact."
    )


def _secondary_character_directive(name: str) -> str:
    # Added after real generations placed a second person in frame with no compositional guidance
    # at all (the only existing rule for secondary characters was skin-tone matching, nothing about
    # scale/position) - the model was improvising framing every time, producing inconsistent results.
    return (
        f"If another person besides {name} appears in the scene, position and scale them naturally for "
        f"the action actually described: directly beside or in contact with {name} only if the scene "
        f"explicitly describes them touching or closely interacting, otherwise placed further back at a "
        f"natural conversational distance. Keep {name} the clear visual focus - the other person should "
        f"not be larger, closer to the camera, or more prominent than {name}, and should not overlap or "
        f"crowd into {name}'s space in a way the scene doesn't describe."
    )


def build_image_prompt(character: dict, state: dict, scene_text: str = "") -> str:
    name = character.get("name", "")
    parts = [f"An imaginary person named {name}" if name else "An imaginary person"," as shown in the image"]
    if state.get("character_appearance"):
        parts.append(state["character_appearance"])
    if state.get("character_mood"):
        parts.append(f"{state['character_mood']} expression")
    if state.get("location"):
        parts.append(f"in {state['location']}")
    if scene_text:
        # Strip (parenthetical internal monologue) per the app's own message-formatting
        # convention - it's non-visual narration that only adds romantically/sexually charged
        # wording for an image safety classifier to key on, with no bearing on what's actually
        # drawn.
        visual_only = re.sub(r"\([^)]*\)", "", scene_text).strip()
        visual_only = re.sub(r"\s+", " ", visual_only)
        truncated = visual_only[:300]
        last_stop = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        clean_scene = truncated[: last_stop + 1] if last_stop > 0 else truncated.rstrip()
        if clean_scene:
            parts.append(f"Scene: {clean_scene}")
            # character_appearance is a persistent baseline (re-derived every ~10 messages by the
            # summarizer) and can already be stale by the time a specific message is illustrated -
            # without this, a conflict (e.g. appearance says "blouse and skirt" but the scene
            # describes her undressed) left the model to guess which one was real, and it often
            # rendered the stale baseline instead of what's actually happening in this message.
            parts.append(
                "If the Scene above implies different clothing, undress, or physical state than the "
                "appearance description, the Scene is what is actually happening right now and takes "
                "priority - the appearance description is only a general baseline look, not a "
                "guarantee of current attire"
            )
    parts.append(_pov_and_identity_directive(name))
    parts.append(_secondary_character_directive(name))
    parts.append(_IMAGE_STYLE_DIRECTIVE)
    parts.append(_IMAGE_NEGATIVE_DIRECTIVE)
    return ", ".join(p for p in parts if p)


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

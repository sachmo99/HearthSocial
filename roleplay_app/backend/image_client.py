import base64
from pathlib import Path

import httpx

import config


class ImageGenerationUnavailable(Exception):
    """Raised when no provider is configured/available, or the API is unreachable/errors."""


def _format_api_error(provider: str, response: httpx.Response) -> str:
    """Pulls the actual provider-reported error message out of an error response, so callers
    see e.g. a real rate-limit/content-policy/auth reason instead of a generic failure string."""
    detail = response.text[:500]
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            detail = err.get("message") or detail
        elif isinstance(err, str):
            detail = err
    return f"{provider} API error ({response.status_code}): {detail}"


def is_configured(provider: str | None = None) -> bool:
    """Whether the given provider (default: config.IMAGE_PROVIDER) has what it needs to run."""
    provider = provider or config.IMAGE_PROVIDER
    if provider == "xai":
        return bool(config.XAI_API_KEY)
    if provider == "gemini":
        return bool(config.GEMINI_API_KEY)
    return False


async def generate_image(
    prompt: str,
    reference_image_path: Path | None = None,
    aspect_ratio: str = "16:9",
    provider: str | None = None,
) -> bytes:
    """Public entrypoint - stable regardless of which provider is configured. Adding a new
    provider means adding a `_generate_<name>()` function and one branch here, not touching
    any caller. `provider` overrides config.IMAGE_PROVIDER for this call only (used for the
    cross-provider fallback in routers/images.py)."""
    provider = provider or config.IMAGE_PROVIDER
    if provider == "xai":
        return await _generate_xai(prompt, reference_image_path, aspect_ratio)
    if provider == "gemini":
        return await _generate_gemini(prompt, reference_image_path, aspect_ratio)
    raise ImageGenerationUnavailable(f"unknown image provider '{provider}' (set ROLEPLAY_IMAGE_PROVIDER)")


# Appended to the prompt whenever a reference image is used, for both providers - without this,
# models tend to carry the portrait's own background/setting into the new scene instead of the
# location actually described in the prompt.
_REFERENCE_IMAGE_INSTRUCTION = (
    " Use the attached reference image only for the character's face and likeness - ignore its "
    "background and setting entirely, and use the location described above instead."
)


def _mime_type(path: Path) -> str:
    return "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"


def _to_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_mime_type(path)};base64,{encoded}"


async def _extract_xai_image_bytes(client: httpx.AsyncClient, entry: dict) -> bytes:
    if "b64_json" in entry:
        return base64.b64decode(entry["b64_json"])
    # Fallback only - both request payloads now explicitly ask for response_format=b64_json, so
    # this only fires if a future response ever omits it. Zero Data Retention xAI accounts can't
    # use the URL format at all (the account can't retain a hosted copy to serve it from), so
    # b64_json isn't just an optimization here, it's required for those accounts to work.
    img_resp = await client.get(entry["url"])
    img_resp.raise_for_status()
    return img_resp.content


async def _generate_xai(prompt: str, reference_image_path: Path | None, aspect_ratio: str) -> bytes:
    if not config.XAI_API_KEY:
        raise ImageGenerationUnavailable("no XAI API key configured (set ROLEPLAY_XAI_API_KEY)")
    headers = {"Authorization": f"Bearer {config.XAI_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            if reference_image_path is not None:
                # Use the character's portrait as a reference image so the generated scene keeps
                # a consistent face/likeness instead of the model inventing a new one each time.
                payload = {
                    "model": config.XAI_IMAGE_MODEL,
                    "prompt": prompt + _REFERENCE_IMAGE_INSTRUCTION,
                    "image": {"type": "image_url", "url": _to_data_uri(reference_image_path)},
                    "response_format": "b64_json",
                }
                r = await client.post(config.XAI_IMAGE_EDIT_URL, json=payload, headers=headers)
            else:
                payload = {
                    "model": config.XAI_IMAGE_MODEL,
                    "prompt": prompt,
                    "n": 1,
                    "aspect_ratio": aspect_ratio,
                    "response_format": "b64_json",
                }
                r = await client.post(config.XAI_IMAGE_URL, json=payload, headers=headers)
            r.raise_for_status()
            return await _extract_xai_image_bytes(client, r.json()["data"][0])
    except httpx.HTTPStatusError as e:
        raise ImageGenerationUnavailable(_format_api_error("xAI", e.response)) from e
    except httpx.HTTPError as e:
        raise ImageGenerationUnavailable(f"xAI image API unreachable: {e}") from e


def _extract_gemini_image_bytes(response_json: dict) -> bytes:
    # Google's Interactions API (https://ai.google.dev/gemini-api/docs/image-generation) returns
    # a list of steps; the model's output step contains content blocks, one of which is the
    # generated image (type "image", base64 in "data"). Walked manually rather than via a
    # convenience accessor since this is a raw REST call, not the SDK.
    text_fallback = None
    for step in response_json.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if block.get("type") == "image" and block.get("data"):
                return base64.b64decode(block["data"])
            if block.get("type") == "text" and block.get("text") and text_fallback is None:
                text_fallback = block["text"].strip()
    # No image block usually means the model refused (safety filter) and replied with text
    # instead - surface that text since it's the actual reason, not a generic failure.
    if text_fallback:
        raise ImageGenerationUnavailable(f"Gemini did not return an image: {text_fallback}")
    raise ImageGenerationUnavailable(f"Gemini response contained no image data: {response_json}")


async def _generate_gemini(prompt: str, reference_image_path: Path | None, aspect_ratio: str) -> bytes:
    if not config.GEMINI_API_KEY:
        raise ImageGenerationUnavailable("no Gemini API key configured (set ROLEPLAY_GEMINI_API_KEY)")
    headers = {"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"}
    # Gemini's native multimodal generation produces a text response alongside the image by
    # default (unlike xai's dedicated image-only endpoints) - there's no documented modality
    # flag to hard-disable that, so this is a prompt-level ask to skip it and save output tokens.
    text_prompt = f"{prompt}\n\nDo not include any text response, caption, or commentary - output only the image."
    if reference_image_path is not None:
        text_prompt += _REFERENCE_IMAGE_INSTRUCTION
    input_items = [{"type": "text", "text": text_prompt}]
    if reference_image_path is not None:
        # Reference image alongside the text prompt in the same input array, for the same
        # face-consistency reason as the xai path.
        input_items.append({
            "type": "image",
            "mime_type": _mime_type(reference_image_path),
            "data": base64.b64encode(reference_image_path.read_bytes()).decode("ascii"),
        })
    payload = {
        "model": config.GEMINI_IMAGE_MODEL,
        "input": input_items,
        # image_size pinned to the model's cheapest/only-supported tier deliberately, to keep
        # cloud costs down - Gemini rejects a lowercase value here ("1k"), must be "1K".
        "response_format": {
            "type": "image",
            "mime_type": "image/jpeg",
            "aspect_ratio": aspect_ratio,
            "image_size": config.GEMINI_IMAGE_SIZE,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(config.GEMINI_IMAGE_URL, json=payload, headers=headers)
            r.raise_for_status()
            return _extract_gemini_image_bytes(r.json())
    except httpx.HTTPStatusError as e:
        raise ImageGenerationUnavailable(_format_api_error("Gemini", e.response)) from e
    except httpx.HTTPError as e:
        raise ImageGenerationUnavailable(f"Gemini image API unreachable: {e}") from e

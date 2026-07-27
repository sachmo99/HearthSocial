import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
CHARACTERS_DIR = BACKEND_DIR / "characters"
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
PORTRAITS_DIR = BACKEND_DIR.parent / "frontend" / "public" / "portraits"
GENERATED_IMAGES_DIR = BACKEND_DIR.parent / "frontend" / "public" / "generated"

# Static default; override at server bootup with, e.g., ROLEPLAY_LLAMA_URL=http://192.168.1.5:8080
# set before starting uvicorn - for pointing at a llama-server running on a different host/port.
LLAMA_SERVER_URL = os.environ.get("ROLEPLAY_LLAMA_URL", "http://127.0.0.1:8080")

# Optional - the only feature in this app that calls out to the internet. Everything else
# stays fully local/offline; image generation is opt-in by setting these before starting
# uvicorn. IMAGE_PROVIDER selects which backend image_client.py dispatches to - "xai" and
# "gemini" are implemented, and the selector means adding another provider later is a contained
# change in image_client.py, not a rewrite of every call site.
IMAGE_PROVIDER = os.environ.get("ROLEPLAY_IMAGE_PROVIDER", "gemini")

# xai provider config. Empty key means this provider is simply unavailable. Standard tier
# ("grok-imagine-image", $0.02/image) deliberately used over "grok-imagine-image-quality"
# ($0.05/image) to keep cloud costs down, same reasoning as Gemini's lite model + 1K pin below -
# xAI is already only the fallback path (see routers/images.py), so it doesn't need the pricier tier.
XAI_API_KEY = os.environ.get("ROLEPLAY_XAI_API_KEY", "")
XAI_IMAGE_MODEL = os.environ.get("ROLEPLAY_XAI_IMAGE_MODEL", "grok-imagine-image")
XAI_IMAGE_URL = "https://api.x.ai/v1/images/generations"
XAI_IMAGE_EDIT_URL = "https://api.x.ai/v1/images/edits"

# gemini provider config ("Nano Banana 2 Lite" / Gemini 3.1 Flash Lite Image, via Google's
# Interactions API - https://ai.google.dev/gemini-api/docs/image-generation). Empty key means
# this provider is simply unavailable. The lite model + 1K (its only supported resolution, see
# GEMINI_IMAGE_SIZE below) is deliberately the cheapest combination, to keep cloud costs down.
GEMINI_API_KEY = os.environ.get("ROLEPLAY_GEMINI_API_KEY", "")
GEMINI_IMAGE_MODEL = os.environ.get("ROLEPLAY_GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image")
GEMINI_IMAGE_SIZE = os.environ.get("ROLEPLAY_GEMINI_IMAGE_SIZE", "1K")
GEMINI_IMAGE_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

# Cloud image providers generally refuse to generate explicit sexual content, but this app's
# scene prompts are built straight from live roleplay chat text, which can be explicit. When
# enabled (default), the prompt is rewritten through the local model to neutralize explicit
# wording before it ever leaves the machine. Disable with ROLEPLAY_IMAGE_MODERATION=false.
IMAGE_MODERATION_ENABLED = os.environ.get("ROLEPLAY_IMAGE_MODERATION", "true").strip().lower() not in ("false", "0", "no")

CONTEXT_WINDOW_TOKENS = 16384
GENERATION_HEADROOM_TOKENS = 1024
RECENT_MESSAGE_CAP = 20
SUMMARIZE_EVERY_N_MESSAGES = 10
NOTABLE_FACTS_CONSOLIDATE_THRESHOLD = 12
MAX_STAT_DELTA_PER_CYCLE = 10
MAX_CHARACTER_MEMORY_CHARS = 600

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
RAG_OVERFETCH_K = 50
RAG_TOP_K = 5

# Static default; override at server bootup with, e.g., ROLEPLAY_UNHIDE_PIN=5678 before launching uvicorn.
UNHIDE_PIN = os.environ.get("ROLEPLAY_UNHIDE_PIN", "1234")

SAMPLING_PRESETS = {
    "calm": {"temperature": 0.6, "top_p": 0.75, "top_k": 40, "min_p": 0.05},
    "balanced": {"temperature": 0.8, "top_p": 0.85, "top_k": 60, "min_p": 0.05},
    "chaotic": {"temperature": 1.05, "top_p": 0.95, "top_k": 100, "min_p": 0.02},
}

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
CHARACTERS_DIR = BACKEND_DIR / "characters"
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
PORTRAITS_DIR = BACKEND_DIR.parent / "frontend" / "public" / "portraits"

LLAMA_SERVER_URL = "http://127.0.0.1:8080"

CONTEXT_WINDOW_TOKENS = 16384
GENERATION_HEADROOM_TOKENS = 1024
RECENT_MESSAGE_CAP = 20
SUMMARIZE_EVERY_N_MESSAGES = 10

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
RAG_OVERFETCH_K = 50
RAG_TOP_K = 5

SAMPLING_PRESETS = {
    "calm": {"temperature": 0.6, "top_p": 0.9, "top_k": 40, "min_p": 0.05},
    "balanced": {"temperature": 0.8, "top_p": 0.95, "top_k": 60, "min_p": 0.05},
    "chaotic": {"temperature": 1.05, "top_p": 0.98, "top_k": 100, "min_p": 0.02},
}

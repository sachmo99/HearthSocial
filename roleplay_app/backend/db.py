import json
import sqlite3
from datetime import datetime, timezone

import sqlite_vec

import config

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS characters (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(id),
  status TEXT NOT NULL CHECK(status IN ('active','archived')),
  created_at TEXT NOT NULL,
  archived_at TEXT,
  hidden INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_session ON sessions(character_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  seq INTEGER NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user','assistant','hidden_trigger')),
  content TEXT NOT NULL,
  visible INTEGER NOT NULL DEFAULT 1,
  token_count INTEGER,
  created_at TEXT NOT NULL,
  UNIQUE(session_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, seq);

CREATE TABLE IF NOT EXISTS summaries (
  session_id TEXT PRIMARY KEY REFERENCES sessions(id),
  summary_json TEXT NOT NULL,
  last_summarized_seq INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS message_vectors USING vec0(
  message_id INTEGER PRIMARY KEY,
  session_id TEXT,
  embedding FLOAT[{config.EMBEDDING_DIM}]
);

CREATE TABLE IF NOT EXISTS feed_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id TEXT REFERENCES characters(id),
  parent_id INTEGER REFERENCES feed_posts(id),
  author_type TEXT NOT NULL CHECK(author_type IN ('character','user')),
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  CHECK((author_type='character' AND character_id IS NOT NULL) OR (author_type='user' AND character_id IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_feed_posts_character ON feed_posts(character_id);
CREATE INDEX IF NOT EXISTS idx_feed_posts_parent ON feed_posts(parent_id);
CREATE INDEX IF NOT EXISTS idx_feed_posts_created ON feed_posts(created_at);
"""

_conn: sqlite3.Connection | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    if "hidden" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate(conn)
        _conn = conn
    return _conn


def upsert_character(conn: sqlite3.Connection, character_id: str, name: str, file_path: str) -> None:
    conn.execute(
        """
        INSERT INTO characters (id, name, file_path, updated_at) VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET name = excluded.name, file_path = excluded.file_path, updated_at = excluded.updated_at
        """,
        (character_id, name, file_path, now_iso()),
    )
    conn.commit()


def sync_characters_from_disk(conn: sqlite3.Connection) -> None:
    config.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    for path in config.CHARACTERS_DIR.glob("*.json"):
        card = json.loads(path.read_text(encoding="utf-8"))
        upsert_character(conn, path.stem, card["name"], str(path))

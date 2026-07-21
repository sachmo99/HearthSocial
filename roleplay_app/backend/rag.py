import sqlite3

import sqlite_vec

import config
import embeddings


def embed_and_store(conn: sqlite3.Connection, message_id: int, session_id: str, content: str) -> None:
    vector = embeddings.embed_document(content)
    conn.execute(
        "INSERT INTO message_vectors (message_id, session_id, embedding) VALUES (?, ?, ?)",
        (message_id, session_id, sqlite_vec.serialize_float32(vector)),
    )
    conn.commit()


def retrieve_top_k(conn: sqlite3.Connection, session_id: str, query: str, exclude_seqs: set[int] | None = None) -> list[dict]:
    exclude_seqs = exclude_seqs or set()
    query_vector = embeddings.embed_query(query)
    # Deliberately not JOINed with `messages` in this query: sqlite-vec's KNN planner only
    # recognizes the LIMIT constraint on a plain scan of the vec0 table (confirmed empirically —
    # adding a JOIN here raised "A LIMIT or 'k = ?' constraint is required on vec0 knn queries").
    rows = conn.execute(
        """
        SELECT message_id, session_id, distance
        FROM message_vectors
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
        """,
        (sqlite_vec.serialize_float32(query_vector), config.RAG_OVERFETCH_K),
    ).fetchall()

    hits = []
    for row in rows:
        if row["session_id"] != session_id:
            continue
        message_row = conn.execute(
            "SELECT content, seq FROM messages WHERE id = ?", (row["message_id"],)
        ).fetchone()
        if message_row is None or message_row["seq"] in exclude_seqs:
            continue
        hits.append({"content": message_row["content"], "seq": message_row["seq"], "distance": row["distance"]})
        if len(hits) >= config.RAG_TOP_K:
            break
    return hits

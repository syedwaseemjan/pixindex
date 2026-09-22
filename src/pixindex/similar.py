from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from pixindex.query import Filters, QueryError, where_clause
from pixindex.vectors import cosine, unpack_vector


@dataclass(frozen=True)
class PictureMatch:
    uri: str
    score: float


def search_pictures(
    conn: sqlite3.Connection,
    filters: Filters,
    text: str,
    embedder,
    limit: int,
) -> tuple[list[PictureMatch], int]:
    """Rank catalog pictures by how close they are to the words.

    Filters run first. Pictures with no number list for this model are left
    out and counted, so the caller can say they still need embed.
    """
    if limit < 1:
        raise QueryError("--limit must be 1 or greater.")

    where, params = where_clause(filters)
    rows = conn.execute(
        f"""
        SELECT images.uri AS uri, embeddings.vector AS vector
        FROM images
        LEFT JOIN embeddings
          ON embeddings.uri = images.uri
         AND embeddings.model_id = ?
         AND embeddings.size = images.size
         AND embeddings.mtime_ns = images.mtime_ns
         AND (
            (embeddings.etag IS NULL AND images.etag IS NULL)
            OR embeddings.etag = images.etag
         )
        WHERE images.uri IN (SELECT uri FROM images{where})
        """,
        [embedder.model_id, *params],
    ).fetchall()
    if not rows:
        return [], 0

    query = embedder.embed_text(text)
    matches: list[PictureMatch] = []
    missing = 0
    for row in rows:
        blob = row["vector"]
        if blob is None:
            missing += 1
            continue
        try:
            vector = unpack_vector(blob)
        except ValueError:
            missing += 1
            continue
        if len(vector) != len(query):
            missing += 1
            continue
        matches.append(PictureMatch(str(row["uri"]), cosine(query, vector)))

    matches.sort(key=lambda match: (-match.score, match.uri))
    return matches[:limit], missing

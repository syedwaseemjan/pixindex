from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    uri TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    width INTEGER,
    height INTEGER,
    captured_at TEXT,
    camera_make TEXT,
    camera_model TEXT,
    has_gps INTEGER NOT NULL DEFAULT 0,
    gps_lat REAL,
    gps_lon REAL,
    etag TEXT,
    indexed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS images_source_idx ON images (source);

CREATE TABLE IF NOT EXISTS embeddings (
    uri TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    vector BLOB NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    etag TEXT,
    embedded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS picture_hashes (
    uri TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    etag TEXT
);
"""


@dataclass(frozen=True)
class ImageRow:
    uri: str
    source: str
    size: int
    mtime_ns: int
    width: int | None
    height: int | None
    captured_at: str | None
    camera_make: str | None
    camera_model: str | None
    has_gps: bool
    gps_lat: float | None
    gps_lon: float | None
    etag: str | None = None


def default_db_path() -> Path:
    root = os.environ.get("XDG_DATA_HOME")
    base = Path(root) if root else Path.home() / ".local" / "share"
    return base / "pixindex" / "index.sqlite"


def resolve_db_path(db: Path | None) -> Path:
    path = Path(db).expanduser().resolve() if db is not None else default_db_path()
    return path


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
    if "etag" not in columns:
        conn.execute("ALTER TABLE images ADD COLUMN etag TEXT")
        conn.commit()


def lookup(conn: sqlite3.Connection, uri: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT size, mtime_ns, etag FROM images WHERE uri = ?",
        (uri,),
    ).fetchone()


def fingerprint(conn: sqlite3.Connection, uri: str) -> tuple[int, int] | None:
    row = lookup(conn, uri)
    if row is None:
        return None
    return int(row["size"]), int(row["mtime_ns"])


_FRESH = """
    embeddings.size = images.size
    AND embeddings.mtime_ns = images.mtime_ns
    AND (
        (embeddings.etag IS NULL AND images.etag IS NULL)
        OR embeddings.etag = images.etag
    )
"""

_FRESH_HASH = """
    picture_hashes.size = images.size
    AND picture_hashes.mtime_ns = images.mtime_ns
    AND (
        (picture_hashes.etag IS NULL AND images.etag IS NULL)
        OR picture_hashes.etag = images.etag
    )
"""


def fresh_embedding(conn: sqlite3.Connection, uri: str, model_id: str) -> bool:
    row = conn.execute(
        f"""
        SELECT 1
        FROM embeddings
        JOIN images ON images.uri = embeddings.uri
        WHERE embeddings.uri = ?
          AND embeddings.model_id = ?
          AND {_FRESH}
        """,
        (uri, model_id),
    ).fetchone()
    return row is not None


def save_embedding(
    conn: sqlite3.Connection,
    *,
    uri: str,
    model_id: str,
    vector: bytes,
    size: int,
    mtime_ns: int,
    etag: str | None,
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute(
        """
        INSERT INTO embeddings (
            uri, model_id, vector, size, mtime_ns, etag, embedded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(uri) DO UPDATE SET
            model_id = excluded.model_id,
            vector = excluded.vector,
            size = excluded.size,
            mtime_ns = excluded.mtime_ns,
            etag = excluded.etag,
            embedded_at = excluded.embedded_at
        """,
        (uri, model_id, vector, size, mtime_ns, etag, now),
    )
    conn.commit()


def fresh_hash(conn: sqlite3.Connection, uri: str) -> str | None:
    row = conn.execute(
        f"""
        SELECT picture_hashes.hash AS hash
        FROM picture_hashes
        JOIN images ON images.uri = picture_hashes.uri
        WHERE picture_hashes.uri = ?
          AND {_FRESH_HASH}
        """,
        (uri,),
    ).fetchone()
    if row is None:
        return None
    return str(row["hash"])


def save_hash(
    conn: sqlite3.Connection,
    *,
    uri: str,
    fingerprint: str,
    size: int,
    mtime_ns: int,
    etag: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO picture_hashes (uri, hash, size, mtime_ns, etag)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(uri) DO UPDATE SET
            hash = excluded.hash,
            size = excluded.size,
            mtime_ns = excluded.mtime_ns,
            etag = excluded.etag
        """,
        (uri, fingerprint, size, mtime_ns, etag),
    )
    conn.commit()


def upsert(conn: sqlite3.Connection, row: ImageRow) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute("DELETE FROM embeddings WHERE uri = ?", (row.uri,))
    conn.execute("DELETE FROM picture_hashes WHERE uri = ?", (row.uri,))
    conn.execute(
        """
        INSERT INTO images (
            uri, source, size, mtime_ns, width, height, captured_at,
            camera_make, camera_model, has_gps, gps_lat, gps_lon, etag, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(uri) DO UPDATE SET
            source = excluded.source,
            size = excluded.size,
            mtime_ns = excluded.mtime_ns,
            width = excluded.width,
            height = excluded.height,
            captured_at = excluded.captured_at,
            camera_make = excluded.camera_make,
            camera_model = excluded.camera_model,
            has_gps = excluded.has_gps,
            gps_lat = excluded.gps_lat,
            gps_lon = excluded.gps_lon,
            etag = excluded.etag,
            indexed_at = excluded.indexed_at
        """,
        (
            row.uri,
            row.source,
            row.size,
            row.mtime_ns,
            row.width,
            row.height,
            row.captured_at,
            row.camera_make,
            row.camera_model,
            int(row.has_gps),
            row.gps_lat,
            row.gps_lon,
            row.etag,
            now,
        ),
    )
    conn.commit()

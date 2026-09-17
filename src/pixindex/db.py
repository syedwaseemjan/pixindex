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
    indexed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS images_source_idx ON images (source);
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
    return conn


def fingerprint(conn: sqlite3.Connection, uri: str) -> tuple[int, int] | None:
    row = conn.execute(
        "SELECT size, mtime_ns FROM images WHERE uri = ?",
        (uri,),
    ).fetchone()
    if row is None:
        return None
    return int(row["size"]), int(row["mtime_ns"])


def upsert(conn: sqlite3.Connection, row: ImageRow) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute(
        """
        INSERT INTO images (
            uri, source, size, mtime_ns, width, height, captured_at,
            camera_make, camera_model, has_gps, gps_lat, gps_lon, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            now,
        ),
    )
    conn.commit()

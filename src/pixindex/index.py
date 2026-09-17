from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pixindex.db import ImageRow, connect, fingerprint, upsert
from pixindex.metadata import read_metadata

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class IndexResult:
    indexed: int = 0
    skipped: int = 0
    failed: int = 0


def index_local(source: Path, db_path: Path) -> IndexResult:
    source = source.resolve()
    result = IndexResult()
    conn = connect(db_path)
    try:
        for path in iter_images(source):
            try:
                if _index_one(conn, source, path):
                    result.indexed += 1
                else:
                    result.skipped += 1
            except Exception as exc:
                result.failed += 1
                print(f"{path}: {exc}", file=sys.stderr)
            _progress(result)
    finally:
        conn.close()
        if result.indexed or result.skipped or result.failed:
            print(file=sys.stderr)
    return result


def iter_images(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            path = Path(dirpath) / name
            if path.suffix.lower() in EXTENSIONS:
                paths.append(path)
    return paths


def _index_one(conn, source: Path, path: Path) -> bool:
    stat = path.stat()
    uri = str(path.resolve())
    existing = fingerprint(conn, uri)
    if existing == (stat.st_size, stat.st_mtime_ns):
        return False
    meta = read_metadata(path)
    upsert(
        conn,
        ImageRow(
            uri=uri,
            source=str(source),
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            width=meta.width,
            height=meta.height,
            captured_at=meta.captured_at,
            camera_make=meta.camera_make,
            camera_model=meta.camera_model,
            has_gps=meta.has_gps,
            gps_lat=meta.gps_lat,
            gps_lon=meta.gps_lon,
        ),
    )
    return True


def _progress(result: IndexResult) -> None:
    print(
        f"\r{result.indexed} indexed, {result.skipped} skipped, {result.failed} failed",
        end="",
        file=sys.stderr,
        flush=True,
    )

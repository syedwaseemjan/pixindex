from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pixindex.db import ImageRow, connect, lookup, upsert
from pixindex.metadata import EXTENSIONS, JPEG_EXTENSIONS, read_metadata
from pixindex.s3 import (
    JPEG_RANGE,
    S3Error,
    S3Object,
    normalize_s3_source,
    parse_s3_uri,
)


class IndexSourceError(Exception):
    """The folder or s3:// URI cannot be indexed."""


@dataclass
class IndexResult:
    indexed: int = 0
    skipped: int = 0
    failed: int = 0


def index_source(source: str, db_path: Path, store=None) -> IndexResult:
    if source.startswith("s3://"):
        return index_s3(source, db_path, store=store)
    path = Path(source).expanduser()
    if not path.exists():
        raise IndexSourceError(f"Not found: {path}")
    return index_local(path, db_path)


def index_local(source: Path, db_path: Path) -> IndexResult:
    source = source.resolve()
    result = IndexResult()
    conn = connect(db_path)
    try:
        for path in iter_images(source):
            try:
                if _index_local_one(conn, source, path):
                    result.indexed += 1
                else:
                    result.skipped += 1
            except Exception as exc:
                result.failed += 1
                print(f"{path}: {exc}", file=sys.stderr)
            _progress(result)
    finally:
        conn.close()
        _end_progress(result)
    return result


def index_s3(uri: str, db_path: Path, store=None) -> IndexResult:
    from pixindex.s3 import BotoS3Store

    try:
        bucket, prefix = parse_s3_uri(uri)
    except S3Error as exc:
        raise IndexSourceError(str(exc)) from exc
    source = normalize_s3_source(bucket, prefix)
    client = store if store is not None else BotoS3Store()
    try:
        objects = client.list_images(bucket, prefix)
    except S3Error as exc:
        raise IndexSourceError(str(exc)) from exc

    result = IndexResult()
    conn = connect(db_path)
    try:
        for obj in objects:
            try:
                if _index_s3_one(conn, source, obj, client):
                    result.indexed += 1
                else:
                    result.skipped += 1
            except Exception as exc:
                result.failed += 1
                print(f"s3://{obj.bucket}/{obj.key}: {exc}", file=sys.stderr)
            _progress(result)
    finally:
        conn.close()
        _end_progress(result)
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


def _index_local_one(conn, source: Path, path: Path) -> bool:
    stat = path.stat()
    uri = str(path.resolve())
    existing = lookup(conn, uri)
    if existing is not None and (existing["size"], existing["mtime_ns"]) == (
        stat.st_size,
        stat.st_mtime_ns,
    ):
        return False
    _save(conn, source=str(source), uri=uri, size=stat.st_size, mtime_ns=stat.st_mtime_ns, meta=read_metadata(path))
    return True


def _index_s3_one(conn, source: str, obj: S3Object, store) -> bool:
    uri = f"s3://{obj.bucket}/{obj.key}"
    existing = lookup(conn, uri)
    if existing is not None and existing["etag"] == obj.etag and existing["size"] == obj.size:
        return False
    meta = read_metadata(_s3_bytes(store, obj))
    _save(
        conn,
        source=source,
        uri=uri,
        size=obj.size,
        mtime_ns=0,
        meta=meta,
        etag=obj.etag,
    )
    return True


def _s3_bytes(store, obj: S3Object) -> bytes:
    """Return the object bytes that ``read_metadata`` should parse.

    JPEG EXIF usually sits in the first 64 KiB, so a JPEG is fetched with a
    range GET first. ``read_metadata`` on that header is only a probe, its
    result is discarded. If the header parses, those bytes are enough and the
    rest of the object is left on S3. If it fails, because the EXIF runs past
    the range or the file is truncated, the whole object is fetched instead.
    PNG and WebP always take the full object.

    ``_index_s3_one`` calls ``read_metadata`` again on whatever this returns.
    That second call is the one whose metadata is saved.
    """
    suffix = Path(obj.key).suffix.lower()
    if suffix in JPEG_EXTENSIONS:
        header = store.get_bytes(obj, JPEG_RANGE)
        try:
            read_metadata(header)
            return header
        except Exception:
            return store.get_bytes(obj)
    return store.get_bytes(obj)


def _save(
    conn,
    *,
    source: str,
    uri: str,
    size: int,
    mtime_ns: int,
    meta,
    etag: str | None = None,
) -> None:
    upsert(
        conn,
        ImageRow(
            uri=uri,
            source=source,
            size=size,
            mtime_ns=mtime_ns,
            width=meta.width,
            height=meta.height,
            captured_at=meta.captured_at,
            camera_make=meta.camera_make,
            camera_model=meta.camera_model,
            has_gps=meta.has_gps,
            gps_lat=meta.gps_lat,
            gps_lon=meta.gps_lon,
            etag=etag,
        ),
    )


def _progress(result: IndexResult) -> None:
    print(
        f"\r{result.indexed} indexed, {result.skipped} skipped, {result.failed} failed",
        end="",
        file=sys.stderr,
        flush=True,
    )


def _end_progress(result: IndexResult) -> None:
    if result.indexed or result.skipped or result.failed:
        print(file=sys.stderr)

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pixindex.s3 import S3Error, normalize_s3_source, parse_s3_uri

_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")
_SIZE_UNITS = {
    "": 1,
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
}


class QueryError(ValueError):
    """User-facing problem with a search filter."""


@dataclass(frozen=True)
class Filters:
    source: str | None = None
    camera: str | None = None
    after: str | None = None
    before: str | None = None
    has_gps: bool | None = None
    ext: str | None = None
    min_size: int | None = None


def resolve_source(source: str | None) -> str | None:
    if source is None:
        return None
    if source.startswith("s3://"):
        try:
            bucket, prefix = parse_s3_uri(source)
        except S3Error as exc:
            raise QueryError(str(exc)) from exc
        return normalize_s3_source(bucket, prefix)
    return str(Path(source).expanduser().resolve())


def parse_filters(
    *,
    source: str | None = None,
    camera: str | None = None,
    after: str | None = None,
    before: str | None = None,
    has_gps: bool | None = None,
    ext: str | None = None,
    min_size: str | None = None,
) -> Filters:
    return Filters(
        source=resolve_source(source),
        camera=camera.strip() if camera else None,
        after=_parse_date(after, "--after"),
        before=_parse_date(before, "--before"),
        has_gps=has_gps,
        ext=_parse_ext(ext),
        min_size=_parse_size(min_size),
    )


def where_clause(filters: Filters) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if filters.source is not None:
        clauses.append("source = ?")
        params.append(filters.source)
    if filters.camera:
        clauses.append(
            "(LOWER(COALESCE(camera_make, '')) LIKE ? OR "
            "LOWER(COALESCE(camera_model, '')) LIKE ?)"
        )
        needle = f"%{filters.camera.lower()}%"
        params.extend([needle, needle])
    if filters.after:
        clauses.append("captured_at >= ?")
        params.append(filters.after)
    if filters.before:
        clauses.append("captured_at < ?")
        params.append(_next_day(filters.before))
    if filters.has_gps is True:
        clauses.append("has_gps = 1")
    elif filters.has_gps is False:
        clauses.append("has_gps = 0")
    if filters.ext:
        if filters.ext in {".jpg", ".jpeg"}:
            clauses.append("(LOWER(uri) LIKE ? OR LOWER(uri) LIKE ?)")
            params.extend(["%.jpg", "%.jpeg"])
        else:
            clauses.append("LOWER(uri) LIKE ?")
            params.append(f"%{filters.ext}")
    if filters.min_size is not None:
        clauses.append("size >= ?")
        params.append(filters.min_size)

    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params


def search_uris(conn: sqlite3.Connection, filters: Filters) -> list[str]:
    where, params = where_clause(filters)
    rows = conn.execute(
        f"SELECT uri FROM images{where} ORDER BY uri",
        params,
    )
    return [str(row["uri"]) for row in rows]


def _parse_date(value: str | None, flag: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise QueryError(f"{flag} must be YYYY-MM-DD, got {value!r}.") from exc


def _next_day(day: str) -> str:
    return (datetime.strptime(day, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()


def _parse_ext(value: str | None) -> str | None:
    if value is None:
        return None
    ext = value.strip().lower()
    if not ext:
        return None
    if not ext.startswith("."):
        ext = f".{ext}"
    return ext


def _parse_size(value: str | None) -> int | None:
    if value is None:
        return None
    match = _SIZE.match(value)
    if match is None:
        raise QueryError(f"--min-size must look like 5mb, got {value!r}.")
    amount = float(match.group(1))
    unit = match.group(2).lower()
    if unit not in _SIZE_UNITS:
        raise QueryError(f"Unknown size unit in --min-size {value!r}.")
    return int(amount * _SIZE_UNITS[unit])

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from pixindex.db import connect, fresh_hash, save_hash
from pixindex.dhash import dhash, hamming
from pixindex.pictures import open_picture
from pixindex.query import Filters, where_clause
from pixindex.stat import format_bytes

# How many of the 64 comparisons may differ and still count as the same shot.
# 0 means the fingerprints are identical. Lower is stricter.
DEFAULT_DISTANCE = 8


@dataclass
class DuplicateResult:
    hashed: int = 0
    skipped: int = 0
    failed: int = 0
    bytes_read: int = 0
    groups: list[list[str]] = field(default_factory=list)


def find_duplicates(
    db_path: Path,
    filters: Filters,
    distance: int = DEFAULT_DISTANCE,
    store=None,
    *,
    quiet: bool = False,
) -> DuplicateResult:
    """Group pictures whose light and dark pattern is almost the same.

    Comparing every pair is enough for a personal catalog. Each comparison
    is one 64-bit fingerprint, not a model.
    """
    result = DuplicateResult()
    conn = connect(db_path)
    try:
        where, params = where_clause(filters)
        rows = conn.execute(
            f"SELECT uri, size, mtime_ns, etag FROM images{where} ORDER BY uri",
            params,
        ).fetchall()
        fingerprints: list[tuple[str, str]] = []
        for row in rows:
            uri = str(row["uri"])
            try:
                saved = fresh_hash(conn, uri)
                if saved is not None:
                    result.skipped += 1
                    fingerprints.append((uri, saved))
                else:
                    image, nbytes = open_picture(
                        uri,
                        size=int(row["size"]),
                        mtime_ns=int(row["mtime_ns"]),
                        store=store,
                    )
                    result.bytes_read += nbytes
                    try:
                        fingerprint = dhash(image)
                    finally:
                        image.close()
                    save_hash(
                        conn,
                        uri=uri,
                        fingerprint=fingerprint,
                        size=int(row["size"]),
                        mtime_ns=int(row["mtime_ns"]),
                        etag=row["etag"],
                    )
                    result.hashed += 1
                    fingerprints.append((uri, fingerprint))
            except Exception as exc:
                result.failed += 1
                print(f"{uri}: {exc}", file=sys.stderr)
            _progress(result, quiet)
        result.groups = group_hashes(fingerprints, distance)
    finally:
        conn.close()
        _end_progress(result, quiet)
    return result


def group_hashes(items: list[tuple[str, str]], distance: int) -> list[list[str]]:
    parent = {uri: uri for uri, _fingerprint in items}

    def find(uri: str) -> str:
        while parent[uri] != uri:
            parent[uri] = parent[parent[uri]]
            uri = parent[uri]
        return uri

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for index, (left_uri, left_hash) in enumerate(items):
        for right_uri, right_hash in items[index + 1 :]:
            if hamming(left_hash, right_hash) <= distance:
                union(left_uri, right_uri)

    clusters: dict[str, list[str]] = {}
    for uri, _fingerprint in items:
        clusters.setdefault(find(uri), []).append(uri)
    groups = [sorted(members) for members in clusters.values() if len(members) > 1]
    groups.sort(key=lambda members: members[0])
    return groups


def format_duplicate_result(result: DuplicateResult) -> str:
    count = len(result.groups)
    noun = "group" if count == 1 else "groups"
    return (
        f"Hashed {result.hashed}, skipped {result.skipped}, "
        f"failed {result.failed}. Read {format_bytes(result.bytes_read)}. "
        f"{count} {noun}."
    )


def _progress(result: DuplicateResult, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"\r{result.hashed} hashed, {result.skipped} skipped, {result.failed} failed",
        end="",
        file=sys.stderr,
        flush=True,
    )


def _end_progress(result: DuplicateResult, quiet: bool) -> None:
    if quiet:
        return
    if result.hashed or result.skipped or result.failed:
        print(file=sys.stderr)

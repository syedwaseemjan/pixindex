from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from pixindex.db import connect, fresh_embedding, save_embedding
from pixindex.embedder import EmbedError
from pixindex.pictures import open_picture
from pixindex.query import Filters, where_clause
from pixindex.stat import format_bytes
from pixindex.vectors import pack_vector


@dataclass
class EmbedResult:
    embedded: int = 0
    skipped: int = 0
    failed: int = 0
    bytes_read: int = 0


def embed_catalog(
    db_path: Path,
    embedder,
    filters: Filters,
    store=None,
    *,
    quiet: bool = False,
) -> EmbedResult:
    """Build number lists for pictures that do not have one yet.

    A saved list is reused when the model is the same and the file fingerprint
    in the catalog is unchanged. Lists from a different model are rebuilt.
    """
    result = EmbedResult()
    conn = connect(db_path)
    try:
        where, params = where_clause(filters)
        rows = conn.execute(
            f"SELECT uri, size, mtime_ns, etag FROM images{where} ORDER BY uri",
            params,
        ).fetchall()
        for row in rows:
            uri = str(row["uri"])
            try:
                if fresh_embedding(conn, uri, embedder.model_id):
                    result.skipped += 1
                else:
                    image, nbytes = open_picture(
                        uri,
                        size=int(row["size"]),
                        mtime_ns=int(row["mtime_ns"]),
                        store=store,
                    )
                    result.bytes_read += nbytes
                    try:
                        vector = embedder.embed_image(image)
                    finally:
                        image.close()
                    save_embedding(
                        conn,
                        uri=uri,
                        model_id=embedder.model_id,
                        vector=pack_vector(vector),
                        size=int(row["size"]),
                        mtime_ns=int(row["mtime_ns"]),
                        etag=row["etag"],
                    )
                    result.embedded += 1
            except EmbedError:
                raise
            except Exception as exc:
                result.failed += 1
                print(f"{uri}: {exc}", file=sys.stderr)
            _progress(result, quiet)
    finally:
        conn.close()
        _end_progress(result, quiet)
    return result


def format_embed_result(result: EmbedResult, model_id: str) -> str:
    return (
        f"Embedded {result.embedded}, skipped {result.skipped}, "
        f"failed {result.failed}. Read {format_bytes(result.bytes_read)}. "
        f"Model {model_id}."
    )


def _progress(result: EmbedResult, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"\r{result.embedded} embedded, {result.skipped} skipped, {result.failed} failed",
        end="",
        file=sys.stderr,
        flush=True,
    )


def _end_progress(result: EmbedResult, quiet: bool) -> None:
    if quiet:
        return
    if result.embedded or result.skipped or result.failed:
        print(file=sys.stderr)

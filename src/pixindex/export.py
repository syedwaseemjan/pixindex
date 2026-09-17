from __future__ import annotations

import csv
import json
import sqlite3
from io import StringIO

from pixindex.query import Filters, QueryError, where_clause

COLUMNS = (
    "uri",
    "source",
    "size",
    "width",
    "height",
    "captured_at",
    "camera_make",
    "camera_model",
    "has_gps",
    "gps_lat",
    "gps_lon",
)


def search_rows(conn: sqlite3.Connection, filters: Filters) -> list[dict]:
    where, params = where_clause(filters)
    columns = ", ".join(COLUMNS)
    rows = conn.execute(
        f"SELECT {columns} FROM images{where} ORDER BY uri",
        params,
    )
    exported = []
    for row in rows:
        item = {name: row[name] for name in COLUMNS}
        item["has_gps"] = bool(item["has_gps"])
        exported.append(item)
    return exported


def parse_format(output_format: str) -> str:
    fmt = output_format.strip().lower()
    if fmt not in {"csv", "json"}:
        raise QueryError("Format must be csv or json.")
    return fmt


def render_export(rows: list[dict], output_format: str) -> str:
    fmt = parse_format(output_format)
    if fmt == "json":
        return json.dumps(rows, indent=2) + "\n"
    return _csv(rows)


def _csv(rows: list[dict]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                **row,
                "has_gps": "true" if row["has_gps"] else "false",
            }
        )
    return buffer.getvalue()

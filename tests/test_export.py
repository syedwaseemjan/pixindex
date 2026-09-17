import csv
import json
from io import StringIO
from pathlib import Path

import pytest

from pixindex.db import ImageRow, connect, upsert
from pixindex.export import parse_format, render_export, search_rows
from pixindex.query import QueryError, parse_filters


def _row(uri: str, source: str, **kwargs) -> ImageRow:
    return ImageRow(
        uri=uri,
        source=source,
        size=kwargs.get("size", 100),
        mtime_ns=1,
        width=8,
        height=8,
        captured_at=kwargs.get("captured_at"),
        camera_make=kwargs.get("camera_make"),
        camera_model=kwargs.get("camera_model"),
        has_gps=kwargs.get("has_gps", False),
        gps_lat=1.0 if kwargs.get("has_gps") else None,
        gps_lon=2.0 if kwargs.get("has_gps") else None,
    )


def test_parse_format() -> None:
    assert parse_format("CSV") == "csv"
    assert parse_format(" json ") == "json"
    with pytest.raises(QueryError, match="csv or json"):
        parse_format("xlsx")


def test_export_json_and_csv(tmp_path: Path) -> None:
    db = tmp_path / "catalog.sqlite"
    conn = connect(db)
    source = str(tmp_path / "photos")
    upsert(
        conn,
        _row(
            f"{source}/a.jpg",
            source,
            camera_make="Canon",
            camera_model="EOS R6",
            has_gps=True,
            captured_at="2024-03-12T10:00:00",
        ),
    )
    upsert(conn, _row(f"{source}/b.png", source, camera_make="Apple"))

    rows = search_rows(conn, parse_filters(camera="Canon"))
    conn.close()
    assert len(rows) == 1
    assert rows[0]["has_gps"] is True
    assert rows[0]["uri"].endswith("a.jpg")

    payload = json.loads(render_export(rows, "json"))
    assert payload[0]["camera_make"] == "Canon"
    assert payload[0]["has_gps"] is True

    table = list(csv.DictReader(StringIO(render_export(rows, "csv"))))
    assert table[0]["has_gps"] == "true"
    assert table[0]["camera_model"] == "EOS R6"


def test_empty_export_still_has_csv_header() -> None:
    csv_text = render_export([], "csv")
    assert csv_text.startswith("uri,source,size,")
    assert json.loads(render_export([], "json")) == []

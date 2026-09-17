from pathlib import Path

import pytest

from pixindex.db import ImageRow, connect, upsert
from pixindex.query import QueryError, parse_filters, search_uris


def _row(
    uri: str,
    source: str,
    *,
    size: int = 100,
    camera_make: str | None = None,
    camera_model: str | None = None,
    captured_at: str | None = None,
    has_gps: bool = False,
) -> ImageRow:
    return ImageRow(
        uri=uri,
        source=source,
        size=size,
        mtime_ns=1,
        width=8,
        height=8,
        captured_at=captured_at,
        camera_make=camera_make,
        camera_model=camera_model,
        has_gps=has_gps,
        gps_lat=1.0 if has_gps else None,
        gps_lon=2.0 if has_gps else None,
    )


def _catalog(tmp_path: Path):
    db = tmp_path / "catalog.sqlite"
    conn = connect(db)
    source = str(tmp_path / "photos")
    upsert(
        conn,
        _row(
            f"{source}/canon.jpg",
            source,
            size=5_000_000,
            camera_make="Canon",
            camera_model="EOS R6",
            captured_at="2024-03-12T10:00:00",
            has_gps=True,
        ),
    )
    upsert(
        conn,
        _row(
            f"{source}/iphone.png",
            source,
            size=200_000,
            camera_make="Apple",
            camera_model="iPhone 15",
            captured_at="2024-11-02T18:00:00",
        ),
    )
    return conn, source


def test_search_camera_and_gps(tmp_path: Path) -> None:
    conn, source = _catalog(tmp_path)
    hits = search_uris(conn, parse_filters(camera="canon", has_gps=True))
    assert hits == [f"{source}/canon.jpg"]
    conn.close()


def test_search_date_range_is_inclusive(tmp_path: Path) -> None:
    conn, source = _catalog(tmp_path)
    hits = search_uris(
        conn, parse_filters(after="2024-03-12", before="2024-03-12")
    )
    assert hits == [f"{source}/canon.jpg"]
    conn.close()


def test_search_ext_and_min_size(tmp_path: Path) -> None:
    conn, source = _catalog(tmp_path)
    hits = search_uris(conn, parse_filters(ext="jpg", min_size="1mb"))
    assert hits == [f"{source}/canon.jpg"]
    no_hits = search_uris(conn, parse_filters(ext="png", min_size="1mb"))
    assert no_hits == []
    conn.close()


def test_search_source_filter(tmp_path: Path) -> None:
    conn, source = _catalog(tmp_path)
    other = str(tmp_path / "other")
    upsert(conn, _row(f"{other}/x.jpg", other, camera_make="Canon"))
    hits = search_uris(conn, parse_filters(source=str(tmp_path / "photos"), camera="Canon"))
    assert hits == [f"{source}/canon.jpg"]
    conn.close()


def test_bad_date() -> None:
    with pytest.raises(QueryError, match="--after"):
        parse_filters(after="12-03-2024")


def test_bad_min_size() -> None:
    with pytest.raises(QueryError, match="--min-size"):
        parse_filters(min_size="huge")

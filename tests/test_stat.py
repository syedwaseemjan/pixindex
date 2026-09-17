from pathlib import Path

from PIL import Image

from pixindex.db import ImageRow, connect, upsert
from pixindex.index import index_local
from pixindex.stat import catalog_stats, format_bytes, format_stats


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
        gps_lat=33.7 if has_gps else None,
        gps_lon=73.0 if has_gps else None,
    )


def test_format_bytes() -> None:
    assert format_bytes(200) == "200 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(2 * 1024 * 1024) == "2.0 MB"


def test_empty_catalog(tmp_path: Path) -> None:
    conn = connect(tmp_path / "empty.sqlite")
    stats = catalog_stats(conn)
    assert stats.files == 0
    assert format_stats(stats) == "No pictures in the catalog yet."
    conn.close()


def test_summary_counts_cameras_dates_and_gps(tmp_path: Path) -> None:
    db = tmp_path / "catalog.sqlite"
    conn = connect(db)
    source = str(tmp_path / "photos")
    upsert(
        conn,
        _row(
            f"{source}/a.jpg",
            source,
            size=1000,
            camera_make="Canon",
            camera_model="EOS R6",
            captured_at="2024-03-12T10:00:00",
            has_gps=True,
        ),
    )
    upsert(
        conn,
        _row(
            f"{source}/b.jpg",
            source,
            size=3000,
            camera_make="Canon",
            camera_model="EOS R6",
            captured_at="2024-11-02T18:00:00",
        ),
    )
    upsert(
        conn,
        _row(
            f"{source}/c.jpg",
            source,
            size=1000,
            camera_make="Apple",
            camera_model="iPhone 15",
            captured_at="2024-06-01T12:00:00",
        ),
    )

    stats = catalog_stats(conn)
    conn.close()

    assert stats.files == 3
    assert stats.bytes == 5000
    assert stats.with_gps == 1
    assert stats.first_captured == "2024-03-12"
    assert stats.last_captured == "2024-11-02"
    assert [camera.name for camera in stats.cameras] == [
        "Canon EOS R6",
        "Apple iPhone 15",
    ]

    text = format_stats(stats)
    assert "3 pictures" in text
    assert "Taken: 2024-03-12 to 2024-11-02" in text
    assert "With GPS: 1 of 3 (33%)" in text
    assert "Canon EOS R6" in text


def test_source_filter(tmp_path: Path) -> None:
    db = tmp_path / "catalog.sqlite"
    conn = connect(db)
    one = str(tmp_path / "one")
    two = str(tmp_path / "two")
    upsert(conn, _row(f"{one}/a.jpg", one, size=10))
    upsert(conn, _row(f"{two}/b.jpg", two, size=20))
    stats = catalog_stats(conn, source=one)
    conn.close()
    assert stats.files == 1
    assert stats.bytes == 10


def test_stat_after_index(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (8, 8), color="red").save(photos / "shot.png")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db)

    conn = connect(db)
    stats = catalog_stats(conn)
    conn.close()
    assert stats.files == 1
    assert stats.with_gps == 0
    assert stats.cameras[0].name == "unknown"
    assert "1 picture" in format_stats(stats)
    assert "Taken: unknown" in format_stats(stats)

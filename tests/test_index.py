from pathlib import Path

from PIL import Image

from pixindex.db import connect
from pixindex.index import index_local


def _png(path: Path, size: tuple[int, int] = (8, 8)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color="blue").save(path)
    return path


def test_index_then_skip_unchanged(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _png(photos / "a.png")
    _png(photos / "nested" / "b.png", size=(4, 2))
    db = tmp_path / "catalog.sqlite"

    first = index_local(photos, db)
    assert (first.indexed, first.skipped, first.failed) == (2, 0, 0)

    second = index_local(photos, db)
    assert (second.indexed, second.skipped, second.failed) == (0, 2, 0)

    conn = connect(db)
    rows = conn.execute(
        "SELECT uri, width, height FROM images ORDER BY uri"
    ).fetchall()
    conn.close()
    assert len(rows) == 2
    assert {row["width"] for row in rows} == {8, 4}


def test_reindex_after_change(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    image = _png(photos / "a.png")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db)

    Image.new("RGB", (20, 10), color="green").save(image)
    result = index_local(photos, db)
    assert result.indexed == 1

    conn = connect(db)
    row = conn.execute("SELECT width, height FROM images").fetchone()
    conn.close()
    assert (row["width"], row["height"]) == (20, 10)


def test_corrupt_file_is_failed_not_fatal(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "bad.jpg").write_text("not an image")
    _png(photos / "good.png")
    db = tmp_path / "catalog.sqlite"

    result = index_local(photos, db)
    assert result.indexed == 1
    assert result.failed == 1

    conn = connect(db)
    count = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    conn.close()
    assert count == 1


def test_skips_hidden_files_and_dirs(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _png(photos / "visible.png")
    _png(photos / ".hidden.png")
    _png(photos / ".thumbs" / "thumb.png")
    db = tmp_path / "catalog.sqlite"

    result = index_local(photos, db)
    assert result.indexed == 1

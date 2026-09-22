from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pixindex.db import connect
from pixindex.duplicates import find_duplicates, format_duplicate_result
from pixindex.index import index_local
from pixindex.query import Filters, parse_filters


def _bar(path: Path, size: tuple[int, int], box: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).rectangle(box, fill="black")
    image.save(path)

def test_copies_group_and_a_different_shape_does_not(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _bar(photos / "left.png", (64, 64), (0, 0, 31, 63))
    _bar(photos / "left-small.png", (32, 32), (0, 0, 15, 31))
    _bar(photos / "right.png", (64, 64), (32, 0, 63, 63))
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)

    first = find_duplicates(db, Filters(), quiet=True)
    assert len(first.groups) == 1
    names = {Path(uri).name for uri in first.groups[0]}
    assert names == {"left.png", "left-small.png"}
    assert first.hashed == 3
    assert first.bytes_read > 0
    assert "1 group." in format_duplicate_result(first)

    second = find_duplicates(db, Filters(), quiet=True)
    assert second.hashed == 0
    assert second.skipped == 3
    assert second.bytes_read == 0
    assert len(second.groups) == 1

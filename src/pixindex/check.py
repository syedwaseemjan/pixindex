from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from pixindex.db import connect
from pixindex.duplicates import DEFAULT_DISTANCE, find_duplicates
from pixindex.embed import embed_catalog
from pixindex.index import index_local
from pixindex.query import Filters
from pixindex.similar import search_pictures


@dataclass(frozen=True)
class CheckReport:
    search_passed: int
    search_total: int
    duplicates_passed: bool

    @property
    def ok(self) -> bool:
        return self.duplicates_passed and self.search_passed == self.search_total


def run_check(embedder) -> CheckReport:
    """Score picture search and copy grouping on a few drawn examples.

    The examples are created in a temporary folder. The user's catalog is
    not read or changed.
    """
    with TemporaryDirectory() as tmp:
        photos = Path(tmp) / "photos"
        photos.mkdir()
        _write_examples(photos)
        db = Path(tmp) / "catalog.sqlite"
        index_local(photos, db, quiet=True)
        embed_catalog(db, embedder, Filters(), quiet=True)
        conn = connect(db)
        try:
            search_passed, search_total = _score_search(conn, embedder, photos)
        finally:
            conn.close()
        duplicates = find_duplicates(db, Filters(), DEFAULT_DISTANCE, quiet=True)
        return CheckReport(
            search_passed=search_passed,
            search_total=search_total,
            duplicates_passed=_score_duplicates(duplicates.groups, photos),
        )


def format_check(report: CheckReport) -> str:
    duplicates = "1/1" if report.duplicates_passed else "0/1"
    return (
        f"Picture search: {report.search_passed}/{report.search_total}\n"
        f"Duplicates: {duplicates}"
    )


def _write_examples(photos: Path) -> None:
    _bar(photos / "red-left.png", (64, 64), (0, 0, 31, 63), "red")
    _bar(photos / "red-left-small.png", (32, 32), (0, 0, 15, 31), "red")
    _bar(photos / "blue-right.png", (64, 64), (32, 0, 63, 63), "blue")
    _bar(photos / "green-top.png", (64, 64), (0, 0, 63, 31), "green")


def _bar(path: Path, size: tuple[int, int], box: tuple[int, int, int, int], color: str) -> None:
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).rectangle(box, fill=color)
    image.save(path)


def _score_search(conn, embedder, photos: Path) -> tuple[int, int]:
    expectations = (
        ("red", {"red-left.png", "red-left-small.png"}),
        ("blue", {"blue-right.png"}),
    )
    passed = 0
    for text, names in expectations:
        matches, _missing = search_pictures(
            conn, Filters(), text, embedder, limit=len(names)
        )
        got = {Path(match.uri).name for match in matches}
        if got == names:
            passed += 1
    return passed, len(expectations)


def _score_duplicates(groups: list[list[str]], photos: Path) -> bool:
    left = str((photos / "red-left.png").resolve())
    small = str((photos / "red-left-small.png").resolve())
    outsider = str((photos / "blue-right.png").resolve())
    return any(
        left in group and small in group and outsider not in group for group in groups
    )

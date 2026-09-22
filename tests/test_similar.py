from __future__ import annotations

from pathlib import Path

from PIL import Image

from color_embedder import ColorEmbedder
from pixindex.db import connect, save_embedding
from pixindex.embed import embed_catalog
from pixindex.index import index_local
from pixindex.query import Filters, parse_filters
from pixindex.similar import search_pictures
from pixindex.vectors import pack_vector


def _save(path: Path, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color).save(path)


def _ready(tmp_path: Path) -> tuple[Path, Path]:
    photos = tmp_path / "photos"
    _save(photos / "red.png", "red")
    _save(photos / "blue.png", "blue")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)
    embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)
    return photos, db


def test_words_rank_the_closer_color(tmp_path: Path) -> None:
    _photos, db = _ready(tmp_path)
    conn = connect(db)
    matches, missing = search_pictures(conn, Filters(), "red", ColorEmbedder(), limit=2)
    conn.close()

    assert missing == 0
    assert Path(matches[0].uri).name == "red.png"
    assert Path(matches[1].uri).name == "blue.png"
    assert matches[0].score > matches[1].score


def test_filters_run_before_the_words(tmp_path: Path) -> None:
    _photos, db = _ready(tmp_path)
    conn = connect(db)
    conn.execute(
        "UPDATE images SET camera_make = 'Canon' WHERE uri LIKE ?",
        ("%/blue.png",),
    )
    conn.execute(
        "UPDATE images SET camera_make = 'Nikon' WHERE uri LIKE ?",
        ("%/red.png",),
    )
    conn.commit()
    filters = parse_filters(camera="Canon")
    matches, missing = search_pictures(conn, filters, "red", ColorEmbedder(), limit=5)
    conn.close()

    assert missing == 0
    assert [Path(match.uri).name for match in matches] == ["blue.png"]


def test_pictures_without_a_list_are_counted(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _save(photos / "red.png", "red")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)

    conn = connect(db)
    matches, missing = search_pictures(conn, Filters(), "red", ColorEmbedder(), limit=5)
    conn.close()
    assert matches == []
    assert missing == 1


def test_an_old_model_is_not_used(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _save(photos / "red.png", "red")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)

    conn = connect(db)
    row = conn.execute("SELECT uri, size, mtime_ns FROM images").fetchone()
    save_embedding(
        conn,
        uri=row["uri"],
        model_id="old",
        vector=pack_vector([1.0, 0.0, 0.0]),
        size=row["size"],
        mtime_ns=row["mtime_ns"],
        etag=None,
    )
    matches, missing = search_pictures(conn, Filters(), "red", ColorEmbedder(), limit=5)
    conn.close()
    assert matches == []
    assert missing == 1


def test_limit_keeps_the_best_matches(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _save(photos / "red.png", "red")
    _save(photos / "blue.png", "blue")
    _save(photos / "green.png", "green")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)
    embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)

    conn = connect(db)
    matches, _missing = search_pictures(conn, Filters(), "red", ColorEmbedder(), limit=1)
    conn.close()
    assert [Path(match.uri).name for match in matches] == ["red.png"]

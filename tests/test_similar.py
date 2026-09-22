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

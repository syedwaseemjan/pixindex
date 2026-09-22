from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from color_embedder import ColorEmbedder
from pixindex.db import connect
from pixindex.embed import embed_catalog, format_embed_result
from pixindex.index import index_local
from pixindex.query import Filters


def _png(path: Path, color: str = "red", size: tuple[int, int] = (16, 16)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)

def test_second_run_skips_and_reads_nothing(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _png(photos / "a.png")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)

    first = embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)
    second = embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)

    assert first.embedded == 1
    assert first.bytes_read > 0
    assert (second.embedded, second.skipped, second.failed, second.bytes_read) == (0, 1, 0, 0)
    assert "Model color." in format_embed_result(first, "color")

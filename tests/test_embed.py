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

def test_a_different_model_is_rebuilt(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _png(photos / "a.png")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)
    embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)

    conn = connect(db)
    conn.execute("UPDATE embeddings SET model_id = 'old'")
    conn.commit()
    conn.close()

    again = embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)
    assert again.embedded == 1

    conn = connect(db)
    model_id = conn.execute("SELECT model_id FROM embeddings").fetchone()["model_id"]
    conn.close()
    assert model_id == "color"

def test_reindex_drops_the_old_list(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    image = photos / "a.png"
    _png(image)
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)
    embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)

    _png(image, color="blue", size=(20, 10))
    index_local(photos, db, quiet=True)

    conn = connect(db)
    count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    conn.close()
    assert count == 0

    again = embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)
    assert again.embedded == 1

def test_changed_file_is_not_embedded_until_reindex(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    image = photos / "a.png"
    _png(image)
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)

    _png(image, color="blue", size=(24, 8))
    result = embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)
    assert result.embedded == 0
    assert result.failed == 1
    assert result.bytes_read == 0

def test_one_bad_file_does_not_stop_the_rest(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    _png(photos / "good.png")
    db = tmp_path / "catalog.sqlite"
    index_local(photos, db, quiet=True)

    conn = connect(db)
    conn.execute(
        """
        INSERT INTO images (
            uri, source, size, mtime_ns, has_gps, indexed_at
        ) VALUES (?, ?, ?, ?, 0, '2024-01-01T00:00:00+00:00')
        """,
        (str(tmp_path / "missing.png"), str(photos), 10, 1),
    )
    conn.commit()
    conn.close()

    result = embed_catalog(db, ColorEmbedder(), Filters(), quiet=True)
    assert result.embedded == 1
    assert result.failed == 1

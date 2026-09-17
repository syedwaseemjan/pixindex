from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from pixindex.db import connect
from pixindex.index import IndexSourceError, index_s3
from pixindex.query import parse_filters
from pixindex.s3 import (
    JPEG_RANGE,
    S3Error,
    S3Object,
    is_image_key,
    normalize_s3_source,
    parse_s3_uri,
)


def _image_bytes(fmt: str, size: tuple[int, int] = (8, 8)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color="red").save(buffer, format=fmt)
    return buffer.getvalue()


class FakeStore:
    def __init__(self, objects: dict[str, tuple[bytes, str]]) -> None:
        self.objects = objects
        self.gets: list[tuple[str, tuple[int, int] | None]] = []

    def list_images(self, bucket: str, prefix: str) -> list[S3Object]:
        items = []
        for key, (data, etag) in self.objects.items():
            if prefix and not key.startswith(prefix):
                continue
            if not is_image_key(key):
                continue
            items.append(S3Object(bucket, key, len(data), etag))
        return items

    def get_bytes(
        self, obj: S3Object, byte_range: tuple[int, int] | None = None
    ) -> bytes:
        self.gets.append((obj.key, byte_range))
        data = self.objects[obj.key][0]
        if byte_range is None:
            return data
        start, end = byte_range
        return data[start : end + 1]


def test_parse_and_normalize_s3_uri() -> None:
    assert parse_s3_uri("s3://media") == ("media", "")
    assert parse_s3_uri("s3://media/photos/2024/") == ("media", "photos/2024/")
    assert normalize_s3_source("media", "photos/2024/") == "s3://media/photos/2024"
    with pytest.raises(S3Error, match="bucket"):
        parse_s3_uri("s3://")


def test_search_source_accepts_s3_uri() -> None:
    filters = parse_filters(source="s3://media/photos/")
    assert filters.source == "s3://media/photos"


def test_index_s3_then_skip(tmp_path: Path) -> None:
    store = FakeStore(
        {
            "photos/a.jpg": (_image_bytes("JPEG"), "etag-a"),
            "photos/b.png": (_image_bytes("PNG"), "etag-b"),
            "photos/.hidden.jpg": (_image_bytes("JPEG"), "etag-h"),
            "photos/notes.txt": (b"hi", "etag-t"),
        }
    )
    db = tmp_path / "catalog.sqlite"
    first = index_s3("s3://media/photos/", db, store=store)
    assert (first.indexed, first.skipped, first.failed) == (2, 0, 0)

    second = index_s3("s3://media/photos", db, store=store)
    assert (second.indexed, second.skipped, second.failed) == (0, 2, 0)

    conn = connect(db)
    rows = conn.execute("SELECT uri, etag, source FROM images ORDER BY uri").fetchall()
    conn.close()
    assert [row["uri"] for row in rows] == [
        "s3://media/photos/a.jpg",
        "s3://media/photos/b.png",
    ]
    assert rows[0]["source"] == "s3://media/photos"
    assert rows[0]["etag"] == "etag-a"


def test_index_s3_reindexes_when_etag_changes(tmp_path: Path) -> None:
    jpeg = _image_bytes("JPEG", (8, 8))
    store = FakeStore({"shot.jpg": (jpeg, "v1")})
    db = tmp_path / "catalog.sqlite"
    index_s3("s3://media", db, store=store)

    store.objects["shot.jpg"] = (_image_bytes("JPEG", (16, 9)), "v2")
    result = index_s3("s3://media", db, store=store)
    assert result.indexed == 1

    conn = connect(db)
    row = conn.execute("SELECT width, etag FROM images").fetchone()
    conn.close()
    assert (row["width"], row["etag"]) == (16, "v2")


def test_jpeg_uses_range_get(tmp_path: Path) -> None:
    store = FakeStore({"x.jpg": (_image_bytes("JPEG"), "e1")})
    index_s3("s3://media", tmp_path / "c.sqlite", store=store)
    assert store.gets[0] == ("x.jpg", JPEG_RANGE)


def test_png_uses_full_get(tmp_path: Path) -> None:
    store = FakeStore({"x.png": (_image_bytes("PNG"), "e1")})
    index_s3("s3://media", tmp_path / "c.sqlite", store=store)
    assert store.gets[0] == ("x.png", None)


def test_bad_s3_object_is_failed_not_fatal(tmp_path: Path) -> None:
    store = FakeStore(
        {
            "bad.jpg": (b"not an image", "bad"),
            "good.png": (_image_bytes("PNG"), "good"),
        }
    )
    result = index_s3("s3://media", tmp_path / "c.sqlite", store=store)
    assert result.indexed == 1
    assert result.failed == 1


def test_list_error_stops_the_run(tmp_path: Path) -> None:
    class Boom:
        def list_images(self, bucket: str, prefix: str):
            raise S3Error("No AWS credentials. Set AWS_PROFILE or AWS_ACCESS_KEY_ID.")

    with pytest.raises(IndexSourceError, match="AWS credentials"):
        index_s3("s3://media", tmp_path / "c.sqlite", store=Boom())

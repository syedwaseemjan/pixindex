from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image


class PictureError(Exception):
    """The picture file could not be read for a full look at the pixels."""


def open_picture(
    uri: str,
    *,
    size: int,
    mtime_ns: int,
    store=None,
) -> tuple[Image.Image, int]:
    """Open the full picture and return it with how many bytes were read.

    Refuses when the file no longer matches the catalog. The caller should
    run index again before trusting the pixels.
    """
    path = Path(uri)
    if not path.is_file():
        raise PictureError("file is missing; run pixindex index")
    stat = path.stat()
    if stat.st_size != size or stat.st_mtime_ns != mtime_ns:
        raise PictureError("file changed since index; run pixindex index")
    data = path.read_bytes()

    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as exc:
        raise PictureError(f"could not read the picture: {exc}") from exc
    return image, len(data)

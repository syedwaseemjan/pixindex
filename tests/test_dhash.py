from __future__ import annotations

from PIL import Image, ImageDraw

from pixindex.dhash import dhash, hamming
from pixindex.duplicates import DEFAULT_DISTANCE


def _bar(size: tuple[int, int], box: tuple[int, int, int, int], color: str) -> Image.Image:
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).rectangle(box, fill=color)
    return image


def test_same_pixels_match_and_a_different_shape_is_farther() -> None:
    original = _bar((64, 64), (0, 0, 31, 63), "red")
    smaller = _bar((32, 32), (0, 0, 15, 31), "red")
    other = _bar((64, 64), (32, 0, 63, 63), "blue")
    top = _bar((64, 64), (0, 0, 63, 31), "green")

    assert hamming(dhash(original), dhash(original.copy())) == 0
    close = hamming(dhash(original), dhash(smaller))
    far = hamming(dhash(original), dhash(other))
    upward = hamming(dhash(original), dhash(top))
    assert close <= DEFAULT_DISTANCE, (close, far, upward)
    assert far > DEFAULT_DISTANCE, (close, far, upward)
    assert upward > DEFAULT_DISTANCE, (close, far, upward)
    assert close < far

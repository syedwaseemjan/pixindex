from __future__ import annotations

from PIL import Image

# 8 rows, and 9 columns so each row has 8 left-versus-right comparisons.
_WIDTH = 9
_HEIGHT = 8


def dhash(image: Image.Image) -> str:
    """Fingerprint the light and dark pattern of a picture.

    The same shot saved again, or saved smaller, usually gets the same
    fingerprint. This does not look at colors on purpose, and it does not
    use a model. The result is 16 hex characters (64 yes/no comparisons).
    """
    gray = image.convert("L").resize((_WIDTH, _HEIGHT), Image.Resampling.LANCZOS)
    bits = 0
    for y in range(_HEIGHT):
        for x in range(_WIDTH - 1):
            left = int(gray.getpixel((x, y)))
            right = int(gray.getpixel((x + 1, y)))
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()

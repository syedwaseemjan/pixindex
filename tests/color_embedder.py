from __future__ import annotations

from PIL import Image, ImageStat


class ColorEmbedder:
    """Stand-in for the real model, used in tests.

    A picture becomes its average color. The words "red", "green", and "blue"
    point at those colors. No download, and the same picture always gives the
    same list of numbers.
    """

    model_id = "color"

    def embed_image(self, image: Image.Image) -> list[float]:
        red, green, blue = ImageStat.Stat(image.convert("RGB")).mean
        return _unit([red / 255, green / 255, blue / 255])

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0, 0.0, 0.0]
        words = {
            "red": (1.0, 0.0, 0.0),
            "green": (0.0, 1.0, 0.0),
            "blue": (0.0, 0.0, 1.0),
        }
        for word, color in words.items():
            if word in text.lower():
                vector = [left + right for left, right in zip(vector, color)]
        if vector == [0.0, 0.0, 0.0]:
            vector = [1.0, 1.0, 1.0]
        return _unit(vector)


def _unit(vector: list[float]) -> list[float]:
    length = sum(value * value for value in vector) ** 0.5
    if length == 0:
        return vector
    return [value / length for value in vector]

from __future__ import annotations

from typing import Protocol

from PIL import Image

# One id for the text model and the picture model together. They only make
# sense as a pair: both turn input into the same kind of number list.
# Change this if either model name below changes, so old lists are not
# mixed with new ones.
MODEL_ID = "Qdrant/clip-ViT-B-32"
TEXT_MODEL = "Qdrant/clip-ViT-B-32-text"
VISION_MODEL = "Qdrant/clip-ViT-B-32-vision"


class EmbedError(Exception):
    """The picture model is missing or could not be loaded."""


class Embedder(Protocol):
    model_id: str

    def embed_image(self, image: Image.Image) -> list[float]: ...

    def embed_text(self, text: str) -> list[float]: ...


class ClipEmbedder:
    model_id = MODEL_ID

    def __init__(self) -> None:
        self._image = None
        self._text = None

    def load(self) -> None:
        if self._image is not None and self._text is not None:
            return
        try:
            from fastembed import ImageEmbedding, TextEmbedding
        except ImportError as exc:
            raise EmbedError(
                "Picture search needs an extra install: pip install 'pixindex[embed]'"
            ) from exc
        try:
            self._image = ImageEmbedding(model_name=VISION_MODEL)
            self._text = TextEmbedding(model_name=TEXT_MODEL)
        except Exception as exc:
            raise EmbedError(
                "Could not load the picture model. "
                "The first run downloads it (about 600 MB) and needs a network connection. "
                f"{exc}"
            ) from exc

    def embed_image(self, image: Image.Image) -> list[float]:
        self.load()
        assert self._image is not None
        vector = next(iter(self._image.embed([image.convert("RGB")])))
        return [float(value) for value in vector]

    def embed_text(self, text: str) -> list[float]:
        self.load()
        assert self._text is not None
        vector = next(iter(self._text.embed([text])))
        return [float(value) for value in vector]


def load_embedder() -> ClipEmbedder:
    embedder = ClipEmbedder()
    embedder.load()
    return embedder

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



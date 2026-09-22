from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from io import BytesIO

from PIL import Image
from PIL.ExifTags import IFD

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
JPEG_EXTENSIONS = {".jpg", ".jpeg"}

MAKE = 271
MODEL = 272
DATETIME = 306
DATETIME_ORIGINAL = 36867
DATETIME_DIGITIZED = 36868
GPS_LATITUDE_REF = 1
GPS_LATITUDE = 2
GPS_LONGITUDE_REF = 3
GPS_LONGITUDE = 4


@dataclass(frozen=True)
class ImageMeta:
    width: int | None
    height: int | None
    captured_at: str | None
    camera_make: str | None
    camera_model: str | None
    gps_lat: float | None
    gps_lon: float | None

    @property
    def has_gps(self) -> bool:
        return self.gps_lat is not None and self.gps_lon is not None


def read_metadata(source: Path | bytes) -> ImageMeta:
    opened = BytesIO(source) if isinstance(source, bytes) else source
    with Image.open(opened) as img:
        width, height = img.size
        exif = img.getexif()

    make = _as_str(exif.get(MAKE)) if exif else None
    model = _as_str(exif.get(MODEL)) if exif else None
    captured_at = None
    gps_lat = None
    gps_lon = None

    if exif:
        exif_ifd = _ifd(exif, IFD.Exif)
        captured_at = _captured_at(exif, exif_ifd)
        gps_lat, gps_lon = _gps_coords(_ifd(exif, IFD.GPS))

    return ImageMeta(
        width=width,
        height=height,
        captured_at=captured_at,
        camera_make=make,
        camera_model=model,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )


def gps_degrees(dms: Any, ref: str | None) -> float | None:
    try:
        degrees, minutes, seconds = (_ratio(part) for part in dms)
    except (TypeError, ValueError):
        return None
    value = degrees + minutes / 60 + seconds / 3600
    if ref in {"S", "W"}:
        value = -value
    return value


def _ifd(exif: Any, tag: int) -> dict[int, Any]:
    """Read one EXIF Image File Directory (IFD) as a tag-to-value dict.

    EXIF is a set of these tables. The main IFD holds camera make, model,
    and DateTime. ``IFD.Exif`` holds capture details such as DateTimeOriginal.
    ``IFD.GPS`` holds latitude and longitude.
    """
    try:
        return dict(exif.get_ifd(tag))
    except Exception:
        return {}


def _captured_at(exif: Any, exif_ifd: dict[int, Any]) -> str | None:
    raw = (
        exif_ifd.get(DATETIME_ORIGINAL)
        or exif_ifd.get(DATETIME_DIGITIZED)
        or exif.get(DATETIME)
    )
    return _exif_datetime(_as_str(raw))


def _gps_coords(gps: dict[int, Any]) -> tuple[float | None, float | None]:
    if not gps:
        return None, None
    lat = gps_degrees(gps.get(GPS_LATITUDE), _as_str(gps.get(GPS_LATITUDE_REF)))
    lon = gps_degrees(gps.get(GPS_LONGITUDE), _as_str(gps.get(GPS_LONGITUDE_REF)))
    if lat is None or lon is None:
        return None, None
    return lat, lon


def _exif_datetime(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return value


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).strip().strip("\x00")
    return text or None


def _ratio(value: Any) -> float:
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return float(value.numerator) / float(value.denominator)
    if isinstance(value, tuple) and len(value) == 2:
        return float(value[0]) / float(value[1])
    return float(value)

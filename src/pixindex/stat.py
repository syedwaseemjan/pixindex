from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from pixindex.query import Filters, where_clause


@dataclass(frozen=True)
class CameraCount:
    name: str
    count: int


@dataclass(frozen=True)
class CatalogStats:
    files: int
    bytes: int
    with_gps: int
    first_captured: str | None
    last_captured: str | None
    cameras: list[CameraCount]


def catalog_stats(
    conn: sqlite3.Connection, filters: Filters | None = None
) -> CatalogStats:
    where, params = where_clause(filters or Filters())

    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS files,
            COALESCE(SUM(size), 0) AS bytes,
            COALESCE(SUM(has_gps), 0) AS with_gps,
            MIN(captured_at) AS first_captured,
            MAX(captured_at) AS last_captured
        FROM images
        {where}
        """,
        params,
    ).fetchone()

    cameras = [
        CameraCount(name=camera["name"], count=camera["count"])
        for camera in conn.execute(
            f"""
            SELECT
                CASE
                    WHEN camera_make IS NULL AND camera_model IS NULL THEN 'unknown'
                    WHEN camera_make IS NULL THEN camera_model
                    WHEN camera_model IS NULL THEN camera_make
                    ELSE camera_make || ' ' || camera_model
                END AS name,
                COUNT(*) AS count
            FROM images
            {where}
            GROUP BY name
            ORDER BY count DESC, name
            """,
            params,
        )
    ]

    return CatalogStats(
        files=int(row["files"]),
        bytes=int(row["bytes"]),
        with_gps=int(row["with_gps"]),
        first_captured=_day(row["first_captured"]),
        last_captured=_day(row["last_captured"]),
        cameras=cameras,
    )


def format_stats(stats: CatalogStats) -> str:
    if stats.files == 0:
        return "No pictures in the catalog yet."

    noun = "picture" if stats.files == 1 else "pictures"
    lines = [
        f"{stats.files} {noun}",
        format_bytes(stats.bytes),
        "",
        _date_line(stats),
        _gps_line(stats),
    ]
    if stats.cameras:
        width = max(len(camera.name) for camera in stats.cameras)
        lines.append("")
        lines.append("Cameras")
        for camera in stats.cameras:
            lines.append(f"  {camera.name:<{width}}  {camera.count}")
    return "\n".join(lines)


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _day(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def _date_line(stats: CatalogStats) -> str:
    if stats.first_captured is None and stats.last_captured is None:
        return "Taken: unknown"
    if stats.first_captured == stats.last_captured:
        return f"Taken: {stats.first_captured}"
    return f"Taken: {stats.first_captured} to {stats.last_captured}"


def _gps_line(stats: CatalogStats) -> str:
    percent = round(100 * stats.with_gps / stats.files)
    return f"With GPS: {stats.with_gps} of {stats.files} ({percent}%)"

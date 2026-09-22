from __future__ import annotations

import struct


def pack_vector(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def unpack_vector(blob: bytes) -> list[float]:
    if len(blob) % 4 != 0:
        raise ValueError("Stored picture data is not a list of numbers.")
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


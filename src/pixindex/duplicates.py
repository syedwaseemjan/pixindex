from __future__ import annotations

from dataclasses import dataclass, field
from pixindex.dhash import dhash, hamming
# How many of the 64 comparisons may differ and still count as the same shot.
# 0 means the fingerprints are identical. Lower is stricter.
DEFAULT_DISTANCE = 8


@dataclass
class DuplicateResult:
    hashed: int = 0
    skipped: int = 0
    failed: int = 0
    bytes_read: int = 0
    groups: list[list[str]] = field(default_factory=list)



def group_hashes(items: list[tuple[str, str]], distance: int) -> list[list[str]]:
    parent = {uri: uri for uri, _fingerprint in items}

    def find(uri: str) -> str:
        while parent[uri] != uri:
            parent[uri] = parent[parent[uri]]
            uri = parent[uri]
        return uri

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for index, (left_uri, left_hash) in enumerate(items):
        for right_uri, right_hash in items[index + 1 :]:
            if hamming(left_hash, right_hash) <= distance:
                union(left_uri, right_uri)

    clusters: dict[str, list[str]] = {}
    for uri, _fingerprint in items:
        clusters.setdefault(find(uri), []).append(uri)
    groups = [sorted(members) for members in clusters.values() if len(members) > 1]
    groups.sort(key=lambda members: members[0])
    return groups


def format_duplicate_result(result: DuplicateResult) -> str:
    count = len(result.groups)
    noun = "group" if count == 1 else "groups"
    return (
        f"Hashed {result.hashed}, skipped {result.skipped}, "
        f"failed {result.failed}. Read {format_bytes(result.bytes_read)}. "
        f"{count} {noun}."
    )




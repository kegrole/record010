"""Deterministic candidate generation and entity grouping."""

from __future__ import annotations

from .distance import damerau_levenshtein


STRONG_FIELDS = ("phone", "email")
NAME_MATCH_DISTANCE = 1


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parents = list(range(size))
        self._ranks = [0] * size

    def find(self, index: int) -> int:
        parent = self._parents[index]
        if parent != index:
            self._parents[index] = self.find(parent)
        return self._parents[index]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self._ranks[left_root] < self._ranks[right_root]:
            left_root, right_root = right_root, left_root
        self._parents[right_root] = left_root
        if self._ranks[left_root] == self._ranks[right_root]:
            self._ranks[left_root] += 1


def build_entity_groups(records: list[dict[str, object]]) -> list[tuple[int, ...]]:
    size = len(records)
    union_find = _UnionFind(size)
    strong_buckets: dict[tuple[str, str], list[int]] = {}
    weak_name_indexes: list[int] = []

    for index, record in enumerate(records):
        fields = record["fields"]
        has_strong_identifier = False
        for field in STRONG_FIELDS:
            value = fields.get(field)
            if value:
                has_strong_identifier = True
                bucket = strong_buckets.setdefault((field, value), [])
                if bucket:
                    union_find.union(index, bucket[0])
                bucket.append(index)
        if not has_strong_identifier and fields.get("name"):
            weak_name_indexes.append(index)

    name_buckets: dict[tuple[str, object], list[int]] = {}
    for index in weak_name_indexes:
        name = str(records[index]["fields"]["name"])
        bucket_keys = [
            ("first", name[0]),
            ("chars", tuple(sorted(name))),
        ]
        for bucket_key in bucket_keys:
            bucket = name_buckets.setdefault(bucket_key, [])
            for candidate in bucket:
                candidate_name = str(records[candidate]["fields"]["name"])
                if damerau_levenshtein(name, candidate_name) <= NAME_MATCH_DISTANCE:
                    union_find.union(index, candidate)
            bucket.append(index)

    groups: dict[int, list[int]] = {}
    for index in range(size):
        groups.setdefault(union_find.find(index), []).append(index)
    return [tuple(indexes) for indexes in groups.values()]

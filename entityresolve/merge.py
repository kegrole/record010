"""Trust-based entity merging and conflict detection."""

from __future__ import annotations

from .candidates import build_entity_groups
from .conflicts import RESOLVED, UNRESOLVED, EntityConflict


def _group_anchor(records: list[dict[str, object]], indexes: tuple[int, ...]) -> tuple:
    return tuple(
        sorted(
            (
                str(records[index]["source"]),
                int(records[index]["trust_level"]),
                tuple(sorted(records[index]["fields"].items())),
            )
            for index in indexes
        )
    )


def _entity_id(
    records: list[dict[str, object]], groups: list[tuple[int, ...]], position: int
) -> str:
    ordered_groups = sorted(groups, key=lambda indexes: _group_anchor(records, indexes))
    return f"entity_{position + 1:04d}"


def merge_records(records: list[dict[str, object]]) -> dict[str, list[dict]]:
    groups = build_entity_groups(records)
    entity_ids: dict[tuple[int, ...], str] = {
        group: _entity_id(records, groups, position)
        for position, group in enumerate(
            sorted(groups, key=lambda indexes: _group_anchor(records, indexes))
        )
    }

    entities: list[dict[str, object]] = []
    conflicts: list[dict[str, str]] = []

    for group in sorted(groups, key=lambda indexes: _group_anchor(records, indexes)):
        entity_id = entity_ids[group]
        field_values: dict[str, dict[str, list[tuple[int, str]]]] = {}
        for index in group:
            record = records[index]
            source = str(record["source"])
            trust_level = int(record["trust_level"])
            for field, value in record["fields"].items():
                field_values.setdefault(field, {}).setdefault(value, []).append(
                    (trust_level, source)
                )

        entity: dict[str, object] = {"entity_id": entity_id}
        for field in sorted(field_values):
            distinct_values = field_values[field]
            candidates = [
                (
                    max(trust for trust, _ in occurrences),
                    min(source for _, source in occurrences),
                    value,
                )
                for value, occurrences in distinct_values.items()
            ]
            candidates.sort(reverse=True)
            highest_trust = candidates[0][0]
            highest = [candidate for candidate in candidates if candidate[0] == highest_trust]

            if len(highest) > 1:
                sorted_values = sorted(candidate[2] for candidate in highest)
                for dropped_value in sorted_values:
                    conflicts.append(
                        EntityConflict(
                            entity_id=entity_id,
                            field=field,
                            kept_value="",
                            dropped_value=dropped_value,
                            kept_source="",
                            status=UNRESOLVED,
                        ).as_dict()
                    )
                continue

            trust_level, kept_source, kept_value = highest[0]
            entity[field] = kept_value
            for _, _, dropped_value in sorted(candidates[1:], key=lambda item: item[2]):
                conflicts.append(
                    EntityConflict(
                        entity_id=entity_id,
                        field=field,
                        kept_value=kept_value,
                        dropped_value=dropped_value,
                        kept_source=kept_source,
                        status=RESOLVED,
                    ).as_dict()
                )
        entities.append(entity)

    conflicts.sort(
        key=lambda row: (
            row["entity_id"],
            row["field"],
            row["status"],
            row["dropped_value"],
        )
    )
    return {"entities": entities, "conflicts": conflicts}

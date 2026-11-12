"""Conflict representation and status constants."""

from __future__ import annotations

from dataclasses import dataclass


RESOLVED = "resolved"
UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class EntityConflict:
    entity_id: str
    field: str
    kept_value: str
    dropped_value: str
    kept_source: str
    status: str = RESOLVED

    def as_dict(self) -> dict[str, str]:
        return {
            "entity_id": self.entity_id,
            "field": self.field,
            "kept_value": self.kept_value,
            "dropped_value": self.dropped_value,
            "kept_source": self.kept_source,
            "status": self.status,
        }

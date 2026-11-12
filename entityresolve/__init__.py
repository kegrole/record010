"""Multi-source entity resolution and conflict merging."""

from .aliases import AliasResolver
from .candidates import build_entity_groups
from .merge import merge_records
from .normalize import normalize_record

__all__ = [
    "AliasResolver",
    "build_entity_groups",
    "merge_records",
    "normalize_record",
]

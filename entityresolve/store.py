"""SQLite and JSON output persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ENTITY_BASE_COLUMNS = ["entity_id"]
CONFLICT_COLUMNS = [
    "entity_id",
    "field",
    "kept_value",
    "dropped_value",
    "kept_source",
    "status",
]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def write_sqlite(path: str | Path, result: dict[str, list[dict]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    entity_fields = sorted(
        {
            field
            for entity in result["entities"]
            for field in entity
            if field != "entity_id"
        }
    )
    entity_columns = ENTITY_BASE_COLUMNS + entity_fields
    entity_column_sql = ", ".join(_quote_identifier(column) for column in entity_columns)
    entity_placeholders = ", ".join("?" for _ in entity_columns)
    conflict_column_sql = ", ".join(_quote_identifier(column) for column in CONFLICT_COLUMNS)
    conflict_placeholders = ", ".join("?" for _ in CONFLICT_COLUMNS)

    with sqlite3.connect(output_path) as connection:
        connection.execute(
            f"CREATE TABLE entities ({entity_column_sql})"
        )
        connection.execute(
            "CREATE TABLE entity_conflicts ("
            f"{conflict_column_sql})"
        )
        connection.executemany(
            f"INSERT INTO entities ({entity_column_sql}) VALUES ({entity_placeholders})",
            [
                tuple(entity.get(column) for column in entity_columns)
                for entity in result["entities"]
            ],
        )
        connection.executemany(
            "INSERT INTO entity_conflicts "
            f"({conflict_column_sql}) VALUES ({conflict_placeholders})",
            [
                tuple(row.get(column, "") for column in CONFLICT_COLUMNS)
                for row in result["conflicts"]
            ],
        )


def write_json(path: str | Path, result: dict[str, list[dict]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")

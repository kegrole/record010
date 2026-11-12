"""Command-line interface for entity resolution."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from .aliases import AliasResolver
from .merge import merge_records
from .normalize import normalize_record
from .store import write_json, write_sqlite


def _source_metadata(path: Path) -> tuple[str, int]:
    match = re.match(r"^(?P<name>.+?)__(?P<trust>[123])$", path.stem)
    if match:
        return match.group("name"), int(match.group("trust"))
    match = re.search(r"(?P<trust>[123])$", path.stem)
    if match:
        return path.stem[: match.start()].rstrip("_-"), int(match.group("trust"))
    return path.stem, 1


def _read_json(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if isinstance(payload, dict):
        records = payload.get("records", [])
    else:
        records = payload
    if not isinstance(records, list):
        raise ValueError(f"JSON file {path} must contain a record list")
    return [dict(record) for record in records]


def _read_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def load_sources(sources_path: str | Path) -> list[dict[str, object]]:
    source_directory = Path(sources_path)
    if not source_directory.is_dir():
        raise NotADirectoryError(f"sources path is not a directory: {source_directory}")

    alias_resolver = AliasResolver()
    normalized_records: list[dict[str, object]] = []
    paths = sorted(
        path
        for path in source_directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".json"}
    )
    for path in paths:
        default_source, default_trust = _source_metadata(path)
        raw_records = _read_json(path) if path.suffix.lower() == ".json" else _read_csv(path)
        for raw_record in raw_records:
            normalized_records.append(
                normalize_record(
                    raw_record,
                    default_source=default_source,
                    default_trust_level=default_trust,
                    alias_resolver=alias_resolver,
                )
            )
    return normalized_records


def run(sources_path: str | Path, db_path: str | Path, out_path: str | Path) -> dict:
    records = load_sources(sources_path)
    result = merge_records(records)
    write_sqlite(db_path, result)
    write_json(out_path, result)
    unresolved_count = sum(
        row["status"] == "unresolved" for row in result["conflicts"]
    )
    summary = {
        "source_records": len(records),
        "entities": len(result["entities"]),
        "conflicts": len(result["conflicts"]),
        "unresolved": unresolved_count,
    }
    return {**result, "summary": summary}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve entities from multiple CSV or JSON sources."
    )
    parser.add_argument("--sources", required=True, help="directory of source files")
    parser.add_argument("--db", required=True, help="output SQLite database path")
    parser.add_argument("--out", required=True, help="output JSON path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run(args.sources, args.db, args.out)
    summary = result["summary"]
    print(
        "来源记录数: {source_records}，合并后实体数: {entities}，"
        "冲突条数: {conflicts}，其中 unresolved 的条数: {unresolved}".format(**summary)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

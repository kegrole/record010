import json
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from entityresolve.aliases import AliasResolver
from entityresolve.cli import load_sources, run
from entityresolve.distance import damerau_levenshtein, levenshtein
from entityresolve.merge import merge_records
from entityresolve.normalize import (
    normalize_date,
    normalize_email,
    normalize_phone,
    normalize_record,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "sources"

def find_entity(entities, **criteria):
    matches = []
    for entity in entities:
        if all(entity.get(field) == value for field, value in criteria.items()):
            matches.append(entity)
    if len(matches) != 1:
        raise AssertionError(f"expected one entity for {criteria!r}, got {matches!r}")
    return matches[0]


class EntityResolveAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_directory.name)
        cls.db_path = cls.temp_path / "entities.db"
        cls.json_path = cls.temp_path / "entities.json"
        cls.result = run(FIXTURES, cls.db_path, cls.json_path)
        cls.entities = cls.result["entities"]
        cls.conflicts = cls.result["conflicts"]

    @classmethod
    def tearDownClass(cls):
        cls.temp_directory.cleanup()

    def test_01_three_sources_eleven_records_merge_to_four_entities(self):
        self.assertEqual(self.result["summary"]["source_records"], 11)
        self.assertEqual(len(self.entities), 4)
        self.assertEqual({entity["entity_id"] for entity in self.entities}, {
            "entity_0001",
            "entity_0002",
            "entity_0003",
            "entity_0004",
        })

    def test_02_phone_variants_normalize_and_merge(self):
        self.assertEqual(normalize_phone("+86 138-0013-8000"), "13800138000")
        self.assertEqual(normalize_phone("0086138000138000"), "13800138000")
        self.assertEqual(normalize_phone("138 0013 8000"), "13800138000")
        entity = find_entity(self.entities, phone="13800138000")
        self.assertEqual(entity["email"], "zhangwei@example.com")
        self.assertEqual(entity["name"], "张伟".casefold())

    def test_03_date_variants_normalize_to_same_day(self):
        self.assertEqual(normalize_date("2024-01-02"), "2024-01-02")
        self.assertEqual(normalize_date("2024/1/2"), "2024-01-02")
        self.assertEqual(normalize_date("2024年1月2日"), "2024-01-02")
        self.assertEqual(normalize_date("2024-01-02T10:00:00+08:00"), "2024-01-02")
        entity = find_entity(self.entities, phone="13800138000")
        self.assertEqual(entity["created_at"], "2024-01-02")

    def test_04_name_transposition_uses_one_cost_and_merges(self):
        self.assertEqual(levenshtein("张伟", "伟张"), 2)
        self.assertEqual(damerau_levenshtein("张伟", "伟张"), 1)
        entity = find_entity(self.entities, created_at="2024-06-07")
        self.assertEqual(entity["name"], "张伟".casefold())
        conflict = next(
            row
            for row in self.conflicts
            if row["entity_id"] == entity["entity_id"]
            and row["field"] == "name"
            and row["dropped_value"] == "伟张"
        )
        self.assertEqual(conflict["kept_value"], "张伟")
        self.assertEqual(conflict["status"], "resolved")

    def test_05_higher_trust_wins_and_lower_value_is_conflict(self):
        entity = find_entity(self.entities, phone="13800138000")
        self.assertEqual(entity["city"], "北京")
        conflict = next(
            row
            for row in self.conflicts
            if row["entity_id"] == entity["entity_id"]
            and row["field"] == "city"
            and row["dropped_value"] == "北京市"
        )
        self.assertEqual(conflict["kept_value"], "北京")
        self.assertEqual(conflict["kept_source"], "source_a")
        self.assertEqual(conflict["status"], "resolved")

    def test_06_equal_trust_conflict_is_unresolved_and_omitted(self):
        entity = find_entity(self.entities, email="chenjing@example.com")
        self.assertNotIn("city", entity)
        unresolved = [
            row
            for row in self.conflicts
            if row["entity_id"] == entity["entity_id"]
            and row["field"] == "city"
        ]
        self.assertEqual(len(unresolved), 2)
        self.assertTrue(all(row["kept_value"] == "" for row in unresolved))
        self.assertTrue(all(row["kept_source"] == "" for row in unresolved))
        self.assertTrue(all(row["status"] == "unresolved" for row in unresolved))
        self.assertEqual(
            sorted(row["dropped_value"] for row in unresolved),
            ["广州", "杭州"],
        )

    def test_07_similar_names_with_different_strong_identifiers_do_not_merge(self):
        first = find_entity(self.entities, phone="13700137001")
        second = find_entity(self.entities, phone="13900139001")
        self.assertNotEqual(first["entity_id"], second["entity_id"])
        self.assertEqual(first["name"], "陈静".casefold())
        self.assertEqual(second["name"], "陈净".casefold())
        self.assertEqual(damerau_levenshtein(first["name"], second["name"]), 1)
        self.assertNotEqual(first["phone"], second["phone"])
        self.assertNotEqual(first["email"], second["email"])

    def test_08_database_and_json_tables_have_required_columns(self):
        with sqlite3.connect(self.db_path) as connection:
            entity_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(entities)")
            }
            conflict_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(entity_conflicts)")
            }
            conflict_count = connection.execute(
                "SELECT COUNT(*) FROM entity_conflicts"
            ).fetchone()[0]
        self.assertIn("entity_id", entity_columns)
        self.assertTrue({"name", "phone", "email", "created_at"} & entity_columns)
        self.assertEqual(
            conflict_columns,
            {
                "entity_id",
                "field",
                "kept_value",
                "dropped_value",
                "kept_source",
                "status",
            },
        )
        self.assertEqual(conflict_count, len(self.conflicts))
        with self.json_path.open(encoding="utf-8") as stream:
            payload = json.load(stream)
        self.assertEqual(payload["entities"], self.entities)
        self.assertEqual(payload["conflicts"], self.conflicts)
        required = {
            "entity_id",
            "field",
            "kept_value",
            "dropped_value",
            "kept_source",
        }
        self.assertTrue(all(required.issubset(row.keys()) for row in self.conflicts))

    def test_09_result_is_independent_of_input_file_order(self):
        alternate_directory = Path(tempfile.mkdtemp()) / "reordered"
        alternate_directory.mkdir()
        source_paths = sorted(FIXTURES.iterdir())
        for target_name in reversed([path.name for path in source_paths]):
            source = FIXTURES / target_name
            shutil.copy(source, alternate_directory / target_name)
        alternate_db = alternate_directory / "entities.db"
        alternate_json = alternate_directory / "entities.json"
        alternate = run(alternate_directory, alternate_db, alternate_json)
        self.assertEqual(alternate["entities"], self.entities)
        self.assertEqual(alternate["conflicts"], self.conflicts)
        records = load_sources(FIXTURES)
        for seed in range(10):
            shuffled = records[:]
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(merge_records(shuffled), {
                "entities": self.entities,
                "conflicts": self.conflicts,
            })

    def test_alias_extension_and_email_normalization(self):
        alias_resolver = AliasResolver()
        alias_resolver.add_alias("name", "customer_name")
        record = normalize_record(
            {
                "customer_name": "Ａｌｉｃｅ",
                "EMAIL": "Alice@Example.COM",
                "source": "custom",
                "trust_level": 2,
            },
            alias_resolver=alias_resolver,
        )
        self.assertEqual(record["fields"]["name"], "alice")
        self.assertEqual(normalize_email("Alice@Example.COM"), "alice@example.com")
        self.assertEqual(record["fields"]["email"], "alice@example.com")


class CommandLineTest(unittest.TestCase):
    def test_module_command_prints_summary(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "entityresolve.cli",
                "--sources",
                str(FIXTURES),
                "--db",
                str(Path(tempfile.mkdtemp()) / "entities.db"),
                "--out",
                str(Path(tempfile.mkdtemp()) / "entities.json"),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertIn("来源记录数: 11", completed.stdout)
        self.assertIn("合并后实体数: 4", completed.stdout)
        self.assertIn("冲突条数: 5", completed.stdout)
        self.assertIn("unresolved 的条数: 2", completed.stdout)


if __name__ == "__main__":
    unittest.main()

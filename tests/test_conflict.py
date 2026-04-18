"""Testes de passmerge.core.conflict — log de conflitos para revisão manual."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from passmerge.core.conflict import ConflictLog, ReviewConflict


def _entry(conflicting_fields=None):
    return ReviewConflict(
        conflict_id="test-id-1234",
        item_title="GitHub",
        category="login",
        conflicting_fields=conflicting_fields or ["password"],
        versions=[
            {
                "source": "1password",
                "updated_at": None,
                "fields": {"username": "user@example.com", "password": "secret1"},
            },
            {
                "source": "nordpass",
                "updated_at": None,
                "fields": {"username": "user@example.com", "password": "secret2"},
            },
        ],
    )


class TestReviewConflict(unittest.TestCase):
    def test_to_dict_has_required_keys(self):
        entry = _entry()
        d = entry.to_dict()
        for key in ("conflict_id", "item_title", "category", "conflicting_fields", "versions"):
            self.assertIn(key, d)

    def test_versions_contain_fields(self):
        entry = _entry()
        for version in entry.versions:
            self.assertIn("source", version)
            self.assertIn("fields", version)

    def test_plaintext_values_present(self):
        entry = _entry()
        sources = {v["source"]: v["fields"] for v in entry.versions}
        self.assertEqual(sources["1password"]["password"], "secret1")
        self.assertEqual(sources["nordpass"]["password"], "secret2")


class TestConflictLog(unittest.TestCase):
    def setUp(self):
        self.log = ConflictLog()
        self.log.add(_entry(["password"]))
        self.log.add(_entry(["username", "password"]))

    def test_len(self):
        self.assertEqual(len(self.log), 2)

    def test_to_json_is_array(self):
        data = json.loads(self.log.to_json())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

    def test_to_json_has_required_keys(self):
        data = json.loads(self.log.to_json())
        for entry in data:
            self.assertIn("conflict_id", entry)
            self.assertIn("conflicting_fields", entry)
            self.assertIn("versions", entry)

    def test_to_json_includes_plaintext_passwords(self):
        text = self.log.to_json()
        self.assertIn("secret1", text)
        self.assertIn("secret2", text)

    def test_save_creates_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conflicts.json"
            self.log.save(path)
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 2)

    def test_summary(self):
        s = self.log.summary()
        self.assertEqual(s["requires_review"], 2)

    def test_empty_log(self):
        log = ConflictLog()
        self.assertEqual(len(log), 0)
        self.assertEqual(json.loads(log.to_json()), [])


if __name__ == "__main__":
    unittest.main()

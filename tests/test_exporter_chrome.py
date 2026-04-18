"""Testes do ChromeExporter."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.exporters.chrome import ChromeExporter


def _login(title="GitHub", username="alice", password="pass1",
           url="https://github.com", notes="") -> CanonicalItem:
    return CanonicalItem(
        category=Category.LOGIN, title=title,
        fields={"username": username, "password": password, "url": url},
        sources=[SourceRef(source="test")],
        notes=notes,
    )


def _note(title="My Note") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SECURE_NOTE, title=title,
        fields={"body": "secret"},
        sources=[SourceRef(source="test")],
    )


class TestChromeExporter(unittest.TestCase):

    def _export(self, items) -> tuple[Path, object]:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "chrome.csv"
            report = ChromeExporter().export(items, out)
            content = out.read_text(encoding="utf-8")
        return content, report

    def test_creates_valid_csv(self):
        content, report = self._export([_login()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "GitHub")
        self.assertEqual(rows[0]["username"], "alice")
        self.assertEqual(rows[0]["password"], "pass1")
        self.assertEqual(rows[0]["url"], "https://github.com")
        self.assertEqual(report.exported_count, 1)

    def test_unsupported_category_skipped(self):
        content, report = self._export([_login(), _note()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(report.skipped_items), 1)
        self.assertEqual(report.skipped_items[0]["reason"], "unsupported_category")

    def test_unicode_preserved(self):
        content, report = self._export([_login(
            title="Meu Site", username="usuário", password="sênha@123"
        )])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["username"], "usuário")
        self.assertEqual(rows[0]["password"], "sênha@123")

    def test_notes_with_newline(self):
        content, report = self._export([_login(notes="linha1\nlinha2")])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertIn("linha1", rows[0]["note"])

    def test_empty_vault_creates_header_only(self):
        content, report = self._export([])
        lines = [l for l in content.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("name", lines[0])
        self.assertEqual(report.exported_count, 0)

    def test_multiple_items(self):
        items = [_login(title=f"Site{i}", username=f"u{i}", password=f"p{i}")
                 for i in range(5)]
        content, report = self._export(items)
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(len(rows), 5)
        self.assertEqual(report.exported_count, 5)


if __name__ == "__main__":
    unittest.main()

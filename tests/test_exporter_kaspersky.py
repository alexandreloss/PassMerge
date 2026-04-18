"""Testes do KasperskyExporter."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.exporters.kaspersky import KasperskyExporter


def _login(title="GitHub", username="alice", password="pass1",
           url="https://github.com") -> CanonicalItem:
    return CanonicalItem(
        category=Category.LOGIN, title=title,
        fields={"username": username, "password": password, "url": url},
        sources=[SourceRef(source="test")],
    )


def _note(title="My Note", body="secret") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SECURE_NOTE, title=title,
        fields={"body": body},
        sources=[SourceRef(source="test")],
    )


def _card(title="Visa") -> CanonicalItem:
    return CanonicalItem(
        category=Category.CREDIT_CARD, title=title,
        fields={"cardholder": "Alice", "number": "4111"},
        sources=[SourceRef(source="test")],
    )


class TestKasperskyExporter(unittest.TestCase):

    def _export(self, items):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "kaspersky.txt"
            report = KasperskyExporter().export(items, out)
            content = out.read_text(encoding="utf-8")
        return content, report

    def test_login_block_structure(self):
        content, report = self._export([_login()])
        self.assertIn("Websites", content)
        self.assertIn("Website name: GitHub", content)
        self.assertIn("Website URL: https://github.com", content)
        self.assertIn("Password: pass1", content)
        self.assertIn("---", content)
        self.assertEqual(report.exported_count, 1)

    def test_note_block_structure(self):
        content, report = self._export([_note()])
        self.assertIn("Notes", content)
        self.assertIn("Note name: My Note", content)
        self.assertIn("Note text: secret", content)
        self.assertEqual(report.exported_count, 1)

    def test_both_blocks_present(self):
        content, report = self._export([_login(), _note()])
        self.assertIn("Websites", content)
        self.assertIn("Notes", content)
        self.assertEqual(report.exported_count, 2)

    def test_unsupported_category_skipped(self):
        content, report = self._export([_login(), _card()])
        self.assertEqual(len(report.skipped_items), 1)
        self.assertEqual(report.skipped_items[0]["reason"], "unsupported_category")
        self.assertEqual(report.exported_count, 1)

    def test_multiple_logins_separated_by_dashes(self):
        items = [_login(title=f"Site{i}") for i in range(3)]
        content, report = self._export(items)
        # Should have 3 "---" separators within the Websites block
        self.assertEqual(report.exported_count, 3)
        self.assertGreaterEqual(content.count("---"), 3)

    def test_unicode_preserved(self):
        content, _ = self._export([_login(title="Meu Sîte", password="sênha@1")])
        self.assertIn("Meu Sîte", content)
        self.assertIn("sênha@1", content)

    def test_empty_vault_creates_file(self):
        content, report = self._export([])
        self.assertIsNotNone(content)
        self.assertEqual(report.exported_count, 0)


if __name__ == "__main__":
    unittest.main()

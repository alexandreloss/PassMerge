"""Testes do NordPassExporter."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.exporters.nordpass import NordPassExporter


def _login(title="GitHub", username="alice", password="pass1") -> CanonicalItem:
    return CanonicalItem(
        category=Category.LOGIN, title=title,
        fields={"username": username, "password": password, "url": "https://github.com"},
        sources=[SourceRef(source="test")],
    )


def _card(title="Visa") -> CanonicalItem:
    return CanonicalItem(
        category=Category.CREDIT_CARD, title=title,
        fields={"cardholder": "Alice", "number": "4111111111111111",
                "cvv": "123", "expiration": "12/2030", "zip": "12345"},
        sources=[SourceRef(source="test")],
    )


def _note(title="My Note") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SECURE_NOTE, title=title,
        fields={"body": "secret text"},
        sources=[SourceRef(source="test")],
    )


def _identity(title="Alice Identity") -> CanonicalItem:
    return CanonicalItem(
        category=Category.IDENTITY, title=title,
        fields={"first_name": "Alice", "email": "alice@example.com",
                "phone": "+1234567890", "city": "NYC"},
        sources=[SourceRef(source="test")],
    )


def _server(title="My Server") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SERVER, title=title,
        fields={"hostname": "server.example.com", "username": "root", "password": "pass"},
        sources=[SourceRef(source="test")],
    )


class TestNordPassExporter(unittest.TestCase):

    def _export(self, items):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nordpass.csv"
            report = NordPassExporter().export(items, out)
            content = out.read_text(encoding="utf-8")
        return content, report

    def test_login_exported(self):
        content, report = self._export([_login()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "GitHub")
        self.assertEqual(rows[0]["username"], "alice")
        self.assertEqual(rows[0]["type"], "password")
        self.assertEqual(report.exported_count, 1)

    def test_credit_card_exported(self):
        content, report = self._export([_card()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["cardholder"], "Alice")
        self.assertEqual(rows[0]["cardnumber"], "4111111111111111")
        self.assertEqual(rows[0]["type"], "credit_card")

    def test_secure_note_exported(self):
        content, report = self._export([_note()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["note"], "secret text")
        self.assertEqual(rows[0]["type"], "note")

    def test_identity_exported(self):
        content, report = self._export([_identity()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["full_name"], "Alice")
        self.assertEqual(rows[0]["email"], "alice@example.com")
        self.assertEqual(rows[0]["type"], "identity")

    def test_unsupported_category_skipped(self):
        content, report = self._export([_login(), _server()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(report.skipped_items), 1)
        self.assertEqual(report.skipped_items[0]["reason"], "unsupported_category")

    def test_all_columns_present(self):
        content, _ = self._export([_login()])
        header = content.splitlines()[0]
        for col in ["name", "url", "username", "password", "note", "type",
                    "cardholder", "cardnumber"]:
            self.assertIn(col, header)

    def test_unicode_preserved(self):
        content, _ = self._export([_login(username="usuário", password="sênha")])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["username"], "usuário")


if __name__ == "__main__":
    unittest.main()

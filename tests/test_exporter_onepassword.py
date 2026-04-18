"""Testes do OnePasswordExporter."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.exporters.onepassword import OnePasswordExporter


def _login(title="GitHub", username="alice", password="pass1",
           url="https://github.com") -> CanonicalItem:
    return CanonicalItem(
        category=Category.LOGIN, title=title,
        fields={"username": username, "password": password, "url": url},
        sources=[SourceRef(source="test")],
    )


def _card(title="Visa") -> CanonicalItem:
    return CanonicalItem(
        category=Category.CREDIT_CARD, title=title,
        fields={"cardholder": "Alice", "number": "4111111111111111",
                "cvv": "123", "expiration": "202512"},
        sources=[SourceRef(source="test")],
    )


def _note(title="My Note", body="secret note content") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SECURE_NOTE, title=title,
        fields={"body": body},
        sources=[SourceRef(source="test")],
    )


def _server(title="DB Server") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SERVER, title=title,
        fields={"hostname": "db.example.com", "port": "5432",
                "username": "admin", "password": "dbpass"},
        sources=[SourceRef(source="test")],
    )


def _load_export_data(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        with zf.open("export.data") as fh:
            return json.load(fh)


class TestOnePasswordExporter(unittest.TestCase):

    def _export(self, items):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export.1pux"
            report = OnePasswordExporter().export(items, out)
            data = _load_export_data(out)
        return data, report

    def test_creates_valid_zip_with_export_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export.1pux"
            OnePasswordExporter().export([_login()], out)
            self.assertTrue(zipfile.is_zipfile(out))
            with zipfile.ZipFile(out) as zf:
                self.assertIn("export.data", zf.namelist())

    def test_structure_has_accounts_vaults_items(self):
        data, _ = self._export([_login()])
        self.assertIn("accounts", data)
        items = data["accounts"][0]["vaults"][0]["items"]
        self.assertEqual(len(items), 1)

    def test_login_fields_present(self):
        data, report = self._export([_login()])
        item = data["accounts"][0]["vaults"][0]["items"][0]
        self.assertEqual(item["overview"]["title"], "GitHub")
        self.assertEqual(item["categoryUuid"], "001")
        login_fields = item["details"]["loginFields"]
        usernames = [f["value"] for f in login_fields if f["designation"] == "username"]
        passwords = [f["value"] for f in login_fields if f["designation"] == "password"]
        self.assertEqual(usernames, ["alice"])
        self.assertEqual(passwords, ["pass1"])
        self.assertEqual(report.exported_count, 1)

    def test_credit_card_in_sections(self):
        data, _ = self._export([_card()])
        item = data["accounts"][0]["vaults"][0]["items"][0]
        self.assertEqual(item["categoryUuid"], "002")
        sections = item["details"]["sections"]
        self.assertTrue(len(sections) > 0)
        fields = sections[0]["fields"]
        field_ids = [f["id"] for f in fields]
        self.assertIn("cardholder", field_ids)
        self.assertIn("ccnum", field_ids)

    def test_secure_note_in_notes_plain(self):
        data, _ = self._export([_note()])
        item = data["accounts"][0]["vaults"][0]["items"][0]
        self.assertEqual(item["categoryUuid"], "003")
        self.assertEqual(item["details"]["notesPlain"], "secret note content")

    def test_server_category(self):
        data, _ = self._export([_server()])
        item = data["accounts"][0]["vaults"][0]["items"][0]
        self.assertEqual(item["categoryUuid"], "110")

    def test_unsupported_category_skipped(self):
        other = CanonicalItem(
            category=Category.OTHER, title="Unknown",
            fields={}, sources=[SourceRef(source="test")],
        )
        # OTHER maps to "003" (secure note fallback) — it IS in CANONICAL_TO_ONEPASSWORD
        # So no items should be skipped for 1Password (covers all categories)
        data, report = self._export([_login(), other])
        items = data["accounts"][0]["vaults"][0]["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(report.exported_count, 2)

    def test_unicode_title_and_fields(self):
        data, _ = self._export([_login(title="Meu Sîte", username="usuário")])
        item = data["accounts"][0]["vaults"][0]["items"][0]
        self.assertEqual(item["overview"]["title"], "Meu Sîte")

    def test_multiple_items(self):
        items = [_login(title=f"Site{i}") for i in range(4)]
        data, report = self._export(items)
        exported = data["accounts"][0]["vaults"][0]["items"]
        self.assertEqual(len(exported), 4)
        self.assertEqual(report.exported_count, 4)


if __name__ == "__main__":
    unittest.main()

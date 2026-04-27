"""Testes do NordPassExporter."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.exporters.nordpass import NordPassExporter, _COLUMNS


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
        self.assertEqual(report.exported_count, 1)

    def test_credit_card_exported(self):
        content, report = self._export([_card()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["cardholdername"], "Alice")
        self.assertEqual(rows[0]["cardnumber"], "4111111111111111")

    def test_secure_note_exported(self):
        content, report = self._export([_note()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["note"], "secret text")

    def test_identity_exported(self):
        content, report = self._export([_identity()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["full_name"], "Alice")
        self.assertEqual(rows[0]["email"], "alice@example.com")

    def test_other_category_exported_as_login(self):
        content, report = self._export([_login(), _server()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(report.skipped_items), 0)
        server_row = next(r for r in rows if r["name"] == "My Server")
        # sem type → passa como login (username/password preenchidos)
        self.assertEqual(server_row["username"], "root")

    def test_official_columns_present(self):
        content, _ = self._export([_login()])
        header = content.splitlines()[0]
        for col in _COLUMNS:
            self.assertIn(col, header)

    def test_type_column_login(self):
        content, _ = self._export([_login()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["type"], "password")

    def test_type_column_credit_card(self):
        content, _ = self._export([_card()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["type"], "credit_card")

    def test_type_column_secure_note(self):
        content, _ = self._export([_note()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["type"], "note")

    def test_type_column_identity(self):
        content, _ = self._export([_identity()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["type"], "identity")

    def test_type_column_unsupported_falls_back_to_password(self):
        content, _ = self._export([_server()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["type"], "password")

    def test_additional_urls_exported(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="GitHub",
            fields={"username": "alice", "password": "pass",
                    "url": "https://github.com",
                    "urls_additional": "https://github.com/login"},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["additional_urls"], "https://github.com/login")

    def test_pin_exported_for_credit_card(self):
        item = CanonicalItem(
            category=Category.CREDIT_CARD, title="Visa",
            fields={"cardholder": "Alice", "number": "4111111111111111",
                    "cvv": "123", "expiration": "12/2030", "zip": "12345", "pin": "1234"},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["pin"], "1234")

    def test_unicode_preserved(self):
        content, _ = self._export([_login(username="usuário", password="sênha")])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["username"], "usuário")

    def test_folder_from_first_tag(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="Tagged",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            tags=["Mercantil do Brasil", "VLI"],
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["folder"], "Mercantil do Brasil")

    def test_folder_from_item_folder_when_no_tags(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="Foldered",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            folder="Work",
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["folder"], "Work")

    def test_folder_empty_when_no_tags_no_folder(self):
        content, _ = self._export([_login()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["folder"], "")

    def test_extras_plain_field_type_text(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="WithExtras",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            extras={"Código do cliente": "12345"},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        cf = json.loads(rows[0]["custom_fields"])
        self.assertEqual(cf[0]["type"], "text")
        self.assertEqual(cf[0]["label"], "Código do cliente")
        self.assertEqual(cf[0]["value"], "12345")

    def test_extras_hidden_type_on_password_keyword(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="WithExtras",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            extras={"Chave de Segurança": "IBH"},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        cf = json.loads(rows[0]["custom_fields"])
        self.assertEqual(cf[0]["type"], "hidden")

    def test_extras_hidden_type_on_senha_keyword(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="WithExtras",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            extras={"Senha Secundária": "abc"},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        cf = json.loads(rows[0]["custom_fields"])
        self.assertEqual(cf[0]["type"], "hidden")

    def test_extras_date_type_on_date_keyword(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="WithExtras",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            extras={"Data de Expiração": "2026-12-31"},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        cf = json.loads(rows[0]["custom_fields"])
        self.assertEqual(cf[0]["type"], "date")

    def test_extras_multiple_fields_correct_types(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="WithExtras",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            extras={"Chave de Segurança": "IBH", "Data de Criação": "2024-01-01", "Apelido": "xpto"},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        cf = json.loads(rows[0]["custom_fields"])
        self.assertEqual(len(cf), 3)
        by_label = {e["label"]: e["type"] for e in cf}
        self.assertEqual(by_label["Chave de Segurança"], "hidden")
        self.assertEqual(by_label["Data de Criação"], "date")
        self.assertEqual(by_label["Apelido"], "text")

    def test_empty_extras_produces_empty_custom_fields(self):
        content, _ = self._export([_login()])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["custom_fields"], "")

    def test_losers_key_excluded_from_custom_fields(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="WithLosers",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            extras={"Apelido": "xpto", "_losers": [{"source": "chrome", "field": "password"}]},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        cf = json.loads(rows[0]["custom_fields"])
        labels = [e["label"] for e in cf]
        self.assertIn("Apelido", labels)
        self.assertNotIn("_losers", labels)

    def test_only_losers_in_extras_produces_empty_custom_fields(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="OnlyLosers",
            fields={"username": "u", "password": "p", "url": "https://x.com"},
            extras={"_losers": [{"source": "chrome", "field": "password"}]},
            sources=[SourceRef(source="test")],
        )
        content, _ = self._export([item])
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["custom_fields"], "")


if __name__ == "__main__":
    unittest.main()

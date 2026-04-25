"""Testes do importer 1Password (.1pux)."""
from __future__ import annotations

import io
import json
import unittest
import zipfile
from pathlib import Path

from passmerge.core.canonical import Category
from passmerge.importers.onepassword import OnePasswordImporter

FIXTURE = Path(__file__).parent / "fixtures" / "onepassword_test.1pux"


def _make_minimal_1pux(items: list[dict]) -> bytes:
    """Cria um .1pux em memória com a lista de items fornecida."""
    data = {"accounts": [{"vaults": [{"items": items}]}]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("export.data", json.dumps(data))
    return buf.getvalue()


class TestOnePasswordImporterProperties(unittest.TestCase):
    def setUp(self):
        self.imp = OnePasswordImporter()

    def test_source_name(self):
        self.assertEqual(self.imp.source_name, "1password")

    def test_supports_timestamps(self):
        self.assertTrue(self.imp.supports_timestamps)

    def test_supported_categories_includes_login(self):
        self.assertIn(Category.LOGIN, self.imp.supported_categories)

    def test_supported_categories_includes_credit_card(self):
        self.assertIn(Category.CREDIT_CARD, self.imp.supported_categories)

    def test_supported_categories_includes_secure_note(self):
        self.assertIn(Category.SECURE_NOTE, self.imp.supported_categories)


class TestOnePasswordFixture(unittest.TestCase):
    def setUp(self):
        self.imp = OnePasswordImporter()
        self.items = self.imp.parse(FIXTURE)
        self._by_uuid = {s.source_id: item for item in self.items for s in item.sources}

    def test_total_item_count(self):
        self.assertEqual(len(self.items), 7)

    def test_login_category(self):
        logins = [i for i in self.items if i.category == Category.LOGIN]
        self.assertGreaterEqual(len(logins), 1)

    def test_credit_card_category(self):
        self.assertEqual(len([i for i in self.items if i.category == Category.CREDIT_CARD]), 1)

    def test_secure_note_category(self):
        self.assertEqual(len([i for i in self.items if i.category == Category.SECURE_NOTE]), 1)

    def test_server_category(self):
        self.assertEqual(len([i for i in self.items if i.category == Category.SERVER]), 1)

    def test_wireless_category(self):
        self.assertEqual(len([i for i in self.items if i.category == Category.WIRELESS]), 1)

    def test_source_ref_populated(self):
        for item in self.items:
            self.assertEqual(item.sources[0].source, "1password")
            self.assertIsNotNone(item.sources[0].source_id)

    def test_login_fields(self):
        item = self._by_uuid["login-item-001"]
        self.assertEqual(item.fields["username"], "user@example.com")
        self.assertEqual(item.fields["password"], "s3cr3t!Pass")
        self.assertEqual(item.fields["url"], "https://github.com")

    def test_login_otp(self):
        item = self._by_uuid["login-item-001"]
        self.assertIn("otp", item.fields)
        self.assertIn("otpauth://", item.fields["otp"])

    def test_login_tags(self):
        item = self._by_uuid["login-item-001"]
        self.assertIn("dev", item.tags)
        self.assertIn("git", item.tags)

    def test_login_favorite(self):
        self.assertTrue(self._by_uuid["login-item-001"].favorite)

    def test_updated_at_populated(self):
        item = self._by_uuid["login-item-001"]
        self.assertIsNotNone(item.updated_at)
        self.assertIn("2023", item.updated_at)

    def test_created_at_and_updated_at_differ(self):
        item = self._by_uuid["login-item-001"]
        self.assertNotEqual(item.created_at, item.updated_at)

    def test_unicode_title_and_fields(self):
        item = self._by_uuid["login-item-002"]
        self.assertEqual(item.title, "Ação, Büro & Co.")
        self.assertEqual(item.fields["username"], "üser")
        self.assertEqual(item.fields["password"], "pässwörd")

    def test_secure_note_body(self):
        item = self._by_uuid["note-item-001"]
        self.assertIn("EmpresaWifi", item.fields.get("body", ""))

    def test_credit_card_fields(self):
        item = self._by_uuid["cc-item-001"]
        self.assertEqual(item.fields.get("cardholder"), "Alexandre Loss")
        self.assertEqual(item.fields.get("number"), "4111111111111111")
        self.assertEqual(item.fields.get("cvv"), "123")

    def test_server_fields(self):
        item = self._by_uuid["server-item-001"]
        self.assertEqual(item.fields.get("hostname"), "db.example.com")
        self.assertEqual(item.fields.get("username"), "admin")
        self.assertEqual(item.fields.get("port"), "5432")

    def test_wireless_fields(self):
        item = self._by_uuid["wifi-item-001"]
        self.assertEqual(item.fields.get("ssid"), "MyHomeNetwork")
        self.assertEqual(item.fields.get("security_type"), "WPA2")

    def test_trashed_item_imported_with_flag(self):
        self.assertTrue(self._by_uuid["trashed-item-001"].trashed)


class TestOnePasswordEdgeCases(unittest.TestCase):
    def setUp(self):
        self.imp = OnePasswordImporter()

    def _parse_bytes(self, raw: bytes) -> list:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".1pux", delete=False) as f:
            f.write(raw)
            tmp = Path(f.name)
        try:
            return self.imp.parse(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    def test_empty_export(self):
        items = self._parse_bytes(_make_minimal_1pux([]))
        self.assertEqual(items, [])

    def test_unknown_category_uuid_becomes_other(self):
        items = self._parse_bytes(_make_minimal_1pux([{
            "uuid": "x", "categoryUuid": "999",
            "overview": {"title": "Unknown"},
            "details": {"loginFields": [], "notesPlain": "", "sections": []},
        }]))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, Category.OTHER)

    def test_missing_timestamps_allowed(self):
        items = self._parse_bytes(_make_minimal_1pux([{
            "uuid": "no-ts", "categoryUuid": "001",
            "overview": {"title": "No Timestamp"},
            "details": {
                "loginFields": [{"value": "u", "designation": "username"}],
                "notesPlain": "", "sections": [],
            },
        }]))
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0].created_at)
        self.assertIsNone(items[0].updated_at)

    def test_note_with_empty_body(self):
        items = self._parse_bytes(_make_minimal_1pux([{
            "uuid": "empty-note", "categoryUuid": "003",
            "overview": {"title": "Empty Note"},
            "details": {"loginFields": [], "notesPlain": "", "sections": []},
        }]))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, Category.SECURE_NOTE)

    def test_archived_item_ignored(self):
        items = self._parse_bytes(_make_minimal_1pux([
            {"uuid": "active", "categoryUuid": "001",
             "overview": {"title": "Active"},
             "details": {"loginFields": [
                 {"designation": "username", "value": "u"},
                 {"designation": "password", "value": "p"},
             ], "notesPlain": "", "sections": []}},
            {"uuid": "archived", "categoryUuid": "001", "state": "archived",
             "overview": {"title": "Archived"},
             "details": {"loginFields": [
                 {"designation": "username", "value": "u2"},
                 {"designation": "password", "value": "p2"},
             ], "notesPlain": "", "sections": []}},
        ]))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Active")

    def test_password_category_reads_details_password(self):
        """Categoria 005: senha fica em details.password, não em loginFields."""
        items = self._parse_bytes(_make_minimal_1pux([{
            "uuid": "pwd-item-001",
            "categoryUuid": "005",
            "state": "active",
            "overview": {"title": "Village Geribá", "url": ""},
            "details": {
                "loginFields": [],
                "sections": [],
                "password": "afdjadsf888$$",
            },
        }]))
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.category, Category.PASSWORD)
        self.assertEqual(item.fields.get("password"), "afdjadsf888$$")

    def test_invalid_file_raises_value_error(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".1pux", delete=False) as f:
            f.write(b"not a zip file")
            tmp = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                self.imp.parse(tmp)
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

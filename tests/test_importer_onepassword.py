"""Testes do importer 1Password (SQLite)."""
from __future__ import annotations

import io
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from passmerge.core.canonical import Category
from passmerge.importers.onepassword import OnePasswordImporter

FIXTURE = Path(__file__).parent / "fixtures" / "onepassword_test.sqlite.zip"


def _make_minimal_sqlite_zip(items: list[dict], *, internal_name: str = "export.sqlite") -> bytes:
    """Cria um ZIP em memória com SQLite contendo os itens fornecidos.

    Use ``internal_name="data"`` (sem extensão) para exercitar a detecção
    por magic bytes.
    """
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        tmp_db = tf.name
    try:
        conn = sqlite3.connect(tmp_db)
        conn.execute("""CREATE TABLE items (
            uuid TEXT PRIMARY KEY, category_uuid TEXT NOT NULL,
            created_at INTEGER, updated_at INTEGER,
            trashed INTEGER DEFAULT 0, favorite INTEGER DEFAULT 0,
            title TEXT, url TEXT, notes TEXT
        )""")
        conn.execute("""CREATE TABLE item_fields (
            item_uuid TEXT NOT NULL, section_name TEXT, field_id TEXT,
            field_title TEXT, field_value TEXT, field_type TEXT DEFAULT 'string'
        )""")
        conn.execute("""CREATE TABLE item_tags (
            item_uuid TEXT NOT NULL, tag TEXT NOT NULL
        )""")
        for item in items:
            overview = item.get("overview") or {}
            details = item.get("details") or {}
            uuid = item["uuid"]
            conn.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?)", (
                uuid,
                item.get("categoryUuid", "001"),
                item.get("createdAt"),
                item.get("updatedAt"),
                1 if str(item.get("trashed", "N")).upper() == "Y" else 0,
                item.get("favorite", 0),
                overview.get("title", "sem título"),
                overview.get("url", ""),
                details.get("notesPlain", ""),
            ))
            for lf in details.get("loginFields") or []:
                d = lf.get("designation", "")
                conn.execute("INSERT INTO item_fields VALUES (?,?,?,?,?,?)",
                             (uuid, None, d, d, lf.get("value", ""), "string"))
        conn.commit()
        conn.close()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db, internal_name)
        return buf.getvalue()
    finally:
        os.unlink(tmp_db)


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
        # 7 items na fixture (incluindo o trashed)
        self.assertEqual(len(self.items), 7)

    def test_login_category(self):
        logins = [i for i in self.items if i.category == Category.LOGIN]
        self.assertGreaterEqual(len(logins), 1)

    def test_credit_card_category(self):
        cards = [i for i in self.items if i.category == Category.CREDIT_CARD]
        self.assertEqual(len(cards), 1)

    def test_secure_note_category(self):
        notes = [i for i in self.items if i.category == Category.SECURE_NOTE]
        self.assertEqual(len(notes), 1)

    def test_server_category(self):
        servers = [i for i in self.items if i.category == Category.SERVER]
        self.assertEqual(len(servers), 1)

    def test_wireless_category(self):
        wifi = [i for i in self.items if i.category == Category.WIRELESS]
        self.assertEqual(len(wifi), 1)

    def test_source_ref_populated(self):
        for item in self.items:
            self.assertEqual(len(item.sources), 1)
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
        item = self._by_uuid["login-item-001"]
        self.assertTrue(item.favorite)

    def test_updated_at_populated(self):
        item = self._by_uuid["login-item-001"]
        self.assertIsNotNone(item.updated_at)
        self.assertIn("2023", item.updated_at)  # timestamp 1700010000 ≈ Nov 2023

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
        item = self._by_uuid["trashed-item-001"]
        self.assertTrue(item.trashed)

    def test_created_at_and_updated_at_differ(self):
        item = self._by_uuid["login-item-001"]
        self.assertNotEqual(item.created_at, item.updated_at)


class TestOnePasswordEdgeCases(unittest.TestCase):
    def setUp(self):
        self.imp = OnePasswordImporter()

    def _parse_bytes(self, raw: bytes, *, suffix: str = ".zip") -> list:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(raw)
            tmp = Path(f.name)
        try:
            return self.imp.parse(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    def test_empty_export(self):
        raw = _make_minimal_sqlite_zip([])
        items = self._parse_bytes(raw)
        self.assertEqual(items, [])

    def test_unknown_category_uuid_becomes_other(self):
        raw = _make_minimal_sqlite_zip([{
            "uuid": "x",
            "categoryUuid": "999",
            "overview": {"title": "Unknown"},
            "details": {"loginFields": [], "notesPlain": "", "sections": []},
        }])
        items = self._parse_bytes(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, Category.OTHER)

    def test_missing_timestamps_allowed(self):
        raw = _make_minimal_sqlite_zip([{
            "uuid": "no-ts",
            "categoryUuid": "001",
            "overview": {"title": "No Timestamp"},
            "details": {
                "loginFields": [{"value": "u", "designation": "username"}],
                "notesPlain": "",
                "sections": [],
            },
        }])
        items = self._parse_bytes(raw)
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0].created_at)
        self.assertIsNone(items[0].updated_at)

    def test_note_with_empty_body(self):
        raw = _make_minimal_sqlite_zip([{
            "uuid": "empty-note",
            "categoryUuid": "003",
            "overview": {"title": "Empty Note"},
            "details": {"loginFields": [], "notesPlain": "", "sections": []},
        }])
        items = self._parse_bytes(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].category, Category.SECURE_NOTE)

    def test_sqlite_detected_by_magic_bytes_without_extension(self):
        """ZIP com arquivo interno sem extensão — detectado por magic bytes."""
        raw = _make_minimal_sqlite_zip([{
            "uuid": "magic-test",
            "categoryUuid": "001",
            "overview": {"title": "Magic Bytes Test"},
            "details": {"loginFields": [], "notesPlain": "", "sections": []},
        }], internal_name="data")
        items = self._parse_bytes(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Magic Bytes Test")


if __name__ == "__main__":
    unittest.main()

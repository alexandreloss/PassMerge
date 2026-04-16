"""Testes do importer Google Chrome (CSV de 5 colunas)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import Category
from passmerge.importers.chrome import ChromeImporter

FIXTURE = Path(__file__).parent / "fixtures" / "chrome_test.csv"


def _write_csv(rows: list[str]) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", encoding="utf-8", delete=False
    )
    tmp.write("name,url,username,password,note\n")
    for r in rows:
        tmp.write(r + "\n")
    tmp.close()
    return Path(tmp.name)


class TestChromeImporterProperties(unittest.TestCase):
    def setUp(self):
        self.imp = ChromeImporter()

    def test_source_name(self):
        self.assertEqual(self.imp.source_name, "chrome")

    def test_supports_timestamps(self):
        self.assertFalse(self.imp.supports_timestamps)

    def test_supported_categories_only_login(self):
        self.assertEqual(self.imp.supported_categories, {Category.LOGIN})


class TestChromeFixture(unittest.TestCase):
    def setUp(self):
        self.imp = ChromeImporter()
        self.items = self.imp.parse(FIXTURE)
        self._by_title = {i.title: i for i in self.items}

    def test_total_item_count(self):
        self.assertEqual(len(self.items), 5)

    def test_all_items_are_logins(self):
        for item in self.items:
            self.assertEqual(item.category, Category.LOGIN)

    def test_source_ref_present(self):
        for item in self.items:
            self.assertEqual(len(item.sources), 1)
            self.assertEqual(item.sources[0].source, "chrome")

    def test_github_fields(self):
        item = self._by_title["GitHub"]
        self.assertEqual(item.fields["username"], "user@example.com")
        self.assertEqual(item.fields["password"], "s3cr3t!Pass")
        self.assertEqual(item.fields["url"], "https://github.com")

    def test_unicode_title_and_fields(self):
        item = self._by_title["Ação, Büro & Co."]
        self.assertEqual(item.fields["username"], "üser")
        self.assertEqual(item.fields["password"], "pässwörd")
        self.assertEqual(item.fields["url"], "https://example.com/ação")

    def test_note_with_comma_preserved(self):
        item = self._by_title["Ação, Büro & Co."]
        self.assertIn("vírgula", item.notes)

    def test_empty_url(self):
        item = self._by_title["Empty URL"]
        self.assertEqual(item.fields["url"], "")
        self.assertEqual(item.fields["username"], "nobody")

    def test_comma_in_note_field(self):
        item = self._by_title["Note with comma, inside"]
        self.assertIn("Second line", item.notes)

    def test_no_updated_at(self):
        for item in self.items:
            self.assertIsNone(item.updated_at)

    def test_no_created_at(self):
        for item in self.items:
            self.assertIsNone(item.created_at)


class TestChromeEdgeCases(unittest.TestCase):
    def setUp(self):
        self.imp = ChromeImporter()

    def test_empty_csv(self):
        p = _write_csv([])
        try:
            items = self.imp.parse(p)
            self.assertEqual(items, [])
        finally:
            p.unlink(missing_ok=True)

    def test_missing_name_gets_fallback_title(self):
        p = _write_csv([",https://x.com,u,p,"])
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertTrue(items[0].title.startswith("Chrome item"))
        finally:
            p.unlink(missing_ok=True)

    def test_empty_password_allowed(self):
        p = _write_csv(["NoPass,https://x.com,user,,"])
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].fields["password"], "")
        finally:
            p.unlink(missing_ok=True)

    def test_multiple_rows(self):
        p = _write_csv([
            "Site1,https://a.com,u1,p1,",
            "Site2,https://b.com,u2,p2,",
            "Site3,https://c.com,u3,p3,",
        ])
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 3)
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

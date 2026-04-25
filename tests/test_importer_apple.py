"""Testes do importer Apple Passwords (.csv)."""
from __future__ import annotations

import unittest
from pathlib import Path

from passmerge.core.canonical import Category
from passmerge.importers.apple import ApplePasswordsImporter

FIXTURE = Path(__file__).parent / "fixtures" / "apple_test.csv"


class TestApplePasswordsImporterProperties(unittest.TestCase):
    def setUp(self):
        self.imp = ApplePasswordsImporter()

    def test_source_name(self):
        self.assertEqual(self.imp.source_name, "applesenhas")

    def test_supports_timestamps(self):
        self.assertFalse(self.imp.supports_timestamps)

    def test_supported_categories(self):
        self.assertEqual(self.imp.supported_categories, {Category.LOGIN})


class TestApplePasswordsFixture(unittest.TestCase):
    def setUp(self):
        self.imp = ApplePasswordsImporter()
        self.items = self.imp.parse(FIXTURE)

    def test_item_count(self):
        self.assertEqual(len(self.items), 4)

    def test_all_items_are_login(self):
        for item in self.items:
            self.assertEqual(item.category, Category.LOGIN)

    def test_source_ref(self):
        for item in self.items:
            self.assertEqual(item.sources[0].source, "applesenhas")

    def test_github_fields(self):
        item = next(i for i in self.items if i.title == "GitHub")
        self.assertEqual(item.fields["username"], "user@example.com")
        self.assertEqual(item.fields["password"], "s3cr3t!Pass")
        self.assertEqual(item.fields["url"], "https://github.com")
        self.assertIn("otpauth://", item.fields["otp"])

    def test_github_notes(self):
        item = next(i for i in self.items if i.title == "GitHub")
        self.assertEqual(item.notes, "Conta dev principal")

    def test_item_without_otp_has_no_otp_field(self):
        item = next(i for i in self.items if i.title == "Banco Inter")
        self.assertNotIn("otp", item.fields)

    def test_unicode_title_and_fields(self):
        item = next(i for i in self.items if "Büro" in i.title)
        self.assertEqual(item.fields["username"], "üser")
        self.assertEqual(item.fields["password"], "pässwörd")

    def test_item_without_url(self):
        item = next(i for i in self.items if i.title == "Item sem URL")
        self.assertEqual(item.fields.get("url", ""), "")

    def test_fallback_title_when_blank(self):
        """Linha com Title vazio deve receber título gerado."""
        import io
        import csv
        import tempfile

        content = "Title,URL,Username,Password,Notes,OTPAuth\n,https://x.com,u,p,,\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            items = self.imp.parse(tmp)
            self.assertEqual(len(items), 1)
            self.assertTrue(items[0].title.startswith("Apple item"))
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

"""Testes do importer Kaspersky Password Manager (TXT com blocos)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import Category
from passmerge.importers.kaspersky import KasperskyImporter

FIXTURE = Path(__file__).parent / "fixtures" / "kaspersky_test.txt"


def _write_txt(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", encoding="utf-8", delete=False
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


class TestKasperskyImporterProperties(unittest.TestCase):
    def setUp(self):
        self.imp = KasperskyImporter()

    def test_source_name(self):
        self.assertEqual(self.imp.source_name, "kaspersky")

    def test_supports_timestamps(self):
        self.assertFalse(self.imp.supports_timestamps)

    def test_supported_categories_login(self):
        self.assertIn(Category.LOGIN, self.imp.supported_categories)

    def test_supported_categories_secure_note(self):
        self.assertIn(Category.SECURE_NOTE, self.imp.supported_categories)


class TestKasperskyFixture(unittest.TestCase):
    def setUp(self):
        self.imp = KasperskyImporter()
        self.items = self.imp.parse(FIXTURE)
        self._by_title = {item.title: item for item in self.items}

    def test_total_item_count(self):
        # 3 Websites + 2 Applications + 2 Notes = 7
        self.assertEqual(len(self.items), 7)

    def test_websites_are_logins(self):
        websites = [i for i in self.items if i.title in
                    {"GitHub", "Ação, Büro & Co.", "Empty URL Site"}]
        self.assertTrue(all(i.category == Category.LOGIN for i in websites))

    def test_applications_are_logins(self):
        apps = [i for i in self.items if i.title in {"VPN Client", "Database Tool"}]
        self.assertTrue(all(i.category == Category.LOGIN for i in apps))

    def test_notes_are_secure_notes(self):
        notes = [i for i in self.items if i.title in
                 {"Wi-Fi da Empresa", "Dados Bancários"}]
        self.assertTrue(all(i.category == Category.SECURE_NOTE for i in notes))

    def test_login_count(self):
        logins = [i for i in self.items if i.category == Category.LOGIN]
        self.assertEqual(len(logins), 5)

    def test_secure_note_count(self):
        notes = [i for i in self.items if i.category == Category.SECURE_NOTE]
        self.assertEqual(len(notes), 2)

    def test_source_ref_present(self):
        for item in self.items:
            self.assertEqual(len(item.sources), 1)
            self.assertEqual(item.sources[0].source, "kaspersky")

    def test_github_fields(self):
        item = self._by_title["GitHub"]
        self.assertEqual(item.fields["username"], "user@example.com")
        self.assertEqual(item.fields["password"], "s3cr3t!Pass")
        self.assertEqual(item.fields["url"], "https://github.com")

    def test_comment_becomes_notes(self):
        item = self._by_title["GitHub"]
        self.assertIn("Conta pessoal", item.notes)

    def test_unicode_entry(self):
        item = self._by_title["Ação, Büro & Co."]
        self.assertEqual(item.fields["username"], "üser")
        self.assertEqual(item.fields["password"], "pässwörd")
        self.assertEqual(item.fields["url"], "https://example.com/ação")

    def test_unicode_note(self):
        item = self._by_title["Ação, Büro & Co."]
        self.assertIn("vírgula", item.notes)

    def test_empty_url_website(self):
        item = self._by_title["Empty URL Site"]
        self.assertEqual(item.fields["url"], "")
        self.assertEqual(item.fields["username"], "nobody")

    def test_application_fields(self):
        item = self._by_title["VPN Client"]
        self.assertEqual(item.fields["username"], "vpnuser")
        self.assertEqual(item.fields["password"], "vpnSecure99")
        self.assertIn("corporativa", item.notes)

    def test_application_has_empty_url(self):
        # Applications não têm Website URL
        item = self._by_title["Database Tool"]
        self.assertEqual(item.fields.get("url", ""), "")

    def test_secure_note_body(self):
        item = self._by_title["Wi-Fi da Empresa"]
        self.assertIn("EmpresaWifi", item.fields.get("body", ""))

    def test_secure_note_body_with_colon_in_value(self):
        # "Note text: SSID: EmpresaWifi" — o colon no valor não deve ser partido
        item = self._by_title["Wi-Fi da Empresa"]
        self.assertIn("SSID:", item.fields.get("body", ""))

    def test_updated_at_is_none(self):
        for item in self.items:
            self.assertIsNone(item.updated_at)


class TestKasperskyEdgeCases(unittest.TestCase):
    def setUp(self):
        self.imp = KasperskyImporter()

    def test_empty_file(self):
        p = _write_txt("")
        try:
            self.assertEqual(self.imp.parse(p), [])
        finally:
            p.unlink(missing_ok=True)

    def test_single_website_entry(self):
        txt = (
            "Websites\n\n"
            "Website name: Test\n"
            "Website URL: https://test.com\n"
            "Login name:\n"
            "Login: u\n"
            "Password: p\n"
            "Comment:\n\n"
            "---\n"
        )
        p = _write_txt(txt)
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].title, "Test")
            self.assertEqual(items[0].category, Category.LOGIN)
            self.assertEqual(items[0].fields["username"], "u")
            self.assertEqual(items[0].fields["url"], "https://test.com")
        finally:
            p.unlink(missing_ok=True)

    def test_entry_without_final_separator(self):
        # Arquivo termina sem --- no final
        txt = (
            "Websites\n\n"
            "Website name: NoTrail\n"
            "Login: x\n"
            "Password: y\n"
        )
        p = _write_txt(txt)
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].title, "NoTrail")
        finally:
            p.unlink(missing_ok=True)

    def test_notes_block_creates_secure_note(self):
        txt = (
            "Notes\n\n"
            "Note name: MyNote\n"
            "Note text: Secret content\n"
            "Comment:\n\n"
            "---\n"
        )
        p = _write_txt(txt)
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].category, Category.SECURE_NOTE)
            self.assertIn("Secret content", items[0].fields.get("body", ""))
        finally:
            p.unlink(missing_ok=True)

    def test_notes_fallback_to_comment(self):
        # Sem note text, usa comment como body
        txt = (
            "Notes\n\n"
            "Note name: FallbackNote\n"
            "Note text:\n"
            "Comment: Conteúdo via comment\n\n"
            "---\n"
        )
        p = _write_txt(txt)
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertIn("comment", items[0].fields.get("body", ""))
        finally:
            p.unlink(missing_ok=True)

    def test_multiple_sections(self):
        txt = (
            "Websites\n\n"
            "Website name: W1\nLogin: u1\nPassword: p1\nComment:\n\n---\n\n"
            "Applications\n\n"
            "Application name: A1\nLogin: u2\nPassword: p2\nComment:\n\n---\n\n"
            "Notes\n\n"
            "Note name: N1\nNote text: body\nComment:\n\n---\n"
        )
        p = _write_txt(txt)
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 3)
            cats = {i.category for i in items}
            self.assertIn(Category.LOGIN, cats)
            self.assertIn(Category.SECURE_NOTE, cats)
        finally:
            p.unlink(missing_ok=True)

    def test_url_with_colon_parsed_correctly(self):
        # URL como "https://..." não deve ser partido no colon interno
        txt = (
            "Websites\n\n"
            "Website name: HTTPS Site\n"
            "Website URL: https://example.com/path?a=1\n"
            "Login: u\nPassword: p\nComment:\n\n---\n"
        )
        p = _write_txt(txt)
        try:
            items = self.imp.parse(p)
            self.assertEqual(items[0].fields["url"], "https://example.com/path?a=1")
        finally:
            p.unlink(missing_ok=True)

    def test_login_field_preferred_over_login_name(self):
        txt = (
            "Websites\n\n"
            "Website name: Pref\n"
            "Login name: display_name\n"
            "Login: actual_login\n"
            "Password: p\nComment:\n\n---\n"
        )
        p = _write_txt(txt)
        try:
            items = self.imp.parse(p)
            self.assertEqual(items[0].fields["username"], "actual_login")
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

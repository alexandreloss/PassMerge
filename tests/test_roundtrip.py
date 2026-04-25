"""Testes de round-trip: export → reimport → comparação campo a campo."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.exporters.apple import ApplePasswordsExporter
from passmerge.exporters.chrome import ChromeExporter
from passmerge.exporters.kaspersky import KasperskyExporter
from passmerge.exporters.nordpass import NordPassExporter
from passmerge.exporters.onepassword import OnePasswordExporter
from passmerge.importers.apple import ApplePasswordsImporter
from passmerge.importers.chrome import ChromeImporter
from passmerge.importers.kaspersky import KasperskyImporter
from passmerge.importers.nordpass import NordPassImporter
from passmerge.importers.onepassword import OnePasswordImporter


def _login(title="GitHub", username="alice", password="pass123",
           url="https://github.com") -> CanonicalItem:
    return CanonicalItem(
        category=Category.LOGIN, title=title,
        fields={"username": username, "password": password, "url": url},
        sources=[SourceRef(source="test")],
    )


def _card(title="Visa") -> CanonicalItem:
    return CanonicalItem(
        category=Category.CREDIT_CARD, title=title,
        fields={"cardholder": "Alice Smith", "number": "4111111111111111",
                "cvv": "321", "expiration": "202512", "zip": "10001"},
        sources=[SourceRef(source="test")],
    )


def _note(title="Backup Codes", body="alpha bravo charlie") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SECURE_NOTE, title=title,
        fields={"body": body},
        sources=[SourceRef(source="test")],
    )


def _server(title="Prod DB") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SERVER, title=title,
        fields={"hostname": "db.prod.example.com", "port": "5432",
                "username": "dbadmin", "password": "dbsecret"},
        sources=[SourceRef(source="test")],
    )


class TestChromeRoundTrip(unittest.TestCase):

    def test_login_roundtrip(self):
        items = [_login()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "chrome.csv"
            ChromeExporter().export(items, out)
            reimported = ChromeImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.title, "GitHub")
        self.assertEqual(r.fields["username"], "alice")
        self.assertEqual(r.fields["password"], "pass123")
        self.assertEqual(r.fields["url"], "https://github.com")

    def test_multiple_logins_roundtrip(self):
        items = [_login(title=f"Site{i}", username=f"u{i}", password=f"p{i}",
                        url=f"https://site{i}.com")
                 for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "chrome.csv"
            ChromeExporter().export(items, out)
            reimported = ChromeImporter().parse(out)

        self.assertEqual(len(reimported), 3)

    def test_unsupported_items_skipped_on_export(self):
        items = [_login(), _note()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "chrome.csv"
            report = ChromeExporter().export(items, out)
            reimported = ChromeImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        self.assertEqual(len(report.skipped_items), 1)

    def test_unicode_roundtrip(self):
        items = [_login(title="Meu Sîte", username="usuário", password="sênha@123")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "chrome.csv"
            ChromeExporter().export(items, out)
            reimported = ChromeImporter().parse(out)

        self.assertEqual(reimported[0].fields["username"], "usuário")
        self.assertEqual(reimported[0].fields["password"], "sênha@123")


class TestNordPassRoundTrip(unittest.TestCase):

    def test_login_roundtrip(self):
        items = [_login()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nordpass.csv"
            NordPassExporter().export(items, out)
            reimported = NordPassImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.fields["username"], "alice")
        self.assertEqual(r.fields["password"], "pass123")
        self.assertEqual(r.fields["url"], "https://github.com")

    def test_credit_card_roundtrip(self):
        items = [_card()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nordpass.csv"
            NordPassExporter().export(items, out)
            reimported = NordPassImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.category, Category.CREDIT_CARD)
        self.assertEqual(r.fields["cardholder"], "Alice Smith")
        self.assertEqual(r.fields["number"], "4111111111111111")
        self.assertEqual(r.fields["cvv"], "321")

    def test_secure_note_roundtrip(self):
        items = [_note()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nordpass.csv"
            NordPassExporter().export(items, out)
            reimported = NordPassImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        self.assertEqual(reimported[0].fields["body"], "alpha bravo charlie")

    def test_mixed_categories_roundtrip(self):
        items = [_login(), _card(), _note()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nordpass.csv"
            NordPassExporter().export(items, out)
            reimported = NordPassImporter().parse(out)

        self.assertEqual(len(reimported), 3)
        cats = {i.category for i in reimported}
        self.assertIn(Category.LOGIN, cats)
        self.assertIn(Category.CREDIT_CARD, cats)
        self.assertIn(Category.SECURE_NOTE, cats)

    def test_unsupported_exported_as_login(self):
        items = [_login(), _server()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nordpass.csv"
            report = NordPassExporter().export(items, out)
            reimported = NordPassImporter().parse(out)

        self.assertEqual(len(reimported), 2)
        self.assertEqual(len(report.skipped_items), 0)
        cats = {i.category for i in reimported}
        self.assertIn(Category.LOGIN, cats)


class TestKasperskyRoundTrip(unittest.TestCase):

    def test_login_roundtrip(self):
        items = [_login()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "kaspersky.txt"
            KasperskyExporter().export(items, out)
            reimported = KasperskyImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.title, "GitHub")
        self.assertEqual(r.fields["password"], "pass123")
        self.assertEqual(r.fields["url"], "https://github.com")

    def test_note_roundtrip(self):
        items = [_note()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "kaspersky.txt"
            KasperskyExporter().export(items, out)
            reimported = KasperskyImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.category, Category.SECURE_NOTE)
        self.assertEqual(r.title, "Backup Codes")
        self.assertEqual(r.fields["body"], "alpha bravo charlie")

    def test_login_and_note_roundtrip(self):
        items = [_login(), _note()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "kaspersky.txt"
            KasperskyExporter().export(items, out)
            reimported = KasperskyImporter().parse(out)

        self.assertEqual(len(reimported), 2)
        cats = {i.category for i in reimported}
        self.assertIn(Category.LOGIN, cats)
        self.assertIn(Category.SECURE_NOTE, cats)

    def test_unsupported_skipped(self):
        items = [_login(), _card()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "kaspersky.txt"
            report = KasperskyExporter().export(items, out)
            reimported = KasperskyImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        self.assertEqual(len(report.skipped_items), 1)


class TestOnePasswordRoundTrip(unittest.TestCase):

    def test_login_roundtrip(self):
        items = [_login()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export.1pux"
            OnePasswordExporter().export(items, out)
            reimported = OnePasswordImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.title, "GitHub")
        self.assertEqual(r.fields["username"], "alice")
        self.assertEqual(r.fields["password"], "pass123")
        self.assertEqual(r.fields.get("url"), "https://github.com")

    def test_credit_card_roundtrip(self):
        items = [_card()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export.1pux"
            OnePasswordExporter().export(items, out)
            reimported = OnePasswordImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.category, Category.CREDIT_CARD)
        self.assertEqual(r.fields["cardholder"], "Alice Smith")
        self.assertEqual(r.fields["number"], "4111111111111111")

    def test_secure_note_roundtrip(self):
        items = [_note()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export.1pux"
            OnePasswordExporter().export(items, out)
            reimported = OnePasswordImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        self.assertEqual(reimported[0].fields["body"], "alpha bravo charlie")

    def test_server_roundtrip(self):
        items = [_server()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export.1pux"
            OnePasswordExporter().export(items, out)
            reimported = OnePasswordImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.category, Category.SERVER)
        self.assertEqual(r.fields["hostname"], "db.prod.example.com")
        self.assertEqual(r.fields["port"], "5432")

    def test_mixed_categories_roundtrip(self):
        items = [_login(), _card(), _note(), _server()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export.1pux"
            OnePasswordExporter().export(items, out)
            reimported = OnePasswordImporter().parse(out)

        self.assertEqual(len(reimported), 4)
        cats = {i.category for i in reimported}
        self.assertIn(Category.LOGIN, cats)
        self.assertIn(Category.CREDIT_CARD, cats)
        self.assertIn(Category.SECURE_NOTE, cats)
        self.assertIn(Category.SERVER, cats)


class TestApplePasswordsRoundTrip(unittest.TestCase):

    def test_login_roundtrip(self):
        items = [_login()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "apple.csv"
            ApplePasswordsExporter().export(items, out)
            reimported = ApplePasswordsImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        r = reimported[0]
        self.assertEqual(r.title, "GitHub")
        self.assertEqual(r.fields["username"], "alice")
        self.assertEqual(r.fields["password"], "pass123")
        self.assertEqual(r.fields["url"], "https://github.com")

    def test_otp_roundtrip(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="GitHub OTP",
            fields={"username": "u", "password": "p", "url": "https://github.com",
                    "otp": "otpauth://totp/GitHub?secret=ABC123"},
            sources=[SourceRef(source="test")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "apple.csv"
            ApplePasswordsExporter().export([item], out)
            reimported = ApplePasswordsImporter().parse(out)

        self.assertEqual(reimported[0].fields["otp"],
                         "otpauth://totp/GitHub?secret=ABC123")

    def test_notes_roundtrip(self):
        item = _login(title="Noted")
        item.notes = "linha um\nlinha dois"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "apple.csv"
            ApplePasswordsExporter().export([item], out)
            reimported = ApplePasswordsImporter().parse(out)

        self.assertEqual(reimported[0].notes, "linha um\nlinha dois")

    def test_unsupported_skipped(self):
        items = [_login(), _note()]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "apple.csv"
            report = ApplePasswordsExporter().export(items, out)
            reimported = ApplePasswordsImporter().parse(out)

        self.assertEqual(len(reimported), 1)
        self.assertEqual(len(report.skipped_items), 1)

    def test_unicode_roundtrip(self):
        items = [_login(title="Ação", username="üser", password="pässwörd")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "apple.csv"
            ApplePasswordsExporter().export(items, out)
            reimported = ApplePasswordsImporter().parse(out)

        self.assertEqual(reimported[0].title, "Ação")
        self.assertEqual(reimported[0].fields["username"], "üser")


if __name__ == "__main__":
    unittest.main()

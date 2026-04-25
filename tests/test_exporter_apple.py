"""Testes do exporter Apple Passwords (.csv)."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import CanonicalItem, Category
from passmerge.exporters.apple import ApplePasswordsExporter


def _login(title: str, username: str = "u", password: str = "p",
           url: str = "https://example.com", notes: str = "",
           otp: str = "") -> CanonicalItem:
    fields = {"username": username, "password": password, "url": url}
    if otp:
        fields["otp"] = otp
    return CanonicalItem(category=Category.LOGIN, title=title,
                         fields=fields, notes=notes)


class TestApplePasswordsExporter(unittest.TestCase):
    def setUp(self):
        self.exp = ApplePasswordsExporter()

    def _export(self, items: list[CanonicalItem]) -> list[dict]:
        with tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False, mode="w"
        ) as f:
            tmp = Path(f.name)
        try:
            self.exp.export(items, tmp)
            with tmp.open(newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))
        finally:
            tmp.unlink(missing_ok=True)

    def test_header_columns(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp = Path(f.name)
        try:
            self.exp.export([], tmp)
            with tmp.open(newline="", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                header = next(reader)
            self.assertEqual(header, ["Title", "URL", "Username", "Password", "Notes", "OTPAuth"])
        finally:
            tmp.unlink(missing_ok=True)

    def test_basic_row(self):
        rows = self._export([_login("GitHub", "user@x.com", "pass")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Title"], "GitHub")
        self.assertEqual(rows[0]["Username"], "user@x.com")
        self.assertEqual(rows[0]["Password"], "pass")

    def test_otp_column_populated(self):
        rows = self._export([_login("Test", otp="otpauth://totp/Test?secret=ABC")])
        self.assertEqual(rows[0]["OTPAuth"], "otpauth://totp/Test?secret=ABC")

    def test_otp_column_empty_when_absent(self):
        rows = self._export([_login("NoOtp")])
        self.assertEqual(rows[0]["OTPAuth"], "")

    def test_notes_exported(self):
        rows = self._export([_login("X", notes="minha nota")])
        self.assertEqual(rows[0]["Notes"], "minha nota")

    def test_non_login_skipped(self):
        note = CanonicalItem(category=Category.SECURE_NOTE, title="N",
                             fields={"body": "txt"})
        report = self.exp.export([note], Path(tempfile.mktemp(suffix=".csv")))
        self.assertEqual(report.exported_count, 0)
        self.assertEqual(len(report.skipped_items), 1)
        self.assertEqual(report.skipped_items[0]["reason"], "unsupported_category")

    def test_export_count(self):
        items = [_login(f"Item{i}") for i in range(5)]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp = Path(f.name)
        try:
            report = self.exp.export(items, tmp)
            self.assertEqual(report.exported_count, 5)
        finally:
            tmp.unlink(missing_ok=True)

    def test_unicode_preserved(self):
        rows = self._export([_login("Ação", username="üser", password="pässwörd")])
        self.assertEqual(rows[0]["Title"], "Ação")
        self.assertEqual(rows[0]["Username"], "üser")


if __name__ == "__main__":
    unittest.main()

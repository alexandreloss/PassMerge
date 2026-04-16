"""Testes do importer NordPass (CSV multi-categoria)."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from passmerge.core.canonical import Category
from passmerge.importers.nordpass import NordPassImporter

FIXTURE = Path(__file__).parent / "fixtures" / "nordpass_test.csv"

_CSV_HEADER = (
    "name,url,username,password,note,cardholder,cardnumber,cvc,expirydate,"
    "zipcode,folder,full_name,phone_number,email,address1,address2,city,"
    "country,state,type,note_date\n"
)


def _write_csv(rows: list[str]) -> Path:
    """Escreve CSV em arquivo temporário e retorna o Path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", encoding="utf-8", delete=False
    )
    tmp.write(_CSV_HEADER)
    for r in rows:
        tmp.write(r + "\n")
    tmp.close()
    return Path(tmp.name)


class TestNordPassImporterProperties(unittest.TestCase):
    def setUp(self):
        self.imp = NordPassImporter()

    def test_source_name(self):
        self.assertEqual(self.imp.source_name, "nordpass")

    def test_supports_timestamps(self):
        self.assertTrue(self.imp.supports_timestamps)

    def test_supported_categories_login(self):
        self.assertIn(Category.LOGIN, self.imp.supported_categories)

    def test_supported_categories_credit_card(self):
        self.assertIn(Category.CREDIT_CARD, self.imp.supported_categories)

    def test_supported_categories_secure_note(self):
        self.assertIn(Category.SECURE_NOTE, self.imp.supported_categories)

    def test_supported_categories_identity(self):
        self.assertIn(Category.IDENTITY, self.imp.supported_categories)


class TestNordPassFixture(unittest.TestCase):
    def setUp(self):
        self.imp = NordPassImporter()
        self.items = self.imp.parse(FIXTURE)

    def test_total_item_count(self):
        self.assertEqual(len(self.items), 6)

    def test_login_count(self):
        logins = [i for i in self.items if i.category == Category.LOGIN]
        self.assertEqual(len(logins), 3)

    def test_credit_card_count(self):
        cards = [i for i in self.items if i.category == Category.CREDIT_CARD]
        self.assertEqual(len(cards), 1)

    def test_secure_note_count(self):
        notes = [i for i in self.items if i.category == Category.SECURE_NOTE]
        self.assertEqual(len(notes), 1)

    def test_identity_count(self):
        identities = [i for i in self.items if i.category == Category.IDENTITY]
        self.assertEqual(len(identities), 1)

    def test_source_ref_present(self):
        for item in self.items:
            self.assertEqual(len(item.sources), 1)
            self.assertEqual(item.sources[0].source, "nordpass")

    def test_login_fields(self):
        github = next(i for i in self.items if i.title == "GitHub")
        self.assertEqual(github.fields["username"], "user@example.com")
        self.assertEqual(github.fields["password"], "s3cr3t")
        self.assertEqual(github.fields["url"], "https://github.com")

    def test_login_unicode_title_and_fields(self):
        item = next(i for i in self.items if "Ação" in i.title)
        self.assertEqual(item.fields["username"], "üser")
        self.assertEqual(item.fields["password"], "pässwörd")

    def test_note_preserved_in_notes_field(self):
        item = next(i for i in self.items if "Ação" in i.title)
        self.assertIn("vírgula", item.notes)

    def test_folder_preserved(self):
        item = next(i for i in self.items if "Ação" in i.title)
        self.assertEqual(item.folder, "Work")

    def test_credit_card_fields(self):
        card = next(i for i in self.items if i.category == Category.CREDIT_CARD)
        self.assertEqual(card.fields["number"], "4111111111111111")
        self.assertEqual(card.fields["cvv"], "321")
        self.assertEqual(card.fields["expiration"], "2026-12")

    def test_credit_card_updated_at(self):
        card = next(i for i in self.items if i.category == Category.CREDIT_CARD)
        self.assertEqual(card.updated_at, "2024-03-15T10:00:00")

    def test_secure_note_body(self):
        note = next(i for i in self.items if i.category == Category.SECURE_NOTE)
        self.assertIn("HomeNet", note.fields["body"])

    def test_secure_note_updated_at(self):
        note = next(i for i in self.items if i.category == Category.SECURE_NOTE)
        self.assertEqual(note.updated_at, "2023-11-01T08:30:00")

    def test_identity_fields(self):
        identity = next(i for i in self.items if i.category == Category.IDENTITY)
        self.assertEqual(identity.fields["first_name"], "João da Silva")
        self.assertEqual(identity.fields["email"], "joao@example.com")
        self.assertEqual(identity.fields["city"], "São Paulo")

    def test_empty_url_login(self):
        item = next(i for i in self.items if i.title == "Empty URL Login")
        self.assertEqual(item.fields["url"], "")
        self.assertEqual(item.fields["username"], "nobody")

    def test_no_updated_at_when_note_date_absent(self):
        github = next(i for i in self.items if i.title == "GitHub")
        self.assertIsNone(github.updated_at)


class TestNordPassEdgeCases(unittest.TestCase):
    def setUp(self):
        self.imp = NordPassImporter()

    def test_empty_csv(self):
        p = _write_csv([])
        try:
            items = self.imp.parse(p)
            self.assertEqual(items, [])
        finally:
            p.unlink(missing_ok=True)

    def test_default_type_is_password(self):
        # sem coluna type → deve usar "password" → LOGIN
        p = _write_csv([
            "MyLogin,https://x.com,user,pass,,,,,,,,,,,,,,,,,"
        ])
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].category, Category.LOGIN)
        finally:
            p.unlink(missing_ok=True)

    def test_comma_in_note_handled(self):
        p = _write_csv([
            '"NoteTitle",,,,"Linha 1, Linha 2, Linha 3",,,,,,,,,,,,,,,note,2024-01-01'
        ])
        try:
            items = self.imp.parse(p)
            self.assertEqual(len(items), 1)
            self.assertIn("Linha 2", items[0].fields["body"])
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

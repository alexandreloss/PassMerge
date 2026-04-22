"""Testes do schema canônico."""
import json
import unittest

from passmerge.core.canonical import (
    SCHEMA_VERSION,
    CanonicalItem,
    Category,
    SourceRef,
    Vault,
    empty_vault,
)


class TestCanonicalItem(unittest.TestCase):
    def test_create_login(self):
        item = CanonicalItem(
            category=Category.LOGIN,
            title="GitHub",
            fields={"username": "alex", "password": "p"},
        )
        self.assertEqual(item.category, Category.LOGIN)
        self.assertTrue(item.id)
        self.assertEqual(item.validate(), [])

    def test_to_from_dict_roundtrip(self):
        item = CanonicalItem(
            category=Category.CREDIT_CARD,
            title="Visa",
            fields={"cardholder": "Alex", "number": "4111111111111111",
                    "expiration": "12/30"},
            tags=["pessoal"],
            sources=[SourceRef(source="1password", source_id="abc123")],
            updated_at="2024-05-01T10:00:00+00:00",
        )
        d = item.to_dict()
        restored = CanonicalItem.from_dict(d)
        self.assertEqual(restored.to_dict(), d)

    def test_empty_title_invalid(self):
        item = CanonicalItem(category=Category.LOGIN, title="  ")
        self.assertIn("title vazio", item.validate())

    def test_unknown_fields_warned(self):
        item = CanonicalItem(
            category=Category.LOGIN, title="x",
            fields={"username": "a", "XPTO": 1},
        )
        errs = item.validate()
        # "campos não esperados" é warning, não bloqueante em F1
        self.assertTrue(any("XPTO" in e for e in errs))


class TestVault(unittest.TestCase):
    def test_empty_vault_is_valid(self):
        v = empty_vault()
        self.assertEqual(v.schema_version, SCHEMA_VERSION)
        self.assertEqual(v.items, [])
        self.assertEqual(v.validate(), [])

    def test_json_roundtrip(self):
        v = empty_vault()
        v.items.append(CanonicalItem(
            category=Category.LOGIN, title="GitHub",
            fields={"username": "a", "password": "b"},
        ))
        blob = v.to_bytes()
        restored = Vault.from_bytes(blob)
        self.assertEqual(len(restored.items), 1)
        self.assertEqual(restored.items[0].title, "GitHub")
        self.assertEqual(restored.items[0].category, Category.LOGIN)

    def test_schema_version_mismatch_raises(self):
        bad = {"schema_version": "9.9", "items": []}
        with self.assertRaises(ValueError):
            Vault.from_dict(bad)

    def test_duplicate_id_flagged(self):
        v = empty_vault()
        a = CanonicalItem(category=Category.LOGIN, title="A", fields={"username": "x"})
        b = CanonicalItem(category=Category.LOGIN, title="B", fields={"username": "y"})
        b.id = a.id
        v.items.extend([a, b])
        errs = v.validate()
        self.assertTrue(any("ID duplicado" in e for e in errs))

    def test_summary_counts(self):
        v = empty_vault()
        v.items.append(CanonicalItem(category=Category.LOGIN, title="L1",
                                     fields={"username": "x"}))
        v.items.append(CanonicalItem(category=Category.LOGIN, title="L2",
                                     fields={"username": "y"}))
        v.items.append(CanonicalItem(category=Category.SECURE_NOTE, title="N",
                                     fields={"body": "txt"}))
        s = v.summary()
        self.assertEqual(s["login"], 2)
        self.assertEqual(s["secure_note"], 1)
        self.assertEqual(s["_total"], 3)
        self.assertEqual(s["_conflicts"], 0)

    def test_json_is_valid(self):
        v = empty_vault()
        v.items.append(CanonicalItem(
            category=Category.LOGIN, title="Sítê com acentos ção 🔐",
            fields={"username": "û", "password": "ß"},
        ))
        parsed = json.loads(v.to_json())
        self.assertEqual(parsed["items"][0]["title"], "Sítê com acentos ção 🔐")


class TestCategory(unittest.TestCase):
    def test_all_categories_in_enum(self):
        expected = {
            "login", "credit_card", "server", "secure_note", "identity",
            "software_license", "database", "wireless",
            "password", "bank_account", "driver_licence", "outdoor_license",
            "membership", "passport", "reward_program", "ssn",
            "email_account", "api_credential", "medical_record",
            "crypto_wallet", "document", "other",
        }
        self.assertEqual({c.value for c in Category}, expected)


if __name__ == "__main__":
    unittest.main()

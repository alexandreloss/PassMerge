"""Testes de passmerge.core.matching — chaves de deduplicação."""
from __future__ import annotations

import unittest

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.core.matching import primary_key


def _login(url="", username="", title="Login", **fields) -> CanonicalItem:
    return CanonicalItem(
        category=Category.LOGIN, title=title,
        fields={"url": url, "username": username, **fields},
    )


def _card(number="", cardholder="") -> CanonicalItem:
    return CanonicalItem(
        category=Category.CREDIT_CARD, title="Card",
        fields={"number": number, "cardholder": cardholder},
    )


def _note(title="", body="") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SECURE_NOTE, title=title,
        fields={"body": body},
    )


def _server(hostname="", username="", port="") -> CanonicalItem:
    return CanonicalItem(
        category=Category.SERVER, title="Server",
        fields={"hostname": hostname, "username": username, "port": port},
    )


def _wifi(ssid="") -> CanonicalItem:
    return CanonicalItem(
        category=Category.WIRELESS, title="WiFi",
        fields={"ssid": ssid},
    )


class TestLoginKey(unittest.TestCase):
    def test_same_domain_variants_same_key(self):
        a = _login("https://github.com/login", "alice@example.com")
        b = _login("http://www.github.com",    "alice@example.com")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_username_different_key(self):
        a = _login("https://github.com", "alice@example.com")
        b = _login("https://github.com", "bob@example.com")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_different_domain_different_key(self):
        a = _login("https://github.com",  "alice@example.com")
        b = _login("https://gitlab.com",  "alice@example.com")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_username_case_insensitive(self):
        a = _login("https://github.com", "Alice@Example.COM")
        b = _login("https://github.com", "alice@example.com")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_empty_url_still_produces_key(self):
        a = _login("", "alice")
        b = _login("", "alice")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_login_and_card_never_collide(self):
        login = _login("", "")
        card = _card("1234", "")
        self.assertNotEqual(primary_key(login), primary_key(card))


class TestCreditCardKey(unittest.TestCase):
    def test_same_last4_and_cardholder_same_key(self):
        a = _card("4111111111111111", "Alexandre Loss")
        b = _card("5500001111111111", "Alexandre Loss")
        # últimos 4 dígitos ambos "1111" → mesma chave
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_last4_different_key(self):
        a = _card("4111111111111111", "Alexandre Loss")
        b = _card("4111111111119999", "Alexandre Loss")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_different_cardholder_different_key(self):
        a = _card("4111111111111111", "Alexandre Loss")
        b = _card("4111111111111111", "Maria Loss")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_cardholder_case_insensitive(self):
        a = _card("4111111111111111", "ALEXANDRE LOSS")
        b = _card("4111111111111111", "alexandre loss")
        self.assertEqual(primary_key(a), primary_key(b))


class TestSecureNoteKey(unittest.TestCase):
    def test_same_title_and_body_same_key(self):
        a = _note("Wifi Empresa", "senha: abc123")
        b = _note("Wifi Empresa", "senha: abc123")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_body_different_key(self):
        a = _note("Wifi Empresa", "senha: abc123")
        b = _note("Wifi Empresa", "senha: xyz789")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_different_title_different_key(self):
        a = _note("Wifi Casa",    "senha: abc123")
        b = _note("Wifi Empresa", "senha: abc123")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_title_case_insensitive(self):
        a = _note("WIFI EMPRESA", "senha: abc123")
        b = _note("wifi empresa", "senha: abc123")
        self.assertEqual(primary_key(a), primary_key(b))


class TestServerKey(unittest.TestCase):
    def test_same_host_user_port_same_key(self):
        a = _server("db.example.com", "admin", "5432")
        b = _server("DB.Example.COM", "Admin", "5432")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_port_different_key(self):
        a = _server("db.example.com", "admin", "5432")
        b = _server("db.example.com", "admin", "3306")
        self.assertNotEqual(primary_key(a), primary_key(b))


class TestWirelessKey(unittest.TestCase):
    def test_same_ssid_same_key(self):
        a = _wifi("MyHomeNetwork")
        b = _wifi("myhomenetwork")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_ssid_different_key(self):
        a = _wifi("HomeNetwork")
        b = _wifi("OfficeNetwork")
        self.assertNotEqual(primary_key(a), primary_key(b))


if __name__ == "__main__":
    unittest.main()

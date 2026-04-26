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


def _server(hostname="", username="", port="", **extras) -> CanonicalItem:
    return CanonicalItem(
        category=Category.SERVER, title="Server",
        fields={"hostname": hostname, "username": username, "port": port},
        extras=extras,
    )


def _card_extras(**extras) -> CanonicalItem:
    return CanonicalItem(
        category=Category.CREDIT_CARD, title="Card",
        fields={},
        extras=extras,
    )


def _server_extras(**extras) -> CanonicalItem:
    return CanonicalItem(
        category=Category.SERVER, title="Server",
        fields={},
        extras=extras,
    )


def _wifi_extras(**extras) -> CanonicalItem:
    return CanonicalItem(
        category=Category.WIRELESS, title="WiFi",
        fields={},
        extras=extras,
    )


def _wifi(ssid="") -> CanonicalItem:
    return CanonicalItem(
        category=Category.WIRELESS, title="WiFi",
        fields={"ssid": ssid},
    )


class TestLoginKey(unittest.TestCase):
    def test_path_and_query_ignored(self):
        # path, query e fragmento não fazem parte da chave
        a = _login("https://prd-aa1.lg.com.br/Autoatendimento/index.html?id=1447&uid=448165025", "alice")
        b = _login("https://prd-aa1.lg.com.br/outra/pagina", "alice")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_www_normalized(self):
        # www. é removido — https://www.aa.com == https://aa.com
        a = _login("https://www.aa.com/homePage.do", "alice")
        b = _login("https://aa.com/homePage.do",     "alice")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_subdomain_preserved(self):
        # subdomínio completo é preservado
        a = _login("https://prd-aa1.lg.com.br/path", "alice")
        b = _login("https://lg.com.br/path",          "alice")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_scheme_preserved(self):
        # scheme faz parte da chave
        a = _login("https://visabenefits.force.com/webportal/", "alice")
        b = _login("http://visabenefits.force.com/webportal/",  "alice")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_same_origin_same_key(self):
        a = _login("https://github.com/login", "alice@example.com")
        b = _login("https://github.com/other", "alice@example.com")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_username_different_key(self):
        a = _login("https://github.com", "alice@example.com")
        b = _login("https://github.com", "bob@example.com")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_different_origin_different_key(self):
        a = _login("https://github.com", "alice@example.com")
        b = _login("https://gitlab.com", "alice@example.com")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_username_case_insensitive(self):
        a = _login("https://github.com", "Alice@Example.COM")
        b = _login("https://github.com", "alice@example.com")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_origin_case_insensitive(self):
        a = _login("HTTPS://GitHub.COM/login", "alice")
        b = _login("https://github.com/other", "alice")
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
    def test_same_full_number_and_cardholder_same_key(self):
        a = _card("4111111111111111", "Alexandre Loss")
        b = _card("4111111111111111", "Alexandre Loss")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_same_last4_but_different_number_different_key(self):
        # com número completo, dois cartões com últimos 4 iguais mas números distintos → chaves diferentes
        a = _card("4111111111111111", "Alexandre Loss")
        b = _card("5500001111111111", "Alexandre Loss")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_different_number_different_key(self):
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

    def test_extras_numero_fallback(self):
        # número em extras["número"] (campo português não mapeado pelo importer)
        a = _card("4111111111111111", "Alexandre Loss")
        b = _card_extras(**{"número": "4111111111111111", "titular": "Alexandre Loss"})
        self.assertEqual(primary_key(a), primary_key(b))

    def test_extras_numero_different_card_different_key(self):
        a = _card_extras(**{"número": "4111111111111111"})
        b = _card_extras(**{"número": "5500000000000004"})
        self.assertNotEqual(primary_key(a), primary_key(b))


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
    def test_same_host_user_same_key(self):
        a = _server("db.example.com", "admin")
        b = _server("DB.Example.COM", "Admin")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_port_same_key(self):
        # porta não faz parte da chave; mesmo host+user → mesma chave
        a = _server("db.example.com", "admin", "5432")
        b = _server("db.example.com", "admin", "3306")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_host_different_key(self):
        a = _server("db.example.com", "admin")
        b = _server("db2.example.com", "admin")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_extras_url_fallback(self):
        # campos pt: "url" como host, "nome de usuário"
        a = _server("db.example.com", "admin")
        b = _server_extras(**{"url": "db.example.com", "nome de usuário": "admin"})
        self.assertEqual(primary_key(a), primary_key(b))

    def test_extras_servidor_fallback(self):
        a = _server_extras(**{"servidor": "db.example.com", "nome de usuário": "admin"})
        b = _server_extras(**{"servidor": "db.example.com", "nome de usuário": "admin"})
        self.assertEqual(primary_key(a), primary_key(b))


class TestWirelessKey(unittest.TestCase):
    def test_same_ssid_same_key(self):
        a = _wifi("MyHomeNetwork")
        b = _wifi("myhomenetwork")
        self.assertEqual(primary_key(a), primary_key(b))

    def test_different_ssid_different_key(self):
        a = _wifi("HomeNetwork")
        b = _wifi("OfficeNetwork")
        self.assertNotEqual(primary_key(a), primary_key(b))

    def test_extras_nome_da_rede_fallback(self):
        a = _wifi("MinhaRede")
        b = _wifi_extras(**{"nome da rede": "MinhaRede"})
        self.assertEqual(primary_key(a), primary_key(b))

    def test_extras_nome_da_rede_different_ssid_different_key(self):
        a = _wifi_extras(**{"nome da rede": "Rede1"})
        b = _wifi_extras(**{"nome da rede": "Rede2"})
        self.assertNotEqual(primary_key(a), primary_key(b))


class TestDatabaseExtrasKey(unittest.TestCase):
    def test_extras_servidor_tipo_usuario(self):
        a = CanonicalItem(
            category=Category.DATABASE, title="DB",
            fields={},
            extras={"servidor": "db.host.com", "tipo": "mysql", "nome de usuário": "root"},
        )
        b = CanonicalItem(
            category=Category.DATABASE, title="DB",
            fields={},
            extras={"servidor": "db.host.com", "tipo": "mysql", "nome de usuário": "root"},
        )
        self.assertEqual(primary_key(a), primary_key(b))

    def test_canonical_fields_take_precedence_over_extras(self):
        a = CanonicalItem(
            category=Category.DATABASE, title="DB",
            fields={"hostname": "db.host.com", "database": "mydb", "username": "root"},
            extras={"servidor": "other.host.com"},
        )
        b = CanonicalItem(
            category=Category.DATABASE, title="DB",
            fields={"hostname": "db.host.com", "database": "mydb", "username": "root"},
            extras={},
        )
        self.assertEqual(primary_key(a), primary_key(b))


if __name__ == "__main__":
    unittest.main()

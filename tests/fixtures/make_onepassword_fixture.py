"""Gerador da fixture .1pux do 1Password.

Execute com:
    python tests/fixtures/make_onepassword_fixture.py

Produz tests/fixtures/onepassword_test.1pux — um ZIP contendo export.data
com 7 itens cobrindo as principais categorias.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

EXPORT_DATA = {
    "accounts": [{
        "vaults": [{
            "items": [
                # --- Login com OTP, tags e favorito ---
                {
                    "uuid": "login-item-001",
                    "createdAt": 1672531200,   # 2023-01-01
                    "updatedAt": 1700010000,   # 2023-11-14
                    "categoryUuid": "001",
                    "favorite": 1,
                    "trashed": "N",
                    "overview": {
                        "title": "GitHub",
                        "url": "https://github.com",
                        "tags": ["dev", "git"],
                    },
                    "details": {
                        "loginFields": [
                            {"designation": "username", "value": "user@example.com"},
                            {"designation": "password", "value": "s3cr3t!Pass"},
                        ],
                        "notesPlain": "",
                        "sections": [{
                            "title": "OTP",
                            "fields": [{
                                "id": "TOTP_login-item-001",
                                "title": "one-time password",
                                "value": {"totp": "otpauth://totp/GitHub:user%40example.com"
                                          "?secret=JBSWY3DPEHPK3PXP&issuer=GitHub"},
                            }],
                        }],
                    },
                },
                # --- Login com unicode ---
                {
                    "uuid": "login-item-002",
                    "createdAt": 1675209600,
                    "updatedAt": 1675209600,
                    "categoryUuid": "001",
                    "favorite": 0,
                    "trashed": "N",
                    "overview": {"title": "Ação, Büro & Co.", "url": "", "tags": []},
                    "details": {
                        "loginFields": [
                            {"designation": "username", "value": "üser"},
                            {"designation": "password", "value": "pässwörd"},
                        ],
                        "notesPlain": "",
                        "sections": [],
                    },
                },
                # --- Cartão de crédito ---
                {
                    "uuid": "cc-item-001",
                    "createdAt": 1677628800,
                    "updatedAt": 1677628800,
                    "categoryUuid": "002",
                    "favorite": 0,
                    "trashed": "N",
                    "overview": {"title": "Visa Pessoal", "url": "", "tags": []},
                    "details": {
                        "loginFields": [],
                        "notesPlain": "",
                        "sections": [{
                            "title": "Dados do cartão",
                            "fields": [
                                {"id": "cardholder", "title": "cardholder",
                                 "value": {"string": "Alexandre Loss"}},
                                {"id": "ccnum", "title": "ccnum",
                                 "value": {"string": "4111111111111111"}},
                                {"id": "cvv",  "title": "cvv",
                                 "value": {"concealed": "123"}},
                            ],
                        }],
                    },
                },
                # --- Nota segura ---
                {
                    "uuid": "note-item-001",
                    "createdAt": 1680307200,
                    "updatedAt": 1680307200,
                    "categoryUuid": "003",
                    "favorite": 0,
                    "trashed": "N",
                    "overview": {"title": "Senha EmpresaWifi", "url": "", "tags": []},
                    "details": {
                        "loginFields": [],
                        "notesPlain": "EmpresaWifi: senha123",
                        "sections": [],
                    },
                },
                # --- Servidor ---
                {
                    "uuid": "server-item-001",
                    "createdAt": 1682899200,
                    "updatedAt": 1682899200,
                    "categoryUuid": "110",
                    "favorite": 0,
                    "trashed": "N",
                    "overview": {"title": "DB Produção", "url": "", "tags": []},
                    "details": {
                        "loginFields": [],
                        "notesPlain": "",
                        "sections": [{
                            "title": "Conexão",
                            "fields": [
                                {"id": "hostname", "title": "hostname",
                                 "value": {"string": "db.example.com"}},
                                {"id": "username", "title": "username",
                                 "value": {"string": "admin"}},
                                {"id": "password", "title": "password",
                                 "value": {"concealed": "dbpass"}},
                                {"id": "port",     "title": "port",
                                 "value": {"string": "5432"}},
                            ],
                        }],
                    },
                },
                # --- Rede wireless ---
                {
                    "uuid": "wifi-item-001",
                    "createdAt": 1685577600,
                    "updatedAt": 1685577600,
                    "categoryUuid": "111",
                    "favorite": 0,
                    "trashed": "N",
                    "overview": {"title": "MyHomeNetwork", "url": "", "tags": []},
                    "details": {
                        "loginFields": [],
                        "notesPlain": "",
                        "sections": [{
                            "title": "Rede",
                            "fields": [
                                {"id": "ssid", "title": "ssid",
                                 "value": {"string": "MyHomeNetwork"}},
                                {"id": "wireless_security", "title": "wireless_security",
                                 "value": {"menu": "WPA2"}},
                            ],
                        }],
                    },
                },
                # --- Item na lixeira ---
                {
                    "uuid": "trashed-item-001",
                    "createdAt": 1688256000,
                    "updatedAt": 1688256000,
                    "categoryUuid": "001",
                    "favorite": 0,
                    "trashed": "Y",
                    "overview": {"title": "Item Deletado", "url": "", "tags": []},
                    "details": {
                        "loginFields": [
                            {"designation": "username", "value": "old@example.com"},
                            {"designation": "password", "value": "oldpass"},
                        ],
                        "notesPlain": "",
                        "sections": [],
                    },
                },
            ],
        }],
    }],
}


def build_fixture(dest: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.data", json.dumps(EXPORT_DATA, ensure_ascii=False))
    dest.write_bytes(buf.getvalue())
    print(f"Fixture gravada em {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    build_fixture(Path(__file__).parent / "onepassword_test.1pux")

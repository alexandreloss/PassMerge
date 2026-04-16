"""Gerador da fixture sintética do 1Password.

Execute com:
    python tests/fixtures/make_onepassword_fixture.py

Produz tests/fixtures/onepassword_test.1pux — um ZIP mínimo com export.data.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

EXPORT_DATA = {
    "accounts": [
        {
            "attrs": {"name": "Test Account"},
            "vaults": [
                {
                    "attrs": {"name": "Personal"},
                    "items": [
                        # --- LOGIN ---
                        {
                            "uuid": "login-item-001",
                            "createdAt": 1700000000,
                            "updatedAt": 1700010000,
                            "categoryUuid": "001",
                            "favorite": 1,
                            "trashed": "N",
                            "overview": {
                                "title": "GitHub",
                                "url": "https://github.com",
                                "tags": ["dev", "git"],
                                "ainfo": "user@example.com",
                            },
                            "details": {
                                "loginFields": [
                                    {
                                        "value": "user@example.com",
                                        "designation": "username",
                                    },
                                    {
                                        "value": "s3cr3t!Pass",
                                        "designation": "password",
                                    },
                                ],
                                "notesPlain": "Conta pessoal do GitHub",
                                "sections": [
                                    {
                                        "title": "OTP",
                                        "fields": [
                                            {
                                                "title": "one-time password",
                                                "id": "TOTP_001",
                                                "value": {"totp": "otpauth://totp/gh?secret=ABCD"},
                                            }
                                        ],
                                    }
                                ],
                            },
                        },
                        # --- LOGIN com unicode e vírgula no título ---
                        {
                            "uuid": "login-item-002",
                            "createdAt": 1700020000,
                            "updatedAt": 1700030000,
                            "categoryUuid": "001",
                            "favorite": 0,
                            "trashed": "N",
                            "overview": {
                                "title": "Ação, Büro & Co.",
                                "url": "https://example.com/ação",
                                "tags": [],
                            },
                            "details": {
                                "loginFields": [
                                    {"value": "üser", "designation": "username"},
                                    {"value": "pässwörd", "designation": "password"},
                                ],
                                "notesPlain": "",
                                "sections": [],
                            },
                        },
                        # --- CREDIT_CARD ---
                        {
                            "uuid": "cc-item-001",
                            "createdAt": 1700040000,
                            "updatedAt": 1700050000,
                            "categoryUuid": "002",
                            "favorite": 0,
                            "trashed": "N",
                            "overview": {"title": "Visa Gold"},
                            "details": {
                                "loginFields": [],
                                "notesPlain": "",
                                "sections": [
                                    {
                                        "title": "Card Details",
                                        "fields": [
                                            {
                                                "title": "cardholder",
                                                "id": "cardholder",
                                                "value": {"string": "Alexandre Loss"},
                                            },
                                            {
                                                "title": "ccnum",
                                                "id": "ccnum",
                                                "value": {"concealed": "4111111111111111"},
                                            },
                                            {
                                                "title": "cvv",
                                                "id": "cvv",
                                                "value": {"concealed": "123"},
                                            },
                                            {
                                                "title": "expiry",
                                                "id": "expiry",
                                                "value": {"monthYear": "202612"},
                                            },
                                        ],
                                    }
                                ],
                            },
                        },
                        # --- SECURE_NOTE ---
                        {
                            "uuid": "note-item-001",
                            "createdAt": 1700060000,
                            "updatedAt": 1700070000,
                            "categoryUuid": "003",
                            "favorite": 0,
                            "trashed": "N",
                            "overview": {"title": "Wi-Fi da Empresa"},
                            "details": {
                                "loginFields": [],
                                "notesPlain": "SSID: EmpresaWifi\nSenha: superSecret99",
                                "sections": [],
                            },
                        },
                        # --- SERVER (categoryUuid 110) ---
                        {
                            "uuid": "server-item-001",
                            "createdAt": 1700080000,
                            "updatedAt": 1700090000,
                            "categoryUuid": "110",
                            "favorite": 0,
                            "trashed": "N",
                            "overview": {"title": "Production DB Server"},
                            "details": {
                                "loginFields": [],
                                "notesPlain": "",
                                "sections": [
                                    {
                                        "title": "Server",
                                        "fields": [
                                            {
                                                "title": "hostname",
                                                "id": "hostname",
                                                "value": {"string": "db.example.com"},
                                            },
                                            {
                                                "title": "username",
                                                "id": "username",
                                                "value": {"string": "admin"},
                                            },
                                            {
                                                "title": "password",
                                                "id": "password",
                                                "value": {"concealed": "dbpass123"},
                                            },
                                            {
                                                "title": "port",
                                                "id": "port",
                                                "value": {"string": "5432"},
                                            },
                                        ],
                                    }
                                ],
                            },
                        },
                        # --- WIRELESS (categoryUuid 111) ---
                        {
                            "uuid": "wifi-item-001",
                            "createdAt": 1700100000,
                            "updatedAt": 1700110000,
                            "categoryUuid": "111",
                            "favorite": 0,
                            "trashed": "N",
                            "overview": {"title": "HomeWifi"},
                            "details": {
                                "loginFields": [],
                                "notesPlain": "",
                                "sections": [
                                    {
                                        "title": "Wireless",
                                        "fields": [
                                            {
                                                "title": "ssid",
                                                "id": "ssid",
                                                "value": {"string": "MyHomeNetwork"},
                                            },
                                            {
                                                "title": "network_key",
                                                "id": "network_key",
                                                "value": {"concealed": "wifipass!"},
                                            },
                                            {
                                                "title": "wireless_security",
                                                "id": "wireless_security",
                                                "value": {"menu": "WPA2"},
                                            },
                                        ],
                                    }
                                ],
                            },
                        },
                        # --- TRASHED item (deve aparecer mas trashed=True) ---
                        {
                            "uuid": "trashed-item-001",
                            "createdAt": 1700120000,
                            "updatedAt": 1700130000,
                            "categoryUuid": "001",
                            "favorite": 0,
                            "trashed": "Y",
                            "overview": {"title": "Old Account"},
                            "details": {
                                "loginFields": [
                                    {"value": "old@example.com", "designation": "username"},
                                    {"value": "oldpass", "designation": "password"},
                                ],
                                "notesPlain": "",
                                "sections": [],
                            },
                        },
                    ],
                }
            ],
        }
    ]
}


def build_fixture(dest: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("export.data", json.dumps(EXPORT_DATA, ensure_ascii=False))
    dest.write_bytes(buf.getvalue())
    print(f"Fixture gravada em {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    here = Path(__file__).parent
    build_fixture(here / "onepassword_test.1pux")

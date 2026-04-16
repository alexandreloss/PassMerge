"""Gerador da fixture SQLite do 1Password.

Execute com:
    python tests/fixtures/make_onepassword_sqlite_fixture.py

Produz tests/fixtures/onepassword_test.sqlite.zip — um ZIP contendo
export.sqlite com os mesmos itens da fixture JSON (.1pux).

Esquema do banco:
    items(uuid, category_uuid, created_at, updated_at, trashed, favorite,
          title, url, notes)
    item_fields(item_uuid, section_name, field_id, field_title,
                field_value, field_type)
    item_tags(item_uuid, tag)
"""
from __future__ import annotations

import io
import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

# Permite rodar tanto como script quanto importado nos testes
sys.path.insert(0, str(Path(__file__).parent))
from make_onepassword_fixture import EXPORT_DATA  # noqa: E402


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE items (
            uuid          TEXT PRIMARY KEY,
            category_uuid TEXT    NOT NULL,
            created_at    INTEGER,
            updated_at    INTEGER,
            trashed       INTEGER DEFAULT 0,
            favorite      INTEGER DEFAULT 0,
            title         TEXT,
            url           TEXT,
            notes         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE item_fields (
            item_uuid    TEXT NOT NULL,
            section_name TEXT,
            field_id     TEXT,
            field_title  TEXT,
            field_value  TEXT,
            field_type   TEXT DEFAULT 'string'
        )
    """)
    conn.execute("""
        CREATE TABLE item_tags (
            item_uuid TEXT NOT NULL,
            tag       TEXT NOT NULL
        )
    """)
    conn.commit()


def _insert_item(conn: sqlite3.Connection, item: dict) -> None:
    overview = item.get("overview") or {}
    details = item.get("details") or {}
    uuid = item["uuid"]

    conn.execute(
        "INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?)",
        (
            uuid,
            item.get("categoryUuid", "001"),
            item.get("createdAt"),
            item.get("updatedAt"),
            1 if str(item.get("trashed", "N")).upper() == "Y" else 0,
            item.get("favorite", 0),
            overview.get("title", "sem título"),
            overview.get("url", ""),
            details.get("notesPlain", ""),
        ),
    )

    # Campos de login (designation)
    for lf in details.get("loginFields") or []:
        designation = lf.get("designation", "")
        conn.execute(
            "INSERT INTO item_fields VALUES (?,?,?,?,?,?)",
            (uuid, None, designation, designation, lf.get("value", ""), "string"),
        )

    # Campos de seção
    for section in details.get("sections") or []:
        section_name = section.get("title", "")
        for field in section.get("fields") or []:
            fv = field.get("value") or {}
            if isinstance(fv, dict) and fv:
                field_type = next(iter(fv))
                field_value = str(fv[field_type]) if fv[field_type] is not None else ""
            else:
                field_type = "string"
                field_value = str(fv) if fv else ""
            conn.execute(
                "INSERT INTO item_fields VALUES (?,?,?,?,?,?)",
                (
                    uuid,
                    section_name,
                    field.get("id", ""),
                    field.get("title", ""),
                    field_value,
                    field_type,
                ),
            )

    # Tags
    for tag in overview.get("tags") or []:
        conn.execute("INSERT INTO item_tags VALUES (?,?)", (uuid, tag))

    conn.commit()


def build_fixture(dest: Path) -> None:
    """Cria o ZIP com SQLite em *dest*."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        tmp_db = tf.name

    try:
        conn = sqlite3.connect(tmp_db)
        _create_schema(conn)

        for account in EXPORT_DATA.get("accounts") or []:
            for vault in account.get("vaults") or []:
                for item in vault.get("items") or []:
                    _insert_item(conn, item)

        conn.close()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db, "export.sqlite")
        dest.write_bytes(buf.getvalue())
        print(f"Fixture SQLite gravada em {dest} ({dest.stat().st_size} bytes)")
    finally:
        os.unlink(tmp_db)


if __name__ == "__main__":
    here = Path(__file__).parent
    build_fixture(here / "onepassword_test.sqlite.zip")

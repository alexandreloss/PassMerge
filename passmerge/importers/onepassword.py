"""Importer para o 1Password.

Suporta dois formatos de exportação:
1. Arquivo ``.sqlite`` / ``.db`` passado diretamente
2. ZIP contendo um arquivo SQLite — detectado por extensão (``.sqlite``,
   ``.db``, ``.sqlite3``) ou por magic bytes (``SQLite format 3\\x00``),
   independentemente do nome do arquivo dentro do ZIP

Esquema SQLite esperado::

    CREATE TABLE items (
        uuid          TEXT PRIMARY KEY,
        category_uuid TEXT    NOT NULL,
        created_at    INTEGER,
        updated_at    INTEGER,
        trashed       INTEGER DEFAULT 0,   -- 0 = não, 1 = sim
        favorite      INTEGER DEFAULT 0,
        title         TEXT,
        url           TEXT,
        notes         TEXT
    );

    CREATE TABLE item_fields (
        item_uuid    TEXT NOT NULL,
        section_name TEXT,                  -- NULL para campos designation (login)
        field_id     TEXT,
        field_title  TEXT,
        field_value  TEXT,
        field_type   TEXT DEFAULT 'string'  -- string, concealed, totp, url,
                                            -- monthYear, menu, …
    );

    CREATE TABLE item_tags (
        item_uuid TEXT NOT NULL,
        tag       TEXT NOT NULL
    );

"""
from __future__ import annotations

import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category, SourceRef
from ..core.categories import ONEPASSWORD_TO_CANONICAL
from .base import Importer

# Campos de login por designation
_LOGIN_DESIGNATIONS = {"username", "password"}

# Extensões de arquivo SQLite reconhecidas
_SQLITE_EXTENSIONS = {".sqlite", ".db", ".sqlite3"}

# Magic bytes do SQLite — usados para detectar o banco mesmo sem extensão
_SQLITE_MAGIC = b"SQLite format 3\x00"

# Mapeamento de field-id/title comuns para chaves canônicas
_SECTION_FIELD_MAP: dict[str, str] = {
    "username": "username",
    "password": "password",
    "hostname": "hostname",
    "port": "port",
    "database": "database",
    "type": "type",
    "server": "hostname",
    "cardholder": "cardholder",
    "ccnum": "number",
    "cvv": "cvv",
    "expiry": "expiration",
    "pin": "pin",
    "firstname": "first_name",
    "lastname": "last_name",
    "email": "email",
    "phone": "phone",
    "address": "address1",
    "city": "city",
    "state": "state",
    "country": "country",
    "zip": "zip",
    "birthdate": "birth_date",
    "product": "product",
    "reg_code": "license_key",
    "reg_name": "licensed_to",
    "version": "version",
    "ssid": "ssid",
    "network_key": "password",
    "wireless_security": "security_type",
}


# ---------------------------------------------------------------------------
# Funções auxiliares compartilhadas entre os dois formatos
# ---------------------------------------------------------------------------

def _epoch_to_iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(
            timespec="seconds"
        )
    except (ValueError, OSError, OverflowError):
        return None


def _extract_field_value(fv: Any) -> str:
    """Extrai valor de um campo de section (pode ser dict com tipo ou escalar)."""
    if isinstance(fv, dict):
        # Tipos conhecidos: string, concealed, url, totp, date, monthYear, email, phone, …
        for key in ("string", "concealed", "url", "totp", "date", "monthYear",
                    "email", "phone", "gender", "menu", "cctype"):
            if key in fv:
                v = fv[key]
                return str(v) if v is not None else ""
        # Fallback: primeiro valor não-nulo
        for v in fv.values():
            return str(v) if v is not None else ""
        return ""
    return str(fv) if fv is not None else ""


def _parse_item(raw: dict[str, Any]) -> CanonicalItem | None:
    """Converte um item bruto (dict no formato .1pux) em CanonicalItem."""
    category_uuid = raw.get("categoryUuid", "")
    category = ONEPASSWORD_TO_CANONICAL.get(category_uuid, Category.OTHER)

    overview = raw.get("overview") or {}
    details = raw.get("details") or {}

    title = overview.get("title") or raw.get("uuid", "sem título")
    if not title:
        title = "sem título"

    created_at = _epoch_to_iso(raw.get("createdAt"))
    updated_at = _epoch_to_iso(raw.get("updatedAt"))

    favorite = bool(raw.get("favorite", 0))
    trashed = str(raw.get("trashed", "N")).upper() == "Y"

    tags: list[str] = list(overview.get("tags") or [])
    folder: str | None = None

    source_id: str | None = raw.get("uuid") or None
    source_ref = SourceRef(source="1password", source_id=source_id)

    fields: dict[str, Any] = {}
    extras: dict[str, Any] = {}

    # --- loginFields (designation username/password) ---
    for lf in details.get("loginFields") or []:
        designation = (lf.get("designation") or "").lower()
        value = lf.get("value") or ""
        if designation in _LOGIN_DESIGNATIONS:
            fields[designation] = value
        elif designation:
            extras[f"loginField_{designation}"] = value

    # URL principal da overview
    main_url = overview.get("url") or ""
    if main_url and category == Category.LOGIN:
        fields.setdefault("url", main_url)

    # URLs adicionais
    urls = overview.get("urls") or []
    additional = [u.get("url", "") for u in urls
                  if u.get("url") and u.get("url") != main_url]
    if additional and category == Category.LOGIN:
        fields["urls_additional"] = additional

    # --- sections ---
    for section in details.get("sections") or []:
        for sf in section.get("fields") or []:
            raw_title = (sf.get("title") or sf.get("id") or "").lower().strip()
            raw_value = _extract_field_value(sf.get("value"))
            if not raw_value:
                continue

            # TOTP detection
            if (sf.get("id") or "").upper().startswith("TOTP"):
                fields["otp"] = raw_value
                continue

            canonical_key = _SECTION_FIELD_MAP.get(raw_title)
            if canonical_key:
                fields.setdefault(canonical_key, raw_value)
            else:
                extras[raw_title] = raw_value

    # Notas
    notes = details.get("notesPlain") or ""

    # Para SECURE_NOTE, o corpo vai em fields["body"]
    if category == Category.SECURE_NOTE and notes:
        fields["body"] = notes
        notes = ""

    return CanonicalItem(
        category=category,
        title=title,
        fields=fields,
        favorite=favorite,
        trashed=trashed,
        tags=tags,
        folder=folder,
        created_at=created_at,
        updated_at=updated_at,
        sources=[source_ref],
        notes=notes,
        extras=extras,
    )


# ---------------------------------------------------------------------------
# Helpers exclusivos do leitor SQLite
# ---------------------------------------------------------------------------

def _find_sqlite_in_zip(zf: zipfile.ZipFile) -> str | None:
    """Retorna o nome do primeiro arquivo SQLite encontrado no ZIP, ou None.

    Detecta por extensão primeiro; se não encontrar, testa magic bytes para
    suportar zips cujos arquivos internos não têm extensão reconhecível.
    """
    for name in zf.namelist():
        if Path(name).suffix.lower() in _SQLITE_EXTENSIONS:
            return name
    for name in zf.namelist():
        try:
            with zf.open(name) as fh:
                if fh.read(16) == _SQLITE_MAGIC:
                    return name
        except Exception:
            continue
    return None


def _sqlite_field_value_dict(value: str | None, field_type: str | None) -> dict:
    """Reconstrói o dict de valor de campo compatível com _extract_field_value."""
    if not value:
        return {}
    ft = (field_type or "string").lower()
    return {ft: value}


def _sqlite_rows_to_raw(
    item_row: tuple,
    field_rows: list[tuple],
    tags: list[str],
) -> dict[str, Any]:
    """Converte linhas SQLite para o dict bruto esperado por _parse_item()."""
    uuid, category_uuid, created_at, updated_at, trashed, favorite, title, url, notes = item_row

    login_fields: list[dict] = []
    sections: dict[str, dict] = {}

    for section_name, field_id, field_title, field_value, field_type in field_rows:
        section_name_str = section_name or ""
        field_title_lower = (field_title or "").lower()

        if not section_name_str and field_title_lower in ("username", "password"):
            # Campo de designation (login direto)
            login_fields.append({
                "designation": field_title_lower,
                "value": field_value or "",
            })
        else:
            if section_name_str not in sections:
                sections[section_name_str] = {"title": section_name_str, "fields": []}
            fv = _sqlite_field_value_dict(field_value, field_type)
            sections[section_name_str]["fields"].append({
                "id": field_id or field_title or "",
                "title": field_title or "",
                "value": fv,
            })

    return {
        "uuid": uuid,
        "categoryUuid": category_uuid or "001",
        "createdAt": created_at,
        "updatedAt": updated_at,
        "trashed": "Y" if trashed else "N",
        "favorite": favorite or 0,
        "overview": {
            "title": title or "sem título",
            "url": url or "",
            "tags": tags,
        },
        "details": {
            "loginFields": login_fields,
            "notesPlain": notes or "",
            "sections": list(sections.values()),
        },
    }


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------

class OnePasswordImporter(Importer):
    """Lê exportações do 1Password a partir de arquivo SQLite.

    Formatos aceitos:
    - ``arquivo.sqlite`` / ``.db`` / ``.sqlite3`` — diretamente
    - ``arquivo.zip`` contendo um arquivo SQLite — detectado por extensão
      ou por magic bytes (suporta zips sem extensão no arquivo interno)
    """

    @property
    def source_name(self) -> str:
        return "1password"

    @property
    def supported_categories(self) -> set[Category]:
        return set(ONEPASSWORD_TO_CANONICAL.values())

    @property
    def supports_timestamps(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Leitores internos
    # ------------------------------------------------------------------

    def _parse_sqlite(self, db_path: Path) -> list[CanonicalItem]:
        """Lê itens de um arquivo SQLite do 1Password."""
        conn = sqlite3.connect(str(db_path))
        try:
            item_rows = conn.execute(
                "SELECT uuid, category_uuid, created_at, updated_at, "
                "trashed, favorite, title, url, notes FROM items"
            ).fetchall()

            items: list[CanonicalItem] = []
            for item_row in item_rows:
                uuid = item_row[0]

                field_rows = conn.execute(
                    "SELECT section_name, field_id, field_title, "
                    "field_value, field_type "
                    "FROM item_fields WHERE item_uuid = ?",
                    (uuid,),
                ).fetchall()

                tag_rows = conn.execute(
                    "SELECT tag FROM item_tags WHERE item_uuid = ?",
                    (uuid,),
                ).fetchall()
                tags = [t[0] for t in tag_rows]

                raw = _sqlite_rows_to_raw(item_row, list(field_rows), tags)
                item = _parse_item(raw)
                if item is not None:
                    items.append(item)

            return items
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Ponto de entrada público
    # ------------------------------------------------------------------

    def parse(self, path: Path) -> list[CanonicalItem]:
        # Arquivo SQLite direto (sem ZIP)
        if path.suffix.lower() in _SQLITE_EXTENSIONS:
            return self._parse_sqlite(path)

        # ZIP: busca SQLite por extensão ou magic bytes
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as zf:
                sqlite_name = _find_sqlite_in_zip(zf)
            if sqlite_name:
                with zipfile.ZipFile(path, "r") as zf:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        zf.extract(sqlite_name, path=tmpdir)
                        db_path = Path(tmpdir) / sqlite_name
                        return self._parse_sqlite(db_path)
            raise ValueError(
                f"Nenhum arquivo SQLite encontrado no ZIP: {path}. "
                "O arquivo interno deve ter extensão .sqlite/.db ou conter "
                "magic bytes SQLite."
            )

        raise ValueError(
            f"Formato não suportado: {path.suffix!r}. "
            "Esperado ZIP contendo arquivo SQLite ou arquivo .sqlite / .db direto."
        )

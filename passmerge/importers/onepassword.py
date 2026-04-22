"""Importer para o 1Password — formato ``.1pux``.

O arquivo ``.1pux`` é um ZIP contendo ``export.data`` (JSON). Exporte pelo app:
    Arquivo → Exportar → Todos os Vaults → formato 1PUX

Estrutura esperada de ``export.data``::

    {
      "accounts": [{
        "vaults": [{
          "items": [{
            "uuid": "...",
            "createdAt": 1234567890,
            "updatedAt": 1234567890,
            "categoryUuid": "001",
            "favorite": 0,
            "trashed": "N",
            "overview": {"title": "...", "url": "...", "tags": [...]},
            "details": {
              "loginFields": [
                {"value": "user@example.com", "designation": "username"},
                {"value": "secret",           "designation": "password"}
              ],
              "notesPlain": "...",
              "sections": [{
                "title": "...",
                "fields": [
                  {"title": "label", "value": {"totp": "..."}, "id": "TOTP_..."}
                ]
              }]
            }
          }]
        }]
      }]
    }
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category, SourceRef
from ..core.categories import ONEPASSWORD_TO_CANONICAL
from .base import Importer

_LOGIN_DESIGNATIONS = {"username", "password"}

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
    """Extrai valor de campo de section (pode ser dict tipado ou escalar)."""
    if isinstance(fv, dict):
        for key in ("string", "concealed", "url", "totp", "date", "monthYear",
                    "email", "phone", "gender", "menu", "cctype"):
            if key in fv:
                v = fv[key]
                return str(v) if v is not None else ""
        for v in fv.values():
            return str(v) if v is not None else ""
        return ""
    return str(fv) if fv is not None else ""


def _parse_item(raw: dict[str, Any]) -> CanonicalItem | None:
    """Converte um item bruto do export.data em CanonicalItem."""
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

    source_ref = SourceRef(source="1password", source_id=raw.get("uuid") or None)

    fields: dict[str, Any] = {}
    extras: dict[str, Any] = {}

    for lf in details.get("loginFields") or []:
        designation = (lf.get("designation") or "").lower()
        value = lf.get("value") or ""
        if designation in _LOGIN_DESIGNATIONS:
            fields[designation] = value
        elif designation:
            extras[f"loginField_{designation}"] = value

    main_url = overview.get("url") or ""
    if main_url and category == Category.LOGIN:
        fields.setdefault("url", main_url)

    urls = overview.get("urls") or []
    additional = [u.get("url", "") for u in urls
                  if u.get("url") and u.get("url") != main_url]
    if additional and category == Category.LOGIN:
        fields["urls_additional"] = additional

    for section in details.get("sections") or []:
        for sf in section.get("fields") or []:
            raw_title = (sf.get("title") or sf.get("id") or "").lower().strip()
            raw_value = _extract_field_value(sf.get("value"))
            if not raw_value:
                continue
            if (sf.get("id") or "").upper().startswith("TOTP"):
                fields["otp"] = raw_value
                continue
            canonical_key = _SECTION_FIELD_MAP.get(raw_title)
            if canonical_key:
                fields.setdefault(canonical_key, raw_value)
            else:
                extras[raw_title] = raw_value

    notes = details.get("notesPlain") or ""
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
        folder=None,
        created_at=created_at,
        updated_at=updated_at,
        sources=[source_ref],
        notes=notes,
        extras=extras,
    )


class OnePasswordImporter(Importer):
    """Lê exportações do 1Password no formato ``.1pux`` (ZIP com export.data JSON).

    Exporte pelo app: Arquivo → Exportar → Todos os Vaults → formato 1PUX.
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

    def parse(self, path: Path) -> list[CanonicalItem]:
        if not zipfile.is_zipfile(path):
            raise ValueError(
                f"Formato não suportado: {path.suffix!r}. "
                "Esperado arquivo .1pux exportado pelo 1Password."
            )
        with zipfile.ZipFile(path, "r") as zf:
            with zf.open("export.data") as fh:
                data = json.load(fh)

        items: list[CanonicalItem] = []
        for account in data.get("accounts") or []:
            for vault in account.get("vaults") or []:
                for raw_item in vault.get("items") or []:
                    item = _parse_item(raw_item)
                    if item is not None:
                        items.append(item)
        return items

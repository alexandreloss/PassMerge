"""Importer para o CSV exportado pelo NordPass.

Colunas esperadas (multi-categoria)::

    name,url,username,password,note,cardholder,cardnumber,cvc,expirydate,
    zipcode,folder,full_name,phone_number,email,address1,address2,city,
    country,state,type,note_date

A coluna ``type`` determina a categoria canônica via NORDPASS_TO_CANONICAL.
Se ``note_date`` estiver presente e não for vazio, usada como ``updated_at``.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category, SourceRef
from ..core.categories import NORDPASS_TO_CANONICAL
from .base import Importer


def _parse_date(raw: str) -> str | None:
    """Retorna a string de data como-está se não vazia, senão None."""
    if raw and raw.strip():
        return raw.strip()
    return None


class NordPassImporter(Importer):
    """Lê CSVs exportados pelo NordPass (todas as categorias)."""

    @property
    def source_name(self) -> str:
        return "nordpass"

    @property
    def supported_categories(self) -> set[Category]:
        return set(NORDPASS_TO_CANONICAL.values())

    @property
    def supports_timestamps(self) -> bool:
        return True  # campo note_date quando presente

    def parse(self, path: Path) -> list[CanonicalItem]:
        items: list[CanonicalItem] = []
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for idx, row in enumerate(reader):
                item = self._parse_row(row, idx)
                if item is not None:
                    items.append(item)
        return items

    def _parse_row(self, row: dict[str, str], idx: int) -> CanonicalItem | None:
        raw_type = (row.get("type") or "password").strip().lower()
        category = NORDPASS_TO_CANONICAL.get(raw_type, Category.OTHER)

        title = (row.get("name") or "").strip() or f"NordPass item {idx + 1}"
        updated_at = _parse_date(row.get("note_date", ""))

        source_ref = SourceRef(source="nordpass")
        fields: dict[str, Any] = {}

        if category == Category.LOGIN:
            fields["username"] = row.get("username") or ""
            fields["password"] = row.get("password") or ""
            fields["url"] = row.get("url") or ""

        elif category == Category.CREDIT_CARD:
            fields["cardholder"] = row.get("cardholder") or ""
            fields["number"] = row.get("cardnumber") or ""
            fields["cvv"] = row.get("cvc") or ""
            fields["expiration"] = row.get("expirydate") or ""
            fields["zip"] = row.get("zipcode") or ""

        elif category == Category.IDENTITY:
            fields["first_name"] = row.get("full_name") or ""
            fields["email"] = row.get("email") or ""
            fields["phone"] = row.get("phone_number") or ""
            fields["address1"] = row.get("address1") or ""
            fields["address2"] = row.get("address2") or ""
            fields["city"] = row.get("city") or ""
            fields["state"] = row.get("state") or ""
            fields["country"] = row.get("country") or ""

        elif category == Category.SECURE_NOTE:
            fields["body"] = row.get("note") or ""

        notes = row.get("note") or ""
        if category != Category.SECURE_NOTE:
            # para categorias que não são note, 'note' vai como notes do item
            pass
        else:
            notes = ""  # já em fields["body"]

        folder: str | None = (row.get("folder") or "").strip() or None

        return CanonicalItem(
            category=category,
            title=title,
            fields=fields,
            folder=folder,
            updated_at=updated_at,
            sources=[source_ref],
            notes=notes if category != Category.SECURE_NOTE else "",
        )

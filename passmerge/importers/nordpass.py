"""Importer para o CSV exportado pelo NordPass.

Suporta dois layouts:

Export do NordPass (colunas com ``type`` e ``note_date``)::

    name,url,username,password,note,cardholder,cardnumber,cvc,expirydate,
    zipcode,folder,full_name,phone_number,email,address1,address2,city,
    country,state,type,note_date

Template oficial de import do NordPass (sem ``type``/``note_date``)::

    name,url,username,password,note,cardholdername,cardnumber,cvc,expirydate,
    zipcode,folder,full_name,phone_number,email,address1,address2,city,
    country,state,totp,shared_folder

Quando ``type`` está ausente ou vazio, a categoria é inferida pelo conteúdo:
    cardnumber preenchido → CREDIT_CARD
    full_name preenchido  → IDENTITY
    username e password vazios, note preenchido → SECURE_NOTE
    demais casos          → LOGIN
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category, SourceRef
from ..core.categories import NORDPASS_TO_CANONICAL
from .base import Importer


def _parse_date(raw: str) -> str | None:
    if raw and raw.strip():
        return raw.strip()
    return None


def _infer_category(row: dict[str, str]) -> Category:
    """Infere categoria pelo conteúdo quando a coluna ``type`` está ausente."""
    if row.get("cardnumber") or row.get("cvc") or row.get("expirydate"):
        return Category.CREDIT_CARD
    if row.get("full_name") and not (row.get("username") or row.get("password")):
        return Category.IDENTITY
    if row.get("note") and not row.get("username") and not row.get("password"):
        return Category.SECURE_NOTE
    return Category.LOGIN


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
        raw_type = (row.get("type") or "").strip().lower()
        if raw_type:
            category = NORDPASS_TO_CANONICAL.get(raw_type, Category.OTHER)
        else:
            category = _infer_category(row)

        title = (row.get("name") or "").strip() or f"NordPass item {idx + 1}"
        updated_at = _parse_date(row.get("note_date") or "")

        source_ref = SourceRef(source="nordpass")
        fields: dict[str, Any] = {}

        if category == Category.LOGIN:
            fields["username"] = row.get("username") or ""
            fields["password"] = row.get("password") or ""
            fields["url"] = row.get("url") or ""
            if row.get("totp"):
                fields["otp"] = row["totp"]

        elif category == Category.CREDIT_CARD:
            # aceita tanto "cardholdername" (template oficial) como "cardholder" (export legado)
            fields["cardholder"] = row.get("cardholdername") or row.get("cardholder") or ""
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

        folder: str | None = (row.get("folder") or "").strip() or None
        notes = "" if category == Category.SECURE_NOTE else (row.get("note") or "")

        return CanonicalItem(
            category=category,
            title=title,
            fields=fields,
            folder=folder,
            updated_at=updated_at,
            sources=[source_ref],
            notes=notes,
        )

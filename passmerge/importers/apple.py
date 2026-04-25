"""Importer para o CSV exportado pelo Apple Passwords (iPhone/macOS).

Formato: CSV com 6 colunas fixas::

    Title,URL,Username,Password,Notes,OTPAuth

Suporta apenas Category.LOGIN. Sem timestamps.
A coluna OTPAuth contém URIs no formato ``otpauth://totp/...`` quando presente.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category, SourceRef
from .base import Importer


class ApplePasswordsImporter(Importer):
    """Lê CSVs exportados pelo Apple Passwords (iPhone / macOS Sequoia+)."""

    @property
    def source_name(self) -> str:
        return "applesenhas"

    @property
    def supported_categories(self) -> set[Category]:
        return {Category.LOGIN}

    @property
    def supports_timestamps(self) -> bool:
        return False

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
        title = (row.get("Title") or "").strip() or f"Apple item {idx + 1}"
        fields: dict[str, Any] = {
            "username": row.get("Username") or "",
            "password": row.get("Password") or "",
            "url":      row.get("URL") or "",
        }
        otp = (row.get("OTPAuth") or "").strip()
        if otp:
            fields["otp"] = otp
        notes = (row.get("Notes") or "").strip()
        return CanonicalItem(
            category=Category.LOGIN,
            title=title,
            fields=fields,
            sources=[SourceRef(source="applesenhas")],
            notes=notes,
        )

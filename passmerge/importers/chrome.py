"""Importer para o CSV exportado pelo Google Chrome / Google Password Manager.

Formato: CSV com 5 colunas fixas::

    name,url,username,password,note

Suporta apenas Category.LOGIN. Sem timestamps.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category, SourceRef
from .base import Importer


class ChromeImporter(Importer):
    """Lê CSVs exportados pelo Google Chrome (Google Password Manager)."""

    @property
    def source_name(self) -> str:
        return "chrome"

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
        title = (row.get("name") or "").strip() or f"Chrome item {idx + 1}"
        fields: dict[str, Any] = {
            "username": row.get("username") or "",
            "password": row.get("password") or "",
            "url": row.get("url") or "",
        }
        notes = (row.get("note") or "").strip()
        source_ref = SourceRef(source="chrome")
        return CanonicalItem(
            category=Category.LOGIN,
            title=title,
            fields=fields,
            sources=[source_ref],
            notes=notes,
        )

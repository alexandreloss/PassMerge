"""Exporter para o formato CSV do NordPass."""
from __future__ import annotations

import csv
from pathlib import Path

from ..core.canonical import CanonicalItem, Category
from ..core.categories import CANONICAL_TO_NORDPASS
from .base import ExportReport, Exporter

_COLUMNS = [
    "name", "url", "username", "password", "note",
    "cardholder", "cardnumber", "cvc", "expirydate", "zipcode",
    "folder", "full_name", "phone_number", "email",
    "address1", "address2", "city", "country", "state", "type",
]


def _row_for(item: CanonicalItem) -> dict[str, str]:
    f = item.fields
    base: dict[str, str] = {
        "name": item.title,
        "folder": item.folder or "",
        "type": CANONICAL_TO_NORDPASS.get(item.category, ""),
    }

    if item.category == Category.LOGIN:
        base["url"] = f.get("url") or ""
        base["username"] = f.get("username") or ""
        base["password"] = f.get("password") or ""
        base["note"] = item.notes or ""

    elif item.category == Category.CREDIT_CARD:
        base["cardholder"] = f.get("cardholder") or ""
        base["cardnumber"] = f.get("number") or ""
        base["cvc"] = f.get("cvv") or ""
        base["expirydate"] = f.get("expiration") or ""
        base["zipcode"] = f.get("zip") or ""
        base["note"] = item.notes or ""

    elif item.category == Category.SECURE_NOTE:
        base["note"] = f.get("body") or ""

    elif item.category == Category.IDENTITY:
        base["full_name"] = f.get("first_name") or ""
        base["email"] = f.get("email") or ""
        base["phone_number"] = f.get("phone") or ""
        base["address1"] = f.get("address1") or ""
        base["address2"] = f.get("address2") or ""
        base["city"] = f.get("city") or ""
        base["state"] = f.get("state") or ""
        base["country"] = f.get("country") or ""

    return base


class NordPassExporter(Exporter):
    target_name = "nordpass"
    supported_categories = set(CANONICAL_TO_NORDPASS.keys())

    def export(self, items: list[CanonicalItem], out_path: Path) -> ExportReport:
        report = ExportReport(target=self.target_name)

        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=_COLUMNS,
                extrasaction="ignore", quoting=csv.QUOTE_ALL,
            )
            writer.writeheader()
            for item in items:
                if item.category not in self.supported_categories:
                    report.skip(item, "unsupported_category")
                    continue
                row = _row_for(item)
                # Fill missing columns with empty string
                for col in _COLUMNS:
                    row.setdefault(col, "")
                writer.writerow(row)
                report.exported_count += 1

        return report

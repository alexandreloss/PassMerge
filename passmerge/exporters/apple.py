"""Exporter para o formato CSV do Apple Passwords (iPhone/macOS)."""
from __future__ import annotations

import csv
from pathlib import Path

from ..core.canonical import CanonicalItem, Category
from .base import ExportReport, Exporter

_COLUMNS = ["Title", "URL", "Username", "Password", "Notes", "OTPAuth"]


class ApplePasswordsExporter(Exporter):
    target_name = "applesenhas"
    supported_categories = {Category.LOGIN}

    def export(self, items: list[CanonicalItem], out_path: Path) -> ExportReport:
        report = ExportReport(target=self.target_name)

        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
            writer.writerow(_COLUMNS)
            for item in items:
                if item.category not in self.supported_categories:
                    report.skip(item, "unsupported_category")
                    continue
                writer.writerow([
                    item.title,
                    item.fields.get("url") or "",
                    item.fields.get("username") or "",
                    item.fields.get("password") or "",
                    item.notes or "",
                    item.fields.get("otp") or "",
                ])
                report.exported_count += 1

        return report

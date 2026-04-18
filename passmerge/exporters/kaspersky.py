"""Exporter para o formato TXT proprietário do Kaspersky Password Manager."""
from __future__ import annotations

from pathlib import Path

from ..core.canonical import CanonicalItem, Category
from ..core.categories import CANONICAL_TO_KASPERSKY_BLOCK
from .base import ExportReport, Exporter


def _login_block(item: CanonicalItem) -> str:
    f = item.fields
    lines = [
        f"Website name: {item.title}",
        f"Website URL: {f.get('url') or ''}",
        f"Login name: {f.get('username') or ''}",
        f"Login: {f.get('username') or ''}",
        f"Password: {f.get('password') or ''}",
        f"Comment: {item.notes or ''}",
    ]
    return "\n".join(lines)


def _note_block(item: CanonicalItem) -> str:
    body = item.fields.get("body") or item.notes or ""
    return f"Note name: {item.title}\nNote text: {body}"


class KasperskyExporter(Exporter):
    target_name = "kaspersky"
    supported_categories = set(CANONICAL_TO_KASPERSKY_BLOCK.keys())

    def export(self, items: list[CanonicalItem], out_path: Path) -> ExportReport:
        report = ExportReport(target=self.target_name)

        logins = [i for i in items if i.category == Category.LOGIN]
        notes  = [i for i in items if i.category == Category.SECURE_NOTE]
        for item in items:
            if item.category not in self.supported_categories:
                report.skip(item, "unsupported_category")

        sections: list[str] = []

        if logins:
            entries = [_login_block(i) for i in logins]
            block = "Websites\n\n" + "\n\n---\n\n".join(entries) + "\n\n---"
            sections.append(block)
            report.exported_count += len(logins)

        if notes:
            entries = [_note_block(i) for i in notes]
            block = "Notes\n\n" + "\n\n---\n\n".join(entries) + "\n\n---"
            sections.append(block)
            report.exported_count += len(notes)

        out_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
        return report

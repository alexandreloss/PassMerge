"""Interface abstrata para exporters do PassMerge."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..core.canonical import CanonicalItem, Category


@dataclass
class ExportReport:
    target: str
    exported_count: int = 0
    skipped_items: list[dict] = field(default_factory=list)
    truncated_fields: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def skip(self, item: CanonicalItem, reason: str) -> None:
        self.skipped_items.append({
            "id": item.id,
            "title": item.title,
            "category": item.category.value,
            "reason": reason,
        })

    def truncate(self, item: CanonicalItem, field_name: str,
                 original_len: int, max_len: int) -> None:
        self.truncated_fields.append({
            "id": item.id,
            "title": item.title,
            "field": field_name,
            "original_len": original_len,
            "max_len": max_len,
        })


class Exporter(ABC):
    target_name: str
    supported_categories: set[Category]

    @abstractmethod
    def export(self, items: list[CanonicalItem], out_path: Path) -> ExportReport: ...

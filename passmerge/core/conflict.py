"""Log de conflitos que requerem revisão manual — Fase 3.

AVISO DE SEGURANÇA: este arquivo contém senhas e campos sensíveis em texto
claro. Trate o arquivo .conflicts.json gerado como dado sigiloso.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ReviewConflict:
    """Conflito que o merger não pôde resolver automaticamente."""
    conflict_id: str
    item_title: str
    category: str
    conflicting_fields: list[str]
    versions: list[dict]   # [{source, updated_at, fields: {todos os campos}}]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConflictLog:
    _entries: list[ReviewConflict] = field(default_factory=list)

    def add(self, entry: ReviewConflict) -> None:
        self._entries.append(entry)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def to_json(self) -> str:
        return json.dumps(
            [e.to_dict() for e in self._entries],
            ensure_ascii=False,
            indent=2,
        )

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    def summary(self) -> dict[str, int]:
        return {"requires_review": len(self._entries)}

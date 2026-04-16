"""Classe abstrata base para todos os importers do PassMerge."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..core.canonical import CanonicalItem, Category


class Importer(ABC):
    """Interface comum para parsear arquivos exportados de gerenciadores de senha.

    Cada importer concreto deve implementar `parse()` e as três propriedades
    abstratas. O método `parse()` retorna uma lista de `CanonicalItem` com
    `sources` já preenchido.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identificador curto da fonte: 'chrome', 'nordpass', '1password', 'kaspersky'."""

    @property
    @abstractmethod
    def supported_categories(self) -> set[Category]:
        """Conjunto de categorias que este importer pode produzir."""

    @property
    @abstractmethod
    def supports_timestamps(self) -> bool:
        """True se o formato de origem contém timestamps utilizáveis."""

    @abstractmethod
    def parse(self, path: Path) -> list[CanonicalItem]:
        """Lê o arquivo em *path* e retorna itens canônicos.

        Cada item deve ter pelo menos um `SourceRef` em `item.sources`
        com `source == self.source_name`.
        """

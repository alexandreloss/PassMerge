"""Importer para o formato TXT proprietário do Kaspersky Password Manager.

Formato real do arquivo exportado::

    Websites

    Website name: github.com
    Website URL: https://github.com/login
    Login name:
    Login: user@example.com
    Password: secret
    Comment:

    ---

    Website name: another.com
    ...

    ---

    Applications

    Application name: VPN Client
    Login name:
    Login: vpnuser
    Password: vpnpass
    Comment:

    ---

    Notes

    Note name: My Note
    Note text: Some content

    ---

Regras de parsing:
- Cabeçalho de seção: linha contendo apenas o nome da seção (sem dois-pontos).
- Separador de entradas: linha contendo apenas `---`.
- Campos: `Rótulo: valor` (split no primeiro dois-pontos).
- Linhas em branco são ignoradas.

Mapeamento:
    Websites, Applications → Category.LOGIN
    Notes → Category.SECURE_NOTE
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category, SourceRef
from ..core.categories import KASPERSKY_BLOCK_TO_CANONICAL
from .base import Importer

# Chave de título por seção
_SECTION_TITLE_KEY: dict[str, str] = {
    "Websites": "website name",
    "Applications": "application name",
    "Notes": "note name",
}

# Chave de URL por seção (Applications não têm URL)
_SECTION_URL_KEY: dict[str, str] = {
    "Websites": "website url",
}


def _strip_bom(line: str) -> str:
    return line.lstrip("\ufeff")


class KasperskyImporter(Importer):
    """Lê arquivos TXT exportados pelo Kaspersky Password Manager."""

    @property
    def source_name(self) -> str:
        return "kaspersky"

    @property
    def supported_categories(self) -> set[Category]:
        return set(KASPERSKY_BLOCK_TO_CANONICAL.values())

    @property
    def supports_timestamps(self) -> bool:
        return False

    def parse(self, path: Path) -> list[CanonicalItem]:
        text = path.read_text(encoding="utf-8-sig")
        lines = text.splitlines()
        return self._parse_lines(lines)

    def _parse_lines(self, lines: list[str]) -> list[CanonicalItem]:
        items: list[CanonicalItem] = []
        current_block: str | None = None
        current_entry: dict[str, str] = {}

        def _flush() -> None:
            nonlocal current_entry
            if current_block and current_entry:
                item = _make_item(current_block, current_entry)
                if item is not None:
                    items.append(item)
            current_entry = {}

        for raw_line in lines:
            line = _strip_bom(raw_line)
            stripped = line.strip()

            # Linha em branco: ignorar
            if not stripped:
                continue

            # Separador de entradas
            if stripped == "---":
                _flush()
                continue

            # Cabeçalho de seção: sem dois-pontos, nome conhecido
            if ":" not in stripped and stripped in KASPERSKY_BLOCK_TO_CANONICAL:
                _flush()
                current_block = stripped
                continue

            # Campo: "Rótulo: valor" (split no primeiro dois-pontos)
            if current_block and ":" in line:
                colon_pos = line.index(":")
                label = line[:colon_pos].strip()
                value = line[colon_pos + 1:].strip()
                if label:
                    current_entry[label.lower()] = value

        # Última entrada sem separador final
        _flush()

        return items


def _make_item(block: str, raw: dict[str, str]) -> CanonicalItem | None:
    category = KASPERSKY_BLOCK_TO_CANONICAL.get(block, Category.OTHER)

    # Título: chave específica da seção
    title_key = _SECTION_TITLE_KEY.get(block, "name")
    title = raw.get(title_key, "").strip()
    if not title:
        # Fallback genérico
        title = (
            raw.get("website name") or raw.get("application name")
            or raw.get("note name") or raw.get("name") or ""
        ).strip()
    if not title:
        title = f"Kaspersky {block} item"

    fields: dict[str, Any] = {}
    notes = ""

    if category == Category.LOGIN:
        # Preferir "login" sobre "login name" (display name)
        username = raw.get("login") or raw.get("login name") or ""
        fields["username"] = username
        fields["password"] = raw.get("password") or ""
        url_key = _SECTION_URL_KEY.get(block, "")
        fields["url"] = raw.get(url_key, "") if url_key else ""
        notes = raw.get("comment") or ""

    elif category == Category.SECURE_NOTE:
        # Preferir "note text" sobre "comment"
        body = raw.get("note text") or raw.get("comment") or ""
        fields["body"] = body

    else:
        for k, v in raw.items():
            if k not in {title_key, "name"} and v:
                fields[k] = v

    return CanonicalItem(
        category=category,
        title=title,
        fields=fields,
        sources=[SourceRef(source="kaspersky")],
        notes=notes,
    )

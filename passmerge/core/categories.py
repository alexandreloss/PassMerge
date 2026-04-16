"""Mapeamento de categorias entre plataformas.

Fonte canônica para os adaptadores das fases F2/F4. Um importer consulta
FROM_NATIVE para traduzir o tipo nativo para Category; um exporter consulta
TO_NATIVE para obter o identificador usado pelo formato de destino.

Quando a plataforma não suporta uma categoria, o exporter decide a política
(omitir, converter para SECURE_NOTE equivalente, ou salvar em arquivo
auxiliar .unsupported.json).
"""
from __future__ import annotations

from .canonical import Category

# 1Password: códigos internos conhecidos (templateUuid no .1pux)
ONEPASSWORD_TO_CANONICAL: dict[str, Category] = {
    "001": Category.LOGIN,
    "002": Category.CREDIT_CARD,
    "003": Category.SECURE_NOTE,
    "004": Category.IDENTITY,
    "005": Category.SOFTWARE_LICENSE,
    "100": Category.SOFTWARE_LICENSE,   # software license
    "101": Category.LOGIN,              # bank account -> tratado como login
    "102": Category.DATABASE,
    "106": Category.IDENTITY,           # passport
    "110": Category.SERVER,
    "111": Category.WIRELESS,
    "112": Category.LOGIN,              # API credential
}

CANONICAL_TO_ONEPASSWORD: dict[Category, str] = {
    Category.LOGIN: "001",
    Category.CREDIT_CARD: "002",
    Category.SECURE_NOTE: "003",
    Category.IDENTITY: "004",
    Category.SOFTWARE_LICENSE: "100",
    Category.DATABASE: "102",
    Category.SERVER: "110",
    Category.WIRELESS: "111",
    Category.OTHER: "003",              # fallback: secure note
}

# NordPass: valores do campo `type` no CSV
NORDPASS_TO_CANONICAL: dict[str, Category] = {
    "password": Category.LOGIN,
    "login": Category.LOGIN,
    "credit_card": Category.CREDIT_CARD,
    "note": Category.SECURE_NOTE,
    "secure_note": Category.SECURE_NOTE,
    "identity": Category.IDENTITY,
    "personal_info": Category.IDENTITY,
}

CANONICAL_TO_NORDPASS: dict[Category, str] = {
    Category.LOGIN: "password",
    Category.CREDIT_CARD: "credit_card",
    Category.SECURE_NOTE: "note",
    Category.IDENTITY: "identity",
    # Demais categorias não suportadas pelo NordPass
}

# Chrome/Google: apenas logins
CHROME_SUPPORTS: set[Category] = {Category.LOGIN}

# Kaspersky: blocos do TXT
KASPERSKY_BLOCK_TO_CANONICAL: dict[str, Category] = {
    "Websites": Category.LOGIN,
    "Applications": Category.LOGIN,
    "Notes": Category.SECURE_NOTE,
}

CANONICAL_TO_KASPERSKY_BLOCK: dict[Category, str] = {
    Category.LOGIN: "Websites",
    Category.SECURE_NOTE: "Notes",
}


def target_supports(target: str, category: Category) -> bool:
    """Verifica se o formato de destino suporta a categoria."""
    if target == "onepassword":
        return category in CANONICAL_TO_ONEPASSWORD
    if target == "nordpass":
        return category in CANONICAL_TO_NORDPASS
    if target == "chrome":
        return category in CHROME_SUPPORTS
    if target == "kaspersky":
        return category in CANONICAL_TO_KASPERSKY_BLOCK
    raise ValueError(f"target desconhecido: {target}")

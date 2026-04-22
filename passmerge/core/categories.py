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

# 1Password: categoryUuid → Category canônica
ONEPASSWORD_TO_CANONICAL: dict[str, Category] = {
    "001": Category.LOGIN,             # Login
    "002": Category.CREDIT_CARD,       # Credit Card
    "003": Category.SECURE_NOTE,       # Secure Note
    "004": Category.IDENTITY,          # Identity
    "005": Category.PASSWORD,          # Password (autônoma, sem campo de usuário)
    "110": Category.SERVER,            # Server
    "111": Category.SOFTWARE_LICENSE,  # Software License
    "112": Category.BANK_ACCOUNT,      # Bank Account
    "113": Category.DATABASE,          # Database
    "114": Category.DRIVER_LICENCE,    # Driver License
    "115": Category.OUTDOOR_LICENSE,   # Outdoor License
    "116": Category.MEMBERSHIP,        # Membership
    "117": Category.PASSPORT,          # Passport
    "118": Category.REWARD_PROGRAM,    # Reward Program
    "119": Category.SSN,               # Social Security Number
    "120": Category.WIRELESS,          # Wireless Router
    "121": Category.EMAIL_ACCOUNT,     # Email Account
    "122": Category.API_CREDENTIAL,    # API Credential
    "123": Category.MEDICAL_RECORD,    # Medical Record
    "124": Category.CRYPTO_WALLET,     # Crypto Wallet
    "125": Category.DOCUMENT           # Document
}

CANONICAL_TO_ONEPASSWORD: dict[Category, str] = {
    Category.LOGIN:            "001",
    Category.CREDIT_CARD:      "002",
    Category.SECURE_NOTE:      "003",
    Category.IDENTITY:         "004",
    Category.SERVER:           "110",
    Category.SOFTWARE_LICENSE: "111",
    Category.DATABASE:         "113",
    Category.WIRELESS:         "120",
    Category.OTHER:            "003",  # fallback: secure note
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

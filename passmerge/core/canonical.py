"""Modelo de dados canônico do PassMerge.

Schema JSON unificado para representar itens de qualquer gerenciador.
Baseado em 1PUX pela sua riqueza; preserva metadados de rastreabilidade
(sources, timestamps) e campos não mapeados (extras).

Uso:
    >>> item = CanonicalItem(category=Category.LOGIN, title="GitHub",
    ...                       fields={"username": "a", "password": "b"})
    >>> vault = Vault(items=[item])
    >>> vault.to_json()  # serialização para JSON
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "1.0"


class Category(str, Enum):
    """Categorias canônicas suportadas (ver seção 4 da arquitetura)."""
    LOGIN            = "login"
    CREDIT_CARD      = "credit_card"
    SERVER           = "server"
    SECURE_NOTE      = "secure_note"
    IDENTITY         = "identity"
    SOFTWARE_LICENSE = "software_license"
    DATABASE         = "database"
    WIRELESS         = "wireless"
    # Categorias adicionais mapeadas do 1Password
    PASSWORD         = "password"
    BANK_ACCOUNT     = "bank_account"
    DRIVER_LICENCE   = "driver_licence"
    OUTDOOR_LICENSE  = "outdoor_license"
    MEMBERSHIP       = "membership"
    PASSPORT         = "passport"
    REWARD_PROGRAM   = "reward_program"
    SSN              = "ssn"
    EMAIL_ACCOUNT    = "email_account"
    API_CREDENTIAL   = "api_credential"
    MEDICAL_RECORD   = "medical_record"
    CRYPTO_WALLET    = "crypto_wallet"
    DOCUMENT         = "document"
    OTHER            = "other"


# Campos esperados por categoria (validação leve na Fase 1; estrita na F3).
CATEGORY_FIELDS: dict[Category, set[str]] = {
    Category.LOGIN:            {"username", "password", "url", "otp", "urls_additional", "pin"},
    Category.CREDIT_CARD:      {"cardholder", "number", "cvv", "expiration", "brand", "pin", "zip"},
    Category.SERVER:           {"hostname", "port", "username", "password", "private_key", "key_passphrase"},
    Category.SECURE_NOTE:      {"body"},
    Category.IDENTITY:         {"first_name", "last_name", "email", "phone",
                                "address1", "address2", "city", "state", "country", "zip", "birth_date"},
    Category.SOFTWARE_LICENSE: {"product", "version", "license_key", "licensed_to", "purchase_date"},
    Category.DATABASE:         {"hostname", "port", "database", "username", "password", "type"},
    Category.WIRELESS:         {"ssid", "password", "security_type"},
    Category.PASSWORD:         {"password"},
    Category.BANK_ACCOUNT:     {"account_number", "routing_number", "bank_name", "username", "password", "pin"},
    Category.DRIVER_LICENCE:   {"number", "full_name", "expiration", "state", "country"},
    Category.OUTDOOR_LICENSE:  {"number", "full_name", "expiration", "state"},
    Category.MEMBERSHIP:       {"member_id", "organization", "expiration"},
    Category.PASSPORT:         {"number", "full_name", "expiration", "country", "birth_date"},
    Category.REWARD_PROGRAM:   {"member_id", "organization", "username", "password"},
    Category.SSN:              {"number", "full_name"},
    Category.EMAIL_ACCOUNT:    {"username", "password", "smtp_server", "smtp_port", "imap_server", "imap_port"},
    Category.API_CREDENTIAL:   {"username", "password", "hostname", "credential"},
    Category.MEDICAL_RECORD:   {"patient_name", "date", "notes"},
    Category.CRYPTO_WALLET:    {"wallet_address", "private_key", "seed_phrase"},
    Category.DOCUMENT:         {"body"},
    Category.OTHER:            set(),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class SourceRef:
    """Rastreia de qual gerenciador o item (ou sub-registro) veio."""
    source: str                # "1password" | "chrome" | "nordpass" | "kaspersky"
    source_id: Optional[str] = None
    imported_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CanonicalItem:
    """Um registro unificado de credencial."""
    category: Category
    title: str
    fields: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_uuid)
    favorite: bool = False
    trashed: bool = False
    tags: list[str] = field(default_factory=list)
    folder: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    sources: list[SourceRef] = field(default_factory=list)
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "favorite": self.favorite,
            "trashed": self.trashed,
            "tags": list(self.tags),
            "folder": self.folder,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sources": [s.to_dict() for s in self.sources],
            "fields": dict(self.fields),
            "notes": self.notes,
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CanonicalItem":
        return cls(
            id=data.get("id", _new_uuid()),
            category=Category(data["category"]),
            title=data["title"],
            favorite=data.get("favorite", False),
            trashed=data.get("trashed", False),
            tags=list(data.get("tags") or []),
            folder=data.get("folder"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            sources=[SourceRef(**s) for s in data.get("sources", [])],
            fields=dict(data.get("fields") or {}),
            notes=data.get("notes", ""),
            extras=dict(data.get("extras") or {}),
        )

    def validate(self) -> list[str]:
        """Retorna lista de problemas; vazio = válido."""
        errors: list[str] = []
        if not self.title.strip():
            errors.append("title vazio")
        if not isinstance(self.category, Category):
            errors.append(f"category inválida: {self.category!r}")
        expected = CATEGORY_FIELDS.get(self.category, set())
        unknown = set(self.fields.keys()) - expected
        if expected and unknown:
            # não é erro fatal — campos desconhecidos vão para extras em normalização
            # mas alertamos
            errors.append(f"campos não esperados para {self.category.value}: {sorted(unknown)}")
        return errors


@dataclass
class SourceFileRef:
    """Metadados dos arquivos de entrada consumidos."""
    source: str
    path: str
    sha256: str
    item_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Vault:
    """Container raiz do schema canônico.

    Representa o arquivo unificado antes de criptografar.
    """
    items: list[CanonicalItem] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    source_files: list[SourceFileRef] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    generated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "items": [i.to_dict() for i in self.items],
            "conflicts": list(self.conflicts),
            "source_files": [s.to_dict() for s in self.source_files],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_bytes(self) -> bytes:
        """Serialização canônica UTF-8 (para criptografia)."""
        return self.to_json(indent=None).encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Vault":
        version = data.get("schema_version", "0.0")
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Versão de schema incompatível: arquivo={version} esperado={SCHEMA_VERSION}"
            )
        return cls(
            schema_version=version,
            generated_at=data.get("generated_at", _utc_now()),
            items=[CanonicalItem.from_dict(i) for i in data.get("items", [])],
            conflicts=list(data.get("conflicts") or []),
            source_files=[SourceFileRef(**s) for s in data.get("source_files", [])],
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "Vault":
        return cls.from_dict(json.loads(data.decode("utf-8")))

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version inesperado: {self.schema_version}")
        seen_ids: set[str] = set()
        for idx, item in enumerate(self.items):
            if item.id in seen_ids:
                errors.append(f"item[{idx}]: ID duplicado {item.id}")
            seen_ids.add(item.id)
            for err in item.validate():
                errors.append(f"item[{idx}] ({item.title}): {err}")
        return errors

    def summary(self) -> dict[str, int]:
        """Contagem por categoria."""
        counts: dict[str, int] = {}
        for item in self.items:
            key = item.category.value
            counts[key] = counts.get(key, 0) + 1
        counts["_total"] = len(self.items)
        counts["_conflicts"] = len(self.conflicts)
        return counts


def empty_vault() -> Vault:
    """Cria um vault vazio (usado pelo comando `init`)."""
    return Vault()

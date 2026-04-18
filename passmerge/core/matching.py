"""Chaves de deduplicação para o merger da Fase 3.

Cada categoria tem uma chave primária canônica que agrupa itens duplicados
vindos de diferentes fontes. A função `primary_key` retorna uma string
hashável; itens com mesmo `(category, primary_key)` são candidatos a merge.

Regras de normalização:
- Sempre lowercase + strip + collapse de espaços internos.
- Campos ausentes contribuem com string vazia (nunca None).
- URLs: extrair só o netloc (domínio) via `normalize_url`.
"""
from __future__ import annotations

import hashlib
import re

from .canonical import CanonicalItem, Category
from .normalize import normalize_url

_WS = re.compile(r"\s+")


def _norm(value: str | None) -> str:
    """Lowercase + strip + colapsa espaços internos."""
    if not value:
        return ""
    return _WS.sub(" ", str(value).strip().lower())


def _domain(url: str | None) -> str:
    """Extrai o netloc normalizado de uma URL."""
    if not url:
        return ""
    normalized = normalize_url(url)
    # normalize_url devolve URL completa; extraímos só o netloc
    from urllib.parse import urlparse
    try:
        return urlparse(normalized).netloc.lower().lstrip("www.") or _norm(url)
    except Exception:
        return _norm(url)


def _sha256_prefix(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def primary_key(item: CanonicalItem) -> str:
    """Retorna a chave primária canônica do item.

    A chave é prefixada pela categoria para garantir que itens de
    categorias diferentes nunca colidam mesmo que os campos coincidam.
    """
    f = item.fields
    cat = item.category

    if cat == Category.LOGIN:
        domain = _domain(f.get("url") or "")
        username = _norm(f.get("username") or "")
        return f"login|{domain}|{username}"

    if cat == Category.CREDIT_CARD:
        raw_number = _norm(f.get("number") or "")
        last4 = raw_number[-4:] if len(raw_number) >= 4 else raw_number
        cardholder = _norm(f.get("cardholder") or "")
        return f"cc|{last4}|{cardholder}"

    if cat == Category.SERVER:
        host = _norm(f.get("hostname") or "")
        user = _norm(f.get("username") or "")
        port = _norm(f.get("port") or "")
        return f"server|{host}|{user}|{port}"

    if cat == Category.SECURE_NOTE:
        title = _norm(item.title)
        body_hash = _sha256_prefix((f.get("body") or "")[:256])
        return f"note|{title}|{body_hash}"

    if cat == Category.IDENTITY:
        email = _norm(f.get("email") or "")
        if email:
            return f"identity|email|{email}"
        first = _norm(f.get("first_name") or "")
        last = _norm(f.get("last_name") or "")
        phone = _norm(f.get("phone") or "")
        return f"identity|name|{first}|{last}|{phone}"

    if cat == Category.SOFTWARE_LICENSE:
        product = _norm(f.get("product") or "")
        key = _norm(f.get("license_key") or "")
        return f"license|{product}|{key}"

    if cat == Category.DATABASE:
        host = _norm(f.get("hostname") or "")
        db = _norm(f.get("database") or "")
        user = _norm(f.get("username") or "")
        return f"db|{host}|{db}|{user}"

    if cat == Category.WIRELESS:
        ssid = _norm(f.get("ssid") or "")
        return f"wifi|{ssid}"

    # OTHER e fallback
    return f"other|{_norm(item.title)}"

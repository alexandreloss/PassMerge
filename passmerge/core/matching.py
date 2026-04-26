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

_WS = re.compile(r"\s+")


def _norm(value: str | None) -> str:
    """Lowercase + strip + colapsa espaços internos."""
    if not value:
        return ""
    return _WS.sub(" ", str(value).strip().lower())


def _origin(url: str | None) -> str:
    """Extrai o origin normalizado (scheme://netloc) de uma URL.

    Normalização aplicada:
      - scheme e netloc convertidos para minúsculas
      - prefixo "www." removido do netloc (https://www.aa.com == https://aa.com)
      - path, query e fragmento descartados

    Exemplos:
      https://prd-aa1.lg.com.br/Autoatendimento/index.html?id=1  →  https://prd-aa1.lg.com.br
      https://www.aa.com/homePage.do                              →  https://aa.com
      http://visabenefits.force.com/webportal/                    →  http://visabenefits.force.com
    """
    if not url or not url.strip():
        return ""
    raw = url.strip()
    if "://" not in raw:
        raw = "https://" + raw
    try:
        from urllib.parse import urlparse
        parts = urlparse(raw)
        netloc = parts.netloc.lower()
        if not netloc:
            return _norm(url)
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return f"{parts.scheme.lower()}://{netloc}"
    except Exception:
        return _norm(url)


def _sha256_prefix(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _f(item: CanonicalItem, field_key: str, *extra_keys: str) -> str:
    """Retorna valor normalizado de fields[field_key] ou, se vazio, do primeiro extra_key não-vazio."""
    val = _norm(item.fields.get(field_key) or "")
    if val:
        return val
    for ek in extra_keys:
        val = _norm(item.extras.get(ek) or "")
        if val:
            return val
    return ""


def primary_key(item: CanonicalItem) -> str:
    """Retorna a chave primária canônica do item.

    A chave é prefixada pela categoria para garantir que itens de
    categorias diferentes nunca colidam mesmo que os campos coincidam.
    """
    f = item.fields
    cat = item.category

    if cat == Category.LOGIN:
        domain = _origin(f.get("url") or "")
        username = _norm(f.get("username") or "")
        return f"login|{domain}|{username}"

    if cat == Category.CREDIT_CARD:
        # número completo; fallback para "número" (pt) quando não mapeado pelo importer
        number = _f(item, "number", "número", "numero")
        cardholder = _f(item, "cardholder", "titular", "portador")
        return f"cc|{number}|{cardholder}"

    if cat == Category.SERVER:
        # fallback para campos pt: "url" como host, "nome de usuário"
        host = _f(item, "hostname", "url", "servidor")
        user = _f(item, "username", "nome de usuário", "nome de usuario")
        return f"server|{host}|{user}"

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
        # fallback para campos pt: "servidor", "tipo" (type/db name), "nome de usuário"
        host = _f(item, "hostname", "servidor")
        db   = _f(item, "database", "tipo", "nome do banco", "nome do banco de dados")
        user = _f(item, "username", "nome de usuário", "nome de usuario")
        return f"db|{host}|{db}|{user}"

    if cat == Category.WIRELESS:
        # fallback para campo pt: "nome da rede"
        ssid = _f(item, "ssid", "nome da rede")
        return f"wifi|{ssid}"

    # OTHER e fallback
    return f"other|{_norm(item.title)}"

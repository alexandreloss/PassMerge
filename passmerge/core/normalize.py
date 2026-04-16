"""Funções de normalização reutilizadas pelos importers e pela Fase 3 (matching).

Usa apenas a stdlib (urllib.parse, re) conforme decisão de arquitetura.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Normaliza uma URL para comparação.

    - Remove trailing slash do path raiz
    - Converte scheme e host para minúsculas
    - Remove fragmento
    - Retorna string vazia se a entrada for vazia ou não-parseável como URL
    """
    if not url or not url.strip():
        return ""
    raw = url.strip()
    # Se não tem scheme, tenta adicionar https:// para o parse funcionar
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parts = urlparse(raw)
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/") or ""
        # Reconstrói sem fragmento
        normalized = urlunparse((scheme, netloc, path, parts.params, parts.query, ""))
        return normalized
    except Exception:
        return url.strip()


def normalize_email(email: str) -> str:
    """Normaliza um endereço de e-mail para comparação.

    - Remove espaços
    - Converte para minúsculas
    - Retorna string vazia se a entrada for vazia
    """
    if not email or not email.strip():
        return ""
    return email.strip().lower()


_PHONE_NON_DIGITS = re.compile(r"[^\d+]")
_PHONE_LEADING_ZEROS = re.compile(r"^0+")


def normalize_phone(phone: str) -> str:
    """Normaliza um número de telefone para comparação.

    - Remove espaços, hífens, parênteses e pontos
    - Mantém o '+' inicial se presente (discagem internacional)
    - Retorna string vazia se a entrada for vazia
    """
    if not phone or not phone.strip():
        return ""
    raw = phone.strip()
    has_plus = raw.startswith("+")
    digits = _PHONE_NON_DIGITS.sub("", raw)
    if has_plus:
        return "+" + digits
    return digits

"""Exporter para o formato CSV do NordPass.

Segue a estrutura real e atualizada do NordPass::

    name,url,additional_urls,username,password,note,cardholdername,cardnumber,
    cvc,pin,expirydate,zipcode,folder,shared_folder,full_name,phone_number,
    email,address1,address2,city,country,state,type,custom_fields
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from ..core.canonical import CanonicalItem, Category
from ..core.categories import CANONICAL_TO_NORDPASS
from .base import ExportReport, Exporter

_HIDDEN_WORDS = {
    "senha", "password", "segredo", "segurança", "security", "secret",
    "credencial", "credential", "hash", "privado", "privada", "privacy",
    "contrasenha", "palavra-passe", "passcode", "pin", "confidencial",
    "arcano", "sigilo", "hidden", "reservado", "reservada", "classified",
    "restricted", "restrito", "restrita", "classificado", "classificada",
    "sigiloso", "sigilosa",
}

_DATE_WORDS = {"data", "tempo", "time", "date", "timestamp"}


def _yyyymm_to_unix(raw: str) -> str:
    """Converts a YYYYMM string to a Unix timestamp string (first day of the month, UTC)."""
    raw = raw.strip()
    if len(raw) == 6 and raw.isdigit():
        try:
            dt = datetime(int(raw[:4]), int(raw[4:]), 1, tzinfo=timezone.utc)
            return str(int(dt.timestamp()))
        except ValueError:
            pass
    return raw


def _cf_type(label: str) -> str:
    lower = label.lower()
    if any(w in lower for w in _HIDDEN_WORDS):
        return "hidden"
    if any(w in lower for w in _DATE_WORDS):
        return "date"
    return "text"


# Chaves de extras que já foram promovidas a colunas canônicas — não vão para custom_fields
_EXTRAS_SKIP = {
    "_losers",
    "nome do titular", "número", "número de verificação", "data de validade",
}

# Colunas na ordem exata do formato atual do NordPass
_COLUMNS = [
    "name", "url", "additional_urls", "username", "password", "note",
    "cardholdername", "cardnumber", "cvc", "pin", "expirydate", "zipcode",
    "folder", "shared_folder", "full_name", "phone_number", "email",
    "address1", "address2", "city", "country", "state",
    "type", "custom_fields",
]


def _row_for(item: CanonicalItem) -> dict[str, str]:
    f = item.fields
    base: dict[str, str] = {
        "name":   item.title,
        "folder": item.tags[0] if item.tags else (item.folder or ""),
        "type":   CANONICAL_TO_NORDPASS.get(item.category, "password"),
    }

    if item.category == Category.LOGIN:
        base["url"]             = f.get("url") or ""
        base["additional_urls"] = f.get("urls_additional") or ""
        base["username"]        = f.get("username") or ""
        base["password"]        = f.get("password") or ""
        base["note"]            = item.notes or ""

    elif item.category == Category.CREDIT_CARD:
        x = item.extras
        base["cardholdername"] = f.get("cardholder") or x.get("nome do titular") or ""
        base["cardnumber"]     = f.get("number") or x.get("número") or ""
        base["cvc"]            = f.get("cvv") or x.get("número de verificação") or ""
        base["pin"]            = f.get("pin") or ""
        raw_expiry = f.get("expiration") or ""
        if not raw_expiry:
            raw_expiry = _yyyymm_to_unix(x.get("data de validade") or "")
        base["expirydate"]     = raw_expiry
        base["zipcode"]        = f.get("zip") or ""
        base["note"]           = item.notes or ""

    elif item.category == Category.SECURE_NOTE:
        base["note"] = f.get("body") or ""

    elif item.category == Category.IDENTITY:
        base["full_name"]    = f.get("first_name") or ""
        base["email"]        = f.get("email") or ""
        base["phone_number"] = f.get("phone") or ""
        base["address1"]     = f.get("address1") or ""
        base["address2"]     = f.get("address2") or ""
        base["city"]         = f.get("city") or ""
        base["state"]        = f.get("state") or ""
        base["country"]      = f.get("country") or ""

    else:
        # Categorias sem mapeamento nativo → LOGIN
        base["url"]      = f.get("url") or ""
        base["username"] = f.get("username") or ""
        base["password"] = f.get("password") or ""
        base["note"]     = item.notes or ""

    exportable_extras = {k: v for k, v in item.extras.items() if k not in _EXTRAS_SKIP}
    if exportable_extras:
        cf = [{"type": _cf_type(k), "label": k, "value": str(v)}
              for k, v in exportable_extras.items()]
        base["custom_fields"] = json.dumps(cf, ensure_ascii=False, separators=(",", ":"))

    return base


class NordPassExporter(Exporter):
    target_name = "nordpass"
    # Todas as categorias são aceitas — as sem mapeamento nativo viram LOGIN.
    supported_categories = set(Category)

    def export(self, items: list[CanonicalItem], out_path: Path) -> ExportReport:
        report = ExportReport(target=self.target_name)

        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=_COLUMNS,
                extrasaction="ignore", quoting=csv.QUOTE_ALL,
            )
            writer.writeheader()
            for item in items:
                row = _row_for(item)
                for col in _COLUMNS:
                    row.setdefault(col, "")
                writer.writerow(row)
                report.exported_count += 1

        return report

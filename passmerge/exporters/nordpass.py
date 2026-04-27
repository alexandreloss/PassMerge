"""Exporter para o formato CSV do NordPass.

Segue a estrutura real e atualizada do NordPass::

    name,url,additional_urls,username,password,note,cardholdername,cardnumber,
    cvc,pin,expirydate,zipcode,folder,shared_folder,full_name,phone_number,
    email,address1,address2,city,country,state,type,custom_fields
"""
from __future__ import annotations

import csv
import json
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


def _cf_type(label: str) -> str:
    lower = label.lower()
    if any(w in lower for w in _HIDDEN_WORDS):
        return "hidden"
    if any(w in lower for w in _DATE_WORDS):
        return "date"
    return "text"


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
        base["cardholdername"] = f.get("cardholder") or ""
        base["cardnumber"]     = f.get("number") or ""
        base["cvc"]            = f.get("cvv") or ""
        base["pin"]            = f.get("pin") or ""
        base["expirydate"]     = f.get("expiration") or ""
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

    exportable_extras = {k: v for k, v in item.extras.items() if k != "_losers"}
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

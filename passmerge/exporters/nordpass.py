"""Exporter para o formato CSV do NordPass.

Segue o template oficial de import do NordPass::

    name,url,username,password,note,cardholdername,cardnumber,cvc,expirydate,
    zipcode,folder,full_name,phone_number,email,address1,address2,city,
    country,state,totp,shared_folder
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ..core.canonical import CanonicalItem, Category
from .base import ExportReport, Exporter

# Colunas na ordem exata do template oficial do NordPass
_COLUMNS = [
    "name", "url", "username", "password", "note",
    "cardholdername", "cardnumber", "cvc", "expirydate", "zipcode",
    "folder", "full_name", "phone_number", "email",
    "address1", "address2", "city", "country", "state",
    "totp", "shared_folder", "custom_fields",
]


def _row_for(item: CanonicalItem) -> dict[str, str]:
    f = item.fields
    base: dict[str, str] = {
        "name":   item.title,
        "folder": item.tags[0] if item.tags else (item.folder or ""),
    }

    if item.category == Category.LOGIN:
        base["url"]      = f.get("url") or ""
        base["username"] = f.get("username") or ""
        base["password"] = f.get("password") or ""
        base["note"]     = item.notes or ""
        base["totp"]     = f.get("otp") or ""

    elif item.category == Category.CREDIT_CARD:
        base["cardholdername"] = f.get("cardholder") or ""
        base["cardnumber"]     = f.get("number") or ""
        base["cvc"]            = f.get("cvv") or ""
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

    if item.extras:
        base["custom_fields"] = json.dumps(
            [item.extras], ensure_ascii=False, separators=(",", ":")
        )

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

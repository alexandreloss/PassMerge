"""Exporter para o formato .1pux do 1Password (ZIP + export.data JSON)."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.canonical import CanonicalItem, Category
from ..core.categories import CANONICAL_TO_ONEPASSWORD
from .base import ExportReport, Exporter

# canonical_key → (1pux section field id, value_type)
# Para categorias não-LOGIN, username/password também vão para sections.
_CANONICAL_TO_SECTION: dict[str, tuple[str, str]] = {
    # campos de login usados em categorias não-LOGIN (server, db, wireless…)
    "username":      ("username",          "string"),
    "password":      ("password",          "concealed"),
    # credit card
    "cardholder":    ("cardholder",        "string"),
    "number":        ("ccnum",             "concealed"),
    "cvv":           ("cvv",               "concealed"),
    "expiration":    ("expiry",            "monthYear"),
    "pin":           ("pin",               "concealed"),
    # server / database
    "hostname":      ("hostname",          "string"),
    "port":          ("port",              "string"),
    "database":      ("database",          "string"),
    "type":          ("type",              "menu"),
    "private_key":   ("private_key",       "concealed"),
    # identity
    "first_name":    ("firstname",         "string"),
    "last_name":     ("lastname",          "string"),
    "email":         ("email",             "email"),
    "phone":         ("phone",             "phone"),
    "address1":      ("address",           "string"),
    "address2":      ("address2",          "string"),
    "city":          ("city",              "string"),
    "state":         ("state",             "string"),
    "country":       ("country",           "string"),
    "zip":           ("zip",               "string"),
    "birth_date":    ("birthdate",         "date"),
    # software license
    "product":       ("product",           "string"),
    "license_key":   ("reg_code",          "concealed"),
    "licensed_to":   ("reg_name",          "string"),
    "version":       ("version",           "string"),
    # wireless
    "ssid":          ("ssid",              "string"),
    "security_type": ("wireless_security", "menu"),
}

# Campos que nunca vão para sections (tratados fora do loop genérico)
_SKIP_IN_SECTIONS = {"url", "otp", "urls_additional"}


def _iso_to_epoch(ts: str | None) -> int:
    if not ts:
        return 0
    try:
        return int(datetime.fromisoformat(ts).timestamp())
    except Exception:
        return 0


def _section_field(field_id: str, title: str, value: str, vtype: str) -> dict[str, Any]:
    return {"id": field_id, "title": title, "value": {vtype: value}}


def _item_to_1pux(item: CanonicalItem) -> dict[str, Any]:
    category_uuid = CANONICAL_TO_ONEPASSWORD.get(item.category, "003")

    overview: dict[str, Any] = {
        "title": item.title,
        "url": item.fields.get("url") or "",
        "tags": list(item.tags),
    }
    if item.fields.get("url"):
        overview["urls"] = [{"primary": True, "url": item.fields["url"]}]

    details: dict[str, Any] = {
        "loginFields": [],
        "notesPlain": item.notes or "",
        "sections": [],
    }

    if item.category == Category.SECURE_NOTE:
        details["notesPlain"] = item.fields.get("body") or item.notes or ""

    elif item.category == Category.LOGIN:
        details["loginFields"] = [
            {"designation": "username", "value": item.fields.get("username") or ""},
            {"designation": "password", "value": item.fields.get("password") or ""},
        ]
        if item.fields.get("otp"):
            details["sections"].append({"title": "", "fields": [
                _section_field("TOTP_otp", "one-time password",
                               item.fields["otp"], "totp")
            ]})

    else:
        # Todas as outras categorias: campos vão para sections.
        # loginFields fica vazio (padrão 1Password para categorias não-login).
        section_fields: list[dict[str, Any]] = []
        for canonical_key, value in item.fields.items():
            if canonical_key in _SKIP_IN_SECTIONS or not value:
                continue
            mapping = _CANONICAL_TO_SECTION.get(canonical_key)
            if mapping:
                fid, vtype = mapping
                section_fields.append(_section_field(fid, fid, str(value), vtype))
        if section_fields:
            details["sections"].append({"title": "", "fields": section_fields})

    return {
        "uuid": item.id,
        "favorite": 1 if item.favorite else 0,
        "createdAt": _iso_to_epoch(item.created_at),
        "updatedAt": _iso_to_epoch(item.updated_at),
        "trashed": "Y" if item.trashed else "N",
        "categoryUuid": category_uuid,
        "overview": overview,
        "details": details,
    }


def _build_export_data(items: list[CanonicalItem]) -> dict[str, Any]:
    return {
        "accounts": [{
            "vaults": [{
                "items": [_item_to_1pux(i) for i in items],
            }],
        }]
    }


class OnePasswordExporter(Exporter):
    target_name = "1password"
    supported_categories = set(CANONICAL_TO_ONEPASSWORD.keys())

    def export(self, items: list[CanonicalItem], out_path: Path) -> ExportReport:
        report = ExportReport(target=self.target_name)

        exportable: list[CanonicalItem] = []
        for item in items:
            if item.category not in self.supported_categories:
                report.skip(item, "unsupported_category")
            else:
                exportable.append(item)

        json_bytes = json.dumps(
            _build_export_data(exportable), ensure_ascii=False, indent=2
        ).encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("export.data", json_bytes)
        out_path.write_bytes(buf.getvalue())

        report.exported_count = len(exportable)
        return report

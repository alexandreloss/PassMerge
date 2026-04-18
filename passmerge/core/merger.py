"""Algoritmo de merge — Fase 3.

Agrupa itens de múltiplas fontes por (category, primary_key) e resolve
conflitos campo a campo segundo as regras:

  1. Timestamp mais recente vence.
  2. Item com timestamp vence item sem timestamp.
  3. Sem timestamp e valores divergem → prioridade configurada;
     conflito registrado para revisão manual.
  4. Complementação: campos vazios no vencedor são preenchidos por
     outros itens do grupo.
  5. Preservação: valores perdedores ficam em extras["_losers"].
  6. SourceRefs de todos os itens do grupo são acumulados no merged.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .canonical import CanonicalItem, Category, SourceRef
from .conflict import ConflictLog, ReviewConflict
from .matching import primary_key

_DEFAULT_PRIORITY = ["nordpass", "1password", "chrome", "kaspersky"]

_META_FIELDS = {"urls_additional"}


@dataclass
class MergeStats:
    total_input: int = 0
    total_output: int = 0
    groups_merged: int = 0
    fields_complemented: int = 0


@dataclass
class MergeResult:
    items: list[CanonicalItem]
    conflict_log: ConflictLog
    stats: MergeStats


def _source_of(item: CanonicalItem) -> str:
    if item.sources:
        return item.sources[0].source
    return "unknown"


def _ts_epoch(ts: str | None) -> float:
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def _priority_rank(source: str, priority: list[str]) -> int:
    try:
        return priority.index(source)
    except ValueError:
        return len(priority)


def _merge_group(
    group: list[CanonicalItem],
    priority: list[str],
    log: ConflictLog,
    stats: MergeStats,
) -> CanonicalItem:
    if len(group) == 1:
        return group[0]

    stats.groups_merged += 1

    def sort_key(item: CanonicalItem):
        has_ts = item.updated_at is not None
        has_password = bool(item.fields.get("password"))
        rank = _priority_rank(_source_of(item), priority)
        # Ordem de prioridade crescente (menor = melhor):
        # 1. tem timestamp  2. epoch mais recente  3. tem senha  4. rank de fonte
        return (not has_ts, -_ts_epoch(item.updated_at), not has_password, rank)

    ordered = sorted(group, key=sort_key)
    winner = ordered[0]
    losers = ordered[1:]

    merged_fields: dict[str, Any] = dict(winner.fields)
    merged_extras: dict[str, Any] = dict(winner.extras)
    loser_records: list[dict] = list(merged_extras.get("_losers") or [])

    title = winner.title
    category_str = winner.category.value
    winner_has_password = bool(winner.fields.get("password"))

    # Vaults com senha preenchida têm todos a mesma senha?
    # Ignora vaults sem senha (eles são filtrados antes da resolução de conflito).
    pw_items = [item for item in group if bool(item.fields.get("password"))]
    same_nonempty_password = (
        len(pw_items) >= 2
        and len({item.fields.get("password") for item in pw_items}) == 1
    )

    all_field_keys: set[str] = set()
    for item in group:
        all_field_keys.update(item.fields.keys())
    all_field_keys -= _META_FIELDS

    review_fields: list[str] = []

    for fname in sorted(all_field_keys):
        winner_val = merged_fields.get(fname) or ""
        # Complementação: campos ausentes no vencedor são preenchidos pelos perdedores
        loser_vals = [(item, item.fields.get(fname) or "") for item in losers]

        if not winner_val:
            fill_candidates = [(item, v) for item, v in loser_vals if v]
            if fill_candidates:
                unique_vals = {v for _, v in fill_candidates}
                if len(unique_vals) == 1:
                    merged_fields[fname] = fill_candidates[0][1]
                    stats.fields_complemented += 1
                else:
                    best = min(
                        fill_candidates,
                        key=lambda t: _priority_rank(_source_of(t[0]), priority),
                    )
                    merged_fields[fname] = best[1]
                    stats.fields_complemented += 1
                    review_fields.append(fname)
            continue

        diverging = [(item, v) for item, v in loser_vals if v and v != winner_val]
        if not diverging:
            continue

        # Quando o vencedor tem senha, descarta perdedores sem senha do conflito.
        # Aplica-se só quando ao menos um perdedor divergente também tem senha;
        # caso contrário a regra de "só vencedor tem senha" já resolve abaixo.
        if winner_has_password:
            pw_diverging = [(i, v) for i, v in diverging if bool(i.fields.get("password"))]
            if pw_diverging:
                diverging = pw_diverging

        winner_has_ts = winner.updated_at is not None
        any_loser_has_ts = any(i.updated_at for i, _ in diverging)
        requires_review = not winner_has_ts and not any_loser_has_ts

        # Mesma senha em todos os vaults → resolvido por prioridade de fonte.
        if requires_review and same_nonempty_password:
            requires_review = False

        # Vencedor eleito por ter senha e todos os perdedores divergentes não têm
        # senha → critério de senha já resolveu.
        if requires_review and winner_has_password:
            if all(not bool(i.fields.get("password")) for i, _ in diverging):
                requires_review = False

        if requires_review:
            review_fields.append(fname)

        by_ts = winner_has_ts or any_loser_has_ts
        for loser_item, loser_val in diverging:
            loser_records.append({
                "source": _source_of(loser_item),
                "field": fname,
                "value_hash": hashlib.sha256(loser_val.encode()).hexdigest(),
                "reason": "timestamp" if by_ts else "priority",
            })

    if review_fields:
        log.add(ReviewConflict(
            conflict_id=str(uuid.uuid4()),
            item_title=title,
            category=category_str,
            conflicting_fields=review_fields,
            versions=[
                {
                    "source": _source_of(item),
                    "updated_at": item.updated_at,
                    "escolhido": "[]",
                    "fields": dict(item.fields),
                }
                for item in group
            ],
        ))

    if loser_records:
        merged_extras["_losers"] = loser_records

    all_sources: list[SourceRef] = list(winner.sources)
    for loser in losers:
        for src in loser.sources:
            if not any(s.source == src.source and s.source_id == src.source_id
                       for s in all_sources):
                all_sources.append(src)

    merged_tags = list(winner.tags)
    for loser in losers:
        for tag in loser.tags:
            if tag not in merged_tags:
                merged_tags.append(tag)

    favorite = winner.favorite or any(l.favorite for l in losers)
    trashed = winner.trashed and all(l.trashed for l in losers)
    notes = winner.notes or next((l.notes for l in losers if l.notes), "")

    return CanonicalItem(
        id=winner.id,
        category=winner.category,
        title=title,
        fields=merged_fields,
        favorite=favorite,
        trashed=trashed,
        tags=merged_tags,
        folder=winner.folder,
        created_at=winner.created_at,
        updated_at=winner.updated_at,
        sources=all_sources,
        notes=notes,
        extras=merged_extras,
    )


def merge(
    item_groups: list[list[CanonicalItem]],
    priority: list[str] | None = None,
) -> MergeResult:
    if priority is None:
        priority = _DEFAULT_PRIORITY

    log = ConflictLog()
    stats = MergeStats()

    for grp in item_groups:
        stats.total_input += len(grp)

    buckets: dict[tuple[str, str], list[CanonicalItem]] = {}
    for grp in item_groups:
        for item in grp:
            key = (item.category.value, primary_key(item))
            buckets.setdefault(key, []).append(item)

    merged_items: list[CanonicalItem] = []
    for bucket in buckets.values():
        merged = _merge_group(bucket, priority, log, stats)
        merged_items.append(merged)

    stats.total_output = len(merged_items)

    return MergeResult(items=merged_items, conflict_log=log, stats=stats)

"""CLI do PassMerge.

Comandos implementados:
    passmerge init    --vault PATH
    passmerge status  --vault PATH
    passmerge verify  --vault PATH
    passmerge wipe    --file  PATH --yes
    passmerge import  [--chrome X.csv] [--nordpass Y.csv]
                      [--onepassword Z.1pux] [--kaspersky W.txt]
                      --vault out.json
    passmerge manual  --vault out.json --log out.conflicts.json
    passmerge export  --vault out.json
                      [--to-chrome out.csv] [--to-nordpass out.csv]
                      [--to-onepassword out.1pux] [--to-kaspersky out.txt]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import __version__
from .core.canonical import SourceFileRef, Vault, empty_vault
from .security.wipe import secure_wipe


def _load_vault(vault_path: Path) -> Vault:
    try:
        raw = vault_path.read_bytes()
    except FileNotFoundError:
        print(f"ERRO: vault nao encontrado: {vault_path}", file=sys.stderr)
        sys.exit(1)
    try:
        return Vault.from_bytes(raw)
    except Exception as exc:
        print(f"ERRO: vault invalido ({exc})", file=sys.stderr)
        sys.exit(1)


def _save_vault(vault: Vault, vault_path: Path) -> None:
    """Escrita atomica: grava em .tmp e renomeia."""
    vault_path = Path(vault_path)
    tmp = vault_path.with_suffix(vault_path.suffix + ".tmp")
    tmp.write_text(vault.to_json(indent=2), encoding="utf-8")
    tmp.replace(vault_path)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------- comandos ----------

def cmd_init(args: argparse.Namespace) -> int:
    vault_path = Path(args.vault)
    if vault_path.exists() and not args.force:
        print(f"ERRO: {vault_path} ja existe. Use --force para sobrescrever.",
              file=sys.stderr)
        return 1
    vault = empty_vault()
    errs = vault.validate()
    if errs:
        print("ERRO: vault vazio invalido: " + "; ".join(errs), file=sys.stderr)
        return 1
    _save_vault(vault, vault_path)
    print(f"OK: vault criado em {vault_path}")
    print(f"    schema_version = {vault.schema_version}")
    print(f"    itens = 0")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    vault_path = Path(args.vault)
    vault = _load_vault(vault_path)
    summary = vault.summary()
    print(f"Vault: {vault_path}")
    print(f"  schema_version : {vault.schema_version}")
    print(f"  generated_at   : {vault.generated_at}")
    print(f"  total de itens : {summary.pop('_total')}")
    print(f"  conflitos      : {summary.pop('_conflicts')}")
    if summary:
        print("  por categoria:")
        for cat, n in sorted(summary.items()):
            print(f"    {cat:20s} {n}")
    if vault.source_files:
        print("  arquivos de origem:")
        for sf in vault.source_files:
            print(f"    [{sf.source}] {sf.path} "
                  f"(sha256 {sf.sha256[:12]}..., {sf.item_count} itens)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    vault_path = Path(args.vault)
    vault = _load_vault(vault_path)
    errors = vault.validate()
    if errors:
        print("FALHOU: problemas encontrados:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: vault valido ({len(vault.items)} itens, schema {vault.schema_version}).")
    return 0


def cmd_wipe(args: argparse.Namespace) -> int:
    target = Path(args.file)
    if not target.exists():
        print(f"ERRO: arquivo nao encontrado: {target}", file=sys.stderr)
        return 1
    if not args.yes:
        print(f"AVISO: {target} sera sobrescrito 3 vezes e removido.")
        print("Passe --yes para confirmar.")
        return 2
    secure_wipe(target)
    print(f"OK: {target} sobrescrito e removido.")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    # Importação lazy para evitar ciclos no topo do módulo
    from .core.merger import merge
    from .importers.apple import ApplePasswordsImporter
    from .importers.chrome import ChromeImporter
    from .importers.kaspersky import KasperskyImporter
    from .importers.nordpass import NordPassImporter
    from .importers.onepassword import OnePasswordImporter

    sources = [
        ("chrome",       args.chrome,       ChromeImporter()),
        ("nordpass",     args.nordpass,      NordPassImporter()),
        ("onepassword",  args.onepassword,   OnePasswordImporter()),
        ("applesenhas",  args.applesenhas,   ApplePasswordsImporter()),
        ("kaspersky",    args.kaspersky,     KasperskyImporter()),
    ]

    # Valida que ao menos um arquivo foi informado
    active = [(name, path, imp) for name, path, imp in sources if path]
    if not active:
        print(
            "ERRO: informe ao menos um arquivo de entrada "
            "(--chrome, --nordpass, --onepassword, --applesenhas ou --kaspersky).",
            file=sys.stderr,
        )
        return 1

    vault_path = Path(args.vault)

    # Carrega vault existente ou cria novo
    if vault_path.exists():
        vault = _load_vault(vault_path)
    else:
        vault = empty_vault()

    # --- Importar cada fonte ---
    item_groups: list[list] = []
    for source_name, raw_path, importer in active:
        file_path = Path(raw_path)
        if not file_path.exists():
            print(f"ERRO: arquivo nao encontrado: {file_path}", file=sys.stderr)
            return 1
        try:
            items = importer.parse(file_path)
        except Exception as exc:
            print(f"ERRO ao importar {file_path} ({source_name}): {exc}",
                  file=sys.stderr)
            return 1
        item_groups.append(items)
        vault.source_files.append(SourceFileRef(
            source=source_name,
            path=str(file_path.resolve()),
            sha256=_sha256(file_path),
            item_count=len(items),
        ))
        print(f"  [{source_name}] {len(items)} itens lidos de {file_path}")

    # --- Merge (só quando há ≥2 fontes) ---
    if len(item_groups) >= 2:
        result = merge(item_groups)
        vault.items.extend(result.items)
        s = result.stats
        print(f"  merge: {s.total_input} → {s.total_output} itens "
              f"({s.groups_merged} grupos merged, "
              f"{s.fields_complemented} campos complementados)")
        if len(result.conflict_log):
            summary = result.conflict_log.summary()
            conflicts_path = vault_path.with_suffix(".conflicts.json")
            result.conflict_log.save(conflicts_path)
            print(f"  conflitos para revisão manual: {summary['requires_review']} → {conflicts_path.name}")
    else:
        vault.items.extend(item_groups[0])
        print(f"  (fonte única — merge ignorado)")

    _save_vault(vault, vault_path)
    print(f"OK: {len(vault.items)} itens gravados em {vault_path}")
    return 0


def cmd_manual(args: argparse.Namespace) -> int:
    vault_path = Path(args.vault)
    log_path = Path(args.log)

    if not log_path.exists():
        print(f"ERRO: arquivo de conflitos não encontrado: {log_path}", file=sys.stderr)
        return 1

    vault = _load_vault(vault_path)

    try:
        conflicts = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERRO: log de conflitos inválido ({exc})", file=sys.stderr)
        return 1

    resolved_count = 0
    remaining = []

    for conflict in conflicts:
        versions = conflict.get("versions", [])
        chosen = [v for v in versions if v.get("escolhido") == "[x]"]

        if len(chosen) == 0:
            remaining.append(conflict)
            continue

        if len(chosen) > 1:
            print(f"  AVISO: '{conflict['item_title']}' tem {len(chosen)} versões marcadas — ignorado.")
            remaining.append(conflict)
            continue

        chosen_version = chosen[0]
        title = conflict["item_title"]
        category = conflict["category"]
        conflicting_fields = conflict.get("conflicting_fields", [])

        matching = [i for i in vault.items
                    if i.title == title and i.category.value == category]

        if not matching:
            print(f"  AVISO: '{title}' ({category}) não encontrado no vault — ignorado.")
            remaining.append(conflict)
            continue

        chosen_fields = chosen_version.get("fields", {})

        if len(matching) > 1:
            # Múltiplas entradas legítimas com mesmo título/categoria —
            # adiciona a versão escolhida como nova entrada no vault.
            from .core.canonical import CanonicalItem, Category, SourceRef
            try:
                cat = Category(category)
            except ValueError:
                print(f"  AVISO: categoria inválida '{category}' em '{title}' — ignorado.")
                remaining.append(conflict)
                continue
            new_item = CanonicalItem(
                category=cat,
                title=title,
                fields=dict(chosen_fields),
                sources=[SourceRef(source=chosen_version["source"], source_id="manual")],
                updated_at=chosen_version.get("updated_at"),
            )
            vault.items.append(new_item)
            resolved_count += 1
            print(f"  OK: '{title}' — novo item adicionado de [{chosen_version['source']}]")
            continue

        item = matching[0]
        for field in conflicting_fields:
            if field in chosen_fields:
                item.fields[field] = chosen_fields[field]

        resolved_count += 1
        print(f"  OK: '{title}' — {len(conflicting_fields)} campo(s) de [{chosen_version['source']}]")

    if resolved_count == 0:
        print("Nenhum conflito marcado com [x] encontrado.")
        return 0

    _save_vault(vault, vault_path)

    if remaining:
        log_path.write_text(
            json.dumps(remaining, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"OK: {resolved_count} conflito(s) resolvido(s). "
              f"{len(remaining)} restante(s) em {log_path.name}")
    else:
        log_path.unlink()
        print(f"OK: {resolved_count} conflito(s) resolvido(s). "
              f"Todos resolvidos — {log_path.name} removido.")

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from .exporters.apple import ApplePasswordsExporter
    from .exporters.chrome import ChromeExporter
    from .exporters.kaspersky import KasperskyExporter
    from .exporters.nordpass import NordPassExporter
    from .exporters.onepassword import OnePasswordExporter

    targets = [
        ("chrome",       args.to_chrome,       ChromeExporter()),
        ("nordpass",     args.to_nordpass,      NordPassExporter()),
        ("onepassword",  args.to_onepassword,   OnePasswordExporter()),
        ("applesenhas",  args.to_applesenhas,   ApplePasswordsExporter()),
        ("kaspersky",    args.to_kaspersky,     KasperskyExporter()),
    ]
    active = [(name, path, exp) for name, path, exp in targets if path]
    if not active:
        print(
            "ERRO: informe ao menos um destino "
            "(--to-chrome, --to-nordpass, --to-onepassword, --to-applesenhas ou --to-kaspersky).",
            file=sys.stderr,
        )
        return 1

    vault = _load_vault(Path(args.vault))

    for name, raw_path, exporter in active:
        out_path = Path(raw_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        report = exporter.export(vault.items, out_path)
        print(f"  [{name}] {report.exported_count} itens → {out_path}")
        if report.skipped_items:
            for s in report.skipped_items:
                print(f"    SKIP: '{s['title']}' ({s['category']}) — {s['reason']}")
        if report.truncated_fields:
            for t in report.truncated_fields:
                print(f"    TRUNCADO: '{t['title']}' campo '{t['field']}' "
                      f"({t['original_len']} → {t['max_len']} chars)")
        if report.warnings:
            for w in report.warnings:
                print(f"    AVISO: {w}")

    return 0


# ---------- parser ----------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="passmerge",
        description="Consolidador local de senhas entre multiplos gerenciadores.",
    )
    parser.add_argument("--version", action="version",
                        version=f"passmerge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="cria um vault JSON vazio")
    p_init.add_argument("--vault", required=True, help="caminho do vault a criar")
    p_init.add_argument("--force", action="store_true",
                        help="sobrescreve vault existente")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="exibe resumo do vault")
    p_status.add_argument("--vault", required=True)
    p_status.set_defaults(func=cmd_status)

    p_verify = sub.add_parser("verify", help="valida schema + integridade")
    p_verify.add_argument("--vault", required=True)
    p_verify.set_defaults(func=cmd_verify)

    p_wipe = sub.add_parser("wipe",
                            help="sobrescreve e remove um arquivo (ex.: CSV exportado)")
    p_wipe.add_argument("--file", required=True, help="arquivo a apagar")
    p_wipe.add_argument("--yes", action="store_true",
                        help="confirma a remocao")
    p_wipe.set_defaults(func=cmd_wipe)

    p_import = sub.add_parser(
        "import",
        help="importa arquivos de gerenciadores para o vault",
    )
    p_import.add_argument("--chrome", metavar="CSV",
                          help="CSV exportado pelo Google Chrome")
    p_import.add_argument("--nordpass", metavar="CSV",
                          help="CSV exportado pelo NordPass")
    p_import.add_argument("--onepassword", metavar="1PUX",
                          help="arquivo .1pux exportado pelo 1Password")
    p_import.add_argument("--applesenhas", metavar="CSV",
                          help="CSV exportado pelo Apple Passwords (iPhone/macOS)")
    p_import.add_argument("--kaspersky", metavar="TXT",
                          help="arquivo TXT exportado pelo Kaspersky Password Manager")
    p_import.add_argument("--vault", required=True,
                          help="vault de destino (criado se nao existir)")
    p_import.set_defaults(func=cmd_import)

    p_manual = sub.add_parser(
        "manual",
        help="aplica resoluções manuais de conflito marcadas com [x] no log",
    )
    p_manual.add_argument("--vault", required=True, help="vault a atualizar")
    p_manual.add_argument("--log",   required=True,
                          help="arquivo de conflitos gerado pelo import (ex.: vault.conflicts.json)")
    p_manual.set_defaults(func=cmd_manual)

    p_export = sub.add_parser(
        "export",
        help="exporta o vault para os formatos nativos dos gerenciadores",
    )
    p_export.add_argument("--vault", required=True, help="vault de origem")
    p_export.add_argument("--to-chrome",       metavar="CSV",  help="saída para Google Chrome")
    p_export.add_argument("--to-nordpass",     metavar="CSV",  help="saída para NordPass")
    p_export.add_argument("--to-onepassword",  metavar="1PUX", help="saída para 1Password")
    p_export.add_argument("--to-applesenhas",  metavar="CSV",  help="saída para Apple Passwords")
    p_export.add_argument("--to-kaspersky",    metavar="TXT",  help="saída para Kaspersky")
    p_export.set_defaults(func=cmd_export)

    return parser


def _not_implemented(args: argparse.Namespace) -> int:
    print(f"ERRO: '{args.command}' sera implementado nas proximas fases.",
          file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

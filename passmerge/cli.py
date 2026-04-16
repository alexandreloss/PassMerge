"""CLI do PassMerge - Fase 2 (importers + vault em JSON plano).

O vault e armazenado como .json em texto claro (UTF-8). Responsabilidade
do usuario proteger/apagar o arquivo apos o uso. O modulo security/wipe.py
fica disponivel para apagamento seguro opcional.

Comandos implementados:
    passmerge init    --vault PATH          cria vault.json vazio
    passmerge status  --vault PATH          exibe resumo
    passmerge verify  --vault PATH          valida schema
    passmerge wipe    --file  PATH          sobrescreve e remove (util para CSVs)
    passmerge import  [--chrome X.csv]
                      [--nordpass Y.csv]
                      [--onepassword Z.1pux]
                      [--kaspersky W.txt]
                      --vault out.json      importa arquivos para o vault

Comandos planejados (Fases 3+):
    passmerge export ...      (F4)
    passmerge resolve ...     (F5)
"""
from __future__ import annotations

import argparse
import hashlib
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
    from .importers.chrome import ChromeImporter
    from .importers.kaspersky import KasperskyImporter
    from .importers.nordpass import NordPassImporter
    from .importers.onepassword import OnePasswordImporter

    sources = [
        ("chrome", args.chrome, ChromeImporter()),
        ("nordpass", args.nordpass, NordPassImporter()),
        ("onepassword", args.onepassword, OnePasswordImporter()),
        ("kaspersky", args.kaspersky, KasperskyImporter()),
    ]

    # Valida que ao menos um arquivo foi informado
    active = [(name, path, imp) for name, path, imp in sources if path]
    if not active:
        print(
            "ERRO: informe ao menos um arquivo de entrada "
            "(--chrome, --nordpass, --onepassword ou --kaspersky).",
            file=sys.stderr,
        )
        return 1

    vault_path = Path(args.vault)

    # Carrega vault existente ou cria novo
    if vault_path.exists():
        vault = _load_vault(vault_path)
    else:
        vault = empty_vault()

    total_imported = 0

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

        vault.items.extend(items)
        vault.source_files.append(SourceFileRef(
            source=source_name,
            path=str(file_path.resolve()),
            sha256=_sha256(file_path),
            item_count=len(items),
        ))
        print(f"  [{source_name}] {len(items)} itens importados de {file_path}")
        total_imported += len(items)

    _save_vault(vault, vault_path)
    print(f"OK: {total_imported} itens gravados em {vault_path}")
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
    p_import.add_argument("--kaspersky", metavar="TXT",
                          help="arquivo TXT exportado pelo Kaspersky Password Manager")
    p_import.add_argument("--vault", required=True,
                          help="vault de destino (criado se nao existir)")
    p_import.set_defaults(func=cmd_import)

    # Placeholder para fases futuras
    for future_cmd in ("export", "resolve"):
        ph = sub.add_parser(future_cmd,
                            help="[nao implementado ainda]")
        ph.set_defaults(func=_not_implemented)

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

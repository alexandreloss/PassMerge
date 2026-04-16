"""Criterio de aceite da Fase 1 (versao simplificada, JSON plano).

Arquitetura revisada: o vault e gravado como JSON UTF-8 em texto claro.
O usuario e responsavel por apagar o arquivo apos o uso (o comando
`passmerge wipe` pode ajudar).
"""
import json
import tempfile
import unittest
from pathlib import Path

from passmerge.cli import cmd_init, cmd_status, cmd_verify
from passmerge.core.canonical import SCHEMA_VERSION, Vault, empty_vault


class _Args:
    """Namespace minimo para invocar comandos do CLI programaticamente."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestPhase1Acceptance(unittest.TestCase):
    def test_empty_vault_create_and_read(self):
        """F1: criar vault vazio, gravar em JSON, ler, validar."""
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"

            # Criar vault vazio direto via API
            v = empty_vault()
            self.assertEqual(v.validate(), [])
            vault_path.write_text(v.to_json(indent=2), encoding="utf-8")

            self.assertTrue(vault_path.exists())

            # Ler e validar
            raw = vault_path.read_bytes()
            restored = Vault.from_bytes(raw)
            self.assertEqual(restored.schema_version, SCHEMA_VERSION)
            self.assertEqual(len(restored.items), 0)
            self.assertEqual(restored.summary()["_total"], 0)

            # JSON deve ser legivel e bem formado
            parsed = json.loads(vault_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["schema_version"], SCHEMA_VERSION)
            self.assertEqual(parsed["items"], [])

    def test_cli_init_creates_json(self):
        """O comando `passmerge init` cria um JSON valido."""
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"
            rc = cmd_init(_Args(vault=str(vault_path), force=False))
            self.assertEqual(rc, 0)
            self.assertTrue(vault_path.exists())
            parsed = json.loads(vault_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["schema_version"], SCHEMA_VERSION)

    def test_cli_init_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"
            vault_path.write_text("{}", encoding="utf-8")
            rc = cmd_init(_Args(vault=str(vault_path), force=False))
            self.assertEqual(rc, 1)

    def test_cli_init_force_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"
            vault_path.write_text("lixo antigo", encoding="utf-8")
            rc = cmd_init(_Args(vault=str(vault_path), force=True))
            self.assertEqual(rc, 0)
            parsed = json.loads(vault_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["schema_version"], SCHEMA_VERSION)

    def test_cli_verify_on_fresh_vault(self):
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"
            cmd_init(_Args(vault=str(vault_path), force=False))
            rc = cmd_verify(_Args(vault=str(vault_path)))
            self.assertEqual(rc, 0)

    def test_cli_status_on_fresh_vault(self):
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"
            cmd_init(_Args(vault=str(vault_path), force=False))
            rc = cmd_status(_Args(vault=str(vault_path)))
            self.assertEqual(rc, 0)


class TestInvalidVault(unittest.TestCase):
    def test_malformed_json_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"
            vault_path.write_text("{esto-nao-e-json}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                cmd_verify(_Args(vault=str(vault_path)))

    def test_wrong_schema_version_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            vault_path = Path(td) / "vault.json"
            vault_path.write_text(
                json.dumps({"schema_version": "9.9", "items": []}),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                cmd_verify(_Args(vault=str(vault_path)))


if __name__ == "__main__":
    unittest.main()

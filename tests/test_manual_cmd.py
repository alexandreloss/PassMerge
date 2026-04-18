"""Testes do comando passmerge manual."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from passmerge.cli import main
from passmerge.core.canonical import CanonicalItem, Category, Vault, empty_vault, SourceRef


def _make_vault(items: list[CanonicalItem]) -> Vault:
    v = empty_vault()
    v.items.extend(items)
    return v


def _login(title="GitHub", username="alice", password="pass1") -> CanonicalItem:
    return CanonicalItem(
        category=Category.LOGIN,
        title=title,
        fields={"username": username, "password": password, "url": "https://github.com"},
        sources=[SourceRef(source="1password", source_id="x")],
    )


def _conflict(title, category, fields_a, source_a, fields_b, source_b,
              chosen_a=False, chosen_b=False) -> dict:
    return {
        "conflict_id": "test-id",
        "item_title": title,
        "category": category,
        "conflicting_fields": list(set(fields_a) & set(fields_b)),
        "versions": [
            {
                "source": source_a,
                "updated_at": None,
                "escolhido": "[x]" if chosen_a else "[]",
                "fields": fields_a,
            },
            {
                "source": source_b,
                "updated_at": None,
                "escolhido": "[x]" if chosen_b else "[]",
                "fields": fields_b,
            },
        ],
    }


class TestManualCommand(unittest.TestCase):

    def _run(self, vault_path: Path, log_path: Path) -> int:
        return main(["manual", "--vault", str(vault_path), "--log", str(log_path)])

    def test_applies_chosen_version_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault.json"
            log_path   = Path(tmp) / "vault.conflicts.json"

            item = _login(password="old_pass")
            vault = _make_vault([item])
            vault_path.write_text(vault.to_json(indent=2), encoding="utf-8")

            conflict = _conflict(
                title="GitHub", category="login",
                fields_a={"username": "alice", "password": "new_pass"},
                source_a="nordpass", chosen_a=True,
                fields_b={"username": "alice", "password": "old_pass"},
                source_b="1password",
            )
            conflict["conflicting_fields"] = ["password"]
            log_path.write_text(json.dumps([conflict], ensure_ascii=False, indent=2),
                                encoding="utf-8")

            rc = self._run(vault_path, log_path)
            self.assertEqual(rc, 0)

            from passmerge.core.canonical import Vault as V
            updated = V.from_bytes(vault_path.read_bytes())
            self.assertEqual(updated.items[0].fields["password"], "new_pass")

    def test_resolved_conflict_removed_from_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault.json"
            log_path   = Path(tmp) / "vault.conflicts.json"

            vault = _make_vault([_login()])
            vault_path.write_text(vault.to_json(indent=2), encoding="utf-8")

            conflict = _conflict(
                title="GitHub", category="login",
                fields_a={"password": "new"}, source_a="nordpass", chosen_a=True,
                fields_b={"password": "old"}, source_b="1password",
            )
            conflict["conflicting_fields"] = ["password"]
            log_path.write_text(json.dumps([conflict], ensure_ascii=False, indent=2),
                                encoding="utf-8")

            self._run(vault_path, log_path)
            # Sem conflitos restantes → arquivo removido
            self.assertFalse(log_path.exists())

    def test_unresolved_conflict_stays_in_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault.json"
            log_path   = Path(tmp) / "vault.conflicts.json"

            vault = _make_vault([_login(), _login(title="GitLab", password="gl_pass")])
            vault_path.write_text(vault.to_json(indent=2), encoding="utf-8")

            c_resolved = _conflict(
                title="GitHub", category="login",
                fields_a={"password": "new"}, source_a="nordpass", chosen_a=True,
                fields_b={"password": "old"}, source_b="1password",
            )
            c_resolved["conflicting_fields"] = ["password"]
            c_unresolved = _conflict(
                title="GitLab", category="login",
                fields_a={"password": "gl1"}, source_a="nordpass",
                fields_b={"password": "gl2"}, source_b="1password",
            )
            c_unresolved["conflicting_fields"] = ["password"]
            log_path.write_text(
                json.dumps([c_resolved, c_unresolved], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            self._run(vault_path, log_path)
            remaining = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["item_title"], "GitLab")

    def test_ambiguous_choice_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault.json"
            log_path   = Path(tmp) / "vault.conflicts.json"

            vault = _make_vault([_login()])
            vault_path.write_text(vault.to_json(indent=2), encoding="utf-8")

            conflict = _conflict(
                title="GitHub", category="login",
                fields_a={"password": "new"}, source_a="nordpass", chosen_a=True,
                fields_b={"password": "old"}, source_b="1password", chosen_b=True,
            )
            conflict["conflicting_fields"] = ["password"]
            log_path.write_text(json.dumps([conflict], ensure_ascii=False, indent=2),
                                encoding="utf-8")

            rc = self._run(vault_path, log_path)
            self.assertEqual(rc, 0)
            # Ambíguo → permanece no log
            self.assertTrue(log_path.exists())
            remaining = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(len(remaining), 1)

    def test_missing_log_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault.json"
            log_path   = Path(tmp) / "nao_existe.json"

            vault = _make_vault([])
            vault_path.write_text(vault.to_json(indent=2), encoding="utf-8")

            rc = self._run(vault_path, log_path)
            self.assertEqual(rc, 1)

    def test_escolhido_field_present_in_generated_log(self):
        """Verifica que o merger gera o campo escolhido nas versões do log."""
        from passmerge.core.canonical import SourceRef
        from passmerge.core.merger import merge

        def _item(password, source):
            return CanonicalItem(
                category=Category.LOGIN, title="GitHub",
                fields={"username": "alice", "password": password,
                        "url": "https://github.com"},
                sources=[SourceRef(source=source, source_id="x")],
            )

        result = merge([[_item("pass1", "1password")], [_item("pass2", "nordpass")]])
        self.assertGreater(len(result.conflict_log), 0)
        entry = list(result.conflict_log)[0]
        for version in entry.versions:
            self.assertIn("escolhido", version)
            self.assertEqual(version["escolhido"], "[]")


if __name__ == "__main__":
    unittest.main()

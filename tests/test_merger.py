"""Testes de passmerge.core.merger — algoritmo de merge."""
from __future__ import annotations

import hashlib
import unittest

from passmerge.core.canonical import CanonicalItem, Category, SourceRef
from passmerge.core.merger import merge


def _src(source: str, source_id: str = "x") -> SourceRef:
    return SourceRef(source=source, source_id=source_id)


def _login(
    username="user@example.com",
    password="pass",
    url="https://github.com",
    otp="",
    source="1password",
    updated_at=None,
    title="GitHub",
    **extra_fields,
) -> CanonicalItem:
    fields = {"username": username, "password": password, "url": url}
    if otp:
        fields["otp"] = otp
    fields.update(extra_fields)
    return CanonicalItem(
        category=Category.LOGIN,
        title=title,
        fields=fields,
        sources=[_src(source)],
        updated_at=updated_at,
    )


class TestMergeScenario1_TimestampWins(unittest.TestCase):
    """Cenário 1: 2 logins, ambos com timestamp — vence o mais recente."""

    def setUp(self):
        newer = _login(password="newpass", source="1password",
                       updated_at="2023-11-01T00:00:00+00:00",
                       notes_field="note1")
        older = _login(password="oldpass", source="nordpass",
                       updated_at="2023-01-01T00:00:00+00:00",
                       phone="11999999999")
        self.result = merge([[newer], [older]])

    def test_one_item_output(self):
        self.assertEqual(len(self.result.items), 1)

    def test_winner_password_is_newer(self):
        self.assertEqual(self.result.items[0].fields["password"], "newpass")

    def test_groups_merged_counted(self):
        self.assertEqual(self.result.stats.groups_merged, 1)

    def test_total_input_output(self):
        self.assertEqual(self.result.stats.total_input, 2)
        self.assertEqual(self.result.stats.total_output, 1)

    def test_no_review_conflict_when_resolved_by_timestamp(self):
        # Conflito resolvido por timestamp não vai para o arquivo de revisão
        self.assertEqual(len(self.result.conflict_log), 0)

    def test_both_sources_in_merged(self):
        sources = {s.source for s in self.result.items[0].sources}
        self.assertIn("1password", sources)
        self.assertIn("nordpass", sources)


class TestMergeScenario2_OnlyOneHasTimestamp(unittest.TestCase):
    """Cenário 2: só um item tem timestamp — ele vence."""

    def setUp(self):
        with_ts = _login(password="tspass",  source="1password",
                         updated_at="2023-06-01T00:00:00+00:00")
        no_ts   = _login(password="notspass", source="chrome", updated_at=None)
        self.result = merge([[with_ts], [no_ts]])

    def test_winner_is_item_with_timestamp(self):
        self.assertEqual(self.result.items[0].fields["password"], "tspass")

    def test_no_review_conflict_when_resolved_by_timestamp(self):
        self.assertEqual(len(self.result.conflict_log), 0)


class TestMergeScenario3_NoPriorityConflict(unittest.TestCase):
    """Cenário 3: sem timestamp, passwords divergem → prioridade + requires_review."""

    def setUp(self):
        op   = _login(password="oppass",   source="1password",  updated_at=None)
        nord = _login(password="nordpass", source="nordpass",   updated_at=None)
        self.result = merge([[op], [nord]])
        self.item = self.result.items[0]

    def test_winner_by_priority(self):
        # nordpass tem prioridade maior agora
        self.assertEqual(self.item.fields["password"], "nordpass")

    def test_conflict_logged_for_review(self):
        self.assertEqual(len(self.result.conflict_log), 1)
        entry = list(self.result.conflict_log)[0]
        self.assertIn("password", entry.conflicting_fields)

    def test_review_conflict_has_both_versions(self):
        entry = list(self.result.conflict_log)[0]
        sources = {v["source"] for v in entry.versions}
        self.assertIn("1password", sources)
        self.assertIn("nordpass", sources)

    def test_review_conflict_versions_have_plaintext_fields(self):
        entry = list(self.result.conflict_log)[0]
        pw_by_source = {v["source"]: v["fields"]["password"] for v in entry.versions}
        self.assertEqual(pw_by_source["1password"], "oppass")
        self.assertEqual(pw_by_source["nordpass"], "nordpass")

    def test_loser_in_extras(self):
        losers = self.item.extras.get("_losers", [])
        # nordpass vence agora; 1password é o perdedor
        self.assertTrue(any(l["source"] == "1password" and l["field"] == "password"
                            for l in losers))

    def test_loser_value_is_hash_not_plaintext(self):
        losers = self.item.extras.get("_losers", [])
        op_loser = next(l for l in losers if l["source"] == "1password")
        self.assertEqual(
            op_loser["value_hash"],
            hashlib.sha256("oppass".encode()).hexdigest(),
        )
        self.assertNotIn("oppass", str(op_loser.get("value_hash", "")))


class TestMergeScenario4_ThreeSources(unittest.TestCase):
    """Cenário 4: 3 fontes para o mesmo login — resolução em cascata."""

    def setUp(self):
        op   = _login(password="op",   source="1password", updated_at="2023-12-01T00:00:00+00:00")
        nord = _login(password="nord", source="nordpass",  updated_at="2023-06-01T00:00:00+00:00")
        ksp  = _login(password="ksp",  source="kaspersky", updated_at=None)
        self.result = merge([[op], [nord], [ksp]])

    def test_one_output(self):
        self.assertEqual(len(self.result.items), 1)

    def test_newest_timestamp_wins(self):
        self.assertEqual(self.result.items[0].fields["password"], "op")

    def test_all_three_sources_accumulated(self):
        sources = {s.source for s in self.result.items[0].sources}
        self.assertEqual(sources, {"1password", "nordpass", "kaspersky"})


class TestMergeScenario5_NoOverlap(unittest.TestCase):
    """Cenário 5: itens sem duplicata passam direto."""

    def setUp(self):
        github = _login(url="https://github.com",  username="alice", source="1password")
        gitlab = _login(url="https://gitlab.com",  username="alice", source="nordpass",
                        title="GitLab")
        self.result = merge([[github], [gitlab]])

    def test_two_outputs(self):
        self.assertEqual(len(self.result.items), 2)

    def test_no_groups_merged(self):
        self.assertEqual(self.result.stats.groups_merged, 0)

    def test_no_conflicts(self):
        self.assertEqual(len(self.result.conflict_log), 0)

    def test_total_input_output(self):
        self.assertEqual(self.result.stats.total_input, 2)
        self.assertEqual(self.result.stats.total_output, 2)


class TestMergeScenario6_Complementation(unittest.TestCase):
    """Cenário 6: vencedor sem OTP, perdedor com OTP → merged herda OTP."""

    def setUp(self):
        winner = _login(password="newpass", source="1password",
                        updated_at="2023-11-01T00:00:00+00:00",
                        otp="")
        loser  = _login(password="oldpass", source="nordpass",
                        updated_at="2023-01-01T00:00:00+00:00",
                        otp="otpauth://totp/GitHub?secret=ABC")
        self.result = merge([[winner], [loser]])

    def test_otp_complemented(self):
        self.assertEqual(
            self.result.items[0].fields.get("otp"),
            "otpauth://totp/GitHub?secret=ABC",
        )

    def test_fields_complemented_counted(self):
        self.assertGreater(self.result.stats.fields_complemented, 0)

    def test_password_is_from_winner(self):
        self.assertEqual(self.result.items[0].fields["password"], "newpass")


class TestMergeScenario7_ReviewFileHasPlaintext(unittest.TestCase):
    """Cenário 7: arquivo de revisão contém senhas em texto claro para avaliação humana."""

    def setUp(self):
        op   = _login(password="minha_senha_secreta", source="1password", updated_at=None)
        nord = _login(password="outra_senha_secreta", source="nordpass",  updated_at=None)
        self.result = merge([[op], [nord]])

    def test_review_file_has_plaintext_passwords(self):
        json_out = self.result.conflict_log.to_json()
        self.assertIn("minha_senha_secreta", json_out)
        self.assertIn("outra_senha_secreta", json_out)

    def test_extras_losers_still_hashed(self):
        # _losers no item merged continua com hash (não é o arquivo de revisão)
        losers = self.result.items[0].extras.get("_losers", [])
        for loser in losers:
            self.assertNotIn("outra_senha_secreta", str(loser))
            self.assertIn("value_hash", loser)
            self.assertRegex(loser["value_hash"], r"^[0-9a-f]{64}$")


class TestMergeScenario8_PasswordPresenceTieBreaker(unittest.TestCase):
    """Cenário 8: sem timestamp, apenas um vault tem senha → vence sem revisão manual."""

    def test_vault_with_password_wins_over_higher_priority_without(self):
        # chrome tem prioridade baixa, mas é o único com senha
        with_pass = _login(password="mypass", source="chrome",     updated_at=None)
        no_pass   = _login(password="",       source="1password",  updated_at=None)
        result = merge([[with_pass], [no_pass]])
        self.assertEqual(result.items[0].fields["password"], "mypass")

    def test_no_review_conflict_when_only_one_has_password(self):
        with_pass = _login(password="mypass", source="chrome",    updated_at=None)
        no_pass   = _login(password="",       source="1password", updated_at=None)
        result = merge([[with_pass], [no_pass]])
        self.assertEqual(len(result.conflict_log), 0)

    def test_no_review_conflict_on_other_fields_when_only_one_has_password(self):
        # username também difere, mas como só chrome tem senha, tudo é auto-resolvido
        with_pass = _login(password="mypass", username="chrome_user", source="chrome",    updated_at=None)
        no_pass   = _login(password="",       username="op_user",     source="1password", updated_at=None)
        result = merge([[with_pass], [no_pass]])
        self.assertEqual(len(result.conflict_log), 0)
        self.assertEqual(result.items[0].fields["username"], "chrome_user")

    def test_timestamp_still_beats_password_presence(self):
        with_ts   = _login(password="",       source="1password", updated_at="2023-01-01T00:00:00+00:00")
        with_pass = _login(password="mypass", source="chrome",    updated_at=None)
        result = merge([[with_ts], [with_pass]])
        # 1password vence por timestamp mesmo sem senha; password é complementado
        self.assertEqual(result.items[0].fields["password"], "mypass")
        self.assertEqual(len(result.conflict_log), 0)


class TestMergeScenario9_SamePassword(unittest.TestCase):
    """Cenário 9: vaults com mesma senha → conflito em outros campos é auto-resolvido por prioridade."""

    def test_no_review_conflict_when_same_password(self):
        op   = _login(password="shared", username="alice_op",   source="1password", updated_at=None)
        nord = _login(password="shared", username="alice_nord", source="nordpass",  updated_at=None)
        result = merge([[op], [nord]])
        self.assertEqual(len(result.conflict_log), 0)

    def test_priority_decides_when_same_password(self):
        # Mesma conta (mesmo username/url → mesma primary_key), mesma senha,
        # campo extra diverge → nordpass vence por prioridade
        op   = _login(password="shared", source="1password", updated_at=None, extra="op_val")
        nord = _login(password="shared", source="nordpass",  updated_at=None, extra="nord_val")
        result = merge([[op], [nord]])
        self.assertEqual(result.items[0].fields["extra"], "nord_val")

    def test_different_passwords_still_requires_review(self):
        op   = _login(password="pass1", source="1password", updated_at=None)
        nord = _login(password="pass2", source="nordpass",  updated_at=None)
        result = merge([[op], [nord]])
        self.assertGreater(len(result.conflict_log), 0)


class TestMergeScenario10_IgnoreBlankPasswordVaultsInConflict(unittest.TestCase):
    """Cenário 10: em conflitos multi-vault, vaults sem senha são ignorados na resolução."""

    def test_blank_password_vault_ignored_in_three_way_conflict(self):
        # 1password e nordpass têm senhas diferentes; chrome não tem senha
        # Apenas 1password vs nordpass devem ser considerados
        op   = _login(password="pass_op",   username="alice", source="1password", updated_at=None)
        nord = _login(password="pass_nord", username="alice", source="nordpass",  updated_at=None)
        chrome = _login(password="",        username="alice", source="chrome",    updated_at=None)
        result = merge([[op], [nord], [chrome]])
        # Conflito genuíno entre op e nord (senhas diferentes) → revisão necessária
        self.assertGreater(len(result.conflict_log), 0)
        entry = list(result.conflict_log)[0]
        # chrome (sem senha) não deve estar nos conflicting versions considerados
        # o winner foi eleito por prioridade entre os que têm senha
        sources_with_conflict = {v["source"] for v in entry.versions if bool(v["fields"].get("password"))}
        self.assertIn("1password", sources_with_conflict)
        self.assertIn("nordpass", sources_with_conflict)

    def test_only_one_vault_has_password_among_three_no_conflict(self):
        # Apenas 1password tem senha → vence sem revisão, outros são ignorados
        # username default igual nos três → mesma primary_key → agrupados
        op     = _login(password="secret", source="1password", updated_at=None)
        nord   = _login(password="",       source="nordpass",  updated_at=None)
        chrome = _login(password="",       source="chrome",    updated_at=None)
        result = merge([[op], [nord], [chrome]])
        self.assertEqual(len(result.conflict_log), 0)
        self.assertEqual(result.items[0].fields["password"], "secret")

    def test_same_password_among_password_vaults_no_conflict(self):
        # 1password e nordpass têm mesma senha; chrome não tem → sem revisão
        # username default igual nos três → mesma primary_key → agrupados
        op     = _login(password="shared", source="1password", updated_at=None)
        nord   = _login(password="shared", source="nordpass",  updated_at=None)
        chrome = _login(password="",       source="chrome",    updated_at=None)
        result = merge([[op], [nord], [chrome]])
        self.assertEqual(len(result.conflict_log), 0)


class TestMergeScenario11_ComplementationAlwaysApplies(unittest.TestCase):
    """Cenário 10: campos únicos dos perdedores sempre enriquecem o registro final.

    Nota: o matching de LOGINs usa domínio da URL + username como chave primária.
    Para serem agrupados, os itens devem ter o mesmo domínio (ou ambos sem URL).
    """

    def test_password_from_winner_otp_from_loser(self):
        # Mesma URL (mesmo domínio → mesma chave), 1password tem senha, chrome tem OTP
        op     = _login(password="secret", source="1password", updated_at=None)
        chrome = _login(password="",       source="chrome",    updated_at=None,
                        otp="otpauth://totp/GitHub?secret=ABC")
        result = merge([[op], [chrome]])
        item = result.items[0]
        self.assertEqual(item.fields["password"], "secret")
        self.assertEqual(item.fields["otp"], "otpauth://totp/GitHub?secret=ABC")
        self.assertEqual(len(result.conflict_log), 0)

    def test_extra_fields_complemented_when_same_password(self):
        # Mesma senha + mesmo domínio → sem conflito; campo extra do perdedor é herdado
        op   = _login(password="shared", source="1password", updated_at=None)
        nord = _login(password="shared", source="nordpass",  updated_at=None,
                      notes_field="nota importante")
        result = merge([[op], [nord]])
        item = result.items[0]
        self.assertEqual(item.fields.get("notes_field"), "nota importante")
        self.assertEqual(len(result.conflict_log), 0)

    def test_complementation_counted_in_stats(self):
        op     = _login(password="secret", source="1password", updated_at=None)
        chrome = _login(password="",       source="chrome",    updated_at=None,
                        otp="otpauth://totp/GitHub?secret=ABC")
        result = merge([[op], [chrome]])
        self.assertGreater(result.stats.fields_complemented, 0)


class TestMergeStats(unittest.TestCase):
    def test_single_source_no_merge(self):
        item = _login(source="1password")
        result = merge([[item]])
        self.assertEqual(result.stats.total_input, 1)
        self.assertEqual(result.stats.total_output, 1)
        self.assertEqual(result.stats.groups_merged, 0)

    def test_tags_union(self):
        a = _login(source="1password", updated_at="2023-11-01T00:00:00+00:00")
        a.tags = ["dev", "git"]
        b = _login(source="nordpass",  updated_at="2023-01-01T00:00:00+00:00")
        b.tags = ["git", "work"]
        result = merge([[a], [b]])
        tags = set(result.items[0].tags)
        self.assertIn("dev", tags)
        self.assertIn("git", tags)
        self.assertIn("work", tags)

    def test_favorite_union(self):
        a = _login(source="1password", updated_at="2023-11-01T00:00:00+00:00")
        a.favorite = False
        b = _login(source="nordpass",  updated_at="2023-01-01T00:00:00+00:00")
        b.favorite = True
        result = merge([[a], [b]])
        self.assertTrue(result.items[0].favorite)


if __name__ == "__main__":
    unittest.main()

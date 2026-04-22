"""Testes do comando `passmerge schema`."""
import json
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from passmerge.cli import (
    _schema_filter,
    _schema_is_empty,
    _schema_merge,
    cmd_schema,
)

FIXTURE = Path(__file__).parent / "fixtures" / "onepassword_test.1pux"


def _run(extra_args: list[str]) -> tuple[int, str]:
    """Executa cmd_schema capturando stdout."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--category", default=None)
    args = parser.parse_args(extra_args)

    buf = StringIO()
    with patch("sys.stdout", buf):
        rc = cmd_schema(args)
    return rc, buf.getvalue()


class TestSchemaHelpers(unittest.TestCase):
    def test_is_empty(self):
        self.assertTrue(_schema_is_empty(None))
        self.assertTrue(_schema_is_empty(""))
        self.assertTrue(_schema_is_empty([]))
        self.assertFalse(_schema_is_empty(0))
        self.assertFalse(_schema_is_empty(False))
        self.assertFalse(_schema_is_empty("x"))
        self.assertFalse(_schema_is_empty([1]))
        self.assertFalse(_schema_is_empty({"a": 1}))

    def test_filter_removes_empty_scalars(self):
        result = _schema_filter({"a": "x", "b": "", "c": None, "d": []})
        self.assertEqual(result, {"a": "x"})

    def test_filter_recursive(self):
        v = {"outer": {"inner": "", "keep": "val"}, "empty_list": []}
        result = _schema_filter(v)
        self.assertEqual(result, {"outer": {"keep": "val"}})

    def test_filter_nested_list_of_dicts(self):
        v = [{"a": "x", "b": ""}, {"a": "", "c": "z"}]
        result = _schema_filter(v)
        self.assertEqual(result, [{"a": "x"}, {"c": "z"}])

    def test_filter_all_empty_returns_none(self):
        self.assertIsNone(_schema_filter({"a": "", "b": None}))
        self.assertIsNone(_schema_filter([]))
        self.assertIsNone(_schema_filter(""))

    def test_merge_adds_new_keys(self):
        a = {"x": 1}
        b = {"y": 2}
        self.assertEqual(_schema_merge(a, b), {"x": 1, "y": 2})

    def test_merge_recursive_dicts(self):
        a = {"d": {"k1": "v1"}}
        b = {"d": {"k2": "v2"}}
        result = _schema_merge(a, b)
        self.assertEqual(result, {"d": {"k1": "v1", "k2": "v2"}})

    def test_merge_skips_empty_in_b(self):
        a = {"x": 1}
        b = {"y": "", "z": None}
        self.assertEqual(_schema_merge(a, b), {"x": 1})

    def test_merge_list_of_dicts_unions(self):
        a = [{"designation": "username", "value": "user"}]
        b = [{"designation": "password", "value": "pass"}]
        result = _schema_merge(a, b)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        merged = result[0]
        self.assertIn("designation", merged)
        self.assertIn("value", merged)

    def test_merge_empty_a_returns_b(self):
        self.assertEqual(_schema_merge({}, {"x": 1}), {"x": 1})
        self.assertEqual(_schema_merge(None, "val"), "val")

    def test_merge_empty_b_returns_a(self):
        self.assertEqual(_schema_merge({"x": 1}, {}), {"x": 1})
        self.assertEqual(_schema_merge("val", None), "val")


class TestCmdSchema(unittest.TestCase):
    def test_returns_zero(self):
        rc, _ = _run(["--file", str(FIXTURE)])
        self.assertEqual(rc, 0)

    def test_output_contains_known_categories(self):
        _, out = _run(["--file", str(FIXTURE)])
        self.assertIn("LOGIN", out)
        self.assertIn("CREDIT_CARD", out)
        self.assertIn("SECURE_NOTE", out)
        self.assertIn("SERVER", out)
        self.assertIn("WIRELESS", out)

    def test_output_is_valid_json_per_category(self):
        _, out = _run(["--file", str(FIXTURE)])
        # Extract JSON blocks: lines between separators
        lines = out.split("\n")
        json_lines: list[str] = []
        in_block = False
        for line in lines:
            if line.startswith("{") or in_block:
                in_block = True
                json_lines.append(line)
            if in_block and line == "}":
                in_block = False
                json.loads("\n".join(json_lines))
                json_lines = []

    def test_no_empty_fields_in_output(self):
        _, out = _run(["--file", str(FIXTURE)])
        # No empty string, null, or [] values in JSON output
        self.assertNotIn(': ""', out)
        self.assertNotIn(': null', out)
        self.assertNotIn(': []', out)

    def test_login_schema_has_expected_fields(self):
        _, out = _run(["--file", str(FIXTURE), "--category", "login"])
        self.assertIn("LOGIN", out)
        self.assertIn("uuid", out)
        self.assertIn("loginFields", out)
        self.assertIn("overview", out)
        # OTP present (merged from login-item-001)
        self.assertIn("TOTP", out)

    def test_login_merges_multiple_items(self):
        # Fixture has 2 non-trashed logins (plus 1 trashed which still appears in raw)
        # Both should be merged into single schema
        _, out = _run(["--file", str(FIXTURE), "--category", "login"])
        # login-item-001 has tags and login-item-002 has unicode title
        # Both urls from overview should appear in merged schema
        self.assertIn("github.com", out)

    def test_category_filter_excludes_others(self):
        _, out = _run(["--file", str(FIXTURE), "--category", "credit_card"])
        self.assertIn("CREDIT_CARD", out)
        self.assertNotIn("LOGIN", out)
        self.assertNotIn("SERVER", out)

    def test_unknown_category_returns_nonzero(self):
        rc, _ = _run(["--file", str(FIXTURE), "--category", "nonexistent"])
        self.assertNotEqual(rc, 0)

    def test_invalid_file_returns_nonzero(self):
        rc, _ = _run(["--file", "/tmp/does_not_exist.1pux"])
        self.assertNotEqual(rc, 0)

    def test_trashed_item_included_in_schema(self):
        # The schema command shows raw structure — trashed items still appear
        _, out = _run(["--file", str(FIXTURE), "--category", "login"])
        # trashed-item-001 contributes "trashed": "Y" to the LOGIN schema
        self.assertIn('"trashed"', out)


if __name__ == "__main__":
    unittest.main()

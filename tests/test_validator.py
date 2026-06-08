"""Tests for the functional validate() API (stdlib unittest only)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from llm_output_validator import Rule, ValidationError, validate  # noqa: E402


TEXT = "Summary: The Eiffel Tower is in Paris. It was built in 1889."


class TestInlineKwargs(unittest.TestCase):
    """validate() driven purely by keyword arguments."""

    def test_all_pass(self):
        result = validate(TEXT)
        self.assertTrue(result.ok)
        self.assertEqual(result.rule_count, 0)

    def test_must_contain_pass(self):
        self.assertTrue(validate(TEXT, must_contain="Eiffel").ok)

    def test_must_contain_fail(self):
        self.assertFalse(validate(TEXT, must_contain="Berlin").ok)

    def test_must_contain_case_insensitive(self):
        self.assertTrue(validate(TEXT, must_contain="EIFFEL").ok)

    def test_must_contain_case_sensitive_fail(self):
        self.assertFalse(validate(TEXT, must_contain="eiffel", case_sensitive=True).ok)

    def test_must_not_contain_pass(self):
        self.assertTrue(validate(TEXT, must_not_contain="Berlin").ok)

    def test_must_not_contain_fail(self):
        self.assertFalse(validate(TEXT, must_not_contain="Eiffel").ok)

    def test_min_length_pass(self):
        self.assertTrue(validate(TEXT, min_length=10).ok)

    def test_min_length_fail(self):
        self.assertFalse(validate("hi", min_length=100).ok)

    def test_max_length_pass(self):
        self.assertTrue(validate(TEXT, max_length=1000).ok)

    def test_max_length_fail(self):
        self.assertFalse(validate(TEXT, max_length=5).ok)

    def test_matches_regex_pass(self):
        self.assertTrue(validate(TEXT, matches_regex=r"^Summary:").ok)

    def test_matches_regex_fail(self):
        self.assertFalse(validate(TEXT, matches_regex=r"^\d+").ok)

    def test_not_matches_regex_pass(self):
        self.assertTrue(validate(TEXT, not_matches_regex=r"\bBerlin\b").ok)

    def test_not_matches_regex_fail(self):
        self.assertFalse(validate(TEXT, not_matches_regex=r"\bParis\b").ok)

    def test_multiple_inline_and(self):
        result = validate(TEXT, must_contain="Paris", min_length=10, max_length=500)
        self.assertTrue(result.ok)

    def test_multiple_inline_one_fails(self):
        result = validate(TEXT, must_contain="Paris", must_not_contain="Paris")
        self.assertFalse(result.ok)


class TestRuleObjects(unittest.TestCase):
    """validate() driven by explicit Rule objects."""

    def test_rules_list(self):
        rules = [
            Rule("has_summary", must_contain="Summary:"),
            Rule("min_length", min_length=10),
        ]
        result = validate(TEXT, rules=rules)
        self.assertTrue(result.ok)
        self.assertEqual(result.rule_count, 2)

    def test_rules_failure(self):
        rules = [
            Rule("no_berlin", must_not_contain="Berlin"),
            Rule("has_berlin", must_contain="Berlin"),
        ]
        result = validate(TEXT, rules=rules)
        self.assertFalse(result.ok)
        self.assertIn("has_berlin", result.failed_rules)

    def test_rules_and_inline_combined(self):
        rules = [Rule("has_summary", must_contain="Summary:")]
        result = validate(TEXT, rules=rules, min_length=10)
        self.assertEqual(result.rule_count, 2)
        self.assertTrue(result.ok)


class TestValidationResult(unittest.TestCase):
    def test_result_failures_list(self):
        result = validate("hi", must_contain="Summary:", min_length=100)
        self.assertEqual(len(result.failures), 2)
        self.assertTrue(
            all(isinstance(f, tuple) and len(f) == 2 for f in result.failures)
        )

    def test_result_failure_count(self):
        result = validate("x", min_length=100, max_length=0)
        self.assertEqual(result.failure_count, 2)

    def test_result_failed_rules(self):
        rules = [Rule("r1", must_contain="X"), Rule("r2", must_contain="Y")]
        result = validate("hello", rules=rules)
        self.assertEqual(set(result.failed_rules), {"r1", "r2"})

    def test_result_bool_true(self):
        self.assertTrue(bool(validate(TEXT)))

    def test_result_bool_false(self):
        self.assertFalse(bool(validate("x", must_contain="Z")))

    def test_result_summary_ok(self):
        result = validate(TEXT, must_contain="Paris")
        self.assertIn("passed", result.summary())

    def test_result_summary_fail(self):
        result = validate("x", must_contain="Berlin")
        self.assertIn("failed", result.summary().lower())

    def test_result_text_stored(self):
        self.assertEqual(validate(TEXT).text, TEXT)


class TestRuleCheck(unittest.TestCase):
    def test_rule_check_no_failures(self):
        r = Rule("r", must_contain="Paris")
        self.assertEqual(r.check(TEXT), [])

    def test_rule_check_failure(self):
        r = Rule("r", must_contain="Berlin")
        self.assertEqual(len(r.check(TEXT)), 1)

    def test_rule_custom_message(self):
        r = Rule("r", must_contain="Berlin", message="City must be Berlin")
        self.assertEqual(r.check(TEXT)[0], "City must be Berlin")

    def test_rule_multiple_checks(self):
        r = Rule("r", must_contain="Berlin", min_length=100000)
        self.assertEqual(len(r.check(TEXT)), 2)


class TestErrorCases(unittest.TestCase):
    def test_invalid_regex_raises(self):
        with self.assertRaises(ValidationError):
            validate(TEXT, matches_regex="[invalid")

    def test_invalid_not_regex_raises(self):
        r = Rule("r", not_matches_regex="[bad")
        with self.assertRaises(ValidationError):
            r.check(TEXT)

    def test_empty_text_min_length(self):
        self.assertFalse(validate("", min_length=1).ok)

    def test_empty_text_no_rules(self):
        self.assertTrue(validate("").ok)


if __name__ == "__main__":
    unittest.main()

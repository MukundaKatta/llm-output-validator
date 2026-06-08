"""Tests for the OutputValidator object API and rule factories.

Uses only the Python standard library (unittest); no third-party deps.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from llm_output_validator import (  # noqa: E402
    OutputValidationError,
    OutputValidator,
    RuleResult,
    RuleSpec,
    rules,
)


class TestOutputValidator(unittest.TestCase):
    def test_all_rules_pass(self):
        v = OutputValidator([
            rules.length(min_chars=1, max_chars=100),
            rules.regex_must_match(r"hello"),
        ])
        result = v.check("hello world")
        self.assertTrue(result.ok)
        self.assertEqual(result.failed_rules, [])

    def test_no_short_circuit_collects_all_failures(self):
        v = OutputValidator([
            rules.length(min_chars=100),
            rules.regex_must_match(r"absent-token"),
        ])
        result = v.check("short")
        self.assertFalse(result.ok)
        self.assertEqual(set(result.failed_rules), {"length", "regex_must_match"})
        # every rule should have a detail entry, even passing ones
        self.assertEqual(set(result.details), {"length", "regex_must_match"})

    def test_details_contain_messages(self):
        v = OutputValidator([rules.length(min_chars=10)])
        result = v.check("hi")
        self.assertFalse(result.details["length"].passed)
        self.assertIn("min 10", result.details["length"].message)

    def test_rules_property_is_copy(self):
        rule = rules.length(min_chars=1)
        v = OutputValidator([rule])
        got = v.rules
        got.clear()
        # mutating the returned list must not affect the validator
        self.assertEqual(len(v.rules), 1)

    def test_duplicate_rule_names_rejected(self):
        with self.assertRaises(ValueError):
            OutputValidator([rules.length(min_chars=1), rules.length(max_chars=5)])

    def test_non_rule_rejected(self):
        with self.assertRaises(TypeError):
            OutputValidator(["not a rule"])

    def test_check_rejects_non_str(self):
        v = OutputValidator([rules.length(min_chars=1)])
        with self.assertRaises(TypeError):
            v.check(123)  # type: ignore[arg-type]


class TestCheckOrRaise(unittest.TestCase):
    def test_passes_silently(self):
        v = OutputValidator([rules.length(min_chars=1)])
        self.assertIsNone(v.check_or_raise("ok"))

    def test_raises_on_failure(self):
        v = OutputValidator([rules.length(min_chars=100)])
        with self.assertRaises(OutputValidationError) as ctx:
            v.check_or_raise("short")
        err = ctx.exception
        self.assertIn("length", err.failed_rules)
        self.assertIn("length", err.details)
        self.assertIn("length", str(err))


class TestLengthRules(unittest.TestCase):
    def test_min_and_max(self):
        r = rules.length(min_chars=2, max_chars=4)
        self.assertTrue(r.check("abc").passed)
        self.assertFalse(r.check("a").passed)
        self.assertFalse(r.check("abcde").passed)

    def test_invalid_bounds_rejected(self):
        with self.assertRaises(ValueError):
            rules.length(min_chars=-1)
        with self.assertRaises(ValueError):
            rules.length(min_chars=5, max_chars=2)

    def test_length_words(self):
        r = rules.length_words(min_words=2, max_words=3)
        self.assertTrue(r.check("two words").passed)
        self.assertFalse(r.check("one").passed)
        self.assertFalse(r.check("a b c d").passed)


class TestRegexRules(unittest.TestCase):
    def test_must_match(self):
        r = rules.regex_must_match(r"\d{4}")
        self.assertTrue(r.check("year 1889").passed)
        self.assertFalse(r.check("no digits").passed)

    def test_must_not_match(self):
        r = rules.regex_must_not_match(r"BEGIN PRIVATE KEY")
        self.assertTrue(r.check("clean text").passed)
        result = r.check("-----BEGIN PRIVATE KEY-----")
        self.assertFalse(result.passed)
        self.assertIn("BEGIN PRIVATE KEY", result.message)

    def test_accepts_compiled_pattern(self):
        import re

        r = rules.regex_must_match(re.compile(r"abc", re.IGNORECASE))
        self.assertTrue(r.check("xxABCxx").passed)


class TestAllowedValues(unittest.TestCase):
    def test_case_sensitive(self):
        r = rules.allowed_values(["yes", "no"])
        self.assertTrue(r.check("yes").passed)
        self.assertFalse(r.check("YES").passed)
        self.assertFalse(r.check("maybe").passed)

    def test_case_insensitive(self):
        r = rules.allowed_values(["yes", "no"], case_sensitive=False)
        self.assertTrue(r.check("YES").passed)
        self.assertTrue(r.check("No").passed)
        self.assertFalse(r.check("maybe").passed)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            rules.allowed_values([])

    def test_non_str_rejected(self):
        with self.assertRaises(TypeError):
            rules.allowed_values(["a", 1])  # type: ignore[list-item]


class TestPrefixSuffix(unittest.TestCase):
    def test_starts_with(self):
        r = rules.starts_with("Summary:")
        self.assertTrue(r.check("Summary: done").passed)
        self.assertFalse(r.check("no prefix").passed)

    def test_ends_with(self):
        r = rules.ends_with("</xml>")
        self.assertTrue(r.check("<xml>...</xml>").passed)
        self.assertFalse(r.check("incomplete").passed)

    def test_type_errors(self):
        with self.assertRaises(TypeError):
            rules.starts_with(123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            rules.ends_with(123)  # type: ignore[arg-type]


class TestNoPII(unittest.TestCase):
    def test_clean_text_passes(self):
        self.assertTrue(rules.no_pii().check("just an ordinary sentence").passed)

    def test_email_detected(self):
        result = rules.no_pii().check("reach me at user@example.com please")
        self.assertFalse(result.passed)
        self.assertIn("email", result.message)

    def test_ssn_detected(self):
        result = rules.no_pii(["ssn"]).check("ssn 123-45-6789")
        self.assertFalse(result.passed)

    def test_restricted_type_ignores_others(self):
        # only checking email; a phone number should not trip it
        self.assertTrue(rules.no_pii(["email"]).check("call 555-123-4567").passed)

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            rules.no_pii(["passport"])

    def test_empty_types_rejected(self):
        with self.assertRaises(ValueError):
            rules.no_pii([])


class TestJSONRules(unittest.TestCase):
    def test_parseable_pass(self):
        self.assertTrue(rules.json_parseable().check('{"a": 1}').passed)

    def test_parseable_fail(self):
        result = rules.json_parseable().check("not json")
        self.assertFalse(result.passed)
        self.assertIn("json.loads failed", result.message)

    def test_json_schema_requires_optional_dep(self):
        # jsonschema is an optional extra; in the test env it is absent, so
        # constructing the rule should raise ImportError. If it ever becomes
        # available, the rule should build instead. Accept either outcome.
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            with self.assertRaises(ImportError):
                rules.json_schema({"type": "object"})
        else:  # pragma: no cover - depends on optional install
            rule = rules.json_schema({"type": "object"})
            self.assertTrue(rule.check("{}").passed)
            self.assertFalse(rule.check("[]").passed)


class TestCustomRule(unittest.TestCase):
    def test_bool_return(self):
        r = rules.custom("is_upper", lambda t: t.isupper())
        self.assertTrue(r.check("HELLO").passed)
        self.assertFalse(r.check("hello").passed)

    def test_ruleresult_return(self):
        r = rules.custom("len5", lambda t: RuleResult(len(t) == 5, "need len 5"))
        self.assertTrue(r.check("hello").passed)
        self.assertEqual(r.check("hi").message, "need len 5")

    def test_invalid_return_type(self):
        r = rules.custom("bad", lambda t: 42)  # type: ignore[return-value, arg-type]
        with self.assertRaises(TypeError):
            r.check("x")

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            rules.custom("", lambda t: True)

    def test_non_callable_rejected(self):
        with self.assertRaises(TypeError):
            rules.custom("x", "not callable")  # type: ignore[arg-type]


class TestRuleSpecExport(unittest.TestCase):
    def test_rule_factories_return_rulespec(self):
        self.assertIsInstance(rules.length(min_chars=1), RuleSpec)


if __name__ == "__main__":
    unittest.main()

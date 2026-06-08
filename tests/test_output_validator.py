"""Tests for the OutputValidator rule-engine API and the rules factories."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest

from llm_output_validator import (
    CallableRule,
    OutputValidationError,
    OutputValidator,
    RuleResult,
    rules,
)


# ---------------------------------------------------------------------------
# OutputValidator
# ---------------------------------------------------------------------------


def test_all_rules_pass():
    v = OutputValidator([rules.length(min_chars=1), rules.starts_with("ok")])
    result = v.check("ok done")
    assert result.ok is True
    assert result.failed_rules == []


def test_collects_every_failure_no_short_circuit():
    v = OutputValidator(
        [rules.length(min_chars=100), rules.starts_with("X"), rules.ends_with("Z")]
    )
    result = v.check("hi")
    assert result.ok is False
    assert result.failed_rules == ["length", "starts_with", "ends_with"]
    # details are recorded for every rule, including the ones that passed
    assert set(result.details) == {"length", "starts_with", "ends_with"}


def test_check_rejects_non_str():
    v = OutputValidator([rules.length(min_chars=1)])
    with pytest.raises(TypeError):
        v.check(123)  # type: ignore[arg-type]


def test_duplicate_rule_names_rejected():
    with pytest.raises(ValueError, match="duplicate rule name"):
        OutputValidator([rules.length(min_chars=1), rules.length(max_chars=5)])


def test_non_rule_rejected():
    with pytest.raises(TypeError):
        OutputValidator(["not a rule"])  # type: ignore[list-item]


def test_rules_property_is_a_copy():
    rule = rules.length(min_chars=1)
    v = OutputValidator([rule])
    snapshot = v.rules
    snapshot.clear()
    assert len(v.rules) == 1


def test_check_or_raise_passes_silently():
    v = OutputValidator([rules.length(min_chars=1)])
    assert v.check_or_raise("hello") is None


def test_check_or_raise_raises_with_details():
    v = OutputValidator([rules.length(min_chars=100)])
    with pytest.raises(OutputValidationError) as exc:
        v.check_or_raise("short")
    assert exc.value.failed_rules == ["length"]
    assert "length" in exc.value.details


# ---------------------------------------------------------------------------
# rules factories
# ---------------------------------------------------------------------------


def test_length_bounds():
    r = rules.length(min_chars=2, max_chars=4)
    assert r.check("abc").passed is True
    assert r.check("a").passed is False
    assert r.check("abcde").passed is False


def test_length_invalid_bounds():
    with pytest.raises(ValueError):
        rules.length(min_chars=5, max_chars=1)


def test_length_words():
    r = rules.length_words(min_words=2, max_words=3)
    assert r.check("two words").passed is True
    assert r.check("one").passed is False
    assert r.check("a b c d").passed is False


def test_regex_must_match():
    r = rules.regex_must_match(r"\d{4}")
    assert r.check("year 2024").passed is True
    assert r.check("no digits").passed is False


def test_regex_must_not_match():
    r = rules.regex_must_not_match(r"BEGIN")
    assert r.check("clean").passed is True
    assert r.check("BEGIN secret").passed is False


def test_allowed_values_case_sensitive():
    r = rules.allowed_values(["yes", "no"])
    assert r.check("yes").passed is True
    assert r.check("Yes").passed is False
    assert r.check("maybe").passed is False


def test_allowed_values_case_insensitive():
    r = rules.allowed_values(["yes", "no"], case_sensitive=False)
    assert r.check("YES").passed is True


def test_allowed_values_empty_raises():
    with pytest.raises(ValueError):
        rules.allowed_values([])


def test_starts_and_ends_with():
    assert rules.starts_with("Sum").check("Summary").passed is True
    assert rules.starts_with("Sum").check("nope").passed is False
    assert rules.ends_with(".").check("done.").passed is True
    assert rules.ends_with(".").check("done").passed is False


def test_no_pii_detects_email():
    r = rules.no_pii()
    assert r.check("contact me@example.com").passed is False
    assert r.check("no contact info here").passed is True


def test_no_pii_restricted_types():
    r = rules.no_pii(types=["email"])
    # a phone-like string should not trip an email-only check
    assert r.check("call 555-123-4567").passed is True
    assert r.check("a@b.co").passed is False


def test_no_pii_unknown_type_raises():
    with pytest.raises(ValueError):
        rules.no_pii(types=["passport"])


def test_json_parseable():
    r = rules.json_parseable()
    assert r.check('{"a": 1}').passed is True
    assert r.check("not json").passed is False


def test_custom_bool_return():
    r = rules.custom("is_upper", lambda t: t.isupper())
    assert r.check("HELLO").passed is True
    assert r.check("hello").passed is False


def test_custom_ruleresult_return():
    r = rules.custom("never", lambda t: RuleResult(False, "always fails"))
    res = r.check("anything")
    assert res.passed is False
    assert res.message == "always fails"


def test_custom_bad_return_raises():
    r = rules.custom("bad", lambda t: "not a bool")
    with pytest.raises(TypeError):
        r.check("x")


def test_callable_rule_is_exported_type():
    r = rules.length(min_chars=1)
    assert isinstance(r, CallableRule)


# ---------------------------------------------------------------------------
# json_schema (optional jsonschema dependency)
# ---------------------------------------------------------------------------

jsonschema = pytest.importorskip("jsonschema")


def test_json_schema_valid_and_invalid():
    r = rules.json_schema(
        {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
    )
    assert r.check('{"name": "ada"}').passed is True
    missing = r.check("{}")
    assert missing.passed is False
    assert "required" in (missing.message or "")
    assert r.check("not json").passed is False


def test_json_schema_rejects_malformed_schema():
    with pytest.raises(ValueError):
        rules.json_schema({"type": "not-a-real-type"})

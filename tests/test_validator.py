"""Tests for llm-output-validator."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest
from llm_output_validator import Rule, ValidationError, ValidationResult, validate


TEXT = "Summary: The Eiffel Tower is in Paris. It was built in 1889."


# ---------------------------------------------------------------------------
# validate() — inline kwargs
# ---------------------------------------------------------------------------

def test_all_pass():
    result = validate(TEXT)
    assert result.ok is True
    assert result.rule_count == 0

def test_must_contain_pass():
    result = validate(TEXT, must_contain="Eiffel")
    assert result.ok is True

def test_must_contain_fail():
    result = validate(TEXT, must_contain="Berlin")
    assert result.ok is False

def test_must_contain_case_insensitive():
    result = validate(TEXT, must_contain="EIFFEL")
    assert result.ok is True

def test_must_contain_case_sensitive_fail():
    result = validate(TEXT, must_contain="eiffel", case_sensitive=True)
    assert result.ok is False

def test_must_not_contain_pass():
    result = validate(TEXT, must_not_contain="Berlin")
    assert result.ok is True

def test_must_not_contain_fail():
    result = validate(TEXT, must_not_contain="Eiffel")
    assert result.ok is False

def test_min_length_pass():
    result = validate(TEXT, min_length=10)
    assert result.ok is True

def test_min_length_fail():
    result = validate("hi", min_length=100)
    assert result.ok is False

def test_max_length_pass():
    result = validate(TEXT, max_length=1000)
    assert result.ok is True

def test_max_length_fail():
    result = validate(TEXT, max_length=5)
    assert result.ok is False

def test_matches_regex_pass():
    result = validate(TEXT, matches_regex=r"^Summary:")
    assert result.ok is True

def test_matches_regex_fail():
    result = validate(TEXT, matches_regex=r"^\d+")
    assert result.ok is False

def test_not_matches_regex_pass():
    result = validate(TEXT, not_matches_regex=r"\bBerlin\b")
    assert result.ok is True

def test_not_matches_regex_fail():
    result = validate(TEXT, not_matches_regex=r"\bParis\b")
    assert result.ok is False

def test_multiple_inline_and():
    result = validate(TEXT, must_contain="Paris", min_length=10, max_length=500)
    assert result.ok is True

def test_multiple_inline_one_fails():
    result = validate(TEXT, must_contain="Paris", must_not_contain="Paris")
    assert result.ok is False


# ---------------------------------------------------------------------------
# validate() — Rule objects
# ---------------------------------------------------------------------------

def test_rules_list():
    rules = [
        Rule("has_summary", must_contain="Summary:"),
        Rule("min_length", min_length=10),
    ]
    result = validate(TEXT, rules=rules)
    assert result.ok is True
    assert result.rule_count == 2

def test_rules_failure():
    rules = [
        Rule("no_berlin", must_not_contain="Berlin"),
        Rule("has_berlin", must_contain="Berlin"),
    ]
    result = validate(TEXT, rules=rules)
    assert result.ok is False
    assert "has_berlin" in result.failed_rules

def test_rules_and_inline_combined():
    rules = [Rule("has_summary", must_contain="Summary:")]
    result = validate(TEXT, rules=rules, min_length=10)
    assert result.rule_count == 2
    assert result.ok is True


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

def test_result_failures_list():
    result = validate("hi", must_contain="Summary:", min_length=100)
    assert len(result.failures) == 2
    assert all(isinstance(f, tuple) and len(f) == 2 for f in result.failures)

def test_result_failure_count():
    result = validate("x", min_length=100, max_length=0)
    assert result.failure_count == 2

def test_result_failed_rules():
    rules = [Rule("r1", must_contain="X"), Rule("r2", must_contain="Y")]
    result = validate("hello", rules=rules)
    assert set(result.failed_rules) == {"r1", "r2"}

def test_result_bool_true():
    result = validate(TEXT)
    assert bool(result) is True

def test_result_bool_false():
    result = validate("x", must_contain="Z")
    assert bool(result) is False

def test_result_summary_ok():
    result = validate(TEXT, must_contain="Paris")
    assert "passed" in result.summary()

def test_result_summary_fail():
    result = validate("x", must_contain="Berlin")
    text = result.summary()
    assert "failed" in text.lower()

def test_result_text_stored():
    result = validate(TEXT)
    assert result.text == TEXT


# ---------------------------------------------------------------------------
# Rule.check() directly
# ---------------------------------------------------------------------------

def test_rule_check_no_failures():
    r = Rule("r", must_contain="Paris")
    assert r.check(TEXT) == []

def test_rule_check_failure():
    r = Rule("r", must_contain="Berlin")
    failures = r.check(TEXT)
    assert len(failures) == 1

def test_rule_custom_message():
    r = Rule("r", must_contain="Berlin", message="City must be Berlin")
    failures = r.check(TEXT)
    assert failures[0] == "City must be Berlin"

def test_rule_multiple_checks():
    r = Rule("r", must_contain="Berlin", min_length=100000)
    failures = r.check(TEXT)
    assert len(failures) == 2


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_invalid_regex_raises():
    with pytest.raises(ValidationError, match="invalid regex"):
        validate(TEXT, matches_regex="[invalid")

def test_invalid_not_regex_raises():
    r = Rule("r", not_matches_regex="[bad")
    with pytest.raises(ValidationError):
        r.check(TEXT)

def test_empty_text_min_length():
    result = validate("", min_length=1)
    assert result.ok is False

def test_empty_text_no_rules():
    result = validate("")
    assert result.ok is True

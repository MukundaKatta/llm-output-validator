"""Tests for OutputValidator core (aggregation, ordering, raise path)."""

from __future__ import annotations

import pytest

from llm_output_validator import (
    OutputValidationError,
    OutputValidator,
    Rule,
    RuleResult,
    ValidationResult,
    rules,
)


def _always_pass(name: str = "always_pass") -> Rule:
    return Rule(name=name, check=lambda _t: RuleResult(True))


def _always_fail(name: str = "always_fail", msg: str = "nope") -> Rule:
    return Rule(name=name, check=lambda _t: RuleResult(False, msg))


# ---- happy path / aggregation ----


def test_all_rules_pass_yields_ok():
    v = OutputValidator(
        [
            rules.length(min_chars=1),
            rules.starts_with("H"),
            rules.regex_must_match(r"world"),
        ]
    )
    result = v.check("Hello world")
    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.failed_rules == []
    assert set(result.details.keys()) == {"length", "starts_with", "regex_must_match"}
    assert all(d.passed for d in result.details.values())


def test_single_failure_reports_just_that_rule():
    v = OutputValidator(
        [
            rules.length(min_chars=1),
            rules.starts_with("Z"),  # fails
            rules.regex_must_match(r"world"),
        ]
    )
    result = v.check("Hello world")
    assert result.ok is False
    assert result.failed_rules == ["starts_with"]
    assert result.details["starts_with"].passed is False
    assert result.details["length"].passed is True


def test_multiple_failures_all_collected_in_declared_order():
    v = OutputValidator(
        [
            _always_fail("first_fail", "msg1"),
            _always_pass("middle_ok"),
            _always_fail("last_fail", "msg2"),
        ]
    )
    result = v.check("anything")
    assert result.ok is False
    assert result.failed_rules == ["first_fail", "last_fail"]
    assert result.details["first_fail"].message == "msg1"
    assert result.details["last_fail"].message == "msg2"


def test_empty_rule_list_always_passes():
    v = OutputValidator([])
    result = v.check("anything")
    assert result.ok is True
    assert result.failed_rules == []
    assert result.details == {}


# ---- construction ----


def test_rejects_non_rule_entries():
    with pytest.raises(TypeError):
        OutputValidator([lambda _t: True])  # type: ignore[list-item]


def test_rejects_duplicate_rule_names():
    with pytest.raises(ValueError):
        OutputValidator([_always_pass("dup"), _always_pass("dup")])


def test_rules_property_is_a_copy():
    inner = _always_pass()
    v = OutputValidator([inner])
    out = v.rules
    out.clear()
    # validator state must be unchanged after mutating the returned list
    assert len(v.rules) == 1


# ---- input typing ----


def test_check_rejects_non_string_input():
    v = OutputValidator([_always_pass()])
    with pytest.raises(TypeError):
        v.check(123)  # type: ignore[arg-type]


# ---- raise path ----


def test_check_or_raise_passes_silently_on_success():
    v = OutputValidator([_always_pass()])
    # no return value, no raise
    assert v.check_or_raise("hi") is None


def test_check_or_raise_raises_with_correct_payload():
    v = OutputValidator(
        [
            _always_pass("ok_one"),
            _always_fail("bad_one", "boom"),
            _always_fail("bad_two", "kapow"),
        ]
    )
    with pytest.raises(OutputValidationError) as exc:
        v.check_or_raise("x")
    err = exc.value
    assert err.failed_rules == ["bad_one", "bad_two"]
    assert set(err.details.keys()) == {"ok_one", "bad_one", "bad_two"}
    assert err.details["bad_one"].message == "boom"
    # exception message should at least mention the first failure
    assert "bad_one" in str(err)


def test_validation_error_details_are_independent_copies():
    bad = _always_fail("bad", "boom")
    v = OutputValidator([bad])
    with pytest.raises(OutputValidationError) as exc:
        v.check_or_raise("x")
    err = exc.value
    err.failed_rules.append("tampered")
    err.details["extra"] = RuleResult(False, "x")
    # subsequent run should not see the tampered fields
    with pytest.raises(OutputValidationError) as exc2:
        v.check_or_raise("x")
    assert exc2.value.failed_rules == ["bad"]
    assert "extra" not in exc2.value.details

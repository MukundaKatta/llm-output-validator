"""Tests for built-in rule factories (pass + fail + edge cases)."""

from __future__ import annotations

import re
import sys
from unittest import mock

import pytest

from llm_output_validator import OutputValidator, RuleResult, rules

# ---- length ----


def test_length_pass_within_bounds():
    r = rules.length(min_chars=3, max_chars=10)
    assert r.check("hello").passed is True


def test_length_fail_too_short():
    r = rules.length(min_chars=5)
    res = r.check("hi")
    assert res.passed is False
    assert "min" in (res.message or "")


def test_length_fail_too_long():
    r = rules.length(max_chars=4)
    res = r.check("hello")
    assert res.passed is False
    assert "max" in (res.message or "")


def test_length_only_min_or_only_max():
    only_min = rules.length(min_chars=2)
    assert only_min.check("ab").passed is True
    assert only_min.check("a").passed is False
    only_max = rules.length(max_chars=2)
    assert only_max.check("ab").passed is True
    assert only_max.check("abc").passed is False


def test_length_rejects_bad_bounds():
    with pytest.raises(ValueError):
        rules.length(min_chars=-1)
    with pytest.raises(ValueError):
        rules.length(max_chars=-1)
    with pytest.raises(ValueError):
        rules.length(min_chars=5, max_chars=3)


# ---- length_words ----


def test_length_words_pass_and_fail():
    r = rules.length_words(min_words=2, max_words=4)
    assert r.check("two words").passed is True
    assert r.check("one").passed is False
    assert r.check("one two three four five").passed is False


def test_length_words_rejects_bad_bounds():
    with pytest.raises(ValueError):
        rules.length_words(min_words=-1)
    with pytest.raises(ValueError):
        rules.length_words(min_words=5, max_words=2)


# ---- regex must / must not match ----


def test_regex_must_match_pass_and_fail():
    r = rules.regex_must_match(r"^[A-Z]")
    assert r.check("Hello").passed is True
    res = r.check("hello")
    assert res.passed is False
    assert "no match" in (res.message or "")


def test_regex_must_match_accepts_compiled_pattern():
    r = rules.regex_must_match(re.compile(r"\d+"))
    assert r.check("abc123").passed is True
    assert r.check("abc").passed is False


def test_regex_must_not_match_pass_and_fail():
    r = rules.regex_must_not_match(r"\b(badword)\b")
    assert r.check("clean text").passed is True
    res = r.check("this has badword in it")
    assert res.passed is False
    assert "badword" in (res.message or "")


# ---- allowed_values ----


def test_allowed_values_pass_and_fail_exact():
    r = rules.allowed_values(["yes", "no", "maybe"])
    assert r.check("yes").passed is True
    assert r.check("YES").passed is False
    assert r.check("definitely").passed is False


def test_allowed_values_case_insensitive():
    r = rules.allowed_values(["Yes", "No"], case_sensitive=False)
    assert r.check("yes").passed is True
    assert r.check("NO").passed is True
    assert r.check("nope").passed is False


def test_allowed_values_validates_construction():
    with pytest.raises(ValueError):
        rules.allowed_values([])
    with pytest.raises(TypeError):
        rules.allowed_values([1, 2])  # type: ignore[list-item]


# ---- starts_with / ends_with ----


def test_starts_with_pass_and_fail():
    r = rules.starts_with("Hello")
    assert r.check("Hello world").passed is True
    assert r.check("hello world").passed is False


def test_ends_with_pass_and_fail():
    r = rules.ends_with("!")
    assert r.check("Hello world!").passed is True
    assert r.check("Hello world").passed is False


def test_prefix_suffix_type_guards():
    with pytest.raises(TypeError):
        rules.starts_with(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        rules.ends_with(None)  # type: ignore[arg-type]


# ---- no_pii ----


def test_no_pii_pass_on_clean_text():
    r = rules.no_pii()
    assert r.check("This is a clean sentence with no secrets.").passed is True


def test_no_pii_detects_email():
    r = rules.no_pii()
    res = r.check("contact me at foo@example.com please")
    assert res.passed is False
    assert "email" in (res.message or "")


def test_no_pii_detects_phone():
    r = rules.no_pii()
    res = r.check("call (415) 555-2671 tomorrow")
    assert res.passed is False
    assert "phone" in (res.message or "")


def test_no_pii_detects_ssn():
    r = rules.no_pii()
    res = r.check("ssn 123-45-6789 here")
    assert res.passed is False
    assert "ssn" in (res.message or "")


def test_no_pii_detects_credit_card_like():
    r = rules.no_pii()
    res = r.check("card 4111 1111 1111 1111 thanks")
    assert res.passed is False
    assert "cc" in (res.message or "")


def test_no_pii_restricted_types_only_checks_named():
    r = rules.no_pii(types=["email"])
    # phone present, but only email is checked -> passes
    assert r.check("call (415) 555-2671 tomorrow").passed is True
    # email present -> fails
    assert r.check("foo@example.com").passed is False


def test_no_pii_unknown_type_raises():
    with pytest.raises(ValueError):
        rules.no_pii(types=["nope"])
    with pytest.raises(ValueError):
        rules.no_pii(types=[])


# ---- json_parseable ----


def test_json_parseable_pass_on_valid_json():
    r = rules.json_parseable()
    assert r.check('{"a": 1}').passed is True
    assert r.check("[1, 2, 3]").passed is True
    assert r.check("null").passed is True
    assert r.check('"hello"').passed is True


def test_json_parseable_fail_on_invalid():
    r = rules.json_parseable()
    res = r.check("{not json")
    assert res.passed is False
    assert "json.loads" in (res.message or "")


# ---- json_schema (optional dep) ----


def test_json_schema_pass_and_fail_when_jsonschema_installed():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    r = rules.json_schema(schema)
    assert r.check('{"name": "Mukunda", "age": 30}').passed is True
    bad = r.check('{"name": "Mukunda"}')
    assert bad.passed is False
    assert "schema" in (bad.message or "")
    not_json = r.check("not json at all")
    assert not_json.passed is False
    assert "json.loads" in (not_json.message or "")


def test_json_schema_raises_informative_import_error_when_missing():
    # Hide jsonschema from the import system temporarily so the lazy
    # import inside json_schema() resolves to ImportError even on
    # machines that have it installed.
    saved = {k: v for k, v in sys.modules.items() if k.startswith("jsonschema")}
    for k in list(saved):
        del sys.modules[k]
    with mock.patch.dict(sys.modules, {"jsonschema": None}):
        with pytest.raises(ImportError) as exc:
            rules.json_schema({"type": "object"})
        msg = str(exc.value)
        assert "jsonschema" in msg
        assert "llm-output-validator[schema]" in msg
    sys.modules.update(saved)


# ---- custom ----


def test_custom_rule_with_bool_return():
    r = rules.custom("is_short", lambda t: len(t) < 5)
    assert r.check("hi").passed is True
    assert r.check("hello world").passed is False
    assert r.name == "is_short"


def test_custom_rule_with_ruleresult_return():
    def fn(text: str) -> RuleResult:
        if text.startswith("ok"):
            return RuleResult(True, "looks good")
        return RuleResult(False, "expected leading 'ok'")

    r = rules.custom("ok_prefix", fn)
    good = r.check("okay")
    assert good.passed is True
    assert good.message == "looks good"
    bad = r.check("nope")
    assert bad.passed is False
    assert bad.message == "expected leading 'ok'"


def test_custom_rule_rejects_bad_return_type():
    r = rules.custom("bogus", lambda _t: 1)  # type: ignore[arg-type, return-value]
    with pytest.raises(TypeError):
        r.check("anything")


def test_custom_rule_validation():
    with pytest.raises(ValueError):
        rules.custom("", lambda _t: True)
    with pytest.raises(TypeError):
        rules.custom("name", "not callable")  # type: ignore[arg-type]


# ---- integration: realistic combined validator ----


def test_realistic_validator_combined():
    v = OutputValidator(
        [
            rules.length(min_chars=10, max_chars=500),
            rules.regex_must_match(r"^[A-Z]"),
            rules.regex_must_not_match(r"\b(badword)\b"),
            rules.no_pii(),
        ]
    )
    good = v.check("Hello world this is a clean response without secrets.")
    assert good.ok is True

    leaky = v.check("Hello world contact me at foo@example.com please.")
    assert leaky.ok is False
    assert leaky.failed_rules == ["no_pii"]

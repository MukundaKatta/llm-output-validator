"""Built-in rule factories for OutputValidator.

Each factory returns a `Rule`. Rules are pure functions of the candidate
string and have no LLM, network, or process side effects.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from typing import Any

from llm_output_validator.validator import Rule, RuleResult

# ---- internal regex set for no_pii ----

# These are deliberately conservative so we err on the side of catching PII.
# They are not authoritative; pair with a real redaction library when stakes
# are high.
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # 10+ digit phone-like sequences with common separators
    "phone": re.compile(
        r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)"
    ),
    # US SSN: 3-2-4 digits, separated by - or space. Avoid matching long digit runs.
    "ssn": re.compile(r"(?<!\d)\d{3}[- ]\d{2}[- ]\d{4}(?!\d)"),
    # 13-19 digit credit-card-like sequences, with optional spaces/dashes every 4.
    "cc": re.compile(
        r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
    ),
}


_PII_TYPES = frozenset(_PII_PATTERNS.keys())


# ---- length ----


def length(
    *, min_chars: int | None = None, max_chars: int | None = None
) -> Rule:
    """Pass if `len(text)` is between min_chars and max_chars (inclusive)."""
    if min_chars is not None and min_chars < 0:
        raise ValueError("min_chars must be >= 0 or None")
    if max_chars is not None and max_chars < 0:
        raise ValueError("max_chars must be >= 0 or None")
    if min_chars is not None and max_chars is not None and min_chars > max_chars:
        raise ValueError("min_chars cannot exceed max_chars")

    def _check(text: str) -> RuleResult:
        n = len(text)
        if min_chars is not None and n < min_chars:
            return RuleResult(False, f"length {n} < min {min_chars}")
        if max_chars is not None and n > max_chars:
            return RuleResult(False, f"length {n} > max {max_chars}")
        return RuleResult(True)

    return Rule(name="length", check=_check)


def length_words(
    *, min_words: int | None = None, max_words: int | None = None
) -> Rule:
    """Pass if the whitespace-split word count is between min and max."""
    if min_words is not None and min_words < 0:
        raise ValueError("min_words must be >= 0 or None")
    if max_words is not None and max_words < 0:
        raise ValueError("max_words must be >= 0 or None")
    if min_words is not None and max_words is not None and min_words > max_words:
        raise ValueError("min_words cannot exceed max_words")

    def _check(text: str) -> RuleResult:
        n = len(text.split())
        if min_words is not None and n < min_words:
            return RuleResult(False, f"word count {n} < min {min_words}")
        if max_words is not None and n > max_words:
            return RuleResult(False, f"word count {n} > max {max_words}")
        return RuleResult(True)

    return Rule(name="length_words", check=_check)


# ---- regex ----


def regex_must_match(pattern: str | re.Pattern[str]) -> Rule:
    """Pass if `re.search(pattern, text)` matches at least once."""
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern

    def _check(text: str) -> RuleResult:
        if compiled.search(text) is None:
            return RuleResult(False, f"no match for pattern {compiled.pattern!r}")
        return RuleResult(True)

    return Rule(name="regex_must_match", check=_check)


def regex_must_not_match(pattern: str | re.Pattern[str]) -> Rule:
    """Pass if `re.search(pattern, text)` finds no match."""
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern

    def _check(text: str) -> RuleResult:
        m = compiled.search(text)
        if m is not None:
            return RuleResult(
                False, f"matched forbidden pattern {compiled.pattern!r}: {m.group(0)!r}"
            )
        return RuleResult(True)

    return Rule(name="regex_must_not_match", check=_check)


# ---- allowed values ----


def allowed_values(
    values: Iterable[str], *, case_sensitive: bool = True
) -> Rule:
    """Pass if `text` equals one of `values` exactly.

    When `case_sensitive=False`, comparison is done with `.casefold()`.
    """
    vals = list(values)
    if not vals:
        raise ValueError("allowed_values requires at least one value")
    for v in vals:
        if not isinstance(v, str):
            raise TypeError(
                f"allowed_values entries must be str, got {type(v).__name__}"
            )

    if case_sensitive:
        allowed_set: set[str] = set(vals)

        def _check(text: str) -> RuleResult:
            if text in allowed_set:
                return RuleResult(True)
            return RuleResult(False, f"{text!r} not in allowed values")

    else:
        folded = {v.casefold() for v in vals}

        def _check(text: str) -> RuleResult:
            if text.casefold() in folded:
                return RuleResult(True)
            return RuleResult(False, f"{text!r} not in allowed values (case-insensitive)")

    return Rule(name="allowed_values", check=_check)


# ---- prefix / suffix ----


def starts_with(prefix: str) -> Rule:
    """Pass if `text.startswith(prefix)`."""
    if not isinstance(prefix, str):
        raise TypeError("starts_with prefix must be a str")

    def _check(text: str) -> RuleResult:
        if text.startswith(prefix):
            return RuleResult(True)
        return RuleResult(False, f"does not start with {prefix!r}")

    return Rule(name="starts_with", check=_check)


def ends_with(suffix: str) -> Rule:
    """Pass if `text.endswith(suffix)`."""
    if not isinstance(suffix, str):
        raise TypeError("ends_with suffix must be a str")

    def _check(text: str) -> RuleResult:
        if text.endswith(suffix):
            return RuleResult(True)
        return RuleResult(False, f"does not end with {suffix!r}")

    return Rule(name="ends_with", check=_check)


# ---- PII ----


def no_pii(types: Iterable[str] | None = None) -> Rule:
    """Pass if no internal PII regex matches.

    Default types: email, phone, ssn, cc. Pass `types=["email", "phone"]` to
    restrict the check. Unknown type names raise ValueError.
    """
    if types is None:
        active = list(_PII_TYPES)
    else:
        active = list(types)
        unknown = [t for t in active if t not in _PII_TYPES]
        if unknown:
            raise ValueError(
                f"unknown PII type(s): {unknown}. valid: {sorted(_PII_TYPES)}"
            )
        if not active:
            raise ValueError("no_pii requires at least one type")

    patterns: list[tuple[str, re.Pattern[str]]] = [
        (t, _PII_PATTERNS[t]) for t in active
    ]

    def _check(text: str) -> RuleResult:
        for kind, pat in patterns:
            m = pat.search(text)
            if m is not None:
                return RuleResult(False, f"contains {kind}-like substring: {m.group(0)!r}")
        return RuleResult(True)

    return Rule(name="no_pii", check=_check)


# ---- JSON ----


def json_parseable() -> Rule:
    """Pass if `json.loads(text)` succeeds."""

    def _check(text: str) -> RuleResult:
        try:
            json.loads(text)
        except (ValueError, TypeError) as e:
            return RuleResult(False, f"json.loads failed: {e}")
        return RuleResult(True)

    return Rule(name="json_parseable", check=_check)


def json_schema(schema: dict[str, Any]) -> Rule:
    """Pass if `text` is JSON and validates against `schema`.

    Requires the optional `jsonschema` extra. Install with:
        pip install "llm-output-validator[schema]"
    """
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(
            "rules.json_schema requires the optional 'jsonschema' dependency. "
            "Install with: pip install \"llm-output-validator[schema]\""
        ) from e

    # Validate the schema itself up front so a malformed schema fails loudly
    # at construction time instead of on first check call.
    try:
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
    except Exception as e:  # pragma: no cover - defensive
        raise ValueError(f"invalid JSON Schema: {e}") from e
    validator = validator_cls(schema)

    def _check(text: str) -> RuleResult:
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as e:
            return RuleResult(False, f"json.loads failed: {e}")
        errors = sorted(validator.iter_errors(data), key=lambda er: er.path)
        if errors:
            first = errors[0]
            path = "/".join(str(p) for p in first.absolute_path) or "<root>"
            return RuleResult(False, f"schema mismatch at {path}: {first.message}")
        return RuleResult(True)

    return Rule(name="json_schema", check=_check)


# ---- custom ----


def custom(
    name: str, fn: Callable[[str], bool | RuleResult]
) -> Rule:
    """Wrap a user function `fn(text) -> bool | RuleResult` as a named Rule."""
    if not isinstance(name, str) or not name:
        raise ValueError("custom rule name must be a non-empty str")
    if not callable(fn):
        raise TypeError("custom rule fn must be callable")

    def _check(text: str) -> RuleResult:
        out = fn(text)
        if isinstance(out, RuleResult):
            return out
        if isinstance(out, bool):
            return RuleResult(out)
        raise TypeError(
            f"custom rule {name!r} must return bool or RuleResult, got {type(out).__name__}"
        )

    return Rule(name=name, check=_check)

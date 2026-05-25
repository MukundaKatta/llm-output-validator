"""Validate LLM response text against declarative rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class ValidationError(Exception):
    """Raised when validate() is called with an invalid rule configuration."""


@dataclass
class Rule:
    """A single validation rule.

    Attributes:
        name: rule identifier used in failure reports.
        must_contain: text that must appear in the output (case-insensitive by default).
        must_not_contain: text that must NOT appear.
        min_length: minimum character count (inclusive).
        max_length: maximum character count (inclusive).
        matches_regex: regex that must match somewhere in the output.
        not_matches_regex: regex that must NOT match.
        case_sensitive: if False (default), string checks are case-insensitive.
        message: optional human-readable description used in failure reports.
    """

    name: str = "rule"
    must_contain: str | None = None
    must_not_contain: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    matches_regex: str | None = None
    not_matches_regex: str | None = None
    case_sensitive: bool = False
    message: str | None = None

    def check(self, text: str) -> list[str]:
        """Run the rule against text. Return list of failure descriptions."""
        failures: list[str] = []
        flags = 0 if self.case_sensitive else re.IGNORECASE

        if self.must_contain is not None:
            needle = self.must_contain if self.case_sensitive else self.must_contain.lower()
            haystack = text if self.case_sensitive else text.lower()
            if needle not in haystack:
                failures.append(
                    self.message or f"must contain {self.must_contain!r}"
                )

        if self.must_not_contain is not None:
            needle = self.must_not_contain if self.case_sensitive else self.must_not_contain.lower()
            haystack = text if self.case_sensitive else text.lower()
            if needle in haystack:
                failures.append(
                    self.message or f"must not contain {self.must_not_contain!r}"
                )

        if self.min_length is not None and len(text) < self.min_length:
            failures.append(
                self.message or f"length {len(text)} < min {self.min_length}"
            )

        if self.max_length is not None and len(text) > self.max_length:
            failures.append(
                self.message or f"length {len(text)} > max {self.max_length}"
            )

        if self.matches_regex is not None:
            try:
                if not re.search(self.matches_regex, text, flags):
                    failures.append(
                        self.message or f"must match regex {self.matches_regex!r}"
                    )
            except re.error as e:
                raise ValidationError(f"invalid regex in rule {self.name!r}: {e}") from e

        if self.not_matches_regex is not None:
            try:
                if re.search(self.not_matches_regex, text, flags):
                    failures.append(
                        self.message or f"must not match regex {self.not_matches_regex!r}"
                    )
            except re.error as e:
                raise ValidationError(f"invalid regex in rule {self.name!r}: {e}") from e

        return failures


@dataclass
class ValidationResult:
    """Result of a validate() call.

    Attributes:
        ok: True if all rules passed.
        failures: list of (rule_name, failure_description) tuples.
        text: the text that was validated.
        rule_count: total number of rules checked.
    """

    ok: bool
    failures: list[tuple[str, str]]
    text: str
    rule_count: int

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def failed_rules(self) -> list[str]:
        """Names of rules that failed."""
        return [name for name, _ in self.failures]

    def summary(self) -> str:
        """Human-readable summary."""
        if self.ok:
            return f"All {self.rule_count} rules passed."
        lines = [f"{self.failure_count}/{self.rule_count} rules failed:"]
        for rule, desc in self.failures:
            lines.append(f"  [{rule}] {desc}")
        return "\n".join(lines)

    def __bool__(self) -> bool:
        return self.ok


def validate(
    text: str,
    rules: list[Rule] | None = None,
    *,
    must_contain: str | None = None,
    must_not_contain: str | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    matches_regex: str | None = None,
    not_matches_regex: str | None = None,
    case_sensitive: bool = False,
) -> ValidationResult:
    """Validate LLM output text against a set of rules.

    Rules can be provided as a list of Rule objects, or as keyword arguments
    for quick one-off checks. Both are AND-combined.

    Args:
        text: the LLM output to validate.
        rules: list of Rule objects.
        must_contain: text that must appear (case-insensitive by default).
        must_not_contain: text that must NOT appear.
        min_length: minimum character count.
        max_length: maximum character count.
        matches_regex: regex that must match somewhere.
        not_matches_regex: regex that must NOT match.
        case_sensitive: applies to keyword-arg string checks only.

    Returns:
        ValidationResult with ok=True if all rules pass.
    """
    all_rules: list[Rule] = list(rules) if rules else []

    # Build inline rules from keyword args
    inline = Rule(
        name="inline",
        must_contain=must_contain,
        must_not_contain=must_not_contain,
        min_length=min_length,
        max_length=max_length,
        matches_regex=matches_regex,
        not_matches_regex=not_matches_regex,
        case_sensitive=case_sensitive,
    )
    # Only add inline rule if any kwargs were given
    has_inline = any([
        must_contain, must_not_contain, min_length, max_length,
        matches_regex, not_matches_regex,
    ])
    if has_inline:
        all_rules.append(inline)

    failures: list[tuple[str, str]] = []
    for rule in all_rules:
        for desc in rule.check(text):
            failures.append((rule.name, desc))

    return ValidationResult(
        ok=len(failures) == 0,
        failures=failures,
        text=text,
        rule_count=len(all_rules),
    )

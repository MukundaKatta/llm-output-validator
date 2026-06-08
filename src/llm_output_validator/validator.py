"""Core OutputValidator + Rule/Result dataclasses."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuleResult:
    """Outcome of evaluating one rule against a candidate string.

    Attributes:
        passed: True if the rule accepted the input.
        message: Optional human-readable detail (failure reason or note).
    """

    passed: bool
    message: str | None = None


@dataclass(frozen=True)
class Rule:
    """A named callable that produces a RuleResult for a candidate string."""

    name: str
    check: Callable[[str], RuleResult]


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate result from `OutputValidator.check`.

    Attributes:
        ok: True only when every rule passed.
        failed_rules: Names of rules that failed, in the order they ran.
        details: Per-rule RuleResult, keyed by rule name.
    """

    ok: bool
    failed_rules: list[str] = field(default_factory=list)
    details: dict[str, RuleResult] = field(default_factory=dict)


class OutputValidationError(Exception):
    """Raised by `OutputValidator.check_or_raise` when one or more rules fail.

    Attributes:
        failed_rules: list of failing rule names
        details: per-rule RuleResult for every rule that ran
    """

    def __init__(self, failed_rules: list[str], details: dict[str, RuleResult]) -> None:
        self.failed_rules = list(failed_rules)
        self.details = dict(details)
        first_msg = ""
        if failed_rules:
            first = failed_rules[0]
            res = details.get(first)
            if res is not None and res.message:
                first_msg = f": {first}: {res.message}"
            else:
                first_msg = f": {first}"
        super().__init__(f"output failed {len(failed_rules)} rule(s){first_msg}")


class OutputValidator:
    """Run a list of `Rule`s against an output string.

    Rules run in declared order. All rules always run (no short-circuit) so
    callers get a complete picture of every failure on a single check.
    """

    def __init__(self, rules: Iterable[Rule]) -> None:
        rule_list = list(rules)
        for r in rule_list:
            if not isinstance(r, Rule):
                raise TypeError(
                    f"OutputValidator rules must be Rule instances, got {type(r).__name__}"
                )
        # detect duplicate names early - details is keyed by name and a
        # collision would silently shadow earlier results.
        seen: set[str] = set()
        for r in rule_list:
            if r.name in seen:
                raise ValueError(f"duplicate rule name: {r.name!r}")
            seen.add(r.name)
        self._rules: list[Rule] = rule_list

    @property
    def rules(self) -> list[Rule]:
        """Read-only copy of the configured rules."""
        return list(self._rules)

    def check(self, text: str) -> ValidationResult:
        """Run every rule against `text` and return the aggregate result."""
        if not isinstance(text, str):
            raise TypeError(f"check() expects a str, got {type(text).__name__}")
        details: dict[str, RuleResult] = {}
        failed: list[str] = []
        for rule in self._rules:
            result = rule.check(text)
            details[rule.name] = result
            if not result.passed:
                failed.append(rule.name)
        return ValidationResult(ok=not failed, failed_rules=failed, details=details)

    def check_or_raise(self, text: str) -> None:
        """Run `check(text)`; raise OutputValidationError if any rule failed."""
        result = self.check(text)
        if not result.ok:
            raise OutputValidationError(result.failed_rules, result.details)

"""llm-output-validator: validate LLM response text against declarative rules.

Two complementary APIs are provided:

* The quick functional API — ``validate(text, ...)`` plus the declarative
  :class:`Rule` / :class:`ValidationResult` / :class:`ValidationError` types.
  This is the surface documented in the README.

* The composable rule-engine API — :class:`OutputValidator` driven by the
  reusable rule factories in :mod:`llm_output_validator.rules` (``length``,
  ``no_pii``, ``json_parseable``, ``allowed_values`` and friends). These build
  :class:`CallableRule` objects that produce :class:`RuleResult` outcomes; a
  failing check can raise :class:`OutputValidationError`.
"""

from . import rules
from .core import Rule, ValidationError, ValidationResult, validate
from .validator import (
    OutputValidationError,
    OutputValidator,
    RuleResult,
)
from .validator import Rule as CallableRule
from .validator import ValidationResult as OutputValidationResult

__all__ = [
    # Functional API (README)
    "Rule",
    "ValidationError",
    "ValidationResult",
    "validate",
    # Rule-engine API
    "OutputValidator",
    "OutputValidationError",
    "OutputValidationResult",
    "RuleResult",
    "CallableRule",
    "rules",
]

"""llm-output-validator: validate LLM response text against declarative rules.

Two complementary APIs are exposed:

* The quick functional API — :func:`validate` plus the :class:`Rule` dataclass
  and :class:`ValidationResult` from :mod:`llm_output_validator.core`. Best for
  one-off, ad-hoc checks driven by keyword arguments.
* The composable object API — :class:`OutputValidator` plus the rule factories
  in :mod:`llm_output_validator.rules` (``length``, ``regex_must_match``,
  ``no_pii``, ``json_parseable`` …). Best when you want to assemble a reusable
  set of named rules and run them many times.
"""

from . import rules
from .core import Rule, ValidationError, ValidationResult, validate
from .validator import (
    OutputValidationError,
    OutputValidator,
    RuleResult,
)
from .validator import Rule as RuleSpec

__version__ = "0.1.0"

__all__ = [
    # Functional API (core)
    "Rule",
    "ValidationError",
    "ValidationResult",
    "validate",
    # Object API (validator + rules)
    "OutputValidator",
    "OutputValidationError",
    "RuleResult",
    "RuleSpec",
    "rules",
    "__version__",
]

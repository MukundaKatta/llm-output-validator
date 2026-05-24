"""llm-output-validator - rule-based validator for LLM output strings.

A small, zero-dependency check stage you run AFTER the LLM has produced a
string. Use it to enforce length, regex, allowed values, no-PII,
JSON-parseable, JSON Schema, or your own custom predicates. Failing rules
come back as a structured `ValidationResult` (or as an
`OutputValidationError` if you prefer the raise path).

    from llm_output_validator import OutputValidator, rules

    v = OutputValidator([
        rules.length(min_chars=10, max_chars=500),
        rules.regex_must_match(r"^[A-Z]"),
        rules.no_pii(),
        rules.json_parseable(),
    ])

    result = v.check("Hello world this is a response")
    if not result.ok:
        for name in result.failed_rules:
            print(name, result.details[name].message)

For BYO-LLM retry loops on structured JSON output, see the sibling library
`agentcast`. For tool-arg validation before the LLM-driven call, see
`agentvet`.
"""

from llm_output_validator import rules
from llm_output_validator.validator import (
    OutputValidationError,
    OutputValidator,
    Rule,
    RuleResult,
    ValidationResult,
)

__version__ = "0.1.0"

__all__ = [
    "OutputValidationError",
    "OutputValidator",
    "Rule",
    "RuleResult",
    "ValidationResult",
    "__version__",
    "rules",
]

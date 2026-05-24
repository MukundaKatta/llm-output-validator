# llm-output-validator

[![PyPI](https://img.shields.io/pypi/v/llm-output-validator.svg)](https://pypi.org/project/llm-output-validator/)
[![Python](https://img.shields.io/pypi/pyversions/llm-output-validator.svg)](https://pypi.org/project/llm-output-validator/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Rule-based validator for LLM output strings.**

Run a list of small, named rules against whatever string your LLM produced.
Every rule runs (no short-circuit), so a single check tells you everything
that is wrong. Built-in rules cover length, regex, allowed values,
prefix/suffix, no-PII, JSON-parseable, and JSON Schema. Zero required
runtime dependencies; `jsonschema` is an optional extra for the
`json_schema` rule only.

This sits in the "after the LLM call, before you trust the string" slot. It
does not call an LLM and does not retry. For a structured-output retry loop
that does call back into the LLM, see the sibling library
[`agentcast`](https://pypi.org/project/agentcast/). For tool-arg
validation before an LLM-driven tool call, see
[`agentvet`](https://pypi.org/project/agentvet/).

## Install

```bash
pip install llm-output-validator
# or, with the optional JSON Schema rule
pip install "llm-output-validator[schema]"
```

## Use

```python
from llm_output_validator import OutputValidator, rules

v = OutputValidator([
    rules.length(min_chars=10, max_chars=500),
    rules.regex_must_match(r"^[A-Z]"),
    rules.regex_must_not_match(r"\b(badword1|badword2)\b"),
    rules.no_pii(),
    rules.json_parseable(),
])

result = v.check('{"answer": "Hello world this is a response"}')
if not result.ok:
    for name in result.failed_rules:
        print(name, result.details[name].message)
```

Prefer the raise path? Use `check_or_raise`:

```python
from llm_output_validator import OutputValidationError

try:
    v.check_or_raise(model_output)
except OutputValidationError as e:
    print("failed:", e.failed_rules)
    print("details:", e.details)
```

## Built-in rules

All factories live in the `rules` namespace.

| Rule | What it does |
| ---- | ------------ |
| `rules.length(min_chars=..., max_chars=...)` | Bound `len(text)` (either bound optional). |
| `rules.length_words(min_words=..., max_words=...)` | Bound whitespace-split word count. |
| `rules.regex_must_match(pattern)` | Pass if `re.search(pattern, text)` matches. |
| `rules.regex_must_not_match(pattern)` | Pass if `re.search(pattern, text)` does NOT match. |
| `rules.allowed_values(values, case_sensitive=True)` | Exact match against a fixed list. |
| `rules.starts_with(prefix)` | Pass if `text.startswith(prefix)`. |
| `rules.ends_with(suffix)` | Pass if `text.endswith(suffix)`. |
| `rules.no_pii(types=None)` | Pass if no email/phone/SSN/credit-card-like substring is found. Pass `types=["email"]` to restrict. |
| `rules.json_parseable()` | Pass if `json.loads(text)` succeeds. |
| `rules.json_schema(schema)` | Pass if `text` is JSON and validates against the schema. Requires `pip install "llm-output-validator[schema]"`. |
| `rules.custom(name, fn)` | Wrap your own `fn(text) -> bool \| RuleResult`. |

## Custom rule

```python
from llm_output_validator import OutputValidator, RuleResult, rules

def must_be_balanced_parens(text: str) -> RuleResult:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return RuleResult(False, "unbalanced: extra ')'")
    if depth != 0:
        return RuleResult(False, f"unbalanced: {depth} unclosed '('")
    return RuleResult(True)

v = OutputValidator([
    rules.custom("balanced_parens", must_be_balanced_parens),
])
```

A `bool` return is also accepted and gets wrapped into a `RuleResult`.

## Optional `jsonschema` dependency

`rules.json_schema(schema)` is the only built-in that needs an extra
package. It imports lazily, and the import error message tells you exactly
which extra to install:

```python
import pytest
from llm_output_validator import rules

# raises ImportError with install hint if jsonschema is not installed
rules.json_schema({"type": "object"})
```

## What it does NOT do

- No LLM call. Rules are pure functions of the candidate string.
- No retries. Pair with `agentcast` if you want a BYO-LLM repair loop on
  structured JSON output.
- No tool-arg validation. Pair with `agentvet` for that.
- No process-level state. A validator is just a list of rules; safe to
  share across threads.

## License

MIT

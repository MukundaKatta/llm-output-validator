# llm-output-validator

Validate LLM response text against declarative rules — length, contains, regex,
allowed values, prefix/suffix, PII detection, and JSON/JSON-Schema parsing.

Zero required dependencies. Python 3.10+. MIT.

The library ships **two complementary APIs**:

1. **Functional API** — `validate()` for quick, one-off keyword-driven checks.
2. **Object API** — `OutputValidator` + the `rules` factories for assembling a
   reusable, named set of rules you run many times.

## Install

```bash
pip install llm-output-validator

# Optional: enables rules.json_schema()
pip install "llm-output-validator[schema]"
```

## Functional API: `validate()`

```python
from llm_output_validator import validate

result = validate(
    response_text,
    must_contain="Summary:",
    must_not_contain="I don't know",
    min_length=50,
    max_length=2000,
    matches_regex=r"^Summary:",
)

if not result.ok:
    print(result.summary())
    # 1/3 rules failed:
    #   [inline] must contain 'Summary:'
```

## Named rules

```python
from llm_output_validator import Rule, validate

rules = [
    Rule("has_summary", must_contain="Summary:"),
    Rule("no_apology", must_not_contain="I apologize"),
    Rule("reasonable_length", min_length=50, max_length=2000),
    Rule("valid_format", matches_regex=r"^Summary:"),
]

result = validate(response_text, rules=rules)
print(result.failed_rules)   # ["has_summary"] if summary missing
```

## ValidationResult

```python
result.ok              # True if all rules passed
result.failures        # [(rule_name, description), ...]
result.failed_rules    # ["rule_name", ...]
result.failure_count   # int
result.rule_count      # total rules checked
result.summary()       # human-readable report
bool(result)           # same as result.ok
```

## Case-sensitive matching

```python
result = validate(text, must_contain="JSON", case_sensitive=True)
```

## Object API: `OutputValidator` + `rules`

For reusable validators built from named, composable rules, use
`OutputValidator` together with the rule factories in
`llm_output_validator.rules`. Every rule always runs (no short-circuit), so a
single `check()` returns the complete set of failures.

```python
from llm_output_validator import OutputValidator, rules

validator = OutputValidator([
    rules.length(min_chars=20, max_chars=2000),
    rules.starts_with("Summary:"),
    rules.regex_must_match(r"\b\d{4}\b"),       # mentions a 4-digit year
    rules.regex_must_not_match(r"(?i)as an ai"),  # no boilerplate disclaimer
    rules.no_pii(),                              # no email/phone/ssn/cc leaks
])

result = validator.check("Summary: The tower opened in 1889.")
print(result.ok)            # True
print(result.failed_rules)  # []
print(result.details)       # {rule_name: RuleResult(passed=..., message=...)}

# Or raise on the first failure instead of inspecting the result:
validator.check_or_raise("Summary: The tower opened in 1889.")
```

### Built-in rule factories

| Factory | Passes when… |
| --- | --- |
| `length(min_chars=, max_chars=)` | character count is within bounds |
| `length_words(min_words=, max_words=)` | whitespace word count is within bounds |
| `regex_must_match(pattern)` | `re.search(pattern, text)` matches |
| `regex_must_not_match(pattern)` | `re.search(pattern, text)` does not match |
| `allowed_values(values, case_sensitive=True)` | text equals one of `values` |
| `starts_with(prefix)` / `ends_with(suffix)` | text has the given prefix/suffix |
| `no_pii(types=None)` | no email/phone/ssn/cc-like substrings are found |
| `json_parseable()` | `json.loads(text)` succeeds |
| `json_schema(schema)` | text is JSON and validates against `schema` (needs the `[schema]` extra) |
| `custom(name, fn)` | wraps `fn(text) -> bool \| RuleResult` as a named rule |

> The `no_pii` patterns are deliberately conservative heuristics, not an
> authoritative detector — pair them with a real redaction library when the
> stakes are high.

### `ValidationResult` (object API)

```python
result.ok            # True only when every rule passed
result.failed_rules  # ["rule_name", ...] in the order they ran
result.details       # {rule_name: RuleResult(passed, message)}
```

`check_or_raise()` raises `OutputValidationError` (with `.failed_rules` and
`.details`) when any rule fails.

## Development

The test suite uses only the Python standard library — no `pytest` or other
third-party test dependencies are required:

```bash
python -m unittest discover -s tests -v
```

## License

MIT

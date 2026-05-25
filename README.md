# llm-output-validator

Validate LLM response text against declarative rules — length, contains, regex.

Zero dependencies. Python 3.10+. MIT.

## Install

```bash
pip install llm-output-validator
```

## Usage

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

## License

MIT

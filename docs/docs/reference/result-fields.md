# Result fields

This page says what each field of a `RefinementResult`, a `StageResult`, a `SeriesResult` and a `SeriesEntry` holds, and what it means when it is empty.

A number in a field costs nothing until you read it, so a statistic that does not tell one fit from another is kept in a field and explained here, rather than raised as a diagnostic on every run.
The entries are generated from `rietx.help.RESULT_FIELD_HELP`, the one place each is written.
[The refinement result](result.md) and [Sequential refinement](series.md) show the same types in use.

## Looking one up in code

`rietx.help.explain` takes a result field, named `Type.field`, or a diagnostic code, and returns its entry.
The two kinds of name cannot collide, because a code has no dot in it.
A name this version does not describe, such as a code read from an older file, returns `None`.

```python
from rietx.help import explain

entry = explain("RefinementResult.status")
print(entry.title)
print(explain("BOUND_HIT") is not None)
print(explain("NO_SUCH_CODE"))
```

```text
Solver exit
True
None
```

```{include} ../_generated/result-fields.md
```

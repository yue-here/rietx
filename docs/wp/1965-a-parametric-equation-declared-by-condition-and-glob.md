# WP-1965 — a parametric equation declared by condition and glob

Milestone: parametric · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Depends on: 1325 (the declaration this lowers onto); 1964 soft (an expression as what a glob expands)
Priority: P3 2026-11-04 — writing the lists by hand is the workaround, and no user has asked yet; last in the milestone's order

## Goal

A parametric equation can name its subset by a condition on the coordinates and its
target by a glob. Each form is lowered to today's `ParametricEquation` when the
declaration is resolved, so the stored declaration keeps its current data form.

## Context

Filed as a stub on 2026-10-14, from a review of WP-1325's API against prior art. The
two items share one seam (`schemas/parametric.py` and
`params.parametric.resolve_parametric`) and one decision (how a declaration is
spelled).

### Why a formula left this WP

This WP also held a Wilkinson formula for a polynomial's terms, the notation of R and
patsy. The maintainer's track ruling of 2026-11-04 dropped it. WP-1964's grammar
replaces it: a user writes `a0 + a1*T + a2*T^2`, and a term list stays the data form.
Keeping both would have given one package two meanings for `*` and `^`, since in a
Wilkinson formula `x*y` is `x + y + x:y` and `x^2` is crossing. Check that an expression
linear in its coefficients keeps `polynomial`'s closed-form start, which is 1964's to
settle.

### A subset by condition

`ParametricEquation.patterns` is a list of indices into the patterns as passed,
and `design` rows follow the subset's order. A library that drops one bad
pattern shifts every later index, so every subset has to be rewritten by
hand. A phase field is also a region of composition, which a condition on the
coordinate columns states directly (`T < 800`, `x between 0.1 and 0.3`).
Tidy-data practice keys rows by a sample ID. CAMEO keys each sample by
composition, position and process (WP-1325 § Prior art).

`PatternData` has no label field (`schemas/pattern.py`).
`HistogramResult.label` exists on the result side. Decide whether a label
column on `CoordinateTable` or a condition is the key.

Decide what is stored. Patsy's lesson, which 1325 applies to the reference
and scale, is that a coefficient's meaning must not move when patterns join.
Subset membership is different: a new pattern inside a phase field should
join that field's equation. So storing the condition, and re-evaluating it at
each resolution, may be right here. A `design` basis keeps positional rows,
or needs a key per row.

### A glob for the target

1325's design said "targets as globs". The code takes one bare path, and
`ParametricEquation._check` refuses a glob. An orthorhombic cell linear in T is
three declarations with three names. A glob would expand at resolution into
one declaration per matched path, each with its own coefficients.

- **Naming.** Coefficients are `vars.<name>_<j>`, and a name must be one
  identifier. An expansion needs a naming rule that cannot collide.
- **What a glob may match.** `phases.0.cell.*` on a cubic phase matches `b`
  and `c` (tied to `a`) and three locked angles, and each of those is refused
  as a target today. A blocked glob is reported, never silent (root
  CLAUDE.md § A hold), so the expansion skips them and says which.

### Carried from 1325 (folded from § Inherited on 2026-11-16)

- **A resolved spelling is refittable.** `RefinementResult.parametric` carries each
  declaration as resolved, the form a refit passes back (1325's seventh session, PR #977).
  A condition or glob spelling resolves to that same `ParametricEquation`, so a result read
  back refits whichever spelling declared it.
- **Where a boundary goes is a physical fact, declared or detected, never "every N
  patterns"** (@mustachefeeling, PR #977 comments, numbers as reported). A condition
  is how a declared boundary is written. A detector that *proposes* one is not this
  WP's: their own detector's calibration inverted within seven weeks, so it is
  calibrated inside the suite against a seeded planted-events series first (#141,
  [1317](1317-series-scrubber.md)).
- **Not this WP's tasks, still true:** a `rietx events` line per parametric equation of a
  joint fit (subset size, form verdict, any detector firing inside the subset), and the
  report of which detector on main fired inside each subset. Both go to an issue at
  this WP's close, with 1325's two rules for the events line: pair events in file order,
  never by `(series_index, series_pass)`, and a segmented chain's summed fit time is
  not its wall time.

## Non-goals

- A Wilkinson formula, and any other way to write a function:
  [1964](1964-a-parametric-equation-the-user-writes.md).
- A pandas dependency. A condition reads `CoordinateTable` columns.

## Tasks

- [x] A subset by condition, or by label. Decide what is stored, and pin a
  dropped pattern by test: the equation covers the same specimens afterwards.
  *(2026-11-16: `ParametricEquation.where`, a condition in the expression
  grammar's condition syntax over the coordinate columns. The condition is the
  key, not a label: a phase field is a region of the coordinates, and a label
  column would be a second key a pattern must be given by hand. The condition is
  stored and re-evaluated at each resolution (`params.parametric.subset_of`), the
  reference and scale still frozen at the first; refused beside `patterns` and on
  a `design` basis, whose rows stay positional.
  `test_a_condition_keeps_its_specimens_when_a_pattern_is_dropped` pins the drop.)*
- [x] A glob target, expanded at resolution, with skipped paths reported.
  *(2026-11-16: a linear basis's `target` may be a glob. `MultiParameterTable`
  expands it before any of its tables exist (`_expand_globs`, matched on a scratch
  table of the subset's first pattern, since a target decides the sharing map)
  through `params.parametric.expand_glob`: one declaration per drivable path, named
  `{name}_{tail}` (`glob_member_name`, the path past the glob's literal segments),
  so the stored declaration keeps its data form with bare targets. Skipped paths
  are `_target_refusal`'s, recorded in `glob_expansions` and reported as
  `PARAMETRIC_GLOB_SKIPPED` (info, tier 1). An expression basis refuses a glob: its
  variables are shared, so every matched path would take one value.)*
- [x] Manual: `reference/parametric.md` § Declaration shows the new forms beside
  the data form. *(2026-11-16: the field table's `target` and `where` rows, and
  § A subset by condition and § A target glob, each with an executed example;
  `reference/expressions.md` § Conditions names `where` as a second place a
  condition appears.)*
- [x] Skill: the series reference's parametric row, or "none" and why.
  *(2026-11-16: the row names both spellings, "(`where=` subset, glob target)",
  paid for in the same row so `series.md` stays inside its budget (34 597 of
  34 600 B); `PARAMETRIC_GLOB_SKIPPED` joined the parametric codes' row in
  `diagnostics.md`.)*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_parametric_series.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Kusne, A. G. et al. (2020). *Nat. Commun.* 11, 5966 — CAMEO.
- WP-1325 § Prior art and § The shape.

## Handover log

- **2026-11-04** — The maintainer's track ruling moved this WP into the `parametric`
  milestone and dropped the formula, so the file and title were renamed. Next: the
  condition's stored form.
- **2026-10-14** — Filed as a stub from a review of 1325's API against prior
  art. No open WP owned declaration syntax: 1325 owns the declaration and
  its correctness, and these three items are sugar over it at a lower
  priority.

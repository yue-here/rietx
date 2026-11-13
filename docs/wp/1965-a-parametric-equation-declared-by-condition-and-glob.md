# WP-1965 — a parametric equation declared by condition and glob

Milestone: parametric · Status: ⬜
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

### Inherited

- **2026-11-12, from [1325](1325-parametric-series.md) (closed): `rietx events`
  could print one line per parametric equation of a joint fit.** 1325 held this
  in its own § Inherited since 1322 closed without it, and moved it here at its
  close, because the line reports this WP's subset and detectors. This is
  @mustachefeeling's point from the PR #977 comments. A joint fit keeps no
  history (`multi.py`), but it has emitted events since #926, and `rietx events`
  (`history.aggregate.summarize_events`) shipped in PR #902. The line would
  carry the subset size, the form verdict, and whether a detector fired inside
  the subset. Two rules for whoever builds it:
  - Pair events in file order, never by `(series_index, series_pass)`, since
    indices recur on reseeds and restarted segments. The aggregator already
    clears its open stages at each `fit_start` (`aggregate.py:185`).
  - A segmented chain's summed fit time is not its wall time: 700 s against
    148 s on one chain, as reported and not re-measured.

- **2026-10-15, from [1325](1325-parametric-series.md), from @mustachefeeling's comments on PR #977: where a subset's boundary goes.** Numbers as
  reported, not re-measured. Since 2026-10-15 the declaration is
  `ParametricEquation` and the resolved one `RefinedParametricEquation`
  (1325 decision 7), so read the entry below in those names.
  - Their draft's default for equations per phase field: a phase transition
    breaks cell, Biso, profile and composition equations; a gas switch
    breaks composition only; isothermal ↔ ramp breaks nothing. Biso is
    never tied across a transition. Each default is overridable per path and
    boundary, with the override recorded. Boundaries are physical, declared
    or detected, never "every N patterns".
  - A misplaced edge is the expensive error: 1325's kink row covers its gap
    0.66 of the time.
  - Their blind event detector (Le Bail, one high-symmetry model along the
    chain): a cell discontinuity did not fire, since a high-symmetry cell
    fitted to lower-symmetry patterns wanders and the jump was 3× the median
    step against `SEQUENTIAL_DISCONTINUITY`'s 5×. What held: the GoF step
    (30× the median), a sustained Rwp regime shift (ratio 1.87), and the
    tallest unmatched peak collapsing (h/σ 510 to 24). The null control fired
    nothing. At a real transition the two directions disagree by one step,
    so agreement is corroboration rather than a test.
  - A ΔBIC symmetry test needs a negative control: a cubic null once
    "required" R-3m at ΔBIC +1.4 × 10⁶ before a cell-window guard.
  - A continuous reaction needs another detector: a reduction onset showed
    as an agreement shift of 1.2σ, and the abrupt logic fired only at the
    gas switch.
  - **The detector's calibration inverted in seven weeks** (their addendum,
    re-run on 1.9.0.dev0): the positive series is now missed, the null
    control now fires, and a subgroup screen gives one false "lower symmetry
    required" per run on a different compound each time. So a detector that
    proposes a boundary is calibrated inside the test suite, against a
    seeded planted-events series (#141, which still owes its generator;
    [1317](1317-series-scrubber.md)).
  - A cheap first step they propose: report, beside each equation, whether
    any detector on main (`SeriesResult.discontinuities`, `moved_paths`,
    the `MagneticOnset` bracket, `split_localisation`) fired inside its
    subset.

- **2026-10-14, from [1325](1325-parametric-series.md) (seventh session,
  PR #977): a result now carries each equation as resolved.**
  `RefinementResult.parametric`'s resolved equation is the declaration with its
  reference and scale filled in, the form a refit passes back. A condition
  or glob spelling should resolve to that same `ParametricEquation`,
  so a result read back can be refitted whichever spelling declared it.

## Non-goals

- A Wilkinson formula, and any other way to write a function:
  [1964](1964-a-parametric-equation-the-user-writes.md).
- A pandas dependency. A condition reads `CoordinateTable` columns.

## Tasks

- [ ] A subset by condition, or by label. Decide what is stored, and pin a
  dropped pattern by test: the equation covers the same specimens afterwards.
- [ ] A glob target, expanded at resolution, with skipped paths reported.
- [ ] Manual: `reference/parametric.md` § Declaration shows the new forms beside
  the data form.
- [ ] Skill: the series reference's parametric row, or "none" and why.

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

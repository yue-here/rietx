# WP-1453 — both directions name the lower cost

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Track: A long run is not one fit
Depends on: — (1420 soft: its fixture may serve this one)
Priority: P3 2026-11-15 — `SeriesResult.direction_gaps` already lists the gap but does not say which answer to quote; the package's own passes now measured to disagree in cost on one public ramp (issue #1556, relative Rwp up to 1.4e-3), which keeps the row at P3: a diagnostic that says less than it could

## Goal

When the forward and backward chains disagree, the series result says, per
pattern, which pass reached the lower cost. A caller can ask for the better
one.

## Context

**What the package does now** *(superseded in part, 2026-11-16, checked
against the tree at `bc77a934e`: WP-2003 removed `SEQUENTIAL_PATH_DEPENDENT`
and its 3σ bar).* `direction="both"` runs the chain each way and lists every
path's gap at every pattern, unthresholded, as `SeriesResult.direction_gaps`:
one `DirectionGap` row per path and pattern, carrying both values, the signed
gap, the gap over the combined esd and both kept rungs
(`schemas/sequential.py:496`). The docstring still says "The reported entries
are the forward ones" (`src/rietx/sequential.py:1317-1318`). Its writer,
`_direction_gaps` (`sequential.py:3444`), compares parameter values and never
costs. The backward chain itself rides on the result as `series.backward`
(WP-1076), so each pattern's backward `Statistics` is already readable at
`series.backward.entries[j].statistics`; what nothing does is put the two
costs side by side or say which is lower.

Within one pattern the ladder already ranks attempts. `_prefer` and
`_better` (`sequential.py:2393-2418`) rank a diverged fit below a finished one,
rank a truncated attempt below a completed one, and then go on Rwp. A
backward pass is two more attempts at the same pattern, and nothing ranks
them against the forward one.

**Two limits on that argument.** Each pass sets its own WP-1301 holds and
cell windows, so the two passes search different feasible sets. A lower cost
is still the better fit to the data, but the two are not one problem solved
twice. And nobody has shown that `SequentialRefinement`'s own passes
disagree in cost. The evidence below comes from a hand-written chain. Task 1
measures the package's.

**The evidence.** A 2026-09-24 transcript review read an agent session on a
private synchrotron in-situ series of 48 patterns: `in-situ series 1` in the
private `yue-here/rietx-corpus-map`, which says where the data and the
transcript live. Quote only fit qualities and counts (CONTRIBUTING, WP-1450).
The phases came and went along the series, so the agent wrote its own chain
rather than use `SequentialRefinement` (WP-1420's `### Inherited` has that
half). It compared three solutions per pattern by hand: forward, backward
and a cold refit.

Neither direction won everywhere. Over the 27 patterns the agent compared,
the lower-BIC pass was the forward one at 13 and the backward one at 14. The
two differed by more than 10³ in BIC at 15 of the 27, inside the transition
windows and outside them. At one pattern the forward pass's χ²_red was 2.4×
the backward's, and at another the backward's was 1.5× the forward's. That
chain pruned phases, so the two passes sometimes fitted different phase
sets, and the agent ranked on BIC. With one phase list, χ² compares
directly.

**A public series** (issue #1556 § 1, 2026-11-15, folded from Inherited). On
the 11-BM CuCr₂O₄ + CuO ramp (`tests/data/seqrefine_cucr2o4/`, 17 patterns,
6.8-288.7 K, `direction="both"`) the reporter measured the relative Rwp
difference, forward minus backward, on the same points: up to 1.4e-3 (OH_49),
7.5e-4 (OH_41) and −8.3e-4 (OH_53). With CuO's cell held the two chains agree
to 1.4e-8 or better on 16 of 17 patterns, so the weak minor phase's cell
carries the history, not the cold start. The reporter proposes option 1 as a
χ² pair on each `DirectionGap` (Σw·Δ² on the same points), offering
`forward_chi2` and `backward_chi2` and leaving the names to the maintainer
(the issue's question 1, open). χ² is unchanged by any exact equivalence, so
the pair needs no ruling on the issue's § 2.

**The package's own passes, measured** (task 1, 2026-11-16, `[dev]`, darwin
arm64, tree `bc77a934e`). Issue #267's two-basin construction as WP-1420's
PR #1401 builds it (`tests/test_identity_point_seed.py` helpers, the
`tests/repro_1420.py chains` loop): a Cu `F m -3 m` parent and its
`I 4/m m m` subgroup, present from p004 at 0.15, 0.25 and 0.40 of the
parent's scale, seven noise draws (20260904 and 1-6), each sign of the true
distortion, so 42 series. The subgroup starts at the identity point,
`carry=("*",)`, `direction="both"`, defaults otherwise. Measured before
WP-1420's probe rung, which was never built (its tasks 2-5 went to issue
#1402). The cost is Σw·Δ² = `Statistics.chi2`·(N − P) per pattern and pass;
N was the same in both passes on all 336 pattern pairs.

- **They disagree, and only across basins.** At 36 of the 168 present
  pairs (p004-p007; 9 of 42 series, three per fraction) the two passes sat
  on opposite sides of the identity point. Σw·Δ² differed there by 3.6-6.8 %
  at 0.15, 11-15 % at 0.25 and 33-39 % at 0.40 (relative Rwp 1.8e-2 to
  1.5e-1), always at equal P. The lower-cost pass was on the true side in
  36 of 36, and it was the forward pass every time: the backward chain's
  cold start at p007 from the identity point fell to the wrong side in all
  42 series, as WP-1420 measured for cold fits. `direction_gaps` already
  saw these patterns (cell `|gap_esd|` 29-56 there); what it cannot say is
  which side is lower.
- **Agreement is not correctness.** At the other 132 present pairs both
  passes sat on the same wrong side, at costs equal to 1.7e-6 relative or
  better. A cost comparison is silent there, exactly as the value gaps are.
- **Off the onset the passes fit different parameter sets.** At p000-p003,
  where the subgroup is absent, P differed between the passes at 117 of 168
  pairs (WP-1301 holds the subgroup in one pass and not the other), and
  Σw·Δ² differed by up to 1.15e-3 relative (relative Rwp ≤ 5.7e-4). The pass
  with more free parameters was lower at 86 of those 117 and higher at 31.
  These noise-level differences are the size of #1556's CuCr₂O₄ ones
  (relative Rwp ≤ 1.4e-3), and a lower cost at a different P is not a better
  fit, which is "Two limits" above, now measured.

**The design question.** A per-pattern best mixes the two passes, so the
returned trajectory is no longer one chain. Each entry is still a converged
optimum of its own pattern. The options:

1. Report only. Each `SEQUENTIAL_PATH_DEPENDENT` finding carries the two
   costs, and the entries carry the backward cost beside the forward one.
   *(2026-11-16: the finding is now a `DirectionGap` row, one per path, so a
   per-pattern pair there repeats on every path's row at that pattern; and
   the entries' backward cost is already reachable through `series.backward`.)*
2. `keep="lower_cost"` returns the better pass per pattern and marks which
   one it took.
3. A cold rung at every pattern the two passes disagree on, ranked by
   `_prefer` with the other two.

Option 1 changes no fitted number and could land first. Its new field needs
its writer named at review (root CLAUDE.md, a declared name is a claim).

### Inherited

## Non-goals

- Choosing between different models. With different phase sets the
  comparison needs an information criterion, and WP-1417 owns ΔBIC at powder
  channel counts. 1417 closed with ΔBIC at N/f² and `report.compare_freed`
  for nested pairs, which refuses two models with different phase sets; a
  hand comparison takes each `Statistics.chi2` (reduced) back to Σw·Δ² at its
  own N − P before `report.delta_bic`.
- Changing how a single chain seeds its successor.

## Tasks

- [x] Measure whether the package's own passes disagree in cost: a synthetic
      series with a known two-basin pattern, run with `direction="both"`.
      The WP-1420 fixture (issue #267) may already be one. If the passes
      never disagree in cost, close this WP on that measurement.
      *(2026-11-16: they do, in 9 of 42 series, so the WP stays open;
      § Context, "The package's own passes, measured".)*
- [ ] Option 1: the costs on the finding and on the entry.
- [ ] Decide whether option 2 or 3 ships, and write the decision here.
- [ ] Tests: the fixture reports the right pass at the right pattern.
- [ ] Skill: `references/series.md`'s `direction="both"` paragraph says
      which pass to quote when the two disagree.

## Acceptance

On the fixture, the finding at the disagreeing pattern names the pass with
the lower cost, and quotes both costs.

```sh
.venv/bin/python -m pytest tests/test_sequential.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-0505 (the chain), WP-1051 (the ladder), WP-1127 (`_prefer`'s truncation
  rule), WP-1301 (the holds), WP-1417 (ΔBIC).

## Handover log

- **2026-09-24** — created from the review of an agent session on a private
  series. The forward-only return and the value-only comparison were checked
  against the tree at `2d42303a`. The pass counts and χ² ratios were
  re-read from the session's saved tables. Next: task 1.

# WP-1453 — both directions name the lower cost

Milestone: unscheduled · Status: ⬜
Depends on: — (1420 soft: its fixture may serve this one)
Priority: P3 2026-09-24 — `SEQUENTIAL_PATH_DEPENDENT` already fires but does not say which answer to quote; whether the package's own passes disagree in cost is unmeasured

## Goal

When the forward and backward chains disagree, the series result says, per
pattern, which pass reached the lower cost. A caller can ask for the better
one.

## Context

**What the package does now.** `direction="both"` runs the chain each way
and reports `SEQUENTIAL_PATH_DEPENDENT` where a parameter disagrees beyond
its esds. The docstring says so plainly: "The reported entries are the
forward ones" (`src/rietx/sequential.py:743-745`).
`_path_dependence_diagnostics` (`sequential.py:1937`) compares parameter
values and never costs.

Within one pattern the ladder already ranks attempts. `_prefer` and
`_better` (`sequential.py:1550`) rank a diverged fit below a finished one,
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

**The design question.** A per-pattern best mixes the two passes, so the
returned trajectory is no longer one chain. Each entry is still a converged
optimum of its own pattern. The options:

1. Report only. Each `SEQUENTIAL_PATH_DEPENDENT` finding carries the two
   costs, and the entries carry the backward cost beside the forward one.
2. `keep="lower_cost"` returns the better pass per pattern and marks which
   one it took.
3. A cold rung at every pattern the two passes disagree on, ranked by
   `_prefer` with the other two.

Option 1 changes no fitted number and could land first. Its new field needs
its writer named at review (root CLAUDE.md, a declared name is a claim).

### Inherited

- **From WP-1417, 2026-09-27: the ΔBIC this WP's Non-goals defers to
  is settled.** 1417 closed with ΔBIC at N/f² and
  `report.compare_freed` for nested pairs. Two models with different
  phase sets are not nested, so `compare_freed` refuses them. A hand
  comparison takes each `Statistics.chi2` (reduced) back to Σw·Δ² at
  its own N − P before `report.delta_bic`.

- **2026-09-24, from a review of the open WPs: task 1's fixture can be fixed
  out from under it.** Task 1 closes this WP if the two passes never
  disagree in cost, and it names WP-1420's #267 fixture as a candidate.
  1420's probe rung is written to bring the forward chain into the right
  basin on that fixture at all three fractions. Once it lands, the passes
  may agree there because 1420 fixed the forward chain, and a close on that
  measurement would be wrong. So measure before 1420's rung lands, or on a
  two-basin series with no held phase, and record which in the handover.

## Non-goals

- Choosing between different models. With different phase sets the
  comparison needs an information criterion, and WP-1417 owns ΔBIC at powder
  channel counts.
- Changing how a single chain seeds its successor.

## Tasks

- [ ] Measure whether the package's own passes disagree in cost: a synthetic
      series with a known two-basin pattern, run with `direction="both"`.
      The WP-1420 fixture (issue #267) may already be one. If the passes
      never disagree in cost, close this WP on that measurement.
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

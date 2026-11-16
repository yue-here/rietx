# WP-1524 — The step scan's last two blind spots

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Track: A long run is not one fit
Depends on: — (1469 landed the rule this extends)
Priority: P3 2026-09-29 — a false flag on a run of failed patterns, and a second real step on one path goes unreported; both on paths few series run

## Goal

`SEQUENTIAL_DISCONTINUITY` never bridges a gap it did not measure, and a path
with two real steps reports both.

## Context

> **Superseded in part, 2026-11-16** (checked against `bc77a934e`). WP-2003
> removed `SEQUENTIAL_DISCONTINUITY` and its three thresholds (released in
> 1.11.0). Its successor, `SeriesResult.steps` (`sequential._series_steps`),
> lists every refined path's step between consecutive patterns, with no
> threshold and no flag. Shape 1's rule landed there in c9c59b3fc (WP-2003's
> review fixes): a step is a row only between entries whose **series index**
> differs by 1, so a run of `SeriesFailure`s is a gap. That commit carried no
> test. Shape 2 is moot: no argmax is left, so a path with two steps has two
> rows. Since no threshold acts, task 2's measurement would count against
> legs that no longer exist, and it informs no code. The text below is the
> WP as filed. The tasks record what was done instead.

`sequential._discontinuity_steps` flags a step that is over
`DISCONTINUITY_FACTOR` (5) × the path's median step **and** over
`DISCONTINUITY_SIGMA` (3) × the two points' combined esd, one flag per path.
WP-1469 left out the steps into and out of a pattern the fence rejected
(`"diverged"`, or above the Rwp fence). It drops those steps rather than
bridging them, because a bridge over a run of k patterns spans k of the
series' steps and reads as k medians: a clean ramp flagged "8×" across seven
rejected patterns (1469's *Decisions taken*, item 2). Two shapes survive.

1. **A pattern with no entry is still bridged.** Under `on_error="carry"` or
   `"skip"`, a pattern on which every rung raised is a `SeriesFailure` and has
   no `SeriesEntry`, so `SeriesResult.trajectory` steps straight from its
   predecessor to its successor. A run of such failures on a ramp reads as one
   step of that many medians. This predates 1469; its review declined it as
   out of scope. The positions are in `Trajectory.positions` and the gaps are
   the missing `SeriesEntry.index` values between two consecutive points, so
   the scan can tell a bridge from a step.
2. **One flag per path.** `argmax` over the steps that pass both legs keeps
   the largest, so a path with two real steps (two transitions in one ramp)
   reports one. 1469 fixed the case where the other step was a rejected
   frame's. No issue has reported this shape yet, and the WP should measure
   whether it appears on the suite's real series before changing it.

**Why a new WP rather than a fold.** No open WP owns the step scan: 1420
owns a held phase re-entering a chain and 1453 the cost of running it both
ways, and 1469, which set the rule, is closed.

Two consumers read the flag and must move with it: `SeriesResult.discontinuities`
(one `SeriesStep` per diagnostic, `path` the key — which stops being a key if
a path can carry two) and the verification pass, which refits each flagged
pair once. `plot_trajectory` shades each recorded pair.

### Inherited

- **2026-10-17, from WP-1986 (writing the series guides): a cubic cell is
  flagged three times for one step.** On the synthetic LaB6 ramp of
  `examples/guides/_lab6_ramp.py` with the 700 K cell made 2 % larger,
  `SEQUENTIAL_DISCONTINUITY` fires once each for `phases.0.cell.a`, `.b` and
  `.c`, with identical messages, and `SeriesResult.discontinuities` holds
  three `SeriesStep`s for one pair of patterns. `b` and `c` are tied to `a`
  by symmetry. `SeriesResult.moved_paths` already drops a tied path that
  repeats an earlier candidate's values exactly; the step scan does not. The
  verification refit is shared, so the cost is three findings where a reader
  needs one. `examples/guides/path.py` asserts the three, so a fix updates
  that assertion and its page `docs/docs/guides/path.md`, which says the three
  flags share one pair of refits.

## Non-goals

- The fences' thresholds; neither shape is a threshold problem.
- A pattern above the Rwp fence or diverged: 1469 settled those.

## Tasks

- [x] Shape 1: drop the steps that span a missing index, as 1469 did for
      rejected patterns, with a test built from `SeriesFailure`s on a ramp.
      *2026-11-16:* the rule was already on `main` (c9c59b3fc, WP-2003), so
      this item is the test only:
      `tests/test_series_error_policy.py::test_a_run_of_failed_patterns_is_never_bridged_by_a_step`,
      with three consecutive patterns raising on every rung under `skip`
      and under `carry`. Its positive arm: with `adjacent` widened to
      `>= 1`, both cases fail on an extra `(2, 6)` row.
- [ ] Shape 2: measure how many paths on the suite's real series (round
      robin, the thermal and held-phase ramps) have a second step passing
      both legs; decide, and record here, whether to flag every such step.
      If they are flagged, `SeriesStep` needs a key other than `path`, and
      the verification and the plot follow.
- [ ] Tests: both shapes, and the suite's clean series firing nothing new
      (1469's counting wrapper, `SequentialRefinement._run`, is the recipe).
- [ ] Skill: the `SEQUENTIAL_DISCONTINUITY` row in `references/series.md` if
      a path can carry two flags; otherwise "none".

## Acceptance

A ramp with three consecutive failed patterns flags nothing; a ramp with two
planted steps on one path flags both, if task 2 decides so; the suite's
existing series fire nothing new.

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_series_error_policy.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1469 (the drop-not-bridge rule and its measurement), issue #481.
- WP-1333 (`SeriesFailure`, `on_error`), WP-1305 (the verification pass).

## Handover log

- **2026-09-29** — created, from WP-1469's session: shape 1 was the review's
  declined finding, shape 2 the limit its decision 2 recorded. Next: task 1,
  which is small; task 2 is a measurement first.

# WP-1524 — The step scan's last two blind spots

Milestone: unscheduled · Status: ✅ 2026-11-16
Track: A long run is not one fit
Depends on: — (1469 landed the rule this extends)

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
> WP as filed, less its *Inherited* note, which is now #1590. The tasks
> record what was done instead.

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
- [x] Shape 2: measure how many paths on the suite's real series (round
      robin, the thermal and held-phase ramps) have a second step passing
      both legs; decide, and record here, whether to flag every such step.
      If they are flagged, `SeriesStep` needs a key other than `path`, and
      the verification and the plot follow.
      *2026-11-16, superseded by WP-2003:* nothing is flagged and every step
      is a row, so a path with two steps already has both. There is one
      `SeriesStep` per (path, index pair), and `verify_steps=k` and the plot
      read rows. No measurement was run: the two legs it would count against
      are gone, and its answer would move no code. The behaviour is pinned
      by `tests/test_sequential.py::test_a_path_with_two_planted_steps_lists_both`.
- [x] Tests: both shapes, and the suite's clean series firing nothing new
      (1469's counting wrapper, `SequentialRefinement._run`, is the recipe).
      *2026-11-16:* the two tests above. No source changed, so no series
      can fire anything new, and the counting wrapper is not needed.
- [x] Skill: the `SEQUENTIAL_DISCONTINUITY` row in `references/series.md` if
      a path can carry two flags; otherwise "none".
      *2026-11-16:* none. The code is gone, and `references/series.md`
      already has `series.steps` and `verify_steps` rows.

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

- **2026-11-16** — closed. Ghostshift runner, PR #1588. The diagnostic this WP was
  filed against no longer exists. WP-2003 replaced it with a plain list of every step,
  and that change had already fixed both shapes. A run of failed patterns is a gap and
  never one step. A path with two transitions shows both. What was missing was a test
  for the first, which this session adds; it fails when the gap check is loosened. The
  one open question was inherited from WP-1986. Should a cubic cell's three tied axes
  give one row per step or three? And should the count of steps to re-check count them
  once? That question is the maintainer's, and it is #1590.

  *Done.* `cebd7ed06`: `test_a_run_of_failed_patterns_is_never_bridged_by_a_step`
  (`tests/test_series_error_policy.py`; patterns 3-5 of the eight-pattern ramp raise on
  every rung, under `skip` and under `carry`; `steps` keeps (0, 1), (1, 2), (6, 7)).
  `a1188e716`: `test_a_path_with_two_planted_steps_lists_both` (`tests/test_sequential.py`).
  Context marked superseded in part. Tasks ticked with what was done in place of each.
  No source changed. *Inherited* pruned: WP-1986's tied-axis finding is #1590, and
  WP-2003's next actions (item 2, "`verify_steps` counting tied rows") already own its
  `verify_steps` half.

  *Measured.* Positive arm: with `adjacent = np.diff(idx) >= 1`, both shape-1 cases fail on
  an extra `(2, 6)` row (Mac, darwin arm64, worktree venv `[dev]`); the source was restored
  by sed before the commit. The workstation (Linux x86-64 WSL2, venv `[dev]` 1.12.0.dev0, tree a1188e716,
  co-tenant). The canary, the two touched files plus audit_table, help and docs_consistency
  at `-n 4`: 260 passed. The fast suite at `-n 4`: 14853 passed, 280 skipped, 32 xfailed,
  0 failed in 934 s. Added-test cost from that run's junit: the shape-1 test 1.11 s (2 cases),
  the shape-2 test 0.00 s. Neither joins the slow tail. The full suite was not run: the branch
  is test-only. `tests.reader_output` exit 0 (unchanged). On the Mac: docs_consistency 26
  passed, ruff clean.

  *Review.* A read-only review subagent found nothing. It made one nit: say "one row per
  (path, index pair)" rather than "keyed by". It was taken. `/code-review` was not run,
  because the runner rules forbid it (it edits the main checkout).

  *Generality.* No `_audit.py` change, and no heuristic, default or threshold added. The judge
  was not dispatched.

  Next: none here. #1590 waits for the maintainer's ruling, and WP-2003's C4 touch takes it.

- **2026-09-29** — created, from WP-1469's session: shape 1 was the review's
  declined finding, shape 2 the limit its decision 2 recorded. Next: task 1,
  which is small; task 2 is a measurement first.

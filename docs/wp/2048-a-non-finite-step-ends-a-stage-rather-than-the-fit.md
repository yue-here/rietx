# WP-2048 — a non-finite step ends a stage rather than the fit

Milestone: unscheduled · Status: ✅ 2026-11-01 — every task done; PR #1292
Track: What fires, and what stays silent
Depends on: —

## Goal

A stage whose solve meets a non-finite residual or Jacobian ends with a
result and a diagnostic naming the stage and the paths it had free, never a
`ValueError` out of `Refinement.fit`.

## Context

`tests/test_cell_runaway_safety.py::test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error`
was red on the Linux nightly `full` job on `c9dde14` (run 40116626316,
2026-10-24) with `ValueError: array must not contain infs or NaNs`. The test
fits a valid but wrong ~7 Å³ P 1 cell to synthetic silicon in Le Bail mode
under `solver="trf"`, `profile_only` then `lab_bragg_brentano`. It passes on
an arm64 Mac at its own start.

**Reproduced on 2026-10-25** (`deff4c301`, macOS arm64, `[dev]`), by
multiplying cell `a`'s start by 1 + k·1e-14 (WP-1930's nudge). `profile_only`
ended at Rwp 0.3316 with one `CELL_RUNAWAY` at all six starts. The second plan
raised out of `fit` at four of six:

| k | second plan |
|---|---|
| 0, 3 | Rwp 0.354, three `CELL_RUNAWAY` |
| −1, 2, −2 | `ValueError: array must not contain infs or NaNs` |
| 1 | `ValueError: Residuals are not finite in the initial point.` |

The row passed on the next Linux nightly (run 40184228951, `deff4c301`), which
is the same rounding lottery read from the other side.

The two raise sites are different solves of one stage:

- `fit` → `_fit_pass` → `_run_plan` (`refine.py:5363`) → `_run_stage`'s first
  solve (`refine.py:4480`) → `run_least_squares` (`optimize/least_squares.py:2617`)
  → `_trf_svd` (`optimize/lapack.py:156`). The TRF step's SVD met a NaN in the
  Jacobian.
- `_run_stage`'s second solve, the support re-measure after a release or a
  collapse (`refine.py:4705`), into SciPy's `least_squares`, which refuses a
  non-finite residual at its starting point. So the first solve ended at
  values where the model is not finite, and nothing between the two solves
  checked.

The probe is `docs/wp/2048-batch/lebail_nudge.py`: the test's two fits in a
loop over k, about 2 min a start, printing every rietx frame of a raise. The test's own comment records that the same
trajectory read Rwp 127.7, 0.33, 7.8e6 and 1.1e9 at different starts, so the
fit is a non-fit by construction, and its claim is only that a result comes
back.

The tier of each rule this WP adds: `STAGE_NOT_FINITE` is tier 1, ambiguity 1
(arithmetic: neither driver has a step from a non-finite point), and its
suggestion tier 1, ambiguity 3 (it names the free set and the start and picks
neither). Ending the stage at its **start** rather than at the last finite
iterate is settled by Claude under in-package precedent: `reset_cell_runaway`'s
restore (WP-1528, PR #736), the collapse restore (WP-2002 B14) and a cancelled
stage's abandonment. At the second solve the last finite iterate is the
runaway the reset rejected, so the start is the only finite point there.
GSAS-II 5.8.4's `HessianLSQ` returns its current iterate on a failed
evaluation, and its caller then saves nothing (the generality judge's read).

## Non-goals

- Making the wrong cell fit. The test's cell is wrong on purpose.
- The LM driver, the default since WP-1938: under it the cell stays within
  0.01 Å of its start and the guard is never asked (the test's comment). Check
  it reaches the same guard, but its trajectory is not this WP's.

## Tasks

- [x] Find where the first non-finite value appears on a raising start (k = −1):
      the residual, a Jacobian column, or a decoded parameter, and which path.
      *Found 2026-11-01:* at k = −1 a **Jacobian column**, `phases.0.cell.alpha`,
      at a point TRF had accepted, where the residual was finite. TRF had
      already rejected 16 trial steps whose residual was NaN (the TCHZ
      Γ⁵ going negative under Y < 0, `pseudovoigt.py:45`). The decoded values
      there: zero shift −8584°, U −1.59, V −1.09, W 2412, Y −2.08. At k = 1 the
      first solve ends finite; the cell reset puts the cell back while the
      profile stays at its end (zero −9303°, U −91, V −1802, Y −97), and the
      **residual** at that mixture is NaN where the second solve begins.
- [x] End the stage there with a diagnostic, at the solve sites in `_run_stage`
      and in `multi.py`'s joint twin, never by catching `ValueError` around `fit`.
      *Done:* both solver entry points check the start residual and guard the
      Jacobian (`least_squares.NonFiniteStop`, `_FiniteJacobianGuard`); the
      stage ends at its start and says `STAGE_NOT_FINITE`.
- [x] Tests: the nudged start that raised now returns a result with the
      diagnostic; the test above stays green at all six starts.
      *Done:* `tests/test_non_finite_stage.py` injects both kinds on both
      solver entry points and through both runners; the slow row gains a
      `nudged` case (k = −1). All six starts return a finite Rwp (handover).
- [x] Skill: the new diagnostic code's row in `references/diagnostics.md`.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_cell_runaway_safety.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-2036 (found it on the nightly), WP-1930 (the nudge), WP-1528 and PR #736
  (`clamp_cell_runaway`'s restore), WP-1938 (LM as the default).

## Handover log

- **2026-11-01** — every task done; PR #1292. A refinement whose model
  turns into NaN or infinity partway through a stage no longer crashes out of
  `fit`. The stage stops, every value goes back to where the stage started, the
  plan carries on with the next stage, and a warning names the stage, what went
  non-finite and which parameters were free. All six nudged starts of the
  nightly's red row now return a result with a finite Rwp, where four raised.
  The values a stopped stage reached are discarded rather than kept. That was
  settled on in-package precedent, and it is the call the maintainer may want
  to look at (below).

  *Done.* `optimize/least_squares.py`: both solver entry points check the
  residual at the start and wrap every Jacobian in `_FiniteJacobianGuard`
  (outermost, over the degenerate-cell guard). A stop returns the solve's own
  start with `status="diverged"`, `termination="non_finite_residual|jacobian"`
  and `LSQOutcome.non_finite` (`NonFiniteStop`: kind, non-finite columns, free
  paths). `refine._run_stage`: a stopped first solve runs no second solve,
  scans no moment axes and skips the post-solve Le Bail update; a stopped
  second solve puts every entry back at `start_values`, Pawley intensities
  included, without committing. `multi.py` mirrors both
  (`_restore_stage_start`). `_answer_significance` keeps the screen when the
  Jacobian it builds is not finite. `STAGE_NOT_FINITE` (warning) is emitted per
  stage on both refine paths and the joint one; help entry, audit rows, skill
  row and silence pair added. No schema field and no `SCHEMA_VERSION` bump.

  *Measured* (macOS arm64, `[dev]` venv, this worktree's). The six nudged
  starts (probe `docs/wp/2048-batch/lebail_nudge.py`, second plan): k = 0 Rwp
  0.354 and k = 3 0.354 (no stage stopped), k = 2 0.385 (`lines_axial`,
  `roughness` and `closing` stopped on the Jacobian), k = −2 0.318
  (`lines_axial` stopped on the Jacobian),
  k = −1 0.571 (`lines_axial` stopped on the Jacobian, `roughness` on the
  residual), k = 1 9.4e6 (`lines_axial` and `closing` stopped). All are the
  same non-fit the row's comment describes. The slow row, now parametrised
  `start`/`nudged`: 2 passed, 291 s and 233 s with another suite running.
  Fast selection: 13 171 passed, 310 skipped, 32 xfailed, 1 failed (tests/test_display.py's kernel row: this Mac's Jupyter kernel spec points at a deleted venv, not this change), 12:30 with another runner's session active. Added tests: 1.56 s over the 6 added test functions, all in tests/test_non_finite_stage.py, slowest 0.86 s (local junit, macOS arm64).
  `python -m tests.reader_output`: exit 0, unchanged against `f4db77639`.

  *Review.* `/code-review high --fix` found 10. Fixed: the second-stop restore
  now covers every path (a moment turned between the solves stayed turned);
  no moment scan on a stopped stage; no significance off a non-finite
  Jacobian; the TRF sentence only under TRF; column sums before a full mask;
  one redundant parameter. Declined: the release, collapse and cell-reset
  records stay after a second-solve stop, since they record what the stage
  decided and the next plan stage replaces the vary flags anyway; a NaN start
  cost stays NaN in the `stage_end` event, as TRF's rejected trials already
  write NaN `eval` costs; the two driver dispatches stay separate; the nudged
  row's assertion stays pinned to darwin/arm64, where it was measured.

  *Generality* (judge's sections, unedited in substance):
  `STAGE_NOT_FINITE` **holds** (tier 1, kind 1; would change it: a named
  refiner who continues from a non-finite point). `.suggestion` was **weak,
  mis-tiered**: the width-and-zero-shift pointer rested on one fixture.
  Author: the pointer is removed from the suggestion, the help entry and the
  audit row, which now name only the free set and the start, plus TRF's
  missing width floor under TRF. The end-at-start action **holds**, lean
  tier 2 (GSAS-II keeps the start in its project file; the other six not
  checked); gap: `StageResult`'s docstring said "no fourth" way to build an
  outcome. Author: the docstring now says a non-finite stop is one more way
  to `diverged`. Would change it: a fit whose stage gained real ground before
  a late NaN, and what the start then cost it against a reference.

  *Gotchas.* The trigger is TRF with no floor under the widths: the TCHZ
  Γ⁵ goes negative once Y < 0. Under the default LM driver the floors hold
  and the row never reaches this. A rigid-body anchor survives a second-solve
  stop because nothing is committed before the restore; a commit there would
  have replaced the anchor the restore reads.

  **Settled by Claude:** the stage ends at its start, not at the last finite
  iterate (grounds above); `STAGE_NOT_FINITE` is a new code rather than a
  `StageResult` field.

  Next: none in this WP. WP-2036's nightly waits on 2049 and 2050 once #1292
  merges.

- **2026-10-25** — filed by WP-2036's session, which reproduced the nightly's
  raise under start nudges. No open WP owns it: WP-1528 holds only `Cell`'s
  docstring, and WP-1334 a stage's budget. Next: the first task, at k = −1.

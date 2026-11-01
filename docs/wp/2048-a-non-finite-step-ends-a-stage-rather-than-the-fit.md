# WP-2048 — a non-finite step ends a stage rather than the fit

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-25 — a raise out of a public `fit`, on a path few fits run (TRF on a wrong cell), with no workaround but another start

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

The tier of each rule this WP adds: none decided yet. Ending a stage on a
non-finite value and reporting it is an automatic action whose ambiguity is
none (no competent refiner continues from a NaN). The choice of which values
the stage ends at (its start, or the last finite iterate) is new judgement,
and the guard's existing precedent is `clamp_cell_runaway`'s restore to the
stage's starting values (WP-1528's log, PR #736).

## Non-goals

- Making the wrong cell fit. The test's cell is wrong on purpose.
- The LM driver, the default since WP-1938: under it the cell stays within
  0.01 Å of its start and the guard is never asked (the test's comment). Check
  it reaches the same guard, but its trajectory is not this WP's.

## Tasks

- [ ] Find where the first non-finite value appears on a raising start (k = −1):
      the residual, a Jacobian column, or a decoded parameter, and which path.
- [ ] End the stage there with a diagnostic, at the solve sites in `_run_stage`
      and in `multi.py`'s joint twin, never by catching `ValueError` around `fit`.
- [ ] Tests: the nudged start that raised now returns a result with the
      diagnostic; the test above stays green at all six starts.
- [ ] Skill: the new diagnostic code's row in `references/diagnostics.md`.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_cell_runaway_safety.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-2036 (found it on the nightly), WP-1930 (the nudge), WP-1528 and PR #736
  (`clamp_cell_runaway`'s restore), WP-1938 (LM as the default).

## Handover log

- **2026-10-25** — filed by WP-2036's session, which reproduced the nightly's
  raise under start nudges. No open WP owns it: WP-1528 holds only `Cell`'s
  docstring, and WP-1334 a stage's budget. Next: the first task, at k = −1.

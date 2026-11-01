# WP-1999 — a held cell's ties leave the answer with it

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-10-18 — a reported value that is not a measurement, on the series path (a trajectory point with no fit behind it)

## Goal

When WP-1301 holds a phase's cell for a stage, every parameter tied to a held
path leaves `RefinementResult.parameters` with it. A series trajectory then
has no point at that pattern for any cell edge, where today it has none for
`a` and a stale one for `b` and `c`.

## Context

Found by WP-1545's notebook 05 lane (2026-10-18), on the broken-frame series:
at 700 K the phase's scale reaches its floor, `PHASE_UNCONSTRAINED` holds the
cell, and `series.trajectory("phases.0.cell.a")` correctly has no 700 K point.
`trajectory("phases.0.cell.b")` does. Its value is the previous pattern's
carried value and its esd is `None`.

**The mechanism.** The hold sets a held path's `vary` to `False` before the
answer is built. The result's rows come from `refine.py:6953`, which keeps an
entry when `e.vary or e.tie is not None or e.path in derived`. A tetragonal or
cubic cell ties `b` (and `c`) to `a`, so the followers pass on their tie while
their source is gone. Root CLAUDE.md's hold clause says "a value that is not a
measurement is the caller's: held paths leave `RefinementResult.parameters`".
The followers are the same non-measurement.

**What to decide.** Whether the filter should drop a tied row whose sources are
all held (the narrow fix), or every tied row whose sources do not move
(`ParameterTable.moving_paths`, the root rule for "can this parameter move?").
The second also drops followers of a user-fixed source, which every result
reports today with esd `None`. That changes the reported set for ordinary fits,
so measure how many goldens and tests move before choosing.

- The tier of each rule this WP adds: none. It changes which rows a result
  lists and adds no flag, threshold, default or automatic action.

## Tasks

- [x] Reproduce with a single fit (a cubic phase whose scale is floored) and
  with WP-1545's notebook 05 broken series. Single fit on main 62034506e (the
  absent-phase fixture, `mccusker_default`): `phases.1.cell.a` held and absent,
  `b` and `c` reported at 5.2 with `vary=False` and no esd. Notebook 05's
  broken series on the fixed tree: `a`, `b` and `c` all have six points and no
  700 K point.
- [x] Choose the narrow or the `moving_paths` rule, with the count of moved
  tests for each. Rows each rule drops, measured on six fits (probe in the
  handover): the narrow rule drops 2 rows on the held fit and none elsewhere;
  the `moving_paths` rule drops 4 on the held fit, 1 on LaB6 `mccusker_default`
  (the B site's `x`), 3 on LaB6 `lab_calibrate` with the cell held (`b`, `c`,
  `x`), 1 on LaB6 Le Bail, 0 on LaB6 `mccusker_structural`, and 16 of 44 on the
  11-BM NAC walkthrough (coordinates of sites no stage frees). Tests moved by
  the `moving_paths` rule: 3 of the 1064 in the 25 files that read result rows
  (one count, two pins of "a held source's followers report with no esd").
  The narrow rule would move the same two pins and not the count. **Chose
  `moving_paths`** (settled by Claude under root CLAUDE.md's "can this
  parameter move? is `moving_paths`" and the result contract's "a fixed
  parameter is absent"; the change to what a fit returns goes to the
  maintainer before merge under the 2026-11-01 reader-output ruling).
- [x] The fix at `refine.py:6953` (now `_build_result`, `refine.py:8428`), and
  a test that a held source's followers leave `parameters` and the trajectory
  (`tests/test_reported_rows_move.py`).
- [x] Find the siblings. Same leak, fixed: the joint fit's own row builder
  (`MultiHistogramRefinement._parameters`), and `stage_reports_`, which builds through
  `_build_result` and so inherits the fix. Not leaks: `Refinement.parameters()`
  and the GUI's parameter table read the whole table by design, each held row
  naming its reason; the CIF export writes all six cell edges from the model
  and only reads esds from the rows. Statements of the old rule rewritten:
  `RefinedParameter`'s docstring, `reference/parameter-table.md`,
  `_display.refined_parameter_text`, `refine._moved`,
  `topas_refined._result_rows`, root CLAUDE.md's hold clause. Left alone:
  `sequential._path_dependence_diagnostics`' docstring still cites "a tie row
  off a source never freed" as one reason for its esd filter; the filter is
  still right, and the function is WP-1991's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_held_phase.py tests/test_sequential.py tests/test_reported_rows_move.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-18** — filed by WP-1545's session. No open WP owns it: WP-1420 is
  about a held phase *re-entering* a chain, and this is a reporting leak a
  single fit shows too.

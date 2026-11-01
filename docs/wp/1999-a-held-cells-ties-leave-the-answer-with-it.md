# WP-1999 — a held cell's ties leave the answer with it

Milestone: unscheduled · Status: ✅ 2026-11-01 — a result lists only the rows the fit could move (`moving_paths`), PR #1046
Track: A long run is not one fit
Depends on: —

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

- **2026-11-01** — closed, PR #1046 (a ghostshift runner continued the
  2026-10-18 claim branch, main merged in). A result now lists a parameter
  only when the fit could move it. Before, a tied parameter was listed
  whatever its source did, so a cubic `b` and `c` stayed in the answer beside
  a held or fixed `a`, at the carried value and with no esd. A series then
  drew a trajectory point where it had measured nothing. The rule that closes
  it is wider than the held-cell case: it also drops the coordinates of every
  site no stage frees, which were a third of the rows on the 11-BM NAC
  walkthrough. This changes what a fit returns by default, so the maintainer
  rules on it before merge (the 2026-11-01 reader-output ruling).

  *Decision, settled by Claude under root CLAUDE.md's "can this parameter
  move? is `moving_paths`" and the result contract's "a fixed parameter is
  absent".* The narrow rule (drop a tied row whose sources the stage held)
  was the alternative. It fixes the held cell and leaves the same leak for a
  cell the caller holds: `lab_calibrate` with the certified cell held still
  reported `b` and `c` and not `a`. The maintainer is asked to confirm at
  merge, because the change moves an ordinary fit's `parameters` list and
  the `RefinedParameter` docstring's literal "varied or tied" said otherwise.

  *Done.* `refine._build_result` and `MultiHistogramRefinement._parameters`
  keep a row iff `ParameterTable.moving_paths` holds it (each joint table
  asks its own). `stage_reports_` builds through `_build_result` and
  inherits it. Statements of the old rule rewritten: `RefinedParameter`,
  `reference/parameter-table.md`, the skill's `CELL_RUNAWAY` row (copies
  re-synced), `_display.refined_parameter_text`, `refine._moved`,
  `topas_refined._result_rows`, a benchmark comment, a TOPAS test docstring,
  root CLAUDE.md's hold clause. New `tests/test_reported_rows_move.py`
  (5 tests: held cell, held-phase trajectory, held certified cell, unfreed
  coordinate, joint fit), each failing on the old filter (mutation run: 5 of
  5 red). Re-pinned: `test_result_rows` (Le Bail NAC count 18 tied → 2), two
  `test_cell_runaway_safety` rows and one joint twin (the held value now
  read off the working model), two `test_parametric_series` asserts.

  *Measured* (`[dev]` venv, darwin/arm64, main 62034506e). Rows each rule
  drops, probe `~/.cache/ghostshift/rietx/wp-1999/probe_rules.py`: held-phase
  fit 2 narrow / 4 `moving_paths`; LaB6 `mccusker_default` 0 / 1; LaB6
  `mccusker_structural` 0 / 0; LaB6 `lab_calibrate`, cell held 0 / 3; LaB6
  Le Bail 0 / 1; NAC walkthrough 0 / 16 of 44. Notebook 05's broken series:
  `a`, `b` and `c` each have six points and no 700 K point. Targeted runs
  before the fast suite: 25 files 1060 passed + 4 failed, then 49 files 1457
  passed + 3 failed; every failure but one pinned the leak and was re-pinned,
  the one being `test_display`'s kernel test, which fails on this Mac's stale
  Jupyter kernel spec. `python -m tests.reader_output`: exit 0, the printed
  LaB6 text is unchanged; the change is in the field. Fast suite (`-m "not slow"`, `[dev]`, darwin/arm64, tree 50be32b56, run under
  the shift's suite lock): 13191 passed, 310 skipped, 32 xfailed, 1 failed in 8:18.
  The failure is `test_display`'s kernel test again (the stale kernel spec). The 5
  added tests are 5 passes and cost 4.14 s on one local run, the slowest 1.28 s
  (`tests.added_test_times`), so none joins the slow tail. No local baseline count,
  so the +5 is not checked against main; CI's run is the comparison. The full
  suite did not run: the brief allowed the fast selection once.

  *Review.* `/code-review high --fix`: nine findings, seven fixed (commit
  a5eefefe1). Declined: simplifying `refine._moved`, since it changes what
  `summary()` prints; and a test that a tie inherits a withheld esd. The
  "end" arm of `test_a_reset_cells_stderr_is_withheld` carried that check
  through the rows this WP removes, so `_cell_runaway_withheld`'s tie loop
  now has no test in either builder. A fixture that keeps a reset cell free
  at the answer (a late restore, or a free `vars.X` driving it) would. No
  open WP owns it.

  *Gotchas.* `Refinement.parameters()` and the GUI's parameter table are not
  this leak: they list the whole table by design, each held row naming why.
  `sequential._path_dependence_diagnostics`' docstring still cites "a tie row
  off a source never freed" as a reason for its esd filter; the filter is
  right and the function is WP-1991's, so it was left. WP-1325 inherits that
  a held coefficient's target rows leave `parameters`.

  Next: the maintainer confirms the `moving_paths` rule or asks for the
  narrow one (a two-line change in each builder, with the coordinate and
  `lab_calibrate` tests dropped). Then the tie-withholding test above, if
  anyone takes it.
- **2026-10-18** — filed by WP-1545's session. No open WP owns it: WP-1420 is
  about a held phase *re-entering* a chain, and this is a reporting leak a
  single fit shows too.

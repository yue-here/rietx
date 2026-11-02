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

- **2026-11-02** — a ghostshift runner took main's red slow test to PR
  #PRNUM. `test_acceptance_si640c.py::test_the_held_cell_is_the_certificate`
  raised KeyError on `phases.0.cell.b` after PR #1046 merged. The test was
  wrong and the behaviour is the ruled one. The si640c fit holds the
  certified cell and never frees it, so its cubic `b` and `c` are exactly the
  rows the 2026-11-01 ruling removed from the answer. The test now reads the
  held cell from the model and asserts the answer has no cell row. It was the
  only casualty: the whole slow tier is green on the fixed tree. This entry
  corrects this closed WP's own record and asks for no work.

  *Cause, verified.* `refine._build_result` keeps a row only when
  `ParameterTable.moving_paths` holds it. The si640c plan's stages never
  match `phases.0.cell.a`, so `a` cannot move, and `b` and `c` are tied to
  it. #1046's own table lists the same case (LaB6 `lab_calibrate` with the
  cell held drops `b`, `c` and `x`). #1046 did not run the slow tier, which
  is where this test lives.

  *Done.* The test takes a new `full_fit` fixture, which returns the
  refinement beside the result, so the one fit is still shared. It asserts
  four things. The answer has no cell row. No stage's `freed` list holds a
  cell path. `a`, `b` and `c` in `Refinement.parameters()` equal the
  certificate to the bit. `b` and `c` are tied to `phases.0.cell.a` by name.
  The generated sibling followed: the claim in `tests/validation_matrix.py`
  and the `docs/VALIDATION.md` entry rendered from it. `/code-review high
  --fix` made five findings and three are fixed. The old esd check could
  never fail, because a parameter-table row takes its esd from the answer's
  row. The final `vary` flag says only what the last stage freed. The tie
  check did not name its source. Declined: folding `_fit` into
  `_fit_with_model`, which is cosmetic.

  *Siblings.* No other reader of a held source's tied follower was found.
  The static sweep covered `src/`, `examples/`, `docs/` and the skill.
  `examples/guides/cell.py` reads `cell.b`, but its `a` is free. The slow
  tier ran whole as the empirical sweep, with 0 failures.

  *Measured* (`[dev]` venv, darwin/arm64, tree 6eb40ac04, each run under the
  shift's suite lock with nothing else running). The si640c file: 18
  passed. The slow tier (`-m slow`): 912 passed, 21 skipped, 18 xfailed, 0
  failed, in 30:04. The fast selection: 13286 passed, 310 skipped, 32
  xfailed, 0 failed, in 7:43. No test was added, so passed+skipped owes no
  delta. `python -m tests.reader_output` exited 0, so the printed text is
  unchanged. After origin/main was merged in (b397dcd3e), the si640c file,
  `test_reported_rows_move.py`, `test_validation_matrix.py` and
  `test_docs_consistency.py` were re-run: 790 passed, 0 skipped.

  Next: merge the PR. Nothing else is owed here.
- **2026-11-02** — a ghostshift runner chased the Kernels workflow's
  intermittent macOS x86_64 failure on this PR. *Cause:* the gate, not this
  PR. The PR reaches Kernels only through a comment in
  `examples/bench_refinement.py`. The step "Agreement with the numpy path
  inside two real fits" compares a fit on the twins (the bench's numpy copies
  of the kernels) with a numpy-path fit. It gates that only when a second
  numpy-path fit agrees bit for bit. On that runner the numpy path differs
  from itself between some fits and not others (WP-1940's handover, up to
  7.1e-1 esd), so one agreeing pair proves nothing. *Evidence:* the same
  verdict ("the twins left the numpy path in: trigger") on three other
  branches: runs 38603684026, 38896527839 and 38924988380. Here, cpd-1a's
  twins sat 1.4e-06 esd away in run 41367944436 (attempt 1). The numpy path's
  own pair on cpd-1a differed by 1.1e-06 in run 41378211395. Trigger's twins
  sat 3.0e-06 away in 41378211395, and its numpy pair differed by 1.7e-07 in
  41367944436. The rows "with the same value and another esd" (7 on trigger,
  9 on cpd-1a) are exactly each fit's free rows sitting on a bound of 0
  (`gauss_size`, `gauss_strain`, `lor_strain`, one `biso`), with esds from
  8.8e-02 to 1.4e+02. This PR neither adds nor removes them. Under Rosetta 2
  the numpy path reproduced itself (four trigger fits, three cpd-1a fits),
  so the noise is the runner's. *Fix:* `bench_aot_kernels.NONDETERMINISTIC`
  names macOS x86_64, and `twins_verdict` reports rather than gates the
  twins' gap there whatever the numpy pair did. Every kernel call still meets
  its bar on that platform, and the four deterministic platforms still gate
  the twins. New test
  `test_one_agreeing_numpy_pair_does_not_make_a_noisy_platform_checkable`
  (red on the old verdict). *Not done:* whether one Accelerate thread
  (`VECLIB_MAXIMUM_THREADS=1`) makes that runner deterministic. That is
  WP-1940's hypothesis and would let the gate return there. It needs a run
  on the Intel runner, which Rosetta cannot stand in for.

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

  *Ruled 2026-11-01 by Yue, "option 1"*: `RefinementResult.parameters` lists
  a row only when `ParameterTable.moving_paths` holds it, over the narrow
  rule. *Consumer audit* (the flip condition: a user-facing reader needing a
  fixed row from `result.parameters`): none found. Of 35 reading sites in
  `src/` and about 15 in `examples/` and the manual, the CIF writer and the
  recipe CSVs take values from the model and only esds from the rows (a
  dropped row had none); the GUI and `.rxt` read `Refinement.parameters()`;
  the rest read free rows, esds, or trajectories, where a dropped row is a
  constant the series did not measure. So nothing needed fixing;
  `test_the_cif_still_states_every_row_the_answer_dropped` pins that the CIF
  still carries every cell length and coordinate, a dropped one with no su.

  *Done.* `refine._build_result` and `MultiHistogramRefinement._parameters`
  keep a row iff `ParameterTable.moving_paths` holds it (each joint table
  asks its own). `stage_reports_` builds through `_build_result` and
  inherits it. Statements of the old rule rewritten: `RefinedParameter`,
  `reference/parameter-table.md`, the skill's `CELL_RUNAWAY` row (copies
  re-synced), `_display.refined_parameter_text`, `refine._moved`,
  `topas_refined._result_rows`, a benchmark comment, a TOPAS test docstring,
  root CLAUDE.md's hold clause. New `tests/test_reported_rows_move.py`
  (5 tests: held cell, held-phase trajectory, held certified cell, unfreed
  coordinate, joint fit; the ruling session added two, the CIF and the
  withheld esd), each failing on the old filter (mutation run: 5 of
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
  through the rows this WP removes. The ruling session added
  `test_a_tied_row_inherits_a_withheld_esd`, which rebuilds a LaB6 answer
  from its own covariance with a `CELL_RUNAWAY` finding handed in, so `b`
  and `c` must lose their esd with `a` (fails with the tie loop disabled).
  *Not done:* the joint builder's copy of that loop (`multi.py`) is still
  untested, and no real fit reaches the case, since a reset cell is held.

  *Gotchas.* `Refinement.parameters()` and the GUI's parameter table are not
  this leak: they list the whole table by design, each held row naming why.
  `sequential._path_dependence_diagnostics`' docstring still cites "a tie row
  off a source never freed" as a reason for its esd filter; the filter is
  right and the function is WP-1991's, so it was left. WP-1325 inherits that
  a held coefficient's target rows leave `parameters`.

  Next: merge, the rule being ruled. The joint builder's withholding test
  above, if anyone takes it.
- **2026-10-18** — filed by WP-1545's session. No open WP owns it: WP-1420 is
  about a held phase *re-entering* a chain, and this is a reporting leak a
  single fit shows too.

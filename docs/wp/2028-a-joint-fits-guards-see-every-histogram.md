# WP-2028 — a joint fit's guards see every histogram

Milestone: unscheduled · Status: 🔄 2026-10-23 — tasks 1-3, 5, 6 built, on review; 4 measured; 7 and 8 open
Track: What fires, and what stays silent
Depends on: — (1341 closed: it built the joint report this WP completes; 1325
soft: its parametric codes and per-pattern holds are what tasks 3 and 6
render; 1421 soft: the joint fit's compile at the answer, which decides whether
a report after a width stage can be trusted)
Priority: P2 2026-10-23 — a joint fit with per-histogram structure has its specimen guards read histogram 0 alone and its per-pattern holds named nowhere: a wrong value nothing flags, on a path few fits run

## Goal

A joint fit's guards and diagnostics read every histogram's values. A guard
that reads a table reads each histogram's, a hold made in some patterns says
which, the joint support test says whether it takes WP-1523's significance
reading, and each histogram's report shows the fit-level findings that name it.

## Context

**What exists.** WP-1341 (closed 2026-10-23) gave `MultiHistogramRefinement`
(`src/rietx/multi.py`) events, `cancel=`, `max_shift_over_esd` and
`report(h)`: Layers 0-2 built off `result_.for_histogram(h)` and histogram h's
compiled model and frozen answer (`_freeze_answer`). Two tables place every
check. `DIAGNOSTIC_SCOPES` (`multi.py:195`) puts each `_*_diagnostics` helper
at `HISTOGRAM`, `SPECIMEN`, `FIT` or `ABSENT`, and `GUARD_SCOPES`
(`multi.py:338`) does the same for each `GuardReport` field.
`tests/test_multi_diagnostics.py` holds both tables against `_build_result`.
What follows was left open by 1341, or arrived in its Inherited section after
its work landed. Line numbers are as of 2026-10-23.

**Why the tables are now wrong in places.** Both were written when the
structure was one object shared by every histogram. Since WP-1325 a structural
path can be per histogram: a `SharingMap(per_histogram=["phases.*"])` override,
or a parametric target whose `vars.` coefficients set a `hist.<h>.` row. The
joint support hold already follows that change (1325, 2026-10-14):
`_joint_unsupported_phases` (`multi.py:391`) and `_unseen` (`:424`) judge each
entry a column reaches in its own histogram, and joint stages write
`StageResult.held_reach`. The guards and the reports have not followed.

1. **The specimen guards read histogram 0's table only.** `_top_diagnostics`
   (`multi.py:2080`) runs `check_adp_positive_definite`,
   `check_biso_plausible` and `check_biso_negative` on `mt.tables[0]` and
   `models[0]`, and `GUARD_SCOPES` gives the reason "every histogram's gives
   the same". A per-histogram path is checked in histogram 0 alone, so a bad
   value in histogram 2 fires nothing. This predates 1325. `_stephens_once`
   and `_texture_once` already loop every histogram and keep one finding per
   path, which is the shape to copy.
2. **The joint `CELL_RUNAWAY` names no coefficient.** The single fit's
   `refine._vars_driven_cell_escapes` (`refine.py:1401`) names a cell that a
   `vars.` coefficient drives out of its window. The joint reset,
   `_reset_cell_runaway_multi` (`multi.py:871`), has no twin of it.
3. **A per-pattern hold is in no diagnostic.** The hold is on
   `StageResult.held`, but `PHASE_UNCONSTRAINED` names only a phase that no
   histogram sees (`DIAGNOSTIC_SCOPES`' row for `_phase_support_diagnostics`
   still says "a phase is unseen only when every histogram misses it"). So
   nothing says "held in 12 of 33 patterns". `PARAMETRIC_TARGET_UNSEEN`
   (`multi.py:2284`) says it per equation, for parametric targets only.
4. **The joint support test reads the screen alone.** A single fit calls a
   phase seen when its scale is 3σ from zero, conditional on the other
   phases' scales (`refine._answer_significance`, `refine.py:1757`, WP-1523).
   The joint path reads only `CompiledModel.phase_support`, and the docstring
   at `multi.py:408-411` leaves the choice to the joint report. Measured
   elsewhere: on issue #481's blank frame `phase_support` reached 3.1-4.4σ
   once a released cell chased the noise (WP-1523). On 1325's ZrMo₂O₈ ramp
   the chain held a fading phase in 2 of 33 patterns by the significance
   test, and the joint fit left the same 14 columns free. Open: whether the
   joint path takes the test, and how histograms combine (in quadrature, or
   the joint covariance's own marginal). The answer also changes which
   patterns `PARAMETRIC_FORM_REJECTED`'s score test sees, since it leaves out
   the patterns `_unseen` holds.
5. **A histogram view drops two fields** (found by WP-1986, 2026-10-20).
   `HistogramResult` carries `tick_hkl` and `phase_agreement`
   (`multi.py:1821`, `:1826`), but `RefinementResult.for_histogram`
   (`schemas/results.py:1780`) copies `ticks` alone (`:1821`), and the joint
   top level passes `ticks=histograms[0].ticks` with no `tick_hkl`
   (`multi.py:1962`). So a view's ticks name no reflection and its structure
   R-factors are empty. `docs/docs/reference/joint.md:251` documents the gap.
6. **Fit-level findings reach no histogram's report.** `report(h)` reads the
   view, whose `diagnostics` are histogram h's own (`schemas/results.py:1825`).
   The top-level ones are reported nowhere a reader of one histogram looks:
   `STAGE_FREED_NOTHING` (one per histogram, `value` the index,
   `multi.py:2438`), `STAGE_PATH_UNKNOWN`, `SCALE_B_INSEPARABLE` (WP-1534),
   and 1325's three, `PARAMETRIC_OUT_OF_RANGE`, `PARAMETRIC_FORM_REJECTED` and
   `PARAMETRIC_TARGET_UNSEEN`. The parametric data a report would quote beside
   a row is already on the result: `RefinedParameter.equations` on the view's
   rows, `RefinementResult.parametric`, `parametric_form` (each
   `ParametricFormTest` has `tied` and `others_freed` readings),
   `parametric_form_joint`, `parametric_equations`, and `parametric_value()`,
   which evaluates an equation at any coordinate.
7. **Nobody has listed what else `multi.py` re-derives.** WP-1344 placed every
   diagnostics helper but not the other members that re-derive something
   `Refinement` derives. `_ticks` (`multi.py:1604`) is the known case, left
   while WP-1908 edited the tick builders; 1908 closed 2026-10-15. WP-1103's
   rule holds: a declared peak belongs to every histogram that sees it. Root
   CLAUDE.md puts it as "a second builder of anything (`multi.py` keeps its
   own) is the miss". `MultiHistogramRefinement` also has no `parameters()`, so
   `STAGE_PATH_UNKNOWN`'s suggestion names the `mtable` listing instead. The
   joint path also runs neither the declared-peak screen nor the parameter-space
   screens (`schemas/results.py:391-395`), so `extra_peak_absorption` is always
   empty on a joint fit (1341's review).
8. **`DATA_SUPPORT_LOW`'s ratio half is not asked on a joint fit.**
   `DIAGNOSTIC_SCOPES['_data_support_diagnostics']` (`multi.py:230-237`) passes
   `support=None`, since McCusker's observations-per-parameter has no agreed joint
   definition, and calls it "WP-1341's territory". 1341 closed without a definition.
   Three more comments name WP-1341 as the owner of future work: `multi.py:411`,
   `:1920` and `:1923`.

**Rules this WP may add, and their tier** (generality § The rule,
`docs/milestones/generality.md`). Tasks 1, 2 and 5 add no rule: each runs an
existing check on more tables, or copies a field. Task 3 reports a hold the
fit already made, which is an action recorded in a field (DESIGN.md § Rules,
1); its text is the number with its meaning, "held in k of n". Task 4 is new
judgement unless it reads WP-1523's test unchanged on the joint covariance.
How histograms combine is a choice, and it must be measured on #481's blank
frame, 1325's ZrMo₂O₈ ramp and `tests/test_multi_histogram.py`'s LaB6 pair
before it is written. From WP-2001/2004 (2026-10-18): a gate added to the
joint report is a tier-3 heuristic and will be asked for its evidence; its
output follows DESIGN.md § Rules, 1 (a verdict only where every competent
refiner would draw it, a ranking where the data rank the alternatives,
otherwise the number with its meaning); and a threshold added here bumps
`THRESHOLDS_VERSION` (history in `report/schemas.py`) in this WP. A new code
also needs its `_audit` row with a tier, a `help.py` entry, a
`DIAGNOSTIC_SCOPES` row, and a skill reference row.

**Constraints carried from 1341.** No joint-fit number moves except where a
task says it does. Task 4 can move holds, and so values; measure what moves.
The specimen has one crystallite size (WP-1131), and a report quotes it once.
The joint fit's curves come from the last stage's compile, not a compile at
the answer, which is WP-1421's; a Layer 0 reading after a width stage carries
that caveat until 1421 lands.

## Non-goals

- The joint fit's compile at the answer (the #272 sibling): WP-1421.
- The report's cost, and `stage_reports=` on a joint fit: WP-1335.
- Tiering the single fit's report gates: WP-2004, which touches no joint-fit
  code.
- Issue #442 (`unreached_histograms`), which the maintainer tied to the TOF
  design on 2026-09-24.
- New joint physics. This is guards and reporting over a fit that works.

## Tasks

- [x] Specimen guards over every histogram: `_top_diagnostics` runs the ADP
      and both Biso checks on each histogram's table and model, one finding
      per path, a per-histogram path named with its histogram; the three
      `GUARD_SCOPES` reasons say so. Test: a negative Biso set in histogram 1
      alone, through a `SharingMap(per_histogram=…)` override, fires.
- [x] The joint `CELL_RUNAWAY` names the coefficient: a twin of
      `refine._vars_driven_cell_escapes` in the joint reset. Test: a
      parametric cell driven out of its window is named with its `vars.`
      path.
- [x] A per-pattern hold is reported: a finding naming the phase and the
      patterns where its per-histogram structure was held, agreeing with
      `PARAMETRIC_TARGET_UNSEEN` rather than repeating it for parametric
      targets. Update the `_phase_support_diagnostics` scope reason.
- [ ] Decide WP-1523's test on the joint path: measure the three datasets
      named in Context, then take it (and how histograms combine) or write
      why not where `_joint_unsupported_phases` declares the choice. Record
      what moves, including `PARAMETRIC_FORM_REJECTED`'s pattern set.
- [x] The view keeps `tick_hkl` and `phase_agreement`: `for_histogram`
      copies both from `HistogramResult`, the joint top level passes
      histogram 0's `tick_hkl` beside its ticks, and the caveat at
      `docs/docs/reference/joint.md:251` goes.
- [x] Fit-level findings in each histogram's report: the findings that name
      histogram h (`STAGE_FREED_NOTHING` with `value == h`, the patterns
      `PARAMETRIC_TARGET_UNSEEN` lists) sit beside it, and the FIT ones
      (`SCALE_B_INSEPARABLE`, `PARAMETRIC_OUT_OF_RANGE`,
      `PARAMETRIC_FORM_REJECTED`) appear once. Decide whether a row with
      `equations` quotes `parametric_value()` beside it.
- [ ] The `multi.py` census: list each member that re-derives something
      `Refinement` derives, `_ticks` first, compare it with the single path,
      and fold it or record why it stays, as `DIAGNOSTIC_SCOPES` does. Say
      whether a joint `parameters()` is owed. Include the declared-peak and
      parameter-space screens the joint path skips (Context item 7).
- [ ] Decide a joint observations-per-parameter for `DATA_SUPPORT_LOW`, or write
      why there is none in that scope reason (Context item 8). Re-point the four
      comments naming WP-1341 as owner (`multi.py:237`, `:411`, `:1920`, `:1923`)
      to this WP or to the decision taken.
- [x] Tests in `tests/test_joint_report.py`, each landed with its feature.
      `tests/test_multi_diagnostics.py` is untouched: its scope-table tests
      pass unchanged, and the new code's scope row is held by them.
- [x] Skill: `surprises.md` 8.30 (1341's row) says what the joint report now
      shows, and the new code has its `diagnostics.md` row. `watching.md`
      9d.10 is unchanged: it says nothing the PR contradicts.

## Acceptance

On a joint fit with a per-histogram structural override, each specimen guard
fires on the histogram that holds the bad value. A coefficient-driven cell
escape is named. A hold made in some patterns is named with its count. The
joint support decision is written beside its measurements.
`for_histogram(h)` carries `tick_hkl` and `phase_agreement`, and `report(h)`
shows the findings that name histogram h.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_joint_report.py tests/test_multi_diagnostics.py tests/test_multi_histogram.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- #1124: taken by @mustachefeeling, with the plan this WP's handover follows.
- Issues #252 and #803 (closed by WP-1341), #481 (WP-1523's blank frame).
- WP-1341 (the joint report), WP-1325 (parametric series, per-pattern holds),
  WP-1344 (`DIAGNOSTIC_SCOPES`), WP-1414 (`STAGE_FREED_NOTHING`), WP-1523 (the
  significance test), WP-1534 (the scale-B probe), WP-1986 (the view gap),
  WP-2001 and WP-2004 (the tier rule).

## Handover log

- **2026-10-23** — created by WP-1341's close, on the maintainer's decision
  that day to close 1341 and forward its open items to one new WP. It holds
  1341's three open questions (WP-1523's test, the `multi.py` census,
  `STAGE_FREED_NOTHING` beside its histogram), the four open items and
  rendering notes 1325 forwarded on 2026-10-14, WP-1986's view gap and the
  `SCALE_B_INSEPARABLE` rendering. No open WP owned them: 1421 owns the fresh
  compile, 1335 the report's cost, 2004 fences joint-fit code out, and 1325
  had forwarded its joint items to 1341. Each line number in Context was
  checked against the `wp-closeouts` tree that day.

- **2026-10-23** — built tasks 1-3, 5 and 6 as planned on #1124 (taken by
  @mustachefeeling); task 4 measured and not wired; 7 and 8 left open with
  their findings below. Each built task has a test in
  `tests/test_joint_report.py` § WP-2028 that fails on `main` `12f459e5` and
  passes here: 10 of the 13 new items fail on `main`, and the other three are
  controls that pass on both. *Done*: (1) `_specimen_once` asks the ADP and
  both Biso guards of every histogram's table and model, one finding per path
  as the joint result spells it. On `main` a negative B set in histogram 1
  alone through `SharingMap(per_histogram=["phases.0.atoms.*.biso"])` fired
  nothing, and one in histogram 0 alone fired under the bare path. Here each
  fires as `hist.<h>.phases.0.atoms.0.biso` in the histogram that holds it; a
  shared negative B is one bare finding, as before. (2)
  `_vars_driven_cell_escapes_multi`, the joint twin of
  `refine._vars_driven_cell_escapes`, feeds the joint `CELL_RUNAWAY`: a
  parametric cell walked 30 % along `vars.a_0` is named with `vars.a_0` and
  both histograms' `hist.<h>.phases.0.cell.a`, "not put back". On `main` no
  `CELL_RUNAWAY` fired. (3) `PHASE_HELD_IN_PATTERNS` (info, tier 1): one
  finding per phase whose `hist.<h>.` structure the answer's support hold
  kept, `value` the pattern count, read off `StageResult.held`; parametric
  targets, the ridge and moment holds left to their own codes. (5)
  `for_histogram` copies `tick_hkl` and `phase_agreement`, and the joint top
  level passes histogram 0's `tick_hkl`. (6) `for_histogram(h).diagnostics`
  adds the top-level findings whose `where` names a `hist.<h>.` row,
  `STAGE_FREED_NOTHING` with `value == h`, and once each the fit-wide
  `SCALE_B_INSEPARABLE`, `PARAMETRIC_OUT_OF_RANGE`, `PARAMETRIC_FORM_REJECTED`
  and `STAGE_PATH_UNKNOWN` (`schemas.results.FINDINGS_IN_EVERY_VIEW`).
  `FitReport` carries no diagnostics on either path, so the view `report(h)`
  reads is where they sit. Whether a row with `equations` quotes
  `parametric_value()` beside it is not decided here. *Measured, task 4*
  (`.venv` `[dev]`, macOS arm64, readings at each fit's answer; screen /
  WP-1523's z on histogram h alone / WP-1523's z on the joint covariance's
  marginal): the LaB6 pair 1026.8 / 1024.7 / 1024.7 and 867.5 / 866.0 / 866.0;
  #481's seen frame 0 beside the blank seed-107 frame, per-histogram phase,
  blank histogram 3.73 / 1.60 / 1.60, so the screen refines the blank
  pattern's own cell where either WP-1523 reading would hold it; two blank
  frames (7 and seed 107) sharing a cell, 2.60 / 1.33 / 1.33 and 3.71 / 1.58 /
  1.58, so the joint fit refines the shared cell against noise with no
  `PHASE_UNCONSTRAINED` (max screen 3.71), where quadrature of the singles
  reads 2.06 and the max joint marginal 1.58, both unseen. The ZrMo₂O₈ ramp
  is not held on the Mac that measured this and was not fetched, so what
  moves in `PARAMETRIC_FORM_REJECTED`'s pattern set is not measured.
  *Open*: task 4's choice, task 7's census (listed in the PR; `_ticks` lacks
  the single path's magnetic tick row, issue #278, and was not folded since
  that moves a joint result's ticks), task 8.

- **2026-10-24** — review round 1 on #1128 (items 1-6): a phase held in every
  pattern is left to `PHASE_UNCONSTRAINED`; the ridge exclusion reuses
  `refine._DISPLACEMENT_PATH` (so `adp.k` columns count); an ADP site is
  scoped by the columns that move it (`adp.k` and `u11`..`u23`), and
  `_parameters` reads a tied row's shared-ness off its tie sources
  (`_row_shared`); `OCCUPANCY_ABOVE_ONE` is asked of every histogram
  (`_occupancy_once`); the Upgrading sentence names the `hist.<h>.` path
  change; the audit row's ambiguity is 1 with the `phase_support_sigma`
  evidence. Item 7 (rebase onto #1103, and who names the patterns where only a
  scale was held) waits for #1103 to merge. Follow-ups left: shared helpers
  for `_merge_unresolved` and `_specimen_path`, a test crossing
  `FINDINGS_IN_EVERY_VIEW` with `DIAGNOSTIC_HELP`, and the Lindemann bound's
  histogram.

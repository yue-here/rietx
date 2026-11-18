# WP-1512 — A simulated diffuse curve rides on the phase scale, through the fixed-background slot and a tie

Milestone: unscheduled · Status: ✅ 2026-11-18 — option A (Yue): no component; the fixed-background slot plus a tie to the phase scale, documented and pinned at the joint minimum, in PR #1678
Track: Data and metadata in, a structure out
Depends on: —

## Goal

A curve on 2θ computed by another program (a stacking-fault diffuse term
from DIFFaX, a Debye sum, an amorphous reference) enters a fit as a member
of `Instrument.extra_components`, with its own amplitude, its source and its
σ. A tie holds that amplitude to a phase scale, so "the diffuse term is
locked to the Bragg scale" is one declared constraint instead of a loop of
refits.

## Context

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. The agent modelled stacking faults in DIFFaX and fitted
`y = Chebyshev + S·Bragg + S·c*·D(2θ)`: D the faulted minus the ideal DIFFaX
pattern, c* a unit conversion it calibrated with `Refinement.predict()` at
scale 1, S the phase scale. The lock mattered. A free diffuse amplitude is
degenerate with the background and the Bisos, so only a locked one tests
whether the diffuse term helps. It found no seam for this and built one:

- S·c*·D went in as the fixed curve of `BackgroundFixedPlusChebyshev`, with
  `fixed_source` unset.
- An outer loop refit up to four times, rebuilding the curve from the new
  phase scale until S moved by less than 1 %.
- c* was calibrated once, over a narrower 2θ window than the final fit
  used.
- The curve was interpolated onto the data at 2θ minus the fitted zero
  shift, by hand.

**The workaround breaks silently now.** In 1.4.0 the fixed curve had no
scale. WP-1309 (1.5.0) added `instrument.background.scale`, and every preset
frees `instrument.background.*`. Checked on `c1bd21dd` with a minimal
script: a stage turning on `phases.0.scale` and `instrument.background.*`
frees `c0`–`c3` *and* `scale`. So the run's script, rerun today, lets the
diffuse amplitude float free of the phase scale, and nothing says so. WP-1309
recorded that break for a *measured* blank, with `instrument.background.c*`
as the escape. A simulated term is a different object and should never have
been in that slot.

**The seam.** `ExtraComponent` (`src/rietx/schemas/instrument.py:1670`),
the union behind `Instrument.extra_components`, with its six-clause member
contract in the comment above it. It has two members today, a hump and a
sharp peak (WP-1103). This would be the **third**, and root CLAUDE.md's rule
applies: a third member audits every reader of the list before an evaluator
is written (`n_extra_components`, the CIF description, a reopened result,
an analytic branch's declared reach, the absorption statistics, both tick
builders, and `multi.py`'s own copy).

**The lock is already expressible.** `Refinement.tie(path, source, *,
scale, offset)` is affine (`src/rietx/refine.py:1858`), so the member's
amplitude tied to `phases.0.scale` with `scale=c*` is the whole constraint.
The outer loop's fixed point should then come out of one fit.

**Design questions.**

- **Aggregate membership** (contract clause 2). A diffuse term from the
  phase is not instrument background. Decide whether it joins
  `y_background`, a new aggregate, or the phase's own share, and what the
  Le Bail/Pawley partition subtracts (clause 3).
- **Does the curve move with the zero shift?** A curve computed on the
  specimen's 2θ axis does, which puts an interpolation inside the traced
  residual. Check whether `xp` has an `interp` op (`_OP_NAMES`). If not, it
  is a new op on every backend (root CLAUDE.md, the hot-path rule).
- **σ.** A simulated curve has none. A tabulated measured reference does.
  One field, optional, like `fixed_sigma`.
- **Screening.** `background_absorption` anchors its targets at `phases.`
  (`_structural_targets`). Decide whether a tied amplitude is a target.

## Findings (2026-11-18, on `439032dde`)

**The audit (task 1).** Paths under `src/rietx/`. The class behind most hazards is one: **several
readers use the aggregate as a proxy for the shape**, testing `COMPONENT_AGGREGATE == "background"`
and then reading a hump's fields. That is WP-1103's lesson one axis over. A third member landing
in `"background"` breaks each of them, and one landing anywhere new passes the two `compile_model`
filters silently.

Break or mislead for a third member:

- `model/forward.py:4702-4706`: `component_paths` builds a `HUMP_FIELDS` triple for every
  background-aggregate member. `CompiledModel.background` (`:1061-1070`) feeds each triple to
  `hump_curve`, and `optimize/least_squares.py:2371` and `strategy/staged.py:1527-1543`
  (`check_hump_width`) unpack it.
- `model/forward.py:4052-4053` (`_compile_extra_peaks`): reads `eta`, `fwhm`, `center` of every
  ticks-aggregate member.
- `indexing/extinction.py:997-1010`: reads `.position` and `.fwhm` of every background-aggregate
  member.
- `refine.py:9715-9717`: `n_extra_components = len(component_paths) + len(peak_components)`,
  so a member in neither tuple is not counted. `n_background_components` is right only for a
  background-aggregate member that joins `component_paths`.
- `io/exporters.py:411-412`: every background-aggregate member is written to the CIF as an
  "explicit Gaussian background peak".
- `io/recipe.py:1653-1664`: names every member's field `background_peak_{i}_{field}`.
- If the curve reads the zero shift: `model/forward.py:2989-2996` withdraws polarisation and line
  weights from the analytic chain when `peak_components` is non-empty, and would need the same
  withdrawal for `instrument.zero_shift`, or that column comes back short (the WP-1070 failure).
  `refine.py:1615-1630` (`_peak_only_instrument_path`) inherits the same gap.

Correct only if the member's aggregate is `"background"` and its curve is inside
`CompiledModel.background()`: the Le Bail and Pawley nets (`model/forward.py:3314, 3473`) and
`solve/cost.py:333-345`, which subtract only `extra_peak_curve` explicitly; `evaluate`,
`evaluate_with_background`, `evaluate_parts` (`model/forward.py:2368, 2388, 2410`);
`optimize/statistics.py:773-776` (`background_absorption`) and `:1033-1036`
(`_roughness_nuisance`), which treat every non-peak component path as background;
`report/background.py:137`; `gui/background.py:120`, which reads `component_paths`.

Member-blind and correct: `params/vector.py:349, 2673, 5109` (through `COMPONENT_FIELDS`, which
raises `KeyError` on a missing row); `capabilities.py:462-476`; `model/forward.py:2975` (an amplitude
takes the whole-model FD column, correct and slow); `optimize/least_squares.py:196, 2153-2166`;
`refine.py:7420`; `io/recipe.py:1400, 1424, 1466`; `io/instrument_profile.py:152, 1236, 1865`;
`io/projects/topas_input.py:658` and `io/projects/fullprof.py:4059` (refuse any non-empty list);
`strategy/staged.py:299` (the `mccusker_structural` glob would free an untied amplitude);
`indexing/extinction.py:974-978`. `multi.py` keeps **no** second builder: it compiles each
histogram through `compile_model` and reads `model.background` (`multi.py:2498`),
`peak_component_prefixes` (`:2532, 2552`), `_tick_rows` (`:2635`) and `_extra_peak_diagnostics`
(`:2637`), and `params/multi.py:180` makes every `instrument.*` path per histogram. Outside
`src/`: `gui/src/lib/history.ts:381-386` needs a print-format row for any new field (the GUI
track's file, so owed rather than edited here).

**The lock works today, and so does the silent break's repair.** Probe
`~/.cache/ghostshift/rietx/wp-1512/probe/lock_today.py`: synthetic LaB6, Cu Kα1, 15-110° at
0.02°, Poisson noise, a five-Lorentzian diffuse shape on a 0.1° grid at 150 counts peak.
`ref.tie("instrument.background.scale", "phases.0.scale")` with the curve stored as c*·D holds
the amplitude to the phase scale in one fit. A preset-style `set_vary(["instrument.background.*"])`
then frees `c0`-`c3` and **not** the scale, whose row reads `tied: = 1·phases.0.scale`. So the
break the Priority line names is closed by one call with no new code.

**The acceptance's premise is wrong.** One fit with the tie does not reach the outer loop's fixed
point, and it should not. The loop holds the curve fixed while it refits S, so its fixed point
makes χ² stationary with respect to the Bragg term alone. The joint fit makes χ² stationary
with respect to S everywhere S appears, which is the least-squares answer. Measured: the loop
converged in 7 refits to S = 3.03735e-4 at Rwp 0.062786; the one tied fit landed 0.50 % lower, at
S = 3.02224e-4, with the lower Rwp 0.062781 (truth 3e-4, one noise draw). The lock test should pin
the joint minimum instead, and the loop's offset is a number to report, not a bar.

**What ignoring the zero shift costs.** Probe `zero_and_glob.py`: truth zero shift 0.05°, applied
to the Bragg peaks by the model and to the curve by hand. Fitted with the curve frozen at
compile against the curve shifted, zero shift free in both:

| diffuse feature width (HWHM) | ΔS/S, frozen vs following | GoF, following → frozen |
|---|---|---|
| 2.5° | −9.0e-5 | 1.020 → 1.020 |
| 0.5° | −8.9e-4 | 1.021 → 1.028 |
| 0.15° | −1.6e-3 | 1.021 → 1.044 |

A DIFFaX faulted-minus-ideal curve has features as narrow as the Bragg peaks it broadens, so the
last row is the realistic one. GSAS-II's fixed curve applies no shift because it is a measured
histogram that already carries the instrument's zero offset. A simulated curve does not.

**Practice** is in `docs/practice.md` § A curve computed by another program: GSAS-II and FullProf
add a file curve to the background with one multiplier; FullProf also refines a shift and a
stretch; TOPAS lets the user write the shift, the amplitude and where the curve lands.

## Non-goals

- Computing any diffuse term (WP-1516 scopes it).
- The measured-blank background's semantics (WP-1309).

## Tasks

- [x] Audit every reader of `extra_components` and list them here, before
      writing the member. (§ Findings, 2026-11-18.)
- [x] Decide the four design questions above, in this file. **Option A**, Yue's ruling of
      2026-11-18: no new component. The curve, stored as c*·D, goes in
      `BackgroundFixedPlusChebyshev`'s fixed curve, and
      `ref.tie("instrument.background.scale", "phases.0.scale")` holds its amplitude to the phase
      scale. Yue chose A "for now, as the easiest". What would flip it to C (the member, with the
      curve following the zero shift): a second case needing a blank and a simulated curve
      together, or a sharp curve on a pattern with a large zero shift. So the four questions
      close as follows. Aggregate: the background, since the curve is in the background slot.
      Zero shift: the curve does not follow it (0.16 % on S at 0.05° with 0.15°-wide features,
      § Findings), and the manual says so. σ: `fixed_sigma`, already there. Screening: no change
      (handover 2026-11-18, settled point 3).
- [x] ~~The member: schema, `SCHEMA_VERSION` bump, evaluator in `xp` ops,
      refinable fields through the one registration helper, cross-backend
      `CONFIGS` row, manual equation with its `*Source:*` line, `help.py`.~~
      **Declined** under option A: no member is built, so none of its rows is owed, and
      `gui/src/lib/history.ts` needs no new print format either.
- [x] A test pinning the lock, restated (handover 2026-11-18, settled point 1): a synthetic
      Bragg-plus-diffuse pattern where one fit with the tie reaches the **joint** least-squares
      minimum to 1e-6, and a preset glob over `instrument.background.*` leaves the tied scale
      alone. `tests/test_simulated_curve_tie.py`.
- [x] Skill: a reference row saying a simulated curve goes in the fixed slot, with the tie.
      Under option A the row points at the slot instead of away from it. Plus the
      `help.py` entry for `instrument.background.scale` and a section of the manual's blank
      guide.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_simulated_curve_tie.py tests/test_manual_api.py tests/test_help.py tests/test_skill.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The lock test above passes. Restated under option A: the cross-backend and
extra-component rows the member would have needed are gone with the member, and
`solution case 1`'s rebuild on the member is replaced by the synthetic joint-minimum
test, since no member exists to rebuild it on.

## References

- Treacy, M. M. J., Newsam, J. M. & Deem, M. W. (1991). *Proc. R. Soc. Lond.
  A* 433, 499–520. The DIFFaX recursion whose output the run fed in.

## Handover log

- **2026-11-18 (2nd session)** (ghostshift runner, PR #1678) — closed as option A.

  A user who brings a stacking-fault curve from DIFFaX now has a documented route, and it needs
  no new code. The curve goes in the fixed-background slot, multiplied by the factor that puts it
  in counts at phase scale 1, and one call ties its scale to the phase scale. One fit then lands
  at the true least-squares answer, which the old loop of refits missed by 0.09 % to 0.5 % of the
  scale. The route's known cost is that the curve stays put on the 2θ axis while the zero shift
  and the other position corrections move the Bragg peaks; the manual says so, with the measured
  bias and a remedy. Yue ruled option A on 2026-11-18, "for now, as the easiest", and plans an
  in-house stacking-fault code later.

  **The ruling.** Option A: no new component. What would flip it to C (a member whose curve
  follows the zero shift): a second case needing a blank and a simulated curve together, or a
  sharp curve on a pattern with a large zero shift. The previous entry's "Settled here" points
  stand, the restated acceptance first. Yue's plan for an in-house stacking-fault code went to
  WP-1516's `### Inherited`, beside the note that its `Depends on: 1512` premise changed.

  **Done.**
  - `tests/test_simulated_curve_tie.py`: synthetic LaB6 with a five-feature diffuse curve stored as
    c*·D. One tied fit is compared with the joint minimum and the outer loop's fixed point, both
    solved in closed form from the model's own linear columns (`Refinement.predict`). A second
    test pins that a glob over `instrument.background.*` frees the Chebyshev terms and leaves the
    tied scale alone. Plots go to `tests/output/simulated_curve_tie*.png`; looked at, GoF 1.03,
    the diffuse humps under the five lines fitted.
  - `src/rietx/help.py`, `instrument.background.scale`: a DIFFaX faulted-minus-ideal curve is stored
    as c*·D and its scale tied; the stored curve follows no peak-position correction. `typical`
    names the tied case.
  - `docs/docs/guides/blank.md` § Hold a curve another program computed: the route as an executed
    block, c* as a least-squares ratio against `predict` with a flatness check, a separate
    fraction keeping a free scale, a series re-declaring the tie in `constrain=`, and the position
    corrections' cost and remedy.
  - Skill row 8.29 (`references/surprises.md`): one sentence for the faulted-minus-ideal curve. Paid
    for by cutting two clauses the help entry carries (`HIGH_CORRELATION` against c0 expected; a
    blank never on the specimen's scale) and the file's "Each one cost a debugging pass."
    34 588 → 34 596 B against a 34 600 B budget.
  - Task 3 (the member) declined. The acceptance is restated in this file around the joint
    minimum.

  **Measured** (darwin/arm64, `[dev]`, this worktree's venv). The tied fit's S sits 5.7e-11 from the
  joint minimum; the loop's fixed point 8.7e-4 from it, 0.17 of S's esd (1.56e-6 on 3.02e-4). The
  bar is 1e-6, so 17 000× margin on one side and 870× on the other. The first version of the test
  used `closing_window_tol=None`, and the gap was then 4e-4: the fit's own model cut peak tails
  the oracle's fresh compile kept. A default closing stage measures the answer at the windows
  `predict(grid)` compiles at. Fast suite: 14 789 passed, 432 skipped, 32 xfailed in 9:38 at load average about 21, on `ea62581d5` (darwin/arm64, `[dev]`); the 2 added tests pass, 0.72 s together, so neither joins the tail. The prose and help-text commits after it were covered by rerunning the six files they touch on the final tree, 280 passed..

  **Code review** (`/code-review high --fix`). Applied: the remedy covers every position
  correction, not the zero shift alone; c* is calibrated with the background at zero; a series
  re-declares the tie; the loop oracle raises if it does not converge. Declined: restoring the
  cut clauses of row 8.29 (the help entry carries them and the file is at its budget); moving c*
  into `tie(..., scale=c*)` (the ruling stores c*·D); the WP-1516 note's "closed" before this
  status flipped (resolved by this entry).

  **Generality** (generality-review agent, pasted unedited):

  #### 1. Skill row 8.29 (`docs/skill/rietx/references/surprises.md`): a computed curve goes in the fixed-background slot, tied to phase 0's scale

  **holds.** The case for the tie is stronger. It closes a silent break and is pinned by a test. The case against is real only for a curve whose amount is not the phase's own.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | Store the curve as c*·D and call `tie("instrument.background.scale", "phases.0.scale")` (diff, row 8.29). Here D is the other program's curve and c* converts its units to counts at phase scale 1. | The package acts on nothing. The row steers an agent to three choices: the slot (`BackgroundFixedPlusChebyshev`'s fixed curve), a locked amplitude rather than a free multiplier, and a coefficient of 1. | clear |
  | 2. Kind of ambiguity | none given (no audit row) | The kind depends on what D is. For a faulted-minus-ideal DIFFaX curve (DIFFaX is a stacking-fault simulator) it is kind 1, by arithmetic: the faulted pattern is S·c*·(ideal + D), with S the phase scale. For a curve whose amount is independent of the phase, such as an amorphous reference or a separate disordered fraction, it is kind 3: whether it scales with the phase is a fact outside the pattern. The row says "for phase 0" and does not state that condition. | weak on scope |
  | 3. Case against | none given | `docs/practice.md` lines 1336-1347 and 1360 say GSAS-II and FullProf put a file curve in the background with **one free multiplier** by default, and no surveyed program ties it to a phase scale. A refiner who treats the curve's amount as unknown frees the multiplier: an amorphous fraction, or a fault probability they do not trust. The WP's Context says a free amplitude is "degenerate with the background and the Bisos". No measurement backs that sentence. | real, narrow |
  | 4. Case for | Since 1.5.0 every preset frees `instrument.background.scale`, so the amplitude "floats free of the phase scale, and nothing says so" (WP Context). The loop of refits lands off the joint least-squares minimum, 0.50 % in S (§ Findings). | Confirmed by the test file. The tied fit sits 5.7e-11 from the closed-form joint minimum. The loop's point is 8.7e-4 away, 0.17 of S's esd (`tests/test_simulated_curve_tie.py`). The tie costs one call and one fit; the loop took 4-7 refits. | strong |
  | 5. Tier | none given | The coefficient 1, given c* calibrated at S = 1, is arithmetic (tier 1). Locking rather than freeing the amplitude has no tier-2 support: GSAS-II and FullProf dissent by default (per practice.md, which cites GSAS-II source and the FullProf manual; I did not check the programs). TOPAS lets the user write the tie. The package decides nothing, so the choice stays the caller's. Tests: `test_one_tied_fit_reaches_the_joint_minimum_and_not_the_loops_fixed_point` and `test_a_preset_glob_frees_the_terms_and_not_the_tied_scale`, both in `tests/test_simulated_curve_tie.py`. | tier 1 coefficient, caller's choice |
  | 6. Dataset families | "(Measured: WP-1512)" | One family: synthetic LaB6 at Cu Kα1, built by the test itself. It is development data. The reference is the known truth plus a closed-form linear solve, so it verifies and validates nothing. The real run that motivated the WP ("solution case 1", an agent run in the private corpus) was not rebuilt (WP § Acceptance). | adequate for a mechanics claim |
  | 7. Record that it fired | none given | The `tie` field of `ParameterRow` reads `= 1·phases.0.scale`, and `fixed_source` holds the caller's note. | clear |

  Evidence that would change the verdict: an agent routing an amorphous or separate-fraction curve through "for phase 0" and tying an amplitude that should be free.

  One thing outside the named items: the same edit deletes the row's sentence "`HIGH_CORRELATION` against `c0` there is the correct report" (HIGH_CORRELATION is a diagnostic code). The `help.py` entry still tells the reader to expect that code.

  #### 2. `help.py` entry for `instrument.background.scale`

  **holds.** The case for is stronger, as in item 1. The entry also states the frozen-axis limit as a report and stops, which is the right answer for a kind-3 consequence. One example in it is weak.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | A curve another program computed for one phase "scales with that phase". Store it as c*·D and tie this scale with `Refinement.tie`. "The stored curve does not follow the zero shift or any other peak-position correction" (diff, `help.py` ~759). The `typical` field gains "the phase scale, tied, for a computed curve". | Advice only. The axis sentence covers every position correction, capillary offsets included. | clear |
  | 2. Kind of ambiguity | none given | Same as item 1. "Scales with that phase" is stated as fact. That holds for faulted-minus-ideal. It is contestable for "a Debye sum", which often models a separate nanocrystalline or disordered fraction whose amount is independent of the Bragg phase. | weak clause |
  | 3. Case against | none given | Same dissent as item 1 (free multiplier by default in GSAS-II and FullProf). The Debye-sum example widens the advice into the cases where that dissent applies. | narrow |
  | 4. Case for | as item 1 | as item 1 | strong |
  | 5. Tier | none given | As item 1. The axis sentence is a report (kind 3, report and stop), which is correct. | as item 1 |
  | 6. Dataset families | none given | As item 1: one synthetic family. | as item 1 |
  | 7. Record that it fired | none given | `ParameterRow.tie`. No diagnostic says the curve stayed fixed on the axis. | partial |

  Evidence that would change the verdict: a source showing that a Debye-sum curve used beside a Bragg phase is normally that phase's own correction rather than an independent fraction. Failing that, drop or qualify the example.

  #### 3. Manual blank guide, § Hold a curve another program computed (`docs/docs/guides/blank.md`)

  **weak.** The route and the series sentence hold. The c* recipe and the zero-shift remedy rest on no measurement of their own, and the probe scripts behind the quoted biases are missing.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | Find c* by comparing the other program's ideal pattern with `Refinement.predict` at phase scale 1 "over the whole fitted range", with every background coefficient at zero. In a series, re-declare the tie in `constrain=` (the per-pattern hook). If the fit finds a peak shift Δ(2θ), store the curve at `two_theta + Δ(two_theta)` and fit again (diff, blank.md lines 18-19, 50-58). | Three suggestions the caller did not ask for: an estimator for c*, a calibration window, and a remedy for the frozen axis. | clear |
  | 2. Kind of ambiguity | none given | The remedy is kind 1. Geometry says a curve on the specimen's axis moves with the peaks, and FullProf (shift b₄) and TOPAS (`fo_transform_X`) both offer this (practice.md 1344-1354). The c* recipe is kind 1 only if the ratio between the two programs' ideal patterns is flat in 2θ. Nothing checks that. | partly unstated |
  | 3. Case against | none given | (a) "Compare" names no estimator: ratio of sums, a least-squares ratio, or one strong line. (b) The two programs' Lorentz-polarisation, monochromator, Debye-Waller and absorption terms can differ, so the ratio can drift with angle. That is my reasoning and is not measured. The guide gives no check for a non-flat ratio. (c) The source run calibrated c* over a narrower window (WP Context). The guide's "whole range" carries no measured difference. (d) The remedy was measured with the shift applied to the curve by hand (§ Findings), not with a fitted Δ followed by a refit. (e) The guide names only the zero shift and the flat-plate corrections. The capillary offsets (`instrument.geometry.capillary_offset_along_beam` and `_across_beam`) also move peaks. The help entry covers them; the guide does not. (f) No function is named that returns Δ(2θ) from fitted values, so the caller writes the formulas and signs. The zero-shift sign the guide implies matches `help.py`'s "added to every calculated 2θ". | substantive |
  | 4. Case for | The frozen curve costs 0.16 % in S and GoF 1.02 → 1.04 at a 0.05° zero shift with 0.15°-wide features, and 0.009 % at 2.5° (blank.md 55-56; § Findings table). | The numbers match § Findings. From the test, S's esd is about 0.5 %, so 0.16 % is roughly 0.3 esd. The guide does not give that comparison. The remedy costs one extra fit. The series sentence agrees with root CLAUDE.md (WP-1441: ties are re-declared per pattern through `constrain=` and never carried). | moderate |
  | 5. Tier | none given | Remedy: tier 1 (geometry), with FullProf and TOPAS as practice (from practice.md; not checked by me). c* estimator and window: no source, so rietx's own. No test covers the c* recipe or the remedy. The joint-minimum claim and the glob claim are pinned (item 1). | remedy tier 1; c* none given |
  | 6. Dataset families | none given | One synthetic family and one noise draw for the zero-shift table. It is development data. Its reference is a fit with the curve shifted by hand, so it is relative and validates nothing. The probe scripts § Findings cites (`~/.cache/ghostshift/rietx/wp-1512/probe/lock_today.py` and `zero_and_glob.py`) are **not on disk**: that directory does not exist. Only `/Users/yue/.cache/ghostshift/rietx/wp-1512/probe1.py` survives, and it reproduces the lock test, not the zero-shift table. | one family, unreproducible table |
  | 7. Record that it fired | none given | Nothing reports that the curve stayed fixed on the axis. `fixed_source` is free text the caller writes; the example puts c* there. | none |

  Evidence that would change the verdict: the zero-shift probe restored and rerun with a fitted Δ and a refit, a check that the c* ratio is flat across 2θ on one real DIFFaX/rietx pair, and the capillary offsets added to the guide's list.

  The author's answer to item 3's "weak": the scope, c* estimator and capillary clauses were
  fixed in `83aea6e0c`. The zero-shift table and the remedy stay development data on one
  synthetic family, as the agent says.

  **Gotchas.** The first session's probes (`probe/lock_today.py`, `probe/zero_and_glob.py`) are
  gone from the scratch directory, so § Findings' zero-shift table cannot be rerun from disk. Its
  numbers are quoted as that session measured them. The fast suite ran while two commits of
  prose and help text landed; the files those touch were rerun after (counts above).

  Next: none in this WP. Reopen as option C on either trigger above. WP-1516 carries the in-house
  code.
- **2026-11-18** (ghostshift runner, draft PR #1678) — audit, practice survey and three probes
  landed; no code. **Stopped for a decision of Yue's** before writing the member.

  **The decision.** Whether WP-1512 builds a new component at all, or closes as documentation of
  a tie in the slot that exists today. Three triggers send it: the member would be a new
  top-level name beside `rx.HumpComponent` and `rx.PeakComponent`, where the field has no
  standard term (TOPAS `user_y`, GSAS-II "fixed background file", FullProf "background file");
  it is a stored-format change (a `SCHEMA_VERSION` bump, contract clause 5); and a measurement
  contradicts the WP's acceptance.

  **Why it matters.** The WP was filed because a run that put a simulated stacking-fault curve
  in the fixed-background slot needed an outer loop of refits to keep the curve's amplitude in
  step with the phase scale, and since 1.5.0 every preset frees that slot's scale silently. Both
  problems turn out to be solved today by one call,
  `ref.tie("instrument.background.scale", "phases.0.scale")`, with the curve stored as c*·D.
  What the slot cannot do is hold a measured blank and a simulated curve together, report the
  curve as anything but background, or move the curve with the zero shift. Importance:
  moderate. The one observed use is `solution case 1`.

  **Aim.** Correct numbers for a user who brings a curve from DIFFaX or a Debye sum, with the
  smallest surface that gives them.

  **Options.**
  - *A. Document the tie.* A skill row and a manual paragraph. Cost: an hour. Reversible. The
    curve stays frozen on the axis, so with a zero shift of 0.05° and curve features as narrow
    as 0.15° the phase scale reads 0.16 % low and GoF rises from 1.02 to 1.04 (measured,
    § Findings). The user can still shift the curve by hand before the fit.
  - *B. The member as filed, frozen at compile, landing in the background.* Cost: the member,
    fixes at the seven break sites in § Findings, tests, manual, help; about a day. Allows a
    blank and several curves at once and a correct CIF description. Same accuracy as A. Adds a
    name and a format bump.
  - *C. B, with the curve following the zero shift* (and, for full correctness, displacement and
    transparency). Cost: B plus an `interp` op on numpy, jax and torch with its conformance row,
    and the zero-shift withdrawal from the analytic chain. The only option that removes the
    measured bias. FullProf (a refinable shift b₄) and TOPAS (`fo_transform_X`) both offer it.
  - Dropped: a new aggregate beside `"background"` and `"ticks"`, since it touches about ten
    more readers and no program does it except TOPAS's free per-object flag.

  **Practice.** `docs/practice.md` § A curve computed by another program, read this session:
  GSAS-II 5.8.4 source, the FullProf manual, the TOPAS 5 Technical Reference. Settled practice
  is a file curve in the background with one multiplier. None ties the amplitude to a phase
  scale by default; TOPAS lets the user write it.

  **Recommendation.** A lean for A. The crux is whether B's name and format bump buy anything
  A lacks, and on accuracy they buy nothing: A and B both freeze the curve. So the real choice is
  A against C. C is the accurate option, but its bias measured at 0.16 % of the scale for the
  sharpest curve tried, and its cost is a new backend op for a use seen once. A second case
  that needs a blank and a simulated curve together, or a sharp curve on a pattern with a
  large zero shift, would flip it to C.

  **Settled here, for whichever option is chosen.** (1) The acceptance is restated: one tied
  fit must reach the joint least-squares minimum, not the outer loop's fixed point, which is a
  different point (0.50 % apart in S, the joint fit at the lower Rwp; § Findings). Grounds: the
  measurement and least-squares theory; the alternative is to keep the WP's bar, which a correct
  fit fails. (2) σ, if a member is built, is one optional field like `fixed_sigma`. Grounds: that
  precedent. (3) The absorption screen needs no change: a tied amplitude has no column of its
  own, its curve rides on `phases.0.scale`'s column, and an untied one lands in the background
  block (`optimize/statistics.py:773-776`). Grounds: the code read. (4) For B or C the aggregate
  is `"background"`. Grounds: GSAS-II and FullProf, and clause 3 then costs nothing; the
  alternative is TOPAS's per-object flag.

  **Owed outside this WP's files**, if B or C is chosen: `gui/src/lib/history.ts:381-386` needs a
  print-format row for the new field (the GUI track's file, not edited here).

  Next: on Yue's answer, tick task 2 with the chosen option, then the member (B or C) or the
  skill row and manual paragraph (A). Gates run: none, since nothing outside `docs/` changed.
- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510, 1511 and 1513 to 1517. Nothing started.

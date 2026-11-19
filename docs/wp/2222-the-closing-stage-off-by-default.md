# WP-2222 — The closing stage off by default

Milestone: unscheduled · Status: ✅ 2026-11-19 — off by default; a carried Pawley series and lab_calibrate keep it; WP-2225 retunes the GUI preview
Track: A long run is not one fit
Depends on: —

## Goal

A plan runs no closing stage unless its caller asks for one.
`closing_window_tol` defaults to `None` on both plan mirrors. `1e-3`
(`CLOSING_WINDOW_TOL`) stays the documented opt-in for a final answer.

## Context

**The ruling, 2026-11-19.** Users complained about refinement speed. The
maintainer said that codes such as TOPAS are fast, with accuracy their users
consider very sufficient, and then: "turn off by default". This reverses
the default of WP-2002's eighth round (ruled 2026-10-21,
`2002-batch/rulings.md` § Eighth round), which kept the closing stage on at
1e-3 with `closing_window_tol=None` as the speed switch.

**What the closing stage is.** After a plan's declared stages, `run_stages()`
appends one more stage. It frees every glob the plan freed, recompiles at
the answer with peak windows that drop 0.1 % of each peak's area instead of
the declared stages' 2 % (`forward.WINDOW_AREA_TOL`), and solves again.
TOPAS drops about the same 2 % as the declared stages (`docs/practice.md`).

**Measured 2026-11-19** (macOS arm64, `[dev]`, compiled tier on, telemetry
off, three interleaved rounds; `examples/bench_refinement.py`'s case
builders). Wall clock as ranges; "moves" is the largest shift from the
closing answer, plain esd, non-background rows.

| Case | 1.9.0 | no closing | closing 5e-3 | closing 2e-2 | closing 1e-3 (1.10-1.12 default) |
|---|---|---|---|---|---|
| 11-BM NAC | 0.34-0.40 s | 0.43 s, moves 0.16 | 0.51-0.54 s, 0.06 | 0.48-0.50 s, 0.16 | 0.53-0.56 s |
| cpd-1a | 0.99-1.05 s | 0.97-0.98 s, 0.92 | 1.34-1.35 s, 0.34 | 1.08 s, 0.91 | 1.64-1.68 s |
| cpd-2 | 2.21-2.22 s | 2.08-2.11 s, 1.99 | 3.04-3.11 s, 0.14 | 2.87-3.01 s, 2.17 | 3.53-3.55 s |
| trigger (simulated) | 1.75-1.76 s | 1.76-1.77 s, 1.24 | 2.41-2.44 s, 0.21 | 2.03-2.13 s, 1.23 | 3.28-3.38 s |

Three readings. The closing stage adds 7-23 evaluations to fits of 46-270,
but each costs up to ~19× a declared stage's, so it is 43-48 % of stage
time on the lab cases. With it off, today's code runs at 1.9.0's speed (NAC
~0.07 s slower). A closing stage at TOPAS's 2 % gives the same Rwp as none on
cpd-1a and trigger: its effect is the tighter tail, never the recompile.

**Paths that keep their own setting.** `strategy.magnetic._close` sets
`closing_window_tol=CLOSING_WINDOW_TOL` itself (magnetic.py, the winner's
close), so the magnetic solve is unchanged. Magnetic-path decisions are
Mike's (since 2026-11-04). A saved project stores its selected plan whole
(`ProjectDocument.plan`, `model_dump_json`), so a project that saved a plan
under 1.10-1.12 keeps `closing_window_tol: 0.001` until its user changes
it. A project with no saved plan follows the new default.

**Three cases that keep the closing stage, ruled by Yue 2026-11-19.**
Seven tests stayed red under the new default because the default changed what
they measure. Yue took all three of the session's leans ("Yes, finish it
here"):

1. *A Pawley series that carries intensities forward runs the closing
   stage.* With 2 % windows each pattern misassigns a little intensity and
   the next pattern starts from it. On the four-pattern chain Rwp read
   0.0339, 0.0345, 0.0347, 0.0372 carried, 0.0339-0.0345 re-seeded, and
   about 0.034 throughout with the closing stage: the WP-1459 (#440) drift
   back. `SequentialRefinement.fit` sets `CLOSING_WINDOW_TOL` on a plan whose
   value is `None` when `mode="pawley"` and `carry_hkl_intensities` is on;
   `carry_hkl_intensities=False` is the way out. A single Pawley fit has
   nothing to compound and stays off. Le Bail carries the same way and was
   not measured.
2. *`lab_calibrate` runs the closing stage, and the `branch` and `path`
   guides ask for it.* At the default the calibrate guide's sample size and
   strain land 2.9 and 2.4 esd from the simulated truth; with the closing
   stage in the calibration alone, 1.3 and 0.8 esd; in the sample fit too,
   0.3 and 0.4 esd. Every later fit holds the calibration fixed. The two guides teach comparisons of one objective,
   which the declared windows blur (Rwp 0.1031 against 0.0988 where the
   page shows one 0.0947; a 0.02 esd direction gap against 0.005).
3. *The GUI preview keeps 1e-3 windows and the shift is accepted.* A preview
   starting from a default fit moves the curve by up to 0.13 % of the
   strongest peak (26 counts on 20 310, the fluorapatite example) and the
   preview's Rwp in the third digit. Retuning the preview for 2 % windows is
   a follow-up WP.

**Tier.** No new rule. A default moves from one named value to another,
both already audited (`_audit.py`, the `CLOSING_WINDOW_TOL` rows). Ground:
the maintainer's ruling, and TOPAS's 2 % cut as named practice.

## Non-goals

- Windows that follow the parameters (WP-2047, WP-2051, filed for later).
- The magnetic close, which keeps its explicit 1e-3.
- Migrating a saved project's stored `0.001`.

## Tasks

- [x] Flip the default on `PlanSpec` and `RefinementPlan`; the help text, docstrings and field descriptions say what the default is and what 1e-3 buys. `Refinement.run_stage`'s `window_area_tol=None` and a FitReport action applied in the GUI follow, to the declared stages' 2 %; `compile_model`, `predict` and the FitReport misfit keep evaluating at 1e-3
- [x] Tests: those that assumed a closing stage by default declare it, or assert the new default
- [x] The three rulings of § Context: a carried Pawley series runs the closing stage (`SequentialRefinement.fit`); `lab_calibrate` declares it and the `calibrate`, `branch` and `path` guides ask for it; the GUI preview's shift accepted in its tests, WP-2225 filed to retune it
- [x] Audit rows, manual (`reference/refinement.md` speed section), skill rows (`batch-operating.md` 9c.34), staged release notes
- [x] Skill: the opt-in row for a final answer: 9c.34 rewritten as the opt-in, and `series.md`'s runaway row says only an opted-in plan has a closing stage

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_closing_stage.py tests/test_window_domain.py tests/test_staged_start_invariance.py
.venv/bin/python -m ruff check src tests examples
```

## Handover log

- **2026-11-19** — closed. A default fit no longer ends with the closing
  stage, so the cases measured run 1.2-1.9× faster, at answers that move by
  0.16-2.0 esd. That is TOPAS's trade, which Yue ruled sufficient. Three
  places keep the closing stage, each where an error spreads beyond one fit:
  a Pawley series that carries intensities from pattern to pattern, the
  `lab_calibrate` preset whose profile every later fit inherits, and the
  guides that teach numbers to quote. A GUI preview that starts from a
  default fit now shifts by up to 0.13 % of the strongest peak. That is
  accepted, and WP-2225 retunes the preview.

  *Done.* The default flipped on both plan mirrors. `run_stage` and an
  applied FitReport action follow to 2 %, while `compile_model`, `predict`,
  the GUI preview and the FitReport misfit stay at 1e-3. About a hundred
  tests that pinned numbers through the default now declare the closing
  stage. The three rulings (§ Context) are implemented: the carried-Pawley
  condition in `SequentialRefinement.fit`, `lab_calibrate`'s
  `closing_window_tol`, and the `calibrate`, `branch` and `path` guides'
  opt-ins. The calibrate guide's sample fits ask for it too, because the
  preset alone left the sample size 1.3 esd from the truth. Manual, skill
  rows, `PLAN_INFO` and the audit rows say so. The session handed the WP to
  the "Staging strategy and refinement speed" session before the clear and
  took it back on Yue's word.

  *Measured* (macOS arm64, `[dev]`, compiled tier on). The speed table is in
  § Context. The calibrate guide's sample size and strain: 2.9 and 2.4 esd
  from truth with no closing stage, 1.3 and 0.8 with it in the calibration,
  0.3 and 0.4 with it in the sample fit too. WP-2224's re-fit probe on this
  branch, from a warm start converged without the closing stage: one stage
  reaches all 8 standards at 0.36-0.49× the staged re-fit's time and within
  0.02 esd of the first answer. A staged re-fit moved zincite 2.05 esd and
  fluorite 0.83 esd to a slightly lower Rwp (0.1102 → 0.1094,
  0.1817 → 0.1814). So WP-2224's acceptance line, "within 0.5 esd of a
  staged re-fit", would fail on zincite. It should compare with the first
  answer, as its § Measured does. That WP is on PR 1710, not on `main`; its
  session has the finding.

  *Review.* `/code-review high --fix` found five. Three were fixed: the
  calibration's error split, `PLAN_INFO`'s `lab_calibrate` text and the
  calibrate page. Two were declined. An explicit `PlanSpec` `None` is
  overridden in a carried Pawley series, because the dataclass mirror cannot
  tell an explicit `None` from the default and the two must behave alike;
  the way out is `carry_hkl_intensities=False`. A carried Le Bail chain is
  not covered, because the ruling named Pawley and Le Bail is unmeasured;
  WP-2003's `### Inherited` carries the measurement.

  *Gotchas.* A project saved under 1.10-1.12 keeps its stored `0.001` and
  its closing stage. A plan's `None` on `RefinementPlan` cannot be told from
  the default, which is why the Pawley condition overrides it.

  *Generality* (the `generality-review` agent, pasted unedited; its headings set in bold, since a heading in the log must open with a date):

**`rietx.schemas.plan.PlanSpec:closing_window_tol` (default 0.001 → None)**

**Verdict: holds.** The two sides are close, and the case for keeping the closing stage (the extra all-free stage that re-solves on peak windows dropping 0.1 % of each peak's area instead of 2 %) is measured. It was put to the maintainer, who ruled to turn the stage off with the numbers in front of them. The `ambiguity=1` label is contestable, and the row this default now leans on (`WINDOW_AREA_TOL`) still gives grounds that assume the closing stage is on.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides; what the caller must now decide | Field description, `schemas/plan.py`: "null (the default) = no closing stage … 1e-3 … the opt-in for an answer to publish" | A default fit's answer is now computed on the declared stages' 2 % windows (`forward.WINDOW_AREA_TOL`). Before, it was computed on 0.1 % windows. The caller must now decide when a number is worth the closing stage: anything published, quoted or used to seed other fits. | clear |
| 2. Kind of ambiguity | `ambiguity=1` (row) | This is a trade of speed against arithmetic accuracy, and the right answer depends on what the number is for. The data cannot tell a screening fit from a published one. The WP itself names fits where the maintainer wanted the other choice: a carried Pawley series, the calibration, and two guides. So a competent refiner who acts otherwise is named in the change itself. Kind 1 holds only in the narrow sense that the package must pick some window, and TOPAS's is inside practice. | weak |
| 3. Case against acting (against running the closing stage) | Row evidence: "the closing stage cost 1.2-1.3x on 11-BM NAC, 1.7x on CPD cpd-1a and cpd-2 and 1.9x on the bench's simulated trigger case"; "TOPAS cuts each peak at 0.001 of the strongest line's height, 2 % of a Lorentzian … and has no closing run" | `docs/practice.md` § How far a peak is computed and § Staging agree. TOPAS loses 2.0 % of a Lorentzian, MAUD 2.1 %, RIETAN-FP 2.8 % and FullProf 5.3 % at Wdt 6. Of the seven programs, only BGMN has a closing run by default. FullProf (`Ias = 0`) freezes its windows for the whole run, so rietx's frozen-per-stage 2 % window sits inside practice on both counts. The WP table also shows that a closing stage at 2e-2 moves the answer as much as no closing stage does (0.16/0.91/2.17/1.23 esd against 0.16/0.92/1.99/1.24). So the cost buys the tighter tails, not the recompile. The row says this "in Rwp", but the WP's esd column carries it too. | strong |
| 4. Case for acting (keeping it) | Row: "moved those answers 0.16, 0.92, 2.0 and 1.24 plain esd"; field description: "moves lab answers by up to 1-2 esd" | The cost is quantified, but only against the 1e-3 closing answer. That is a numerical reference: it verifies and does not validate. The one independent reference in the row is SRM 660c's certified cell, which is +24.6 ppm with and without the closing stage. cpd-1a and cpd-2 carry weighed compositions, and the stage's largest past mover was cpd-1a's zincite scale (the `WINDOW_AREA_TOL` row), yet no wt% against the weighed value is reported with and without the stage. BGMN restarts all-free by default. The `WINDOW_AREA_TOL` row (tier 3) records that 2 % fails its own accuracy test on all four families (max \|Δy\|/σ 0.71-2.15). It was kept on the grounds that the declared stages "only steer" while the answer comes from the closing stage, and the diff leaves that row's grounds unchanged. | real, partly unvalidated |
| 5. Tier and source | `tier=2`; TOPAS via `docs/practice.md`; `approved="2026-11-19"` | Tier 2 holds as a default inside the seven programs' range. Dissenters (BGMN's closing run, GSAS-II's 0.53 % cut) do not move a default off tier 2. I checked practice.md in this repository. I did not check the programs' manuals myself. practice.md marks TOPAS "checked (manual)". | holds |
| 6. Dataset families and reference | WP § Context table: NAC, cpd-1a, cpd-2, trigger | 11-BM NAC (APS synchrotron), the IUCr CPD round robin (cpd-1a and cpd-2: one source, two mixtures) and one simulated case. That is two real sources at most, all development data. The reference is the closing answer, so these runs verify only. | weak as validation; adequate as a cost measurement |
| 7. Record that it fired | Row: "recorded in RefinementResult.stages as the stage named 'closing'" | With the stage off, the record is its absence, plus the last stage's `StageResult.window_area_tol`, where a recorded `None` means the declared 2 %. No diagnostic code tells a reader the answer came from 2 % windows. | adequate |

Evidence that would change the verdict: cpd-1a/cpd-2 wt% against the weighed composition, with and without the closing stage. If the 2 % answer lands further outside the round-robin spread, the case for keeping the stage becomes a validation case, not a numerical one.

**`rietx.refine.Refinement.run_stage:window_area_tol` (None now resolves to `WINDOW_AREA_TOL`, 2 %)**

**Verdict: weak.** The case against acting (cost parity with a plan's stage) is stronger and follows the ruling. But the row keeps `tier=1` while it now resolves to a tier-3 constant, and it has no approval. At tier 1 the table's check does not require one.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides; what the caller must now decide | Docstring, `refine.py` `run_stage`: "None is forward.WINDOW_AREA_TOL, the declared stages' 2 % … Pass CLOSING_WINDOW_TOL for an answer computed on near-complete tails" | A stage run by hand, including the GUI's "Run this stage" and an applied FitReport action (`report/apply.py`), now fits on 2 % windows. The caller must ask for 1e-3 to get the tighter tails. | clear |
| 2. Kind of ambiguity | `ambiguity=1` (row) | Same trade as item 1: accuracy against speed, decided by the caller's purpose. | weak, as item 1 |
| 3. Case against acting (against 1e-3 here) | Row grounds: "runs on the windows a default fit's stages run on, so it costs what the same stage in a plan costs" | Coherent. With plans off by default, a stage run by hand at 1e-3 would cost more than the same stage inside a plan, and its answer would sit on different windows. | sound |
| 4. Case for acting (keeping 1e-3) | Old grounds, removed by the diff: "No closing stage follows a stage driven by hand … at the declared stages' 2 % that answer carried up to 0.97 esd on lab data" | That premise still holds: nothing follows a hand-run stage. In the GUI, that stage's answer is what the user keeps. The new row does not answer the 0.97 esd figure; it replaces it with parity. The GUI preview stays at 1e-3 (WP Context, ruling 3), so a hand-run stage and its preview now use different windows (follow-up WP-2225). | real, unanswered in the row |
| 5. Tier and source | `tier=1`; evidence: "inherits that row's tier"; `approved` cleared; grounds: "settled by Claude under that ruling, not yet approved for this seat" | **Contradiction.** "That row" is `rietx.model.forward.WINDOW_AREA_TOL`, which is `tier=3` (`_audit.py` line 3080). The seat was tier 1 only because it used to inherit `CLOSING_WINDOW_TOL` (tier 1). Inheriting now gives tier 3, or tier 2 if it cites TOPAS. The `Row` docstring requires `approved` on a tier-3 row, so the stale `tier=1` is what lets this unapproved row pass the table test. | fails |
| 6. Dataset families and reference | none given for this seat | It inherits item 1's measurements and `WINDOW_AREA_TOL`'s four families (SRM 660c, FAP, cpd-1a, NAC), on which that constant fails its accuracy test. | none given |
| 7. Record that it fired | Row: "the stage records the fraction it ran at" | `StageResult.window_area_tol` and the node's `NodeAction.window_area_tol`. `api_call` now omits the keyword at 2 % (`schemas/history.py`), so a replayed line stays faithful. | adequate |

  *Author's answer:* retiered to tier 2 on TOPAS's cut, as the `PlanSpec` row cites; the evidence now answers the 0.97 esd figure. The seat's approval waits on Yue.


Evidence that would change the verdict: the row retiered to inherit `WINDOW_AREA_TOL` (tier 3), or to tier 2 citing TOPAS, and the maintainer's dated approval for this seat.

**`SequentialRefinement.fit`: carried Pawley series forces the closing stage (not seen by the table)**

**Verdict: weak.** The case against is stronger. The only evidence is an Rwp drift on one synthetic chain. The override ignores a caller's explicit `None` and leaves no record on the series result. The repository's own measurement of the cheaper alternative (not carrying the intensities) is not weighed.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | Code comment, `sequential.py` after `resolve_plan`: "A plan's None cannot be told from the default, so the way out is carry_hkl_intensities=False" | For a Pawley series that carries the extracted intensities from one pattern to the next (`carry_hkl_intensities`, on by default), the package adds a closing stage the plan did not ask for. A caller who explicitly passed `closing_window_tol=None` is overridden. To avoid it they must give up carrying, which is a different decision. | clear; an override of an explicit caller value |
| 2. Kind of ambiguity | none given | Kind 1 is claimed implicitly ("ruled"). Item 3's alternatives (closing stage, re-seeding, or accepting the drift) are enumerable, and the data can rank them. | none given |
| 3. Case against acting | none given | (a) The evidence is Rwp alone. DESIGN.md § Rules, 4 bars an Rwp comparison as the evidence for a default or automatic action. No cell or other refined value is reported along the chain. (b) The re-seeded chain at 2 % matched (Rwp 0.0339-0.0345, WP Context). The `carry_hkl_intensities` row (`_audit.py` line 5285) records that carrying "moved no measured value" and costs +30 % evaluations on Pawley (planted chain). The closing stage costs a further 1.2-1.9× (item 1). So the cheaper route to the same Rwp is re-seeding, and that row's evidence (2026-11-03) was measured while the closing stage was on by default, so it no longer describes the default path. (c) Practice: no program of the seven carries intensities by default. GSAS-II's opt-in Copy2Next runs no closing stage. (d) Le Bail carries the same way, is left uncovered, and was not measured. | strong |
| 4. Case for acting | WP Context, ruling 1: "Rwp read 0.0339, 0.0345, 0.0347, 0.0372 carried, 0.0339-0.0345 re-seeded, and about 0.034 throughout with the closing stage: the WP-1459 (#440) drift back" | The mechanism is real: a misassigned intensity seeds the next pattern, so the error compounds with chain length. Pattern 4's Rwp is about 10 % above its re-seeded value. Four patterns is short, and the size on a 60-pattern ramp is unmeasured. Ruled by the maintainer 2026-11-19. | real mechanism, Rwp-only measurement |
| 5. Tier and source | none given (no row) | rietx's own: tier 3, one family, ruled 2026-11-19 in WP § Context. Its natural home is the `carry_hkl_intensities` row's grounds, which the diff does not touch. | none given |
| 6. Dataset families and reference | `tests/test_sequential.py`'s four-pattern chain | One family: `tests/test_pawley.fap_series`, issue #440's synthetic fluorapatite ramp. It is development data and is the WP-1459 regression fixture. It was generated through `compile_model`'s default, which is the 1e-3 windows, so part of the measured drift is the generator's window against the fit's. The reference is Rwp, not a known truth on any refined value, although the synthetic truth exists and was not used. | one synthetic family |
| 7. Record that it fired | Comment: "Every stage it runs is recorded" | Only inside each pattern's history tree (a stage named "closing" and its `StageResult.window_area_tol`). `SeriesEntry` has no stages field, and there is no diagnostic code or `SeriesResult` field saying the package changed the plan. `tests/test_sequential.py::test_a_carried_pawley_chain_runs_the_closing_stage` pins the behaviour. | weak |

Evidence that would change the verdict: the cell, coordinate and Biso errors against `fap_series`' known truth along the chain under three arms (carried with closing, carried without, re-seeded without), plus a longer chain and a Le Bail arm.

**`RefinementPlan.lab_calibrate`: declares `closing_window_tol=CLOSING_WINDOW_TOL` (not seen by the table)**

**Verdict: holds.** The case for acting is stronger. A calibration's error reaches every later fit that holds it, and its cost is paid once per instrument. Its evidence is one simulated pair, though, and the certified standards on disk were not run with and without the stage.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | Docstring, `strategy/staged.py` `lab_calibrate`: "It runs the closing stage … Every later fit holds this result fixed, so its error reaches all of them"; `PLAN_INFO`: "It ends with the closing stage" | When a caller picks this preset, the package adds the closing stage. The caller chose the preset; its contents are the package's choice. | clear |
| 2. Kind of ambiguity | none given | Kind 1 is plausible. A calibration is run once and inherited by everything after it, and I could name no refiner who would refuse tighter tails at 1.2-1.9× the cost of a fit that takes seconds. | holds; not stated |
| 3. Case against acting | none given | TOPAS, FullProf, GSAS-II and MAUD run no closing stage, so a calibration in those programs uses their ordinary cut (practice.md § Staging). This is weak against a once-per-instrument fit. The `CLOSING_WINDOW_TOL` row's stated failure is on SRM 660c LaB6, a calibration standard: 0.908 esd on U from the Gaussian-variance clamp. That row says the clamp "moves U at any window", so it is not a case against the stage. | weak |
| 4. Case for acting | Docstring: "the sample's size and strain land 2.9 and 2.4 esd from the truth with no closing stage anywhere, 1.3 and 0.8 esd with it in the calibration alone, and 0.3 and 0.4 esd with it in the sample fit too" | Measured against a known truth, which is the right kind of reference for a simulation. BGMN ends with a closing run by default. The same numbers show that a default sample fit (`lab_sample_refine`, still off) carries 0.8-1.3 esd of window error even after a closing-stage calibration. | strong on one case |
| 5. Tier and source | none given (no row) | Either tier 2 citing BGMN's default closing run, or tier 3 on one simulated family. The value itself is `CLOSING_WINDOW_TOL`'s tier-1 row. Ruled 2026-11-19 (WP Context, ruling 2). | none given |
| 6. Dataset families and reference | `examples/guides/calibrate.py` | One family: `examples/guides/_calibration_pair.py`, synthetic LaB6 standards and CeO₂ samples on two simulated setups, made with `Refinement.predict` at its default 1e-3 windows. The closing stage therefore matches the generator's arithmetic exactly, which flatters it somewhat. The data are development data. Not reported: the real certified calibrations on disk, NIST SRM 660c (LaB6) and SRM 676a (corundum, `tests/test_acceptance_srm676a.py`, which runs this preset). | one synthetic family |
| 7. Record that it fired | none given | A `StageResult` named "closing" in `RefinementResult.stages`, with `window_area_tol` 0.001, and the `PLAN_INFO` text. No test pins the preset's value directly. It is pinned only indirectly, because `tests/test_examples.py` asserts the calibrate guide's quoted numbers. | adequate; no direct pin |

Evidence that would change the verdict: SRM 660c and SRM 676a calibrations with and without the closing stage, carried into a sample fit. If the instrument profile, zero and displacement do not move beyond their esds there, the action buys nothing on real data.

  Next: none on this WP. WP-2225 (the preview) and WP-2224 (one-stage
  re-fits, after PR 1710 merges) build on it.

- **2026-11-19** — created. No open WP owns the default: WP-2017 measures
  tier-3 thresholds, WP-2047/2051 are closed, and WP-2002 is closed.

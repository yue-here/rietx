# WP-2017 — The second pass: every surviving tier-3 threshold measured on three families

Milestone: generality · Status: 🔄 2026-11-16 — the list and group A landed (PR #1428); group A's hard starts and H in #1494; group G measured in #1577, unreached on real trace phases; group C measured in #1577, four of its seven constants unreachable from a fit; groups D, E and F measured in #1577, D's layouts agreeing to the noise floor, E's angle half over its threshold at ftol 1e-3, F's knot step not inert on a real hump; group I measured in #1577, no old position bound binding on three flat plates; group J measured in #1577, Pawley's line ratio agreeing with Rietveld's and Le Bail's not; group L measured in #1577, no magnetic-solve count changing a conclusion; group M measured in #1577, both starts invariant only behind the closing stage; group N measured in #1577, two hand rows holding and tested, two not; group Q measured in #1577, #1569's held-SNIP bias repeated on its synthetic and in direction on SRM 1976a and FAP; group O measured in #1577, the interval's five constants inside their domain but for the growth's overshoot and the fraction grid's three past the bar on its one graded case; group P measured in #1577, the stale-window warning silent on three runaways whose stale stages were intermediate, the other three window rows holding where their evidence said; group R measured in #1577, the width twin hold binding a specimen width on its floor on four multi-phase families and no real Y reaching the floor it lost; B waits on a named family and K on a harness and a sparse family; questions to the maintainer; 2 groups open
Track: The audits
Depends on: 2002
Priority: P2 2026-10-23 — 2002 closed with the width twin hold; the evidence every tier-3 approval in the single-fit audit was granted on the promise of, now with 2002's two owed domain tests

## Goal

Every tier-3 threshold the single-fit audit kept is measured on three unrelated dataset
families, against an independent measurement where one exists and otherwise a reference
value under its protocol (DESIGN.md § Rules, 2). Each one either holds (its evidence line
gains the families and the distance from each reference value), moves to tier 1 or
`invariant` (a test now bounds it), or goes back to the maintainer as a ruling with the
measurement that failed it.

## Context

**Where this came from.** WP-2002 audited what one fit decides by itself and ruled in two
passes, in the record's order (`docs/milestones/generality.md` § The order): first the
judgement ground for every action, then the mechanical ground, three families, only for
the thresholds of actions that survived. The first pass is done: all sixteen classes
ruled (`docs/wp/2002-batch/rulings.md`, four rounds). The maintainer split this second
pass out on 2026-10-20 so that 2002 could close on its owed tests and B14's lifts.

**What waits on it.** In `src/rietx/_audit.py`, 18 rows name the second pass in their
evidence or grounds and 26 say refits are owed "on either side" (2026-10-20 counts; grep
both phrases for the list). They group by the fits they share (§ The list, 19 groups):

- **The solver path.** Twelve stop constants (Coelho's LM rules `_M_HI`, `_M_LO`,
  `_Q_TRIGGER`, `_Q_WINDOW`, `_LAMBDA_FAIL_*`, `lm._CONVERGED_RUNS`; BCCG's
  `_CONVERGED_*`, `_SMALL_*`; `_CAUCHY_ARMIJO`) and seven solver-path switches (B10's six
  and `DENSE_JACOBIAN_MAX_BYTES`), all approved at tier 3 until refits of three families
  on either side give one answer.
- **`auto_background`'s pick** (`HUMP_TRIGGER`, the two knot steps,
  `AIR_SCATTER_TRIGGER`). Measured on seven crystalline patterns (WP-2002's 2nd session
  of 2026-10-20). The generality judge rated the hump switch weak: its target case, a
  real amorphous hump under Bragg peaks (a glass capillary, an amorphous binder), is
  untested, and the air trigger was never checked against qarr's weighed compositions.
- **The absent-phase hold** (`PHASE_SUPPORT_SIGMA`). Mike Gaultois's second read of the
  batch (PR #1050, B1.1) named the case to gate the default on: an in-situ minor phase one
  peak width off its database cell, whose scale reads under 3σ and whose held cell keeps
  it there.
- **The cell window** (`CELL_WINDOW_*`, tier 3 since 2026-10-20): count the stages where it
  binds; if none, remove it from single fits (B8's ruling).
- **The position bounds' removal** (2026-10-20). One family, 11-BM NAC, where the bound
  acted as a prior that held. Owed: a flat-plate lab family with zero and displacement
  free over a narrow range.
- **Le Bail and Pawley refining the lines** (2026-10-20). One standard, SRM 660c; Le
  Bail's Kα2/Kα1 sat 1.7σ from Rietveld's. Owed: a second standard and a tabulated
  reference ratio.
- **`MODEL_FAR_FROM_DATA_RWP`** (B12.13). A sparse-count family: a true model's Rwp is
  0.77-0.83 at 0.5-1 counts a channel. Mike's proposal: Rwp against the background-only
  model's, or Rwp/Rexp, with no tuned number.
- **The magnetic solve's** `SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K`, `SOLVE_K_TRIALS` (B12,
  B12.8), and `SCALE_B_SEPARATION_FLOOR`, `_COS_CLAMP`, the two `*_CAP_RANGE_FRACTION`
  factors, `SCHERRER_K`, `BOND_SLACK_ANG` and `STEPS_PER_FWHM_*` (the judge's 2026-10-20
  reading).

**Nd₂Ru₂O₇ is cited by no audit.** The pair (`tests/data/mg090*`: 11-BM X-ray and NCNR
BT-1 neutron, one specimen, a published joint refinement) is evidence for no audit; it is
run once at the milestone's close (`generality.md` § Acceptance). It is development data,
not a sealed family in DESIGN.md § Rules, 2's sense (ruled 2026-10-27).

**Families on disk** (WP-2002 § Context): the four round-robin standards and the qarr
set (weighed compositions), 11-BM NAC and SRM 660c, the FAP suite, the Durham tutorials
under `~/rietx-local-data` (`python -m tests.local_data`), the magnetic fixtures (Cr₂WO₆,
LaMnO₃). A family is a specimen type with its own instrument, not a pattern.

### The list (task 1, 2026-11-05)

Read off `_audit.ROWS` at `541f0daf7`. 37 rows name the pass in their evidence or grounds,
against the 18 + 26 this file counted on 2026-10-20, which overlapped. The rest come from the
entries this WP inherited, folded into the groups below on 2026-11-05. All 33 constants those
entries name still exist.

Each group's families and reference were fixed here before any group ran (task 2). A row
"reaches" a family only if the switched constant is read on that fit, so every arm carries a
control: it must differ from the shipped arm in evaluations or in the switched path taken, or
the arm measured nothing. Bar for a number: 0.1 plain esd over the larger of the two arms' esds
(`tests/test_window_domain._shift`), the bar the earlier domain tests used, on the rows that
are not background coefficients, and the distance from each family's reference beside it.

**The four protocol families** are the fits `tests/test_window_domain._protocol` builds, each a
different laboratory, instrument and material:

| Key | Family | Reference | Grade |
|---|---|---|---|
| `fap` | lab Bragg-Brentano fluorapatite | GSAS's converged `FAP.EXP`, protocol mirrored | verifies |
| `nac` | 11-BM capillary NAC with CaF₂ | the acceptance suite's reference values | verifies |
| `cpd1a` | IUCr CPD round-robin three-phase mixture | weighed fractions | validates |
| `lab6` | NIST DBD SRM 660c LaB₆ | the certificate | validates |

| Group | Rows | Arms | Families | State |
|---|---|---|---|---|
| A. LM stop | `lm._M_HI`, `_M_LO`, `_Q_TRIGGER`, `_Q_WINDOW`, `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`, `_CONVERGED_RUNS`, `_CURVATURE_GATE`, `FTOL`, `SLOW_DESCENT_ESD` | one each side of each value, `FTOL` at 1e-8 and 1e-10 | the four, then the hard starts below | measured 2026-11-05; three rows owe hard starts, seven closed by ruling |
| B. Bounded step | `lm._POLISH_FEASIBLE`, `_POLISH_STATIONARY`, `BVLS_MAX_COLUMNS` | each side | Stephens fits on qarr brucite and corundum and one more; FAP Pawley for the column cut | not run: the third family is unnamed, a question to the maintainer (2026-11-16) |
| C. BCCG | `bccg._CONVERGED_FRACTION`, `_CONVERGED_RUNS`, `_SMALL_FACTOR`, `_SMALL_RUNS`, `_CAUCHY_ARMIJO`, `_PCG_TOL`, `_PCG_BUDGET_PER_VARIABLE` | each side | Pawley on `fap`, `nac` and `cpd1a` | measured 2026-11-16: four read only in an uncalled `bccg.solve`; `_PCG_TOL` at 1e-8 fails silently on FAP; cpd-1a never past the cut |
| D. Blocked solve | `blocked.DENSE_JACOBIAN_MAX_BYTES` | forced each way | the four cannot reach it (single fits); joint fits fixed 2026-11-16: cpd-1a/-1b/-1c, the CuCr₂O₄ ramp's seven cold frames, the synthetic library | measured 2026-11-16: the two layouts agree to 0.005 esd, the noise floor; the size rule never chose blocked (110 MiB at most); a third real joint family owed |
| E. TRF | `least_squares.GTOL`, `XTOL`, `staged.BOUND_HIT_COS_MIN`, `BOUND_HIT_ESD_FRAC` | 1e-8 against 1e-12; the 32-case bound table on a third family | `cpd1a`, corundum Stephens, 11-BM Si SRM 640c | measured 2026-11-16: `GTOL` unreached, `XTOL` on one family; bound cases all fired, the angle half over its threshold at ftol 1e-3 |
| F. Background pick | `auto.HUMP_TRIGGER`, `AIR_SCATTER_TRIGGER`, `_KNOT_STEP_HUMPY_DEG`, `_KNOT_STEP_SMOOTH_DEG` | near the trigger, each way | the Kapton capillary for a real hump, qarr's weighed mixtures for air | measured 2026-11-16: on Si's Kapton hump 8° knots move Biso 3.0 esd from the measured blank; air flips ≤ 0.17 esd |
| G. Absent phase | `plan.PHASE_SUPPORT_SIGMA`, its two defaults | 1σ, 3σ, off | a weighed trace phase (the cpd-1 suite), CuO on the CuCr₂O₄ ramp started one FWHM off, cpd-1a with zircon declared | measured 2026-11-16: unreached on real trace phases, acts on zircon alone; B1.1's case not produced |
| H. Cell window | `vector.CELL_WINDOW_FRACTION`, `_ANGLE_DEG`, `_PAD_A` | count the stages where it binds | every fit of groups A and G | open |
| I. Position bounds | their removal, 2026-10-20 | free over a narrow range | lab flat plate: `fap`, `lab6`, SRM 1976a | measured 2026-11-16: no old bound binds on the three, bounded and free agree to 5e-6 esd; freeing the zero walks the cell 48-1000 ppm, past three esds on three of six |
| J. Refined lines | Le Bail and Pawley Kα2/Kα1 | second standard, tabulated ratio | SRM 660c, SRM 1976a, FAP | measured 2026-11-16: Pawley within 0.34σ of Rietveld on all three; Le Bail 1.9σ and 2.8σ low on FAP and SRM 1976a; no tabulated reference for a fitted doublet weight |
| K. Far from data | `refine.MODEL_FAR_FROM_DATA_RWP` | both directions; Rwp beside background-subtracted Rwp and Rwp/Rexp | WP-2086's reach table; a sparse-count family | not run (2026-11-16): the reach table's harness is not in the tree and the sparse family is unnamed, a question to the maintainer |
| L. Magnetic solve | `magnetic.SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K`, `SOLVE_K_TRIALS` | each side | the rare-feature clause: Ba₂FeSbSe₅, Cr₂WO₆, LaMnO₃ | measured 2026-11-16: no arm changed a conclusion; `SOLVE_MINIMUM_RTOL` unreached; `SOLVE_K_TRIALS` reached on Ba₂FeSbSe₅ only |
| M. Starts | `structure.BISO_SEED`, `instrument.HARMONIC_WEIGHT_SEED` | the two starts with `closing_window_tol=None` | the four; the synthetic neutron corundum | measured 2026-11-16: both starts invariant only behind the closing stage; without it the Biso start moves FAP and LaB₆ 0.12 and 0.20 esd, the harmonic seed 0.26-1.44 on its one synthetic family |
| N. Hand rows | Le Bail and Pawley intensity seed, `refine._FLAT_AXIS_TEST_DIRECTIONS`, `arpls`'s `max_iter` and `tol`, `vector.FLOOR_SEEDS` | a test for each claim of invariance | named by each test | measured 2026-11-16: the intensity seed and the flat-axis pair hold, now tested; arPLS picks unmoved but its stop unconverged on SRM 660c; `FLOOR_SEEDS` sets floor-row esds on cpd-1a |
| O. Domain tests | `interval.PARAMETER_INTERVAL_*` (five), `fraction.FRACTION_PROFILE_FWHM_MIN`, `_N_FWHM`, `_FWHM_MAX_SPAN` | state a domain, then 0.1 σ of a point and 0.1 esd | the two-site Pnma fixtures; `fap`, `cpd1a` | measured 2026-11-16: the interval's five inside their domain but `BRACKET_GROWTH` 3 (0.52 half-widths), `MAX_REFITS` unreached; the fraction grid graded on one synthetic case, past the bar on every arm; cpd-1a's profiles not on the fit's model |
| P. Window numerics | `forward.AXIAL_SIZING_FLOOR`, `REFLECTION_MARGIN_DEG`, `STAGE_WINDOWS_STALE`, `report.NOMINAL_AXIAL_APERTURE` | each side | the four; a second and third family that runs away | measured 2026-11-16: the floor ≤ 0.0095 esd behind the closing stage but for LaB₆'s two minima; a final polish at any margin ≤ 0.057 esd; `STAGE_WINDOWS_STALE` silent on three +3 % runaways, stale only on intermediate stages; the nominal aperture fires only below each family's own |
| Q. Le Bail passes | `refine.LEBAIL_CONVERGED_REL`, `StageSpec:lebail_tol`, `report.schemas.LEBAIL_GAP_CYCLES` | each side | LaB₆ + cBN, `fap`, `cpd1a` | measured 2026-11-16: `LEBAIL_CONVERGED_REL` reached on none; `lebail_tol` moves cpd-1a 0.8 esd either side; the gap not at its fixed point at 5 cycles on FAP and cpd-1a; the held SNIP (#1569) 8.8 esd high on its synthetic |
| R. Width terms | `StageResult.width_twins_held`, `ProfileTCHZ:y` unfloored | the hold, none, the specimen side; Y ≥ 0; LM and TRF | LaB₆ + cBN, cpd-1a, 11-BM NAC, CuCr₂O₄ + CuO; the four; brucite, corundum | measured 2026-11-17: the hold binds a specimen width on its floor in every family, unheld Rwp lower and rows move up to 9.73 esd; no real Y reaches 0; nothing reaches ±180 under LM or TRF |
| S. Tier-2 citations | `SCHERRER_K`, `BOND_SLACK_ANG`, `STEPS_PER_FWHM_*` | read each citation | none: they stay at tier 2 unless a source fails | open |

**Group A's hard starts, fixed 2026-11-05 before running.** The shipped starts never reached
seven of group A's ten constants on most families (handover, 2026-11-05). So those seven
(`_M_HI`, `_Q_TRIGGER`, `_Q_WINDOW`, `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`,
`_CURVATURE_GATE`, `SLOW_DESCENT_ESD`) run their same arms from harder starts: every phase's
cell lengths displaced +1 % and +3 % on the four families, and cpd-1a with zircon declared at
the shipped start. Each arm is read against the shipped constants from the same start, on the
same bar, and also on whether it changes the fit's verdict: reaching the shipped start's answer
within 0.1 plain esd, or not.

**Group A's open rows, 2026-11-05.** `FTOL`, `_CONVERGED_RUNS` and `_M_LO` gave one answer from shipped starts and owe the same nine hard starts, for a failing case. Seven rows closed by the maintainer's ruling of 2026-11-05: they stay at tier 3 on a named synthetic case, and a later group treats a constant its families barely reach the same way (`docs/milestones/generality.md` § The rule).

**Taken off the list.** `INTERMEDIATE_FTOL` and its default were re-ruled cost-only on
2026-11-01, so they owe nothing here. `PAWLEY_SPARSE_DENSITY` chooses which arithmetic forms
JᵀJ, agrees with the dense build to 2e-15 on each side, and was confirmed on 2026-10-28.
`_COS_CLAMP`, `SCALE_B_SEPARATION_FLOOR` and the two `*_CAP_RANGE_FRACTION` factors are tier 1
and have no free factor to measure, so this file's old list named them without cause.

**What each group inherits.**

- **A.** `FTOL` ends two stages of every plan since WP-2045, the last declared one and the
  closing one, so a refit at 1e-8 and 1e-10 moves both. GSAS-II 5.8.4's default stop is 1e-3.
- **B to E.** `GTOL` and `XTOL` have one trial: WP-1109's 1e-8 ran 1.22-1.27× faster on cpd-1a
  and 1.04× slower on cpd-2, and put corundum's strain anisotropy past the Stephens suite's bar.
- **B, 2026-11-16: its third family is not named, so B has not run.** The table's "one more"
  Stephens family is named nowhere: not in this file, its handover log, `2002-batch/rulings.md`
  or the open PRs. `generality.md` § The rule lists Stephens strain as a rare feature, "one family
  on disk or none", and brucite and corundum are one family by that test (the qarr set: one
  laboratory and instrument). Choosing it after seeing B's answer would not be evidence, so it
  goes to the maintainer as a question in the handover log, and C runs next.
- **C, its starts and arms, fixed 2026-11-16 before running** (`2017-batch/group_c.py`). Each
  fit is `fit(data, mode="pawley")` under the default Pawley plan from
  `test_window_domain._protocol`'s data, structure and instrument for `fap`, `nac` (after its Le
  Bail pass, CaF₂ appended) and `cpd1a`. Arms, one each side: `_PCG_TOL` 1e-8 and 1e-12,
  `_PCG_BUDGET_PER_VARIABLE` 1 and 4, `_CAUCHY_ARMIJO` 1e-5 and 1e-3, `_CONVERGED_FRACTION` 1e-5
  and 1e-3 (also `solve`'s `tol` default, bound at `def` time), `_CONVERGED_RUNS` 2 and 5,
  `_SMALL_FACTOR` 100 and 400, `_SMALL_RUNS` 3 and 12; plus the shipped constants and the noise
  arm (every refinable start value that is not zero ×(1 + 1e-12)). Read off the code before
  running: the first three are read in `bccg.projected_cg`, the LM step above
  `lm.BVLS_MAX_COLUMNS`, and the last four only in `bccg.solve`, which no package code has called
  since WP-1953. So every fit counts the calls to each, with a positive arm for the spy (one extra
  `solve` call after the fit must be counted). Bar and reads as group A: 0.1 plain esd against
  the shipped arm, past the noise arm, and `unreached` when rows, Rwp and evaluations match bit
  for bit. References: FAP's GSAS cell, NAC's and CaF₂'s cells; cpd-1a's weighed fractions are
  not a Pawley fit's to read, so it is read against its shipped arm only. No polish: an arm over
  the bar past noise is reported as measured and goes to the maintainer. The three are three
  families by laboratory, instrument and material.
- **D, read 2026-11-16 before choosing its fits.** `DENSE_JACOBIAN_MAX_BYTES` is read only in
  `blocked.choose_layout`, which only `least_squares.run_multi_least_squares` calls: a joint fit.
  The four protocol families are single fits, so neither forced layout can reach them, and the
  families fixed on 2026-11-05 measure nothing. D's families must be joint fits, fixed here before
  it runs. On disk: the synthetic parametric library `tests/test_parametric_series.library` (the one
  case its row cites), cpd-1a, -1b and -1c fitted jointly on one qarr instrument, frames of the
  CuCr₂O₄ ramp, and the Nd₂Ru₂O₇ X-ray and neutron pair, which is evidence for no audit before the
  milestone's close (§ Context).
- **D, its fits and arms, fixed 2026-11-16 before running** (`2017-batch/group_d.py`). Three
  joint fits, each a `MultiHistogramRefinement` through its plan's closing stage under the `lm`
  driver (the only one with a blocked path). `cpd1_joint`: cpd-1a, -1b and -1c together, the QPA
  acceptance protocol's three phases, `qarr_instrument` for each pattern, `seed_scales` per
  pattern, `qpa_plan`, the default sharing (scales and instrument per pattern, the specimen
  shared). `cucr_cold`: the CuCr₂O₄ ramp's seven frames below the published transition near
  130 K (6.8-122.7 K, `OH_00` to `OH_24`), group G's `cucr_models` for each, `mccusker_default`,
  with every cell parameter and Biso per pattern (`SharingMap(per_histogram=...)`), since a
  cell shared across a ramp is not one specimen. `library20`: the synthetic parametric library at
  20 patterns, the row's cited case, as the harness's positive arm (it must repeat the test's
  0.01 esd). Arms: `dense` and `blocked` forced through `blocked.set_layout`, `rule` (the shipped
  size rule, which these three put dense), and `noise` (dense, every free start value that is not
  zero ×(1 + 1e-12)). Control: each fit's `jacobian_layout` must read its arm's layout, or the
  arm measured nothing. Read: every free row of `blocked` against `dense` in plain esd over the
  larger esd (`_shift`, 0.1 bar), past the noise arm, with Rwp, evaluations, status and the
  diagnostic codes; and each fit's dense Jacobian size against the constant. References: the
  weighed fractions for cpd-1, the 10 K Fddd cell for the coldest frame (as group G), the library's
  surface; read beside the bar, not as it. These are two real families (qarr, 11-BM) and one
  synthetic, against the row's three: no third joint family is on disk but Nd₂Ru₂O₇, which is
  evidence for no audit before the milestone closes, so whether two close D goes to the maintainer
  after it runs, not decided here.
- **E, its starts and arms, fixed 2026-11-16 before running** (`2017-batch/group_e.py`). Every
  fit under `solver="trf"`, the only driver that reads the four constants (LM is the default
  since WP-1938). Part 1, `GTOL` and `XTOL`: three fits, each through its closing stage.
  `cpd1a`, cpd-1a under the QPA acceptance protocol (group G's start; reference the weighed
  fractions). `corundum`, the Stephens acceptance fit with the block freed
  (`_with_block(corundum_phase())`, `_plan(texture=False, stephens=True)`, last stage
  `max_iter` 1000 as its test sets; reference the shipped arm, since no anisotropy is the
  answer the test holds). `si640c`, 11-BM Si SRM 640c under `test_acceptance_si640c`'s XND-range
  protocol (2-50°, FCJ, λ free, cell held at the certificate; reference XND's λ as that test
  reads it). Arms: shipped (both 1e-12), `GTOL` 1e-8, `XTOL` 1e-8, both 1e-8 (WP-1109's trial),
  and the noise arm (every free start value that is not zero ×(1 + 1e-12)). Control: a spy on
  `scipy.optimize.least_squares` records the `gtol` and `xtol` each TRF solve received and its
  termination status, so an arm whose solves stopped on another test measured nothing
  (`unreached` when rows, Rwp and evaluations match bit for bit). Read as group A: 0.1 plain
  esd against shipped, past noise; Rwp, evaluations (× shipped), status, codes. Part 2,
  `BOUND_HIT_ESD_FRAC` and `BOUND_HIT_COS_MIN`: issue #273's construction on cpd-1a, the third
  family under TRF (FAP and Si SRM 640c were the first two). From cpd-1a's shipped TRF answer,
  five cases, each one path freed alone for one stage (no closing stage) with its declared bound
  moved 3 of the answer's esds past the optimum and the path started 1 esd inside that bound: fluorite's first atom's Biso with `min` above it, zincite's last atom's Biso
  with `max` below it, fluorite's `lor_size` with `max` below it, zincite's `scale` with `max`
  below it, and `instrument.zero_shift` with `max` below it; each at `ftol` 1e-9, 1e-6, 1e-4 and
  1e-3 (`test_bound_hit_at_convergence.FTOLS`): 20 binding cases. Their control, the same 20 from
  the same start with the bound 3 esds on the optimum's other side (a free optimum, which must stay
  silent). Read off
  `staged.bound_findings`' own inputs per case: gap over esd against `BOUND_HIT_ESD_FRAC`,
  |residual cosine| against `BOUND_HIT_COS_MIN`, and whether `BOUND_HIT`/`FLOOR_HIT` and
  `at_bound` fired; then the margins on this family beside WP-1434's 13× and 236× (distance) and
  145× and 2e5× (angle). A margin under 1× either way is reported as measured and goes to the
  maintainer; no constant moves here.
- **F, its patterns and arms, fixed 2026-11-16 before running** (`2017-batch/group_f.py`). Each
  pattern's instrument background is replaced by `auto_background(data)`'s pick (the default
  P-spline; both scores recorded). Arms: `pick` (the shipped triggers); `knot_flip`
  (`HUMP_TRIGGER` moved just across the pattern's own `amorphous_hump_score`, so the other knot
  step, 3° or 8°, is taken); `air_flip` (`AIR_SCATTER_TRIGGER` moved just across its
  `air_scatter_gain`); `both_flip`; and the noise arm on the pick. Control: each arm's
  `BackgroundChoice` must show the flipped knot step or air term, or the arm measured nothing.
  Families. The Kapton capillary for a real hump: 11-BM Si SRM 640c under
  `test_acceptance_si640c`'s XND-range protocol (its structure, instrument at 2-50°,
  `_plan(asymmetric=True)`, S/L tied to H/L), whose low-angle halo is the empty capillary's (run
  4736); references XND's λ and that suite's measured-blank arm (`_fit_chebyshev(3,
  blank_scale=1.0, free_scale=True)`: the hump as measured, not fitted), read on λ, zero and Biso.
  qarr's weighed mixtures for air: cpd-1a to -1h under the QPA acceptance protocol (its three
  phases, `seed_scales`, `qpa_plan`), reference the weighed fractions. Read as group A: 0.1 plain
  esd against `pick`, past noise, with Rwp, evaluations, status and whether
  `AIR_SCATTER_UNDECLARED` fires; each pattern's two scores beside their triggers. These are two
  families (11-BM; the qarr laboratory), against the table's two; a third is not owed by the row
  text, which names these two.
- **G.** cpd-1a with zircon declared flips with the intermediate tolerance: zircon's scale sits
  near 2σ, nine structural paths held at 1e-6, the cell walking at 1e-9, `lines_axial` at its
  400-evaluation budget (`2002-batch/waiting.md` § B7).
- **G, from group A's hard starts.** LaB₆ with its cell +1 % takes the scale to 0 in the first
  stage and holds the phase: Rwp 0.86, 9 evaluations, `usable=False` through
  `MODEL_FAR_FROM_DATA`. NAC +3 % keeps NAC, loses CaF₂ to a held scale 0, and reads
  `usable=True`, Rwp 0.139, with `PHASE_UNCONSTRAINED` the only word on it.
- **G, its starts and arms, fixed 2026-11-16 before running** (`2017-batch/group_g.py`).
  Arms: `phase_support_sigma` 3 (shipped), 1 and `None`; 3 with the cell window declaring no
  phase (group H's arm); 3 with every start nudged 1e-12 (the noise floor). Starts: cpd-1a,
  -1b and -1c under the QPA acceptance protocol, whose trace phases are weighed at 1.15, 1.36
  and 1.36 wt %; cpd-1a with zircon declared; the CuCr₂O₄ ramp's coldest and hottest frames
  (11-BM, WP-2081's model and `mccusker_default`), CuO at 1.1 wt % in Suchomel et al. (2012).
  Each but the zircon start also runs with its trace or minor phase's cell lengths scaled so
  the phase's strongest line moves one instrument FWHM to low angle, read off the shipped
  answer from the database cell. The ramp's 17 frames run chained with CuO started one FWHM
  off, on the four arms that are not noise, and once from the database cell. The cpd-1 suite
  and cpd-1a with zircon are one family by laboratory, instrument and material, so this set
  is two families, not three; the WP fixed it so on 2026-11-05, and it is run as fixed.
- **I, read 2026-11-16 before choosing its fits.** The removal has no `_audit` row: it is the
  default of four `Parameter`s (`Instrument.zero_shift`, `Geometry.sample_displacement` and the
  two capillary offsets lost ±0.5° and ±1 mm, `sample_transparency` its ceiling of 0.05; commit
  3d63e9db5), and its evidence lives in the schema comment above `sample_displacement` and in
  `docs/docs/reference/instrument.md`. The three flat-plate protocols all hold the zero shift
  (FAP as GSAS, SRM 660c on a calibrated goniometer, SRM 1976a as its TOPAS file does, whose
  comment says not to refine zero and displacement together), so at their shipped plans the
  removed bounds never bind and the fits measure nothing. Group I's arms must free the zero with
  the displacement, as the NAC case freed the zero with both offsets.
- **I, its fits and arms, fixed 2026-11-16 before running** (`2017-batch/group_i.py`). Three
  laboratory flat plates in Bragg-Brentano, three laboratories, instruments and materials: `fap`
  (FAP under its GSAS protocol, 15-130°; reference GSAS's converged cell, a 9.371724(36),
  c 6.885867(37) Å, verifies), `lab6` (SRM 660c under the NIST calibrated protocol, 20.3-150.9°;
  reference the CIF block's cell 4.156780 Å and displacement −0.07877 mm, validates) and `srm1976a`
  (the sintered SRM 1976a plate on an X'Pert under its TOPAS-mirrored textured protocol, 20-118.6°,
  with a cell stage added after the displacement stage, since that protocol holds the cell;
  reference the TOPAS file's cell, 4.758877 and 12.992880 Å, which it holds, and its refined
  displacement −0.08930 mm, read beside the bar). Two ranges each: `full`, the protocol's, and
  `narrow`, from the protocol's low end to the 2θ at which the smallest eigenvalue of the
  unit-column Gram of the three position shapes {1, cos θ, tan θ} (zero, displacement, cell) on
  the pattern's own channels falls to that of NAC's capillary trio {1, sin 2θ, cos 2θ} over its
  2-24°, 1.6e-5, the one case where the bound was measured to matter. Arms: `shipped` (the
  protocol, zero held); `free` (the zero shift turned on in the displacement stage, one block, all
  three refined together with the cell in the closing stage, no bounds: the default since
  1.10.0); `bounded` (`free` with the pre-1.10 defaults: zero ±0.5°, displacement ±1 mm,
  transparency 0-0.05); `noise` (`free`, every free start value that is not zero ×(1 + 1e-12)).
  Control: `bounded` measured something only where a bounded path ends within 1e-6 of its bound
  or `BOUND_HIT` fires; otherwise rows, Rwp and evaluations must match `free` bit for bit and the
  pair reads `unreached`. Positive arm for the harness: 11-BM NAC over 2-24°, the zero and both
  capillary offsets free (`test_capillary_displacement.nac_pair`'s construction), `free` against
  `bounded` (±1 mm, ±0.5°), which must repeat the cited 1097 and about 5111 ppm. Read: every cell
  row `bounded` against `free` and each against `shipped`, in plain esd over the larger esd
  (`_shift`, 0.1 bar), past `noise`; each cell's distance from its reference in ppm and in its own
  esd (the reference page's claim: the cell's esd grows to cover the walk); the zero and
  displacement values and esds; Rwp, evaluations, status, and whether `FLAT_DIRECTION`,
  `HIGH_CORRELATION` and `BOUND_HIT` fire. Whether the removal stands on what this shows is the
  maintainer's; no default moves here.
- **J, its fits and arms, fixed 2026-11-16 before running** (`2017-batch/group_j.py`). What is
  measured: Le Bail and Pawley refining `instrument.source.lines.*.weight` since 84b9e87a2, read
  against Rietveld on the same pattern and protocol. Families: `lab6` (SRM 660c, the NIST
  calibrated protocol, which already frees the Kα2 weight in its `lines_axial` stage; graphite
  diffracted-beam monochromator), `fap` (FAP under its GSAS protocol, whose file leaves the ratio
  blank, so 0.5 is the start) and `srm1976a` (the SRM 1976a plate under its textured TOPAS-mirrored
  protocol, cell held as there; a five-line CuKα in TOPAS against rietx's doublet). The last two
  get one stage, `lines`, after their last structural stage, freeing the Kα2 weight alone. Arms per
  family: `rietveld`, `lebail` and `pawley`, each with the weight free under that one plan (in
  Le Bail and Pawley the atom, scale and texture rows are the mode's own force-fixed ones); each
  mode again with the weight held at the 0.5 start (`held`); and each free arm with every free
  start value that is not zero ×(1 + 1e-12) (`noise`). Control: the free arm's weight row must be
  among the refined rows, or the arm measured nothing. Positive arm for the harness: SRM 660c must
  repeat WP-2002's 0.5126 ± 0.0048 (Rietveld), 0.5145 ± 0.0036 (Pawley) and 0.5224 ± 0.0033 (Le
  Bail), or the protocol differs from the one that found the 1.7σ. Read: the Kα2/Kα1 weight with
  its reported and plain esds per mode; Le Bail and Pawley against Rietveld in combined σ
  (√(e₁² + e₂²), the measure WP-2002's 1.7σ is in) and over the larger esd; each against 0.5, the
  2j+1 degeneracy ratio (`KA2_RATIO`'s comment: measured integrated ratios run a few percent
  above it, and a diffracted-beam monochromator clips it); and every cell row, free against held
  in each mode, in plain esd over the larger esd (0.1 bar), past `noise`. Rwp, evaluations, status
  and codes beside. These are three laboratories, instruments and materials; whether the modes
  agree well enough is the maintainer's to judge, and no default moves here.
- **K, read 2026-11-16: it cannot run as the table fixes it.** Its families are "WP-2086's reach
  table" and "a sparse-count family". The reach table's 119 fits ran from a harness that is not
  in the tree, against 1.10.0's stored rows, and their raw rows (the cache § Tasks names)
  are gone from that machine, so the table would have to be rebuilt from WP-2086's prose. No
  sparse-count family is named in this file, WP-2002's records or `tests/data/README.md`, and the
  0.77-0.83 reading at 0.5-1 counts a channel names none. Choosing either after reading K's question
  would not be evidence, and the statistic K would compare against (Rwp over the background-only
  model's, or Rwp/Rexp) is itself a new threshold, which § Non-goals sends to the maintainer. So K
  goes to the maintainer as a question, and L runs next.
- **L, its solves and arms, fixed 2026-11-16 before running** (`2017-batch/group_l.py`). Each solve
  is `rx.solve_magnetic` from a converged nuclear fit, built as the acceptance suites build it:
  Cr₂WO₆ at 4 K and at 150 K (`conftest.cr2wo6_nuclear`'s two fits, `sites=["Cr1"]`,
  `ion="Cr3+"`; 4 K takes the k = 0 route, 150 K is the nothing-to-solve case whose unexplained
  peaks match a zone-boundary k), LaMnO₃ at 50 K (`conftest.lamno3_nuclear`, `sites=["Mn2"]`,
  `ion="Mn3+"`), and Ba₂FeSbSe₅ at 1.5 K (`test_magnetic_series`'s nuclear fit of the LLB G4.1
  pattern, `sites=["Fe1"]`, `ion="Fe3+"`, otherwise the defaults; the row's cited case, where two
  k index the same 11 peaks). Three laboratories (HFIR, NIST, LLB) and three materials. Arms:
  `shipped`; `SOLVE_MINIMUM_RTOL` 1e-5 and 1e-3 (patched on the module, read at run time);
  `top_k` 2 and 4; `k_trials` 1 and 3 (both passed as the keyword whose default the constant is);
  `repeat`, the shipped solve run a second time, as the floor: a 1e-12 nudge has no single start to
  act on in a solve that builds its own starts. Control: a `top_k` or `k_trials` arm reaches its
  constant only on the satellite route with more ranked k than the smaller value; a
  `SOLVE_MINIMUM_RTOL` arm only where some trial ran two or more starts; otherwise the arm must
  match `shipped` and reads `unreached`. Read: the verdict, the winning group and k, every trial's
  ΔBIC, status, `n_starts` and `n_minima`, the k-trial table, and the wall time, each arm against
  `shipped`. No published reference grades a constant here; Ba₂FeSbSe₅'s published k and class
  (as `test_magnetic_series` quotes them) and the tutorials' groups are read
  beside the answer. A changed answer is reported as measured and goes to the maintainer.
- **K.** From WP-2086 (PR #1406), the other direction from B12.13: on 119 fits from displaced
  starts, 12 fail silently on real FAP, `usable=True`, `converged`, Rwp 0.44-0.69, zero shift
  to −500 446°. Background-subtracted Rwp reads 0.93-1.00 on nine, 0.575 and 0.467 on two
  `profile_only` rows, 0.256 on `lab_bragg_brentano` at +3 %. Fits that reached the answer read
  0.042 on LaB₆, 0.12-0.14 on FAP and 0.16-0.17 on NAC. The gap is 0.17 to 0.256 on this table,
  each row ran once, and 12 is a lower bound. Sparse counts run the opposite way: a true model
  reads 0.77-0.83 at 0.5-1 counts a channel. The threshold and what a reader sees are the
  maintainer's calls. WP-2005 owns the code's level, and the code's row is still `unaudited`.
- **M.** Since WP-2012 LaB₆'s Biso row passes (`tests/test_staged_start_invariance.py`). cpd-1a's
  reads 15.68 plain esd on zincite's `lor_strain`, a strict xfail, the twin hold's cost.
- **M, its starts and arms, fixed 2026-11-16 before running** (`2017-batch/group_m.py`). Both
  rows' grounds owe "the start without the closing stage on three families", so every fit runs
  twice: under its protocol's shipped closing stage (`closing_window_tol` 1e-3) and with
  `closing_window_tol=None`, the plan ending on its last declared stage. `BISO_SEED`: the four
  protocol families as `test_window_domain._protocol` builds them (`fap`, `nac`, `cpd1a`, `lab6`),
  with every atom's Biso started at 0.5 (the seed) and at 1.5 (the start test's other arm), and
  the noise arm (0.5, every refinable start value that is not zero ×(1 + 1e-12)). Control: an arm
  reaches the start only if the fit refines Biso rows (recorded per fit); otherwise the start is
  the answer and the arm measured nothing. `HARMONIC_WEIGHT_SEED`: no protocol family declares a
  harmonic (recorded per fit), so the four cannot reach it; its one family is the start test's
  synthetic constant-wavelength neutron corundum (`_synthetic`, `_harmonic_fit`: λ/2 at true
  weights 0, 0.003 and 0.05), seeds 0.001, 0.01 (shipped) and 0.3, and the noise arm on 0.01.
  Control: the weight row must be among the refined rows. Positive arm for the harness: under
  the closing stage the pairs must repeat the start test's readings (FAP and NAC 0.000, LaB₆
  ≤ 0.1, cpd-1a near 15.68, the harmonic ≤ 0.003), or the protocol differs from the one the rows
  cite. Read: 1.5 against 0.5 (and each seed against 0.01) in plain esd over the larger esd on
  every row that is not a background coefficient (`_shift`, S/L and H/L ordered as the start
  test orders them, 0.1 bar), past the noise arm, per closing setting; and the closing stage's
  own move (none against shipped at the seed). Rwp, evaluations, status and codes beside, and
  the references beside the bar, not as it: FAP's GSAS cell, NAC's and CaF₂'s cells, cpd-1a's
  weighed fractions, LaB₆'s CIF cell, the synthetic's true weight. These are four real families
  for the Biso start and one synthetic for the harmonic: the only real harmonic on disk is the
  Nd₂Ru₂O₇ neutron pattern, evidence for no audit before the milestone closes (§ Context), so
  whether one synthetic closes the harmonic row goes to the maintainer after it runs.
- **N.** 2002's § The hand rows that stay lists them.
- **N, its four claims and arms, fixed 2026-11-16 before running** (`2017-batch/group_n.py`). The
  four are hand rows, so no `_audit` row carries them; each claim is measured, and a claim that
  holds gets a `slow` test pinning it on the families below, while one that fails goes to the
  maintainer with the measurement and no test. Bar and reads as group A: 0.1 plain esd over the
  larger esd on every row that is not a background coefficient (`_shift`), past a noise arm
  (every refinable non-zero start ×(1 + 1e-12)), with Rwp, evaluations, status and codes.
  (1) **The Le Bail/Pawley intensity seed** (`compile_model`: every reflection of a fresh compile
  starts at max(median y_obs, 1), and a recompile carries matched reflections, so the seed reaches
  the first stage and every reflection that enters later). Fits: `mode="lebail"` and
  `mode="pawley"` under `RefinementPlan.mccusker_default()` on `fap`, `nac` (NAC alone, as its
  protocol's Le Bail pass) and `lab6`, data, structure and instrument from
  `test_window_domain._protocol`. Arms: the seed ×0.01 and ×100, a shaped seed (the median times
  a lognormal draw, σ 1, `default_rng(2017)`, per reflection), and noise; applied by wrapping
  `refine.compile_model`, which counts the seeds it rewrote (control: zero rewrites means the arm
  measured nothing). (2) **`refine._FLAT_AXIS_TEST_DIRECTIONS`** (magnetic path: measurement only,
  its design is Michael's). The claim: which two generic directions stack the SVD does not change
  the axis held or the answer. Fits: `test_magnetic`'s #599 case (R-3m:R, a = 4 Å, α = 70°, the
  moment started at (3.0, 0.2, 0.2)), the same on its tetragonal cousin (`P 4/m m m`, uniaxial
  about c), and `test_joint_flat_moments`' joint #599 case; all three synthetic, the only kind on
  disk with a uniaxial flat rotation. Arms: the shipped pair, the pair turned
  by a fixed generic rotation (30° about (1, 2, 3)/√14), and a pair drawn by `default_rng(2017)`
  on the sphere, rejected within 5° of a lattice axis, face or body diagonal. Control: the spy on
  `_flat_rotation_axis` must see the replaced pair. Read: the angle between held axes, every row
  in plain esd, and whether a hold was taken. (3) **`background.estimators.arpls`'s `max_iter` 50
  and `tol` 1e-3** (changed through `arpls.__kwdefaults__`, read at call time). Arms: shipped,
  tight (500, 1e-6) and loose (10, 1e-2). Patterns: `fap`, `nac`, `cpd1a`, `lab6`, Si SRM 640c
  (2-50°) and SRM 1976a (20-118.6°), six instruments. Read, per pattern: the baseline's largest
  change in σ at the λ each caller passes (`PEAK_MASK_BASELINE_LAMBDA`, `auto_lambda`'s pick, 1e7),
  the background channels `peak_mask` flips, the λ `select_arpls_lambda` and `auto_lambda` choose,
  and `auto_background`'s pick; where a pick changes, the protocol fit refitted on it against
  shipped. (4) **`params.vector.FLOOR_SEEDS`**, the width columns' finite-difference size (the judge
  read it as a numerical setting that moves esds, not an invariant). Arms: every size ×10 and
  ÷10 (the dict mutated in place, read at run time), on `fap`, `nac`, `cpd1a` and `lab6` under their
  protocols. Read: every row in plain esd against shipped, past noise, and each width row's esd
  ratio. No published reference grades any of the four, so each is read against its shipped arm
  only; a size, seed or count that moves an answer is reported as measured.
- **O.** Neither set has a stated domain. The interval runs automatically on every moment angle
  the stationary test leaves out, 20-32 refits an angle, and the grid on every `profile_fraction`
  call. The bars are in `tests/test_window_domain.py`. `PARAMETER_INTERVAL_BRACKET_GROWTH` can
  choose between crossings where window recompiles give several.
- **O, its domains and arms, fixed 2026-11-16 before running** (`2017-batch/group_o.py`, not
  written yet). Each set gets a stated domain first, and the run grades only inside it; a case
  outside it is reported, never graded. Every arm has a noise twin as in Q.
  (O1) **The five interval constants** govern `Refinement.profile_interval` and the automatic
  interval on a moment angle the stationary test leaves out. *Domain claimed*: a converged
  fit's row, interior or on a bound, whose profile crosses the Δχ² threshold at most once a side.
  A profile with several crossings (window recompiles, the growth constant's own docstring) is
  outside it. *Families*: the two-site Pnma set (`test_stationary_moment_angle._fit`, seed 14
  and two seeds the harness fixes from 0-19 before running): Mn2's modulus and the automatic
  angle intervals; `fap`: one interior Biso and one width row on its floor; `cpd1a`: zincite's
  scale and one width on its floor, each the protocol's converged fit. *Arms*, each side:
  `MAX_REFITS` 30 and 120, `SETTLE_RUNS` 2 and 8, `XTOL` 1e-2 and 1e-4, `BRACKET_GROWTH` 1.5
  and 3, `CHI2_TOL` 0.003 and 0.03. `PARAMETER_INTERVAL_LEVEL` is tier 2, a convention, and is
  not armed. *Read*: each end against shipped in units of the row's esd, bar 0.1 esd; refits
  spent; each side's stop reason. *Control*: a reference at `XTOL` 1e-5, `SETTLE_RUNS` 8,
  `MAX_REFITS` 200, run twice from the two noise twins. The shipped end is read against it, and
  if the two references differ by more than 0.1 esd, that row is outside the domain.
  (O2) **The three fraction-grid constants** govern `profile_fraction`'s default grid.
  *Domain claimed*: a phase whose admissible weight fraction is reached somewhere on the grid,
  and whose grid ends neither cut the admissible set nor outrun the frozen windows
  (`FROZEN_COMPILE_STALE` read on every arm). *Families*: `test_qpa_multimodal`'s two-basin
  fixture and its control, and cpd-1a's three phases. *Arms*: `N_FWHM` 5 and 21, `FWHM_MIN`
  0.003 and 0.03, `FWHM_MAX_SPAN` 0.3 and 0.7. *Read*: the admissible set's ends in wt % and in
  the QPA esd, and the grid's best point against shipped (0.1 σ of a point, the table's bar).
  *Positive arm*: on the shipped grid the two-basin fixture shows the basins its test pins, or
  the harness measures something else.
- **O, what its bullet left open, fixed 2026-11-16 before running** (`2017-batch/group_o.py`).
  *The two seeds*: a `screen` step fits seeds 0-19 (14 aside) without intervals, and the two
  lowest whose answer stage passes the stationary-angle test (`moment_angle_tests`, `zeroed`)
  join seed 14. A seed that fails the test has no left-out angle to profile. *The rows*, read
  off each protocol's converged fit on the Mac (macOS arm64) before choosing: FAP's interior
  Biso is `atoms.0.biso`, but **no FAP width row sits on its floor** at that answer (both
  `lor_size` and `lor_strain` interior, no instrument width free), so FAP carries the Biso
  alone and the floor case is cpd-1a's. On cpd-1a, zincite is `phases.1`: its scale and its
  `lor_strain` (on 0, plain esd 0.027). Its `gauss_*` rows also sit on 0, but with the
  41.5-plain-esd floor seeds group N measured, so they are not the case. *How each interval
  runs*: `strategy.parameter_interval.profile_interval(..., record=False)`, the call
  `attach_stationary_intervals` makes, so the Pnma angle rows are the automatic intervals. The
  four search constants are set on that module for the arm; `MAX_REFITS` goes through
  `max_refits`, since it is the argument's bound default. *Control that the explicit call is
  the fit's*: on each Pnma seed, the shipped plain arm also refits with `_auto_intervals` on
  and records the intervals the fit attached. *Read in units of*: the row's plain esd
  (`stderr_uncorrected`), and for an angle with no esd its stationary half-width, the step the
  interval walks in; the reported esd rides beside. *Several crossings*: on each side, points
  sorted by distance from the value, a crossing is each change of sign of Δχ² − cut. *O2's
  grid* is the three module globals of `strategy.fraction_profile`, set for the arm; every
  refit's codes are read through a spy on `Refinement.run_stage`. *Noise twin*: the plain fit
  refitted from every refinable non-zero start ×(1 + 1e-12), and every arm runs on both.
- **P.** At the closing stage's windows the margin errs 0.186 σ and 0.124 σ at the last points of
  FAP and cpd-1a, moving answers 0.026 and 0.043 esd. An edge rule was built and reverted because
  it freed a scale-B ridge (`waiting.md` § B10). The axial floor reads 0.010 on cpd-1a since the
  twin hold, and 0.582 on LaB₆'s `u`, the two minima 0.24 % apart in χ² (WP-2084). `STAGE_WINDOWS_STALE`
  has one family: four protocols at most 1.73 % against 2 %, the chain cpd-1a → cpd-1b at 73.4 %
  under the pre-2045 schedule, and the which-stages rule rests on the calibrate guide's
  `sample_profile` stage at 12.1 %.
- **P, from WP-2054 (PR #1430).** `NOMINAL_AXIAL_APERTURE` (0.02) needs a third family. On SRM
  660c the action fires at 0.005, 0.01 and 0.02 and not at 0.05, and cpd-1a, -1c and -1f behave
  the same way at 0.02. It is a separate row from `AXIAL_SIZING_FLOOR` and no longer reads it.
- **P, its fits and arms, fixed 2026-11-16 before running** (`2017-batch/group_p.py`). Four
  parts. Every refit has a noise twin (every refinable non-zero start ×(1 + 1e-12)) and is read
  in plain esd over the larger esd on the rows that are not background, with the S/L, H/L pair
  ordered as the start test orders it, and Rwp, evaluations, status and codes beside. A family
  is a specimen type with its own instrument (§ Context), so cpd-1a and cpd-1b are one family.
  (P1) **`AXIAL_SIZING_FLOOR`** at 0.01 and 0.05 against the shipped 0.02, set on
  `rietx.model.forward` for the whole fit: the four protocols from their own starts, each with
  the closing stage and with `closing_window_tol=None`, since the row's evidence and its
  ruling both turn on that difference. *Control*: an arm whose evaluations and rows equal the
  shipped arm's never read the floor (11-BM NAC frees no axial term, so it is expected there).
  *Positive arm*: without the closing stage, 0.05 must move LaB₆, FAP or cpd-1a past its noise
  twin, as the row's 0.229-0.516 esd did, or the arm reached nothing.
  (P2) **`REFLECTION_MARGIN_DEG`** at 0.25 and 5 against 0.5, with 20 as the reference the
  window-domain test uses. *Bar 1*, at fixed parameters: each family's shipped answer (the
  closing stage's) drawn at the declared 2 % windows and at the closing 1e-3 windows under each
  margin, the largest |Δy|/σ against 20 and the 2θ where it sits. *Bar 2*, from one common
  start, as § Every refit asks: the shipped answer polished once under each arm (one stage
  freeing every glob the plan frees, then the closing stage), and the shipped margin's polish
  as the control that the polish itself moves nothing. *Positive arm*: bar 1 at 2 % repeats the
  test's 0.124σ on FAP and 0.119σ on cpd-1a within a tenth, or the harness differs from it.
  (P3) **`STAGE_WINDOWS_STALE`**: no refit of its own, since the warning changes no fit. Every
  stage's `window_loss` over its own tolerance is read on every P1 fit, the population of
  fits that reach their answer, and on fits that run away. *The runaway families*: the one
  measured, the QPA round-robin chain cpd-1a → cpd-1b under the tolerance schedule before
  WP-2045 (`test_the_hostile_pairs_runaway_reports_its_stale_windows`' construction, the closing
  compile refused above `axial_sl` 1), with the shipped schedule as its control; the **second**,
  SRM 660c LaB₆ with every cell length +1 % and +3 %, and the **third**, 11-BM NAC with CaF₂ at
  +1 % and +3 %: group A's hard starts, where `lab6_x1.01`, `lab6_x1.03` and `nac_x1.03` missed
  the answer (scale lost, Rwp 9.9× and 1.5× the answer's). cpd-1a +3 % and with zircon declared
  ride beside as more of the first family, and FAP +3 %, which reached its answer, as a hard start
  that does not run away. A fit "runs away" when it misses the family's shipped answer by more
  than 0.1 plain esd on a row that is not background, read against P1's shipped closing fit.
  A runaway that never puts a stage's windows past its tolerance is a different kind of runaway,
  and the warning's silence on it is reported as such, not graded. *Arms*, from the recorded
  losses: the threshold at 0.5×, 1× and 2× the stage's tolerance, and the rule for which stages
  are read: the last only, the shipped rule (the last, and the one before a closing stage), and
  every stage. *Read*: on each fit, which arms fire and on which stage, beside whether it ran
  away. *Positive arm*: the chain under the old schedule reads its warm stage past 0.5 and fires,
  as its test pins; if not, the harness measures something else.
  (P4) **`NOMINAL_AXIAL_APERTURE`** at 0.005, 0.01, 0.02, 0.03 and 0.05, set on `rietx.report`
  between `report()` calls on one fit, so no refit. *Families*: SRM 660c (positive arm: it must
  repeat WP-2054's fires at 0.005-0.02 and silence at 0.05), and the **third**, FAP, with a fourth,
  the SRM 1976a plate, each fitted with both apertures 0 and every axial glob taken off its plan,
  as `test_srm660c_zero_apertures_report_names_axial_asymmetry` and
  `_fit_on_gsas_own_model` do. *Read*: whether `refine_axial_asymmetry` is active and its
  confidence, Layer 1's regions passing their gates out of all, and the asymmetry coefficients
  below 40°. *Reference*: each family's own aperture, its protocol fitted with the axial term
  free (FAP frees S/L with H/L held at 0.02; SRM 1976a ties the two), so each sweep point is
  read as above or below the data's aperture.
- **Q, from WP-1542 (PR #1434).** The held SNIP on PbSO₄ and #726 was not re-measured with
  settled partitions. `StageSpec:lebail_tol` (1e-7) joined the audit table at tier 3 on five
  families of six patterns, with FAP as its stated failing case (a pair 1e-4 Å apart, 1.23 σ at
  that peak). Neither bar reads the split of such a pair. `report.schemas.LEBAIL_GAP_CYCLES`
  (5 plain cycles from flat) was left alone and now sits beside a partition that runs to a
  tolerance. Both are this WP's to weigh in its second pass.
- **Q, its fits and arms, fixed 2026-11-16 before running** (`2017-batch/group_q.py`). Two
  parts, each arm with a noise twin (every refinable non-zero start ×(1 + 1e-12)) and read in
  plain esd over the larger esd, Rwp, evaluations, status and codes beside.
  (Q1) **The held SNIP** that issue #1569 reports, the skill's rule "Under a broad hump, hold
  SNIP" (`docs/skill/rietx/references/judging.md`, SKILL.md §2 item 5), which WP-2008 reads
  against the table, and the PbSO₄ and #726 re-measure WP-1542 left here. *Synthetic*, #1569's
  construction: SRM 660c's LaB₆ model (`test_acceptance_srm660c.build_srm_inputs`' structure)
  with La Biso 0.355 Å² as the truth, Bragg-Brentano Cu Kα₁/Kα₂ with FCJ on, 15-120° at 0.02°,
  a background of 200 + 60·T₁ plus a Gaussian hump at 28° (FWHM 10°, height 150), Poisson noise
  from `default_rng(20261112)`; Rietveld under `RefinementPlan.mccusker_default()` with a Biso
  stage appended, as `_protocol("nac")` does. Arms: a co-refined Chebyshev; P-splines at λ 1
  and 0.01; SNIP held under a 4-term Chebyshev at a half-window of 3 FWHM in points (7, the
  rule's) and 6 FWHM (14, the window #1569 did not try); and the true background held under the
  same 4 terms, the positive arm, which must bring La Biso within two esds of 0.355 or the
  construction measures something else. Positive arm for the harness: the co-refined and the
  3-FWHM held arms repeat #1569's La Biso, 0.3789(158) and 0.4749(163), within one esd; if they
  do not, that is reported and the arms are still read against the truth. Read: La and B Biso
  against the truth in their esds, the cell, background over truth at 26-30°, and
  `BACKGROUND_ABSORPTION`'s worst projection, which #1569 found blind to a held curve.
  *Real*, no truth, so the direction of the move only: #1569's SRM 1976a and FAP under their
  protocols, co-refined against held at 3 FWHM, every Biso; and PbSO₄ (the Durham TOPAS file,
  `tests/local_data.py` `durham-topas/pbso4`) and #726's pattern (WP-1910's) in Le Bail with the
  partition settled at the shipped `lebail_tol`, held against co-refined, on the cell and widths.
  A pattern not on disk is reported, never substituted.
  (Q2) **The three rows**, each side of its value: `refine.LEBAIL_CONVERGED_REL` 1e-3 and 1e-5,
  read only under `lebail_passes > 1`, so its arms run five passes (control: the pass that
  stopped, and why, recorded per fit); `StageSpec:lebail_tol` 1e-6 and 1e-9, with FAP's
  (5 0 6)/(10 −5 0) pair split read beside, since neither bar reads it; and
  `report.schemas.LEBAIL_GAP_CYCLES` 2 and 20 on the layer-0 gap at the converged state, read as
  the ratio against `LEBAIL_GAP_NOTABLE` (1.5). Families: LaB₆ + cBN
  (`test_acceptance_lab6_cbn`), `fap` and `cpd1a`, in Le Bail under their protocols' first
  stages as `mccusker_default()` runs them.
- **Q, what its bullet left open, fixed 2026-11-16 before the full run** (`2017-batch/group_q.py`).
  *The synthetic is #1569's harness, not the bullet's reading of it.* #1569 attaches no
  harness, but the reporter's copy (the triage of 2026-11-16 reproduced the synthetic with it)
  was read before anything ran on the workstation, and it differs from the bullet above. The
  pattern is LaB₆ on `bragg_brentano(monochromator_two_theta=26.6)` at W 2e-3, X 5e-3, no axial
  term, the calculated peaks less their minimum scaled so the strongest is 2e4 counts, then
  the background and Poisson noise. The fit starts W and X from the median FWHM *h* of the
  twelve strongest `pick_peaks` peaks, (0.6 *h*)² and 0.6 *h*, frees the tied axial pair from
  0.02 in a last stage, and runs the plan scale+background, displacement, cell, W, U V X Y,
  coordinates, Biso, axial. The co-refined Chebyshev is `auto_background(kind="chebyshev")`'s
  (16 terms here), the P-splines are `auto_background`'s default (λ 1) and the same at 0.01, and
  the window is round(3 *h* / step), 7 points. So the arms are `cheb`, `ps1`, `ps001`, `snip3`
  (that window), `snip6` (twice it, 14) and `truth`, each with its noise twin, under #1569's
  plan, not `mccusker_default()`. Added: `cheb`, `snip3` and `truth` again with the strongest
  peak at 2e3 and 2e5 counts, and at Poisson seeds 20261113 and 20261114, because one draw and
  one count level are a weak floor. A first version of the harness built the bullet's reading
  (SRM 660c's instrument, `mccusker_default()`, a 6-term Chebyshev). Six fits of it on this
  Mac are discarded, unreported beyond this: they also put the held arm above the co-refined
  one. Three fits of the rewritten harness on this Mac, before the workstation run, repeat
  #1569's La Biso to four digits (0.3789 and 0.4749). The truth arm's 0.3735 is within two of
  its esds, so the construction passes its positive arm before the run.
  *Real, Rietveld*: SRM 1976a and FAP under their acceptance protocols (not #1569's bench plan),
  the held window by #1569's rule on each pattern. *Real, Le Bail*: the PbSO₄ on disk is the
  X-ray pattern (`Pbso4.raw`, 10-160°), not the neutron histogram WP-1542 named, which is not on
  this machine. It is fitted in `P n m a` at Hill's (1992) cell, with Cu Kα₁/Kα₂ at
  1.5405/1.5443 Å as in `test_extinction_gate`'s PbSO₄ instrument, a 6-term Chebyshev, and the
  widths seeded by `seed_widths`. #726's pattern is WP-1910's fixture: `qarr/corundum.prn`,
  20-90°, the CPD instrument, `seed_widths`, the certified cell. *Q2*: `layer0.lebail_gap`
  returns `None` outside Rietveld, so `LEBAIL_GAP_CYCLES` is read on each family's Rietveld
  protocol (LaB₆ + cBN's shared plan, FAP's GSAS-II plan, cpd-1a's QPA plan). Each is fitted
  once, plain and nudged, and the gap is evaluated at 5, 2 and 20 cycles from the one converged
  state, with `n_cycles` echoed back as the control. The `LEBAIL_CONVERGED_REL` arms all run
  five passes, the shipped 1e-4 included, so the control is the pass each stopped at. The
  `lebail_tol` 1e-9 arm runs at a cap of 100 000 cycles, as `test_lebail_cycles` does below
  the default.
- **R.** `width_twins_held` has one real two-phase family, 11-BM LaB₆ + cBN. Y's floor went on a
  physical argument with one synthetic cost (Y −0.0059 against 0, `lor_size` 55 % low). The test:
  SRM 660c with Y free and with Y ≥ 0, read on the certified cell and a sample's size and strain.
  Under TRF no width row holds, and whether brucite and corundum put a coefficient on ±180 is
  unmeasured. `least_squares._fd_typicals` still reads a width off its lower bound and patches Y
  with `_SIGNED_WIDTHS`, so a caller's X or `lor_strain` with min < 0 takes the offset's step of
  1, an error of 1.4e-3 to 1.5e-2 in a width column. A fix declares which rows are widths as table
  data, a design change.
- **R, its fits and arms, fixed 2026-11-17 before running** (`2017-batch/group_r.py`). Three
  parts. Every arm has a noise twin of its shipped arm (every refinable non-zero start
  ×(1 + 1e-12)) and is read in plain esd over the larger esd on the rows that are not
  background, with Rwp, evaluations, status, codes and every stage's `width_twins_held` beside.
  (R1) **`width_twins_held`** on multi-phase fits that free an instrument width and every seen
  phase's twin in one stage. *Families*: 11-BM LaB₆ + cBN under `PLAN_DEGENERATE`, the one the
  row has, as the positive arm: the shipped arm must repeat its test's record (X against both
  `lor_size`, Y against both `lor_strain`) and LaB₆ 16.779(194) wt %, or the harness differs.
  The **second**, the CPD round robin's cpd-1a under `qpa_plan()`, a laboratory Bragg-Brentano
  instrument: its closing stage frees the profile stage's U, V, X, Y with the
  `sample_broadening` stage's widths, so the hold acts there and only there (control: the
  stages before it record no hold). The **third**, 11-BM NAC with CaF₂ under its protocol with
  a `size_strain` stage (`phases.*.lor_size`, `phases.*.lor_strain`, seed 1e-4) inserted after
  `profile`, as `PLAN_DEGENERATE` adds it; and beside it the CuCr₂O₄ ramp's coldest frame with
  CuO (group G's `cucr_cold` start, `mccusker_default()` with the same stage inserted). NAC and
  CuCr₂O₄ were measured on 11-BM, as LaB₆ + cBN was, in other years with other calibrations,
  so by beamline they are one family with it: that is reported, not hidden. *Arms*, all by
  replacing `refine._hold_width_twins` for the fit: `held` (shipped); `none`, which holds
  nothing, so the flat direction stays free; and `specimen`, which holds the specimen columns
  the record pairs with instead of the instrument column (the alternative "measured and not
  adopted" in the row). *Read*: the QPA in wt % against its reference (cpd-1a's weighed
  fractions; TOPAS's 17.907-17.950 for LaB₆), the cells (cBN's against TOPAS's 3.616463 Å), every
  instrument and specimen width with its esd, which specimen widths end on their 0 floor, any
  coefficient on ±`TCHZ_CEILING_DEG`, and the flat-direction codes (`HIGH_CORRELATION`,
  `COVARIANCE_DIRECTION_DISCARDED`). A family is reached if `held` records a hold; `none`
  identical to `held` means the hold changed nothing.
  (R2) **`ProfileTCHZ:y` unfloored** against Y ≥ 0 (`instrument.profile.y` min 0 for the whole
  fit). *Families*: the four protocols, each from its own start, with the closing stage, since
  a floor that no fit's Y reaches measures nothing (control: an arm identical to shipped never
  met the floor). *The row's test*: SRM 660c (the NIST diffractometer) read on its certified
  cell (the CIF block's 4.156780 Å at 20.85 °C, `test_acceptance_srm660c.A_REFERENCE`) and, with
  a `size_strain` stage inserted after `profile`, on the specimen's `lor_size` and `lor_strain`
  under each arm. SRM 660c has no certified size or strain, so those two are read as the
  difference between the arms in their esds, not as a distance from a truth.
  (R3) **TRF and the ±180 bound**. Brucite (isotropic, and with its Stephens block) and
  corundum under `test_acceptance_stephens._plan`, each under LM (the default driver) and TRF,
  with no closing stage as the suite runs them and with the closing stage at 1e-3, which frees
  the instrument and specimen widths together, so the hold acts. *Read*: every width
  coefficient and whether it sits within 1e-6 of ±180, the smallest Lorentzian FWHM
  Γ_L = (X + `lor_size`)/cos θ + (Y + `lor_strain`) tan θ over the pattern, and
  `RESOLUTION_NOT_POSITIVE`. *Control*: the LM fit holds Γ_L ≥ 0 by inequality, so a negative
  Γ_L there means the harness reads something else.
  `_fd_typicals`' step for a signed width is not measured here: its fix is a design change
  (§ R above), so it goes to the maintainer as a question.
- **Reading a wrong answer.** The esd yardstick is blind there, since `_shift` skips a row with
  no esd and a lost phase's rows have none, and a two-valued verdict hides how far a fit
  missed. One noise draw is a weak floor on a chaotic start (cpd-1a +3 % reads 3.99 esd). A
  hard start's table carries Rwp too (`2017-batch/group_a_hard_summary.md`).
- **Every refit.** A staged plan carries a path-dependent scatter of up to about 0.16 esd, and 0.5
  in a background term, from its last frozen compile. Polish both arms from one common start or
  the refit measures that scatter. The CPD QPA plan frees exact pairs (X with `lor_size`, Y with
  `lor_strain`, zero with displacement), so read those rows as one sum.

### Inherited

- **From WP-2020 (2026-11-15).** WP-2020's design brief, which waits on the maintainer, leans
  towards extending the instrument profile file and the plan presets, because no setting in
  the tree needs a new carrier. A demotion here of a limit, a starting value or a plan setting
  is one of the two observations that would flip that pick to a new scenario-set file. Name
  any such demotion in WP-2020's handover log when it lands.

## Non-goals

- New actions or new thresholds. A measurement that suggests one goes to the maintainer.
- The chain actions (WP-2003) and the report's verdicts (WP-2004), which run their own
  second passes.
- The held-out families. Nd₂Ru₂O₇, Zr₆(BDC)₃(Fum)₃, HfIn and CrCl₂(pyrimidine) are evidence
  for no audit before the milestone's close (ruled 2026-10-26 and 2026-10-27, #1052). The
  close session quotes the reporter's hashes and the added HfIn arm from that thread, which
  `generality.md` § Acceptance does not carry yet.

## Tasks

- [x] The list: every row whose evidence or grounds name the second pass or refits on
      either side, grouped by the fits they share, written to a table in this file.
- [x] Per group, the three families and the reference each is measured against, chosen
      before running (a family chosen after seeing its answer is not evidence).
- [ ] Run each group; per row, the answer either side of the threshold and the reference
      distance, with obs/calc/diff PNGs to `tests/output/` for each refit used.
- [ ] Each row's evidence line updated; a row a test now bounds moves to tier 1 or
      `invariant` with the test named; a row that fails goes to a batch for the maintainer.
- [ ] Tell a blank frame with structure from a phase whose peaks missed (from WP-2086,
      PR #1406). WP-2086 holds the instrument on a frame where every phase reads unseen
      only when the residual is noise: Durbin-Watson d ≥ Q, Hill & Flack's (1987) 0.1 %
      point. Q is 1.91 at 4200 channels and 1.96 at 21 001. Fourteen blank frames with
      structure read under Q, at d 0.34-1.49. The real empty Kapton capillary reads
      0.43-1.04 (one pattern, at 6 and 12 background terms), six synthetic humps 0.34-1.49
      and six rebinned-noise frames 0.64-1.02. Strong phases whose peaks missed read
      0.02-0.12. A weak phase that stayed misplaced reads 0.14-1.85, across the whole blank
      range. Raw rows: `~/.cache/ghostshift/rietx/wp-2049/step/disc.jsonl` and
      `blank_fix.jsonl`, not committed; the rebinned and weak-phase figures are from
      WP-2086's handover.
      What a user sees today: these frames stay free as on 1.10.0. Four of the 14, all
      synthetic, refined a zero shift on nothing, each within 2 esd of zero (0.0048 ±
      0.0255° to −0.0029 ± 0.0016°), with U up to 0.38 deg². Kapton stayed at scale 0 and
      zero 0. `PHASE_UNCONSTRAINED` fired on the eight frames whose codes were recorded and
      names the unseen phase. No finding says the instrument stayed free, and the zero
      carries an esd as a measurement does.
      A threshold chosen between 0.12 and 0.34 would be tuned to these frames and would read
      a weak missed phase as blank. So this needs a design, and evidence from more than this
      one fixture set: no real blank frame has yet been seen to pass the check, and the one
      real frame here is from 11-BM. The threshold and anything the reader sees are the
      maintainer's calls.
- [ ] The batch, in the register of `~/.claude/CLAUDE.md`, if any row failed.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py
.venv/bin/python -m tests.audit_delta
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup      # once, on the final tree
```

No row this WP lists still names the second pass as owed.

## References

- WP-2002 and `docs/wp/2002-batch/` (`batch.md`, `rulings.md`, `waiting.md`).
- `docs/milestones/generality.md` § The order, § Acceptance.
- PR #1050's second read of the batch (Mike Gaultois, 2026-10-20).

## Handover log

- **2026-11-17 (group R)** — The width twin hold acts on three more real multi-phase fits, and on all four it is a binding constraint, not a step along a flat direction. Every held fit leaves a specimen width on its 0 floor. Holding nothing lowers Rwp on every family (LaB₆ + cBN 0.1377 → 0.1288) and moves rows other than widths by 9.73 esd (LaB₆ Biso), 4.35 (cpd-1a's axial S/L), 0.96 and 0.17. Unheld, cpd-1a walks Y to −0.198 and zincite's Lorentzian width to −0.0057° at 150°, and NAC's Y goes to −0.0004, with `RESOLUTION_NOT_POSITIVE` on both. Against references the hold neither wins nor loses clearly. On cpd-1a's weighed fractions its largest miss is 0.69 wt % against 0.83 unheld. On LaB₆ + cBN it is the furthest of the three arms from TOPAS's 17.907-17.950 wt % (16.779). Y's lost floor was never reached: no real fit from its protocol's start puts Y below 0, and only two of them free Y at the end. No width coefficient reaches ±180 on brucite or corundum under LM or TRF. No value moved and no tier changed; the two rows now say what was measured, and five questions go to the maintainer.

  *Done.* In PR #1577. `2017-batch/group_r.py`, `group_r_summary.md`; fits and arms fixed in "R, its fits and arms" (fcabab9dd) before anything ran. Evidence added on `StageResult.width_twins_held` and `ProfileTCHZ:y` (e3f1959dc, judge folded in 3dd0d268c); tier, value, grounds and approval unchanged.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `4cb7aedc7`: 42 tasks, 2 from the canary, 40 on 8 workers in 22 s, 313 MB peak). Every arm's noise twin moved at most 4.8e-6 esd.

  | Family (R1) | Hold acts from | Rwp held / unheld / seed-held | Off the widths, unheld / seed-held (esd) | QPA held / unheld / seed-held | Reference |
  |---|---|---|---|---|---|
  | 11-BM LaB₆ + cBN (positive arm) | `size_strain` (X, Y) | 0.137711 / 0.128812 / 0.168625 | 9.73 LaB₆ Biso / 21.3 cBN a | LaB₆ 16.779 / 16.842 / 17.787 wt % | TOPAS 17.907-17.950; cBN a +38 / +39 / +16 ppm |
  | cpd-1a (CPD lab) | `sample_broadening` (U, X, Y) | 0.163072 / 0.161872 / 0.162894 | 4.35 / 4.49 axial S/L | corundum 1.717 / 1.981 / 1.425 wt % | weighed 1.15; largest miss 0.69 / 0.83 / 0.73 |
  | 11-BM NAC + CaF₂ | `size_strain` (X, Y) | 0.088244 / 0.088172 / 0.092877 | 0.96 CaF₂ Biso / 10.8 CaF₂ scale | CaF₂ 1.509 / 1.514 / 1.348 wt % | none |
  | CuCr₂O₄ + CuO, 6.8 K | `size_strain` (X, Y) | 0.223292 / 0.223286 / 0.224123 | 0.17 / 6.73 CuO scale | CuO 0.889 / 0.893 / 0.502 wt % | none |

  *Controls.* The positive arm repeats its test's record (X with both `lor_size`, Y with both `lor_strain`) and 16.779 wt %. The protocol expected cpd-1a's hold in the closing stage only; it acts from `sample_broadening` on, because each stage also frees every earlier stage's globs, and the Stephens fits of R3 hold the same way without a closing stage. The `specimen` arm held every specimen width at its seed (0.02 or 1e-4), so it fits no specimen broadening: on NAC it reproduces R2's fit without the `size_strain` stage to every digit. It is not the alternative WP-2002 measured, a specimen width held on its floor. R2's Y ≥ 0 arm is bit-identical or within 1.3e-4 esd on every family, the protocol's own "never met the floor" control: FAP fixes Y at 0, NAC ends at 0.0052 and SRM 660c at 0.0151, both free, and cpd-1a (0.060) and SRM 660c with `size_strain` (0.0133) end with Y held by the twin hold. SRM 660c's `lor_size` and `lor_strain` sit on their 0 floor under both arms, its cell 4.156877 Å under both. R3: Γ_L ≥ 0.0062° on every fit, under LM (the control) and TRF; `STEPHENS_STRAIN_NOT_POSITIVE` on brucite's block under TRF only; `RESOLUTION_NOT_POSITIVE` fires on plain SRM 660c under both Y arms with Y > 0, so it is not specific to a negative Y.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: every number matches the raw rows but two (a 0.74 for 0.73, and SRM 660c's two cells swapped), both fixed. `width_twins_held` weak: two unrelated families against three, and the evidence now reads as a binding constraint, with the held arm furthest from TOPAS on LaB₆ + cBN, a cross-code check. The seed-held arm is not a fair stand-in for holding the specimen side; said so in the row. `ProfileTCHZ:y` weak, close to measuring nothing: only two fits free Y at the end, and "no real Y below 0" leans on the twin hold, without which cpd-1a goes to −0.198. Every wording fix applied.

  *Tests.* TESTS_PLACEHOLDER

  *Not done, and why.* No test: no row moved toward tier 1. The floor-hold alternative (a specimen width held on its floor, WP-2002's "measured and not adopted") was not re-run, since the protocol named the seed-held arm. `_fd_typicals`' step for a signed width was not measured; its fix is a design change. The fraction esds were not recorded, so the positive arm's (194) is unchecked.

  *Questions for the maintainer.* (37) The hold binds on every real multi-phase family measured: a specimen width on its floor in every held fit, unheld Rwp lower, rows other than widths moving up to 9.73 esd, and on LaB₆ + cBN the held arm the furthest from TOPAS. A refiner who fixes the instrument from a standard and frees the specimen, or who holds the specimen side, would dissent. Does the action still meet the unanimity bar, or should it report the pair and act only to stop the walk (unheld cpd-1a reaches Y −0.198 and a negative zincite width)? (38) Do 11-BM NAC + CaF₂ and the CuCr₂O₄ ramp, measured on 11-BM in other years, count as families apart from LaB₆ + cBN? If not, the hold has two, the CPD lab and 11-BM. (39) Should the next pass run WP-2002's floor-hold alternative as its own arm on these four families? (40) `ProfileTCHZ:y`: no real fit reaches Y < 0 with the hold in place, so the floor's only measured cost remains the synthetic calibration. Is a real family with a true Y ≤ 0 owed, or does the row close on its physical argument? (41) `_fd_typicals` patches only `instrument.profile.y` as a signed width (`_SIGNED_WIDTHS`), so a caller's X or `lor_strain` with min < 0 takes a step of 1. Declare which rows are widths as table data, a design change? Unheld, cpd-1a's zincite Lorentzian width ended at −0.0057° under LM, which holds Γ_L ≥ 0 by inequality; whether that inequality covers every phase over the whole range was not checked.

  *Next:* group S (read the three tier-2 citations, through the fact-check skill). K waits on a harness and a sparse family, B on a named third family, H on #1494.
- **2026-11-16 (group P)** — Of the four window rows, three hold where their evidence said and one is silent on the runaways this group set out to find. The axial sizing floor at 0.01 and 0.05 moved FAP and cpd-1a up to 0.52 esd without the closing stage, and at most 0.0095 behind it, where only LaB₆ moved: 0.58 on `profile.u`, between its two minima, not a window. Behind the closing stage the condition the seventh round set may therefore now hold. The reflection margin's fixed-parameter error repeats the test's 0.124σ on FAP; a final polish at 0.25°, 5° or 20° moved no answer more than 0.057 esd. On fits that run away, the stale-window warning stays silent. From cells displaced 3 %, SRM 660c, 11-BM NAC and cpd-1a missed their answers by 109, 93 and 41.5 esd. Their windows did go stale, by 2.1 %, 57 % and 79 % of the Bragg intensity, but only on intermediate stages, which the shipped rule does not read. Reading every stage would report all three, and also FAP from the same start, which reached its answer. The QPA chain's own runaway repeats and is reported. The report's nominal aperture fires only below each family's own aperture on its third and fourth families, FAP and the SRM 1976a plate; above it the report goes silent, on FAP because Layer 1 abstains. No value moved and no tier changed; the four rows now say what was measured, and four questions go to the maintainer.

  *Done.* In PR #1577. `2017-batch/group_p.py`, `group_p_summary.md`; fits and arms fixed in "P, its fits and arms" (fd746a6b3) before anything ran, the second and third runaway families named there. Evidence added on `forward.AXIAL_SIZING_FLOOR`, `forward.REFLECTION_MARGIN_DEG`, `STAGE_WINDOWS_STALE` and `report.NOMINAL_AXIAL_APERTURE` (d7ca7ce6b, judge folded in c42398c0a and 70ed25334); tier, value, grounds and approval unchanged.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `0d9216dbf`: 51 tasks, 3 from the canary, 48 on 8 workers in 43 s, 462 MB peak; the canary repeats this Mac's Rwp to seven digits). Every refit has a noise twin, which moved at most 4.75e-6 esd.

  | Constant (shipped) | Arms | Without the closing stage, or at the declared 2 % windows | Behind it, or at the closing 1e-3 windows | Not reached |
  |---|---|---|---|---|
  | `AXIAL_SIZING_FLOOR` 0.02 | 0.01, 0.05 | 0.05: FAP 0.516 (`lor_size`), cpd-1a 0.349 (corundum scale), LaB₆ 0.210 (`profile.x`); 0.01: FAP 0.158, cpd-1a 0.269 | ≤ 0.0095 on FAP and cpd-1a; LaB₆ 0.582 on `profile.u` at 0.05, its second minimum (WP-2084) | 11-BM NAC (no axial term), LaB₆ at 0.01 (S/L 0.037, H/L 0.025) |
  | `REFLECTION_MARGIN_DEG` 0.5° | 0.25°, 5°, 20° | fixed parameters, 2 % windows: FAP 0.148σ at 0.25°, 0.125σ at 0.5° (the test's construction 0.124), cpd-1a 0.125σ at both (its 149.9° point's reflection lies past 0.5°), 0.000σ at 5° | 1e-3 windows: FAP 0.209σ / 0.186σ / 0.046σ, cpd-1a 0.130σ / 0.130σ / 0.005σ; one polish under each margin from the shipped answer: ≤ 0.057 esd (cpd-1a fluorite `lor_strain` at 5° and 20°), background 0.39 | 11-BM NAC and LaB₆: ≤ 0.022σ at any margin |

  | Fit | Misses its answer by | Worst stage loss / its tolerance | Shipped rule | Every stage at 1× |
  |---|---|---|---|---|
  | QPA chain cpd-1a → cpd-1b, pre-WP-2045 schedule (positive arm) | runs to `axial_sl` 554, closing compile refused | 36.7 (`warm_refit`, 73 %) | reports it | reports it |
  | the same, shipped schedule | — | ≤ 0.66 | silent | silent |
  | SRM 660c, cell +1 % | 308 esd (scale lost in the first stage, Rwp 9.9×) | no loss recorded | silent | silent |
  | SRM 660c, cell +3 % | 109 esd (Rwp 9.9×) | 1.05 (`lines_axial`, 2.1 %) | silent | reports `lines_axial` |
  | 11-BM NAC, cell +3 % | 93 esd (CaF₂ scale, Rwp 1.5×) | 28.5 (`profile`, 57 %) | silent | reports `profile` |
  | cpd-1a, cell +3 % | 41.5 esd (Rwp 2.3×) | 39.4 (`profile`, 79 %; `sample_broadening` 37 %, `lines_axial` 10 %) | silent | reports all three |
  | FAP, cell +3 % | reaches (4e-6 esd) | 9.9 (`sample_lor`, 19.8 %) | silent | reports `sample_lor` |
  | 11-BM NAC +1 %, cpd-1a with zircon | reach (≤ 0.07 esd) | ≤ 0.66 | silent | silent |
  | the four protocols' 32 fits (P1) | reach | ≤ 0.80 any stage, ≤ 0.025 on the stages read | silent | silent (at 0.5× every cpd-1a and LaB₆ fit) |

  | `NOMINAL_AXIAL_APERTURE` | Own aperture (S/L, H/L) | 0.005 | 0.01 | 0.02 | 0.03 | 0.05 |
  |---|---|---|---|---|---|---|
  | SRM 660c (positive arm, WP-2054's sweep) | 0.037, 0.025 held | 14/15, fires | 15/15, fires | 15/15, fires | 15/15, fires | 14/15, silent |
  | FAP (third family) | 0.017, 0.02 held | 5/15, fires | 5/15, fires | Layer 1 abstains | abstains | abstains |
  | SRM 1976a plate (fourth) | 0.031, tied | 13/15, fires | 14/15, fires | 14/15, fires | 14/15, fires | 13/15, silent |

  *Controls.* Each reading of the nominal sweep was repeated at 0.005 after the sweep and was identical. The P2 polish at the shipped margin, which should move nothing, moved LaB₆ 0.585 esd from the fit it started at, into the same second minimum the floor's 0.05 arm reached (Rwp 0.087326 against 0.087327), so LaB₆'s margin arms compare there; on the other three it moved at most 6e-4. The chain under the shipped schedule carries `CELL_RUNAWAY` on cpd-1b, not this group's code, noted only.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: every number in the four strings matches the raw rows. `STAGE_WINDOWS_STALE` holds (positive arm passes; "silent on all three" counts fits, two new families and a second cpd-1a start). `AXIAL_SIZING_FLOOR` holds, with the two-minima reading now backed by one more polish at the shipped floor. `REFLECTION_MARGIN_DEG` weak: the "under 0.06 esd on four families" claim was one polish, with the margin reaching nothing on NAC and LaB₆ and LaB₆'s polish control failing; reworded. `NOMINAL_AXIAL_APERTURE` holds, FAP's silence by abstention named, and "no wrong call" narrowed to the asymmetry action (`refine_cell` at 0.10 on SRM 1976a at 0.005 was not graded). Every wording fix applied.

  *Tests.* Fast selection at 70ed25334 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14850 passed, 280 skipped, 32 xfailed in 7 min 37 s, 5.6 GB peak. Against group O's 14849 and 281, `test_skill.py`'s origin/main skip passed on this run's fresh workstation clone; no test added. `tests/test_audit_table.py` and `tests/test_docs_consistency.py` 49 passed, `python -m tests.audit_delta` exit 0 (evidence only), `python -m tests.reader_output` exit 0, unchanged against the merge-base (macOS arm64, worktree `[dev]` venv). Ruff clean; Vale 0 errors. Full suite not run: no measured number in the package can move.

  *Not done, and why.* No test: no row moved toward tier 1, and `STAGE_WINDOWS_STALE`'s stage rule and threshold are the maintainer's. Whether the stale intermediate stages caused the runaways or followed from them was not separated: a displaced cell drives the widths up in the profile stage either way.

  *Questions for the maintainer.* (33) `STAGE_WINDOWS_STALE` reads the last stage and the one before a closing stage, on the ground that an earlier stale stage is repaired by the stages after it (one synthetic fit). On three runaways from cells +3 % the earlier stale stage (2.1-79 %) was not repaired and the warning stayed silent; reading every stage at 1× reports them, and also FAP +3 %, which was repaired. Which stages, at which threshold? (34) `AXIAL_SIZING_FLOOR`'s grounds say that behind the closing stage it passes on LaB₆ and FAP and misses on cpd-1a. Now cpd-1a moves 0.0095 and LaB₆ 0.582, between its two minima. Is the seventh round's condition met, and does a move between two minima count as a pass? The older evidence's "cpd-1a's corundum c a strict xfail" may also be stale. (35) `REFLECTION_MARGIN_DEG`: which bar decides, the fixed-parameter error (0.186σ on FAP at the closing windows, past 0.1) or the answer (≤ 0.057 esd)? (36) `NOMINAL_AXIAL_APERTURE`: does the SRM 1976a plate (X'Pert) count as a family apart from SRM 660c (the NIST diffractometer), and is Layer 1 abstaining an acceptable form of the silence the row claims above the aperture?

  *Next:* group R (`width_twins_held`, `ProfileTCHZ:y` unfloored; write its fits-and-arms bullet first), then S (read the three tier-2 citations, through the fact-check skill). K waits on a harness and a sparse family, B on a named third family, H on #1494.
- **2026-11-16 (group O)** — The profile interval's five search constants hold inside their domain, with one exception. The fraction grid's three could be graded on one synthetic case only, and there every arm moves the answer past the bar. Fourteen interval rows were run on five fits, each with a noise twin: the two-site Pnma set at seeds 0, 1 and 14 (Mn2's modulus and every angle the fit left out), FAP's first Biso, and cpd-1a's zincite scale and its `lor_strain` on 0. Every row is inside the stated domain: one crossing a side, and two reference runs agreeing to 3.2e-8 of the row's unit. The shipped ends sit within 4.6e-4 of the reference. `MAX_REFITS` was never reached (25 refits a side at most, under any arm), and `SETTLE_RUNS` 8 changed nothing. `XTOL` and `CHI2_TOL` moved the ends 0.0026 and 1.4e-4 at most. `BRACKET_GROWTH` at 1.5 moved nothing, but at 3 it cut both angle intervals on seed 0 short by 0.52 and 0.54 half-widths, on both twins. Its far probe lands 152-158 over the cut, and every refit nearer in then stays above it. The fraction grid was profiled on `test_qpa_multimodal`'s two-basin fixture, its control and cpd-1a's three phases. On cpd-1a no profile measures the fit's own model: each refit descends 81-90 χ² below the fit (cut 77) even with the axis pinned at its fitted value, and `profile_fraction`, unlike `profile_interval`, does not hold what the fit's last stage held. Corundum's lowest points sit at peak widths of 2-30° FWHM and 51-64 wt %, against 1.72(64) fitted and 1.15 weighed. On the control, the one case graded, the admissible range's ends are grid points, so they move 0.13-0.46 esd under the span and start arms, and 5 widths leave no admissible point at all. The fixture's second basin is one grid point wide, the grid's top at half the span: both span arms lose it. No value moved and no tier changed; the eight rows now say what was measured, and five questions go to the maintainer.
  *Done.* In PR #1577. `2017-batch/group_o.py`, `group_o_summary.md`; domains and arms fixed in "O, its domains and arms" (25cec9b21) and "O, what its bullet left open" (0d4578e06) before the workstation run. Evidence added on the five `PARAMETER_INTERVAL_*` rows and the three `FRACTION_PROFILE_*` grid rows (tier, value, grounds and approval unchanged).

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `0d4578e06`: 162 tasks on 16 workers after the canary, 2 h 17 min wall, the fourteen cpd-1a profiles 16 min to 2 h 14 min each, 743 MB peak; the first launch died on wsrun's process cap and was relaunched with `--max-procs-per-task 40`):

  | Constant (shipped) | Arms | Largest end shift, inside the domain | Refits (shipped → arm, all rows) | Reached |
  |---|---|---|---|---|
  | `MAX_REFITS` 60 | 30, 120 | 0 (bit-identical) | 786 → 786 | no: 25 refits a side at most, under any arm |
  | `SETTLE_RUNS` 4 | 2, 8 | 1.2e-6 (2); 0 (8) | 786 → 736 (2) | a probe used all four runs on two rows (seed 14's two `dof1` angles, both twins), and settled there |
  | `XTOL` 1e-3 | 1e-2, 1e-4 | 0.0026 plain esd (seed 14's Mn2 modulus); 4.6e-4 | 786 → 714, 838 | yes, on every fit |
  | `BRACKET_GROWTH` 2 | 1.5, 3 | 4.8e-4 (1.5); **0.52 and 0.54 half-widths** (3, seed 0's two angles, both twins), 5.0e-4 elsewhere | 786 → 770, 864 | yes, on every fit |
  | `CHI2_TOL` 0.01 | 0.003, 0.03 | 1.4e-4 | 786 → 798, 780 | on four and six of ten fits |

  | Fit | Rows | Shipped interval (one row) | Reference vs shipped | Noise twin vs plain |
  |---|---|---|---|---|
  | Pnma seed 0 (the passing round leaves out the two `dof1` angles) | Mn2 modulus, 2 angles | Mn2 0.6981 to 0.7149 | 3.9e-5 | 3.9e-9 |
  | Pnma seed 1 (the two `dof2` angles) | Mn2 modulus, 2 angles | Mn2 0.6974 to 0.7156 | 2.5e-4 | 2.9e-8 |
  | Pnma seed 14 (all four angles) | Mn2 modulus, 4 angles | Mn2 0.6997 to 0.7110 | 2.4e-4 | 2.1e-8 |
  | FAP | `atoms.0.biso` | 0.2713 to 0.4800 | 2.6e-4 | 2.0e-8 |
  | cpd-1a | zincite scale; `lor_strain` on 0 (one-sided) | `lor_strain` 0 to 0.0284 | 4.5e-4 | 1.2e-5 |

  | Constant (shipped) | Arms | The control (CaF₂ 3.674 ± 0.412 wt %, range 3.291-3.937) | cpd-1a zincite | The two-basin fixture |
|---|---|---|---|---|
| `FRACTION_PROFILE_N_FWHM` 11 | 5, 21 | 5: no admissible grid point, the range the fit's alone (ends 0.93 and 0.64 esd in); 21: ends 5e-6 esd, best point 0.82 esd | ends ≤ 0.003 esd | both basins at 5 and 21, the top point kept by construction |
| `FRACTION_PROFILE_FWHM_MIN` 0.01 | 0.003, 0.03 | ends 0.20 and 0.46 esd; best point 1.11 esd at 0.03 | ≤ 4.5e-4 esd | both basins (the top point does not depend on it) |
| `FRACTION_PROFILE_FWHM_MAX_SPAN` 0.5 | 0.3, 0.7 | ends 0.20 and 0.13 esd | ≤ 3.1e-4 esd | **second basin lost on both** (upper end 77.07 → 1.32 and 1.35 wt %, 230 esd) |

| Family | Fit | χ² fit − lowest point (cut) | Shipped range | What the profile reads |
|---|---|---|---|---|
| two-basin fixture | CaF₂ 0.931 ± 0.33 wt % | 0 (5.2) | 0.930-77.067 | the second basin at 42.49° FWHM alone (Δχ² 5.8 at 27.98° on the 21-point grid; 7.6 at 59.5° on the 0.7 span) |
| control | CaF₂ 3.674 ± 0.412 | 0 (5.1) | 3.291-3.937 | one basin, two to three grid points wide |
| cpd-1a corundum | 1.717 ± 0.643 (weighed 1.15) | 1884-1949 (77.4) | 51.5-64.3 | lowest at 2.1-30° FWHM; `FROZEN_COMPILE_STALE` at 2 points; noise twin and plain disagree on the arms (21 points: upper end −1.8 and +46 esd) |
| cpd-1a zincite | 3.354 ± 0.208 (weighed 4.04) | 90.1 (77.4) | 3.484-3.509 | the fit outside its own range; W and χ² flat from 0.14° to 12° FWHM |
| cpd-1a fluorite | 94.928 ± 0.645 (weighed 94.81) | 89.8 (77.4) | 94.62-94.91 | flat from 0.35° to 72.5° FWHM, the top point admissible; `FROZEN_COMPILE_STALE` at 1-5 points |

  *Controls.* The fit's own intervals, attached with `_auto_intervals` on, equal the explicit calls on all three Pnma seeds (difference 0). The screen picked seeds 0 and 1: the stationary-angle test passes on all nineteen seeds of 0-19 (14 aside), because a round that leaves out a subset of the angles counts. On seeds 0 and 1 that round leaves out two of the four. On seed 0 Mn2's modulus keeps the two `dof2` angles in its covariance, so its plain esd is 0.29 μ_B, against 0.001 on seeds 1 and 14, and in that unit its row reads nothing. On seeds 1 and 14, `fit_is_minimum` is False: a probe found χ² 1.4-1.5 below the fit on seed 1 and 0.14-0.28 on seed 14, against a cut of 5.0. The positive arm passes: on the shipped grid the two-basin fixture shows the two basins its test pins, on both twins. On cpd-1a the interval walk of O1, on the same fit, reads `fit_is_minimum` True on both its rows, while the fraction profile's refit with zincite's `lor_strain` pinned at its fitted 0 reads 81.4 χ² below the fit: the drop comes from the profile's refit, not from the width. `profile_interval` holds the fit's last stage's held parameters beside the pinned one (#1075, `parameter_interval.py`); `fraction_profile.py` pins the axis alone. That is the likely cause, not tested here. *Canary*: FAP shipped and reference, the control fixture's shipped profile, 43 s, 456 MB, 192 % of 2 cores, at `0d4578e06`; FAP's interval repeats the Mac's to 1e-9.

  *How BRACKET_GROWTH 3 fails.* On seed 0's two `dof1` angles the upper side probes +1 half-width (4.6 under the cut), then +3 (152-158 over it). Every refit Brent then places between them, warm from the last probe, reads 4.2-6.0 over the cut from +1.001 on. So the end lands at +1.0, where the shipped walk measured 3.9 under the cut at +1.22 and found the end at +1.535. The profile a walk reads depends on how far its far probe went. That is the hazard the row's evidence names for window recompiles, met here without one. The domain test cannot see it, since the shipped and reference walks both read one clean crossing.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed. O1: `BRACKET_GROWTH` **holds at tier 3, domain weak** (its 3 arm fails the bar about five times over, and the reference keeps it shipped, as it does `CHI2_TOL`); `CHI2_TOL`, `SETTLE_RUNS`, `XTOL` **hold**; `MAX_REFITS` **weak** (never reached, so its arms measure nothing, and no synthetic case reaching it is named). Across O1: the 1e-12 noise twin makes "two reference runs agreeing" close to automatic, and eight of the fourteen rows sit on fits whose walk read `fit_is_minimum` False. O2: all three **weak**: the harness read the domain's "grid ends" as the top point only (zincite's 0-width point is admissible); zincite is not a real inside case (fit not admissible, axis inert), which leaves the synthetic control as the one graded case; and the bar fails there on every arm. The fixture's second basin is outside by the harness's stand-in, not by the protocol's words: the 0.7 arm shows the basin closing before 59.5°, so the top end does not cut it. Two misquotes were fixed in the rows before commit (reference agreement 3.2e-8, not 3.3e-8; all four settle runs used on two rows, not four), and the O2 evidence was rewritten to say the above.

  *Tests.* Fast selection at ba056f679 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14849 passed, 281 skipped, 32 xfailed in 8 min 27 s, as a co-tenant, 5.2 GB peak; after it only `_audit` evidence strings, the harness and its summary changed. `tests/test_audit_table.py` and `tests/test_docs_consistency.py` 49 passed, `tests.audit_delta` exit 0 (35 rows changed against the merge-base), at e4e91eb0f (macOS arm64, worktree `[dev]` venv). `python -m tests.reader_output` exit 0, unchanged against the merge-base with `origin/main` (`bc77a934e`).

  *Not done, and why.* A test bounding the interval constants' error over the domain, which the rows' grounds make the condition for tier 1: the shipped arm sits within 4.6e-4 of the reference on all fourteen rows, so such a test would pass, but writing one is the maintainer's call (question 29). Mn1's modulus, which the fit also profiles: not in the bullet's rows. P, R and S: not started in this run.

  *Questions for the maintainer.* (28) `BRACKET_GROWTH` 3 cuts seed 0's two angle intervals short by half a half-width, because every refit after the far probe starts warm from it and stays in a worse conditional minimum. Should the walk restart from the fit once a probe overshoots the cut, so the measured profile cannot depend on how far the far probe went? (29) A test bounding the five interval constants' error over the domain, which the grounds make the condition for tier 1: `CHI2_TOL`, `XTOL` and `SETTLE_RUNS` would pass it here, `BRACKET_GROWTH` fails at 3, and `MAX_REFITS` was never reached. Should it be written, on which synthetic case reaching the cap, and do fits whose walk reads `fit_is_minimum` False (Pnma seeds 1 and 14), or a 1e-12 noise twin, count toward a domain of converged fits? (30) Every cpd-1a fraction profile reads `fit_admissible` False, the refit descending 81-90 χ² with the axis at its fitted value. Should `profile_fraction` hold what the fit's last stage held, as `profile_interval` does since #1075? Until it does, is any cpd-1a profile evidence, and is a width axis that moves neither W nor χ² over two decades expected? (31) Does the 0-width point count as a grid end that can cut the admissible set, and is the fixture's hump basin, one grid point wide and found only at half the span, inside the domain? (32) The admissible range's ends are grid points, so any grid arm moves them. Is 0.1 esd the bar for them, given it fails on every arm of the one graded case?

  *Next:* group P (write its protocol bullet first: `AXIAL_SIZING_FLOOR`, `REFLECTION_MARGIN_DEG`, `STAGE_WINDOWS_STALE`, `NOMINAL_AXIAL_APERTURE`; the four, and a second and third family that runs away), then R and S. K waits on the harness and a sparse family, B on its third family, H on #1494.

- **2026-11-16 (group Q)** — The held SNIP of issue #1569 biases Biso upward, and the bias reproduces on the real patterns. On #1569's synthetic LaB₆, rebuilt from the reporter's harness, the skill's recipe (SNIP held at 3 FWHMs under a 4-term Chebyshev) puts La Biso at 0.4749(137) against a truth of 0.355, 8.8 esd high. The co-refined Chebyshev gives 0.3789 and the true background held gives 0.3735, so the construction's own floor is about 1.4 esd. Doubling the window to 6 FWHMs (14 points) still leaves it 6.0 esd high. The excess holds on two more Poisson draws (8.0 and 4.6 esd) and at ten times the counts (7.9 esd), and shrinks to 2.3 esd at a tenth. On SRM 1976a and FAP, under their acceptance protocols rather than #1569's bench plan, the held arm raises every Biso, by 12-18 esd on SRM 1976a's two sites and FAP's first three. So the direction #1569 reported is repeated on both real patterns. In Le Bail, the held arm moves PbSO₄'s cell 9.3 esd on b and its widths up to 31 esd, and leaves #726's corundum within 1.4 esd. Of the three Le Bail rows, `LEBAIL_CONVERGED_REL` was never reached on its three families, `lebail_tol` moves cpd-1a 0.8 esd either side, and `LEBAIL_GAP_CYCLES` is not at its fixed point on two families of three. No value moved; four questions go to the maintainer, and #1569's proposed changes stay with WP-2008.
  *Done.* In PR #1577. `2017-batch/group_q.py`, `group_q_summary.md`; fits and arms fixed in "Q, its fits and arms" (89934d719) and "Q, what its bullet left open" (2d6bcc737, 26bf690c9) before the workstation run. Evidence rewritten on `refine.LEBAIL_CONVERGED_REL` and `StageSpec:lebail_tol` (tier, value, grounds and approval unchanged), and added on `report.schemas.LEBAIL_GAP_CYCLES`, which stays unaudited, for the maintainer's tier. The held-SNIP rule is a skill rule with no `_audit` row; the skill is not edited here.

  *Cross-references.* Issue #1569 reports the bias. The 2026-11-16 issue triage (#1585) folds it into WP-2008, which reads the skill against the table and owns the judging rule, the abstention row and the docstring sentence #1569 proposes. This entry is the measurement twin the triage names. The issue is not commented on from here.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `f148d8abb`: 58 tasks, 81 s on 6 workers after the canary, 418 MB peak):

  | Arm, #1569's synthetic (strongest peak 2e4, seed 20261112) | La Biso | from truth 0.355 | B Biso (truth 0.276) | background/truth at 26-30° | worst absorption |
  |---|---|---|---|---|---|
  | Chebyshev co-refined (`auto_background`, 16 terms) | 0.3789(132) | +1.80 esd | 0.280(86) | 0.971 | 0.012 |
  | P-spline λ 1 | 0.3687(146) | +0.94 | 0.256(95) | 0.892 | 0.012 |
  | P-spline λ 0.01 | 0.3730(130) | +1.38 | 0.276(84) | 0.992 | 0.015 |
  | SNIP held, 7 points (3 FWHMs, the rule) | 0.4749(137) | **+8.76** | 0.299(85) | 0.987 | 0.011 |
  | SNIP held, 14 points (6 FWHMs) | 0.4369(136) | +6.02 | 0.326(87) | 0.989 | 0.010 |
  | true background held, 4 terms (positive arm) | 0.3735(128) | +1.44 | 0.268(83) | 0.997 | 0.011 |

  The esds are the unscaled ones (`stderr_uncorrected`); #1569 quoted the inflated ones, 0.0158 and 0.0163. At the other draws and count levels the three arms read, in La Biso from truth: seed 20261113 +1.71, +8.00, +1.26 esd (co-refined, held, truth); seed 20261114 −1.86, +4.57, −2.28; strongest peak 2e3 +0.75, +2.31, +0.07; 2e5 +0.02, +7.89, −0.18. On every one the held arm sits 0.034-0.140 Å² above the co-refined one, and the truth arm within 0.007 of it, except at 2e3 counts (0.056, under one esd of 0.08). `BACKGROUND_ABSORPTION`'s worst projection is 0.011 on the held arm at the main draw, as #1569 found: the screen projects onto the freed terms, and the held curve has none.

  | Real pattern | Mode | Held window | Co-refined → held | Codes the held arm adds |
  |---|---|---|---|---|
  | SRM 1976a | Rietveld, its texture protocol | 23 points | Al Biso 0.992(18) → 1.271(20), +14.0 esd; O 0.963(27) → 1.314(29), +12.1 | `HIGH_CORRELATION` |
  | FAP | Rietveld, GSAS-II protocol | 10 | every Biso up: `atoms.0` 0.374 → 0.847 (+14.4), `.1` 0.250 → 0.733 (+18.1), `.2` 0.245 → 0.726 (+13.4), the four others +1.6 to +5.3; cell a +8.3, c +5.7 | `BACKGROUND_ABSORPTION` (worst 0.199 → 0.272) |
  | PbSO₄ (X-ray, Durham) | Le Bail | 13 | cell b +9.3 esd, c +6.0, a +0.5; widths −31 (Y) to +18 (V) | none (two dropped) |
  | #726, SRM 676a corundum, 20-90° | Le Bail | 24 | every row within 1.4 esd | none |

  | Row | Arms | Largest move against shipped | Its control |
  |---|---|---|---|
  | `LEBAIL_CONVERGED_REL` 1e-4 | 1e-3, 1e-5, five passes | none: bit-identical on all three | LaB₆ + cBN and cpd-1a stop at a pass that raised Rwp (13.609 → 13.649 %; 22.561 → 33.879 %); FAP reaches the cap still falling 1.3 % at its last pass (10.108 → 8.710 %), so no gain fell between the arms |
  | `StageSpec:lebail_tol` 1e-7 | 1e-6, 1e-9 (cap 100 000) | LaB₆ + cBN 0.0002 plain esd; FAP 0.0095 and 0.0005; **cpd-1a 0.76 and 0.82** (corundum a), at 516 and 517 evaluations against 474 | FAP's (5 0 6) share of its pair 0.0010 shipped, 0.048 at 1e-6, 0.0000 at 1e-9 |
  | `LEBAIL_GAP_CYCLES` 5 | 2, 20 cycles, read from one converged Rietveld state | ratio LaB₆ + cBN 0.977/0.978/0.978 (2/5/20); cpd-1a 0.536/0.549/0.626; FAP 0.764/0.980/1.052 | `n_cycles` echoed 2, 5, 20 on every read |

  Every noise twin (every refinable non-zero start ×(1 + 1e-12)) read 0.072 plain esd or less, the largest on PbSO₄'s co-refined `u`, and 2e-6 or less everywhere else. Every fit converged. *Canary*: #1569's co-refined and truth arms, FAP's `lebail_tol` 1e-6, the PbSO₄ pair and FAP's gap read, 210 s, 516 MB, 109 % of 2 cores, at `f148d8abb`; the gap echoed its three cycle counts. *Positive arms*: the harness repeats #1569's La Biso to four digits, 0.3789 and 0.4749, and its background ratios at the hump, 0.971 against 0.966 and 0.987 against 0.983 (the issue's own read of that window may differ in its averaging). The truth arm lands 1.44 esd from the truth at the main draw, inside its two-esd bar, but −2.28 at seed 20261114, outside it. So one draw of three puts even the true background past two esds, and the held arm's excess is read against the co-refined and truth arms on the same draw, where it is 0.086-0.096 Å² at 2e4 counts on all three.

  *How this was reached.* #1569 attaches no harness, and the first version of `group_q.py` built the bullet's reading of it (SRM 660c's instrument, `mccusker_default()`, a 6-term Chebyshev). The triage PR (#1585) said the synthetic had been reproduced with the issue's harness, and the reporter's copy was found and read before the workstation ran. The harness was rebuilt to it, and the bullet "Q, what its bullet left open" records both versions. The first version's six Mac fits are discarded; they also put the held arm above the co-refined one.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: `LEBAIL_CONVERGED_REL` **holds** as evidence that the constant was never reached (the per-pass wording fixed); `lebail_tol` **holds, with a scope caveat**: cpd-1a's Le Bail fit ends at Rwp 22.56 %, above the 16.31 % its Rietveld protocol reaches, so its 0.8 esd may read a fit off its minimum rather than the tolerance (added to the row); `LEBAIL_GAP_CYCLES` **weak as evidence for the value**: every arm is a correct model far below 1.5, so none could change the notable verdict, and more cycles raise the ratio on two families (both added). Q1 read correctly, the one gap the truth arm's −2.28 at seed 20261114, now stated above.

  *Tests.* Fast selection at 2be06afb4 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14849 passed, 281 skipped, 32 xfailed in 6 min 58 s, as a co-tenant, 4.9 GB peak, the same counts as at 19a7c0985; no test added, and only docs changed after it. `tests/test_audit_table.py` and `tests/test_docs_consistency.py` 49 passed, `tests.audit_delta` exit 0, at 2be06afb4 (macOS arm64, worktree `[dev]` venv). `python -m tests.reader_output` exit 0, unchanged against the merge-base with `origin/main` (`bc77a934e`). Full suite not run: no measured number in the package can move (evidence strings, a docs script, a summary).

  *Not done, and why.* The held SNIP on the PbSO₄ neutron histogram WP-1542 named: only the X-ray pattern is on this machine. A reference for the real patterns: none has a truth, so the move's direction is all they give. `LEBAIL_GAP_CYCLES` on a fit whose model is wrong (the pore proxy of its docstring), the only kind of arm that could cross 1.5: not in the table's three families.

  *Questions for the maintainer.* (24) The skill's rule "Under a broad hump, hold SNIP" biases La Biso 8.8 esd high on #1569's synthetic, and its direction repeats on SRM 1976a and FAP at 12-18 esd. Does the rule stand, change or go? That ruling is WP-2008's, with #1569's three proposals; this entry is its measurement. (25) `LEBAIL_CONVERGED_REL` is reached on none of three families: two alternations stop on a pass that raised Rwp, and FAP still gains at five passes. Is a second family that reaches it owed, or does the row's tier rest on WP-1323's one? (26) `lebail_tol` moves cpd-1a's corundum cell 0.76 and 0.82 plain esd either side, past bar 2. Is cpd-1a's Le Bail fit, 6 points of Rwp above its Rietveld one, a family the bar should hold on? (27) `LEBAIL_GAP_CYCLES` is unaudited; at 5 cycles the gap is 0.07 under its 20-cycle value on FAP. What tier, and is a fixed point by cycle 2, measured on one fixture, still the reason for 5?

  *Next:* group O, whose domains and arms are now fixed in "O, its domains and arms" (written this session, nothing run): write `group_o.py`, canary, run; then P, R, S. K waits on the harness and a sparse family, B on its third family, H on #1494.

- **2026-11-16 (group N)** — Of the four hand rows, two hold their claims and two do not. Starting the Le Bail and Pawley intensities a hundred times lower or higher, or with a random shape, changed no answer on FAP, 11-BM NAC or SRM 660c by more than 1.4e-4 esd. Changing the two directions the magnetic flat-axis probe stacks held the same axis and the same answer on #599's case, fitted alone and jointly. Those two claims now have tests. Making arPLS iterate longer or shorter never changed a λ or a background pick on six patterns, but its shipped stop is not converged everywhere: a tighter stop moves SRM 660c's baseline 4.6σ at the λ the selector picks. The finite-difference sizes of the width rows leave every answer alone, but on cpd-1a they set the esd of every width row sitting on its floor, and of W beside them: ten times the size gives ten times the esd, and a tenth of it gives a twelfth. No value moved; two questions go to the maintainer.
  *Done.* In PR #1577. `2017-batch/group_n.py`, `group_n_summary.md`; claims, fits and arms fixed in "N, its four claims and arms" before anything ran (d4ec227ed). New `tests/test_hand_row_claims.py` (`slow`): the intensity seed ×0.01, ×100 and shaped on FAP, NAC and SRM 660c in both modes, and the flat-axis pair turned and redrawn on #599's single and joint cases, each arm with its control (the seeds rewritten counted; the spy on `_flat_rotation_axis` seeing the arm's pair). No `_audit` row: the four are hand rows.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `7a738a47b`: 76 tasks, 33 s on 6 workers, 351 MB peak):

  | Claim | Arms | Largest move against shipped | Its control |
  |---|---|---|---|
  | (1) intensity seed, max(median y_obs, 1) | ×0.01, ×100, lognormal shape, noise; Le Bail and Pawley on FAP, NAC, SRM 660c | 1.4e-4 esd (FAP Pawley `u`, the shape arm); SRM 660c Le Bail bit-identical at ×0.01 and ×100 | 180-2303 seeds rewritten over 5-7 compiles a fit (those a recompile carries are then overwritten by the carry) |
  | (2) `_FLAT_AXIS_TEST_DIRECTIONS` | the pair turned 30° about (1, 2, 3), a pair drawn by `default_rng(2017)`, noise | the same row held (the azimuth), the axis within 1.5e-6°, the moment rows within 1.8e-15 | the spy saw the arm's pair on every call (4 a fit) on the single and joint cases; on the tetragonal cousin no call |
  | (3) `arpls` `max_iter` 50, `tol` 1e-3 | (500, 1e-6), (10, 1e-2) on FAP, NAC, cpd-1a, SRM 660c, Si 640c, SRM 1976a | no λ (`auto_lambda`, `select_arpls_lambda`) and no `auto_background` pick changed; baseline: tight ≤ 0.13σ except SRM 660c at λ 1e5, 4.6σ; tight flipped 1 mask channel on NAC and on Si 640c; loose moved it up to 6.1σ and flipped up to 37 of 3155 channels | `__kwdefaults__` read back at run time |
  | (4) `FLOOR_SEEDS` | every size ×10 and ÷10, noise, on the four protocols | every value within 2.4e-6 esd (FAP bit-identical); on cpd-1a the esds of the six width rows at 0 (`gauss_size`, `gauss_strain` of each phase) and of W (interior, at 0.0106) follow the size: 51 shipped, 511 at ×10, 4.26 at ÷10 (the summary's last list) | 117-254 reads of the table a fit |

  The noise arm, every refinable non-zero start ×(1 + 1e-12), read 3.3e-5 esd or less wherever the patterns are real. #599's patterns are noise-free, so an esd there is a rounding-scale number (1e-18 to 1e-13): the tetragonal cousin's noise arm reads 24.8 esd for a change of 2.2e-16 rad, and the moment rows' absolute change is the reading. On the tetragonal cousin the probe was never called (the column test holds the azimuth), so its arms measured nothing there, as the control says. Every fit converged, and no arm changed a diagnostic code. *Canary*: FAP Le Bail ×1 and ×100, #599 shipped and turned, FAP arPLS loose; 316 MB, 140 % of 2 cores, at `7a738a47b`.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: the intensity seed **weak** as first tested (a uniform factor cancels in a Le Bail partition's ratio, so ×0.01 and ×100 reach only reflections entering at a recompile, and the test left out the shaped arm, the one that reaches every seed); `_FLAT_AXIS_TEST_DIRECTIONS` **holds, on a narrow base** (one synthetic structure; no arm could fail, since the draw rejects every special direction); arPLS **weak** (nothing shows the tight arm is itself converged); `FLOOR_SEEDS` **holds** as a finding, which confirms WP-2002's reading of it as a numerical setting (B10) rather than overturning a claim. It found seven wordings to fix: the noise floor (3.3e-5, not 5e-6), per-row esds the summary did not print, ÷10 giving a twelfth, the tetragonal case's missing spy calls, the carried seeds in the count, LaB₆ against SRM 660c in the test docstring, and the single mask channels the tight arm flipped. *Author:* the shaped arm is in the test, the summary prints the width rows whose esd moved, and all seven wordings are fixed; questions (22) and (23) take its reframing (W is interior; drop "converged").

  *Tests.* Fast selection at 19a7c0985 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14849 passed, 281 skipped, 32 xfailed in 6 min 39 s, as a co-tenant, 5.2 GB peak. The same counts as at ea522617e: the new `tests/test_hand_row_claims.py` is `slow`, so the fast selection does not see it; run alone it is 8 passed in 22.7 s (macOS arm64, worktree `[dev]` venv, serial). `tests/test_audit_table.py` and `tests/test_docs_consistency.py` 49 passed, `tests.audit_delta` exit 0, at 19a7c0985 (macOS arm64, worktree `[dev]` venv). Reader output unchanged (exit 0); ruff clean; Vale 0 errors. Full suite not run: no measured number in the package can move (a docs script, its summary, a slow test).

  *Not done, and why.* A protocol fit refitted on a changed pick (claim 3): no pick changed, so there was nothing to refit. A second real uniaxial family for claim 2: the only flat rotations on disk are synthetic.

  *Questions for the maintainer.* (22) `FLOOR_SEEDS` sets esds on cpd-1a: the six Gaussian width rows on their floor at 0, and W, interior at 0.0106 and sharing the Gaussian width with them, read 51 at the shipped sizes and ten times that at ten times the size. The answer does not move. WP-1929 keeps a row on its bound in the matrix with a marginal esd, and WP-2002 read this constant as a numerical setting (B10). With the step setting the esd there, should those rows, and W through them, report an esd at all, and does `FLOOR_SEEDS` need its own audit row? (23) arPLS's shipped stop leaves SRM 660c's baseline 4.6σ from the (500, 1e-6) arm's at λ 1e5, the selector's pick, though no pick changes; `rietx.background.arpls` is public and `select_arpls_lambda` returns its scores, so a caller reading that baseline sees the move. Does the claim stand on the picks, or should the stop be tightened, which would move the baselines the selector scores?

- **2026-11-16 (group M)** — The two starting values the closing stage was approved to make harmless are harmless only because of it. Every atom's Biso was started at 0.5 Å² and at 1.5 on four real patterns: FAP, 11-BM NAC, cpd-1a and SRM 660c. With the closing stage, three answers agree to 0.009 esd and cpd-1a differs by 15.6, as its strict xfail says. Without the closing stage, FAP moves 0.12 esd and SRM 660c 0.20, past the 0.1 bar, while NAC stays at 0.008. The λ/2 harmonic's starting weight was tried on the synthetic neutron corundum, the only pattern with a harmonic that an audit may use. Seeds of 0.001 and 0.3 against the shipped 0.01 agree to 0.015 esd with the closing stage. Without it they move 0.26-1.44 esd. The 0.015 is five times the 0.003 the start test's docstring quoted, though still well inside its bar. No value moved and no tier changed; the two rows now say what was measured, and three questions go to the maintainer.
  *Done.* In PR #1577. `2017-batch/group_m.py`, `group_m_summary.md`; starts and arms fixed in "M, its starts and arms" before anything ran (d0cc115bf). Evidence rewritten on `schemas.structure.BISO_SEED` and `schemas.instrument.HARMONIC_WEIGHT_SEED`; tier, value, grounds and approval unchanged. BISO_SEED's evidence named zincite's `lor_strain` for cpd-1a's 15.68 and called LaB₆ a strict xfail; the row is fluorite's (`phases.2`, as the test's docstring says), and LaB₆ has passed since WP-2012, so both are corrected. `tests/test_staged_start_invariance.py`'s docstring now carries the harmonic re-reading beside the old one.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `ec68ea97e`: 48 fits, 24 s on 6 workers, 501 MB peak):

  | Start | with the closing stage | without (`closing_window_tol=None`) | the closing stage's own move |
  |---|---|---|---|
  | Biso 1.5 against 0.5, FAP | 0.00003 | 0.119 (Ca2 Biso) | 0.91 (`lor_size`) |
  | NAC with CaF₂ | 0.000003 | 0.008 (X) | 0.16 (X) |
  | cpd-1a | 15.6 (fluorite `lor_strain`) | 14.8 (the same) | 0.90 (zincite scale) |
  | SRM 660c | 0.009 (X) | 0.199 (La Biso) | 0.21 (X) |
  | harmonic seed 0.001 or 0.3 against 0.01, true weight 0 | 0.014 | 0.42, 1.15 (O Biso) | 1.14 |
  | true weight 0.003 | 0.015 | 0.26, 0.69 | 0.81 |
  | true weight 0.05 | 0.004 | 0.99, 1.44 (scale) | 1.54 |

  Every 1e-12 noise arm read 2e-6 esd or less. Every fit refined its Biso rows, so the start was never the answer, and no protocol family declares a harmonic, so the four cannot reach the harmonic seed. FROZEN_COMPILE_STALE fires on seven of the twelve harmonic fits without the closing stage and on none with it. The refined λ/2 weight sits 0.4-2.5 esd from the truth on every arm. *Canary*: FAP without the closing stage, both Biso starts, 8 s, 220 MB, 130 % of 2 cores, at `ec68ea97e`. *Positive arm*: under the closing stage the harness repeats the start test's FAP, NAC and LaB₆ readings, and cpd-1a's 15.68 as 15.6. The harmonic's quoted 0.003 is not repeated: it reads 0.015 at a true weight of 0.003, and 0.004 at 0.05, both on the workstation and on this Mac (macOS arm64, worktree `[dev]` venv). So either the protocol drifted since 2026-10-23 or the quote was from another construction. The drift was not traced.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: `BISO_SEED` **holds** (four unrelated real families; the start dependence without the closing stage shown on two), `HARMONIC_WEIGHT_SEED` **weak** (one self-drawn synthetic against grounds naming three families; the positive arm missed its 0.003; the uncovered fits flag themselves). It found four wordings to fix: a platform claim the summary did not show, a 5e-7 floor that is 5.9e-7, "invariant behind the closing stage only" quoted after NAC's 0.008, and the test docstring's stale 0.003. *Author:* all four fixed (eab2c76bf). The Mac readings are in this entry, the floor reads 6e-7, the row says start-dependent on FAP and LaB₆, and the docstring carries both readings.

  *Tests.* Fast selection at ea522617e on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14849 passed, 281 skipped, 32 xfailed in 6 min 45 s, as a co-tenant, 5.0 GB peak. The same counts as at c486ea466; no test added (the start test's docstring changed, not its assertions). `tests/test_audit_table.py` and `tests/test_docs_consistency.py` 49 passed, `tests.audit_delta` exit 0 (24 rows changed on the branch), at d4ec227ed (macOS arm64, worktree `[dev]` venv). Reader output unchanged (exit 0); ruff clean; Vale 0 errors. Full suite not run: no measured number in the package can move (evidence strings and a docstring).

  *Not done, and why.* A second harmonic family. The only real one on disk is Nd₂Ru₂O₇'s neutron pattern, held out until the milestone closes, and drawing a second synthetic is the maintainer's to ask for.

  *Questions for the maintainer.* (19) Both rows' grounds owe "the start without the closing stage on three families". Without it the Biso start is not invariant on FAP or SRM 660c. Do the rows stay at tier 3 on "invariant behind the closing stage", which is the only way a default fit runs? (20) `HARMONIC_WEIGHT_SEED` has one family, synthetic and drawn by the package's own forward model. Does that close it, as the 2026-11-05 ruling closed group A's barely reached constants, or is a second harmonic family owed? (21) The start test's quoted 0.003 now reads 0.015 on two platforms, inside its 0.1 bar. Is that drift to accept, or should it be traced before the row is accepted?

- **2026-11-16 (groups K and L)** — Group K could not run. Its families are a table of 119 fits, whose harness is not in the tree and whose raw rows are gone, and a sparse-count pattern that nothing names. Group L ran the magnetic solve on four real patterns from three laboratories: Cr₂WO₆ at 4 K and at 150 K, LaMnO₃ at 50 K and Ba₂FeSbSe₅ at 1.5 K. On each, three of its counts were moved either way. No arm changed what the solve concluded. The count of distinct minima was never reached, because every class ran a single start. The number of candidate k's kept changes only how long the reported list is. The number of k's given a full trial matters only on Ba₂FeSbSe₅, the case it was set on. Cutting it to one drops the runner-up k's trial, the pick stays, and the solve runs in a fifth of the time. No value moved and no tier changed; the three rows now say what was measured, and three questions go to the maintainer beside K's.
  *Done.* In PR #1577. K: why it cannot run, in § What each group inherits, "K, read 2026-11-16" (e2174883f). L: `2017-batch/group_l.py`, `group_l_summary.md`; solves and arms fixed in "L, its solves and arms" before anything ran (e2174883f). Evidence rewritten on `strategy.magnetic.SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K` and `SOLVE_K_TRIALS`; tier, value, grounds and approval unchanged.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `1f2b58ab2`: 32 solves, 571 s on 8 workers, 235 MB peak; Ba₂FeSbSe₅'s solve 551-565 s, the others 2-40 s):

  | Row | What moved |
  |---|---|
  | `SOLVE_MINIMUM_RTOL` 1e-5, 1e-3 | nothing, and unreached: every class trial on all four ran one start (each solve names one site), so no two Rwp were compared |
  | `SOLVE_TOP_K` 2, 4 | only the reported list's length, on all four (the k = 0 route cuts it too); the added fourth k matches 0 and 5 satellites against the top-ranked k's 2 and 11; verdict, pick and every trial identical |
  | `SOLVE_K_TRIALS` 1 | on Ba₂FeSbSe₅ only: the (½,½,0) trial (best ΔBIC 47.9) goes, the pick (½,0,½), class 11.55, ΔBIC 143.9, and every class trial stay; 114 s against 556 s |
  | `SOLVE_K_TRIALS` 3 | nothing: no third k inside the offset margin on any solve |

  The `repeat` arm, the shipped solve run again, matched it on all four to every digit recorded: a solve builds its own starts, so a 1e-12 nudge has no single start to act on. Cr₂WO₆ 4 K ranks 58.395 first and LaMnO₃ 62.448, as their acceptance suites state. Cr₂WO₆ 150 K is "nothing to solve" on every arm. Ba₂FeSbSe₅'s pick is the published k and class `test_magnetic_series` quotes. All of it is development data, and Ba₂FeSbSe₅ is the pattern `SOLVE_K_TRIALS` was set on. *Canary*: Cr₂WO₆ 4 K shipped and `top_k` 2, 9 s, 193 MB, 138 % of 2 cores, at `1f2b58ab2`.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: `SOLVE_MINIMUM_RTOL` **weak** (unreached because each solve names one site; the two-site synthetic case in `test_magnetic_solve` runs three starts but asserts nothing at 1e-4; the constant also words the "distinct minima" caveat), `SOLVE_TOP_K` **weak** (only the list's length moves; its other reach, bounding the walk past refused k's, was not exercised), `SOLVE_K_TRIALS` **holds on its one family, weak beyond it** (the runner-up's ΔBIC is the only evidence that k was tested; 4.9× the wall time for the same pick). It also found two faults in the first draft: the k = 0 route does cut the list, and the "every class trial kept" claim was not in the summary. *Author:* both are fixed. The rows, and the summary's two new columns (ranked k, class trials compared), now say it. The compiled tier was on, where the ramp test runs numpy, so the Ba₂FeSbSe₅ nuclear fit is built as there, not bit for bit.

  *Tests* (groups I, J and L). Fast selection at c486ea466 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14849 passed, 281 skipped, 32 xfailed in 9 min 8 s, as a co-tenant, 5.3 GB peak. Against the 14850 and 280 at e83ad62e2, one test moved from pass to skip: `test_skill.py::test_no_change_grows_a_capped_file_past_its_budget`, "no origin/main to measure against", which is the workstation clone's missing ref, not this branch. No test added. `tests/test_audit_table.py` 23 passed, `tests.audit_delta` exit 0 (22 rows changed on the branch), `tests/test_docs_consistency.py` 26 passed (macOS arm64, worktree `[dev]` venv). Reader output unchanged (exit 0); ruff clean; Vale 0 errors. Full suite not run: no measured number in the package can move.

  *Not done, and why.* K, above. For L: a solve that runs several starts of one class, a solve where a fourth k is tried or wins, and a second family with two k inside the offset margin. None is on disk among real patterns, and building synthetic ones is the ruling's to ask for.

  *Questions for the maintainer.* (16) K: name the sparse-count family, and say whether the 119-fit reach table should be rebuilt, or whether K is ruled on WP-2086's numbers as they stand. Comparing against background-subtracted Rwp or Rwp/Rexp is itself a new threshold. (17) `SOLVE_MINIMUM_RTOL` and `SOLVE_TOP_K`: close them as the 2026-11-05 ruling closed group A's barely-reached constants, on named synthetic cases (the two-site case asserting at 1e-4; a case whose first k's refuse)? (18) `SOLVE_K_TRIALS` is reached by one real family, the one it was set on. Does the rare-feature clause still cover it, or is a second family with two k inside the margin owed?

- **2026-11-16 (group J)** — Pawley refines the Kα2/Kα1 ratio as Rietveld does; Le Bail does not quite. On three laboratory patterns, SRM 660c, the FAP tutorial and the SRM 1976a plate, each fitted three ways under its own protocol, Pawley's ratio landed within 0.34σ of Rietveld's every time. Le Bail's agreed on SRM 660c, but read lower on the other two: 1.9σ on FAP and 2.8σ on SRM 1976a. Measured in plain esds those gaps are 4.3 and 11. On SRM 660c the 1.7σ gap that WP-2002 found no longer appears. Rietveld and Pawley repeated their old numbers there to 1e-4, but Le Bail moved from 0.5224 to 0.5133. Its partition has run to a tolerance since WP-1542, which may be why, though that was not checked. Freeing the ratio moved no cell by more than 0.59 esd in any mode. No independent reference for the ratio exists here, since a fitted doublet weight absorbs profile shape. No default moved; the readings now sit in `mode_fixed_path`'s docstring beside SRM 660c's, and two questions go to the maintainer.
  *Done.* In PR #1577. `2017-batch/group_j.py`, `group_j_summary.md`; fits and arms fixed in § What each group inherits, "J, its fits and arms", before anything ran (9a2c36391). No `_audit` row: the change is the force-fix lifted in `refine.mode_fixed_path`, so the readings went to its docstring.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `fc2d89c6d`: 27 fits, 31 s on 4 workers, 523 MB peak). Kα2/Kα1 with its reported esd:

  | Pattern | Rietveld | Pawley (from Rietveld) | Le Bail (from Rietveld) | cell, ratio free against held |
  |---|---|---|---|---|
  | SRM 660c (graphite monochromator) | 0.5125 ± 0.0048 | 0.5146 ± 0.0036 (0.34σ) | 0.5133 ± 0.0029 (0.13σ) | 0.38-0.59 plain esd |
  | FAP | 0.4757 ± 0.0060 | 0.4750 ± 0.0046 (0.08σ) | 0.4609 ± 0.0047 (1.93σ) | 0.07-0.35 |
  | SRM 1976a (cell held) | 0.4753 ± 0.011 | 0.4755 ± 0.0047 (0.01σ) | 0.4430 ± 0.0039 (2.84σ) | no cell row |

  σ is the combined reported esd, √(e₁² + e₂²), the measure of WP-2002's 1.7σ. Two fits to the same counts are not independent, so the plain-esd gaps (4.3 and 11 for Le Bail on FAP and SRM 1976a) are the sharper reading. The noise arm moved at most 4.8e-4 plain esd. On FAP Le Bail's Rwp, 0.0996, sits above Rietveld's 0.0922, which a free partition should not allow. That suggests the partition stopped short, though it is unexplained. Every arm sits 2.3-14.5 esds from 0.5, Rietveld included. FAP and SRM 1976a read about 0.475, below 0.5, against `KA2_RATIO`'s comment that measured ratios run a few percent above it. SRM 1976a's TOPAS file models CuKα with five lines against rietx's two. All of it is development data.

  *Positive arm*: SRM 660c repeats WP-2002's Rietveld (0.5126 ± 0.0048) and Pawley (0.5145 ± 0.0036) readings to 1e-4, and not its Le Bail reading (0.5224 ± 0.0033). By the WP's own test, fixed before running, Le Bail's reading here is not 2026-10-20's, and what changed, the tree or the protocol, was not identified. *Canary*: SRM 1976a Rietveld and Le Bail, 9.6 s, 239 MB, 140 % of 2 cores, at `fc2d89c6d`.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: lifting the force-fix **holds for Pawley** (the doublet is a shape the intensities cannot absorb, and Pawley's agreement bears it out) and is **weak for Le Bail** (a real gap, larger in plain esd, a ratio that moved with the partition's settings, and an Rwp above Rietveld's on FAP). 0.5 **fails as the owed "tabulated ratio"**: it is the 2j+1 seed, and an effective doublet weight has no instrument-independent reference. The protocol is **weak**: the modes are compared on the same data, which verifies and validates nothing, SRM 1976a's cell is held, and the wavelength the change also unlocked was not freed. The docstring's numbers are right. *Author:* the docstring is reordered so the force-fix's end still reads as 2026-10-20, FAP is called the tutorial pattern it is, and the plain-esd gaps are stated. Nothing goes to the skill or the report: rietx's own runs are the only evidence.

  *Not done, and why.* The wavelength freed on a second standard. Le Bail on SRM 660c before and after WP-1542's merge (c081aa681), and on FAP and SRM 1976a with a tighter partition tolerance, which would tell a convergence artefact from a bias. These are diagnostics chosen after seeing the answer, so they are listed, not run. An SRM 1976a arm with the cell free.

  *Questions for the maintainer.* (14) Le Bail reads the Kα2/Kα1 weight 4.3 and 11 plain esds below Rietveld and Pawley on FAP and SRM 1976a, and its FAP Rwp is above Rietveld's. Keep the lines free in Le Bail, or file the gap (and the FAP Rwp) as an issue for the partition first? (15) The "tabulated ratio" this WP owed does not exist for a fitted doublet weight, which absorbs profile shape. Does the agreement between modes close J, or is a reference owed in another form (a known-answer synthetic, say)?

- **2026-11-16 (group I)** — Removing the default limits on the zero shift and the specimen displacement changed nothing on three laboratory flat plates, because none of their fits came near the old limits. The zero was freed beside the displacement on FAP, SRM 660c and SRM 1976a, over each protocol's range and over a narrower one, with and without the pre-1.10 limits (±0.5°, ±1 mm). The largest zero was 0.34° and the largest displacement 0.69 mm, and each fit agreed with its bounded twin to 5e-6 esd. The same harness repeated NAC's case, where the bound did bind: 1097 ppm bounded against 5111 unbounded. What the run did find is about the freedom itself, not the bound. Freeing the zero beside the displacement, as the `lab_bragg_brentano` preset does, moved the cell 48-1000 ppm from the fit that held the zero. The reported esd covered that within three esds on half the fits. On SRM 660c over 20-85° the cell sat 984 ppm from its CIF value at 6.5 esds. So the reference page's sentence that the esd "grows to show it" fails on three of six. No default moved; the measurement is now beside NAC's in the schema comment and the reference page, and two questions go to the maintainer.
  *Done.* In PR #1577. `2017-batch/group_i.py`, `group_i_summary.md`; fits and arms fixed in § What each group inherits, "I, read 2026-11-16" and "I, its fits and arms", before anything ran (e00debe7a). The script was amended after the first run to record the reported esd beside the plain one and to tabulate the walk (7dbbfced3, rows bit-identical). No `_audit` row: the removal is the default of four `Parameter` seats, so its evidence went to the comment above `Geometry.sample_displacement` and to `docs/docs/reference/instrument.md` § position corrections (two sentences each, a22a94a59 and after).

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `7dbbfced3`: 27 fits, 19 s on 4 workers, 349 MB peak). Narrow range: from the protocol's low end to where the smallest eigenvalue of the unit-column Gram of {1, cos θ, tan θ} falls to NAC's capillary trio over 2-24°, 1.6e-5: FAP 15-70.6°, SRM 660c 20.3-84.6°, SRM 1976a 20-90.4°.

  | Family, range | bounded against free | free against zero held: cell walk (reported esds) | free cell from reference (reported esds) | codes on free |
  |---|---|---|---|---|
  | FAP full | bit-identical | −508 ppm (4.5) | −424 ppm (3.8) from GSAS | `FLAT_DIRECTION`, `HIGH_CORRELATION` |
  | FAP 15-71° | bit-identical | −661 ppm (2.8) | −582 ppm (2.5) | both |
  | SRM 660c full | bit-identical | −48 ppm (3.6) | −23 ppm (1.8) from the CIF | `HIGH_CORRELATION` |
  | SRM 660c 20-85° | bit-identical | −1000 ppm (6.6) | −984 ppm (6.5) | both |
  | SRM 1976a full | bit-identical | −340 ppm (1.3) | −64 ppm (0.24) from the TOPAS file's cell | both |
  | SRM 1976a 20-90° | 4.6e-6 esd, no bound reached | −444 ppm (0.49) | −111 ppm (0.12) | both |
  | NAC 2-24° (positive arm) | 11.8 esd; `BOUND_HIT` on the along-beam offset | −5131 ppm (2.0) | −5111 ppm (2.0); bounded −1097 | both |

  Free zero −0.022° to −0.344°, displacement −0.12 to −0.69 mm (SRM 660c's CIF: −0.079 mm; the zero-held fit −0.079), SRM 1976a's transparency at most 1.1e-4 against the old ceiling of 0.05. The noise arm moved 1.4e-7 to 1.8e-5 esd. GSAS's FAP cell is a fit with the zero held, so it verifies the zero-held arm and measures drift for the free one; SRM 660c's CIF cell validates; the TOPAS file holds SRM 1976a's cell, so that reference is read beside the bar and grades nothing. All of it is development data.

  *Canary*: SRM 1976a over 20-90° free and bounded, 10 s, 224 MB, 136 % of 2 cores, at `89efda0b5`, Rwp equal to the Mac's run to seven digits.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: the removal **holds** (a prior about the mount is the caller's and the dissenter is named; but the flat plates are a null result, adding no family where the removal changes anything). The protocol is **weak**: NAC's trio has no cell column while the flat-plate trio has one, so the matched eigenvalue makes "narrow" less degenerate than NAC (walks of 444-1000 ppm against 5131), and the Gram weighs every channel alike. The added sentences **hold**, every number checked. The reference page's "the cell's esd grows to show it" **fails as written**: three of six flat-plate rows walk past three esds, and `FLAT_DIRECTION` did not fire on SRM 660c's full range. *Author:* the reference page now says its 5e-6 is a plain esd. The existing sentence was not reworded: whether to reword it or to change the esd or the flag is the maintainer's (question 12).

  *Not done, and why.* A flat plate on which an old bound binds (a shorter range, or a mount known to be displaced): none of the three reached one, and a range chosen after seeing that would not be evidence. Groups J to S not started in this entry.

  *Questions for the maintainer.* (12) The reference page says that where a scan cannot separate a position error from the cell, `FLAT_DIRECTION` fires and the cell's esd grows to show it. With the zero freed beside the displacement, as `lab_bragg_brentano` does, the walk from the zero-held fit is 3.6-6.6 reported esds on three of six flat-plate fits, and SRM 660c over 20-85° lands 984 ppm (6.5 esds) from its CIF cell. Reword the sentence to what was measured, or is the esd or the flag owed a change? (13) Group I shows the removal moves nothing on three flat plates because no bound binds; is a flat plate where one binds owed before the removal is closed, or does the null result close it?

- **2026-11-16 (groups E and F)** — Two more groups measured, and both found something the rows had not said. The TRF solver's two stopping tolerances barely matter: loosening either to SciPy's own 1e-8 left two of three fits bit-identical and moved Si SRM 640c 0.005 esd. The bound test's two thresholds worked on a third family, cpd-1a: all 20 binding cases fired. But at a loose stop (ftol 1e-3) the angle half reads three of five free optima above its 1e-4 threshold, and only the distance half keeps them silent. In `auto_background`'s pick, the choice of knot step is not inert, as its grounds say it is. On Si SRM 640c, whose Kapton capillary puts a real hump under the pattern, the shipped 3° knots agree with a fit that subtracts the measured empty capillary, while 8° knots move Biso 3.0 esd away from it. The air-term choice moves the eight weighed cpd-1 mixtures up to 0.17 esd and 0.02 wt %. No value moved and no tier changed; the eight rows now say what was measured, and three questions go to the maintainer.
  *Done.* In PR #1577. `2017-batch/group_e.py`, `group_e_summary.md`, `group_f.py`, `group_f_summary.md`; protocols fixed in § What each group inherits, "E, its starts and arms" and "F, its patterns and arms", before anything ran (5dde13f3a, f3857c487; E's bound-case start detail amended before its first run). Evidence rewritten on `least_squares.GTOL`, `XTOL`, `staged.BOUND_HIT_ESD_FRAC`, `BOUND_HIT_COS_MIN`, `auto.HUMP_TRIGGER`, `AIR_SCATTER_TRIGGER`, `_KNOT_STEP_HUMPY_DEG`, `_KNOT_STEP_SMOOTH_DEG`; tier, value, grounds and approval unchanged.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `998b47034`; E: 15 TRF fits and 40 one-path bound stages, 40 s on 4 workers, 397 MB peak; F: 46 fits, 71 s on 4 workers, 422 MB, rows bit-identical to an earlier run at `2660867ee`):

  | Row | What moved |
  |---|---|
  | `GTOL` 1e-8 | nothing: bit-identical on cpd-1a, corundum (Stephens) and Si SRM 640c; no solve stops on gtol at 1e-12 |
  | `XTOL` 1e-8 | Si SRM 640c zero shift 0.0049 plain esd at 0.90× the evaluations; cpd-1a and corundum unreached; corundum's noise arm 0.10 esd |
  | `BOUND_HIT_ESD_FRAC` | 20 binding cases on cpd-1a (five paths × ftol 1e-9…1e-3): largest gap 5.7e-5 esd, 174× under 0.01, all fired |
  | `BOUND_HIT_COS_MIN` | binding |cos| 0.165-0.472; free-optimum controls ≤ 1.6e-7 at ftol ≤ 1e-6, 5.7e-5 at 1e-4, 1.8e-3-3.3e-3 on three of five at 1e-3; none fired |
  | `HUMP_TRIGGER`, the knot steps | Si SRM 640c (score 0.099): 3° within 0.43 esd of the measured-blank arm on λ, zero and Biso; 8° moves Biso 3.0 esd from it and `lor_size` 4.0 esd from the pick. cpd-1a…1h (0.19-0.36): 8° moves 0.20-1.21 esd, at most 0.19 wt % |
  | `AIR_SCATTER_TRIGGER` | gains 0.067 (Si) and 0.245-0.817 (cpd-1): a flip moves cpd-1 0.049-0.17 esd (six of eight past 0.1), at most 0.022 wt %; Si 4e-6 esd |

  cpd-1a and qarr corundum share a laboratory, instrument and phase, so E's tolerances saw two families, and only Si SRM 640c reached `XTOL`. The Si references are XND's λ (verifies) and a rietx fit with the blank measured; the weighed fractions validate. All of it is development data. `AIR_SCATTER_UNDECLARED` fired on every arm with the air term off and on none with it on, including the shipped pick on Si SRM 640c and cpd-1c, where declaring the term moved 4e-6 and 0.049 esd.

  *Canaries*: E, cpd-1a and Si SRM 640c shipped under TRF, 16 s, 353 MB, 134 % of 2 cores; its bound case raised on the first run (the bound was set before the start, which the `Parameter` validator refuses), fixed in 6d1f9d7f7 and re-run, 6.5 s, 191 MB, firing `BOUND_HIT` at gap 2.6e-15 esd. F, cpd-1a and Si SRM 640c pick, 14 s, 339 MB, 139 % of 2. The first F run read QPA through the wrong field names (fixed in 998b47034, with E's; D's raw rows carry none for the same reason), so it was run again.

  *Tests.* Fast selection at e83ad62e2 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14850 passed, 280 skipped, 32 xfailed in 9 min 44 s, as a co-tenant, 6.7 GB peak; it covers group D's row too. No test added. `tests/test_audit_table.py` 23 passed, `tests.audit_delta` exit 0 (19 rows changed on the branch), `tests/test_docs_consistency.py` 26 passed (macOS arm64, worktree `[dev]` venv). Reader output unchanged (exit 0). Full suite not run: no measured number in the package can move.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only), condensed: `GTOL` **weak** (unreached; two families; a synthetic case owed), `XTOL` **weak** (one family reached), `BOUND_HIT_ESD_FRAC` **holds** (the controls cannot test it; the early-stop side rests on one synthetic), `BOUND_HIT_COS_MIN` **weak** (fails at ftol 1e-3 inside the domain WP-1434 claimed; the near-limit free optimum not built), `HUMP_TRIGGER` **weak** (two numbers misquoted, the grounds' 0.8 esd now contradicted, one real hump), `_KNOT_STEP_HUMPY_DEG` and `_KNOT_STEP_SMOOTH_DEG` **weak** (only 3° against 8°; the smooth step unreached where it applies), `AIR_SCATTER_TRIGGER` **holds** (but `AIR_SCATTER_UNDECLARED` does not tell these fits apart). *Author:* the misquotes are corrected (`lor_size`'s 4.0 esd is against the pick, not the blank; the cpd-1 range is 0.20-1.21) and every point of fact is now in the rows. Grounds were not edited: they carry approvals.

  *Not done, and why.* A synthetic case reaching `GTOL`; `XTOL` reached on two more families; an early-stopped binding case on a real family; a free optimum within 0.01 esd of its limit at ftol 1e-4 and 1e-3; a second real amorphous hump with its blank; 2° and 5° knots; a real pattern under 0.05 for the smooth step. Groups I to S not started.

  *Questions for the maintainer.* (9) `HUMP_TRIGGER` and the knot steps were kept as a pick because no near-trigger choice moved a value past 0.8 esd; on Si SRM 640c the other step moves Biso 3.0 esd from the measured-blank fit. Do the grounds stand, or does the pick need a second real hump first? (10) `BOUND_HIT_COS_MIN`: at ftol 1e-3 three free optima read 18-33× over it and only the distance half keeps them silent. Is the claimed domain ftol ≤ 1e-6, or is the near-limit free optimum owed? (11) `AIR_SCATTER_UNDECLARED` fired on the shipped pick of Si SRM 640c, where declaring the term moved nothing: re-measure that code's thresholds (its row is still `unaudited`)?

  *Next.* (1) Groups I to S in order. (2) Group H's removal once #1494 merges.

- **2026-11-16 (group D)** — The size at which a joint fit stops building one dense Jacobian and keeps it in per-pattern blocks makes no difference to the answer on real data. Two real joint fits, the three cpd-1 round-robin mixtures together and seven frames of the CuCr₂O₄ ramp, were each run both ways, and on the synthetic library its test already uses. Every refined number agreed within 0.005 esd, which is exactly the scatter a 1e-12 nudge to the start produces, with the same Rwp, the same rows measured and the same diagnostics. None of these fits is large enough for the size rule to choose the blocked path by itself (110 MiB at most against 256), so only the forced arm reached it. No value moved and no tier changed; the row now says this and that a third real joint family is still owed.
  *Done.* In PR #1577. `2017-batch/group_d.py` and `group_d_summary.md`; fits, arms and reads fixed in § What each group inherits, "D, its fits and arms", before anything ran (commit bc89a5054). Evidence rewritten on `rietx.optimize.blocked.DENSE_JACOBIAN_MAX_BYTES`; tier, value and approval unchanged. Groups E and F fixed in the same section before running (5dde13f3a, f3857c487), scripts `group_e.py` and `group_f.py`.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `bf012fbc5`; 12 joint fits, 193 s on 4 workers, 864 MB peak):

  | Fit | Joint solves | Largest dense J | blocked vs dense, plain esd | noise arm | esds, largest relative difference (noise) |
  |---|---|---|---|---|---|
  | library20 (synthetic) | 6 | 43.6 MiB | 8.5e-6 | 1.7e-5 | 2.9e-5 (4.4e-6) |
  | cpd-1a, -1b, -1c joint (qarr) | 9 | 11.3 MiB | 3.6e-6 | 3.5e-6 | 7.0 % on W (8.5 %) |
  | CuCr₂O₄ ramp, 7 frames ≤ 122.7 K (11-BM) | 6 | 110.0 MiB | 0.0050 | 0.0050 | 0.068 % (0.057 %) |

  Rwp equal to nine digits and the diagnostic codes equal on every pair; the same rows carry an esd in both layouts; the `rule` arm took dense on all three and is bit-identical to it. Both real families are development data, and the reference is rietx's own dense answer, so this verifies and validates nothing beside it: the coldest frame's cell reads −19, +110 and −114 ppm against Suchomel et al. (2012) Table I under both layouts. The cpd-1 weighed fractions were fixed as a reference but the harness read the wrong field names, so they were not recorded (fixed in the script; the fractions are functions of rows that agree to 3.6e-6 esd).

  *Canary*: library20 dense and blocked, 11 s, 340 MB, 134 % of 2 cores, commit bf012fbc5; blocked against dense 8.5e-6 esd, the row's cited test repeated.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only) on the row as first written: **weak** — the esds and which rows carry one were not compared, though `blocked.py` names the near-cut case where the two layouts can discard different directions; development data not stated; the layout reaches no record field; the fractions read was broken. *Author:* the esd comparison was added from the raw rows (no new fits) and the row states it, the development data and the unproduced near-cut case; the script is fixed. The record field is a design change, so it is question (8).

  *Not done, and why.* A third real joint family (only Nd₂Ru₂O₇ is on disk, evidence for no audit before the milestone closes) and the near-cut case.

  *Questions for the maintainer.* (7) Group D: two real joint families and the synthetic case agree to the noise floor; does D close on them, or is a third joint family owed, and from where? (8) `LSQOutcome.jacobian_layout` reaches no field of the result or history: should the layout a joint fit took be recorded?

  *Next.* Groups E and F (the entry above).

- **2026-11-16 (group C)** — Of the seven constants of the conjugate-gradient solve, four can no longer be reached by any fit: they live in the original BCCG routine, which the package stopped calling in WP-1953. The other three steer the step the solver takes on large Pawley problems, and only two of the three families are large enough to use it. There, loosening `_PCG_TOL` a hundredfold sent FAP to a different answer while every stage still said "converged", its c axis 1.29 esds away and ten times further from GSAS's. The shipped value and a tighter one agree. No value moved and no tier changed. The four unreachable rows now name the synthetic test that does reach them, and the other three say what was reached and what is still owed. Group B did not run: its third Stephens family is named nowhere, so that is a question for the maintainer. Group D cannot run as fixed, since its constant is read only by joint fits.

  *Done.* In PR #1577. `2017-batch/group_c.py` and `group_c_summary.md`; starts, arms and reads fixed in § What each group inherits, "C, its starts and arms", before anything ran (commit 174276095). Evidence rewritten on the seven `rietx.optimize.bccg` rows `_PCG_TOL`, `_PCG_BUDGET_PER_VARIABLE`, `_CAUCHY_ARMIJO`, `_CONVERGED_FRACTION`, `_CONVERGED_RUNS`, `_SMALL_FACTOR`, `_SMALL_RUNS`; tier, value and approval unchanged. Group B's missing family and group D's unreachable families are written into § What each group inherits.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, one kernel thread, at `174276095`; 48 Pawley fits, 30 s for the last 46 on 8 workers, 511 MB peak):

  | Family | Solve columns past the cut (Pawley intensities) | Shipped Rwp | Noise arm, plain esd | Reached |
  |---|---|---|---|---|
  | FAP | 343 (329), 37 projected-CG solves | 0.0786244 | 1.75e-6 | `_PCG_TOL`, `_PCG_BUDGET_PER_VARIABLE` |
  | NAC with CaF₂ | 154 (140), 35 solves | 0.0751638 | 2.5e-6 | `_PCG_TOL` (under 2e-7 esd) |
  | cpd-1a | never past 128 (111) | 0.1643022 | 2.2e-6 | none |

  | Constant | Arms | What moved |
  |---|---|---|
  | `_PCG_TOL` | 1e-8, 1e-12 | 1e-8: FAP's c 1.29 plain esd, 4.9e-5 Å from GSAS's Rietveld c against 4.7e-6 (a moved 4.2e-5 against 4.8e-5), Rwp 0.0806 against 0.0786, six stages `converged`. 1e-12: FAP 0.026 esd (background 0.103) at 1.46× the evaluations. NAC under 2e-7 esd both sides |
  | `_PCG_BUDGET_PER_VARIABLE` | 1, 4 | FAP 0.007 esd (background 0.036) at 1.05× and 1.10× the evaluations; NAC bit-identical |
  | `_CAUCHY_ARMIJO` | 1e-5, 1e-3 | bit-identical on all three |
  | `_CONVERGED_FRACTION`, `_CONVERGED_RUNS`, `_SMALL_FACTOR`, `_SMALL_RUNS` | 1e-5 and 1e-3, 2 and 5, 100 and 400, 3 and 12 | bit-identical on all three; `bccg.solve` called 0 times in 48 fits, the spy counting the one call added after each fit |

  GSAS's cell is a Rietveld answer under another protocol, so against a Pawley fit it reads drift, not truth; FAP and NAC are development data, and WP-1953 set the two reached constants on them. FAP's Pawley Rwp matched the Mac's run to seven digits.

  *Canary*: FAP and NAC at the shipped constants, 11.5 s, 330 MB, 125 % of 2 cores, commit 174276095.

  *Tests.* Fast selection at 0522460d8 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup -m "not slow"`): 14850 passed, 280 skipped, 32 xfailed in 7 min 54 s, as a co-tenant (paused once by its memory guard), 6.6 GB peak. No test added. `tests/test_audit_table.py` 23 passed and `tests.audit_delta` exit 0 after the last row edit, `tests/test_docs_consistency.py` 26 passed (macOS arm64, worktree `[dev]` venv). Reader output unchanged (exit 0). Full suite not run: no measured number in the package can move.

  *Gotchas.* `lm.BVLS_MAX_COLUMNS` counts every column of the solve, not the Pawley intensities: NAC's 140 intensities cross it by 26, cpd-1a's 111 never do. `bccg.solve`'s `tol` is a keyword default bound at `def` time, so `_CONVERGED_FRACTION`'s arms patch `solve.__kwdefaults__` too. A wsrun job directory keeps the canary's `DONE`, so `watch_wsjob.sh` reports the next task done at once: delete it before starting the next task.

  *Generality.* The judge (Opus, following `.claude/agents/generality-review.md`, read-only) on the rows as first written, condensed: `_PCG_TOL` **weak** (two families; the GSAS cell reads drift; FAP and NAC development data; no record field says a stop was premature), `_PCG_BUDGET_PER_VARIABLE` **weak** (one family, and far below the 1 493-1 499 columns WP-1953 set it on), `_CAUCHY_ARMIJO` **cannot tell** (unreached; the 2026-11-05 rule asks for a named synthetic case, not a third family), the four `bccg.solve` constants **holds** (unreachable, verified; the rows should name the test that reaches them). It confirmed the design was committed before the first fit. *Author:* agreed on all; the rows now carry the drift label, the development-data label, the size gap, the synthetic-case close for `_CAUCHY_ARMIJO`, and `tests/test_bccg.py::test_published_termination_is_deliberately_inexact` and `::test_removal_scheme_is_cheap_and_harmless` for the four. No record field was added: that is a design change.

  *Not done, and why.* A third family past the cut, ideally a Pawley block over 1 000 columns on the sparse path, for `_PCG_TOL` and the budget; a synthetic case reaching `_CAUCHY_ARMIJO`. Groups B and D, for the reasons above; E, F and I-S not started.

  *Questions for the maintainer.* (4) Group B: which third Stephens family, or does B close under the rare-feature clause (`generality.md` § The rule) on qarr brucite and corundum? (5) The four constants read only by `bccg.solve`: stay at tier 3 on `tests/test_bccg.py`, or does the uncalled routine leave the audit's reach? (6) `_PCG_TOL` at 1e-8 stops FAP elsewhere with every stage `converged` and nothing in the record: is a field saying a projected-CG solve stopped on its budget or tolerance owed?

  *Next.* (1) Group D: fix its joint fits in § What each group inherits (candidates listed there), then force each layout. (2) Groups E and F in order. (3) Group H's removal once #1494 merges.

- **2026-11-16** — The absent-phase hold's 3σ threshold was run on the cases its approval left owed, and on real trace phases it never acts. Three weighed phases near 1 wt % and the CuO impurity in an 11-BM ramp read 9 to 34 esds at every stage. From their database cells, and with their cells moved about one peak width off, holding at 1σ, at 3σ or not at all gave bit-identical fits, and every cell found its way back. The one start where the threshold mattered is a phase weighed at zero (zircon declared in cpd-1a): 3σ holds it at the end, 1σ and off do not, and nothing else in the fit moves by more than the noise. The case the threshold was most suspected of, a real phase pushed under 3σ by its own offset and then held there, was not produced: one peak width is not far enough. So no value moved and no tier changed; the three rows now say what was measured and what is still owed.

  *Done.* PR #1577, a second PR beside #1494 (expect a trivial conflict in this file's Status line, group table and log head, and in `docs/wp/README.md`). `2017-batch/group_g.py` and `group_g_summary.md`; starts and arms fixed in § The list's "G, its starts and arms" bullet before anything ran (commit 51e56e95f). Evidence rewritten on `schemas.plan.PHASE_SUPPORT_SIGMA`, `PlanSpec:phase_support_sigma` and `Refinement.run_stage:phase_support_sigma`; tier, value and approval unchanged.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with the tree on `PYTHONPATH`, rietx-kernels 1.5.0, numpy 2.5.3, compiled tier on, 12 workers of one kernel thread, at `51e56e95f`; 55 single fits and 5 chains in 338 s, 398 MB peak a process):

  | Start | Minor phase | Scale / reported esd | Held at 3σ | 1σ, None, window off against 3σ |
  |---|---|---|---|---|
  | cpd-1a, -1b, -1c | corundum 1.15, zincite 1.36, fluorite 1.36 wt % weighed | 8.7, 33.8, 22.4 | never | bit-identical |
  | the same, cell one fitted FWHM off (1.05-1.09 FWHM from the answer) | as above | as above | never | bit-identical; cell recovered to the database start's answer |
  | CuCr₂O₄ 6.8 K and 288.7 K frames | CuO, 1.1 wt % by Rietveld (Suchomel 2012); reads 0.50 and 0.38(25) | 17.2, 14.8 | never | bit-identical |
  | the same, one FWHM off | as above | as above | never | bit-identical, recovered |
  | the ramp, 17 frames chained, CuO one FWHM off | CuO 0.38-0.64 wt % | 14.9-21.9 | never | bit-identical; within 0.011 plain esd of the chain from the database cell |
  | cpd-1a with zircon declared | zircon, weighed 0 | 1.3 (3σ), 0.7 (1σ, None) | closing stage only | other rows 0.0135 plain esd (noise arm 0.0245), background 0.040 (noise 0.0005), every weight fraction within 0.007 wt % |

  Zircon's reported c walked from 5.980 to 5.870 Å (−1.8 %) in the stages before the closing one under every arm, since it passed the screen at each stage start; the hold at 3σ restored it only to that walked value. Each start's distance from its answer, per axis, is in the summary: the cold frame's off start sat 0.73-0.95 FWHM from its answer, and the hot frame's database cell already sat 2.2-4.9 FWHM below its answer, so its "off" start was the nearer of the two (the displacement was applied to the database cell, as fixed). The FWHM is the fitted U, V, W, X, Y of the answer, which `mccusker_default` refines on the specimen, so on the ramp it is the total width. CuCr₂O₄'s cold-frame cell against Suchomel's 10 K Table I: a −19, b +110, c −114 ppm. Group H on these fits: 628 solves, a phase windowed in 2 (zircon's closing stage), a free cell column bounded in none; the window-off arm is bit-identical on every start and chain. With #1494's 298 fits, the window has now bounded nothing in 3060 solves.

  *Canary*: cpd-1c and the cold frame at 3σ, 15.5 s, 281 MB, 128 % of 2 cores, Rwp equal to the Mac's run to four digits.

  *Tests.* Fast selection at d7ac4cf93 on the workstation (Linux x86_64, `rietx-py312` venv, tree on `PYTHONPATH`, `-n 8 --dist loadgroup`): 14850 passed, 280 skipped, 32 xfailed in 9 min 27 s, as a co-tenant beside two other jobs. No test added. `tests/test_audit_table.py` 23 passed and `tests.audit_delta` exit 0 after the last row edit, `tests/test_docs_consistency.py` 26 passed (macOS arm64, worktree `[dev]` venv). Reader output unchanged. Full suite not run: no measured number in the package can move.

  *Gotchas.* `phase_support_sigma=None` still reports `PHASE_UNCONSTRAINED` against 3, while 1 reports against 1, so on bit-identical fits `off` says yes and `s1` no. The summary's scale/esd column is the reported plain esd, not `refine._answer_significance`, which the hold reads; zircon reads 0.7 at 1σ and was not held. A `StageResult.width_twins_held` key is the held twin and its values the free specimen columns: the rows written at `51e56e95f` took the values out of `support_held` too, so zircon's closing-stage widths are missing from that one list; `held_phases`, which the summary reads, is unaffected (fixed in d7ac4cf93). `wsrun` kills a 12-worker pool under the default process guard: pass `--max-procs-per-task`.

  *Review.* A read-only agent in the worktree (never `/code-review`, which edits the main checkout). Seven findings, all taken in d7ac4cf93: the twin filter above, and the scale-B filter widened to anisotropic paths; the off start's real distance from the answer now printed, and the rows say "0.7-1.1 fitted FWHM" rather than "one instrument FWHM"; the rows no longer quote 1.3σ as the hold's statistic and now name zircon's walk; "a weighed phase under 1 wt %" is kept as owed; the ramp's recovery read on its first frame, frames 2-17 being warm starts; "frames rejected" counted with `schemas.sequential._rejected`; the promised 10 K cell comparison added. Nothing it found changed a number in either table.

  *Generality.* The judge (Opus, reading `.claude/agents/generality-review.md`) on the rows before the review's rewording; the 1.3σ wording, the zircon walk, the development-data and check-only labels, the owed sub-1 wt % phase and the `run_stage` seat it raised are now in the rows. Its sections, unedited:

  ##### `rietx.schemas.plan.PHASE_SUPPORT_SIGMA` (constant, tier 3, 3.0, approved 2026-10-19)

  **Verdict: weak.** The case for the hold itself is still the stronger side, but this row's new evidence does not test its 3σ threshold. The threshold was reached on one start of one family, and the row says "no failing case" even though the WP and the extra raw numbers contain candidates.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | grounds: "The hold it gates passes the judgement ground" (`_audit.py:4165`) | It sets the significance below which a phase counts as unseen. Under it, every free structural path of the phase is held for the stage, and a phase that collapsed at the answer is restored and held (`refine._answer_significance`, `StageResult.held`). | answered |
  | 2. Ambiguity kind | No `ambiguity` field. No constant row in the table carries one (0 of 289). | The hold is kind 1 (the data settle it), as DESIGN.md § Rules, 1 names it. The number 3 is the part on trial. | agrees |
  | 3. Case against acting | grounds: "the 3 sigma is rietx's own, which Currie (1968) does not carry" | **(a) A different number in practice.** TOPAS's opt-in `Remove_Phase(0.3, 0.5)` removes a phase when its esd is more than half its value, which is under 2σ, and its weight is below 0.3 %, with both numbers the caller's (`2002-batch/rulings.md:1179`, checked there). **(b) B1.1's case** (the maintainer's PR #1050 item: a minor phase one peak width off its cell, read under 3σ and held there) was never produced. CuO read 14.9-21.9σ per frame, and every off start recovered. **(c) Candidates on disk the row leaves out.** The WP's inherited G bullets (lines 142-145) record LaB₆ with its cell +1 % (scale to 0, phase held, `usable=False`) and NAC +3 % (CaF₂ lost to a held scale 0, `usable=True`, `PHASE_UNCONSTRAINED` the only word on it). Neither was run at 1σ or None, so whether the hold kept them there is not known. **(d) A missed absent phase.** Zircon (weighed 0) passed the 3σ screen in intermediate stages, and its c walked from 5.9796 to 5.870 Å under every arm. 3σ held it only at the closing stage, after the walk. That is the walk the hold exists to stop. | real, unmeasured |
  | 4. Case for acting | evidence: "3 holds zircon at the answer (1.3 sigma), 1 and None leave it free, the other phases' rows within 0.014 plain esd (noise 0.025) and every weight fraction within 0.01 wt %" | Confirmed by the extra numbers: 0.01345 esd against a noise arm of 0.0245, and 0.0068 wt %. Background rows moved 0.0397 against the noise arm's 0.000539, 74× the noise floor (under the 0.1 bar, and excluded by the protocol). The row does not quote this. On the new data, leaving the phase free cost nothing measurable on the other numbers. The case for still rests on the earlier evidence: the 14.9 Å walk (v1.3) and WP-1523's 20 blank fits. | holds the action, not the number |
  | 5. Tier and source | tier 3, "rietx's own" | Correct. GSAS-II (scale floored at 1e-12, no significance test), TOPAS (scale floored at 1e-11, removal opt-in) and FullProf (a negative scale reset to 1e-10) hold nothing by default. All three are checked in `rulings.md` B1. RIETAN-FP, BGMN, MAUD and EasyDiffraction: not checked in this repository. The "1.3 sigma" the row quotes is the reported scale/esd. The tested statistic is `_answer_significance` (no χ²_red or Bérar-Lelann factor; `tests/test_phase_significance.py` docstring). The s1 arm shows the two differ: zircon reads 0.7 there and was not held at 1σ. | statistic misquoted |
  | 6. Families | "two families by lab, instrument and material" | **Two families, as the row says; the rule asks for three.** The arms reached the threshold on **one start of one family**: cpd-1a with zircon. 50 of 55 fits and all 5 chains were bit-identical across 1, 3 and None, and the row says so ("unreached there"). The row does not say that both families are development data: cpd-1a is graded so in this WP's own handover (line 374), and the CuCr₂O₄ ramp was used in WP-2081. CuO's 1.1 wt % is "Rietveld; temperature not stated" (`tests/data/README.md:1973`), a published refinement under another protocol. It measures drift only and does not validate, yet the row lists it beside the weighed fractions without saying so. CuO reads 0.38-0.64 wt %, unrelated to the arms. | fails the count |
  | 7. Record | not in the row | `StageResult.held`, `.released` and `.collapsed`, and `PHASE_UNCONSTRAINED`. Under None the code still reports against 3σ (`_reported_support_sigma`), which is why zircon's off arm reads "yes" and s1 reads "no". The per-stage `significance` was not recorded by `group_g.py`. | exists |

  **What would change the verdict:** B1.1's case actually reached and run at 1σ, 3σ and None, with each answer's distance from its reference. Candidates: NAC +3 % (CaF₂), LaB₆ +1 %, or CuO started 2-3 FWHM off. Also a third family, the per-stage significance recorded, and a stricter arm (5σ) on the zircon start, where 3σ let the walk through.

  *Author:* agreed; the row now quotes no σ for zircon, names the walk and the owed cases, and labels the families and CuO's reference. The B1.1 case and a third family go to the maintainer as questions (1) and (2).

  ##### `rietx.schemas.plan.PlanSpec:phase_support_sigma` (default, tier 3, ambiguity 1, 3.0)

  **Verdict: weak.** The evidence text is identical to the constant's, so the same gaps apply. The grounds for having the hold on by default are sound, but the default value is untested where it matters.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | grounds: "On by default: the hold touches only parameters the data cannot determine" (`_audit.py:4650`) | Every plan runs the hold at 3σ unless the caller sets another value or None. | answered |
  | 2. Ambiguity kind | `ambiguity=1` | Agrees for the action. The value is rietx's own. | agrees |
  | 3. Case against acting | grounds: "no other code holds by default (TOPAS's Remove_Phase is opt-in)" | Same as the constant's row 3. The nearest practice is opt-in, at under 2σ and 0.3 wt %. The default is applied to every caller's fits, so the zircon walk under 3σ and the untested B1.1 case bear on it directly. | real, unmeasured |
  | 4. Case for acting | "an unseen phase's free cell walked 14.9 A from the truth while Rwp did not move" | Still the strongest evidence, but it predates this change and is one case. This WP measured no cost of None on the other numbers (≤ 0.0135 esd, ≤ 0.0068 wt %). | holds the action |
  | 5. Tier and source | tier 3, "the 3 sigma is rietx's own" | Correct. No program sets this by default (`rulings.md` B1, three programs checked; four not checked here). | correct |
  | 6. Families | same text as the constant | Same as the constant's row 6: two families, reached on one start, development data not stated, CuO's reference only verifies. | fails the count |
  | 7. Record | not in the row | `StageResult.held`, `PHASE_UNCONSTRAINED`. The default `None` is recorded in the plan (`tests/test_textdoc.py:619-643`). | exists |

  **What would change the verdict:** the same as for the constant. In addition, a run of the B1.1 case at the default against None that shows which reaches the reference cell and composition.

  *Author:* agreed, as for the constant.

  ##### `rietx.refine.Refinement.run_stage:phase_support_sigma` (default, tier 3, ambiguity 1, 3.0)

  **Verdict: weak.** This is the same number at a second seat, used when a stage runs outside a plan. Its evidence and grounds are the plan default's word for word, so its findings are the same. No fit in group G went through `run_stage` on its own, so nothing here measured this seat.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | grounds as the plan default's (`_audit.py:4849`) | It sets the hold's threshold for a stage run by hand. Replay passes the node's recorded value (`refine.py:4912`). | answered |
  | 2. Ambiguity kind | `ambiguity=1` | Agrees. | agrees |
  | 3. Case against acting | as the plan default's | Same as the plan default's row 3. A caller running one stage by hand is the most likely person to want the phase's cell free (stepping a trace phase in deliberately). This seat gives them the hold unasked. | real, unmeasured |
  | 4. Case for acting | as the plan default's | Same as the plan default's row 4. One value at both seats keeps a hand-run stage consistent with a plan's. | holds the action |
  | 5. Tier and source | tier 3 | Correct. | correct |
  | 6. Families | same text | **none given** for this seat: every group G fit went through `fit(plan=…)`. | fails the count |
  | 7. Record | not in the row | `StageResult.held`, `PHASE_UNCONSTRAINED`. | exists |

  **What would change the verdict:** the plan default's evidence, plus one hand-run `run_stage` fit on a start that reaches the threshold.

  *Author:* agreed; the row now says no group G fit ran through this seat.

  *Not done, and why.* The rest of group G's debt: B1.1's case was never reached. Candidates the judge named, none run: NAC +3 % (CaF₂ lost to a held scale 0, in § What each group inherits), LaB₆ +1 %, CuO started two or three FWHM off, a phase weighed under 1 wt %, a third family, and a 5σ arm on the zircon start, where 3σ let the walk through. Group H's removal waits on #1494 merging, since that PR rewrites the three `CELL_WINDOW_*` rows.

  *Questions for the maintainer.* (1) Does group G stand closed on this evidence under the 2026-11-05 ruling (a constant its families barely reach stays at tier 3 on a named synthetic case, WP-1523's 20 blank fits here), or should B1.1's case be built first, and at which offset or fraction? (2) The family set fixed on 2026-11-05 was two families, not three; is a third owed for this row? (3) Zircon's c walked 1.8 % under the 3σ hold before the closing stage: is that the hold's job (a stage-start screen that passed it), or a separate question?

  *Next.* (1) Group H's removal once #1494 merges: no fit in groups A or G was bounded by the window. Answer first the case read off the code in #1494's entry (a caller's tie). (2) Group B, the next in this file's order: `_POLISH_FEASIBLE`, `_POLISH_STATIONARY`, `BVLS_MAX_COLUMNS`, whose "one more" Stephens family is not yet named and must be fixed before running.

- **2026-11-05** — On fits that reach their answer, the ten solver stop constants do not matter. Moving each one either side of its value shifted no refined number by more than 0.0084 esd, a twelfth of the bar, on four families from nine harder starts. The same sweep could not clear them, though. Most constants are never read on these fits, and only three acted on three or more families at an answer. On starts that miss the answer, four of the constants choose which wrong minimum the fit lands in, and the shipped values are no better than their neighbours. So nothing was demoted and no value moved. Seven rows go to the maintainer, because no written exit fits a constant that ordinary fits barely reach.

  *Done.* The list (task 1) and the families per group (task 2), both in § The list. Inherited emptied into it. Group A's first arm of task 3: 84 arms from shipped starts and 135 from hard starts, fixed in this file before running. Ten rows' evidence rewritten; tier and value unchanged. Scripts and summaries in `docs/wp/2017-batch/`. The raw rows are not committed, and sit in `~/.cache/rietx/wp-2017/`.

  *Measured* (macOS arm64, worktree `[dev]` venv, compiled tier on, 4 workers of one kernel thread, at `90e67197c` and `1ed7a9517`):

  | Constant | Acted at an answer, families | Worst there, plain esd | On starts that miss |
  |---|---|---|---|
  | `_CONVERGED_RUNS` | 4 | 0.0024 | not run |
  | `FTOL` | 4 at 1e-8, 2 at 1e-10 | 0.0011 | not run |
  | `_M_LO` | 3 at 0.8, 2 at 0.2 | 8.2e-6 | not run |
  | `_LAMBDA_FAIL_FACTOR` | 2 (cpd-1a, FAP) | 0.0084, noise 0.0055 | NAC +3 %: both arms lose NAC, Rwp 0.139 to 0.79-0.80 |
  | `_LAMBDA_FAIL_FLOOR` | 2 (cpd-1a, FAP) | 1.25e-5 | NAC +3 %: both arms lose NAC, Rwp 0.77-0.80 |
  | `_M_HI` | 1 (cpd-1a with zircon) | under its noise | NAC +3 %, arm 20: Rwp 0.794 |
  | `SLOW_DESCENT_ESD` | 0 | none | acts on two starts, under noise |
  | `_Q_TRIGGER` | 1, arm 3 only (FAP) | 3.2e-7 | none |
  | `_Q_WINDOW` | 0 | 0 | none |
  | `_CURVATURE_GATE` | read on cpd-1a, no arm moved it | 0 | none |

  Of the nine hard starts, five reach the shipped start's answer: FAP +1 % and +3 %, NAC +1 %, cpd-1a +1 %, and cpd-1a with zircon declared. Four miss. No arm changed which. A fresh rerun outside the lane's code reproduced three numbers: cpd-1a `_CONVERGED_RUNS` 2 at 0.00242 esd, and LaB₆ +1 % and NAC +3 % at Rwp 0.8616 and 0.1394. Fast selection on the tree before the rows' last rewrite: 13921 passed, 240 skipped, 36 xfailed, 21 min, `[dev]`, macOS arm64. No test added. The rewrite touched row text only, and `tests/test_audit_table.py` passes on it. Reader output unchanged. Full suite not run, since no measured number can move.

  *Lanes.* Two, both on `opus-5-5`:

  | lane | est | requests | main at dispatch | lane base | re-read | lane $ | saved $ |
  |---|---|---|---|---|---|---|---|
  | group A | 25 | 26 | 232K | 99K | 0K | 3.16 | +0.51 |
  | group A hard starts | 15 | 16 | 254K | 99K | 0K | 3.39 | -0.77 |

  Selective policy over the replay: -15 % at u = 0K, the row the baseline command prints.

  *Gotchas.* A stage with a phase-hold second solve records that solve's `termination` (`refine.py:5259`), so `slow_descent` on cpd-1a +3 % shows in the solve log and in no `StageResult`. `FTOL` is a keyword default, so patching the module global does nothing (`group_a.patched`). The esd yardstick skips rows with no esd, so read Rwp on a wrong answer. NAC +3 %'s shipped fit reads `usable=True` with CaF₂ lost, and `PHASE_UNCONSTRAINED` is the only word on it. Arm 20's Rwp 0.794 sits under `MODEL_FAR_FROM_DATA_RWP`, which bears on group K.

  *Review.* `/code-review high --fix` found five. Four fixed: a row naming a code that cannot fire at Rwp 0.794, grounds contradicting their evidence, `_polish_read` ordering the axial pair on one side, and the raw rows' location. One declined: `verdict` lets an unjudged row pass, which would need the stored verdicts re-read, and all nine shipped rows carry none.

  *Generality.* Judge on the rows as first written, which claimed "holds" for six. The author's answer to every `fails`, `weak` and `cannot tell` below: agreed, and the rows were rewritten to what was measured. The rows now claim no "holds", and seven name this WP's batch.

  ##### `rietx.optimize.lm.FTOL`

  **Verdict: weak.** The case for acting is stronger: three-plus families gave one answer, but the row states no failing case and no start domain, and the record's ground asks for the first.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | Old row kept: "The last tolerance of the schedule rietx chose" (grounds) | When the last declared stage and the closing stage stop: relative fall in S under 1e-9, three times running. | clear |
  | 2. Kind | `ambiguity` empty, which a constant row need not fill (`_STATES_AMBIGUITY`) | First kind for having a stop. Only the value is on trial. It is close to a numerical setting in the record's tier 1 sense, but no test bounds it. | fine |
  | 3. Case against | Evidence: GSAS-II 5.8.4's "default 'min dM/M' is 1e-3" and SciPy 1e-8 | GSAS-II users stop six decades looser. FullProf's cycle stop is also 1e-3 (`docs/practice.md`:523, Le Bail, ran). TOPAS's stop: could not find it in `docs/practice.md`. Arms went one decade each way, so nothing here tests a looser stop. The row's 1e-6 case (cpd-1b's axial_sl 555, against 0.0082) is one family, and it fails the looser value, not 1e-9. | real dissent, tolerated at tier 3 |
  | 4. Case for | "worst 0.0011 plain esd, cpd-1a phases.0.scale at 1e-8, 0.957-1.043x evaluations, no reference moved past 3.2e-4 esd" | All four figures match the raw rows (largest `worst_further_esd` 3.16e-4, cpd-1a). Moving to 1e-8 saves at most 4 % of evaluations and moves answers about 1 % of the bar. | strong |
  | 5. Tier | Tier 3, "so it holds at tier 3" | Tier 3 is right, with no source for 1e-9. The value is outside GSAS-II's and FullProf's defaults. The row's stated reason is the one-family 1e-6 case. No `invariant` claim. | acceptable |
  | 6. Families | "cpd-1a and SRM 660c validate, FAP and NAC verify"; development data | Four families at 1e-8. At 1e-10 only NAC and cpd-1a moved; FAP and SRM 660c closed on `exhausted_fp64` (checked, raw lines 24 and 89), so they had no room to differ. The row discloses this. It gives the change in reference distance, not the distance itself, which the WP's Goal asks for. `run_multi_least_squares`' default was never reached (`group_a.py` docstring), so "every seat" is too wide. | count met; **no failing case and no start domain stated** |
  | 7. Record | none given | `StageResult.termination` (`ftol_runs`). `StageResult.ftol` reads `None` on these stages, printed "solver default" (`results.py`:1566). | adequate |

  Would change the verdict: one sentence stating "shipped starts only" with a failing case, or FTOL's arms run from the hard starts (cell lengths +1 % and +3 %).

  ##### `rietx.optimize.lm._CONVERGED_RUNS`

  **Verdict: weak, and the nearest of the ten to holding.** The case for acting is stronger: both arms moved all four families, but the row has no failing case.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | How many consecutive small steps count as converged. | clear |
  | 2. Kind | empty, not required | First kind. A numerical setting in all but name. | fine |
  | 3. Case against | none given | GSAS-II's per-cycle stop differs in shape (row on `FTOL`). No dataset on disk shows 3 failing. No hard start was run on this constant. | none found on disk |
  | 4. Case for | "2 and 5 on FAP, NAC, cpd-1a and SRM 660c: worst 0.0024 plain esd, cpd-1a profile.v, 0.891-1.132x evaluations; no reference moved past 1.8e-4 esd" | All confirmed (1.83e-4 in the raw rows). Each arm differed from shipped on all four families, so the control passed on both sides. The worst shift is 2.4 % of the 0.1 esd bar. | strong |
  | 5. Tier | "so it holds at tier 3" | Tier 3 is correct. The row says the paper is "not on disk", then asserts it "did not validate it on rietx's problems". The repo cannot support that assertion, and WP-0601 never quotes this rule from the paper. | sentence unsupported |
  | 6. Families | As `FTOL` | Four families, all development data, two validating and two verifying. Distances from reference not given. | count met; no failing case |
  | 7. Record | none given | `StageResult.termination` = `ftol_runs`. | adequate |

  Would change the verdict: a stated failing case and start domain would make it `holds`.

  ##### `rietx.optimize.lm._M_LO`

  **Verdict: weak.** The case for acting is stronger, but "either side" is met on the high side only, and the row hides that.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | The floor on r_u (actual-to-predicted decrease ratio) when λ (the Marquardt damping, not wavelength) shrinks after a good step. It sets how fast damping falls, and with it the path. | row's words loose |
  | 2. Kind | empty, not required | Solver-path setting. | fine |
  | 3. Case against | none given | No failing case found, but none was sought: this constant skipped the hard starts. Its neighbours in the same function, `_next_lambda`, decide which minimum NAC +3 % lands in. | none found, not tested |
  | 4. Case for | "worst 8.2e-6 plain esd, cpd-1a axial_sl, noise floor 2.4e-6; NAC never read it; no reference moved past 2.1e-6 esd" | Confirmed (2.05e-6). The effect is under 0.01 % of the bar. | strong where reached |
  | 5. Tier | "so it holds at tier 3" | Tier 3 correct. Coelho's 0.4 is quoted in WP-0601; the row says "not checked". | see `_M_HI` |
  | 6. Families | "0.2 and 0.8 on FAP, cpd-1a and SRM 660c" | 0.8 moved three families. **0.2 moved two**: FAP's arm is bit-identical (`unreached`), since FAP's smallest r_u is 0.585, above both 0.4 and 0.2. The ruling says "on either side". By the WP's own control, FAP's 0.2 arm "measured nothing". | high side met, low side two families; no failing case |
  | 7. Record | none given | No record field. λ stays in `LMOutcome.lambda_final`, which does not reach `StageResult`. | none; acceptable for a path constant |

  Would change the verdict: a third family with an accepted step at r_u under 0.4 and λ above 0, plus a stated failing case.

  ##### `rietx.optimize.lm._M_HI`

  **Verdict: fails.** Stating a failing case does not replace the three-family count, and this row is met at the answer on one family only. The case against the row's "holds" is stronger. The case for the value itself is moderate.

  **The first pressed question.** The record's mechanical ground is a conjunction: "holds across at least three unrelated dataset families ... with a stated case where it fails". The failing case is a second requirement and cannot pay for the first. The phrase "every start that reached the answer" also conditions on the outcome. Starts where the constant matters are removed from the count, so almost any value would pass the sentence. On the evidence this row is in the same state as `_Q_TRIGGER`, which the author calls unproven.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | The ceiling on r_u when a step overshoots, and so how hard λ jumps after an overshoot. It picks the path, and on a far start the minimum. | row's words loose |
  | 2. Kind | empty, not required | First kind for damping at all. On a start that misses, the value silently picks among minima with no record. | gap, not a wrong entry |
  | 3. Case against | "Fails on NAC +3 %, which misses the answer on every arm: 20 loses NAC, Rwp 0.139 to 0.794" | Confirmed, but incomplete. On cpd-1a +3 %, arm 5 moves 102.6 esd against a noise arm of 3.99. It lands at χ² 2.09× the answer's against shipped's 5.03× (both polished), so shipped is the worse minimum there. Rwp 0.794 sits 0.006 under the 0.8 threshold, so it raises no `MODEL_FAR_FROM_DATA`. The row omits that. | stated case too narrow |
  | 4. Case for | "the only start reaching the answer that met it is cpd-1a with zircon, under its 0.0055 esd noise" | Confirmed: 2.1e-4 and 7.5e-5 esd. No arm changed reach-or-miss on any of the nine starts, the best fact available, though not quoted in the row. On NAC +3 % shipped ends 183 esd nearer the reference cell than arm 20, and χ² 2.25× the answer's against 72×. | real, but one family |
  | 5. Tier | "so it holds at tier 3" | Tier 3 is the only tier the evidence allows now. WP-0601 (`/Users/yue/Code/rietx/.claude/worktrees/wp2017-second-pass/docs/wp/0601-bounded-lm-solver.md`:357) quotes eq. 9, the clip [0.4, 10], and gains R_ν 0.96-1.19 "across the crystallographic set". So "did not validate it on rietx's problems" and "not checked" sit awkwardly beside it. A filename search of ~/Zotero found no Coelho file. Whether TOPAS ships these by default: could not find it. | paper unread; tier 2 possible, untested |
  | 6. Families | "cpd-1a with zircon" | **One family at the answer** (development data, validates by weighed fractions). The other three starts reaching it all miss. Below-the-bar agreement on a wrong LaB₆ answer is not "holds", which is measured against a reference. | **fails the count** |
  | 7. Record | none given | None. | none |

  Would change the verdict: two more unrelated families with r_u above 5 on a fit reaching its answer, or a maintainer ruling that a rarely reached constant is kept as a rare feature is.

  ##### `rietx.optimize.lm._LAMBDA_FAIL_FACTOR`

  **Verdict: fails.** Two families at the answer, not three. The evidence for the value is real, and the row's NAC statement names only one of the two arms that fail.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | How fast λ grows after a rejected step, and also the λ/10 factor in branch (ii) (`lm.py`:421). The row omits the second seat. | loose |
  | 2. Kind | empty, not required | As `_M_HI`. | gap |
  | 3. Case against | "5 loses NAC, Rwp 0.139 to 0.802" | **Both arms lose NAC**: 20 reads Rwp 0.790, with S about 72× the answer's. The row implies one direction. The real shape is that shipped sits in a narrow window on this start. LaB₆ +3 % is also unstated: arm 20 moves 118 esd, further from the displacement reference, against noise 0.094. On cpd-1a +3 % arm 5 reaches a lower χ² than shipped. | stated case understates |
  | 4. Case for | "worst 0.0084 esd against 0.0055 noise" on starts reaching the answer | Confirmed. On NAC +3 % both arms sit 223-516 esd further from reference than shipped. No arm changed reach-or-miss. | moderate |
  | 5. Tier | "holds at tier 3 with its failing case stated" | Tier 3 stands as a tier. "Holds" does not. Source as `_M_HI`. | not met |
  | 6. Families | "on cpd-1a and FAP" | **Two families.** Three of the four starts counted are cpd-1a. FAP's single case is +3 %. Development data; cpd-1a validates, FAP verifies. | **fails the count** |
  | 7. Record | none given | None. | none |

  Would change the verdict: a third unrelated family where a step is rejected and the fit reaches its answer, with both arms under the bar.

  ##### `rietx.optimize.lm._LAMBDA_FAIL_FLOOR`

  **Verdict: fails.** Two families, and on most of them the arm changed the fit by nothing or almost nothing.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | The first λ after a rejection from λ near 0. | loose |
  | 2. Kind | empty, not required | As `_M_HI`. | gap |
  | 3. Case against | "0.01 loses NAC, Rwp 0.139 to 0.802" | **Both arms lose NAC**: 1.0 reads Rwp 0.771. On LaB₆ +3 %, arm 1.0 moves 19.4 esd further from the displacement reference. | stated case understates |
  | 4. Case for | "worst 1.25e-5 esd against 2.9e-6 noise" | Confirmed. On NAC +3 % both arms sit 223-518 esd further from reference than shipped. No arm changed reach-or-miss. | moderate |
  | 5. Tier | "holds at tier 3 with its failing case stated" | As `_LAMBDA_FAIL_FACTOR`. | not met |
  | 6. Families | "on cpd-1a and FAP" | **Two families.** On cpd-1a's shipped start and +1 % the arms moved answers 0 esd, one evaluation each way. Real exercise is zircon and FAP +3 %. | **fails the count** |
  | 7. Record | none given | None. | none |

  Would change the verdict: as `_LAMBDA_FAIL_FACTOR`.

  ##### `rietx.optimize.lm._Q_TRIGGER`

  **Verdict: cannot tell.** Neither side has evidence from a real fit at the shipped value. The row says so honestly, but it has no exit in the WP.

  **The second pressed question.** A row may stop naming the *refits* as owed, because rerunning these starts would teach nothing. It may not treat the debt as closed.
  - The approval was conditional: "stay tier 3 until refits of three families on either side give one answer". A bit-identical arm cannot give an answer. The WP's own rule says such an arm "measured nothing".
  - The WP's Goal has three exits: holds, moves to tier 1 or `invariant`, or back to the maintainer. "Stays unproven" is a fourth with no authority, so it is a ruling for the batch.
  - The record's nearest rule is that a guard no ordinary fit reaches "is kept on the strength of an injected case the row names", and "where none exists the batch builds it before the row is recorded kept". The row names none.
  - "A fit that exercises it" has no owner once WP-2017 closes. The row should name who holds it.
  - `approved` still carries the old date, above grounds the maintainer has not seen.
  - "Barely met it" reads as "only just passed". The author means "hardly reached it". The wording should change, since rows are approved in batches.
  - "(ruled 2026-10-20; WP-2017 group A)" sits after that clause, as if the ruling covered the result. It covers only the request.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | When a long overshoot run cuts λ by ten (branch ii). | loose |
  | 2. Kind | empty, not required | First kind, unseen by any refiner. | fine |
  | 3. Case against | none given | none found | none found |
  | 4. Case for | "3 acted once, on FAP (largest Q 4), 3.2e-7 plain esd, 0.98x evaluations" | Confirmed. WP-0601 reports the paper calling this branch "rarely-fired", which fits. The shipped trigger itself never fired on any of 13 starts (see `_Q_WINDOW`). | no case for the value 5 |
  | 5. Tier | "stays at tier 3 unproven" | Tier 3 is the honest place. The paper is unread in the row. | needs a ruling |
  | 6. Families | "on one family at most" | Accurate, and generous: one arm, one family, at a value not shipped. Arm 7 measured nothing. | zero families at 5 |
  | 7. Record | none given | None. `test_lambda_schedule_branches` (`/Users/yue/Code/rietx/.claude/worktrees/wp2017-second-pass/tests/test_lm_solver.py`:101) pins branch (ii)'s formula at a hand-set Q of 6. It is not a fit, and the row does not name it. | none |

  Would change the verdict: an injected fit where Q passes 5 and the row names it, or a ruling that a branch this rare is kept unmeasured.

  ##### `rietx.optimize.lm._Q_WINDOW`

  **Verdict: cannot tell.** No arm measured anything, so `_Q_TRIGGER`'s question and answer apply unchanged.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | How many recent steps Q (the overshoot count) sums. | loose |
  | 2. Kind | empty, not required | As `_Q_TRIGGER`. | fine |
  | 3. Case against | none given | none found | none found |
  | 4. Case for | "bit-identical everywhere, largest Q 4 ...; 5 could never pass the shipped trigger" | Confirmed. So arm 5 is branch (ii) switched off, and bit-identity proves that branch never fired at shipped values on any of 13 starts. The row does not draw this, its most useful conclusion. | no evidence for 10 |
  | 5. Tier | "stays at tier 3 unproven" | As `_Q_TRIGGER`. | needs a ruling |
  | 6. Families | "on one family at most" | **Zero families.** "At most" hides this. Neither arm changed anything on the synthetic seat check either (`seat_reached` false). The bytecode read is the only proof the patch lands. | zero |
  | 7. Record | none given | None. | none |

  Would change the verdict: as `_Q_TRIGGER`, with a window arm that changes a fit.

  ##### `rietx.optimize.lm._CURVATURE_GATE`

  **Verdict: cannot tell.** The shipped value is read on one family, both arms change nothing, and the row contradicts itself on what is owed.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "A solver-path switch no refiner has a view on" | At what λ a rejected step triggers measuring a coordinate's true curvature, which may replace Gauss-Newton's diagonal and reset λ. This is closer to an action than the other nine. | fine |
  | 2. Kind | empty, not required | First kind. | fine |
  | 3. Case against | "no measurement chose 100 over 30 or 1000" | Still true after the sweep. | none found |
  | 4. Case for | none in the row | Tests show the *mechanism* matters: `test_a_column_that_vanishes_at_its_minimum_keeps_its_scale` and `test_a_column_small_from_the_first_iteration_has_its_curvature_measured` (`test_lm_solver.py`:794, 820), with the gate off, stop at over twice the χ². These are synthetic and are the injected case the record asks for, but the row names neither. They test on against off, not 100. | exists, unused |
  | 5. Tier | "stays at tier 3 unproven" | Tier 3. An arm at infinity (gate off), as those tests use, was not in the sweep. It is the arm that would tell. | needs a ruling |
  | 6. Families | "on one family at most" | Accurate: cpd-1a, read 3 to 14 times. Both arms bit-identical, so by the WP's control they measured nothing. **The evidence still reads "second pass owed"**, which contradicts the new grounds and breaks the WP's acceptance line. **The date is wrong**: the row's ruling was 2026-10-19 (old grounds, `approved`), and the new grounds say 2026-10-20. | row must be corrected |
  | 7. Record | none given | None. An adopted curvature leaves no field. | **gap for an action** |

  Would change the verdict: a gate-off arm on the real fits, with the row naming the two tests.

  ##### `rietx.optimize.lm.SLOW_DESCENT_ESD`

  **Verdict: weak.** The case for acting is stronger than the row says, because the row leaves out its best evidence. The count still does not reach three families.

  | Question | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "decides where a solve stops" | Ends a stage and calls it `converged` once another 300 evaluations would buy under one esd of joint travel. | clear |
  | 2. Kind | empty, not required | First kind if every refiner would stop there. The status was ruled by the maintainer on 2026-11-03. | fine |
  | 3. Case against | Evidence: GSAS-II's stop is "looser than this" | GSAS-II is looser, so it is no dissenter. `lm.py`:165-167 states the real cost: a crawl along a flat direction "can sit well above" the minimum. LaB₆ +3 % stops so and reads `converged`, at Rwp 0.86. | moderate |
  | 4. Case for | "worst 0.25 and 0.013 esd under each start's noise; None costs up to 2.2x evaluations" | Confirmed. **Unstated:** NAC +1 % has stages of 374 and 161 evaluations and cpd-1a +1 % one of 155. All passed the rule's reading, ended `ftol_runs` and reached the answer, and all arms were bit-identical, 2.0 included. So the rule left slow, useful descents alone on two families. Also unstated: at shipped value it fired on cpd-1a with zircon under three other arms (raw lines 139, 140, 149), and those fits stayed at the answer within noise. | stronger than written |
  | 5. Tier | "stays at tier 3 on WP-1334's fixtures" | Tier 3 right, rietx's own. | fine |
  | 6. Families | "met it only on two starts that miss the answer" | "Met" means "acted". By `group_a_reach.py`'s own test, "a stage spending 100 evaluations", four starts met it. "A third family" has no clear referent. Noise on cpd-1a +3 % is one draw of 3.99 esd, which the WP calls a weak floor. Silent half: two families. Acting at the answer with all constants shipped: not shown here. | under three |
  | 7. Record | none given | `StageResult.termination` = `slow_descent` and `STAGE_SLOW_DESCENT` (info). On cpd-1a +3 % the solve log shows `slow_descent` at 240 evaluations, but the fit's stage list in `/Users/yue/.cache/rietx/wp-2017/group_a_hard.jsonl` shows none. I did not trace why. | check this |

  Would change the verdict: the row quoting the silent half and naming `/Users/yue/Code/rietx/.claude/worktrees/wp2017-second-pass/tests/test_slow_descent.py` as the injected case, plus the rule acting under shipped constants on a third family's fit that reaches its answer.

  *Settled by Claude.* WP-2017 over WP-2020, under the index's P2 order. Hard starts added to group A, under this file's control rule that a bit-identical arm measured nothing. Cell lengths +1 % and +3 %, under WP-2086's reach table. No demotion and no retier, under the Goal's exits and the judge's reading. Raw rows left out of the tree, under WP-2049's precedent.

  *The papers, read the same day.* This entry and nine rows first said Coelho (2018) and (2005) were not on disk. That was wrong: both sit in the maintainer's second Zotero library, `~/Zotero yue-here/storage/`, the 2018 paper at `KGSXVB95/` and the 2005 one at `HE2XWJEA/`. The nine rows are corrected. Equation (9) prints five of the seven rows' values, plus `_M_LO`: `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`, `_M_HI`, `_Q_TRIGGER`, `_Q_WINDOW`. `_CURVATURE_GATE` and `SLOW_DESCENT_ESD` are rietx's own. The paper compares the whole schedule with the standard one on about sixteen problems and varies none of the constants, so WP-2002's objection (a paper defining an algorithm does not validate its constants) survives the reading. Two differences from the code: the paper's Q sums u-10 to u, eleven terms read literally, and rietx sums ten, which moved nothing in 260 fits. The paper ran AntiBump's penalty under BFGS, so its observation of the Q branch there does not carry to full JᵀJ, where the branch never fired.

  `docs/wp/2017-batch/group_a_paper_cases.py` runs the paper's AntiBump, equation (16), and cusp, equation (12), on `lm.minimize`, 260 fits an arm on 17 arms (macOS arm64, worktree `[dev]` venv, numpy path, no diffraction model). No arm changed an answer: the cusp reached a = 0 from 200 of 200 starts on every arm, and AntiBump at cell 4.5 reached S under 5e-12 on every fit. At cell 4 the spheres would fill 82 % of the box, so S cannot reach 0; fits land on other minima either way and the median S moves by 1.7 % at most. Cost moved: 0.60x (`_M_LO` 0.2) to 1.19x (`_Q_TRIGGER` 3, three more fits on the budget) evaluations on the cusp. So `_M_HI` and both `_LAMBDA_FAIL` constants now have a case that reaches them, and shipped is neither the cheapest nor the dearest. The Q branch fires on one fit of 260, the cusp n = 0.5 from a = 0.2375, and there it hurts. Every step overshoots, so Q sits at 10, branch (ii) takes λ to exactly 0, and branch (iv), the damper, is never reached. `a` zigzags across the minimum to the 2000-evaluation budget and ends at 7.3e-5, where trigger 7 or the branch off stops in 13 evaluations at 4e-13. Nothing changes on this: it is one synthetic start, and no diffraction start of 13 fires the branch. The probe's first run leaked each arm's constant into later arms, through pool workers that outlive a job. Its one clean row was shipped; `one()` now restores the constant, the run above is the second, and `group_a.py` restores it in `finally` so group A is unaffected. The judge did not re-run on this evidence-only correction: no tier, value or condition moved.

  *Ruling, 2026-11-05.* The maintainer took option 1 of the batch. The seven rows stay at tier 3 and close on a named synthetic case, with `_M_LO`, `FTOL` and `_CONVERGED_RUNS` outside it, since they still owe hard starts. The alternative was tier 2 for the five that equation (9) prints. `tests/test_lm_solver.py` gains the cusp, 4 passed on `[dev]`, macOS arm64. From a = 0.2375 to 0.243 at n = 0.5 the stall holds on every start tried, and a nudge of 1e-4 at 0.2375 does not end it, so the test pins it mid-band at 0.24. On 981 starts from 0.01 to 0.5 it fires on those 12 alone. The grounds of the seven rows changed and the judge did not re-run, because the exit is the maintainer's ruling and no tier or value moved.

  *Next.* (1) Hard starts for `FTOL`, `_CONVERGED_RUNS` and `_M_LO`, the same nine starts, 54 fits, for their failing case. (2) Group H next: it needs no new fits beyond counting where the cell window binds, and its removal is already ruled.

- **2026-11-04** — Task added from WP-2086's review: tell a blank frame with structure from a phase whose peaks missed. Numbers re-read from the raw rows. With the synthetic humps the 14 frames span d 0.34-1.49, past the 0.43-1.04 quoted for Kapton, and Kapton's Q is 1.96 at its 21 001 channels. Nothing new measured, no code. PR #1408.

- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the second pass moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

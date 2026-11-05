# WP-2017 — The second pass: every surviving tier-3 threshold measured on three families

Milestone: generality · Status: 🔄 2026-11-05 — claimed by @yue-here
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
| A. LM stop | `lm._M_HI`, `_M_LO`, `_Q_TRIGGER`, `_Q_WINDOW`, `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`, `_CONVERGED_RUNS`, `_CURVATURE_GATE`, `FTOL`, `SLOW_DESCENT_ESD` | one each side of each value, `FTOL` at 1e-8 and 1e-10 | the four, then the hard starts below | done 2026-11-05 |
| B. Bounded step | `lm._POLISH_FEASIBLE`, `_POLISH_STATIONARY`, `BVLS_MAX_COLUMNS` | each side | Stephens fits on qarr brucite and corundum and one more; FAP Pawley for the column cut | open |
| C. BCCG | `bccg._CONVERGED_FRACTION`, `_CONVERGED_RUNS`, `_SMALL_FACTOR`, `_SMALL_RUNS`, `_CAUCHY_ARMIJO`, `_PCG_TOL`, `_PCG_BUDGET_PER_VARIABLE` | each side | Pawley on `fap`, `nac` and `cpd1a` | open |
| D. Blocked solve | `blocked.DENSE_JACOBIAN_MAX_BYTES` | forced each way | the four | open |
| E. TRF | `least_squares.GTOL`, `XTOL`, `staged.BOUND_HIT_COS_MIN`, `BOUND_HIT_ESD_FRAC` | 1e-8 against 1e-12; the 32-case bound table on a third family | `cpd1a`, corundum Stephens, 11-BM Si SRM 640c | open |
| F. Background pick | `auto.HUMP_TRIGGER`, `AIR_SCATTER_TRIGGER`, `_KNOT_STEP_HUMPY_DEG`, `_KNOT_STEP_SMOOTH_DEG` | near the trigger, each way | the Kapton capillary for a real hump, qarr's weighed mixtures for air | open |
| G. Absent phase | `plan.PHASE_SUPPORT_SIGMA`, its two defaults | 1σ, 3σ, off | a weighed trace phase (the cpd-1 suite), CuO on the CuCr₂O₄ ramp started one FWHM off, cpd-1a with zircon declared | open |
| H. Cell window | `vector.CELL_WINDOW_FRACTION`, `_ANGLE_DEG`, `_PAD_A` | count the stages where it binds | every fit of groups A and G | open |
| I. Position bounds | their removal, 2026-10-20 | free over a narrow range | lab flat plate: `fap`, `lab6`, SRM 1976a | open |
| J. Refined lines | Le Bail and Pawley Kα2/Kα1 | second standard, tabulated ratio | SRM 660c, SRM 1976a, FAP | open |
| K. Far from data | `refine.MODEL_FAR_FROM_DATA_RWP` | both directions; Rwp beside background-subtracted Rwp and Rwp/Rexp | WP-2086's reach table; a sparse-count family | open |
| L. Magnetic solve | `magnetic.SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K`, `SOLVE_K_TRIALS` | each side | the rare-feature clause: Ba₂FeSbSe₅, Cr₂WO₆, LaMnO₃ | open |
| M. Starts | `structure.BISO_SEED`, `instrument.HARMONIC_WEIGHT_SEED` | the two starts with `closing_window_tol=None` | the four; the synthetic neutron corundum | open |
| N. Hand rows | Le Bail and Pawley intensity seed, `refine._FLAT_AXIS_TEST_DIRECTIONS`, `arpls`'s `max_iter` and `tol`, `vector.FLOOR_SEEDS` | a test for each claim of invariance | named by each test | open |
| O. Domain tests | `interval.PARAMETER_INTERVAL_*` (five), `fraction.FRACTION_PROFILE_FWHM_MIN`, `_N_FWHM`, `_FWHM_MAX_SPAN` | state a domain, then 0.1 σ of a point and 0.1 esd | the two-site Pnma fixtures; `fap`, `cpd1a` | open |
| P. Window numerics | `forward.AXIAL_SIZING_FLOOR`, `REFLECTION_MARGIN_DEG`, `STAGE_WINDOWS_STALE` | each side | the four; a second and third family that runs away | open |
| Q. Le Bail passes | `refine.LEBAIL_CONVERGED_REL` | each side | LaB₆ + cBN, `fap`, `cpd1a` | open |
| R. Width terms | `StageResult.width_twins_held`, `ProfileTCHZ:y` unfloored | see below | a real multi-phase fit freeing a twin pair; SRM 660c | open |
| S. Tier-2 citations | `SCHERRER_K`, `BOND_SLACK_ANG`, `STEPS_PER_FWHM_*` | read each citation | none: they stay at tier 2 unless a source fails | open |

**Group A's hard starts, fixed 2026-11-05 before running.** The shipped starts never reached
seven of group A's ten constants on most families (handover, 2026-11-05). So those seven
(`_M_HI`, `_Q_TRIGGER`, `_Q_WINDOW`, `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`,
`_CURVATURE_GATE`, `SLOW_DESCENT_ESD`) run their same arms from harder starts: every phase's
cell lengths displaced +1 % and +3 % on the four families, and cpd-1a with zircon declared at
the shipped start. Each arm is read against the shipped constants from the same start, on the
same bar, and also on whether it changes the fit's verdict: reaching the shipped start's answer
within 0.1 plain esd, or not.

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
- **G.** cpd-1a with zircon declared flips with the intermediate tolerance: zircon's scale sits
  near 2σ, nine structural paths held at 1e-6, the cell walking at 1e-9, `lines_axial` at its
  400-evaluation budget (`2002-batch/waiting.md` § B7).
- **G, from group A's hard starts.** LaB₆ with its cell +1 % takes the scale to 0 in the first
  stage and holds the phase: Rwp 0.86, 9 evaluations, `usable=False` through
  `MODEL_FAR_FROM_DATA`. NAC +3 % keeps NAC, loses CaF₂ to a held scale 0, and reads
  `usable=True`, Rwp 0.139, with `PHASE_UNCONSTRAINED` the only word on it.
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
- **N.** 2002's § The hand rows that stay lists them.
- **O.** Neither set has a stated domain. The interval runs automatically on every moment angle
  the stationary test leaves out, 20-32 refits an angle, and the grid on every `profile_fraction`
  call. The bars are in `tests/test_window_domain.py`. `PARAMETER_INTERVAL_BRACKET_GROWTH` can
  choose between crossings where window recompiles give several.
- **P.** At the closing stage's windows the margin errs 0.186 σ and 0.124 σ at the last points of
  FAP and cpd-1a, moving answers 0.026 and 0.043 esd. An edge rule was built and reverted because
  it freed a scale-B ridge (`waiting.md` § B10). The axial floor reads 0.010 on cpd-1a since the
  twin hold, and 0.582 on LaB₆'s `u`, the two minima 0.24 % apart in χ² (WP-2084). `STAGE_WINDOWS_STALE`
  has one family: four protocols at most 1.73 % against 2 %, the chain cpd-1a → cpd-1b at 73.4 %
  under the pre-2045 schedule, and the which-stages rule rests on the calibrate guide's
  `sample_profile` stage at 12.1 %.
- **R.** `width_twins_held` has one real two-phase family, 11-BM LaB₆ + cBN. Y's floor went on a
  physical argument with one synthetic cost (Y −0.0059 against 0, `lor_size` 55 % low). The test:
  SRM 660c with Y free and with Y ≥ 0, read on the certified cell and a sample's size and strain.
  Under TRF no width row holds, and whether brucite and corundum put a coefficient on ±180 is
  unmeasured. `least_squares._fd_typicals` still reads a width off its lower bound and patches Y
  with `_SIGNED_WIDTHS`, so a caller's X or `lor_strain` with min < 0 takes the offset's step of
  1, an error of 1.4e-3 to 1.5e-2 in a width column. A fix declares which rows are widths as table
  data, a design change.
- **Reading a wrong answer.** The esd yardstick is blind there, since `_shift` skips a row with
  no esd and a lost phase's rows have none, and a two-valued verdict hides how far a fit
  missed. One noise draw is a weak floor on a chaotic start (cpd-1a +3 % reads 3.99 esd). A
  hard start's table carries Rwp too (`2017-batch/group_a_hard_summary.md`).
- **Every refit.** A staged plan carries a path-dependent scatter of up to about 0.16 esd, and 0.5
  in a background term, from its last frozen compile. Polish both arms from one common start or
  the refit measures that scatter. The CPD QPA plan frees exact pairs (X with `lor_size`, Y with
  `lor_strain`, zero with displacement), so read those rows as one sum.

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

- **2026-11-04** — Task added from WP-2086's review: tell a blank frame with structure from a phase whose peaks missed. Numbers re-read from the raw rows. With the synthetic humps the 14 frames span d 0.34-1.49, past the 0.43-1.04 quoted for Kapton, and Kapton's Q is 1.96 at its 21 001 channels. Nothing new measured, no code. PR #1408.

- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the second pass moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

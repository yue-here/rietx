# WP-2017 — The second pass: every surviving tier-3 threshold measured on three families

Milestone: generality · Status: 🔄 2026-11-09 — group A's hard starts run for all ten rows and group H counted on group A's fits (PR #1494); 17 groups open
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
| A. LM stop | `lm._M_HI`, `_M_LO`, `_Q_TRIGGER`, `_Q_WINDOW`, `_LAMBDA_FAIL_FACTOR`, `_LAMBDA_FAIL_FLOOR`, `_CONVERGED_RUNS`, `_CURVATURE_GATE`, `FTOL`, `SLOW_DESCENT_ESD` | one each side of each value, `FTOL` at 1e-8 and 1e-10 | the four, then the hard starts below | measured 2026-11-05; seven closed by ruling; the last three's hard starts run 2026-11-09, their failing case stated, approval to re-date |
| B. Bounded step | `lm._POLISH_FEASIBLE`, `_POLISH_STATIONARY`, `BVLS_MAX_COLUMNS` | each side | Stephens fits on qarr brucite and corundum and one more; FAP Pawley for the column cut | open |
| C. BCCG | `bccg._CONVERGED_FRACTION`, `_CONVERGED_RUNS`, `_SMALL_FACTOR`, `_SMALL_RUNS`, `_CAUCHY_ARMIJO`, `_PCG_TOL`, `_PCG_BUDGET_PER_VARIABLE` | each side | Pawley on `fap`, `nac` and `cpd1a` | open |
| D. Blocked solve | `blocked.DENSE_JACOBIAN_MAX_BYTES` | forced each way | the four | open |
| E. TRF | `least_squares.GTOL`, `XTOL`, `staged.BOUND_HIT_COS_MIN`, `BOUND_HIT_ESD_FRAC` | 1e-8 against 1e-12; the 32-case bound table on a third family | `cpd1a`, corundum Stephens, 11-BM Si SRM 640c | open |
| F. Background pick | `auto.HUMP_TRIGGER`, `AIR_SCATTER_TRIGGER`, `_KNOT_STEP_HUMPY_DEG`, `_KNOT_STEP_SMOOTH_DEG` | near the trigger, each way | the Kapton capillary for a real hump, qarr's weighed mixtures for air | open |
| G. Absent phase | `plan.PHASE_SUPPORT_SIGMA`, its two defaults | 1σ, 3σ, off | a weighed trace phase (the cpd-1 suite), CuO on the CuCr₂O₄ ramp started one FWHM off, cpd-1a with zircon declared | open |
| H. Cell window | `vector.CELL_WINDOW_FRACTION`, `_ANGLE_DEG`, `_PAD_A` | count the stages where it binds | every fit of groups A and G | group A's 298 fits counted 2026-11-09: binds in none; group G's owed |
| I. Position bounds | their removal, 2026-10-20 | free over a narrow range | lab flat plate: `fap`, `lab6`, SRM 1976a | open |
| J. Refined lines | Le Bail and Pawley Kα2/Kα1 | second standard, tabulated ratio | SRM 660c, SRM 1976a, FAP | open |
| K. Far from data | `refine.MODEL_FAR_FROM_DATA_RWP` | both directions; Rwp beside background-subtracted Rwp and Rwp/Rexp | WP-2086's reach table; a sparse-count family | open |
| L. Magnetic solve | `magnetic.SOLVE_MINIMUM_RTOL`, `SOLVE_TOP_K`, `SOLVE_K_TRIALS` | each side | the rare-feature clause: Ba₂FeSbSe₅, Cr₂WO₆, LaMnO₃ | open |
| M. Starts | `structure.BISO_SEED`, `instrument.HARMONIC_WEIGHT_SEED` | the two starts with `closing_window_tol=None` | the four; the synthetic neutron corundum | open |
| N. Hand rows | Le Bail and Pawley intensity seed, `refine._FLAT_AXIS_TEST_DIRECTIONS`, `arpls`'s `max_iter` and `tol`, `vector.FLOOR_SEEDS` | a test for each claim of invariance | named by each test | open |
| O. Domain tests | `interval.PARAMETER_INTERVAL_*` (five), `fraction.FRACTION_PROFILE_FWHM_MIN`, `_N_FWHM`, `_FWHM_MAX_SPAN` | state a domain, then 0.1 σ of a point and 0.1 esd | the two-site Pnma fixtures; `fap`, `cpd1a` | open |
| P. Window numerics | `forward.AXIAL_SIZING_FLOOR`, `REFLECTION_MARGIN_DEG`, `STAGE_WINDOWS_STALE`, `report.NOMINAL_AXIAL_APERTURE` | each side | the four; a second and third family that runs away | open |
| Q. Le Bail passes | `refine.LEBAIL_CONVERGED_REL`, `StageSpec:lebail_tol`, `report.schemas.LEBAIL_GAP_CYCLES` | each side | LaB₆ + cBN, `fap`, `cpd1a` | open |
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

**Group A's open rows, 2026-11-05.** `FTOL`, `_CONVERGED_RUNS` and `_M_LO` gave one answer from shipped starts and owe the same nine hard starts, for a failing case. Run 2026-11-09 (handover): one answer at the answer from every start that reaches it, and a failing case on the starts that miss; their approval dates predate it, so the maintainer re-dates or rules. Seven rows closed by the maintainer's ruling of 2026-11-05: they stay at tier 3 on a named synthetic case, and a later group treats a constant its families barely reach the same way (`docs/milestones/generality.md` § The rule).

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
- **P, from WP-2054 (PR #1430).** `NOMINAL_AXIAL_APERTURE` (0.02) needs a third family. On SRM
  660c the action fires at 0.005, 0.01 and 0.02 and not at 0.05, and cpd-1a, -1c and -1f behave
  the same way at 0.02. It is a separate row from `AXIAL_SIZING_FLOOR` and no longer reads it.
- **Q, from WP-1542 (PR #1434).** The held SNIP on PbSO₄ and #726 was not re-measured with
  settled partitions. `StageSpec:lebail_tol` (1e-7) joined the audit table at tier 3 on five
  families of six patterns, with FAP as its stated failing case (a pair 1e-4 Å apart, 1.23 σ at
  that peak). Neither bar reads the split of such a pair. `report.schemas.LEBAIL_GAP_CYCLES`
  (5 plain cycles from flat) was left alone and now sits beside a partition that runs to a
  tolerance. Both are this WP's to weigh in its second pass.
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

- **2026-11-09** — The three solver stop constants left open on 2026-11-05 now have the evidence their approval asked for. From every harder start that still reaches the right answer, moving `FTOL`, `_CONVERGED_RUNS` or `_M_LO` either way changes no refined number by more than a quarter of the bar, on three families. From the starts that miss, they choose which wrong minimum the fit lands in, which is the failing case the judge asked for. The cell window that guards a barely-seen phase's cell (group H) never bounded anything in group A's 298 fits: the absent-phase hold already holds every cell it would bound, so switching the window off changed no fit by a single bit. Its removal, which the B8 ruling makes the exit, still waits on group G's fits and on one case read off the code.

  *Done.* PR #1494. `group_a.py` extended (commits e6a37b511, fabfe9b3f): the hard starts run all ten constants, every fit records group H's count (`window_spied`: per solve, which phases took the window, which free cell columns it bounded, which ended on an edge), each start gets a `CELL_WINDOW` arm with `_freeze_cell_windows` declaring no phase, and `--window control` is the count's positive arm (LaB₆ +1 % with the start hold off). Rows rewritten in `_audit.py`: `lm.FTOL`, `lm._CONVERGED_RUNS`, `lm._M_LO` (evidence gains the hard starts, failing case and start domain; the WP-2017 sentence in their grounds, written by the 2026-11-05 session, now says what was run) and the three `CELL_WINDOW_*` rows (evidence gains group H's count; grounds untouched). Tier and value unchanged on all six. Summaries committed: `2017-batch/group_a_hard_20261109_summary.md` (all ten constants, nine starts) and `2017-batch/group_h_summary.md`. Raw rows not committed; they sit in the workstation job's return directory on the Mac that ran this (job `wp2017h`), and PNGs went to that job's `tests/output/`.

  *Measured* (the workstation, Linux x86_64, `rietx-py312` venv with this tree on `PYTHONPATH`, rietx-kernels 1.4.0, numpy 2.5.3 against the Mac's 2.5.4, compiled tier on, 12 workers of one kernel thread, at `fabfe9b3f`; 43 min wall, one task, 880 MB peak):

  | Constant | Arms acting at an answer | Worst there, plain esd | No reference moved past | On starts that miss |
  |---|---|---|---|---|
  | `FTOL` | 1e-8: FAP, NAC, cpd-1a; 1e-10: NAC, cpd-1a (FAP closes on exhausted fp64 first) | 0.0012 (cpd-1a +1 %, 1e-8) | 3.6e-4 esd | SRM 660c +3 %: 1e-8 moves 0.118 against noise 0.053; polished, shipped and 1e-8 in different wrong minima (Rwp 0.823, 0.861; answer 0.087) |
  | `_CONVERGED_RUNS` | both on FAP, NAC, cpd-1a | 0.0245 (cpd-1a with zircon at 5, at its noise 0.0245); else 0.0011 | 4.4e-4 esd | NAC +3 %: both arms lose NAC, Rwp 0.139 to 0.80, polished S 33× shipped's; cpd-1a +3 %: polished S 0.65× (2) and 1.40× (5); SRM 660c +3 %: 2 moves 51.4 esd |
  | `_M_LO` | 0.8: FAP, NAC, cpd-1a; 0.2: FAP +3 %, cpd-1a (third family SRM 660c from its shipped start) | 0.0247 (cpd-1a with zircon at 0.8, at its noise 0.0245); else 1.7e-4 | 2.2e-4 esd | NAC +3 %: 0.8 loses NAC (polished Rwp 0.790), 0.2 within noise; cpd-1a +3 %: 0.8 Rwp 2.18×; SRM 660c +3 %: 0.317 and 0.111 against noise 0.053 |

  Start domain, per family: FAP's cells within 3 %, NAC's and cpd-1a's within 1 %, SRM 660c only its shipped start, since +1 % already misses on every arm. No arm of the ten changed which of the nine starts reach the shipped start's answer. The same five reach it as on 2026-11-05. Reproduction across platforms and heads (macOS arm64 at `1ed7a9517` then, Linux x86_64 at `fabfe9b3f` now): from the shipped starts `_CONVERGED_RUNS` 2 on cpd-1a reads 0.0023 esd (0.0024 then) and `FTOL` 1e-8 0.0011 (the same); the five reaching starts and LaB₆ ±, NAC +3 % agree to the fourth digit in Rwp. cpd-1a +3 %, whose noise arm reads 7.29 esd, lands in a different wrong minimum (Rwp 0.368 against 0.622), so `SLOW_DESCENT_ESD`'s two acting starts are now LaB₆ +3 % and cpd-1a with zircon. One fit hit the 1200 s guard (cpd-1a +3 %, `_M_HI` 5) and one polish round (cpd-1a +3 %, `_M_LO` 0.8).

  Group H: 2432 solves over 298 fits (every arm but the window's own, 4 shipped and 9 hard starts). A phase took the window in 339 solves, all on hard starts, and a free cell column was bounded in none, so no edge was reached. Switched off, all 13 starts are bit-identical in evaluations and answer. The reason is structural: `refine._hold_unsupported_phases` holds every free column moving only phases under `PHASE_SUPPORT_SIGMA` on `phase_support` at the stage's start values, and `least_squares._freeze_cell_windows` then windows those same phases on the same screen at the same values. The positive arm (start hold off, LaB₆ +1 %) windows a free cell in 6 of 14 solves, so the count can see one.

  *Gotchas.* `rietx.refine` as an attribute is the function; the spy reaches the module through `importlib`. The workstation's venv metadata says 1.11.0.dev0, so each result is stamped `1.12.0.dev0+g<sha>` with a warning; harmless. A second wsrun pass on one job leaves the first pass's `DONE` file, so `watch_wsjob.sh` reported done at once; wait on the runner's pid and `results/<id>.json` instead.

  *Not done, and why.* Removing the window from single fits, B8's exit, is not in this PR. The family set fixed before running is groups A and G, and G has not run. Read off the code and not run: a caller's tie whose free column is an unseen phase's cell and also moves a visible phase is declined by the hold (the column reaches a seen phase), while the window, keyed on the path's name, still bounds it. A removal should answer that case first.

  *Review.* `/code-review high --fix` ran in a forked context whose working directory was the main checkout, not this worktree: it reviewed another branch there and left eight uncommitted files in that checkout (saved as a patch in this runner's scratch directory; not reverted, the user's call). The review of this branch was then done by a read-only agent in the worktree. Five findings on `group_a.py`, all fixed in 09758fc43: the window summary now names fits it could not count and prints an errored arm's error, a sweep resumes only rows from its own head, the raw directory is created, the positive arm overwrites its rows, and `hard_summary` tolerates a row with no measures. Two declined: the spy omits the tie-window intersection `bounds()` applies after `cell_window` (reachable only by a caller's tie with a finite-bounded dependent; none in these fits), and no arm exercises the edge test on a window that binds (the positive arm's cell ends mid-window; recorded in the rows).

  *Fast selection* on the tree before the review fixes and row corrections (both touch only the batch script and row text): 14341 passed, 416 skipped, 32 xfailed in 13 min, worktree `[dev]` venv, macOS arm64. No test added. `tests/test_audit_table.py`: 23 passed after the last row edit; `tests.audit_delta` exit 0. Full suite not run: no measured number can move.

  *Generality.* The judge (Opus, reading `.claude/agents/generality-review.md`) on the six rows as first written; the numbers and wording it corrected are fixed in the rows (`_CONVERGED_RUNS`' worst 0.0156 → 0.0245, `FTOL`'s fp64 sentence, the start domain per family, the window rows' single-fit scope, timeout and mid-window positive arm). Its sections, unedited:

  ##### `rietx.optimize.lm.FTOL`

  **Verdict: weak.** The case for keeping the value is stronger. Two problems remain. The tighter side (1e-10) can be read on two families only. The stated start domain is wider than what was measured.

  | Q | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1 | Grounds: "the last tolerance of the schedule" | Sets where the last declared stage and the closing stage stop. | clear |
  | 2 | `ambiguity` empty, which a constant row may leave empty | First kind for having a stop at all. Only the value is on trial. | fine |
  | 3 Against | Evidence: on SRM 660c (the LaB₆ standard) +3 %, "1e-8 moves 0.118 esd against a noise arm of 0.053 at 0.69x evaluations… Rwp 0.823 and 0.861; the answer reads 0.087" | Every figure matches the summary (0.1179, 0.0534, 0.686, polished shipped 0.8225, answer 0.0874). After polishing, 1e-8 and shipped end 75.9 esd apart (Polish table). This is one start on one family. On cpd-1a +3 % (IUCr round-robin sample 1a), 1e-8 moves 0.28 esd, which is under that start's noise of 7.29. The 11-05 dissent still stands: GSAS-II and FullProf stop near 1e-3 (not rechecked here). | thin but real |
  | 4 For | "worst 0.0012 plain esd (cpd-1a +1 % at 1e-8), no reference moved past 3.6e-4 esd" | Raw: 0.001235. The largest reference move is 3.57e-4 (wt_fluorite). Reach is unchanged on every arm, as the per-constant table shows ("verdict changes: none"). | strong |
  | 5 Tier | 3 | Right. 1e-9 is outside GSAS-II's and FullProf's defaults. No `invariant` claim. | ok |
  | 6 Families | 1e-8 on FAP, NAC and cpd-1a; 1e-10 on NAC and cpd-1a | Confirmed. **1e-10 reaches two families.** The row says "FAP closing on exhausted fp64 before either tolerance". The raw `terminations_changed` shows that FAP's *shipped* closing stage stops on `ftol_runs` (1e-9). Only the 1e-10 arm hits `exhausted_fp64`, with an identical answer. The conclusion survives but the wording is wrong. **The start domain "cells within 1 % of the answer" is too wide.** SRM 660c +1 % misses on shipped and on every arm, after 9 evaluations. So on SRM 660c the domain is the shipped start only, while FAP holds out to +3 %. All four families are development data. | count short on the tight side; domain overstated |
  | 7 Record | none given | `StageResult.termination` (`ftol_runs` / `exhausted_fp64`). | adequate |

  What would change the verdict: a third family that reads 1e-10 at an answer (or a synthetic case, per the 2026-11-05 ruling), or a maintainer ruling that exhausting fp64 counts as the floor. Also a domain sentence written per family.

  Author's answer: agreed; wording and domain fixed. The 1e-10 side cannot reach a third family on these fits because fp64 stops first, which is the maintainer's to rule as a floor or not (*Next*, 1).

  ##### `rietx.optimize.lm._CONVERGED_RUNS`

  **Verdict: holds, with one wrong number.** The case for keeping the value is stronger, and the failing case is real and strong.

  | Q | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1 | "decides where a solve stops" | How many small steps in a row count as converged. | clear |
  | 2 | empty | First kind; in effect a numerical setting. | fine |
  | 3 Against | "on NAC +3 % both arms lose NAC, Rwp 0.139 to 0.80… polished S 33x; on cpd-1a +3 % polished S 0.65x (2) and 1.40x (5); on SRM 660c +3 % 2 moves 51.4 esd against… 0.053" | All confirmed: Rwp 0.802 and 0.809, S ratio 33.117, 0.647, 1.400, 51.39. The NAC phase is lost: cell 10.56 Å against 10.25, one Biso near 3×10⁵ Å². Two things are not in the row. Arm 2 also leaves SRM 660c's displacement 24.7 esd further from its reference, so shipped sits nearer there. And the 0.65x polish did not settle (5 rounds, `settled` False). | strong |
  | 4 For | "worst 0.0156 plain esd (cpd-1a with zircon at 2, under its noise arm's 0.0245)… no reference moved past 4.4e-4" | **0.0156 is not the worst.** On the same start, arm 5 reads **0.02446** (raw and Every-arm table), against a noise arm of 0.02454. The row should say "worst 0.0245 (cpd-1a with zircon at 5, at its noise)". The largest reference move is 4.32e-4 (wt_zincite, zircon arm 5), so the 4.4e-4 bound is true but loose. Both arms act at an answer on FAP, NAC and cpd-1a. | strong; one number wrong |
  | 5 Tier | 3 | Right. | ok |
  | 6 Families | three from hard starts (FAP, NAC, cpd-1a), four from the shipped starts | Confirmed. All development data. The start domain is overstated as for `FTOL`. | met |
  | 7 Record | none given | `StageResult.termination`. | adequate |

  What would change the verdict: nothing, beyond correcting the worst-case figure and the domain sentence.

  ##### `rietx.optimize.lm._M_LO`

  **Verdict: holds.** The case for keeping the value is stronger. The 11-05 gap was that 0.2 reached only two families. FAP +3 % now closes it.

  | Q | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1 | "decides where a solve stops" | The floor on r_u (actual over predicted decrease) used when λ (the damping) shrinks. It shapes the path. | row's words loose (pre-existing) |
  | 2 | empty | A solver-path setting. | fine |
  | 3 Against | "on NAC +3 % 0.8 loses NAC, Rwp 0.139 to 0.79 polished, while 0.2 sits within that start's noise; on cpd-1a +3 % 0.8 reads Rwp 2.18x…; on SRM 660c +3 % 0.8 and 0.2 move 0.317 and 0.111 esd against… 0.053" | All confirmed: polished 0.790, 0.3221 against 0.322, 2.18135, 0.3172 and 0.1113. Not in the row: the 0.790 polish did not settle (5 rounds), and the cpd-1a +3 % 0.8 polish timed out. "Loses NAC" holds in substance (cell 10.63 Å, Biso up to 1.1×10⁴), though its weight fraction still reads 0.93. | strong |
  | 4 For | "worst 0.0247 (cpd-1a with zircon at 0.8, at its noise arm's 0.0245) and otherwise 1.7e-4, no reference moved past 2.2e-4" | Confirmed: 0.02467, 1.672e-4, 2.20e-4. | strong |
  | 5 Tier | 3 | Right. Coelho's paper is still unread (11-05 finding). | ok |
  | 6 Families | 0.8 on FAP, NAC and cpd-1a; 0.2 on FAP +3 %, cpd-1a, and SRM 660c's shipped start | Confirmed. The fabfe9b3f shipped-start rerun has SRM 660c at 0.2 moving 1.0e-7 against a noise of 8.1e-8, so it is reached but sits at noise. FAP +3 % at 0.2 (2.45e-6 against 5.7e-7) is the real third family. The domain is overstated as for `FTOL`. | met |
  | 7 Record | none given | None; λ never reaches `StageResult`. | acceptable for a path constant |

  What would change the verdict: a reaching start where 0.2 moves an answer past its noise and past the bar.

  ##### `rietx.params.vector.CELL_WINDOW_ANGLE_DEG`

  **Verdict: holds as an interim row.** The evidence for removal (it binds in no measured fit) is now stronger. Deferring removal until group G is run is principled, because the family set was fixed before running.

  | Q | Author's answer | What I found | Verdict |
  |---|---|---|---|
  | 1 | Grounds: "a guard on a barely-seen phase's cell" | Bounds the cell of a phase under `PHASE_SUPPORT_SIGMA`, once per stage. | clear |
  | 2 | empty | First kind (no refiner lets an unseen cell walk). Only the size is on trial. | fine |
  | 3 Against | "a free cell column was bounded in none… switched off all 13 starts are bit-identical" | Every count checks: 92+206 = 298 fits; 713+1719 = 2432 solves; 161+100+2+23+30+23 = 339 solves where a phase took the window; 0 where a free cell column was windowed; "no, bit-identical" on all 13 starts. The mechanism also checks in the code. `_freeze_cell_windows` (least_squares.py:2944) reads the same `phase_support` screen at the stage's start values that `_unsupported_phase_paths` holds on, and the hold also reads the prior stage, so it holds a superset. Not in the row: "at every arm" omits the one uncounted timeout (cpd-1a +3 %, `_M_HI` 5), which the summary does name. | strong on the fits measured |
  | 4 For | none given in the row | The handover names one case, read off the code and not run: a caller's tie that moves an unseen cell and also a seen phase. The hold declines it and the window still bounds it. The row omits it. The positive arm shows the count can see a windowed column (6 of 14 solves). But on and off read the same Rwp of 0.861637 and the same 15 evaluations, with the nearest edge at 0.5 (mid-window). So no fit in this change shows the window *binding*. | none measured |
  | 5 Tier | 3, TOPAS § 2.17 (row says checked) | Unchanged; not rechecked by me. | ok |
  | 6 Families | four protocol families | A phase was windowed on three (SRM 660c, NAC, cpd-1a), only from hard starts and never on FAP. **Single fits only.** `_freeze_cell_windows_multi` (least_squares.py:3067), the joint-refinement path, was neither patched nor spied, and the row does not say so. Group G is owed. | partial |
  | 7 Record | none given | No record field reports a window; the count needed a spy. | none |

  What would change the verdict: group G's count. A test for the tie case. For the row to stay kept, an injected case where the window binds, as § The rule asks of a guard that ordinary fits never reach. The tests in `tests/test_absent_phase.py` check only the window's arithmetic.

  ##### `rietx.params.vector.CELL_WINDOW_FRACTION`

  **Verdict: holds as an interim row, as `CELL_WINDOW_ANGLE_DEG`.** The evidence text is identical and every number checks. The same omissions apply: single fits only, the tie case, the one timeout, and no record field. When removal comes, `CELL_SAFETY_FRACTION`'s docstring defines it as three times this value (vector.py:564).

  What would change the verdict: as `CELL_WINDOW_ANGLE_DEG`.

  ##### `rietx.params.vector.CELL_WINDOW_PAD_A`

  **Verdict: holds as an interim row, as `CELL_WINDOW_ANGLE_DEG`.** The text is identical and the numbers check. The same omissions apply. When removal comes, note that `CELL_SAFETY_ANGLE_DEG = 3.0 * CELL_WINDOW_ANGLE_DEG` (vector.py:570) depends on the angle row.

  What would change the verdict: as `CELL_WINDOW_ANGLE_DEG`.

  *Settled by Claude.* Groups A (rest) and H together, H needing no fits beyond group A's own; rerunning all of group A on the workstation rather than only the 54 owed fits, since the hold that decides group H acts per stage on every arm; the three rows' grounds rewritten only in the sentence this WP added on 2026-11-05.

  *Next.* (1) The maintainer re-dates the approval of `FTOL`, `_CONVERGED_RUNS` and `_M_LO` or rules otherwise: the condition they were approved under is met, with `FTOL`'s tighter side readable on two families only, since fp64 stops the others first. (2) Group G (absent phase), whose fits also finish group H's count; then the window's removal from single fits, answering the tie case above, or, if kept, an injected case where it binds; `CELL_SAFETY_FRACTION` and `CELL_SAFETY_ANGLE_DEG` are defined as three times the window's constants and need their own value when it goes. (3) Group B or C next by the list's order.

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

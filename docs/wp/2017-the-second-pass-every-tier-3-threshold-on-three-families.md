# WP-2017 — The second pass: every surviving tier-3 threshold measured on three families

Milestone: generality · Status: ⬜
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
both phrases for the list). They group by the fits they share, so the work is perhaps
ten to fifteen fit campaigns, not one per row:

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

### Inherited

- **From WP-2002 (2026-10-23, 9th session, PR #1113): the twin hold and the floor removal moved three start rows, and give two rows new families.** (1) `BISO_SEED`: cpd-1a's Biso starts now differ by 15.68 plain esd on zincite's `lor_strain` (0.070 before), because the width twin hold keeps the X/Y split `qpa_plan`'s instrument-only stage lands on, a strict xfail (decision 1(a)); FAP and NAC stay at 0.000. The row's evidence now rests on two families. (2) The intermediate-tolerance row on cpd-1a with an absent zircon reads 0.035 (0.185 before) and the axial sizing floor on cpd-1a 0.010 (0.138 before); both strict xfails went. (3) `StageResult.width_twins_held` (tier 2) has one real two-phase family (11-BM LaB6 + cBN) and the synthetic and CPD fits in its row; a second real multi-phase family freeing a twin pair would test it. (4) `ProfileTCHZ:y`'s floor went on a physical argument (a constant Lorentzian projects to Y < 0) with one synthetic cost (`tests/test_v02_core.py`: Y −0.0059 against a truth of 0, sample `lor_size` 55 % low); what real lab calibrations do with Y unfloored is unmeasured; the judge's test is SRM 660c refined with Y free and with Y ≥ 0, read on the certified cell and a sample's size and strain. (5) Under TRF no width row holds, and whether brucite and corundum put a coefficient on the ±180 far bound under the hold is unmeasured. (6) `optimize.least_squares._fd_typicals` still decides a row is a width from a lower bound ≥ 0 and patches Y with a name list (`_SIGNED_WIDTHS`); a caller's X or `lor_strain` with min < 0 takes the offset's step of 1, which put 1.4e-3 to 1.5e-2 errors into width columns (code review, declined as a design change: declare which rows are widths as table data). This entry supersedes the zircon and axial-floor readings in the two entries below.

- **From WP-2002 (2026-10-23, 8th session, PR #1113): the generality judge's owed measurements.** Tier 3 by the maintainer's delegation, each waiting on its three-family evidence here: `optimize.lm.FTOL` (1e-9, never varied: refit the four start-test families at 1e-8 and 1e-10, bar 0.1 plain esd); `schemas.structure.BISO_SEED` and `schemas.instrument.HARMONIC_WEIGHT_SEED` (start-invariant only behind the closing stage, so measure the two starts with `closing_window_tol=None`); `schemas.interval.PARAMETER_INTERVAL_BRACKET_GROWTH` (2.0, lifted by B14; can choose between crossings where window recompiles give several). Four hand rows claimed invariant with no test: the Le Bail/Pawley intensity seed, `refine._FLAT_AXIS_TEST_DIRECTIONS`, `arpls`'s `max_iter`/`tol`, and `params.vector.FLOOR_SEEDS` (a B10 numerical setting); 2002's § The hand rows that stay lists them. The width floors' removal (the maintainer's 2026-10-23 answer) lands under TRF without the per-coefficient guard; its TRF measurement is in 2002's 8th-session entry.

- **From WP-2002 (2026-10-23, 8th session, PR #1113): two domain tests, handed here by the maintainer at 2002's close.** The profile-interval settings (`PARAMETER_INTERVAL_CHI2_TOL` 0.01, `_MAX_REFITS` 60, `_SETTLE_RUNS` 4, `_XTOL` 1e-3) and the fraction-profile width grid (`FRACTION_PROFILE_FWHM_MIN` 0.01, `_N_FWHM` 11, `_FWHM_MAX_SPAN` 0.5, lifted from an inline literal by B14) sit at tier 3, approved 2026-10-19 on B10 option 2: tier 1 once a test bounds each setting's error over its claimed domain. No domain has been stated for either; the interval runs automatically on every moment angle the stationary test leaves out (B2), 20-32 refits an angle on the two-site Pnma fixtures, and the grid on every `profile_fraction` call, which the skill sends every agent to. The bar the earlier domain tests used was 0.1 of a point's σ at fixed parameters and 0.1 plain esd after a common-start polish (`tests/test_window_domain.py`).

- **From WP-2002 (2026-10-22, 6th session, PR #1085).** The eighth round kept `REFLECTION_MARGIN_DEG` at 0.5° and `AXIAL_SIZING_FLOOR` at tier 3, both for this pass. The caller-tier ruling moved `GTOL` and `XTOL` (1e-12, defaulted inside the opt-in TRF solver, SciPy's own 1e-8) from caller to tier 3, with their domain test owed: WP-1109's 1e-8 trial is their only evidence (1.22-1.27× faster on cpd-1a, 1.04× slower on cpd-2, corundum's strain anisotropy past the Stephens suite's bar).

- **From WP-2002 (2026-10-21, 5th session, PR #1085).** The sixth round landed: the four intermediate-tolerance rows at tier 3 (within 0.042 plain esd on four protocols behind the closing stage, 0.185 on cpd-1a with an absent zircon), `HARMONIC_WEIGHT_SEED` invariant, `CLOSING_WINDOW_TOL` tier 1 on three of four families. At the closing stage's windows `REFLECTION_MARGIN_DEG` errs 0.186σ and 0.124σ at the last points of FAP and cpd-1a (answers 0.026 and 0.043 esd). The sixth round's Q1 proposed the closing stage's rule (tight where the answer is computed) for the six other failing numerical settings (the FCJ node rule, the margin, the axial and magnetic sizing floors, `A5_CLIP`, the texture sampling); not built, and the maintainer has not ruled on it. Ruled and built on 2026-10-21, the seventh round (`2002-batch/rulings.md`, `waiting.md` § B10): the FCJ closing rule, `A5_CLIP` and the texture polish at tier 1, the magnetic floor invariant behind the closing stage on one family; the margin's edge rule at the closing windows was built and reverted (it freed a scale-B ridge on `tests/test_scale_b_ridge.py`'s synthetic narrow scan, `waiting.md` § B10), so the margin still errs 0.186σ and 0.124σ there; the axial floor still misses on cpd-1a (0.138 plain esd behind the closing stage), and the declared stages' FCJ, margin and window constants stay tier 3. This WP's second pass inherits the three-family evidence for each.
- **From WP-2002 (2026-10-21, PR #1085).** (1) The absent-phase hold flips with the intermediate tolerance: cpd-1a with zircon declared (a phase the sample lacks), LM, the QPA protocol. At `intermediate_ftol` 1e-6 the last stage holds nine zircon structural paths and `PHASE_UNCONSTRAINED` fires; at 1e-9 nothing is held, the zircon cell walks, and `lines_axial` hits its 400-evaluation budget. Zircon's scale sits near 2σ in plain esd, by `PHASE_SUPPORT_SIGMA`'s 3σ, so it is a case for that threshold's three families. (2) The CPD QPA protocol (`qpa_plan`) frees instrument and sample width terms that pair exactly (x with `lor_size`, y with `lor_strain`, zero with displacement), so the start picks the split; read those rows as one sum. (3) A staged plan's answer carries a path-dependent scatter of up to about 0.16 esd (0.5 in a background term) from the last stage's frozen compile, and one extra stage recompiled at the answer removes most of it. A refit on either side of a threshold should polish both arms from one common start, or it measures the scatter. Measurements in `docs/wp/2002-batch/waiting.md` § B7 and § B8 and B9.

- **From WP-2045 (2026-10-25, PR #1161): `FTOL` now ends two stages of every plan, and the intermediate-tolerance rows were re-measured.** The last declared stage runs at `optimize.lm.FTOL` as well as the closing stage, so refitting the start-test families at 1e-8 and 1e-10 moves both. The four intermediate-tolerance rows' shared evidence now reads 0.000 esd on FAP, cpd-1a and NAC, 0.009 on cpd-1a with zircon declared (your inherited 0.035), and 8.82 on SRM 660c's mirrored axial minima, the one strict xfail (`tests/test_staged_start_invariance.py`, macOS arm64, `[dev]`). Converging the last declared stage costs 1.04-1.07× the evaluations, so the rows' "1.00-2.15x fewer" now nets that out.

- **From WP-2047 (2026-10-25, PR #1171): `STAGE_WINDOWS_STALE` is a new tier-3 row on one family.** Each stage records `StageResult.window_loss`, the Bragg intensity its frozen windows drop at its answer against windows sized there (`forward.window_loss`), and the code fires past the stage's own `window_area_tol` on the last stage and the one before a closing stage. The threshold is no new number, but its separation is measured on one family: the four protocols' stages at most 1.73 % against 2 % (2e-5 against the closing 1e-3), and the QPA chain cpd-1a → cpd-1b under the pre-2045 schedule 73.4 %. The which-stages rule is a session judgement resting on one more fit: the calibrate guide's `sample_profile` stage ends at 12.1 % and the stages after it repair it. A second and third family that run away, or that stay stale behind later stages, would test both halves.

- 2026-10-26 issue triage: #1052 (mustachefeeling, 2026-10-19) offers three held-out families for the milestone's close, and says the reporter will run them at the open and the close: Zr₆(BDC)₃(Fum)₃ on Diamond I11 (Tollitt et al. 2021, Angew. Chem. 60, 26939; pattern deposited CC BY 3.0), HfIn on a lab Empyrean, Cu Kα₁/Kα₂, flat plate (Oliynyk et al. 2018, Inorg. Chem. 57, 7966; not deposited, kept local by the reporter), and CrCl₂(pyrimidine) on ILL D1B at 1.5 K and 30 K, k ≠ 0 (Pitcairn et al. 2023, JACS 145, 1783; data doi:10.17639/nott.7257). Checked against the tree at c0e32ab29: none of the three is in `tests/data/README.md`, and the milestone's named held-out family is still only the Nd₂Ru₂O₇ pair (`11a68d96e`, 2026-10-19). Until the maintainer rules on #1052, do not use any of the three as second-pass evidence here: a public download makes the MOF and the magnet easy to reach for, and using one would end its use as held-out evidence.

- Decided 2026-10-26 (maintainer, #1052): all three offered families are adopted as held-out beside Nd₂Ru₂O₇ (`docs/milestones/generality.md` § Acceptance). So none of them is audit evidence in this pass, nor in any pass before the milestone's close, when they are spent into development data (ruled 2026-10-27, replacing the 2026-10-26 "for good").

## Non-goals

- New actions or new thresholds. A measurement that suggests one goes to the maintainer.
- The chain actions (WP-2003) and the report's verdicts (WP-2004), which run their own
  second passes.

## Tasks

- [ ] The list: every row whose evidence or grounds name the second pass or refits on
      either side, grouped by the fits they share, written to a table in this file.
- [ ] Per group, the three families and the reference each is measured against, chosen
      before running (a family chosen after seeing its answer is not evidence).
- [ ] Run each group; per row, the answer either side of the threshold and the reference
      distance, with obs/calc/diff PNGs to `tests/output/` for each refit used.
- [ ] Each row's evidence line updated; a row a test now bounds moves to tier 1 or
      `invariant` with the test named; a row that fails goes to a batch for the maintainer.
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

- **2026-10-20** — Filed by WP-2002's session at the maintainer's request ("split"): the second pass moves here so that 2002 closes on its owed tests and B14's lifts. Nothing measured yet.

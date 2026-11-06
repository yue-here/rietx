# WP-1955 — a column at a zero aperture, and a column the agreement matrix cannot see

Milestone: unscheduled · Status: 🔄 2026-11-03 — tasks 1-5 landed (PRs #1321, #1372): the exact column and the lift off a zero aperture; tasks 6-8 open
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-03 — the stall and the collapse are fixed (tasks 2 and 5, PR #1372); left are the start value's evidence across families, the Gaussian-width floor and suggest's scoring of a zero aperture

## Goal

The numpy analytic `axial_hl` column at H/L = 0 matches the feasible side's
one-sided difference, as the jax and torch columns already do. The
cross-backend agreement matrix checks a small column at its own scale, so a
column tiny beside the largest is checked rather than skipped. Whether the
column error moved any reported number is measured and written down.

## Context

**Where it came from.** WP-1953's second session (2026-10-12, PR #918), two
review findings it declined because they reach beyond that WP. Measured there
on macOS arm64, `[dev,jax,torch]`, Python 3.12.10.

**The column.** WP-1953 made one FCJ aperture at 0 the h → 0⁺ limit, so LM's
exact bounded step now lands H/L on 0 (`fcj.fcj_live`, `test_e8`'s verify
stage). On `test_cross_backend.py`'s `axial_one_zero` config the `axial_hl`
column at H/L = 0 has a one-sided central difference of norm 0.04696. jax and
torch meet it to rel-L2 1.5e-3
(`test_a_zero_aperture_column_meets_its_one_sided_difference`). The numpy
analytic column has norm 0.0486 and sits 0.240 rel-L2 off the same reference.
No test checks the numpy column there. The fix the review named changes how
`model/forward.py` differences the FCJ nodes at a bound, so it moves every fit
that frees an axial ratio from 0.

**Why it can matter.** A row on its bound stays in the covariance (root
CLAUDE.md, the equilibrated normal matrix, WP-1929), so the esds of S/L and its
neighbours at H/L = 0 read this column. The bound test reads the residual's
cosine with it (`LSQOutcome.residual_cosine`, WP-1434). Neither consequence is
measured.

**The matrix's cut.** `test_cross_backend.py` treats a column as dead when its
norm is under `DEAD_COL_FRAC` (1e-6) of the largest column. The axial column at
H/L = 0 is 0.047 against a largest of 1.82e6, so every backend row skips it.
That is why the traced columns' error (a jax column of norm 3360 against the
reference's 0.047, from a tie at the FCJ kink) went
unseen until CI's jax job hit a different config, and why #918 added a
dedicated test. Any column small beside the largest escapes the same way: a
moment angle near a fixed direction, a weak phase, a parameter in small units.
WP-1953 found a third of all fast-suite LM solves start with a column under
1e-6 of the largest.

**A sibling not probed.** `caglioti.py`'s `xp.maximum(g2, _MIN_GAMMA_G2)` ties
when U and V are both zero beside W on its floor. It is the only other
`minimum` or `maximum` on the traced path found sitting on a bound LM lands on.
`sharp_widths` covers W on its floor with U and V nonzero.

**Both apertures at zero** (folded from `### Inherited` on 2026-11-02).

- **From WP-2060 (2026-11-02): `profile_interval` no longer answers [0.0, 0.0] by its step alone.** A first probe past the Δχ² threshold now steps back in from the fit until one lands inside, so the axial-ratio profile of #1075's repro 1 should find a real end or a lower χ² (`fit_is_minimum=False`) instead of confirming the floor. Not re-run on repro 1. Re-measure it here before building on WP-2060's Context, which quotes the old [0.0, 0.0].
- **From WP-2003 (2026-10-26): both apertures at 0 cost an answer, not only an esd.** CPD
  sample 1b fitted independently under `qpa_plan()` ends with S/L and H/L both on their
  floors at 0 (S/L esd 251). A warm refit of 1c from that state collapses: Rwp 10.724 with
  the closing stage off, 0.791 with it on (S/L to 64.8 and 4284, `STAGE_WINDOWS_STALE`),
  against the independent 1c's 0.10901. The same start with S/L lifted to 0.011 converges at
  0.10881 in 39 evaluations. Reading: the column at the double zero is nearly flat, the first
  LM step is tens to thousands of units, and the windows sized from `AXIAL_SIZING_FLOOR` at
  compile are stale for the rest of the solve. The default CPD chain escapes only because its
  own 1b ends off the floor. Measurement and reproduction: `docs/wp/2003-batch/clashes.md`
  X17 (`measure_reseed.py --family cpd-noclose --arm status_runaway`, and the probe it
  describes). A remedy is this WP's shape one rank out, WP-1938's rule: a floor or a lift where
  the column is live, and it moves every fit that frees an aperture from 0.

- **2026-10-26 issue triage: #1075 repro 1, LM stops with both axial ratios at 0
  on `lab_bragg_brentano` from the constructor's defaults, and calls it
  converged.** Checked against the tree at c0e32ab29 (1.11.0.dev0, macOS arm64,
  numpy), the issue's script with `auto_background(...).background`: Si, Cu Kα,
  truth S/L 0.035, H/L 0.025, transparency 0.0005 (not refined by the plan),
  seed 1. The fit ends `converged`, Rwp 0.0834, S/L = H/L = 0.0 ± 103.8,
  `at_bound` True, `FLOOR_HIT` (plus `FLAT_DIRECTION`, `HIGH_CORRELATION`,
  `RESOLUTION_UNCONSTRAINED`). One more LM stage moves nothing; one TRF stage
  over the same free set reaches Rwp 0.0454 with 0.0329/0.0267, Δχ² −15 905 =
  −1 198 χ²_red·f²; LM from 1e-4 stops at 8e-5. `profile_interval` on S/L
  returns [0.0, 0.0] with `fit_is_minimum=True`. Since the issue's run on
  `d885ade2` the bound flag has started firing, and the profile has stopped
  noticing. Mechanism (the reporter's): the FCJ shift is quadratic in the
  apertures, so both columns are ~1e-6 of the largest at 0, the same scale this
  WP's matrix cut skips, and the way down is a joint move with zero,
  displacement and the widths that Gauss–Newton cannot see from a vanishing
  column. Without the transparency LM left 0 in 42 of 42 fits. This is the
  driver's handling of a small column, which this WP's non-goals give to
  WP-1953; 1953 is closed and its fix does not reach this case, so it lands
  here. Re-rated P3 → P2.

- **2026-11-02, from WP-1467 (closing): the Gaussian-width floor is this WP's
  class one parameter over.** Both bullets came to 1467 from WP-2002 (PR
  #1085, 2026-10-21), and 1467 owns only the Stephens clamp, so they move here,
  where a column read at a floor is the subject. (1) The SRM 660c and cpd-1a
  protocol answers end with high-angle reflections on `caglioti._MIN_GAMMA_G2`
  (`CONSTRAINT_ACTIVE`; a Kα2 reflection near 149.7° on LaB6, corundum past
  150° on cpd-1a). There the FD width column is 2.2e-2 off the right
  derivative, because the step moves Γ_G² by about 0.7 of the floor. A polish
  under a 5e-7 FD step or a 1e-10 floor stops 1.2 plain esd away on
  `profile.u` at χ² 0.25 % worse, and an FD step of 1e-8 does not cure it. A
  candidate fix is analytic width scalars at the clamp
  (`optimize/least_squares.py` near the width step and the scalar block, the
  clamp in `caglioti.py`). Tests: `tests/test_gaussian_width_floor.py` and
  `tests/test_cross_backend.py::test_fd_columns_hold_at_every_protocol_answer`
  (strict xfails on lab6 and cpd1a). (2) The closing stage's LaB6 answer sits
  0.908 plain esd from the converged-tails answer in `profile.u` for the same
  reason: a second recompile moves u by 1 esd and a third by 0.002.
  `tests/test_window_domain.py::test_the_closing_stage_meets_the_bar[lab6]` is
  a strict xfail citing this WP, and turns green when the clamp stops moving
  u. 1467 measured one thing nearby: from a collapsed start on synthetic LaB6
  (U, V, W and scale free) both drivers stay under the floor on 20 of 20
  reflections at χ² 6.34 against 1.01 from the true start, a stall rather than
  a hinge the fit exploits, which is why 1467 left the floor alone.

## Non-goals

- The FCJ limit itself and the traced kink: shipped in WP-1953 (#918).
- The LM driver's handling of a small column in general: WP-1953 (#923).
  The case at both apertures zero (#1075) is this WP's, since 1953's fix
  does not reach it.

## Tasks

- [x] Measure the numpy analytic `axial_hl` and `axial_sl` columns at one
      zero aperture against the one-sided difference, and find the line in
      `model/forward.py` where the node differencing departs from it. A test
      that fails on `main`.
- [x] Fix it, and re-measure the fits that free one aperture from 0:
      `test_e8`, QPA cpd-1a's `lines_axial` stage, the Stephens brucite
      protocol. Record the esds of S/L before and after.
      Reverted in PR #1321. The fix (a second-order node difference, measured
      in the first 2026-11-02 entry) strands a fit at a zero aperture, so it
      returns with task 5. Ruled by Yue 2026-11-02: split. The exact column
      lands later together with a lift off a zero aperture (task 5), as one
      reader-output change with numbers. Until then the numpy rows of the
      zero-aperture test are a strict xfail naming task 5, and the matrix
      leaves out that one column (`KNOWN_DEFECT_COLUMNS`).
      Landed 2026-11-03 with task 5 (the reverts reverted); the re-measures
      are in that day's handover entry.
- [x] The dead-column cut: count the configs whose columns fall under
      `DEAD_COL_FRAC`, and decide whether the matrix checks such a column
      against its own difference at its own scale, as the zero-aperture test
      does. Record it as `Decided YYYY-MM-DD:`.
      Decided 2026-11-02: the matrix checks every column at its own scale
      and skips only a column that is exactly zero on both sides. Two of 30
      configs had columns under the cut, nine columns in all, and every one
      was live: the aperture at zero in `axial_one_zero` (2.6e-8 of the
      largest), and in `nac` the two Biso and six background columns
      (1.3e-9 to 1.3e-7). Every backend and fp32 row met each at its own
      scale, the worst 1.8e-3 at the aperture and 2.4e-7 elsewhere, all under
      the existing bars. Settled by Claude under the WP's acceptance line (no
      backend row skips a live column for its size alone) and the
      measurement. `DEAD_COL_FRAC` stays only in the FD-step oracle, which
      is not a backend row.
- [x] Probe the Caglioti tie: U = V = 0 with W on its floor, traced against
      numpy.
- [x] Both apertures at 0: reproduce WP-2003's warm CPD collapse (X17) and
      #1075's LM stop on `lab_bragg_brentano`, and say whether one remedy (a
      floor or a lift where the column is live, WP-1938's rule) serves both.
      Land task 2's exact column with that remedy, in one change: the
      calibrate guide's second calibration (S/L freed from 0, H/L held) is
      the case the column alone breaks. Remove the strict xfail and the
      `KNOWN_DEFECT_COLUMNS` entry in `tests/test_cross_backend.py` then.
      Decided 2026-11-03: one remedy serves all three, a lift. A stage that
      frees an aperture sitting on zero starts it at `AXIAL_SIZING_FLOOR`
      (0.02), the value its windows and nodes are already sized for
      (`forward.apertures_to_lift`, both runners, recorded in
      `StageResult.seeded`). A floor cannot serve: the column at a small
      positive floor is as small as at zero. #1075 repro 1: Rwp 0.0834 on
      zero → 0.0453; X17's warm 1c: Rwp 10.73 → 0.10881; the calibrate
      guide's second calibration leaves zero again. Settled by Claude on
      those measurements. Revised 2026-11-05 under the review of #1372: the
      start is two constants of its own, `AXIAL_SL_START` 0.02 and
      `AXIAL_HL_START` 0.01, apart from `AXIAL_SIZING_FLOOR`.
- [ ] The start value's evidence (added 2026-11-03 from the generality
      judge's "weak"): a start-invariance test for the lift, 0.02 against
      0.002 and 0.005 and against TRF from zero, on three unrelated families,
      one of them synchrotron (`tests/test_seed_invariance.py` is the
      roughness seed's precedent), and the exact column's comparison against
      jax at S/L and H/L from 0.001 to 0.005 and at a low-angle reflection
      under the ξ cap. The start-invariance test now moves the start alone
      (`AXIAL_SL_START`/`AXIAL_HL_START`, not the sizing floor). The rows for
      both starts and for `AXIAL_NODE_STEP` (tier 3, written 2026-11-05) and
      the amended `StageResult.seeded` row wait for Yue's approval; the
      `AXIAL_SIZING_FLOOR` row is left alone.
- [ ] The Gaussian-width floor (Context, from WP-1467): the FD width column
      at `caglioti._MIN_GAMMA_G2` and the strict xfails that cite this WP
      (`test_fd_columns_hold_at_every_protocol_answer` on lab6 and cpd1a,
      `test_window_domain.py::test_the_closing_stage_meets_the_bar[lab6]`).
- [ ] `Refinement.suggest` scores an aperture on zero from its exact,
      nearly zero column, while a stage freeing it now starts at 0.02.
      Measure whether it should score from the lifted state, as it does a
      roughness at b = 0, without manufacturing a gain (`strategy/suggest.py`
      § the seeds' history).

## Acceptance

The numpy, jax and torch `axial_hl` columns at H/L = 0 meet the one-sided
difference under one bar, and no backend row skips a live column for its size
alone.

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_lab_instrument.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1953 (the FCJ limit, the traced kink, the curvature rule) and its second
  session's handover entry.
- Finger, L. W., Cox, D. E. & Jephcoat, A. P. (1994). *J. Appl. Cryst.*
  **27**, 892-900.

## Handover log

- **2026-11-05** — Yue's review of #1372, six items before merge (ghostshift
  autopilot `ap_1372_1`, Sonnet; Yue's checks quoted below are his).

  1. *Two lifted ratios on the S/L = H/L line.* The pattern is symmetric in
     the pair, so at equal values the columns are identical and a step keeps
     them equal. The start is now two constants, S/L 0.02 and H/L 0.01, and
     `forward.axial_lift_start` gives a ratio the other ratio's number when
     its own would equal its partner's value (S/L declared 0.02, H/L lifted:
     H/L 0.01; H/L declared 0.01: H/L 0.02; and so on). Probe (this branch,
     synthetic rutile at lab counts, strongest line about 68 000, a stage
     freeing only the two ratios from 0/0, four seeds, truths 0.05/0.01 and
     0.035/0.025): both started at 0.02, 4 of 8 fits ended on the line
     (0.0332/0.0332 twice, 0.0303/0.0303 twice); from 0.02/0.01, 0 of 8 did,
     and each reached the true pair, S/L and H/L exchanged in all eight, as
     the symmetry allows. The seeds differ from Yue's, so the 4 of 8 is not
     his 3 of 8. New test `test_two_lifted_apertures_do_not_stop_on_the_equal_line`
     (unequal truth); it fails with the two starts set equal.
  2. *A hand-freed aperture.* The gate was "in the free set before the stage",
     which `set_vary` then `run_stage` satisfies. It is now "an earlier stage
     of this fit refined it": `_run_stage(refined_before=…)`, filled by the
     plan loop in `fit` and the joint runner, empty for `run_stage`. Test
     `test_an_aperture_the_caller_freed_by_hand_is_lifted_too`; the closing-stage
     test now runs a two-stage plan through `fit`.
  3. *Audit rows.* `AXIAL_SL_START`, `AXIAL_HL_START` and `AXIAL_NODE_STEP`
     (was a local `h_ax`) are module constants with tier-3 rows, no `approved`;
     `AXIAL_SIZING_FLOOR`'s row is untouched and `StageResult.seeded`'s is
     amended. The sizing-floor invariance test says it moves only forward's
     binding. The one `approved` test on the three new rows stays red until Yue
     writes the date (the documented waiting state).
  4. *Docstrings* of `apertures_to_lift`: a row on its floor is moved (a typed 0
     and value = min = 0.005), the small-floor sentence now says Yue's
     measurement (any start 0.001 to 0.05 cured repro 1 with S/L alone), and the
     0.0834 → 0.0453 figures are marked as the two-ratio route no shipped plan
     takes since WP-2012 (the shipped one: 0.0831 → 0.0630).
  5. *Joint runner.* Test `test_the_lift_starts_off_the_partners_value_in_a_joint_fit`
     covers all four rows; the docstring of `axial_lift_start` says the two
     histograms may end on opposite orders of the pair.
  6. *Records.* `docs/practice.md` § Axial divergence at zero carries the
     start; `docs/releases/1.12.0.md` has a "Numbers that move" note; the
     `test_e8` row above is marked measured before WP-2012.

  *Reader output.* Yue's follow-up ruled: leave the lift out of the printed
  output; `StageResult.seeded` records it, which Rule 4 asks. Settled by
  Claude under Yue's 2026-11-01 reader-output ruling and Rule 4. On LaB6,
  cutting the pattern from below until S/L could not be seen left no value
  resting at 0.02 with a small esd (Yue's measurement).

  *Follow-up, not blocking.* The S/L = H/L line trap predates this PR: any
  two-column stage started at equal values meets it, and `HIGH_CORRELATION`
  fires with "the data does not separate them", which is wrong for this case.
  A diagnostic there is worth a WP (Yue's suggestion; `OWED_BY_US.md` row).

- **2026-11-03** — A fit that frees an axial-divergence ratio sitting on zero
  now leaves zero. Each stage that newly frees S/L or H/L at zero starts it at
  0.02, the value its peak windows were already sized for. With that in place
  the exact aperture column, reverted from PR #1321, is back. Three cases that
  stalled or collapsed are cured: issue #1075's lab fit that stopped
  `converged` at S/L = H/L = 0 (Rwp 0.0834 → 0.0453 on four seeds of four),
  WP-2003's warm CPD series refit that collapsed (Rwp 10.73 → 0.10881, against
  the independent fit's 0.10901), and the calibrate guide's second
  calibration. A positive floor was ruled out: the column at a small floor is
  as flat as at zero. The start value 0.02 has one real lab family behind it
  and no synchrotron one, so the generality judge rated it weak, and task 6
  holds the evidence it asks for. This entry is a ghostshift runner's; the PR
  is #1372.

  *Done.* Task 2: the four reverts of #1321 reverted (one commit), so
  `_aperture_node_derivs` (second-order, h = 3e-6, mirrored at the kink), its
  gap test, the batched-bases oracle and the `srm660c`/`toy_rich` goldens are
  back. Task 5: `forward.apertures_to_lift` plus the lift in
  `Refinement._run_stage` and `MultiHistogramRefinement`'s stage loop, before
  the plan's `Stage.seed`, recorded in `StageResult.seeded`; the strict xfail
  and `KNOWN_DEFECT_COLUMNS` are gone. `/code-review high --fix` found the
  closing stage re-lifting an aperture an earlier stage had walked back to
  zero; the lift now applies only to a path the stage newly frees (fixed,
  with a test). Help entries for both ratios and `StageResult.seeded`, the
  calibrate guide page and script (its both-free fit now lands on the
  exchanged pair, which the profile's S/L ↔ H/L symmetry allows), and
  `_collapse`'s docstring follow. Review findings declined: `suggest` still
  scores an aperture on zero from its exact column (task 8); a stencil can
  still straddle the kink with both apertures under 2h (rare, needs a new
  rule); the second-order rule costs two more node evaluations per bucket
  (accepted in its docstring); `apertures_to_lift` repeats
  `params.multi._unscoped`'s one line rather than import a private helper
  across the layer.

  *Measured* (macOS arm64, Python 3.12.13, `[dev,jax,torch]`; probes in the
  runner's scratch, control arm `main` at 4099cbd07 on the same machine).
  - #1075 repro 1 (the issue's script; seed 1): main `converged` at 0/0, Rwp
    0.0834, one TRF stage 0.0454. Lifted: S/L 0.030, H/L 0.030, Rwp 0.0453,
    and a further TRF stage moves nothing. Seeds 2-4: Rwp 0.0454, 0.0455,
    0.0459, S/L ≈ H/L ≈ 0.030. A (0.02, 0.01) start gave the same answer as
    (0.02, 0.02) *on this repro*, where transparency flattens the split (esd
    0.13); the review of #1372 found an equal start does trap a stage that
    frees only the two ratios on data with unequal ratios (2026-11-05 entry).
    `profile_interval` on S/L: main [0.0, 0.0533] `fit_is_minimum=False`;
    lifted [0.02744, 0.03251], True.
  - X17 (independent CPD 1b under `qpa_plan()`, warm collapsed 1c): closing
    stage off, main max_iter at Rwp 10.726 with `axial_sl` 64.8; lifted
    converged 0.10881 in 43 evaluations (independent 1c 0.10901). Closing on,
    lifted 0.10495 (independent 0.10518); main's closing-on control was
    stopped after 14 min (WP-2003 records 0.79140 there). 1b walks from 0.02
    back to its floor, the same answer as main.
  - Task 2's list, S/L ± esd main → branch: cpd-1a 0.036439 ± 0.002867 →
    ± 0.002809, Rwp 0.163072 both, fractions within 5e-11. Stephens brucite
    iso (LM) 0 ± 363.7 → 0 ± 363.6. Brucite aniso (TRF) 2.6e-26 ± 3915 →
    2.6e-8 ± 7445, Rwp 0.180419 → 0.180453. `test_e8` report loop: main S/L
    0.04132 ± 0.0161, H/L 0 ± 13 232; branch the mirror answer, S/L 0 ± 41 350,
    H/L 0.04132 ± 0.000307 (as with the column alone). *Measured before
    WP-2012*, with the suggestion freeing both ratios: no shipped route frees
    both now. The shipped report loop frees S/L alone and returns S/L 0.036375
    ± 0.00056 with H/L held at 0.02, on main and on the branch, 3e-5 esd apart
    (the review of #1372).
  - Calibrate guide: both calibrations quote main's numbers to every digit;
    the both-free fit returns S/L 0.01542(87), H/L 0.02476(78), the pair
    exchanged.
  - Tests: `tests/test_cross_backend.py` 241 passed, 36 skipped, 2 xfailed
    (the two numpy zero-aperture rows now pass, xfailed → passed). Against
    main the fast selection gains 6 tests: the gap test's 2 rows (back with
    task 2) and 4 in `test_lab_instrument.py` (the lift's three starts and
    the no-relift row).
    Fast and full counts on the merged tree: the PR body.
  - Re-measured after merging `origin/main` at 5d7622d60, whose WP-2012
    has `lab_bragg_brentano` free S/L alone with H/L held. #1075 repro 1
    (seed 1, H/L at the constructor's 0): main stops `converged` at S/L
    0.00012, Rwp 0.0834, `profile_interval` [0.0, 0.0529]
    `fit_is_minimum=False`. Lifted: S/L 0.04535, Rwp 0.0632, the one-ratio
    minimum (a further stage from main's answer reaches the same 0.0632),
    interval [0.04490, 0.04578], True; `FLOOR_HIT` on the profile's W,
    whose simulated value is 1e-4. The 0.0453 above is the two-ratio fit,
    which now needs H/L freed by hand. `examples/guides/calibrate.py` passes
    unchanged on the merged tree. `python -m tests.reader_output`:
    unchanged, exit 0. The added tests' local seconds: the gap test 24.75 s
    over its 2 rows (it sat in the fast tier before #1321 reverted it), the
    lift's 4 rows 1.64 s. The full suite's one failure,
    `test_eval_skill.py::test_the_placement_episode_builds_and_fires_its_codes`
    (`KeyError` on `axial_hl`), fails on `main` at 9b888120c too: issue
    #1384, not this WP's.

  *Generality* (judge's verdicts, summary). The lift: weak. The action is
  kind 1 (a free parameter whose column vanishes at its start cannot be
  refined), strong for; the start value reuses the approved
  `AXIAL_SIZING_FLOOR` row, whose evidence covers sizing only, and
  `StageResult.seeded`'s row names only the roughness seed; one real
  family; a synchrotron refiner (apertures 0.001-0.005) would start nearer
  GSAS-II's 0.002. Would change it: a start-invariance test on three
  families, one synchrotron, and the rows amended and approved. The column
  stencil: weak, better than before; untested at apertures 0.001-0.005 and
  under the ξ cap. Author's answer: both are task 6; the PR asks Yue whether
  to amend the two rows or give the start value its own.

  *Gotchas.* A lift on every freed path re-lifts on the closing stage, which
  re-frees every glob; compare against the free set before `set_vary`.
  A fast run started before `/code-review --fix` finishes measures a tree
  that changes under it; the first fast run here was discarded for that.

  Next: Yue's ruling on the audit rows (PR body). Then task 6 (the
  start-invariance test with a synchrotron family decides whether 0.02 stays
  or the start depends on the instrument), task 7, task 8.

- **2026-11-02 (second)** — Yue ruled the open question: split. PR #1321
  now carries only the test and traced-backend half, and changes no default
  output. Ruled by Yue 2026-11-02: split. The exact column lands later
  together with a lift off a zero aperture (task 5), as one reader-output
  change with numbers.

  *What the PR contains now.* Task 3: the agreement matrix checks every column
  at its own scale and skips only an exactly zero one. Task 4: the Caglioti
  floor is a select, so jax and torch return the full width column at
  U = V = 0 with W on its floor. Task 1's test: the zero-aperture test has
  numpy, jax and torch rows for both apertures; the numpy rows are a strict
  xfail whose reason names task 5.

  *Reverted.* Task 2, by `git revert` of 976318b07 (node difference and the
  golden re-captures), 851bb6b9f (gap test) and 29724e63b (batched-bases
  oracle), and of the `forward.py` half of e1c225bca (mirrored stencil),
  whose test half (the width-floor test's `importorskip` moved ahead of the
  state build) belongs to task 4 and stays. `forward.py`, both goldens,
  `tests/data/README.md` and `test_derivative_bases_batched.py` are now
  identical to `origin/main`.

  *Departure from task 3's Decided line.* The matrix's reference is numpy's
  analytic column, so with the defect back every backend row of
  `axial_one_zero` failed on `axial_hl` (fd row: rel-L2 0.2316). The matrix
  leaves out that one (config, path) pair, listed in `KNOWN_DEFECT_COLUMNS`
  beside the strict xfail that still holds it; every other column of that
  config is checked. Settled by Claude under the ruling (a green suite must
  not hide the known defect, and the xfail keeps it visible).

  *Measured* (macOS arm64, Python 3.12, `[dev,jax,torch]`, merged with
  `origin/main` at 37e85ae9d). `tests/test_cross_backend.py`: 230 passed,
  35 skipped, 4 xfailed (the two numpy zero-aperture rows and two older
  ones). `test_examples[calibrate]` passes at main's quoted numbers.
  `python -m tests.reader_output`: unchanged against the merge-base, exit 0.
  Fast-suite counts: see the PR body.

  Next: task 5, with task 2's column. The first 2026-11-02 entry holds the
  column's measurements and the calibrate failure that the lift must cure.

- **2026-11-02** — The numpy Jacobian now gives the right axial-divergence
  column when one aperture (S/L or H/L) sits on zero, and the esd of the other
  aperture there is now right too. On the `test_e8` report-loop fit, the
  nonzero aperture's esd was 50 times too large (0.00903 against an exact
  0.000181 from jax's column). The cause was a first-order difference of the
  FCJ quadrature nodes. At a zero aperture the column is a small residue of
  much larger terms, so the difference's small error was 23 % of it. The
  cross-backend test no longer skips columns that are tiny beside the
  largest. It now checks every column at its own scale, and nine such columns
  were checked for the first time, all correct. The Gaussian-width floor also
  gave jax and torch half of each width column where U = V = 0 and W sits on
  its floor; that is fixed. Task 5, both apertures at zero (the warm CPD
  collapse and #1075), is not started. This entry is a ghostshift runner's,
  ended early because its context passed 300K.

  *Done.* Task 1: the zero-aperture test gained a numpy row and an S/L-at-zero
  mirror; on main the numpy rows fail at rel-L2 0.2316 for both apertures, and
  jax and torch pass. Task 2: `_aperture_node_derivs` (`model/forward.py`)
  takes (−3f(0) + 4f(h) − f(2h))/2h at h = 3e-6, from a scan against jax's
  column (1e-7: 8.9e-3 off at zero; 3e-6: 5.3e-4; interior under 2e-7 for
  3e-7 to 1e-5). `/code-review high --fix` found that this stencil crosses
  the S/L = H/L kink when one aperture is under the other by at most 2h, and
  mirrored it there (backward second-order); a test at gaps of 1e-6 and 5e-6
  holds it to 1e-5 against jax (a mutant without the mirror fails at 2.2e-3
  and 7.6e-4). Goldens `srm660c` and `toy_rich` re-captured: only their two
  aperture columns moved, by 3e-6 to 1.1e-5 of their norm
  (`tests/data/README.md`). Task 3: `_assert_columns` skips only a column that
  is exactly zero on both sides (Decided line under the task). Task 4:
  `caglioti.gaussian_fwhm`'s floor is `where(g2 < floor, floor, g2)`; numpy
  values are unchanged, and jax and torch now take g2's side of the tie
  (was rel-L2 0.500 on U, V and W; now 7e-7, 8e-6 and 3e-4 against the
  one-sided difference, the last being the difference's own truncation).

  *Measured* (macOS 26.7.2 arm64, Python 3.12.10, `[dev,jax,torch]`; fits
  through probes on an `origin/main` snapshot at 816fe35ea and on this
  branch). S/L and H/L as value ± esd; Rwp unchanged unless stated.
  - QPA cpd-1a (`qpa_plan`, frees S/L with H/L held at 0): S/L 0.036439 ±
    0.002867 → 0.036439 ± 0.002852. Rwp 0.163072 both; fractions move under
    1e-9.
  - Stephens brucite iso (LM): S/L 0 ± 363.7 both, bit-identical. Both
    apertures sit at zero, where the axial columns take whole-model FD.
  - Stephens brucite aniso (TRF): S/L 2.6e-26 ± 3915 → 2.9e-10 ± 874 714.
    Rwp 0.180419 → 0.180479. TRF parks next to the double zero, where the
    column is nearly flat and either esd means "unmeasured".
  - `test_e8_collinear_window_applies_no_position_action` (report loop,
    `refine_axial_asymmetry` accepted): before S/L 0.041320 ± 0.0161, H/L 0 ±
    13 232; after S/L 0 ± 41 350, H/L 0.041320 ± 0.000307. The FCJ profile is
    symmetric in S/L and H/L, so the fit now lands on the mirror answer. At
    that answer, on one free set, the nonzero aperture's esd is 0.00903 from
    the old column, 0.000181 from the new and 0.000181 from jax.
  - Dead-column count: 2 of 30 configs had columns under `DEAD_COL_FRAC`
    (`axial_one_zero`'s H/L at 2.6e-8 of the largest; `nac`'s two Biso and
    six background columns at 1.3e-9 to 1.3e-7). Every backend and fp32 row
    met each at its own scale: worst 1.8e-3 at the aperture, 2.4e-7
    elsewhere.
  - Tests added: +9 in the fast selection (zero-aperture test 2 → 6 rows,
    width floor 3, gap 2). Fast and full counts: see the PR body, measured
    on this branch merged with `origin/main` at 62bc2ac2b.

  *Reader output.* This moves fitted numbers and esds of every fit that frees
  an aperture (above, and the e8 mirror answer). It goes to Yue before merge
  (the reader-output rule).

  *Generality* (judge's verdicts, unedited summary): 1, the node step: weak,
  for want of tests at a gap under 2h and at synchrotron-scale apertures, and
  for the unrecorded task-2 esds. 2, the mirrored stencil: weak, no test. 3,
  the Caglioti select: holds. 4, the matrix cut: holds. Author's answer: the
  task-2 esds are recorded above, and the gap test now exists (commit after
  the review). Synchrotron-scale apertures (0.001-0.005) are not yet tested.

  *Gotchas.* A forward difference against a column that is a cancellation
  residue fails at any step that is fine elsewhere; check a small column
  against an exact one (jax), never against its size. `fcj` nodes have two
  more kinks a stencil can straddle: the ξ cap (`_tan_cap`) at low angle,
  rare and not handled.

  *Blocking finding, after the fast suite.* The fast run (13 506 passed,
  128 skipped, 32 xfailed, 3 failed) failed `test_examples[calibrate]`, and
  the cause is this change. The calibrate guide's second calibration frees
  S/L from its default of 0 with H/L held at 0.015. On main LM leaves 0 and
  lands S/L 0.02464 (truth 0.025), W 0.00595 and X 0.0305 (truth 0.006 and
  0.030), Rwp 0.0596. On this branch S/L stays at 0, and W 0.00887 and X
  0.0324 absorb the asymmetry, Rwp 0.0642, every stage `converged`. The
  profile is quadratic in a zero aperture, so the exact column there is
  nearly zero, and Gauss-Newton sees no way off the bound. The old
  first-order column carried a spurious O(h) term (0.013 in norm), and that
  error was what pushed LM off zero. This is #1075's mechanism with one
  aperture held. The guide's quotes were left as main's, so that test stays
  red on this branch. The other two failures are not this change's: the
  scalar oracle in `test_derivative_bases_batched.py` still used the
  first-order rule (fixed, commit 29724e63b), and
  `test_display.py::test_a_plot_in_a_kernel…` fails on a Jupyter kernel spec
  pointing at a deleted venv (an environment fault on this Mac). The full
  selection was stopped before it ran.

  *Question for Yue (ruled 2026-11-02: split, see the entry above).* Ship the exact column only together with a lift
  off a zero aperture (a stage that frees an aperture seeds it off 0, WP-1938's
  "a floor or a lift where the column is live"), which also covers task 5 and
  moves every fit that frees an aperture from 0; or revert the column fix
  until that lift exists, keeping the matrix and Caglioti changes. The PR
  stays a draft until this is ruled.

  Next: the ruling above. Then task 5. Reproduce WP-2003's X17 (`docs/wp/2003-batch/clashes.md`)
  and #1075 repro 1 at this branch, since neither path touches the columns
  fixed here (both apertures at zero take whole-model FD). Then decide
  between a floor and a lift for the apertures (WP-1938's rule); either moves
  every fit that frees an aperture from 0, so it comes to Yue with the
  numbers. Also worth a row: the aperture columns at synchrotron-scale
  apertures.

- **2026-10-13** — Filed from WP-1953's close. No open WP owns it: 1467 is a
  Stephens clamp, and the WPs citing the agreement matrix are magnetic,
  rigid-body and test-tier work. The two findings combine because both are a
  column tiny beside the largest, on one test file.

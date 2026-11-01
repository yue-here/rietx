# WP-2002: rows still at `unaudited`, with what each waits on (2026-10-20)

Written by the session's audit-row lane; the B10 rows that landed at tier 3 with their owed test named (B10 option 2) are removed. Each row lands with the change, test or WP it names.

All stay on `UNAUDITED_BASELINE`. Out-of-scope classes (B5, B13, B14) are not listed.
Hand rows (not in `_audit.ROWS`) are not listed; B15 has only hand rows, so nothing of it
is here or landed.

## B3: the roughness seed's two-start test

Measured 2026-10-20 (`tests/test_seed_invariance.py`'s docstring has the table). Suortti's b
is answer-invariant on five lab patterns from three laboratories: every Biso, scale and b
within 2.7e-3 of the smaller esd, the same branch wherever b leaves its floor, the same
distance from each reference.

- `rietx.schemas.results.StageResult.seeded`: landed at tier 3 on 2026-10-21 (the sixth
  round's Q3, ruled (c)). The same literal seeds Pitschke's `c`, which is *not*
  start-invariant (CPD zincite from c = 0: the turned-over regime, scale x2.1,
  `ROUGHNESS_OUTSIDE_REGIME`; corundum: Biso 0.26 esd), and no program supplies a
  Pitschke start. The row records the two models apart; the code keeps one number. The
  off-state esd dependence went into `ROUGHNESS_UNCONSTRAINED`'s message (the fifth
  round's Q4).
- `rietx.strategy.suggest.SUGGEST_SEED_ROUGHNESS` stays here: not measured. It is the suggestion
  probe's start for scoring a column, not a solve's start, so the question is whether
  `suggest`'s ranking moves between 0.3 and other starts.

## B7: the intermediate tolerance's invariance test

Run 2026-10-21 on SRM 660c, FAP, the CPD round robin and 11-BM NAC, under LM and TRF, each
protocol's own plan and the default plan, 1e-6 against `intermediate_ftol=None` (every stage
at 1e-9). "Plain esd" is `stderr_uncorrected`; paths `FLAT_DIRECTION` or
`COVARIANCE_DIRECTION_DISCARDED` names are listed apart as degenerate.

- Within WP-1123's 0.03 esd everywhere but cpd-1a under its QPA protocol: 0.033 (LM,
  corundum scale) and 0.074 (TRF, corundum Al Biso) as fitted, 0.046 and 0.074 after one
  stage recompiled at each answer. In the inflated esd WP-1123 used they are 0.009 and
  0.021, so the switch to plain esds (f = 3.52 there) is what crosses the bar. Under LM
  three recompiles bring the arms within 0.0074; under TRF they stay 0.074 apart and the
  None arm then moves 0.106 by itself, so TRF's own scatter there exceeds the bar. QPA moved
  0.0055 and 0.009 wt %.
- **A hold flips** (the brief's change-my-mind condition, and clash C18): cpd-1a with
  zircon declared, a phase the sample lacks, under LM. At 1e-6 the last stage holds nine
  zircon structural paths and `PHASE_UNCONSTRAINED` fires; at 1e-9 nothing is held, the
  zircon cell walks (0.30 esd as fitted, 1.28 after a recompile, in `axial_sl`) and the
  `lines_axial` stage hits its 400-evaluation budget. Zircon's scale sits near 2σ in plain
  esd, by the hold's threshold. The looser default is the one that held.
- Evaluations saved by 1e-6: 1.00-2.15× on the ordinary fits, 4.9× on the flip.

Landed 2026-10-21 at tier 3 (the sixth round's Q2: a closing stage, and a bar of 0.1 plain
esd). Behind the closing stage the four protocols agree within 0.042 esd and the hold no
longer flips: both schedules hold the absent zircon in the closing stage. The answers
there still differ by 0.185 esd on fluorite `a`, because at 1e-9 an earlier stage walks
the unseen zircon's cell to its budget; `tests/test_staged_start_invariance.py` asserts
the four and xfails that one. The hand row `run_least_squares:ftol` waits on B14's lift.
B11's three budget rows were measured before the closing stage; the full suite re-asks
their margins.

## B8 and B9: limits (the size floor, March r, the harmonic and extra-peak ceilings landed with the limits lane)

- `rietx.schemas.instrument.EXTRA_PEAK_FWHM_MIN`: it guards a pole, but lowered to a pole-only value a Gaussian narrower than about 0.03 of the grid step underflows to an exactly zero column (the W failure, root CLAUDE.md). A floor that keeps the column live depends on the step, so it needs a per-stage freeze like `strain_cap`: a design change.
- `rietx.schemas.instrument.HUMP_FWHM_MIN`: the same.
- `rietx.strategy.staged.HUMP_MIN_WIDTH_MULT`: not a limit on a caller's parameter; a diagnostic threshold (gates `HUMP_TOO_NARROW`, so B13/WP-2005) and the extinction screen's internal floor (`indexing/extinction.py:737`).
- `rietx.schemas.instrument.HARMONIC_WEIGHT_SEED`: landed invariant on 2026-10-21. Behind the
  closing stage seeds 0.001 and 0.3 agree with 0.01 to 0.003 esd
  (`tests/test_staged_start_invariance.py`). Before it: two-start test run 2026-10-20, synthetic
  (corundum, constant-wavelength neutron, true λ/2 weight 0, 0.003, 0.05; the held-out
  Nd₂Ru₂O₇ pair unused) and so one family. Not invariant at B3's bar of 0.01 esd: the
  weight moves up to 0.15 esd between seeds 0.01 and 0.3, a background coefficient 0.86.
  Every seed reaches the right verdict (`HARMONIC_ABSENT` at 0, `HARMONIC_FRACTION`
  otherwise). The mechanism is the plan's, not the seed's: the weight is held at its seed
  until the last stage, whose model is frozen where the earlier stages stopped, and one
  extra stage recompiled at the answer brings the seeds within 0.012 esd. The same
  mechanism fails `Atom:biso` below, so both wait on one question for the maintainer:
  what bar an invariance test across a staged plan should use.
- `Atom:biso`* (hand row, 0.5 Å²): invariant behind the closing stage on 2026-10-21, 0.000,
  0.070 and 0.000 esd on FAP, cpd-1a and NAC (`tests/test_staged_start_invariance.py`);
  LaB6's two starts land in its mirrored axial minima (9.36 esd, WP-2012), a strict xfail.
  Waits only on B14's lift for a seat. Before it: two-start test run 2026-10-20 on SRM 660c, FAP, CPD
  (corundum, fluorite, zincite) and 11-BM NAC, starts 0.5 and 1.5 (worst over 0 to 10 in
  brackets). Biso moves 0.008 to 0.08 esd (0.16), other parameters up to 0.27 esd (0.50),
  χ² up to 6.2e-4 relative; NAC passes. Recompiling the model at one answer changes its
  cost by 0.05 to 0.3 %, and one extra recompiled stage brings FAP, corundum and fluorite
  within 7.9e-3 esd. `crystallography/cif.py:762` carries a second copy of the 0.5 for a
  CIF site with no ADP.
- `TCHZ_DEFAULTS`* (hand row): invariant, `tests/test_seed_invariance.py`'s second test
  (its docstring has the table and the margin). Waits only on B14's lift for a seat. Two
  readings it does not cover: a start near the answer's x lands on a second, deeper
  minimum on LaB6, 46.7 χ² below and nearly the S/L ↔ H/L mirror of the default's, moving u
  0.38 esd (WP-2012's interchange; the FCJ node count was measured and is not the cause); and a protocol holding an uncalibrated width holds it at
  this default, where x = 0 instead moves FAP's `lor_size` 0.69 esd at equal χ².
- Hand rows with no seat until B14's lifts: `Atom:occ` (widened to no ceiling), `EmissionLine:weight` (widened), `Geometry:bounds` (the axial ratios widened; the position corrections widened to no bound on 2026-10-20, transparency keeping its physical floor of 0), `Instrument:zero_shift` (widened to no bound, 2026-10-20), `TCHZ_BOUNDS` and `TCHZ_BOUNDS_COARSE` (ceilings removed on 2026-10-21, the fifth round's Q5, superseding WP-1312's "the bound stays"; the U and V floors are chosen and stay, the guard against a negative width at some angle under TRF; a project stored before keeps its own ceilings).

## B10: numerical settings with no domain test, and one undecided switch

Each waits on a test that bounds its error over its claimed domain (tier 1), or one asserting identity (invariant). The batch found only single-case checks; I found none either.

No B10 row is unaudited now. `MAX_NODES` landed at tier 3 on 2026-10-21 beside the other three FCJ constants. Their domain test (`tests/test_lab_instrument.py`, the FCJ section) fails over part of the domain for all four, and the constants wait on the maintainer. Measured for the ruling (2026-10-21, scratch code, 10 491 cases against converged references; image counts summed over every `compile_model` call at the fitted values, today 664 on SRM 660c and 5036 on FAP):

- Cheapest set meeting both bars under today's equal split: `NODES_PER_FWHM` 11, `MAX_NODES` 768, `SKIP_EXTENT_FWHM_RATIO` 3.5e-4 (any `MIN_NODES` ≤ 8 is inert, since `max(n//2, 4)` floors every reflection at 8 images). Images 948 and 5704 (×1.43, ×1.13). Thin: 0.95 of the bar at the cap and at the skip.
- The first proposal, 12 / 10 / 1024 / 3e-4: worst 0.25 (lab) and 0.81 (synchrotron) of the bar, images ×1.57 and ×1.37, fit wall clock ×1.15-1.3 on the two lab protocols, no parameter moved past 0.025 esd.
- Splitting the nodes between the two segments by length instead of equally is unsafe, because the split would be frozen per stage while S/L and H/L refine. A segment with zero length at compile time (S/L = H/L, or one aperture at zero) gets no nodes and then grows, and its share of the peak is missing: errors 950-1390× the bar. Both lab acceptance protocols start on S/L = H/L and refine off it. A floor of 4 nodes per segment still fails at up to 480×. So the equal split stays.
- The skip ratio's bound is split-independent: a peak drawn symmetric errs by at most 0.477 × extent/FWHM, so 3.67e-4 is the ceiling.
- Measured effect of today's error on answers: SRM 660c with every reflection at 512 nodes moved no parameter past 0.04 esd.

The window rows, measured 2026-10-21 on SRM 660c, FAP, cpd-1a and 11-BM NAC (`tests/test_window_domain.py`'s docstring has every number). The bar is 0.1 of each point's own σ at fixed parameters, and 0.1 plain esd on every non-background row after both arms are polished to a fixed point from one common start:

- `WINDOW_AREA_TOL` 2e-2 fails on all four: up to 2.15σ at a point, and a converged refit moves the cpd-1a zincite scale 0.97 esd, FAP's `lor_size` 0.91 and the background 2.1-5.1. At 1e-3 all four pass, at 1.2-3.5× the fit time (FAP the dearest); at 2e-4, 1.9-6.8×. Against it: from the shipped answer FAP's χ² is 110 higher with converged tails, the other three 37-1730 lower.
- `REFLECTION_MARGIN_DEG` 0.5° fails on FAP and cpd-1a (0.12σ, 0.10 esd); 5° is bit-identical to 20°. The coherent fix generates reflections out to the largest window half-width at the range edges (`forward.py:3733-3734`).
- `AXIAL_SIZING_FLOOR` 0.02 fails for a stage that frees S/L and H/L from zero and reaches the typical 0.05 (0.27 of the peak maximum, 19.5 % of an area dropped); 0.05 passes at 1.25-1.8× the fit time, mostly because the floor also applies to every positive ratio below it (`forward.py:3693-3696`), which a separate refine-from-zero floor would avoid.
- `MAGNETIC_SIZING_FLOOR` 0.1° drops 3.2-4.1 % of a magnetic peak at the planted widths; the preset's answer moves 0.031 esd. Raise it to ≥ 0.3, or size from the width's bound as `_compile_extra_peaks` does (`forward.py:3910-3919`).
- Landed: `_BASES_CHUNK_ROWS` and `_DENSE_EIGEN_MAX` invariant. `WINDOW_MIN_DEG` and `StageSpec:window_slack_deg` stay tier 3: the largest move from starts near each answer is 0.21° against 0.3° (1.4× margin), but a cell 0.3 % off its answer moves a 120° peak about 0.6°, untested, and a peak leaving its window is silent (the generality judge, 2026-10-21).
- Found beside them: windows are sized from start-of-stage widths, so a stage that widens peaks drops 3.0-6.5 % of an area by its end (LaB6 `profile`, cpd-1a `profile` and `sample_broadening`); every final stage holds the 2 % bound. No constant claims this; strict xfails record it.

Eight more, measured 2026-10-21 (each row's evidence has the numbers):

- The three geometry caps (`CONTACT_MAX_ANG`, `MAX_ASYM_ATOMS`, `MAX_CONTACTS_PER_ATOM`) moved to tier 1 on 2026-10-21 under the rule's new cap clause (the fifth round's Q6, its reading re-asked as the sixth round's Q4). The bond-search defect is fixed: the search reaches the longest pair the radii could bond, and CsCl lists its 3.571 Å Cs–Cl bonds.
- `FD_STEP` and `_MIN_GAMMA_G2` pass on the smooth domain and at the FAP and NAC answers, but the SRM 660c and cpd-1a protocol answers end with high-angle reflections on the Gaussian-variance floor, where an FD column is 2.2e-2 off and a polish moves U 1.2 plain esd under a 5e-7 step or a 1e-10 floor, at χ² 0.25 % worse. A defect of the clamp the solver leans on, not of either constant (forwarded to WP-1467); both stay tier 3.
- `A5_CLIP` fails by a little (1.40 % against 1 %); 1e-4 passes at no measured cost.
- `TEXTURE_SPHERE_SAMPLES` fails at every order (2.0e-3 to 7.9e-3 against 1e-3); 32 000 samples pass at 10× the cost, or a local polish at any order.
- `MIN_IMAGE_SHELL`: fixed and at tier 1 since 2026-10-21. A second pass sized by `geometry._shell` from the first pass's distance finds the nearest image in any cell, unreduced monoclinic ones included, and the slow domain test passes on all five cell families.

**Built 2026-10-21 under the seventh round's Q2** (`rulings.md` § Seventh round), each by its kind:

- The FCJ rule: the closing rule (`CLOSING_NODES_PER_FWHM` 12, `CLOSING_MIN_NODES` 10, `CLOSING_MAX_NODES` 1024, `CLOSING_SKIP_EXTENT_FWHM_RATIO` 3e-4) for every compile at `CLOSING_WINDOW_TOL` or tighter, tier 1 on `test_the_closing_node_rule_meets_the_bar`; the four declared-stage constants stay tier 3.
- `REFLECTION_MARGIN_DEG`: built, then reverted (`90b4bc770`). Generating out to the widest edge window at the closing windows met 0.1σ (0.027 FAP, 0.022 cpd-1a) at 1.3× FAP's closing stage, but reflections centred past the edge, reaching the scan only by their tails, lifted the scale-B separation over its floor on the four-phase synthetic 25-50° scan of `tests/test_scale_b_ridge.py`, and the closing stage freed a ridge the declared stages held: corundum 72.5 → 50.8 wt% against a true 72.7. The margin is 0.5° on every compile again, tier 3, leaving 0.186σ and 0.124σ at the last points of FAP and cpd-1a (answers 0.026 and 0.043 esd). Kept at 0.5° by the eighth round (`rulings.md`, 2026-10-22), for WP-2017.
- `A5_CLIP` 1e-4, tier 1 (0.14 %).
- `TEXTURE_SPHERE_SAMPLES` with a local polish (`sphere_minimum`, `TEXTURE_POLISH_STARTS` 5, `TEXTURE_POLISH_LEVELS` 6), all three tier 1 (at most 1.7e-9 at orders 2-8).
- `MAGNETIC_SIZING_FLOOR`: invariant behind the closing stage (0.000 plain esd on MnF2, one family).
- `AXIAL_SIZING_FLOOR`: behind the closing stage 0.007 and 0.002 plain esd on LaB6 and FAP, 0.138 on cpd-1a's corundum `c` (strict xfail, `tests/test_staged_start_invariance.py`); stays tier 3 for WP-2017, ruled in the eighth round (2026-10-22). The separate refine-from-zero floor above is the untried option.

Cost of the closing stage after these builds, against the fit without it, on a quiet machine, interleaved: LaB6 1.42-1.44×, FAP 2.20-2.33×, cpd-1a 1.60-1.62×, NAC 1.2×, against 1.16-1.19×, 2.04-2.18×, 1.37-1.39× and 1.2× before them. The FCJ closing rule is most of the difference.

Domain tests still owed at tier 3: the interval settings (`PARAMETER_INTERVAL_*`) and the width-grid settings (`FRACTION_PROFILE_*`). The other B10 rows sit at tier 3 with their domain tests still owed (grep `_audit.py` for "claimed domain is owed").

## B12: the form-factor follow-up (the other B12 rows landed with the pick-verb changes)

- `rietx.strategy.magnetic.SOLVE_D_MIN`: the form-factor follow-up (not yet filed).

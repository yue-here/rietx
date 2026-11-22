# WP-2151 — the ZrP₂O₇ input's peak equations on its data

Milestone: parametric · Status: ✅ 2026-11-22 — the curve and every TCHZ term refine on the 37 patterns beside the calibration, Rwp 31.79 % (31.48 % with silicon's Gaussian seeded above zero); PR #1783
Depends on: —

## Goal

The ZrP₂O₇ input's 2θ calibration curve and each phase's six TCHZ terms refine on the
real data as peak equations, beside the temperature calibration. The answer is reported
in this WP, with no gate.

## Context

The milestone's ZrP₂O₇ row ([parametric.md](../milestones/parametric.md) § Acceptance)
ends: "the real-data run frees them beside the calibration". Every other clause of the
row is met. WP-1964 measured the cell equations and the cubic temperature calibration on
the data. WP-2107 built the peak equations and recovered all twelve coefficients of a
ZrP₂O₇-shaped synthetic ramp within 2 esd (`tests/test_peak_equations.py`). No one has
run the two together on the data. TOPAS stores nothing for this fit, so the run has no
reference and the row sets no bar.

**The data.** Durham TOPAS tutorial 9.5 (Stinton & Evans, 2007): ZrP₂O₇ with
a silicon standard and Al₂O₃, 37 patterns from 303 K to 1173 K and back. It is a public
teaching download held local only, registered as `durham-topas/zrp2o7` in
`tests/local_data.py` (`python -m tests.local_data durham-topas/zrp2o7`). This WP is a
measurement. No data file, fixture or test built from the data enters the tree. The
numbers go in the handover entry.

**What exists to extend.**

- `docs/wp/1325-measure/zrp2o7_model.py` builds the model and protocol from the input at
  run time. Its docstring lists where the protocol departs from TOPAS's. Two of those
  departures are what this WP removes: the 2θ curve is left out, and each phase's
  sample-broadening terms refine per pattern instead of one TCHZ per phase shared by all
  37 patterns.
- `docs/wp/1964-measure/zrp2o7_formula.py` adds the cell equations and the calibration as
  formula text. Its arm (d) freed the calibration on the data: b −0.40 ± 3.15, c −20.40 ±
  1.53, d −4.24 ± 2.67 K, Rwp 31.488 % against TOPAS's 31.56 %, 133 s ([dev], macOS
  arm64, 2026-11-06). Extend this script with a new arm rather than writing a third.

**The equations, by physics.**

- The 2θ curve is one instrument-level `shift` equation, quadratic in (2θ − 54°). The
  input's `step_error` and `square` give 0.0105° at 15°, zero at 54° and 0.0059° at 90°.
  Write it with `two_theta`, the position before the equation acts.
- Each phase's TCHZ is a `gauss_fwhm_squared` equation, u·tan²θ + v·tanθ + w + z/cos²θ,
  and a `lor_fwhm` equation, x·tanθ + y/cosθ. The input's slots run (u, v, w, z, x, y)
  by argument position (WP-1455). The stored v and w are negative for two of the three
  phases, which is why the Gaussian target is a signed variance.
- Each coefficient is shared across the 37 patterns, as the input shares it. A coefficient
  is a table entry under its phase, and a joint fit shares it through `SharingMap`.
- The instrument's own U, V, W, X and Y duplicate these terms exactly, so they stay held.
  W keeps its floor `caglioti._MIN_GAMMA_G2`.

**What could go wrong, measured on the synthetic ramp.** `Refinement.predict` draws at the
closing window (1e-3) while a default fit measures at 2e-2. On WP-2107's ramp that took a
broad phase's x coefficient 1.2 esd low until the plan closed at `CLOSING_WINDOW_TOL`. A
real pattern has no such mismatch, but a run here should report whether the answer moves
when the plan closes.

**A known gap the run may meet.** The LM driver's width inequalities read the built-in
terms alone, so a negative equation term is caught only by `PEAK_WIDTH_NOT_POSITIVE`
after the fit ([2153](2153-a-peak-equations-width-held-inside-the-step.md)). Two
phases' negative v and w make that gap reachable here. Report each firing.

**Tier.** This WP adds no rule. It runs machinery that exists.

## Non-goals

- A gate on the answer. TOPAS stores nothing for this fit.
- Any code change in `src/`. A defect the run finds is a new WP, named in the handover.
- The agent port of the input (the milestone's last row), which judges a fresh agent.

## Tasks

- [x] A new arm in `docs/wp/1964-measure/zrp2o7_formula.py`: the formula fit of arm (d)
  plus the `shift` equation and both width equations per phase, each coefficient shared
  across patterns, the instrument's width terms held. Seed from the input's stored values.
- [x] Run it on the 37 patterns. Report each coefficient with its esd beside the input's
  stored value, the calibration's b, c and d beside arm (d)'s, Rwp beside 31.488 % and
  TOPAS's 31.56 %, the free-parameter count, every diagnostic code, and the wall clock as
  a range with the machine's load. Save obs/calc/diff PNGs for patterns 0, 18 and 36 to
  `tests/output/` and look at them.
- [x] Report whether closing the plan at `CLOSING_WINDOW_TOL` moves any coefficient by
  more than 0.5 esd.
- [x] Update the milestone's ZrP₂O₇ row with one sentence naming the result, and the
  record of the release in flight.
- [x] Skill: none expected. If the run shows a trap an agent porting this input would
  meet, add a row to `docs/skill/rietx/references/` for the series shape.

## Acceptance

The run completes on all 37 patterns, and its numbers are in the handover entry. The
script stays runnable from the repository root.

```sh
.venv/bin/python docs/wp/1964-measure/zrp2o7_formula.py > ~/.cache/zrp2o7_run.txt   # local data only; ~3-10 min
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95, §§ 4.1-4.2.
- WP-2107 (peak equations), WP-1964 (the cell equations and calibration), WP-1325 (the
  model and protocol), WP-1455 (TCHZ slots by position).

## Handover log

- **2026-11-22** — Closed by a ghostshift runner (MacBook-Air-c4aacd), PR #1783.
  The ZrP₂O₇ input's 2θ calibration curve and its three phases' TCHZ profiles now refine
  on the real data as peak equations, beside the temperature calibration. Each coefficient
  is shared by all 37 patterns, as the input shares it. The joint fit converges at Rwp
  31.79 % (TOPAS 31.56 %). Two things in the input stop a literal port from measuring
  everything. TCHZ's z/cos²θ term equals z + z·tan²θ, so u, w and z cannot be told
  apart, and z must be held for u and w to carry an esd. The input's silicon Gaussian is
  below zero at every reflection, so its four coefficients have no gradient and never
  move. Seeded above zero, silicon's line shape fits and Rwp falls to 31.48 %. Closing the
  plan at the wider peak window moves nothing past 0.5 esd. No code changed.

  *Done.* Arm (e) of `docs/wp/1964-measure/zrp2o7_formula.py`, run as `… zrp2o7_formula.py`
  (all arms) or `… e` (this arm alone). It starts from WP-1325's chain, as (d) does. It
  writes the curve as one instrument `shift` equation,
  `square*(two_theta - 54)^2/1000 + step_error*(two_theta - 54)/1000`, the input's
  `th2_offset` with its held zero left out. Each phase gets
  `u*tan(theta)^2 + v*tan(theta) + w + z/cos(theta)^2` (`gauss_fwhm_squared`) and
  `x*tan(theta) + y/cos(theta)` (`lor_fwhm`), seeded by slot position (WP-1455). The
  sharing is `per_histogram=["phases.*.cell.*", "phases.*.atoms.*"]`,
  `shared=["instrument.peak_equations.*"]`. (d)'s `per_histogram=["phases.*"]` would make
  every phase coefficient per pattern, since the per-pattern list is checked first. The
  instrument's U, V, X and Y are 0 and W is at `_MIN_GAMMA_G2`. Each phase's four built-in
  broadening terms are 0. None of them is freed. The plan is WP-1325's, with its
  `sample_profile` stage replaced by one freeing the equations. Four fits: *as written*
  (all six TCHZ terms free), *z held* (the reported answer), *closed* (z held, plus
  `closing_window_tol=CLOSING_WINDOW_TOL`), and *Si seeded* (z held, silicon's w lifted
  by 0.00746 to 0.02344 deg², so its smallest Γ_G² in 15-90° is 0.002 deg²). The manual's
  TOPAS page and the skill's `PEAK_WIDTH_NOT_POSITIVE` row name both traps. WP-2153
  inherits the silicon case.

  *Measured* (`[dev]`, macOS arm64, compiled tier on, rietx 1.13.0.dev0 at a0d045f6e,
  2026-11-22; full log in the runner's scratch):
  - Previews (a) and (b) unchanged: worst 6.63e-7 Å and 0.0 Å, both PASS. Arm (d) on
    today's tree: Rwp 31.492 %, χ² 197719.6 on 1594 free, b −0.43 ± 3.15, c −20.41 ± 1.53,
    d −4.22 ± 2.67 K (11-06's: 31.488 %, −0.40, −20.40, −4.24).
  - (e), z held: converged, Rwp 31.793 %, χ² 201508.1 on 1167 free, χ²r 1.2441. As
    written: the same χ² to 0.1 on 1170 free, which confirms the degeneracy is exact.
    Closed: Rwp 31.785 %, χ² 201416.6. Si seeded: Rwp 31.481 %, χ² 197573.6 on 1167
    free, so lifting silicon's Gaussian buys Δχ² −3935 for no added parameter.
  - Coefficients, z-held fit (stored → fit ± esd, in esd from stored). z is held at the
    input's value, so u and w carry u + z and w + z.
    - curve: square 0.00579 → 0.00471 ± 0.00039 (−2.8); step_error −0.04428 → +0.1377 ±
      0.0150 (+12.2). The fitted curve is +0.0018° at 15°, −0.0006° at 30°, 0 at 54° and
      +0.0111° at 90°, against the input's 0.0105° and 0.0059°. Its linear term
      shares a 2θ shape with the per-pattern displacement and the cells. Not separated
      here.
    - ZrP₂O₇: u −0.02192 → +0.01204 ± 0.00270 (+12.6); v −0.00248 → −0.02266 ± 0.00232
      (−8.7); w −0.00730 → −0.00354 ± 0.00047 (+8.1); x 0.08237 → 0.03126 ± 0.00685
      (−7.5); y 0.01835 → 0.03184 ± 0.00195 (+6.9).
    - silicon: u, v, w, z unmoved, no esd (start below the floor); x 0.00984 → −0.01845
      ± 0.00291; y 0.03434 → 0.07119 ± 0.00109. The Lorentzian takes up the missing
      Gaussian width. In the Si-seeded fit, x is 0.00984 ± 0.00576 and y 0.03445 ±
      0.00208, the input's own values, and the Gaussian is u 0.02655 ± 0.00167,
      v −0.00919 ± 0.00199, w 0.03011 ± 0.00053.
    - Al₂O₃: u −0.04097 → −0.07731 ± 0.00823 (−4.4); v −0.06632 → −0.00598 ± 0.00788
      (+7.7); w −0.06330 → −0.07581 ± 0.00192 (−6.5); x 0.14293 → 0.07378 ± 0.01625
      (−4.3); y 0.02801 → 0.04128 ± 0.00630 (+2.1).
    - Fitted Γ_G² at 15° and 90°: ZrP₂O₇ 0.0072 and 0.0124 deg², Al₂O₃ 0.0082 and 0.0103.
      The stored values give 0.0055 and −0.0051, and 0.0134 and −0.0012. So the input's
      own widths cross zero inside the range for both phases. Silicon: stored −0.0055
      and −0.0029; seeded fit 0.0069 and 0.0034.
  - Calibration: z held, b −4.02 ± 3.21, c −22.66 ± 1.65, d −0.09 ± 2.80 K; Si seeded,
    −3.19 ± 3.17, −22.72 ± 1.63, −0.89 ± 2.77 K. Against (d), within 1.5 esd.
  - Closing at `CLOSING_WINDOW_TOL` (1e-3): largest move 0.48 esd (ZrP₂O₇ y), then 0.43
    (ZrP₂O₇ x); 0 of 17 rows past 0.5 esd. Calibration rows move ≤ 0.01 esd.
  - Diagnostics. z held and closed: `BISO_UNUSUALLY_LARGE` ×39 (as in (d)),
    `PEAK_WIDTH_NOT_POSITIVE` ×1 (silicon's Gaussian, 7 of 7 reflections, worst −4.95e-3
    deg² at 111), `VARIABLE_NOT_FREED` ×3 (the cell equations' constants, which the
    input holds; (d) carries them too). As written adds `COVARIANCE_DIRECTION_DISCARDED`
    (u, w, z of ZrP₂O₇ and Al₂O₃) and `HIGH_CORRELATION` (ZrP₂O₇ w~z, 0.987). Si seeded
    carries `BISO_UNUSUALLY_LARGE` and `VARIABLE_NOT_FREED` only.
  - Wall clock, two runs at load 5-75: chain 27-32 s; as written 65-119 s; z held
    40-99 s; closed 82-208 s; Si seeded 43-131 s; the whole script 399 s at the lighter
    load. Closing costs about 2× the z-held fit in both runs.
  - Plots (patterns 0, 18, 36, full range and 70-90°, plus pattern 0's Si 111 in the
    z-held and Si-seeded fits) in `tests/output/wp2151_zrp2o7_peak_*.png`. Looked at:
    flat difference curves away from the strongest lines. In the z-held fit, Si 111 at
    28.4° is a pure Lorentzian too sharp at the top, with a dipole in the difference. Si
    seeded fits that line.

  *Gotchas.* A held parameter leaves `RefinementResult.parameters`, so read its value
  from the seed. `SharingMap` checks `per_histogram` before `shared`, so a broad
  per-pattern glob over `phases.*` swallows every phase coefficient.

  *Not done, by scope.* Why the curve's linear term moved 12 esd from TOPAS's, and how
  TOPAS treats a negative Γ_G². One hypothesis fits silicon: TOPAS reads the magnitude.
  The seeded fit lands near the stored values' size with the sign flipped, and silicon's
  Lorentzian returns to the input's. It is not checked, since TOPAS is closed. WP-2153's
  § Practice reading of the Technical Reference is where to check it.

  *Settled by Claude* (the grounds in brackets): the reported coefficients come from the
  z-held fit (1/cos²θ = 1 + tan²θ, an exact reparameterisation; measured χ² equal). The
  Si-seeded fit is added to measure the cost of the `PEAK_WIDTH_NOT_POSITIVE` firing (the
  WP asks for each firing). The silicon finding is folded into WP-2153 rather than filed
  (the fold rule in `docs/wp/TEMPLATE.md`); WP-2153's P3 stands, since the warning fires
  and a reseed is the workaround. The traps go in the manual's TOPAS page as well as the
  skill row, the page an agent porting a TOPAS input reads.

  Next: none here. The milestone's last open row is the agent port of the input. WP-2153
  should read how TOPAS treats a negative Γ_G² before it chooses among its options.

- **2026-11-22** — Filed by the session closing WP-2107, from its handover's next action
  and the milestone row's last clause. No open WP owns a real-data ZrP₂O₇ run: 1964 and
  1325 are closed, and 2103 owns the WO₃ mirrored protocol only. Premises checked on main
  f590981ab. Next: the new arm.

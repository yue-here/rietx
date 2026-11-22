# WP-2151 — the ZrP₂O₇ input's peak equations on its data

Milestone: parametric · Status: ⬜
Depends on: —
Priority: P2 2026-11-22 — a feature the open milestone was opened for: the last unmeasured clause of the ZrP₂O₇ acceptance row

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

- [ ] A new arm in `docs/wp/1964-measure/zrp2o7_formula.py`: the formula fit of arm (d)
  plus the `shift` equation and both width equations per phase, each coefficient shared
  across patterns, the instrument's width terms held. Seed from the input's stored values.
- [ ] Run it on the 37 patterns. Report each coefficient with its esd beside the input's
  stored value, the calibration's b, c and d beside arm (d)'s, Rwp beside 31.488 % and
  TOPAS's 31.56 %, the free-parameter count, every diagnostic code, and the wall clock as
  a range with the machine's load. Save obs/calc/diff PNGs for patterns 0, 18 and 36 to
  `tests/output/` and look at them.
- [ ] Report whether closing the plan at `CLOSING_WINDOW_TOL` moves any coefficient by
  more than 0.5 esd.
- [ ] Update the milestone's ZrP₂O₇ row with one sentence naming the result, and the
  record of the release in flight.
- [ ] Skill: none expected. If the run shows a trap an agent porting this input would
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

- **2026-11-22** — Filed by the session closing WP-2107, from its handover's next action
  and the milestone row's last clause. No open WP owns a real-data ZrP₂O₇ run: 1964 and
  1325 are closed, and 2103 owns the WO₃ mirrored protocol only. Premises checked on main
  f590981ab. Next: the new arm.

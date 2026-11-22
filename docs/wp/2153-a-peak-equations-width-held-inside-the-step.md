# WP-2153 — a peak equation's width held inside the step

Milestone: parametric · Status: ⬜
Depends on: —
Priority: P3 2026-11-22 — a workaround covers it: `PEAK_WIDTH_NOT_POSITIVE` reports a width that went below zero after the fit, and TRF or a refit from a better start avoids it

## Goal

The LM driver keeps a peak's total width positive inside each step, a peak equation's
term included, wherever that can be done exactly. Where it cannot, the WP records why and
what the user sees.

## Context

**What the rows do today.** The default LM driver holds two families of linear
inequalities inside the step (WP-1938 D8): Γ_G² ≥ ε, with ε = `caglioti._MIN_GAMMA_G2`
= 1e-8 deg², and Γ_L ≥ 0, one row per (emission line, reflection). They are built in
`optimize/least_squares.py` by `gaussian_width_inequalities` (line 2698 on main
f590981ab) and `lorentzian_width_inequalities` (line 2802), and for a joint fit by
`_joint_width_inequalities` (line 2907). Each row is exactly affine in θ (the parameter
vector) because its terms are table rows: p = C·θ + d, at the Bragg angles frozen for the
stage. A row the start already violates is dropped, since the step keeps feasibility and
cannot restore it. A row no free column reaches is dropped too.

**Why the Gaussian row exists.** Under ε, `gaussian_fwhm` clamps Γ_G = √max(Γ_G², ε),
and every Gaussian width column is exactly zero there. A step that lands under the clamp
stops the stage in place. Before the rows, the 150 K Cr₂WO₆ fixture ended at Rwp 0.25458
under LM against TRF's 0.09924, with Γ_G² under ε at 31 of 31 reflections (the
function's docstring).

**The gap** (WP-2107's review, finding 2, left open at its close). The rows read the
built-in terms alone: U, V, W, `gauss_strain`, `gauss_size`; X, Y, `lor_size`,
`lor_strain`. A peak equation (WP-2107) adds its own term. A `gauss_fwhm_squared` term
adds to Γ_G² before the floor, and a `lor_fwhm` term adds to Γ_L
(`CompiledModel` docstring near `model/forward.py:1567`). Either may be negative:
Stinton & Evans's per-phase TCHZ stores a negative v and w for two of ZrP₂O₇'s three
phases. So two things follow.

1. A negative equation term can take the total under the floor inside a step. The
   Gaussian columns then go to zero, the same stall the rows were built to prevent.
   `PEAK_WIDTH_NOT_POSITIVE` (`staged.check_peak_width_positive`) reports it at the
   answer.
2. A positive equation term makes the built-in row stricter than the total needs. A
   built-in term that could go negative while the total stays positive is held at the
   row. This one is a hypothesis: no fit has shown it.

Where the instrument's terms are held, as the ZrP₂O₇ protocol holds them, no free column
reaches the built-in rows, so none is built, and the equation's coefficients are held by
nothing inside the step.

**The design options.** These are recorded at filing. A measurement on a fixture chooses
between them, so the choice is this WP's to settle and record.

- **A. Leave it.** The guard reports after the fit. Costs nothing, and a user meets a
  stalled stage with a warning that names the reflections.
- **B. Add the term to the row where it is linear in its coefficients.** At frozen
  angles, a `gauss_fwhm_squared` or `lor_fwhm` expression that is affine in its
  coefficients (the TCHZ forms u·tan²θ + v·tanθ + w + z/cos²θ and x·tanθ + y/cosθ are)
  gives each row an exact extra block: its coefficient gradient, mapped through C. The
  gradient comes from `model.peak_equations.gradient`. Affinity can be tested at compile
  by evaluating that gradient at the stored and at trial coefficients, as `check_orbits`
  does for single-valuedness. A `gauss_fwhm` term enters as f², so it is never affine and
  takes A or C. B fixes both directions above for the forms ZrP₂O₇ uses.
- **C. Linearise a nonlinear term at the stage's start.** The row is then approximate. It
  can let a step cross the floor or refuse a feasible one, and the frozen angles already
  make it approximate in the cell. Re-linearised between stages only, so frozen-per-stage
  discreteness holds.
- **D. A nonlinear constraint in the step.** `optimize/lm.py`'s `LinearInequality` is the
  only kind the driver holds. Recorded so it is not re-derived, and out of scope.

For an equation B does not cover, keeping or dropping the built-in row is a second call:
kept, it can over-restrict; dropped, nothing holds the built-in terms. Record which.

**Practice.** GSAS-II clamps the width (`GSASIIstrMath.GetReflSigGamCW`, σ ≥ 0.001
centideg²), and its Marquardt takes no bounds (the function's docstring). TOPAS's
handling of a negative equation width is not checked. Read the Technical Reference before
choosing, and record what it says in `docs/practice.md`.

**Tier.** Physics: a width is positive. No threshold is added. ε is the existing floor.

### Inherited

- **2026-11-22, from WP-2151 (the ZrP₂O₇ real-data run).** The gap is reachable on real
  data, in a third form none of A-D addresses: a term that starts below the floor at every
  reflection. The input's stored silicon TCHZ gives Γ_G² = −0.0055 deg² at 15° and
  −0.0029 at 90°. So all four Gaussian coefficients start with zero gradient. They stay
  exactly where they started, with no esd, and `PEAK_WIDTH_NOT_POSITIVE` fires at 7 of 7
  reflections. A row the start violates is dropped (above), so no row helps either.
  Lifting w alone until the smallest Γ_G² is 0.002 deg² gave χ² 197573.6 against 201508.1
  on 1167 free parameters, which took Rwp from 31.793 % to 31.481 %. The fitted silicon
  Γ_G² then runs 0.0069 to 0.0034 deg², close to the size of the stored values with the
  sign flipped. Silicon's Lorentzian x and y also returned to the input's values. One
  hypothesis fits that: TOPAS reads a negative Γ_G² as its magnitude. It is not checked,
  so this WP's TOPAS reading in § Practice should look for it. The numbers are in
  WP-2151's handover entry.

## Non-goals

- TRF, which keeps its iterates feasible by its own means. Its guards stay as they are.
- A bound on a coefficient. The total couples every coefficient, so no box bound holds it.

## Tasks

- [ ] A fixture: a synthetic phase whose `gauss_fwhm_squared` equation's optimum sits
  near the floor, started so the step wants to cross it. Show LM stalling against TRF
  (Rwp and the coefficients), or show that no reasonable start stalls and close on A.
- [ ] A second fixture for direction 2, with a positive equation term and a free W.
  Report whether the built-in row binds where the total would not.
- [ ] Choose among A-D on those numbers, write the choice and its grounds here, and build
  it in all three row builders.
- [ ] Tests: the stall fixture lands where TRF lands, and a nonlinear equation follows
  the recorded rule.
- [ ] The functions' docstrings, the guard's docstring, and the skill's row for
  `PEAK_WIDTH_NOT_POSITIVE` if what it means changes.

## Acceptance

On the stall fixture LM lands within 0.1 esd of TRF on every coefficient, or the WP
closes on option A with the fixture's numbers recorded.

```sh
.venv/bin/python -m pytest tests/test_peak_equations.py tests/test_gaussian_width_floor.py tests/test_lm_solver.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95, § 4.2.
- WP-2107 (peak equations, review finding 2), WP-1938 (the rows held inside the step),
  WP-1937 (the bounded step solved exactly).

## Handover log

- **2026-11-22** — Filed by the session closing WP-2107, from its review finding 2, left
  open there. No open WP owns the LM width rows: 1937, 1938 and 1325 are closed. Premises
  checked on main f590981ab: neither row builder reads `peak_equations`. Next: the stall
  fixture.

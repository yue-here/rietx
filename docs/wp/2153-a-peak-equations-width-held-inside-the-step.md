# WP-2153 — a peak equation's width held inside the step

Milestone: parametric · Status: ✅ 2026-11-22 — option B: an exact equation term enters the LM width rows; PR #1784
Depends on: —

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
   row. Filed as a hypothesis; measured on 2026-11-22 (§ Tasks, the second fixture).

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
choosing, and record what it says in `docs/practice.md`. Read 2026-11-22: the TOPAS 5
Technical Reference gives TCHZ's G = (U tan²θ + V tanθ + W + Z/cos²θ)^0.5 (§ 6.2, p. 27)
and says nothing about a negative radicand, and `force_positive_fwhm` is not in v5. So
the hypothesis below, that TOPAS reads a negative Γ_G² as its magnitude, stays
unchecked. `docs/practice.md` § Peak-width limits carries the reading.

**Tier.** Physics: a width is positive. No threshold is added. ε is the existing floor.

**A third form, from WP-2151's ZrP₂O₇ run** (inherited 2026-11-22, folded here at the
close). A term can start below the floor at every reflection. The input's stored silicon
TCHZ gives Γ_G² = −0.0055 deg² at 15° and −0.0029 at 90°, so all four Gaussian
coefficients start with zero gradient. They stay where they started, with no esd, and
`PEAK_WIDTH_NOT_POSITIVE` fires at 7 of 7 reflections. Lifting w alone until the smallest
Γ_G² is 0.002 deg² took Rwp from 31.793 % to 31.481 %, and the fitted silicon Γ_G² then
ran 0.0069 to 0.0034 deg², close to the stored values with the sign flipped. One
hypothesis fits that: TOPAS reads a negative Γ_G² as its magnitude. § Practice found
nothing to check it against. The numbers are in WP-2151's handover entry.

### Decision

Settled by Claude on 2026-11-22 under the WP's own rule (a measurement on a fixture
chooses between the recorded options), the root CLAUDE.md rule that a bound on a
combination is an LM `LinearInequality`, and the WP's goal (exact, or recorded where
not). A fresh subagent reviewed the evidence and options blind and picked the same on
every question.

- **B is built.** `optimize.least_squares._equation_width_rows` adds a width equation's
  term to every Γ_G² and Γ_L row where it is exact at the frozen angles. With its
  coefficients held, it adds the equation's value as a constant, and a `gauss_fwhm`
  value enters squared. With a free coefficient, it adds the exact block T = G·C,
  c = f₀ − T·θ₀, where G is the coefficient gradient. That needs the expression to be
  affine in its coefficients. Both row builders call it, so the joint builder inherits it.
- **Affinity is read off the tree** (`model.peak_equations.is_affine`), never sampled. A
  sampled gradient can miss a kink such as `abs(c)` or `max(c, 0)`. The structural test
  can only err towards "not affine", which sends the equation to the next rule.
- **A term that is not exact is left out, and the built-in row is kept.** That covers a
  free `gauss_fwhm`, a non-affine term with a free coefficient, a derived coefficient
  and a non-finite value. A `gauss_fwhm` term is f² ≥ 0, so its row stays a sufficient
  condition. For a non-affine term the row is neither sufficient nor necessary. It is
  what main already builds, and dropping it would unprotect U, V and W on no
  measurement. `PEAK_WIDTH_NOT_POSITIVE` reports the total at the answer. C (linearise)
  and D (nonlinear constraint) are not built.
- **A start below the floor stays the report's** (WP-2151's silicon). A row the start
  violates is dropped by every builder, because the step keeps feasibility and cannot
  restore it. Lifting a coefficient automatically would be a new automatic action with
  a chosen target, and refiners split on what to do (raise w, flip a sign, edit by hand).
  The skill's `PEAK_WIDTH_NOT_POSITIVE` row already says to raise the constant term.
- **What the rows still miss:** an equation reading `d`, `theta` or `two_theta` follows
  a free cell, λ or zero shift in the forward model. Its row stays where the stage
  started, as the built-in rows do for the cell.

## Non-goals

- TRF, which keeps its iterates feasible by its own means. Its guards stay as they are.
- A bound on a coefficient. The total couples every coefficient, so no box bound holds it.

## Tasks

- [x] A fixture: a synthetic phase whose `gauss_fwhm_squared` equation's optimum sits
  near the floor, started so the step wants to cross it. Show LM stalling against TRF
  (Rwp and the coefficients), or show that no reasonable start stalls and close on A.
  Done 2026-11-22: the floor test's LaB₆ with U, V, W held and the width carried by a
  TCHZ equation, started at u = v = 0, w = 1. Before the fix LM stepped w to −0.150,
  Γ_G² sat under ε at 19 of 19 reflections, and the fit stopped at Rwp 0.195 against
  TRF's 0.0416, with u, v and w 27-427 esd from TRF's.
- [x] A second fixture for direction 2, with a positive equation term and a free W.
  Report whether the built-in row binds where the total would not. It does: a held
  term s = 3e-5 deg² with free U, V, W, X, the truth's built-in Γ_G² dipping to −1.4e-5.
  The built-in row held that sum at ε, and LM ended at Rwp 0.143 against TRF's 0.0418,
  U, V, W and X 5-115 esd from TRF's. So direction 2 is measured, no longer a hypothesis.
- [x] Choose among A-D on those numbers, write the choice and its grounds here, and build
  it in all three row builders. B, § Decision below; the joint builder inherits it.
- [x] Tests: the stall fixture lands where TRF lands, and a nonlinear equation follows
  the recorded rule. With B, LM lands within 0.0025 esd of TRF on the stall fixture and
  within 3e-5 esd on the direction-2 one. Both tests fail with the block removed.
- [x] The functions' docstrings, the guard's docstring, and the skill's row for
  `PEAK_WIDTH_NOT_POSITIVE` if what it means changes. Docstrings, the theory page's two
  row paragraphs and `docs/practice.md` updated. The skill row is unchanged: the code
  still means a total below zero at the answer, and its advice still holds.

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

- **2026-11-22** — Closed by a ghostshift runner, PR #1784. The default LM driver now
  keeps a peak's total width positive inside each step with a width peak equation's term
  included, wherever that term is exact. Before, an equation carrying the Gaussian width
  could step it below zero and stall the fit far from TRF's answer, and a held positive
  term could make the instrument's own row bind where the total did not. Both are measured
  and both now land on TRF's answer. A term that is not exact, and a term that starts
  below zero, are still left to `PEAK_WIDTH_NOT_POSITIVE` after the fit.
  *Done:* `_equation_width_rows` in `optimize/least_squares.py`, called by both row
  builders; `is_affine` in `model/peak_equations.py`; § Decision above; docstrings of the
  builders and of three guards in `strategy/staged.py`; the theory page's two row
  paragraphs; `docs/practice.md` § A width an equation sets. No derivative path was added,
  so `tests/test_cross_backend.py` is unchanged. The skill row is unchanged.
  *Measured* ([dev] venv, macOS arm64): the two fixtures in § Tasks; the TOPAS 5
  Technical Reference reading in § Practice. Fast selection on 20ea53959 (the review's
  fixes in 16b14ae3b change docstrings and test set-up only): 15151 passed, 443 skipped,
  32 xfailed, with 17 test cases added in `tests/test_peak_equations.py`, 1.29 s between
  them; no base count was taken, so the +17 is from the diff, not a measured difference.
  The full suite did not run: only fits with a width equation reach the change, and
  their files (`test_peak_equations`, `test_parametric_expression`, `test_magnetic`,
  `test_textdoc`, `test_cross_backend`, the examples) pass. `tests.reader_output` exit 0.
  *Review:* a blind subagent chose B, the kept built-in row, structural affinity and the
  report for a start below zero, as § Decision does. `/code-review high` found seven nits,
  all fixed in 16b14ae3b. *Generality:* not dispatched. The audit table is untouched, and
  the change adds no threshold or data-driven choice: an exact term enters, an inexact one
  stays out. *CI fix:* Linux CI found TRF from the stall fixture's start stalled under
  the floor too, every esd `None`. Nudging w's start by k·1e-14 reproduced it here: TRF
  stalled in 5 of 7 starts (Rwp 0.191-0.195), and LM landed on the minimum in 7 of 7.
  Nothing holds the total width inside TRF's step, a non-goal here. So the reference is
  now TRF started at the truth, and the free test runs three nudged starts.
  *Gotchas:* `make_lab6`'s cell is free by default, so a "step" on a test table
  must move only the columns it means to. A condition in an equation cannot read a
  coefficient (the schema refuses it), so `is_affine`'s `if` branch only ever sees a
  coefficient-free condition.
  Next: nothing in this WP. A TOPAS run on a negative TCHZ Γ_G² would settle the WP-2151
  hypothesis, if anyone has TOPAS to hand.
- **2026-11-22** — Filed by the session closing WP-2107, from its review finding 2, left
  open there. No open WP owns the LM width rows: 1937, 1938 and 1325 are closed. Premises
  checked on main f590981ab: neither row builder reads `peak_equations`. Next: the stall
  fixture.

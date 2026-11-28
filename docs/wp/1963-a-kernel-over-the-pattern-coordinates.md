# WP-1963 — a kernel over the pattern coordinates: honest intervals where no pattern sees the parameter

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1325 (the joint path, its parametric tie and its form test)
Priority: P3 2026-10-14 — the benefit is measured on synthetic ramps only, its tuning recipe failed there, and 1325's exposure task flags the extrapolated values first

## Goal

A joint fit can let a parameter vary smoothly across the pattern coordinates
under a kernel prior. Where no pattern sees the parameter, its interval then
widens to what the data allow, instead of inheriting a declared equation's
confidence.

## Context

Filed as a stub on 2026-10-14, at the maintainer's decision, from WP-1325's
fifth session. WP-1325's Non-goals named this work as a follow-up; no open
WP owned it.

**The failure it answers, measured in 1325.** A parametric tie declares
p_k = Φ_k·c across patterns. On `1325-measure/kernel_ramp.py`'s weak regime
(a minor phase fading below the WP-1301 hold, so later patterns cannot see
its cell), a curved truth gave the tie's per-pattern values a coverage of
0.03 at 2 esd in the patterns that cannot see the phase, and 0.66 under a
kink. The intervals are confidently wrong there.

**Why 1325's form test does not cover it.** The test
(`params.parametric.form_tests`, WP-1325 § Measured: the form test) checks
the declared form only where a pattern measures the target. On the same
ramps it rejected a bent truth in 0 of 20 seeds, and so did a full untied
refit. An equation is unchecked exactly where it is extrapolated. 1325's
§ Measured: where one pattern cannot see the parameter ended "a lack-of-fit
check could give [honest intervals] more cheaply"; the form test's
measurement withdrew that.

**What a kernel bought there, and what failed.** From the same section:
- At hand-set hyperparameters (`kernel_fix`, s = L/4, ℓ = half the ramp)
  the coverage in those patterns was 0.57 (curve) and 0.91 (kink), against
  the tie's 0.03 and 0.66, at a worse RMSE than the tie on the line and the
  kink. Honest intervals, not better estimates.
- Hyperparameters by REML on the chain's surviving points failed: the
  near-threshold survivors read as curvature (s/σ ≈ 60-180 in 7-10 seeds of
  20), the extrapolation into the gaps reached RMSE 73-77 against the line's
  10, and one seed gave a slope of −48 059. Any recipe has to avoid reading
  those points.
- Broad, overlapped peaks alone stayed linear, and there the tie, the kernel
  and the line agreed.

**The survey.** WP-1325 § A kernel over the coordinates places a kernel in
the family of forms (P-splines, Gaussian-process and Kalman smoothing, the
PET kernel method) and lists its costs and scaling; the literature is in
1325's References. Concepts from papers only (root CLAUDE.md § Licensing).

**Seams.**
- Prior rows are a block below the data in the joint residual, the seam
  [1995](1995-soft-restraints-in-a-joint-fit.md) built for soft restraints
  (`optimize.least_squares._multi_closures`, each model's blocks read off
  `rows.layout`). `kernel_ramp.py` still appends them in a script-only
  replacement of `_multi_closures`.
- Whether prior rows take the χ²_red·f² covariance factor: the script gave
  them the package's penalty-row treatment, and 1325's survey says they
  should take neither.
- Scale: hundreds of patterns, so a dense kernel matrix over the coordinates
  is the first cost to measure against a sparse or state-space form.

### Inherited

- **2026-10-14, from [1325](1325-parametric-series.md) (seventh session,
  PR #977): the blind regime is now named per equation.**
  `PARAMETRIC_TARGET_UNSEEN` lists, for each equation, the patterns where the
  target's phase is unseen and the value is the equation's alone. Its predicate is
  `multi._parametric_unseen`, which the form test's skip also reads. A kernel
  prior serves exactly those patterns. `ParametricValue.outside` flags
  extrapolation by each coordinate's range alone, so a 2-D point inside both
  ranges and far from every pattern is not flagged. A kernel's posterior
  variance would see it.
- **From WP-1966 (2026-10-14): the `WP-1963:` commits of 2026-10-14 are not
  this WP's.** WP-1966 was filed as 1963 the same afternoon this WP was, and
  was renumbered at `7f7b44e0`. Every `WP-1963:`-prefixed commit up to that
  one is the JupyterLite work, so `git log --grep WP-1963` finds it too. The
  session-start hook read those commits as this WP's work and flagged a
  repair. This note touches the file after them and clears the flag.

## Non-goals

- Replacing the hard tie. It earned a measured precision gain in the same
  regime (WP-1325).
- Equations nonlinear in their coefficients: [1964](1964-a-parametric-equation-the-user-writes.md).
- A pattern summed over several specimens ([1962](1962-xrd-ct-a-pattern-summed-over-the-voxels-its-beam-crosses.md)).

## Tasks

- [ ] **Scope against real data first.** When the outside lab's library
  arrives, count how many of their targets' patterns the form test leaves
  out (`ParametricFormTest.n_patterns` against the subset). If their weak,
  broad features are not in the blind regime, this WP may close as moot.
- [ ] Hyperparameters by a rule that does not read the near-threshold
  survivors.
- [ ] Prior rows in the joint residual, and their covariance treatment.
- [ ] Tests on `kernel_ramp.py`'s W and O regimes; obs/calc/diff PNGs to
  `tests/output/`.
- [ ] Skill: the series reference's parametric row, or "none" and why.

## Acceptance

To be fixed when the WP is scoped. The measured bar it starts from: in the
patterns that cannot see the target, coverage at 2 esd near 0.95 under
`kernel_ramp.py`'s curve and kink, with the line truth's slope scatter no
worse than the tie's.

```sh
.venv/bin/python -m pytest tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1325 § A kernel over the coordinates, § Measured: where one pattern
  cannot see the parameter, § Measured: the form test, and its References.

## Handover log

- **2026-10-14** — Filed as a stub at the maintainer's decision, from
  WP-1325's fifth session. No open WP owned it: 1325's Non-goals named the
  kernel as a follow-up. Context restates the measurements it rests on. Next:
  the first task, once the outside lab's library arrives.

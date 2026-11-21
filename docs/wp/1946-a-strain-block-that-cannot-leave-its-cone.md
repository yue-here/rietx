# WP-1946 — a strain block that cannot leave its cone

Milestone: unscheduled · Status: 🛑 2026-11-17 — no sum-of-squares form reaches the bar: brucite's physical optimum sits on the cone's edge
Track: What fires, and what stays silent
Depends on: 1938 (LM the default driver, and the measurement below); 1467 (the clamp's messages; closed 2026-11-02)

## Goal

The Stephens block refines through a form whose σ²(hkl) cannot be negative,
so no fit reaches the cone's edge. On round-robin brucite, five starts 1e-14
apart reach one answer under the default driver.

## Context

**Why** (WP-1938, 2026-10-11; macOS arm64, `[dev]`). LM holds σ²(hkl) ≥ 0 at
every reflection as a linear inequality (`least_squares.strain_cone_inequalities`),
and since WP-1938's D8 its step solves that inequality exactly. On brucite with
the block (`tests/test_acceptance_stephens.py`'s plan), 6 of 43 reflections
end exactly on the edge, σ² = 0. The width goes as √σ², so its slope from
inside is infinite there. Lifting any of the six raises the cost at every step
size, as √h: +0.0032 at 1e-6, +0.10 at 1e-3, +3.3 at 1. So each edge point is
a genuine minimum in that direction. The columns are forward differences
(`least_squares._peak_chain_column`). For an edge reflection a step in a
coefficient either enters the cone and reads the √ secant, about 1/√h, or
leaves it and reads exactly 0. LM then stalls `exhausted_fp64`. All five
starts end with the same six reflections on the edge, at costs up to 4e-5
apart: χ²_red 7.7177-7.7202.

**A floor was measured and declined.** Holding σ² ≥ ε²·M² (a minimum strain ε
for every reflection) makes the edge smooth. At ε = 1 ppm every stage ends
`ftol_runs` and five starts agree, χ²_red 7.74062688-7.74062689. That is 0.3 %
worse than the stall points. At 0.1 ppm and 0.01 ppm the stall returns, at
7.6999-7.7008 and 7.7359-7.7362. The basin moves with the floor's value, so
the floor would be a tuned constant. WP-1938 closed the stall as a recorded
exception instead (its D9).

**Prior art** (a survey on 2026-10-11). No code or paper found keeps σ² ≥ 0
during refinement.

- GSAS-II 5.8.4: `GSASIIstrMath.GetSampleSigGam` takes `np.sqrt(Sum)` with no
  guard (:3265), so a negative sum gives NaN. `GetSampleSigGamDerv` carries the
  1/(2√Sum) slope unguarded.
- TOPAS has no Stephens model of its own. Community macros compute
  `Sqrt(Max(mhkl,0))`, which is rietx's mask (`stephens.strain_width_deg`).
- FullProf's manual does not discuss a negative σ².
- Stephens (1999) derives σ² from a covariance matrix of the metric, which is
  non-negative by construction. The 15 grouped S_HKL that every code refines
  lose that guarantee.
- No diffraction paper was found that parameterises the quartic to stay
  non-negative. No source was found for a Cholesky form of anisotropic ADPs
  either.

**The idea.** Hilbert (1888) proved that every non-negative ternary quartic
form is a sum of three squares of quadratic forms. With v = (h², k², l², kl,
hl, hk), σ²(hkl) = ‖Lᵀv‖² for a 6×3 matrix L. That is 18 numbers less the
3 of a rotation of L's columns, which leaves 15, the dimension of ternary
quartics. (The count is the survey's, unchecked.) The isotropic seed
S = ε²·[M²] is rank one in this form. M = vᵀg with g = (G\*₁₁, G\*₂₂, G\*₃₃,
2G\*₂₃, 2G\*₁₃, 2G\*₁₂), so L's first column is ε·g and the others are zero.

**Open questions, in the order they could kill the idea.**

1. Symmetry. Each Laue class allows a subspace of S_HKL, derived from the
   operators (`crystallography/stephens.py`). The form must reach every
   non-negative member of that subspace and nothing outside it. Averaging the
   Gram form over the group is one route. It needs a proof per class, or a
   measured counter-example.
2. The rotation. L's 3-dimensional rotational freedom gives the solver flat
   directions. Fix it, e.g. a lower-triangular L, and check that this loses no
   member of the cone.
3. The corner at zero. A reflection whose width is exactly zero needs Lᵀv = 0.
   The width ‖Lᵀv‖ then has a V-shaped corner with finite slopes, where √σ²
   had an infinite one. Measure whether LM converges there before relying on it.
4. Reporting. S_HKL stay the quoted coefficients, derived from L. Their esds go
   through the whole covariance, as `model/geometry.py` does for a derived
   quantity (root CLAUDE.md).

**Licensing.** GSAS-II for concepts only. TOPAS through its manual only.

**A joint fit never seeds the block** (WP-1467's close, carried from WP-2002,
PR #1113; still true on 2026-11-17 at `7b761b54d`).
`MultiHistogramRefinement.fit`'s stage loop calls `seed_floored` alone
(`multi.py` ~2030), never `seed_stephens`, so a joint fit through
`lab_sample_refine` starts a freed all-zero block at S ≡ 0, where the width's
square root has unbounded slope, and nothing says so. A joint fit also holds
no cone under either driver. Fixing the seed moves joint fits that seed a
block. On brucite (`[dev]`, macOS arm64) the start barely matters under LM
(χ²_red 7.8939-7.8945 from 1000 ppm, 800 ppm and the isotropic fit's 29 ppm,
all 0 of 43 reflections outside the cone) and matters under TRF
(7.7965-7.9267, 19-23 of 43 outside); measured by WP-1467.

## Non-goals

- TRF's guard (`STEPHENS_STRAIN_NOT_POSITIVE`) and the clamp's messages:
  WP-1467.
- Rendering the strain surface: WP-1318.
- Anisotropic size broadening, which brucite's platelets may carry instead.

## Tasks

- [x] Symmetry: show the group-averaged Gram form reaches each Laue class's
      non-negative cone, or find the class where it fails. Write the map
      L → S_HKL per class. *Done 2026-11-17: it reaches every class's cone,
      by one argument for all classes, with S = R̄·π(L·Lᵀ) the map for each
      (R̄ the group average from the operators). Every class but -1 carries
      flat directions in that map. Proof and map in the docstring of
      `examples/probe_stephens_sos.py`, per-class counts from its `--classes`.*
- [x] Prototype on brucite outside the package: five starts 1e-14 apart under
      LM with no cone inequality. Compare χ²_red and its spread with WP-1938's
      7.7177-7.7202 and with TRF's 7.636 outside the cone. *Done 2026-11-17
      (`examples/probe_stephens_sos.py --forms …`). Those two references have
      moved: on today's main LM gives 7.888124-7.894550 (spread 8.1e-4) and
      TRF 7.803376-7.926666 (1.6e-2). No form that leaves its seed comes near
      the 1e-9 bar: 1.8e-4 for the general form from a turned seed and 2.8e-2
      for a four-parameter -3m1 form. The general form seeded along c* reads
      1.3e-9 only because it never moves. Numbers in the 2026-11-17 handover
      entry.*
- [x] Decide from the prototype: adopt it, or close 🛑 with the numbers.
      *Closed 🛑 2026-11-17: the 2026-11-17 handover entry has the numbers.*
- [ ] ~~If adopted: the parameter rows and their seed, S_HKL reported with
      full-covariance esds, the manual's Part 2 equation with its `*Source:*`
      line, a `test_cross_backend.py` config for the new derivative path, and
      tests plus obs/calc/diff PNGs to `tests/output/`.~~ **Not adopted.**
- [ ] ~~Skill: the `STEPHENS_STRAIN_NOT_POSITIVE` and `CONSTRAINT_ACTIVE` rows,
      if the default driver no longer builds a cone.~~ **Not reached**: the
      default driver still builds its cone.

## Acceptance

Brucite + Stephens, five starts 1e-14 apart under the default driver: χ²_red
spread under 1e-9, the bar of WP-1938's grid, with no cone inequality built.

```sh
.venv/bin/python examples/probe_driver_grid.py --fits brucite_aniso
.venv/bin/python -m ruff check src tests examples
```

## References

- Stephens, P. W. (1999). *J. Appl. Cryst.* 32, 281-289.
- Popa, N. C. (1998). *J. Appl. Cryst.* 31, 176-180.
- Hilbert, D. (1888). Über die Darstellung definiter Formen als Summe von
  Formenquadraten. *Math. Ann.* 32, 342-350.
- Pfister, A. & Scheiderer, C. (2010). An elementary proof of Hilbert's
  theorem on ternary quartics. arXiv:1009.3144.
- Coelho, A. A. TOPAS-Academic V5 Technical Reference, §4.2 and §7.23.

## Handover log

- **2026-11-17** — closed 🛑. Writing the strain variance as a sum of squares
  does reach every Laue class's physical set, and one argument proves it for all
  classes at once. It fails as a refinement on brucite, for two reasons. Both
  general maps (a lower-trapezoidal L, or an invariant Gram matrix) have
  directions that move nothing in every class but the triclinic one. And
  brucite's best physical answer sits on the edge of the
  set, where a sum-of-squares form loses its derivative, so the cone's edge
  comes back through the parametrisation. Five starts 1e-14 apart that leave
  their seed spread by 1.8e-4 and 2.8e-2, against the 1e-9 bar and today's default driver's 8.1e-4.
  The search also found that the default driver's cone holds only at the fitted
  reflections. Its brucite answer is negative on about 1 % of directions between
  them, and the manual now says so.

  *Done.* Inherited pruned on arrival. The platform split (WP-1930) is answered
  without a second platform: on macOS alone, five starts 1e-14 apart put TRF's
  brucite Rwp anywhere in 0.18042-0.18184. That is rounding choosing between
  minima (the 1e-14 rule). `docs/VALIDATION.md` already quotes the current
  values. The joint-fit seed finding is folded into Context and filed as
  yue-here/rietx#1663, since it outlives this WP. New
  `examples/probe_stephens_sos.py`, outside the package, holds the symmetry
  argument (docstring), the per-class table (`--classes`) and the brucite forms
  (`--forms`). Manual `theory/microstructure.md` § The positivity cone now
  says that the LM rows and the guard read the fitted reflections only. WP-1318
  inherits that finding, since a render is where a negative lobe would show.
  PR #1662.

  *Symmetry* (task 1). S(L) = R̄·π(L·Lᵀ), with R̄ the group average of the
  monomial action and π the Gram-to-quartic map. Its image is a class's
  non-negative cone, exactly. Each π(L·Lᵀ)∘g is non-negative, so their average
  is, and it is invariant. Conversely, an invariant non-negative quartic is a
  sum of three squares (Hilbert), and R̄ fixes it. So no per-class proof is
  needed, and the map is the same expression in every class. Measured per class
  (`--classes`): the Jacobian has rank m at a random L in all twelve
  representatives, the image is in the allowed span (≤ 6e-16) and is
  non-negative. Flat directions (directions that move nothing) number
  15 − m for a lower-trapezoidal L, so 0 for -1 and up to 13 for cubic. For a
  Gram matrix restricted to the invariant family (c parameters) they number
  c − m, between 1 and 6, never 0.

  *Measured* (macOS arm64, `[dev]`, `src` at `7b761b54d`; brucite + block, five
  starts 1e-14 apart, LM, cone rows off):

  | form | χ²_red | spread | note |
  |---|---|---|---|
  | default LM, cone rows on (today's main) | 7.888124-7.894550 | 8.1e-4 | Rwp 0.18140-0.18147 |
  | default TRF (today's main) | 7.803376-7.926666 | 1.6e-2 | Rwp 0.18042-0.18184 |
  | general form, seed axis along c* | 9.548344 | 1.3e-9 | never leaves the seed: stage `converged`, reason `no_descent`, no parameter moves |
  | general form, turned seed frame | 7.910398-7.911858 | 1.8e-4 | 2 stages at max_iter, every start |
  | -3m1 form, 4 parameters | 7.903063-8.126565 | 2.8e-2 | c, d → 0 |

  Every start of every form reports `FLAT_DIRECTION` and `HIGH_CORRELATION`.
  The axis-seeded general form has five columns with no true derivative at the
  seed, where the group average cancels it. They read as rounding noise, about
  1e-8 of the others. The step's column equilibration promotes that noise to
  full directions, so every trial step fails. The four-parameter -3m1 form is
  p = (a·r² + b·z²)² + |c·E₁ + d·E₂|². It reaches 200 random members of the
  -3m1 cone to 3e-16, so its own reach is not the problem. Away from c = d = 0
  its Jacobian has full rank, so it has no flat direction of its own. On
  brucite c and d go to 0, and a ≈ 73, b ≈ −2026 in four of the five starts.
  The fifth stops at a = 47.4, b = −2159, χ²_red 8.127, and alone makes the
  2.8e-2 spread. So the best non-negative quartic is the rank-one
  (a·r² + b·z²)², which is zero on a real cone of directions (|z|/r ≈ 0.19).
  At that point c's and d's columns vanish, and the form gives LM no regular
  minimum there.

  The default LM's answer is outside the true cone. Sampling 200 000 random
  directions in hkl at each of the five LM answers, σ² is negative on
  0.96-1.38 % of them, down to −2514 in units of (1 ppm)²·M², while all 43
  fitted reflections are ≥ 0. The best sum-of-squares answers cost χ²_red
  +0.015 to +0.022 over it, which is the price of the true cone.

  *Gotchas.* A seed where a column has no true derivative puts an exactly flat
  column into LM, and the equilibration turns its noise into a direction. Any future nonlinear block
  seeded at a symmetric point meets the same trap.

  *Review.* `/code-review` was not run (it edits the main checkout); a
  read-only review agent read the branch instead. It found no bug and no
  error in the algebra, and checked every quoted number against the probe's
  output. It found three overstated claims (the seed's zero slots, "no form
  comes near the bar", "every form has flat directions") and nine nits, all
  applied: wording, an unused symbol, a `--forms` name check, and a note that
  the probe's recorded `STEPHENS_STRAIN_NOT_POSITIVE` reads L as S.

  *Generality.* No flag, threshold, default or automatic action is added. The
  probe is outside the package, and the manual edit corrects a sentence. No
  `_audit.py` row; the judge was not dispatched.

  *Next.* None for this WP. yue-here/rietx#1663 (a joint fit never seeds the
  block) is the one leftover. A per-class flat-free form, as for -1 or a cubic
  two-ray sum, was not tried: brucite's optimum on the cone's edge would defeat
  it the same way.

- **2026-10-11** — created from WP-1938's decision D9: the maintainer chose
  a recorded exception there and this WP for the formulation. No open WP owns a
  reparameterisation of the block: 1467 owns the clamp's messages, 1318 a
  rendering.

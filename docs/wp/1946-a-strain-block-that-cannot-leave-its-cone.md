# WP-1946 — a strain block that cannot leave its cone

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1938 (LM the default driver, and the measurement below); 1467 (the clamp's messages; closed 2026-11-02)
Priority: P3 2026-10-11 — no quoted number rests on the scatter it removes, since brucite's S_HKL are declared unquotable; 1938 landed (#883), so nothing hard blocks it

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

### Inherited

- **2026-10-12, from WP-1930 (#832's sweep of 2026-10-08): brucite split
  by platform before WP-1938.** TRF stopped at `max_iter` on Linux (Rwp
  0.18030) and converged on macOS (0.17844), so `docs/VALIDATION.md`'s
  17.84 % brucite figure is the macOS value. The default driver has been LM
  since WP-1938; whether the split survives is unmeasured. This WP re-fits
  brucite's Stephens block, so it is the cheapest place to check both
  platforms.

- **2026-11-02, from WP-1467 (closing): its messages landed, and a joint fit
  still starts a block at S ≡ 0.** 1467 made a block replace the
  `lor_strain` it locks, and `STEPHENS_STRAIN_NOT_POSITIVE` now names the
  intensity share the clamp left at zero strain width (19-52 % over the four
  phases 1467 probed under TRF on three CPD patterns). So the soft
  dependency is discharged. Two findings bear on a formulation that cannot
  leave the cone. (1) Carried from WP-2002 (PR #1113, 2026-10-23):
  `MultiHistogramRefinement.fit`'s stage loop calls only `seed_floored`
  (`multi.py` ~1619), never `seed_stephens`, so a joint fit through
  `lab_sample_refine` starts a freed all-zero block at S ≡ 0, where the
  width's square root has unbounded slope, and nothing says so. A joint fit
  also holds no cone under either driver. Fixing the seed moves joint fits
  that seed a block. (2) Measured on brucite (`[dev]`, macOS arm64), the start
  barely matters under LM (χ²_red 7.8939-7.8945 from 1000 ppm, 800 ppm and the
  isotropic fit's 29 ppm, all 0 of 43 reflections outside the cone) and
  matters under TRF (7.7965-7.9267, 19-23 of 43 outside).

## Non-goals

- TRF's guard (`STEPHENS_STRAIN_NOT_POSITIVE`) and the clamp's messages:
  WP-1467.
- Rendering the strain surface: WP-1318.
- Anisotropic size broadening, which brucite's platelets may carry instead.

## Tasks

- [ ] Symmetry: show the group-averaged Gram form reaches each Laue class's
      non-negative cone, or find the class where it fails. Write the map
      L → S_HKL per class.
- [ ] Prototype on brucite outside the package: five starts 1e-14 apart under
      LM with no cone inequality. Compare χ²_red and its spread with WP-1938's
      7.7177-7.7202 and with TRF's 7.636 outside the cone.
- [ ] Decide from the prototype: adopt it, or close 🛑 with the numbers.
- [ ] If adopted: the parameter rows and their seed, S_HKL reported with
      full-covariance esds, the manual's Part 2 equation with its `*Source:*`
      line, a `test_cross_backend.py` config for the new derivative path, and
      tests plus obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the `STEPHENS_STRAIN_NOT_POSITIVE` and `CONSTRAINT_ACTIVE` rows,
      if the default driver no longer builds a cone.

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

- **2026-10-11** — created from WP-1938's decision D9: the maintainer chose
  a recorded exception there and this WP for the formulation. No open WP owns a
  reparameterisation of the block: 1467 owns the clamp's messages, 1318 a
  rendering.

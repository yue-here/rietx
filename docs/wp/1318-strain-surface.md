# WP-1318 — the Stephens strain surface, rendered

Milestone: unscheduled · Status: ✅ 2026-11-16 — `rx.viz.plot_strain_surface` over `stephens.directional_sigma2`; GUI view and esd band left to #1624 (PR #1620)
Track: Render what the fit already knows
Depends on: —

## Goal

A fitted anisotropic-microstrain block renders as a directional strain
surface — the broadening magnitude over crystallographic directions, the 3-D
surface plot GSAS-II offers — from coefficients rietx already refines. Pure
visualization of an already-modelled quantity; no new physics.

## Context

From issue #197's second half, which the issue itself splits off as the
quick win (its first half, Fourier/difference maps, is fenced — see
Non-goals).

**Everything upstream ships.** The Stephens (1999) model landed as WP-0503
(`crystallography/stephens.py`); coefficients refine as
`phases.i.microstrain.dof.k`; `capabilities()` reports
`features.stephens_strain`. A 3-D rendering path exists
(`src/rietx/gui/structure3d.py` and the GUI's viewer). What is missing is
only the projection: evaluate the directional broadening over the unit
sphere of hkl directions and draw the surface.

**The conventions are load-bearing and already stated in the module** — the
renderer quotes them, never re-derives: √Σ·d²·10⁻⁶ is the **FWHM** (not σ)
of the ΔM/M distribution; the coefficients are in 10⁻¹² Å⁻⁴; they multiply
the **literal** monomials, where other codes fold symmetry multiplicities
in. So the surface's values come from the module's own evaluation of
σ²(M) — a renderer with its own copy of the sum is exactly the second
authority the house rules forbid.

**Read a negative lobe honestly.** σ²(M) ≥ 0 is a cone; a direction where
the fitted form dips negative is what `STEPHENS_STRAIN_NOT_POSITIVE`
already reports (or the lm-solver constraint prevents). The surface should
show such a region as what it is — not clip it silently — because the
picture is precisely where a user will first see an unphysical block.

**Two rendering homes, decided in-WP**: a `viz/` function producing the
house-style figure (committed light/dark pair if it enters the manual, via
`make_figures.py` — the one authority for how manual figures are drawn),
and/or the GUI 3-D view. On esds: coefficient esds exist, so a confidence
band on the surface is derivable via the covariance (the
`model/geometry.py` J·Cov·Jᵀ precedent) — include it only if the
propagation is done properly, absent otherwise, never a diagonal shortcut.

**The sphere sampler exists** (folded from `### Inherited`, 2026-11-16):
[WP-1960](1960-spherical-harmonics-texture.md) landed first, so the
directions come from `crystallography.spherical_harmonics.sphere_points`,
the sampler its texture surface and positivity guard already use, never a
second one.

## Non-goals

- **Not Fourier or difference-Fourier maps** — v2+ fence (the McCusker
  audit's entry; the consumer is structure completion, fenced beside
  structure solution). Issue #197 holds that half.
- **Not spherical-harmonics texture** — WP-1960's (shipped, no longer
  fenced; superseded in part 2026-11-16); same family of directional plots,
  different model, not this WP.
- **Not new strain physics, thresholds, or guards** — the cone guard and
  conventions stand as shipped.

## Tasks

- [x] The projection: directional FWHM surface evaluated through
      `crystallography/stephens.py`'s own sum; negative regions rendered as
      unphysical, not clipped. (`stephens.directional_sigma2`, the hkl along a
      unit direction at M = 1 Å⁻² fed to `sigma2_m`; `stephens.reciprocal_frame`
      the Cartesian frame.)
- [x] The `viz/` figure in house figure style; the GUI home decided and, if
      taken, wired to the existing 3-D path with vitest coverage.
      (`rx.viz.plot_strain_surface`, `viz/strain.py`. GUI home **not taken**
      2026-11-16: the GUI frontend is being rebuilt under Yue's claims, so it
      goes to the leftovers issue.)
- [x] Manual: a short section beside the Stephens material, figure pair via
      `make_figures.py`; glossary/help anchors if any new public name
      appears. (`theory/microstructure.md` § The strain surface, equation
      `ms-surface`; `make_figures.strain_surface` draws the pair from the
      acceptance file's brucite TRF fit. No parameter, flag or setting is
      new, so `help.py` has nothing to describe.)
- [x] Tests: surface values pinned against the module's scalar evaluation
      on a corpus case (the brucite/corundum cone-count fixtures exist);
      PNGs to `tests/output/` and looked at. (`tests/test_strain_surface.py`,
      16 fast; the refined pin rides on the brucite TRF fixture in
      `test_acceptance_stephens.py`, slow.)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_strain_surface.py tests/test_acceptance_stephens.py   # first module is new, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: on a refined Stephens fixture the surface's values equal the
module's σ²(M) evaluation direction for direction; an isotropic block draws
a sphere; a deliberately non-positive block shows its unphysical region and
the existing guard's finding beside it.

The shipping PR comments on issue #197 saying its strain half landed —
#197 stays open for the fenced Fourier-maps half.

## References

- Issue #197 (the strain-surface half; GSAS-II parity target).
- Stephens, P. W. (1999), *J. Appl. Cryst.* **32**, 281 — the model whose
  conventions the renderer quotes.
- Root CLAUDE.md § anisotropic strain — the three load-bearing conventions
  restated above.

## Handover log

- **2026-11-16** — closed (ghostshift runner, PR #1620). A fitted Stephens
  block can now be looked at: one call draws its strain broadening over every
  direction of reciprocal space, from the same sum the width law uses, with
  any direction outside the physical cone drawn in red at its true size and
  the guard's finding printed under it. On the brucite acceptance fit under
  TRF the picture shows what that file's assertions say in words: the c*
  lobes broaden to about 2000 ppm while half the sphere, around the basal
  plane, is outside the cone. Nothing about the fit changes; the GUI view and
  a propagated confidence band are not built and wait in #1624.
  - *Done:* `crystallography.stephens.directional_sigma2` (σ²(M)/M² at the
    unit-M hkl B⁻¹u, i.e. `sigma2_m` itself) and `reciprocal_frame` (B, the
    transposed Cholesky factor of G*, a* along x); `viz/strain.py`
    `plot_strain_surface(structure, diagnostics=None, *, phase=0, …)`,
    lazily exported from `rx.viz`, sampling with WP-1960's `sphere_points`;
    `tests/test_strain_surface.py` (16 fast); one slow test on the brucite
    TRF fixture in `test_acceptance_stephens.py` (its xdist group, no new
    fit); theory section `microstructure.md` § The strain surface, equation
    `ms-surface`; `make_figures.strain_surface` and the committed pair.
  - *Decided:* the GUI home is not taken (the GUI frontend is being rebuilt
    under Yue's claims) and the band is absent, because a result carries no
    S_HKL covariance block to propagate and a diagonal one is wrong both ways;
    both are #1624. "Below zero" on the sphere is the guard's
    `STEPHENS_CONE_TOL` applied to σ²/M², so no new threshold; a facet
    touching such a direction is drawn red, so the region is never smaller
    than it is. No flag, threshold or automatic action is added, so there is
    no tier to state and `_audit.py` is untouched.
  - *Measured:* MEASURED_PLACEHOLDER
  - *Review:* a read-only review agent found the silent-guard note claimed
    the region lay between reflections (false for an all-negative block),
    the refined pin could not catch a wrong frame (m cancelled), the note's
    colour broke the notebook dark copy, two wordings, and the colourbar
    shown with no physical facet; all fixed in 3fc87cffd. Its remaining
    point, that the notebook's dark copy keeps the light red for the
    shaded facets, is declined: the dark copy is drawn from the light
    figure by colour mapping, and a shaded facet's colour is no role colour.
  - *Gotchas:* the hull's simplices come in either winding, and matplotlib's
    shading reads the normal, so they are turned outward or the surface draws
    as a checkerboard. Poly3DCollection with `shade=True` needs explicit
    edge colours. A per-value 1e-12 bar fails on Linux at a near-zero
    direction; the bar is relative to the largest value.
  - *Next:* the shipping PR was to comment on #197 that its strain half
    landed (it stays open for the fenced Fourier half); a ghostshift runner
    may not comment, so that is the maintainer's. Then #1624 when the GUI
    rebuild settles.

- **2026-09-01** — created, from issue #197's strain half (2026-09-01
  triage). Settled: values come from the module's own evaluation; first
  open decision is the rendering home (viz figure, GUI view, or both).

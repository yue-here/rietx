# WP-1318 — the Stephens strain surface, rendered

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-09-23 — a view over coefficients already refined

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
- [ ] The `viz/` figure in house figure style; the GUI home decided and, if
      taken, wired to the existing 3-D path with vitest coverage.
- [ ] Manual: a short section beside the Stephens material, figure pair via
      `make_figures.py`; glossary/help anchors if any new public name
      appears.
- [ ] Tests: surface values pinned against the module's scalar evaluation
      on a corpus case (the brucite/corundum cone-count fixtures exist);
      PNGs to `tests/output/` and looked at.

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

- **2026-09-01** — created, from issue #197's strain half (2026-09-01
  triage). Settled: values come from the module's own evaluation; first
  open decision is the rendering home (viz figure, GUI view, or both).

# WP-2234 — The strain surface in the GUI

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: 1318 (the figure and `directional_sigma2`, PR #1620)
Priority: P4 2026-11-21 — was P3 (a view over what the fit already knows): down a rung, since WP-1318's PR #1620 has not merged and where the GUI shows the surface is a visual question nobody has taken

## Goal

A person who refined a Stephens anisotropic-strain block (`Phase.microstrain`) sees its
strain surface in the GUI. It is the same surface `rx.viz.plot_strain_surface` draws, built
from the same values.

## Context

Issue #1624 (mustachefeeling, 2026-11-16), item 1. WP-1318 left the rendering home open: a
`viz/` figure, the GUI's 3-D view, or both. Its PR #1620 ships the figure and leaves the GUI
view, because the GUI's front end is being rebuilt at `/next` under its own WPs (the
gui-overhaul milestone, rounds R1-R7).

**What a view reuses.** WP-1318 adds `crystallography.stephens.directional_sigma2` (σ²(M)/M²
at the unit-M hkl B⁻¹u) and draws it over `crystallography.spherical_harmonics.sphere_points`
(on `main`, WP-1960). A GUI view evaluates the same function on the server and draws its
values. It never computes a second copy of the sum in TypeScript. A direction outside the
physical cone (σ² < 0) is drawn in the figure's way, as √|σ²| in a separate colour, never
clipped. The guard's `STEPHENS_STRAIN_NOT_POSITIVE` finding is shown beside the surface, or a
line saying the guard found nothing. The guard tests reflections and the surface tests the
sphere, so the two can differ.

**Where it could live.** Two homes exist in the rebuild's plan, and choosing between them is a
visual design question for the maintainer (designs come from the GUI workshop):
- WP-2214's inventory row 171 keeps "Trends, attribution, texture, strain (Advanced only)" in
  the Report as a disclosure. Today's `panels/Report.svelte` prints one line there for a phase
  whose strain is directional (`report.strain`).
- The Structure graph (`gui/src/next/Structure.svelte`, R3, WP-2218) already draws a 3-D
  scene, through `GET /api/structure` and `lib/structure3d`.

**Tier.** No rule is added. The view draws values the fit already holds.

**Checked at `c1033a0e8`.** `directional_sigma2` and `plot_strain_surface` are not on `main`
(PR #1620 is open and conflicting on 2026-11-21). No open WP owns a GUI strain view: the
gui-overhaul milestone's rounds name none, and WP-1318 closes with #1620.

### Inherited

## Non-goals

- A confidence band on the surface. It needs the S_HKL block of the covariance, which a result
  does not carry; that half of #1624 is folded into WP-1990, as the first consumer of its
  correlation field.
- Any change to the Stephens model or its guard (WP-1946 owns the cone).

## Tasks

- [ ] Bring the home and the drawing to the maintainer with a workshop mock-up: the Report's
      strain disclosure or the Structure graph, and the drawing of the out-of-cone region.
- [ ] A server route serving `directional_sigma2` over `sphere_points` for one phase, with the
      guard's finding; refused with a reason for a phase without a block.
- [ ] The view in the chosen home, with a vitest mount case and a browser pass on a refined
      brucite block (half its sphere is out of the cone under TRF, WP-1318).
- [ ] Manual: the GUI chapter for the chosen home names the view (`test_gui_manual.py`
      partitions routes and tabs).
- [ ] Skill: none. An agent driving rietx uses `rx.viz.plot_strain_surface`.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_manual.py tests/test_strain_surface.py
```

## References

- Stephens, P. W. (1999). J. Appl. Cryst. 32, 281-289.
- Issue #1624; WP-1318 and PR #1620.

## Handover log

- **2026-11-21** — created, from the 2026-11-21 issue triage (issue #1624, item 1). Checked
  against the tree at `c1033a0e8`: the figure's functions are not on `main` yet, and PR #1620
  is open; no open WP owns a GUI strain view: the gui-overhaul rounds name none, WP-1318
  closes with #1620, and WP-1990 takes only the band. Next: wait for #1620, then the first
  task.

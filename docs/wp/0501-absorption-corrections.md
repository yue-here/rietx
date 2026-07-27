# WP-0501 — Capillary and flat-plate absorption

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Capillary (Debye-Scherrer) and flat-plate absorption (Sabine 1998 /
  Lobanov-Alte da Veiga)

## Context pointers

- Lands beside displacement/transparency in `model/corrections.py`, gated on
  `Geometry.kind` the same way.
- v0.5 milestone acceptance: capillary/absorption vs GSAS-II consistency —
  which means **adopting GSAS-II's protocol**, per
  [../DESIGN.md](../DESIGN.md#testing--validation-policy).
- Distinct from WP-0305 (Brindley acts on QPA fractions; this acts on the
  profile/intensity vs θ).

## Inherited

From **WP-0305** (Brindley, landed 2026-07-23): the per-phase µ machinery
already exists — `crystallography/attenuation.py` interpolating bundled
`data/mu_McMaster.dat` (McMaster 1969, energy-trimmed 2–120 keV, ATTRIBUTION.md
updated). Reuse it rather than rebuilding. It interpolates log-log and
**refuses** a wavelength whose grid interval contains an absorption edge rather
than smearing across it. Measured vs NIST Hubbell-Seltzer at 8 keV: ≤2.5 % for
Z ≥ 9, but B −7 % and O −3.6 % (McMaster's known low-Z weakness) — relevant if
an absorption correction is asserted against a light-element standard.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24): specimen transparency
was measured on SRM 676a corundum and deliberately **kept at 0**. Freeing it is
a wash (Rwp 14.37 → 14.33 %, GoF 1.606 → 1.601, every band Rwp moves < 0.07
points) and merely re-apportions the uniform d-scale across the correlated
{zero, displacement, t} triple — zero −0.075° → −0.012°, displacement +0.008 →
+0.088 mm, µ_eff ≈ 120 cm⁻¹ (solid-alumina-like, not compact-like) — pulling
absolute axes to −202/−171 ppm with no new physics. New absorption terms enter
that same correlated triple and should expect the same trap: judge them by
whether they buy *band-resolved* residual structure, not by Rwp. Do not
silently change the acceptance protocol that holds transparency at 0.

From **WP-0401** (op shim, landed 2026-07-24): `model/corrections.py` is
xp-routed. New correction code calls `xp.*` with `xp = get_backend()` bound
once per compiled-model call, never bare `np.*` and never per-op — otherwise it
breaks the jax and torch backends silently.

From **WP-0504** (anomalous f′/f″, landed 2026-07-27) — three things, one of
which is a trap.

* **µ stays on McMaster; do not switch it to f″.** 0504 bundled a
  Cromer-Liberman f′/f″ table and the optical theorem (σ_photo = 2·r_e·λ·f″,
  `dispersion.photoabsorption_barn`) makes it *look* like µ could be re-sourced
  from it. It cannot: f″ gives **photoabsorption only**, while beam removal
  needs the total, and the Rayleigh + Compton gap is largest for **light**
  elements (photoabsorption ~Z⁴, Rayleigh ~Z²) — exactly where 0305 flagged
  McMaster as weakest. The decision, and the measured numbers, are in 0504.
* **New helper, use it:** `attenuation.photoelectric_cross_section` now exposes
  the photoelectric column separately (0504 split it out of the shared
  interpolator). The edge-refusal behaviour 0305 described is unchanged and now
  lives in `attenuation._interpolate`.
* **The two tables cross-check each other** to 0.04–5.4 % over Z = 8→57 at Cu
  Kα (`test_dispersion.py::test_f_double_prime_reproduces_the_mcmaster_photoabsorption`).
  If an absorption correction ever disagrees with an independent code by more
  than that, the tabulation is not the explanation.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

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

From **WP-0502** (surface roughness, landed 2026-07-27) — this is the sibling
correction and it built most of the machinery you need:

- **Reuse, do not re-derive.** `Geometry.surface_roughness` is the worked
  example of an opt-in, Bragg-Brentano-gated, `kind`-discriminated correction
  block: `params/vector.py:roughness_parameters()` derives dot-paths from
  `model_fields` and is shared by `_collect_instrument` **and**
  `apply_to_models` (one source of truth, so the forgotten-write-back bug is
  unrepresentable); `CompiledModel.roughness` is the compile-time frozen model
  choice; `CompiledModel._roughness_factor()` is the single applier called from
  all three intensity assemblies. An absorption block that multiplies intensity
  should copy that shape verbatim.
- **`optimize/statistics.block_projection_r2(jac, block, targets, nuisance)` is
  now exported** — the QR block-projection core factored out of
  `background_absorption`. Use it rather than writing a third copy.
- **Its `nuisance` argument is the load-bearing part, and 0501 needs it too.**
  Any *multiplicative* correction is trivially ~0.96 "scale-like": projected
  onto a block containing the phase scale, the measured R² moved only
  0.961 → 0.990 across data ranges where identifiability collapsed completely.
  Project the scale and background out first and read the **partial** R².
  Absorption is the same kind of quantity, so a naive R² there will be just as
  blind.
- **A new correction must be judged on reflections, not on the fitted grid.**
  This was found on real data: the IUCr round-robin patterns start at 5° 2θ but
  their first reflections are at 25–32°, and a grid-based fence cheerfully
  reported a 27 % depression that no modelled peak ever saw.
  `_roughness_regime_diagnostics` now evaluates at `phase_peaks` positions.
- **Neither Bragg-Brentano dataset in the repo can constrain a low-angle
  intensity correction.** Measured: qarr corundum/zincite/fluorite have 2–3
  reflections below 40°, SRM 660c starts at 20.3° with LaB6's first line at
  21.4°. If 0501's acceptance needs a real low-angle lever arm, a new dataset
  has to come with it — plan for that rather than discovering it late.
- **Watch for `|ρ| > 1` in the reported correlation matrix.** Fitting fluorite
  with roughness free produced entries of +2.75 and −1.10 on *unrelated* pairs
  (`scale ~ axial_sl`, `axial_sl ~ background.c5`) alongside a legitimate
  ρ(a,b) = +1.000. That is not a Pearson matrix, so `pinv` on a singular JᵀJ is
  returning a non-PSD covariance somewhere. Pre-existing and not caused by
  roughness (WP-0407 fixed the *placement* of the Bérar-Lelann factor, not
  this), but 0501 will free parameters into the same ill-conditioned
  {zero, displacement, transparency} neighbourhood and should expect to meet
  it. Worth its own fix before either WP leans on the correlation guard.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.

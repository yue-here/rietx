# WP-0508 — Flat-plate absorption + a real-data capillary acceptance

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: 0501

## Scope

The two pieces WP-0501 deliberately fenced out:

1. **Flat-plate absorption** for the geometries where it is not degenerate with
   the phase scale — finite-thickness reflection and transmission.
2. **A real-data capillary acceptance** for the cylindrical correction that
   WP-0501 shipped, which currently has algorithm-level evidence only.

## Context pointers

### Why WP-0501 fenced flat plate, and what carries over

Reflection off a specimen thicker than the penetration depth is **exactly**
angle-independent — *International Tables* Vol. C Table 6.3.3.1(1a) gives

    A = 1/2µ                       (thick slab, planes parallel to the surface)

with no θ at all, so it is indistinguishable from the phase scale factor.
GSAS-II returns `1.0` for its `'Bragg'` case for the same reason. Implementing
*that* case is not a simplification worth having; it is a parameter with an
identically zero column.

The two cases that do carry a θ-signature, both from the same ITC table:

    (2) finite-thickness reflection, planes parallel to the surface
        A = {1 − exp(−2µt·cosec θ)} / 2µ

    (3a) transmission through a plate of thickness t, planes at π/2 to the
         surface (φ = 0)
        A = t·sec θ·exp(−µt·sec θ)

Both need a **sample thickness** and, for the general tilted case (3), a tilt
angle φ — neither of which `Geometry` carries. Note that (2) → 1/2µ as µt → ∞,
which is the continuity check any implementation should assert, and that (3) has
a maximum in µt: a transmission plate has an optimal thickness, which is a
genuinely useful thing to report.

### The capillary acceptance that is still owed

WP-0501's evidence is algorithm-level: the correction is pinned against the
published Rouse table and against a quadrature of ITC eq. (6.3.3.4), and the
Biso bias it removes is measured on synthetic data (0.489 Å² at µR = 1, λ =
1.54 Å, recovered to four decimals at 18.8σ). What it has **not** been shown
against is a real capillary pattern, because `tests/data/` contains none —
every real pattern in the repo is flat-plate Bragg-Brentano, and the 11-BM
synchrotron pattern is fitted with the geometry-agnostic `debye_scherrer`
preset, which carries no capillary metadata (no bore radius, no packing).

Sourcing one is the first task, and it is not trivial: the dataset needs a
**stated capillary diameter and specimen** for µR to be checkable, which most
published patterns omit. Options worth trying, in rough order of promise:

- an 11-BM mail-in dataset with its capillary size in the deposited metadata
  (11-BM's standard is a 0.8 mm OD Kapton or glass capillary);
- a synchrotron dataset published alongside a paper that quotes µR;
- a NIST/IUCr standard measured in capillary geometry.

The tolerance question needs deciding up front, per the CLAUDE.md policy: this
is a **cross-code consistency** check, not a certificate anchor, so tolerances
should be referenced to the spread between codes (GSAS-II, TOPAS and pxrdref
implement *different* cylinder fits — see below), never to σ.

### Inherited

From **WP-0501** (cylindrical absorption, landed 2026-07-27) — five things that
change the work here:

- **`model/absorption.py` exists** and is the module to extend, not to
  duplicate. It exports `cylinder_absorption`, `cylinder_absorption_and_dmur`,
  `equivalent_delta_biso` and `CYLINDER_MU_R_MAX = 1.0`. Its docstring carries
  the A-vs-A\* convention statement that a flat-plate function must also honour.
- **`CompiledModel._absorption` is the single seam** every intensity correction
  of this kind goes through, and its docstring records the hazard: A multiplies
  the same product that `_structural_intensity_grad` and `po_intensity_grad`
  rebuild by hand, so a *new* geometry's factor must be applied in all three
  places or those analytic columns are silently wrong while the FD columns stay
  right. The two guard tests in `tests/test_absorption.py` (with their
  `(1 − A).max() > 0.5` pre-asserts) are the pattern to copy.
- **`packed_mu_r` and `estimate_capillary_mu_r` already exist** and are
  shape-agnostic in everything but the final `× R`; a flat-plate µt estimator
  should reuse them rather than re-deriving bulk µ. `Geometry.packing_fraction`
  is already there and applies unchanged.
- **A refinable absorption parameter needs a real justification here.** For a
  cylinder the Rouse fit is *exactly* a constant times exp(c·sin²θ), so µR is an
  exactly singular direction alongside the scale and Biso, and WP-0501 made it a
  plain float rather than a `Parameter` for that reason. Check whether (2) and
  (3) are separable before assuming µt can be refined: (2) is not of that form,
  so it may genuinely carry information — but measure it (project ∂lnA/∂µt onto
  span{1, sin²θ} over the fit range, as `mu_r_identifiable_fraction` does)
  rather than assuming.
- **A digit-transposition trap, and the lesson from it.** WP-0501's coefficient
  b₂ was printed as "−0·0375" in the available scan when it is −0·3750. The
  error was invisible against a constant-θ slice of the published table and
  0.0821 wrong at µR = 1. Any absorption expression must be validated against
  something spanning **both** its arguments, and the ITC integral — not another
  code's transcription — is what makes that possible.

Also standing: `model/` is xp-routed (WP-0401), so bind `xp = get_backend()`
once per call and use no op outside `backend/api.py`'s vocabulary; and the
`sample_`-prefix heuristic at `params/vector.py:239` decides parameter gating by
name, which is a latent trap for any new geometry-gated parameter.

From **WP-0502** (surface roughness, landed 2026-07-27) — it shipped a
correction in **this WP's geometry** (flat-plate, Bragg-Brentano) and in the
same low-angle-intensity family, so most of its machinery and all of its traps
apply here directly:

- **Copy the block shape, don't re-derive it.** `Geometry.surface_roughness` is
  the worked example of an opt-in, geometry-gated, `kind`-discriminated
  correction: `params/vector.py:roughness_parameters()` derives dot-paths from
  `model_fields` and is shared by `_collect_instrument` **and**
  `apply_to_models`, so the forgotten-write-back bug is unrepresentable;
  `CompiledModel.roughness` is the compile-time frozen model choice; and
  `CompiledModel._roughness_factor()` is the single applier called from all
  three intensity assemblies (`phase_peaks`, `_structural_intensity_grad`,
  `po_intensity_grad`). A flat-plate absorption factor is the same shape.
- **The `sample_`-prefix trap above is real and 0502 hit it.**
  `instrument.geometry.surface_roughness.*` does not match it, so
  `scalar_chain_supported` needed the prefix added explicitly. The failure mode
  is a *correct* but whole-model-FD column — a slow test, not a failing one — so
  nothing catches it for you. Add the prefix and pin it with a test.
- **`optimize/statistics.block_projection_r2(jac, block, targets, nuisance)` is
  exported**, and the `nuisance` argument is the load-bearing part. Any
  *multiplicative* correction is trivially ~0.96 "scale-like": projected onto a
  block containing the phase scale, the measured R² moved only 0.961 → 0.990
  across data ranges where identifiability collapsed completely. Project the
  scale and background out first and read the **partial** R². Flat-plate
  absorption is the same kind of quantity.
- **Judge a correction at reflection positions, not on the fitted grid.** Found
  on real data: the IUCr round-robin patterns start at 5° 2θ but their first
  reflections are at 25–32°, and a grid-based fence reported a 27 % depression
  no modelled peak ever saw. `_roughness_regime_diagnostics` evaluates at
  `phase_peaks` positions for that reason.
- **No dataset in the repo can constrain a low-angle intensity correction.**
  Measured: qarr corundum/zincite/fluorite have 2–3 reflections below 40° (first
  at 25.6/31.8/28.3°), SRM 660c starts at 20.3° with LaB6's first line at 21.4°.
  0502's real-data outcome was therefore a *negative* result — the fences fire
  and nothing is measurable. **This WP's acceptance needs a dataset acquired for
  it**; plan that in rather than discovering it at the end. It is the highest-
  value single unblock for both WPs.
- **Watch for `|ρ| > 1` in the reported correlation matrix.** Fitting fluorite
  with roughness free produced +2.75 and −1.10 on *unrelated* pairs
  (`scale ~ axial_sl`, `axial_sl ~ background.c5`) alongside a legitimate
  ρ(a,b) = +1.000. `pinv` on a singular JᵀJ is returning a non-PSD covariance.
  Pre-existing and not caused by roughness (WP-0407 fixed the Bérar-Lelann
  *placement*, not this), but it undermines the correlation guard exactly where
  this WP will be working. Worth its own fix first.

## Non-goals

- Thick-specimen Bragg-Brentano reflection (exactly degenerate — see above).
- Re-opening the cylinder parameterisation. Lobanov & Alte da Veiga's fit
  (GSAS-II/TOPAS) reaches µR ≤ 3 where Rouse stops at 1, but its coefficients
  trace only to an unobtainable conference abstract. If µR > 1 specimens become
  important, the defensible route is a quadrature or a fit *this project*
  derives against ITC eq. (6.3.3.4), not a third-hand transcription.

## Tasks

- [ ] Expand this stub into a full WP before writing code
- [ ] Source a capillary dataset with a stated bore diameter and specimen

## Handover log

- **2026-07-27** — created by WP-0501, which fenced both pieces out with the
  rationale above rather than deferring them silently.

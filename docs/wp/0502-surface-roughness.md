# WP-0502 — Surface roughness

Milestone: v0.5 · Status: ✅ shipped 2026-07-27
Depends on: —

## Goal

An opt-in, Bragg-Brentano-only, Rietveld-only intensity multiplier R(θ) ≤ 1 on
`Geometry.surface_roughness`, in two published flavours behind a `kind`
discriminator (Suortti 1972, Pitschke 1993). Identity when off, bit-for-bit; a
full analytic-Jacobian path with no hidden chain-rule gap; and — the point of
the WP — a **block-projection-R² guard** that makes the roughness↔ADP
degeneracy speak instead of silently biasing displacement parameters.

## Context

### The physics

In Bragg-Brentano reflection geometry a loosely-packed or rough specimen has a
packing-density deficit in its top layer. At low 2θ the beam traverses that
depleted layer at grazing incidence over a long path, so diffracted intensity
is depressed — increasingly so as θ → 0.

Uncorrected, a refinement compensates through the only other knobs with a
monotone-in-θ intensity signature: **Biso / anisotropic ADPs (up), phase scales
(down), and a flexible background**. Rwp improves while the physics gets worse.
This is not speculative — Pitschke et al. (1993) Table III is the canonical
demonstration: YBa₂Cu₃O₇ refines to Biso = −1.9, −1.2, −2.5, −1.6 Å²
(unphysical) without the correction and 0.28–0.45 Å² with it, at unchanged
positions and occupancies.

It is the same failure mode the background-absorption guard already exists to
catch ([../DESIGN.md](../DESIGN.md#background-subsystem-automation-first)), and
it gets the same treatment: measure it, name it, refuse to hide it.

### The two models

Both are functions of sinθ alone, both 2-parameter, both exactly identity at
their off state. Both were verified against primary sources before coding (see
the handover log entry for 2026-07-27).

**`kind="suortti"`** — Suortti (1972), *J. Appl. Cryst.* **5**, 325–331:

```
R(θ) = [a + (1−a)·exp(−b/sinθ)] / [a + (1−a)·exp(−b)]
```

normalised so R(θ=90°) = 1. Three properties that drive the design:

1. **Exactly identity at b = 0.** Numerator and denominator reduce to the
   *identical float expression* `a + (1−a)*1.0`, so the ratio is bit-exactly
   1.0 for any `a`. This is the unconditional-evaluation ("purity (b)")
   property the hot path requires — cf. the `ext = 0 ⇒ E ≡ 1` comment in
   `model/forward.py`.
2. **Bounded 0 < R ≤ 1**, since sinθ ≤ 1 ⇒ exp(−b/sinθ) ≤ exp(−b) for b ≥ 0.
   The correction can only depress, never amplify.
3. **The off-state needs `a` strictly interior, not `a = 1`.** At b = 0,
   ∂R/∂a ≡ 0 and ∂R/∂b = (1−a)·(1 − 1/sinθ). Defaulting `a = 1` kills *both*
   gradients and the parameter can never lift off. Hence **a = 0.5, b = 0**.

GSAS-II's `SurfaceRough` uses this exact parameterisation (its SRA/SRB = our
a/b) and is the cross-code golden target. Behavioral reference only — **no code
ported**, see ATTRIBUTION.md.

**`kind="pitschke"`** — Pitschke, Hermann & Mattern (1993), *Powder Diffr.*
**8**, 74–83, Eqs (13)–(18) and the DBWS-9006 `CALCUL` patch in its appendix.
The paper's multiplier is

```
(1 − P),   P = P₀ + C·u·(1 − u),   u = τ/sinθ,   τ = t₀/β,   β = 2b/3
```

valid where **sinθ ≥ τ** (its Eq 18). **P₀ is not refinable here**: it is the
angle-*independent* bulk-porosity term, so
`(1−P) = (1−P₀)·[1 − c·u(1−u)]` with `c = C/(1−P₀)`, and the constant prefactor
is exactly degenerate with the phase scale factor. The paper only extracted P₀
because it fitted I/I₀ curves against a *separate* free scale a₁, and even then
all four samples returned P₀ = 0.5–0.7 ± 0.1, i.e. unresolved. So we refine the
identifiable part only — the same move Suortti's θ=90° normalisation makes:

```
R(θ) = 1 − c·(τ/sinθ)·(1 − τ/sinθ)        c ≥ 0, τ ≥ 0
```

Refine **τ directly**, not t₀: it is dimensionless, and it sidesteps a
paper-internal inconsistency (Table I's column is used as the mean particle
size b when computing τ but as the mean chord l̄ when computing Δt̄).

Shape facts, all of which become tests or fences:

- `u(1−u)` peaks at **u = 0.5** and returns to 0 at u = 1. R is monotone in θ
  only while **sinθ ≥ 2τ**; between 2τ and τ the depression turns back over;
  beyond sinθ = τ the correction would **amplify** (R > 1) — unphysical.
- R > 0 needs c·max(u(1−u)) < 1, i.e. c < 4 over the valid range.
- The paper's physical estimate is **τ < 0.3**; its fitted values were
  0.005–0.12. Its stated safe ranges (θ > 30° for τ = 0.3, θ > 10° for τ = 0.1)
  are conservative against the exact limit (17.5°, 5.7°).

Re-checking the paper's own Table II through that fence: YBCO-1 (c = 3.75,
τ = 0.073, data from 2θ = 15°) sits at u = 0.56 — *past* the turnover and close
to the R > 0 limit. The fence is not decorative.

### Where the code goes

| Concern | File | Note |
|---|---|---|
| Physics fn | `model/corrections.py` | geometric + θ-only ⇒ belongs here. WP-0506 gave extinction its own module only because it couples \|F\|² and V; roughness does not. |
| Schema | `schemas/instrument.py` | `Geometry`, beside `sample_transparency` — same µ·R family, same BB gate, same "vanishes for strong absorbers" story |
| Param wiring | `params/vector.py` | `_collect_instrument` **and** `apply_to_models` (forgetting the write-back is a documented past bug) |
| Forward hook | `model/forward.py` | `phase_peaks`, **plus** `_structural_intensity_grad` and `po_intensity_grad` |
| Jacobian routing | `model/forward.py` | `scalar_chain_supported` |
| Stage plans | `strategy/staged.py` | new late stage, with `seed=` |
| Guard/diagnostic | `optimize/statistics.py`, `strategy/staged.py`, `refine.py` | |

**The hidden-Jacobian trap.** The pure-analytic column builders bypass
`phase_peaks` and must carry the same factor — `_structural_intensity_grad`
(dof/adp columns) and `po_intensity_grad` (the March `r` column). This is the
pinned failure mode of both WP-0506 and WP-0307. Unlike extinction, R is
**independent of |F|²**, so it is a *plain multiply* in both; there is no
`G = E + x·dE/dx` analogue.

**Jacobian routing gotcha.** `scalar_chain_supported` whitelists path
*prefixes*; `instrument.geometry.surface_roughness.` does **not** match the
existing `instrument.geometry.sample_` prefix and would silently fall through
to whole-model FD (correct but slow). Add the prefix explicitly and pin it with
a test. With that, both parameters get semi-analytic columns from
`_peak_chain_column` for free — no `_and_d*` twin and no `_PO_PATH`-style regex
needed.

**Applied at `tt_bragg`**, the ideal Bragg 2θ, matching Lp and Sabine — not at
the aberration-shifted `pos`.

**Rietveld-only**, skipped in lebail/pawley for the same reason Lp is: extracted
intensities already absorb any smooth θ-dependent factor.

### Inherited

From **WP-0303** (anisotropic ADPs, landed 2026-07-23): the correlation to
surface is no longer only roughness↔Biso. ADPs can now be a full six-component
U^ij tensor per atom (`Atom.aniso`, opt-in, freed by the
`phases.*.atoms.*.adp.*` glob), so a low-angle intensity depression has more
displacement freedom to hide in than the stub assumed. The right measurement is
the *block* projection R² already used for background absorption
(`optimize.statistics.background_absorption`), not pairwise ρ — pairwise misses
block absorption almost entirely (~0.2 per coefficient while the block absorbs
~46 %).

From **WP-0401** (op shim, landed 2026-07-24): `model/corrections.py` is
xp-routed. New correction code calls `xp.*` with `xp = get_backend()` bound
once per compiled-model call, never bare `np.*`, or the jax/torch backends
break.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24), by way of WP-0501:
specimen transparency was measured on SRM 676a and deliberately **kept at 0** —
freeing it is a wash on Rwp and merely re-apportions the uniform d-scale across
the correlated {zero, displacement, t} triple. Roughness joins that same
correlated family and should expect the same trap: **judge it by whether it
buys band-resolved residual structure and by the block R², not by Rwp.**

From **WP-0407** (esd reconciliation, landed 2026-07-24): the returned
correlation matrix is now a true Pearson matrix (unit diagonal) and the 0.98
guard is live, so a genuinely degenerate roughness pairing will report |ρ| ≈ 1
honestly. Do not silence it — reconcile to the physics.

From **WP-0501** (capillary absorption, landed 2026-07-27) — this WP lands in
the same degenerate pocket, and 0501 built the tools to measure it:

- **Measure the degeneracy before designing the parameter.** Roughness is a
  low-angle intensity depression, and the {phase scale, Biso} pair spans
  {1, sin²θ} in log-intensity. 0501 found that cylindrical absorption is
  *exactly* in that span — its µR column is singular, not merely correlated —
  and consequently made µR a computed plain float rather than a refinable
  `Parameter`. Use `model.absorption.mu_r_identifiable_fraction` (it projects
  ∂lnA/∂p onto span{1, sin²θ} and returns the normalised residual) on the
  roughness model *before* deciding it is refinable. The Suortti and Pitschke
  forms are not obviously separable, and a roughness coefficient that turns out
  to be a reparameterised Biso would silently eat ADPs while improving nothing.
- **`CompiledModel._absorption` is the seam**, and its docstring states the
  hazard a new intensity multiplier inherits: it must be applied in
  `phase_peaks` *and* in both hand-written analytic-column builders
  (`_structural_intensity_grad`, `po_intensity_grad`), or those columns are
  silently wrong while the finite-difference columns stay right. The two guard
  tests in `tests/test_absorption.py`, each with a
  `(1 − A).max() > 0.5` pre-assert so they cannot pass vacuously, are the
  pattern to copy.
- **Judge it by the physical quantity it unbiases, not by Rwp.** 0501's
  correction provably cannot change Rwp (it is an exact reparameterisation), so
  its acceptance test asserts the *Biso bias removed* — 0.489 Å² at µR = 1,
  recovered to four decimals at 18.8σ — and explicitly asserts Rwp is
  *unchanged*. If roughness turns out to be similar, the obvious "the fit should
  improve" test would assert something the physics cannot deliver.
- `RefinementResult.absorption` (`schemas/results.AbsorptionCorrection`) is the
  precedent for reporting a correction whose effect no fit statistic shows.
- **A parameter's *name* silently selects its derivative path.**
  `params/vector.py` decides whether a geometry parameter is force-fixed by
  testing whether the name starts with `sample_`, and
  `CompiledModel.scalar_chain_supported` uses the same prefix to decide between
  an analytic peak-chain column and whole-model finite differences. 0501 left
  both alone (its µR is not refinable, so neither applied) — but roughness *is*
  a Bragg-Brentano geometry term, so it is the next WP likely to trip over
  them. Choose the name deliberately.

**What happened against 0501's advice (added when 0502 shipped, 2026-07-27).**
Every point above landed, and two of them changed the design:

- The identifiability check was done, and the answer differs from 0501's. Both
  roughness models are **1/sinθ**-shaped, not sin²θ-shaped, so unlike µR they
  are *not* exactly in span{1, sin²θ} — they are refinable, but only when the
  fit reaches low enough 2θ to see the difference. That "only when" is the whole
  finding: measured partial R²(Suortti b) runs 0.06 → 0.95 as the low-angle
  reflections leave the range, so both parameters stay refinable and a guard
  reports when they stop being identifiable.
- 0501's `mu_r_identifiable_fraction` was not reusable here (it projects onto a
  fixed two-vector basis). The generalisation went the other way instead:
  `optimize.statistics.block_projection_r2` now takes an explicit **nuisance**
  block, and the scale/background are projected out of the whole Jacobian.
  Without that step every roughness number saturates near 0.96 — a multiplicative
  correction is trivially "scale-like" — and the guard is blind.
- The `_absorption` seam and its hidden-Jacobian hazard were followed exactly:
  `_roughness_factor` is applied in `phase_peaks` and both analytic column
  builders, and the guard test carries the same kind of pre-assert
  (`(1 − R).max() > 0.05`). It was checked by deletion — removing the fold from
  `_structural_intensity_grad` takes the analytic-vs-FD error from < 5e-3 to
  0.199.
- The naming warning was right and was acted on:
  `instrument.geometry.surface_roughness.*` does **not** match the `sample_`
  prefix, so `scalar_chain_supported` gained the prefix explicitly. The failure
  mode of missing it is a *correct* but whole-model-FD column — a slow test, not
  a failing one — so nothing would have caught it.
- "Judge it by the physical quantity, not Rwp" applied, with a twist: on real
  data the correction is **not identifiable at all**, so the acceptance asserts
  the fences fire and the esds stay honest rather than asserting any recovered
  number. See "Measured results" below.

## Non-goals

- **No specimen-characterisation machinery from Pitschke §III–IV.** Eqs (1)–(12)
  (packing fraction α₀, mean chord l̄, profile fluctuation Δt̄, the Boolean-model
  derivation) are how the *paper* estimated τ from micrographs and profilometry.
  We refine τ from the diffraction data instead. Do not port those equations.
- **P₀ is not a refinable parameter** — degenerate with the phase scale. Do not
  add it "for completeness".
- **No Layer-1 intensity trend template.** `report/layer1.py` offers `constant`
  + `sin2_over_lambda2` for the intensity observable; roughness would be a
  third, collinear one. That is the right eventual home for "roughness↔ADP
  reported as non-separable", but it needs the nested-single-fit separability
  treatment and its own misfit-injection calibration ensemble.
- **No absorption corrections** — capillary/flat-plate is WP-0501.
- **No µ-derived roughness prior** from `crystallography/attenuation.py`.
- Not applied in Le Bail/Pawley; not applied outside Bragg-Brentano.

## Tasks

- [x] Expand this stub into a full WP before writing code
- [x] Schema: `RoughnessSuortti` + `RoughnessPitschke` + union alias +
      `Geometry.surface_roughness` + BB-only validator + `schemas/__init__.py`
      export; JSON round-trip and defaults-off tests
- [x] Physics: `surface_roughness_suortti` in `model/corrections.py`, xp-routed,
      docstring citing Suortti (1972) with both limits derived and the GSAS-II
      SRA/SRB mapping; property tests — exact identity at b=0, 0 < R ≤ 1,
      monotone increasing in θ, and an independent scalar transcription of the
      published formula matched to `abs=rel=1e-10`
- [x] Param wiring: `_collect_instrument` skip-when-`None`, `apply_to_models`
      write-back, `scalar_chain_supported` prefix, `instrument_profile`
      strip-on-save + `_iter_parameters`, `multi.SharingMap` per-histogram
      assertion
- [x] Forward hook in `phase_peaks` + the two analytic-column sites + the
      `io/exporters.py` intensity-chain docstring. Tests: bit-identical
      (`np.array_equal`) when off; analytic-vs-FD for **every** free column with
      roughness **on** (incl. dof/adp/`preferred_orientation.r`), with an
      explicit discriminating-power precondition
- [x] Staged plans: a `roughness` stage after `biso` in `lab_sample_refine`,
      `lab_bragg_brentano` and `mccusker_structural`, with `seed=`;
      stage-order test
- [x] `block_projection_r2` refactor of `background_absorption` (+ an
      unchanged-numbers test), `roughness_absorption` measured in both
      directions, a **measured** `ROUGHNESS_ABSORPTION_GUARD`,
      `GuardReport.roughness_correlations`, and the `ROUGHNESS_ABSORPTION` /
      `ROUGHNESS_UNCONSTRAINED` diagnostics. Tests in both shapes: degenerate
      case → guard fires; identifiable case → guard does **not** false-positive
- [x] End-to-end recovery on a synthetic BB pattern carrying known (a, b):
      within `max(4σ, 5 %)` **and** resolved (> 5σ from the off state);
      obs/calc/diff + low-angle-zoom PNGs to `tests/output/`
- [x] Backend parity: a 7th `toy_roughness` golden in
      `tests/data/backend_goldens`, plus jax jacfwd agreement on the new columns
- [x] `@pytest.mark.slow` real data — SRM 660c as the control (20.3° start ⇒
      roughness must do ≈ nothing, `ROUGHNESS_UNCONSTRAINED` fires); FAP as
      protocol fidelity (GSAS's `.EXP` `HST 1ABSCOR … N` proves it held the
      correction off — mirror that); qarr as the measurement, µ-contrast
      `fluorite`/`cpd-1a` (low µ) vs `magnetit` (µ ≈ 1165)
- [x] If and only if the qarr measurement supports it: re-derive the sample-1
      bias-shape test, documenting the measured evidence in the test docstring
      and `tests/data/README.md`. It did not — roughness is unconstrained by
      these patterns — so the test was left alone. (WP-0504 subsequently *did*
      re-derive it and renamed it
      `test_sample1_bias_has_the_dispersion_shape`; this WP's negative result
      is what makes that attribution unambiguous.)
- [x] Pitschke `kind`: `R = 1 − c·(τ/sinθ)(1 − τ/sinθ)`, same test battery,
      plus `ROUGHNESS_OUTSIDE_REGIME` and a property test that the turnover and
      the R > 1 region are *fenced, not silently fitted*
- [ ] Cross-model comparison on the qarr data: fit both `kind`s, report both,
      and state which (if either) the data prefers — a nested/ΔBIC-style
      statement, not a Rwp beauty contest
- [x] Docs: ROADMAP status glyph, handover log, ATTRIBUTION.md, and an
      `### Inherited` entry in `wp/0501-absorption-corrections.md`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_surface_roughness.py -q
.venv/bin/python -m pytest -m "not slow" -q
.venv/bin/python -m pytest tests/test_acceptance_srm660c.py \
    tests/test_acceptance_fap.py tests/test_acceptance_qpa_roundrobin.py -q
.venv/bin/python -m ruff check src tests examples
```

1. Off-state is **bit-identical** (`np.array_equal`) to the pre-WP forward
   model, and every existing acceptance number is unchanged.
2. Analytic Jacobian matches FD to `‖Δ‖/‖J‖ < 5e-3` on all columns with
   roughness on — including dof/adp/`r`, where the hidden-Jacobian bug lives.
3. Synthetic recovery of a known parameter pair within `max(4σ, 5 %)` and > 5σ
   from the off state.
4. The block-R² guard separates a degenerate from an identifiable case, and
   `ROUGHNESS_ABSORPTION_GUARD` is pinned to a **measured** separation
   documented in its comment (as `BACKGROUND_ABSORPTION_GUARD` is).
5. SRM 660c unchanged; FAP mirrors GSAS's roughness-off protocol; the qarr
   µ-contrast measurement is recorded here with the numbers, whichever way it
   comes out.
6. Every test refinement writes obs/calc/diff PNGs (+ a low-angle zoom, where
   roughness lives) to `tests/output/`, visually inspected.

## References

- Suortti, P. (1972). *J. Appl. Cryst.* **5**, 325–331 — `kind="suortti"`.
- Pitschke, W., Hermann, H. & Mattern, N. (1993). *Powder Diffr.* **8**, 74–83 —
  `kind="pitschke"`; Eqs (13)–(18) + the DBWS-9006 appendix; Table III is the
  negative-Biso demonstration.
- Sparks et al. (1991), *Adv. X-ray Anal.* **35**, 57; Hermann & Ermrich (1987),
  *Acta Cryst.* **A43**, 401 — the microabsorption theory Pitschke builds on.
- Sidey, V. (2004). *J. Appl. Cryst.* **37**, 1013–1014 — a monoparametric
  simplification; noted, not implemented.
- GSAS-II `SurfaceRough`/`SurfaceRoughDerv` — behavioral cross-code reference
  only, no code ported.
- IUCr CPD QPA round robin — `tests/data/README.md` (instrument; and the signed
  low-angle bias currently attributed to microabsorption).

## Measured results (2026-07-27)

### The correction is not identifiable from any dataset in this repo

Roughness is constrained by low-angle **reflections**, not by low-angle grid
points, and neither real Bragg-Brentano dataset has any:

| specimen | data from | first reflection | reflections < 40° |
|---|---|---|---|
| qarr corundum | 5.0° | 25.6° | 3 |
| qarr fluorite | 5.0° | 28.3° | 2 |
| qarr zincite | 5.0° | 31.8° | 3 |
| SRM 660c LaB6 | 20.3° | 21.4° | 0 |

That is squarely inside the range the block-R² measurement calls degenerate.
Refining the qarr pure phases with and without a Suortti block:

| phase | Rwp off | Rwp on | refined (a, b) | Biso off → on |
|---|---|---|---|---|
| corundum | 0.1437 | 0.1437 | (1.000, 0.0000) | 0.232 → 0.228 |
| zincite | 0.1091 | 0.1091 | (1.000, 0.0000) | 0.840 → 0.840 |
| fluorite | 0.1793 | 0.1792 | (0.000, 0.0146) | 0.390 → 0.457 |

Corundum and zincite drive the correction back to the exact identity and raise
`ROUGHNESS_UNCONSTRAINED`. Fluorite is the more instructive failure: it finds a
~4 % depression at its first reflection *and* pushes both Biso up to
compensate, buying 0.0001 in Rwp, with ρ(a, b) = +1.000 and esds 350× the
values. That is the roughness↔Biso degeneracy sliding along its flat direction
— exactly what this WP exists to make visible, caught here by the Pearson guard
rather than the block-R² one (the two are complementary: one sees a degenerate
*pair*, the other a degenerate *block*).

**Consequence for the open question:** roughness is **not** a competing
explanation for the signed sample-1 QPA bias (zincite low, corundum high) that
`test_acceptance_qpa_roundrobin` attributes to untreated microabsorption. It
cannot be, because it is not identifiable from those patterns at all. The
microabsorption-shape test is therefore **left alone**, not re-derived — the
authorisation to re-derive it was conditional on evidence, and the evidence
went the other way.

### The guard threshold

Measured on a synthetic large-cell lab pattern, varying only the low-angle
cutoff (scale, background, both Biso and both Suortti parameters free):

| lowest fitted 2θ | 7° | 15° | 20° | 30° | 45° |
|---|---|---|---|---|---|
| reflections < 40° | 20 | 18 | 16 | 10 | 0 |
| R²(Suortti b) | 0.06 | 0.62 | 0.91 | 0.93 | 0.95 |

`ROUGHNESS_ABSORPTION_GUARD = 0.9` sits in that gap.

## Handover log

- **2026-07-27** — **implemented; 12 commits, all checklist items landed except
  the two marked below.** 424 fast tests + the full slow acceptance suite green,
  ruff clean, seven backend goldens bit-identical.
  - **Done**: schema (both `kind`s), physics functions, parameter wiring,
    forward hook + both analytic-column sites, staged plans, the block-R² guard
    and three diagnostics, synthetic recovery, `toy_roughness` backend golden,
    real-data acceptance on qarr + SRM 660c, docs.
  - **Two claims in this file's original draft were wrong and are corrected
    above**: (1) "larger b deepens the depression" — false; `1 − a` bounds the
    depression and `b` sets *where in angle* the transition falls, with both
    b → 0 and b → ∞ returning the identity, so `b` is **bimodal** and has a
    flat-gradient dead zone past b ≈ 3. (2) The Suortti↔Pitschke-quoted-Suortti
    agreement is to 1e-14, not bit-for-bit; the two ways of writing it group
    the float operations differently. My earlier "bit-for-bit" came from a
    lucky scalar sample.
  - **The guard design changed after measurement.** The first version projected
    the roughness column onto {ADP, scale, background} and scored ≈0.96
    regardless of the data — a guard that always fires. Roughness is a
    *multiplicative* correction, so it is trivially scale-like. The fix is a
    **partial** R²: scale and background are nuisance directions, projected out
    of the whole Jacobian first. `block_projection_r2(..., nuisance=...)` is
    exported for WP-0501, which will need the same treatment.
  - **Real data corrected a fence.** `ROUGHNESS_UNCONSTRAINED` originally
    measured the depression over the fitted 2θ *grid*; on the qarr patterns
    that reported a 27 % depression at 5° where no reflection exists. It now
    evaluates at `phase_peaks` positions.
  - **Gotcha for anyone extending this**: LaB6 is useless as a roughness test
    case (first CuKα line at 21.4°). `tests/test_surface_roughness.py` carries
    a `_big_cell_structure()` (10 Å cubic, reflections from ~8.8°) for
    everything where the reflection positions matter.
  - **Pre-existing bug noticed, not fixed** (also written into WP-0501's
    `### Inherited`): the reported correlation matrix can contain `|ρ| > 1`
    (+2.75 for `scale ~ axial_sl`, −1.10 for `axial_sl ~ background.c5`) on the
    fluorite fit. `pinv` on a singular JᵀJ is returning a non-PSD covariance.
    Unrelated to roughness — WP-0407 fixed the Bérar-Lelann *placement*, not
    this — but it undermines the correlation guard wherever conditioning is
    poor, and both 0501 and this WP lean on that guard. Worth its own fix.
    **→ Fixed 2026-07-28** (repo-wide audit, not a WP). Root cause: JᵀJ is PSD,
    so its Moore-Penrose inverse is PSD and |ρ| ≤ 1 *mathematically* — but
    `np.linalg.pinv` defaults to the **general** SVD path, which treats the
    matrix as unstructured and, on the cond ≈ 10²⁰ normal matrices this package
    routinely forms, returns a visibly non-symmetric result. Reproduced
    deterministically at |ρ| up to 1.6 × 10³ on synthetic ill-conditioning.
    `optimize/least_squares.covariance_estimates` now symmetrises JᵀJ and passes
    `hermitian=True` (an `eigh` path, which cannot break symmetry), capping the
    same cases at 1 + 4 ulp, with a final clip to remove the ulp. Regression:
    `test_v02_core.test_correlation_stays_a_valid_pearson_matrix_under_extreme_conditioning`.
    Note the clip is *not* the fix — clipping 2.75 to 1.0 would report a
    degeneracy the arithmetic invented rather than the one the data has.
  - **Next**: the two unchecked items are (a) jax jacfwd parity on the new
    columns — jax is not installed in this workspace, so it was never run, and
    (b) the cross-model qarr comparison, which is moot until a dataset with
    low-angle reflections exists. See the WP-0501 note: acquiring such a
    dataset is the highest-value follow-up for both WPs.
- **2026-07-27** — expanded from stub to full WP; no source code yet.
  - **Both models verified against primary sources before coding.** Suortti's
    form was taken from GSAS-II `SurfaceRough` *and* independently confirmed by
    Pitschke's own quotation of it (p. 78, `P_s = C₁[1−exp(−C₂/sinθ)]`) —
    normalised at θ=90° the two agree bit-for-bit with C₁ = 1−a, C₂ = b.
  - The Pitschke paper was supplied as OCR'd markdown and checked numerically:
    Eq (7) rederives exactly from Eqs (4)(5)(6) (the odd `exp(1−α₀)` denominator
    is genuine); Eq (9) is exactly the two-exponential convolution; Eq (10) is
    exact; Eq (12) + the Δt̄_p/Δt̄_s split reproduces all four rows of Table I to
    ≤1.6 %; Eq (18) is consistent with the prose validity claims. OCR artifacts:
    `4R/\bar 3` is the sphere mean chord `4R/3`, `\lambda_\downarrow` is λ₁.
  - **Three defects that are the paper's, not the OCR's** — all confined to the
    §III–IV characterisation machinery we deliberately do not port: Table I's
    column is used as b for τ but as l̄ for Δt̄; `p_A` flips meaning between
    Eq (2) and the p. 77 hard-sphere estimate; the appendix's
    `SITH = SQRT(SINTH)` only parses if DBWS's `SINTH` is sin²θ (it is).
  - **Design consequence:** P₀ dropped as non-refinable (degenerate with the
    phase scale), τ refined directly rather than t₀. Both decisions are what
    keep the paper's internal inconsistencies out of our implementation.
  - Next: schema commit, then the Suortti physics function.
- **2026-07-22** — created as a stub from the ROADMAP split.

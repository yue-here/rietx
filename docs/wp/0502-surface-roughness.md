# WP-0502 — Surface roughness

Milestone: v0.5 · Status: 🔶 in progress
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
- [ ] Schema: `RoughnessSuortti` + `RoughnessPitschke` + union alias +
      `Geometry.surface_roughness` + BB-only validator + `schemas/__init__.py`
      export; JSON round-trip and defaults-off tests
- [ ] Physics: `surface_roughness_suortti` in `model/corrections.py`, xp-routed,
      docstring citing Suortti (1972) with both limits derived and the GSAS-II
      SRA/SRB mapping; property tests — exact identity at b=0, 0 < R ≤ 1,
      monotone increasing in θ, and an independent scalar transcription of the
      published formula matched to `abs=rel=1e-10`
- [ ] Param wiring: `_collect_instrument` skip-when-`None`, `apply_to_models`
      write-back, `scalar_chain_supported` prefix, `instrument_profile`
      strip-on-save + `_iter_parameters`, `multi.SharingMap` per-histogram
      assertion
- [ ] Forward hook in `phase_peaks` + the two analytic-column sites + the
      `io/exporters.py` intensity-chain docstring. Tests: bit-identical
      (`np.array_equal`) when off; analytic-vs-FD for **every** free column with
      roughness **on** (incl. dof/adp/`preferred_orientation.r`), with an
      explicit discriminating-power precondition
- [ ] Staged plans: a `roughness` stage after `biso` in `lab_sample_refine`,
      `lab_bragg_brentano` and `mccusker_structural`, with `seed=`;
      stage-order test
- [ ] `block_projection_r2` refactor of `background_absorption` (+ an
      unchanged-numbers test), `roughness_absorption` measured in both
      directions, a **measured** `ROUGHNESS_ABSORPTION_GUARD`,
      `GuardReport.roughness_correlations`, and the `ROUGHNESS_ABSORPTION` /
      `ROUGHNESS_UNCONSTRAINED` diagnostics. Tests in both shapes: degenerate
      case → guard fires; identifiable case → guard does **not** false-positive
- [ ] End-to-end recovery on a synthetic BB pattern carrying known (a, b):
      within `max(4σ, 5 %)` **and** resolved (> 5σ from the off state);
      obs/calc/diff + low-angle-zoom PNGs to `tests/output/`
- [ ] Backend parity: a 7th `toy_roughness` golden in
      `tests/data/backend_goldens`, plus jax jacfwd agreement on the new columns
- [ ] `@pytest.mark.slow` real data — SRM 660c as the control (20.3° start ⇒
      roughness must do ≈ nothing, `ROUGHNESS_UNCONSTRAINED` fires); FAP as
      protocol fidelity (GSAS's `.EXP` `HST 1ABSCOR … N` proves it held the
      correction off — mirror that); qarr as the measurement, µ-contrast
      `fluorite`/`cpd-1a` (low µ) vs `magnetit` (µ ≈ 1165)
- [ ] If and only if the qarr measurement supports it: re-derive
      `test_sample1_bias_has_the_microabsorption_shape`, documenting the
      measured evidence in the test docstring and `tests/data/README.md`
- [ ] Pitschke `kind`: `R = 1 − c·(τ/sinθ)(1 − τ/sinθ)`, same test battery,
      plus `ROUGHNESS_OUTSIDE_REGIME` and a property test that the turnover and
      the R > 1 region are *fenced, not silently fitted*
- [ ] Cross-model comparison on the qarr data: fit both `kind`s, report both,
      and state which (if either) the data prefers — a nested/ΔBIC-style
      statement, not a Rwp beauty contest
- [ ] Docs: ROADMAP status glyph, handover log, ATTRIBUTION.md, and an
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

## Handover log

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

# WP-0506 — Secondary extinction (Sabine model)

Milestone: v0.5 · Status: 🚧 in progress (2026-07-23)
Depends on: —

## Goal

A refinable secondary-extinction correction as a per-reflection,
per-emission-line intensity multiplier, the one classic Rietveld intensity
correction that was in neither the code nor the roadmap. It attenuates the
strong low-angle reflections of a well-crystallised sample (extinction is
absent from the profile shape and lives entirely in the integrated
intensity), and it is the cross-code protocol target for a GSAS-II
consistency check.

## Context

This landed out of band, from a cross-code review (GSAS-II, CrysFML, cryspy,
MAUD, Profex/BGMN, powerxrd) that asked what *implemented physics* was missing
rather than what the roadmap already planned. Secondary extinction was the one
gap with no plan; GSAS-II ships it, so its parameterization is adopted verbatim
as the golden target (behavioral reference only — its license bars a code port;
see [ATTRIBUTION.md](../../ATTRIBUTION.md)).

### Physics

Per reflection, per emission line, from the calculated |F|² (no multiplicity),
wavelength λ, cell volume V, Bragg angle θ (2θ), and a per-phase coefficient
`ext`:

    Xpol  = 0.079411·(1 + cos²2θ)/2                # X-ray prefactor (GSAS-II constant)
    x     = ext · |F|² · (λ/V)² · Xpol             # dimensionless extinction variable
    E_B   = 1/√(1+x)                               # Bragg (backscatter) component
    E_L   = 1 + Σ_{i=1..6} c_i·x^i    (0<x≤1)      # Laue series
          = √(2/(πx))·(1 − 1/(8x))    (x>1)        # Laue asymptote;  = 1 for x≤0
    E_hkl = E_B·sin²θ + E_L·cos²θ

with the Sabine/GSAS-II series coefficients
`c = [−0.5, 0.25, −0.10416667, 0.036458333, −0.0109375, 2.8497409e−3]`.

**Convention documented by physics, not letter:** the *Bragg* (backscattering)
component blends with **sin²θ** and the *Laue* (forward) component with cos²θ —
the reverse of a naive reading. This is Sabine's result and matches GSAS-II
`GetPwdrExt`; the docstring states it in those terms.

`ext = 0 ⇒ x = 0 ⇒ E_hkl = sin²θ + cos²θ = 1` **exactly** — the identity when
off, so reading a structure or leaving the stage out changes nothing.

References: Sabine (1985) *Aust. J. Phys.* 38, 507; Sabine (1988) *Acta Cryst.*
A44, 368; Sabine, Von Dreele & Jørgensen (1988) *Acta Cryst.* A44, 374. GSAS-II
`GetPwdrExt`/`GetPwdrExtDerv` are the behavioral golden only.

### Where it goes

Extinction is a *physical* (|F|²- and V-coupled) correction, not a geometric
one, so it gets its own module
[`model/extinction.py`](../../src/pxrdref/model/extinction.py) (one-physics-per-
module, like `profiles/*.py`), not `corrections.py`. Two functions:
`sabine_extinction(...) → E` (forward) and `sabine_extinction_and_dx(...) →
(E, dE/dx, x)` (Jacobian support). It is evaluated **inside the emission-line
loop** of `CompiledModel.phase_peaks` (x ∝ λ² and E depends on θ), beside
`lorentz_polarization`, and only in `mode == "rietveld"` (Le Bail intensities
are extracted, not modelled). V comes from
`crystallography.lattice.cell_volume`, recomputed each call (it moves with the
cell).

### Jacobian

Extinction does **not** break `scalar_chain_supported`: it is a pure
intensity-scalar effect on a `phases.*` path, so the `extinction`, `scale`,
`occ`, `biso` and `cell` columns all ride the existing
`_peak_chain_column` FD-of-`phase_peaks` machinery for free once E is folded
into `phase_peaks`. The **only** columns that need new code are the
pure-analytic coordinate (`dof`) and ADP (`adp`) columns in
`_structural_intensity_grad`, which bypass `phase_peaks`: their ∂|F|²/∂p is
multiplied by the per-line chain factor

    G = E + x·(dE/dx)          (because x ∝ |F|²)

Keeping these analytic preserves the v0.2 analytic-Jacobian coverage; routing
them to FD would silently regress it (the "hidden-Jacobian" bug — test 4 is the
guard).

## Non-goals

- Primary extinction and the single-crystal `SCExtinction` model (GSAS-II's
  other branch) — the powder secondary correction is the scope here.
- Extinction *type* selection (I vs II, Gaussian vs Lorentzian mosaic): the
  Sabine powder form already blends the Bragg/Laue limits, so a single `ext`
  coefficient is the intended surface.

## Tasks

- [x] **Schema** — `Phase.extinction: Parameter` (sibling of `scale`), default
      `value=0.0, vary=False, min=0.0, transform="softplus"`, documented by
      physics; JSON round-trip test.
- [x] **Physics module** — `model/extinction.py` (`sabine_extinction`,
      `sabine_extinction_and_dx`) + unit tests: identity at 0, monotonicity
      (E ≤ 1, ∂E/∂ext ≤ 0), angular limits, and a GSAS-II golden covering both
      Laue branches and the Xpol prefactor to ~1e-10.
- [x] **Forward hook** — fold `sabine_extinction(...)` into the Rietveld
      intensity in `phase_peaks` inside the line loop (guard `mode=="rietveld"`,
      Le Bail untouched); `V=cell_volume(*cell)` each call; bit-identical
      regression when `ext=0`.
- [x] **Analytic Jacobian chain** — add the `G = E + x·dE/dx` factor to the
      `dof`/`adp` columns in `_structural_intensity_grad`; FD-agreement test
      with extinction **on** for `phases.*.extinction`, `dof`, and `adp`
      columns (a negative control confirms the columns miss FD by ~6-8%
      without G).
- [x] **Param wiring** — `params/vector.py` `_collect` (next to `scale`) and
      `apply_to_models`; confirm `_STRUCTURAL_PATH` does not match
      `phases.N.extinction`; `set_vary(["phases.*.extinction"])` round-trip.
- [x] **Staged-plan slot** — `Stage("extinction", ["phases.*.extinction"],
      seed=1e-3)` appended to `mccusker_structural` *after* `biso`; new
      `Stage.seed` field + `ParameterTable.seed_softplus` lift `ext` off the
      softplus zero when the stage activates (carried through `StageSpec`);
      Biso→extinction ordering documented. Existing `mccusker_structural`
      tests (coordinates, aniso ADP recovery) still pass with the stage in.
- [ ] **Recovery + does-no-harm tests** — synthetic extinction injection
      recovered within esds on a detectable case; does-no-harm `@slow` on NAC
      and SRM 660c (extinction refines ≈ 0, Rwp not degraded); correlation
      guard surfaces ext↔Biso/scale; obs/calc/diff PNGs to `tests/output/`.
- [ ] **Docs** — this file's ticks + handover; ROADMAP glyph sync.

## Risks

- **ext ↔ Biso ↔ scale correlation** — all three attenuate high-Q intensity in
  overlapping ways. Mitigation: stage Biso *before* extinction, keep the
  correlation and background-absorption guards live, and watch for a
  QPA-fraction bias later at WP-0304.
- **Hidden-Jacobian bug** — if the `G` factor is forgotten, the `dof`/`adp`
  columns silently disagree with FD only when `ext≠0`. Test 4 pins it.
- **sin²θ/cos²θ inversion** — the Bragg-with-sin²θ convention is easy to flip;
  the angular-limit unit test and the GSAS-II golden both catch it.
- **Softplus lift-off** — `ext=0` sits at the softplus floor where the internal
  gradient is ~0; the stage seed is what makes it refinable.
- **Series/asymptote discontinuity at x=1** — GSAS-II's six-term x≤1 series
  and two-term x>1 asymptote do *not* join continuously there (E_L jumps
  ≈ 0.674 → 0.698, a ~2% step). Adopted verbatim rather than smoothed (a
  smoothing would break the cross-code golden). Harmless for real data, where
  x ≪ 1 keeps every reflection on the smooth series branch; a reflection would
  have to lose ~40% of its intensity to extinction to reach x > 1. Pinned by
  `test_series_and_asymptote_jump_at_x_equals_one` so any future change is
  deliberate.
- **Unpolarized Xpol** — GSAS-II's extinction prefactor is the unpolarized
  `(1+cos²2θ)/2` independent of the beam-polarization K; adopted verbatim for
  the golden, flagged for a future polarized-synchrotron refinement.

## Acceptance

`ext = 0` reproduces the uncorrected pattern to machine precision; a synthetic
extinction injection is recovered within esds; NAC and SRM 660c refine
extinction ≈ 0 with Rwp not degraded.

```sh
.venv/bin/python -m pytest tests/test_extinction.py -q
.venv/bin/python -m pytest -m "not slow" -q      # nothing else regresses
.venv/bin/python -m pytest -q                    # incl. NAC/SRM660c does-no-harm
```

## Handover log

- **2026-07-23** — created from the cross-code review plan; implementation in
  progress this session.

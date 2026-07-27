# WP-0405 — True Voigt via a shared Faddeeva w(z)

Milestone: v0.4 · Status: ✅ 2026-07-24
Depends on: WP-0401

## Goal

A true-Voigt profile option built on one backend-agnostic Faddeeva `w(z)`
implemented on the WP-0401 op set — never per-backend native `wofz` — so
every backend computes identical values *and gradients*; it slots beside the
default TCHZ pseudo-Voigt and satisfies the profile-normalization property
tests.

## Context

- The TCHZ pseudo-Voigt (`model/profiles/pseudovoigt.py`) **stays the
  default**; true Voigt is an opt-in shape. jax ships `wofz`, torch does not
  — and even where natives exist, their gradients differ per backend, which
  is exactly the drift WP-0404 exists to catch. One implementation
  everywhere.

### Inherited

From **WP-0401** (op shim, landed 2026-07-24):

- **No `scipy.special`, by decision.** The hot path has none, and the shim
  deliberately ships no special-function layer: "the WP-0405 Faddeeva is built
  *on* this op set, so leave room but implement nothing for it here." So `w(z)`
  is a composition of existing ops, or an explicitly justified new op — and
  every op added is a per-backend maintenance liability (numpy, jax, torch).
- **The op inventory, verified 2026-07-24 rather than quoted.** 0401's own
  handover says "37 named ops"; the shipped vocabulary is **32** entries in
  `_OP_NAMES` plus `window_add` / `segment_sum` (34 total), plus `pi` and
  `linalg` (`.inv`/`.det`). Read `src/pxrdref/backend/api.py::_OP_NAMES` for
  the live list — do not trust either number in prose.
- **Complex is first-class but minimal:** `exp` (complex-capable), `conj`,
  `real`, `imag`. There is no complex `erfc` and no complex division op, which
  constrains which `w(z)` algorithm is expressible. complex128 on host/CPU;
  complex64 only under WP-0403's fp32 policy.
- **No general index-array scatter, ever** — `window_add(y, i0, i1, vals)` on
  frozen contiguous windows is the only scatter, because data-dependent
  indices are what frozen-per-stage discreteness exists to forbid. A
  region-split `w(z)` (the usual Humlíček/Weideman approach picks an algorithm
  per |z| region) must therefore be expressed as `where`-masks over the full
  array, not as gathers into per-region index sets.

From **WP-0403** (mixed-precision policy, landed 2026-07-24): if `w(z)` is
ever evaluated below fp64, that is a *Jacobian-column* concern only — the
policy lives in `backend/linalg64.py` and the residual stays fp64 regardless.

### Design (decided)

- **Algorithm: Weideman (1994) rational approximation, N = 32 terms**
  (~fp64 accuracy over the relevant z range; N is a documented module
  constant). Chosen over Humlíček w4 (partitions the complex plane into 4
  regions → branches, hostile to autodiff and to the 0401 branchless goal)
  and Zaghloul & Ali 2011 (higher accuracy but continued-fraction/series
  branches, heavier). Weideman is a single rational form — a polynomial in
  one auxiliary variable plus a complex division — a handful of 0401 ops,
  trivially differentiable, branchless by construction.
- **Licensing:** implemented from the paper (algorithm, not code);
  ATTRIBUTION.md gets a Weideman entry.
- **Placement:** `Instrument.profile.shape: Literal["tchz_pv", "voigt"]`,
  default `"tchz_pv"` — a per-instrument choice, not per-reflection. The
  Voigt consumes the *same* Gaussian/Lorentzian FWHMs the TCHZ machinery
  already computes (`profiles/caglioti.py`; the instrument ⊕ sample width
  split is untouched): z = (x + iγ_L)/(σ√2), V = Re[w(z)]/(σ√2π). FCJ
  composes unchanged — it convolves whatever unit-area profile it is handed.
- **Files:** `model/profiles/faddeeva.py` (w(z) on the op set) +
  `model/profiles/voigt.py` (unit-area profile + analytic ∂V/∂(σ,γ) from
  w(z)); thread the shape enum through
  `phase_peaks`/`_reflection_profile`/`derivative_bases`.

## Non-goals

Replacing the TCHZ default; per-backend native `wofz` (gradient consistency
is the point); FPA-style physical profiles (v2 fence).

## Tasks

- [x] `model/profiles/faddeeva.py`: Weideman N=32 `w(z)` on the 0401 op set;
      paper citation in the docstring; ATTRIBUTION.md entry
- [x] `model/profiles/voigt.py`: unit-area true Voigt + analytic derivs;
      reuse Caglioti/sample FWHM inputs
- [x] `Instrument.profile.shape` enum (default `tchz_pv`), threaded through
      `phase_peaks`/`_reflection_profile`/`derivative_bases`
- [x] Tests: `tests/test_voigt.py` — unit area <1e-6 on the frozen window;
      γ_L→0 Gaussian and σ→0 Lorentzian limits <1e-8; cross-backend w(z)
      agreement <1e-12 (fp64); analytic ∂V/∂(σ,γ) vs FD <5e-3; the FCJ
      smoothness test holds under the Voigt shape + obs/calc/diff PNGs to
      `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_voigt.py tests/test_profiles_background.py -q
```

Measured (2026-07-24): 26 passed. Weideman N=32 vs `scipy.special.wofz`
≤1e-12 over the upper half-plane; Voigt unit-area |A−1| < 1e-6 (worst 6.4e-7,
mixed σ=γ=0.2); γ_L→0 Gaussian and σ→0 Lorentzian limits each < 1e-8;
numpy↔jax w(z) 1.6e-16; numpy↔jax full Voigt residual ≤1e-9; analytic
∂V/∂(σ,γ) vs central FD ≤ few-1e-8; the whole-model peak-chain analytic
Jacobian vs FD under `shape="voigt"` worst 1.3e-3 (< 5e-3) across all 18
column families incl. FCJ; FCJ second-difference smoothness holds under Voigt;
SRM-660c-style lab LaB6 end-to-end (slow) Rwp 0.031, a within 5e-4 Å.

## References

- Weideman (1994) SIAM J. Numer. Anal. 31, 1497 — "Computation of the
  complex error function" (**the implemented algorithm**).
- Humlíček (1982) J. Quant. Spectrosc. Radiat. Transfer 27, 437 — w4
  (rejected: region branching).
- Zaghloul & Ali (2011) ACM Trans. Math. Softw. 38, Algorithm 916
  (rejected: heavier, branched).

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): Weideman N=32
  chosen for branchlessness; per-instrument `profile.shape` enum; files,
  property tests and tolerances decided.
- **2026-07-24** — **implemented and signed off.** Done: `faddeeva.py`
  (Weideman N=32, coeffs computed once at import in plain numpy; hot path is
  Horner + two complex divisions, all Python operators so it dispatches on the
  array's backend with *no* `get_backend()` call and *no* new op in
  `backend/api.py`); `voigt.py` (`voigt`, `voigt_derivs`, `fwhm_to_voigt_params`);
  `Instrument.profile.shape` Literal threaded to `CompiledModel.shape` and
  dispatched via `_peak_widths`/`_profile`/`_profile_derivs` in `forward.py`;
  `tests/test_voigt.py`; ATTRIBUTION (Weideman + Armstrong). Acceptance +
  `ruff` + full fast suite green.
  Design notes for a successor / downstream WPs:
  * **The `phase_peaks` tuple is now shape-polymorphic.** Its 2nd/3rd slots are
    (Γ, η) for TCHZ but (σ, γ_HWHM) for Voigt — `_peak_widths` picks. Every
    consumer (peak-chain Jacobian in `least_squares._peak_chain_column`,
    `lebail_update`, `phase_component`) treats them as opaque width slots and is
    already shape-agnostic; the FD-of-`phase_peaks` chain in the analytic
    Jacobian *just works* because the profile-deriv slots match the width slots.
  * **KNOWN GAP (not in scope, does not affect the default):** `report/layer1.py`
    still reads `bases.peaks[...][1]` as an FWHM (`fwhm_sum += weight*gamma[k]`,
    line ~90) for its 0.4·FWHM validity radius. Under Voigt that slot is σ,
    ≈FWHM/2.355 — i.e. the radius is *tighter*, which is conservative (errs
    toward "non-separable", never toward a confident-wrong singleton), so it is
    safe but slightly suboptimal. If a future WP wants exact L1 attribution
    under Voigt, expose an FWHM from the width slots per shape rather than
    reading slot 1 directly.
  * σ is bounded away from 0 by the Caglioti Γ_G² floor (`_MIN_GAMMA_G2=1e-8`),
    and the Voigt argument always has Im z = γ/(σ√2) ≥ 0, so only the Weideman
    upper-half-plane branch is ever needed (the reflection formula is unused —
    real branchlessness, not a hidden mask).
  * Compile-time window/FCJ-node sizing still uses TCHZ Γ as the width proxy
    under both shapes (it tracks the Voigt FWHM to ~1 %, dwarfed by the 30·FWHM
    window). No separate Voigt sizing path needed.
  Next on this WP: none — shipped.

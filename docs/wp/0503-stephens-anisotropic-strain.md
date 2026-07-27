# WP-0503 — Stephens anisotropic strain broadening

Milestone: v0.5 · Status: 🔶 in progress
Depends on: —

## Goal

A phase may declare an optional `microstrain` block carrying the Stephens
(1999) rank-4 strain invariants S_HKL. The Laue-allowed subspace is *derived*
from the space-group operators by exact rational algebra (no per-Laue-class
lookup table), the coefficients refine as absolute DOFs through the existing
affine constraint block, and the resulting **hkl-dependent** Lorentzian width
enters the forward model, the analytic Jacobian, the guards and a Layer-1
diagnostic that says "the width misfit is directional, and this is the
pattern". Absent block ⇒ bit-identical to today.

## Context

### The physics, and the conventions this WP pins

Peak *positions* depend on hkl only through d; peak *widths* in every model so
far depend on hkl only through θ (`profiles/caglioti.py`: size ↔ 1/cosθ,
strain ↔ tanθ). Real strained powders break that: the width of (00l) and
(hk0) can differ by 3× at the same 2θ. Stephens' phenomenological model gets
there by letting each crystallite have its own lattice metric and computing the
resulting spread of

    M_hkl ≡ 1/d²_hkl = A h² + B k² + C l² + D kl + E hl + F hk

(A = a*², … F = 2a*b*cos γ*). The spread of a *quadratic form's* coefficients
makes the variance of M a **homogeneous quartic** in (h, k, l):

    σ²(M) = 10⁻¹² · Σ_{H+K+L=4} S_HKL · h^H k^K l^L                     (1)

Fifteen monomials, hence ≤ 15 coefficients; lattice symmetry cuts that down
(§ "Symmetry" below). Because 2θ = 2 arcsin(λ√M/2),

    d(2θ)/dM = tanθ / M   ⇒   Δ(2θ) = tanθ · ΔM/M,

so the anisotropic contribution to the width, **in the same deg-2θ FWHM units
`lor_strain` already uses**, is

    Λ(hkl) = (180/π) · 10⁻⁶ · d²_hkl · √(Σ_HKL S_HKL h^H k^K l^L)   [deg]  (2)
    Γ_L(hkl) = (X + lor_size)/cosθ + (Y + lor_strain + Λ(hkl))·tanθ       (3)

**Conventions pinned here, by physics not by letters** (the CLAUDE.md rule):

1. `√(Σ S·monomial)·d²·10⁻⁶` is the **FWHM** of the ΔM/M = 2·Δd/d
   distribution, *not* its standard deviation. No √(8 ln 2) appears anywhere.
   (This is the practical convention every implementing code uses; the
   difference is a constant rescaling of all S_HKL, so it is a *labelling*
   choice, but an undocumented one silently rescales published values.)
2. **S_HKL are stored/refined in units of 10⁻¹² Å⁻⁴** — the 10⁻¹² in (1) and
   the 10⁻⁶ in (2) are the same convention seen twice. This is not cosmetic;
   see "The FD-step trap" below.
3. The anisotropic term is **entirely Lorentzian**. Gaussian/Lorentzian
   mixing of the microstrain (GSAS-II's `Mustrain;mx`) is a non-goal here.
4. S_HKL are the coefficients of the **literal monomials** of (1). Other codes
   fold symmetry multiplicities into their templates (e.g. writing the cubic
   S220 term as `3·(h²k² + h²l² + k²l²)`), so their printed S values differ
   from these by small integer factors *and* by their own unit convention.
   Never transfer a literature S value without checking numerically.

### Symmetry: derive the subspace, do not tabulate it

σ²(M) must be invariant under the Laue group. Miller indices transform as
**h' = Rᵀh** (the CLAUDE.md reciprocal-space invariant; `symmetry.py` already
relies on it). The induced action on the 15-dimensional space of quartic
monomial coefficients is a 15×15 integer matrix per operator, and the allowed
S_HKL span ∩ ker(A(R) − I) — *exactly* the shape of `wyckoff.adp_basis`, and
solvable with the same exact-rational `wyckoff._nullspace_int`. Degree 4 is
inversion-even, so the point group and its Laue class give the same answer and
no Laue-class classification is needed at all.

**Measured with a prototype against Stephens' Table 1** (this is the acceptance
for the symmetry module — the counts reproduce, so the derivation is right):

| Laue class | example symbol | DOFs |
|---|---|---|
| m-3m / m-3 | `P m -3 m` | 2 |
| 6/mmm, 6/m | `P 6/m m m` | 3 |
| -3m1, -31m | `P -3 m 1`, `R -3 c` | 4 |
| -3 | `P -3` | 5 |
| 4/mmm | `P 4/m m m` | 4 |
| 4/m | `P 4/m` | 5 |
| mmm | `P m m m` | 6 |
| 2/m | `P 1 2/m 1` | 9 |
| -1 | `P -1` | 15 |

and the derived patterns are the published ones, e.g. hexagonal gives
`h⁴ + 2h³k + 3h²k² + 2hk³ + k⁴`, `l⁴`, and `h²l² + hkl² + k²l²`.

### The isotropic limit is the seed — and it is exact

M itself is a Laue invariant, so **M² is a quartic that always lies in the
allowed subspace**. Setting S = ε²·[coefficients of M²] gives σ(M)/M ≡ ε for
every reflection: the isotropic-strain limit, reached exactly, with a positive
σ²(M) guaranteed. That is the analogue of `AnisoU.isotropic` /
`adp.isotropic_u6` from WP-0303 and it solves three problems at once:

* **a physically meaningful starting point** (`StephensStrain.isotropic(...)`
  takes a microstrain and a cell);
* **the gradient trap**: at S ≡ 0 the √ in (2) has infinite slope, so a
  refinement started from zero gets a first Jacobian column ~10³× too large
  and TRF takes a garbage step. This is the WP-0310 inherited gotcha in a
  nastier form — see `### Inherited`;
* **positivity**: σ²(M) ≤ 0 for some hkl is unphysical and makes (2) complex;
  starting on the isotropic ray starts inside the cone.

### Degenerate with `lor_strain`, so lock it

The isotropic direction of the S subspace produces exactly `Λ·tanθ` — the
same column as `lor_strain`. The pair is *identically* collinear, not merely
correlated, so a phase carrying a `microstrain` block must have `lor_strain`
locked, exactly as an `Atom` with an `aniso` block has `biso` locked
(`Atom._one_displacement_model`, and `_collect_atom_adps`'s
`force_fixed=True`). `gauss_strain` stays free: it is a different convolution
component (Gaussian variance), not the same column.

### The FD-step trap (why the units matter)

`optimize/least_squares._peak_chain_column` finite-differences `phase_peaks`
with `h = 1e-6 · max(1.0, |θ_c|)` — **absolute** below |θ| = 1. A parameter
whose natural magnitude is 10⁻⁸ gets a step 100× its own value and a
meaningless column. In the 10⁻¹² Å⁻⁴ convention a 0.2 % strain in a 3 Å cell
gives S ≈ 1.6·10⁵ and even a 20 Å cell at 0.1 % gives S ≈ 6, so the step stays
relative. Restate this next to the unit definition in the code: a future
"tidy-up" that rescales S to physical Å⁻⁴ would silently destroy the Jacobian.

### Frozen-per-stage

Windows and FCJ node counts are sized at compile (`compile_model`) from
per-reflection estimated widths — those estimates must include Λ, which means
the frozen monomial matrix and the compile-time S both live on
`CompiledPhase`. Nothing hkl-discrete changes during a solve: Λ moves
smoothly with S and the cell. `WINDOW_FWHM_MULT = 30` leaves ample margin, but
size with a floor if the block is about to be freed from a near-zero start
(the `AXIAL_SIZING_FLOOR` precedent).

### Files to touch

| file | change |
|---|---|
| `crystallography/stephens.py` *(new)* | monomial table, invariant basis (reuses `wyckoff._nullspace_int`), monomial matrix for an hkl list, M² isotropic-limit coefficients |
| `schemas/structure.py` | `StephensStrain` block + `Phase.microstrain`, validators |
| `params/vector.py` | `phases.i.microstrain.dof.k` DOFs, absolute affine ties, out-of-subspace raise, `lor_strain` lock, write-back |
| `model/profiles/caglioti.py` | `lorentzian_fwhm(..., aniso_strain=0.0)` |
| `model/forward.py` | `CompiledPhase.strain_monomials`, Λ in `phase_peaks`, Λ in the compile-time width estimate |
| `strategy/staged.py` | `microstrain` stage; `check_stephens_positive` guard → `GuardReport` |
| `report/strain.py` *(new)*, `report/schemas.py`, `report/__init__.py` | Layer-1 hkl-direction width diagnostic |
| `tests/test_stephens.py` *(new)*, `tests/test_acceptance_brucite.py` *(new)* | unit/property + real-data acceptance |

### Inherited

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — **the one that will
cost a debugging session.** Softplus-transformed sample-broadening terms
starting at exactly 0 have a dead gradient and *never move*: they refine
silently to their start value rather than erroring. The fix is
`Stage(..., seed=…)`, following the extinction-stage precedent
(`pr.Stage("extinction", ["phases.*.extinction"], seed=1e-3)`).

**How it lands here, and why the stock fix does not apply.** The S_HKL DOFs
are *identity*-transform and unbounded (like the ADP DOFs — positivity of
σ²(M) couples all the coefficients, so it cannot be a box), and
`ParameterTable.seed_softplus` touches `transform == "softplus"` entries only.
So `Stage(seed=…)` is a **no-op** on this block. Worse, the failure mode
inverts: a softplus parameter at zero has a *dead* gradient, whereas S ≡ 0 sits
at the √ cusp and has an *exploding* one. The fix is the isotropic seed above
(`StephensStrain.isotropic`), applied at block construction and re-asserted
when the stage frees the DOFs; freeing an all-zero block must **raise**, not
refine to nothing.

From **WP-0303** (anisotropic ADPs, landed 2026-07-23): the ADP tensor
machinery is *not* reusable here, and 0303 fenced this out from its side —
"anisotropic *strain broadening* (Stephens) — that is peak width, not ADPs".
The U^ij site-symmetry basis (`crystallography/wyckoff.adp_basis`) is built for
a rank-2 tensor on a Wyckoff site; Stephens S_HKL are rank-4 invariants per
*Laue class*. Same "symmetry-allowed subspace" idea, different group action —
expect to write it, not import it. Worth copying from 0303 instead: the
convention of making the parameters **absolute** (U = Σₖ θₖ·Bₖ) so site
symmetry is enforced exactly, and raising on an out-of-subspace tensor rather
than silently symmetrising it. *(Confirmed at expansion: only
`wyckoff._nullspace_int` is shared; the group action is written fresh.)*

From **WP-0401** (op shim, landed 2026-07-24): `model/profiles/*.py`
(`pseudovoigt`, `fcj`, `caglioti`) are xp-routed — new width code calls `xp.*`,
bound once per compiled-model call. Also note the frozen-per-stage invariant
bites here: anything hkl-dependent that changes *shapes* (node counts, window
extents) must be computed at stage compile, never inside the solve.

## Non-goals

* **Gaussian/Lorentzian mixing of the anisotropic term** (Stephens' ξ, GSAS-II
  `Mustrain;mx`). Λ is pure Lorentzian here. `gauss_strain` remains the
  isotropic Gaussian strain channel. Revisit only if a real dataset forces it.
* **Anisotropic size broadening** (the 1/cosθ counterpart, e.g. ellipsoidal or
  spherical-harmonics domain shape). Different angular law, different WP.
* **Popa's (1998) alternative parameterisation** and the strain-tensor
  *physical* interpretation of the S_HKL (they are linear combinations of
  lattice-metric covariances). Phenomenological fitting only.
* **CIF export of S_HKL.** No standard `_atom_site`-style loop covers them;
  exporters stay as WP-0309 left them.
* **Multi-histogram.** Single-histogram Rietveld/Le Bail/Pawley only, matching
  where WP-0406 stopped. (Λ depends only on the phase and the cell, so it is
  histogram-independent by construction — but that is untested here.)

## Tasks

- [x] Expand this stub into a full WP before writing code
- [ ] `crystallography/stephens.py`: 15-monomial table, induced quartic action
      from the operators, invariant basis via `_nullspace_int`, monomial matrix
      for an hkl list, M²-expansion for the isotropic limit. Unit tests: DOF
      counts for all Laue classes against the table above, published patterns,
      determinism, and the M² coefficients reproducing 1/d⁴ exactly.
- [ ] `schemas/structure.py`: `StephensStrain` (15 named Parameters +
      `isotropic(microstrain, cell)` / `zero()` constructors),
      `Phase.microstrain`, validator rejecting `lor_strain.vary` alongside a
      block. JSON round-trip test.
- [ ] `params/vector.py`: `phases.i.microstrain.dof.k` DOFs (absolute, identity,
      unbounded), affine ties for the 15 components, raise on an
      out-of-subspace S, raise on freeing an all-zero block, lock `lor_strain`,
      write-back in `apply_to_models`.
- [ ] `model/profiles/caglioti.py` + `model/forward.py`: Λ from (2) folded into
      the Lorentzian strain term; frozen monomial matrix on `CompiledPhase`;
      compile-time window/FCJ sizing sees Λ. Absent block stays bit-identical
      (golden test).
- [ ] Jacobian: confirm the `phases.*` scalar chain covers `…microstrain.dof.k` and that
      the analytic column matches FD *and* jax `jacfwd` to the bars
      `backend/linalg64.py` exports. Add a `toy_stephens` backend golden.
- [ ] Guard + diagnostic: `STEPHENS_STRAIN_NOT_POSITIVE` when σ²(M) ≤ 0 on any
      reflection of the frozen list (mirrors `check_adp_positive_definite`),
      wired into `GuardReport` and the staged runner.
- [ ] `strategy/staged.py`: a `microstrain` stage after `sample_profile`, with
      the isotropic re-seed; document why `Stage.seed` does not serve here.
- [ ] `report/strain.py`: Layer-1 hkl-direction width diagnostic —
      per-reflection ΔΓ extracted from the residual through the existing
      `derivative_bases` ∂Ω/∂Γ column, regressed against the Laue-allowed
      templates (linear in S once squared), scored against the isotropic-only
      baseline so the answer is "how much of the width misfit is *directional*".
      Must report non-separable rather than a confident singleton when the
      templates are collinear over the sampled hkl. `StrainAnalysis` on
      `FitReport`, thresholds pinned in `report/schemas.py`.
- [ ] Tests: misfit injection (inject known S, assert recovery + ranking + low
      confidence in a deliberately collinear setup), negative control on cubic
      SRM 660c (freeing the 2 cubic DOFs must not move `a` beyond its esd and
      must not report detected anisotropy), obs/calc/diff PNGs to
      `tests/output/`.
- [ ] Acceptance on `qarr/brucite.prn` (see below); record the measured numbers
      in the handover log.

## Acceptance

**Real data — `tests/data/qarr/brucite.prn`.** Pure-phase Mg(OH)₂, `P -3 m 1`
(4 Stephens DOFs), the round-robin's platy layered hydroxide: a textbook
anisotropic-broadening specimen where (00l) is sharp and (hk0) broad. The
phase already exists in the repo as `test_acceptance_qpa_roundrobin.brucite_phase`
(cell 3.142, 3.142, 4.766, 90, 90, 120). Criterion: freeing the Stephens block
after an isotropic-strain refinement **improves Rwp by a margin that survives a
Hamilton/ΔBIC test for the 3 added parameters**, the fitted anisotropy is in
the physically expected sense (Λ smaller along 00l than along hk0 — the platy
habit's own signature, independently corroborated by the March-Dollase r ≈ 0.67
WP-0310 measured on the same material), and the Layer-1 diagnostic reports the
anisotropy as detected and separable. Numbers get pinned into the test once
measured — do not invent a tolerance before the first run.

**Negative control — SRM 660c.** Cubic LaB6, 2 DOFs, a certified line-profile
standard with no anisotropic strain. Freeing the block must leave
a = 4.15678 ± 2e-4 Å intact and the Layer-1 diagnostic must report
`detected=False`.

```sh
.venv/bin/python -m pytest tests/test_stephens.py -q
.venv/bin/python -m pytest tests/test_acceptance_brucite.py -q          # slow
.venv/bin/python -m pytest -m "not slow" -q                             # no regressions
.venv/bin/python -m pytest -q                                           # full suite
.venv/bin/python -m ruff check src tests examples
```

## References

- Stephens, P. W. (1999). *J. Appl. Cryst.* **32**, 281–289 — phenomenological
  model of anisotropic peak broadening; the S_HKL invariants and Table 1's
  per-Laue-class term counts.
- Popa, N. C. (1998). *J. Appl. Cryst.* **31**, 176–180 — the equivalent
  strain-tensor formulation (concept reference; not implemented).
- Peterse & Palm (1966). *Acta Cryst.* **20**, 147 — invariant-subspace method
  for symmetry-restricted tensors (the rank-2 case `wyckoff.adp_basis` cites;
  the same construction is used here at rank 4).
- Thompson, Cox & Hastings (1987). *J. Appl. Cryst.* **20**, 79 — the TCH
  pseudo-Voigt the Lorentzian FWHM feeds.
- Data: IUCr CPD QPA round robin, `tests/data/qarr/brucite.prn` — provenance and
  licence note in `tests/data/README.md`.

## Handover log

Append-only, newest first.

- **2026-07-27** — expanded the stub into this WP (task 1 of the checklist).
  Design settled and prototyped before writing it: the Laue-allowed subspace is
  *derived* from the gemmi operators by the induced rank-4 action + exact
  rational nullspace (`wyckoff._nullspace_int`), and a throwaway prototype
  reproduced Stephens' Table 1 DOF counts for every Laue class (2/3/4/5/4/5/6/9/15)
  and the published hexagonal patterns — so no lookup table and no GPL/closed
  source is needed. Four decisions worth not relitigating: (i) S_HKL live in
  10⁻¹² Å⁻⁴ because `_peak_chain_column`'s FD step is absolute below |θ|=1 and
  physical-Å⁻⁴ values (~10⁻⁸) would get a step 100× their own size; (ii) the
  isotropic limit S = ε²·[M²] is exactly in the subspace and is therefore the
  seed, replacing the `Stage(seed=…)` mechanism which is a no-op on
  identity-transform DOFs; (iii) `lor_strain` gets locked when the block is
  present — the two are *identically* collinear, the `biso`/`aniso` precedent;
  (iv) Λ is pure Lorentzian, mixing fenced. Next: `crystallography/stephens.py`.
- **2026-07-22** — created as a stub from the ROADMAP split.
</content>
</invoke>

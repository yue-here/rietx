# WP-2314 — a structural Jacobian costs one structure factor, not one per column

Milestone: unscheduled · Status: ⬜
Track: A large cell
Depends on: 2313 soft (its `bigcell-structural` bench case and the R1 ruling)
Priority: P2 2026-11-27 — a user at the wall: a 40-atom structural fit takes 268.7 s, 77 % of it rebuilding the same structure factor once per column; the workaround (fewer free coordinates) costs the user the refinement they asked for

The coordinate and ADP columns of a Jacobian build the phase's structure factor
**once** per evaluation, and each atom's ∂|F|² **once**, rather than both once
per column. The Biso and occupancy columns take an analytic or incremental
|F|² rather than a whole-phase recompute. A structural stage's cost per Jacobian
then grows with atoms × reflections × operators, not with its square in atoms.
On the 40-atom bench case the structural stages run at least 10× faster (target;
measure before claiming), with every converged number within its reference
tolerance.

## Context

**The measurement** (WP-2313 probe 1; Linux x86_64, 4 cores, `[dev]`, compiled
tier on, under cProfile; 12 × 36 × 4 Å, P2₁2₁2₁, 40 general-position atoms,
899 reflections, `mccusker_structural`). The fit took 268.7 s. The `coordinates`
stage took 119 iterations over 120 columns and `biso` took 30 over 40.

| call | calls | cumulative |
|---|---|---|
| `least_squares._structural_column` | 20 880 | 207.1 s |
| → `forward._structural_intensity_grad` → `structure_factor.d_f2_d_xyz` | 20 880 | 180.7 s |
| → `structure_factor._orbit_terms` | **964 760** | 189.0 s (149.6 s own) |
| → `scattering.f0` | 964 760 | 39.0 s |
| `least_squares._peak_chain_column` (Biso, scale, cell, … by FD of `phase_peaks`) | 4 019 | 29.5 s |
| → `forward._total_f2` → `_nuclear_f2` | 3 239 | 28.4 s |

964 760 / 20 880 = 46 `_orbit_terms` calls per column. That is every atom in the
asymmetric unit plus the target again.

**Why: the code.** `d_f2_d_xyz(hkl, d, sites, xyz, occ, biso, j, …)`
(`src/rietx/crystallography/structure_factor.py:433`) loops over **every**
site, recomputing each one's `_orbit_terms` (positions, `exp(2πi h·x)` over the
frozen op subset, f₀, Debye-Waller) to rebuild A (and B under dispersion), so
that it can return 2·Re(Ā·∂A/∂x_j). `_structural_column`
(`src/rietx/optimize/least_squares.py:1531`) calls it once **per column**, with
that column's coefficients in C, so an atom with three coordinate DOFs pays three
full rebuilds. Per Jacobian that is n_cols × n_asym orbit expansions where
n_asym (to build A once) plus n_asym (one ∂A per atom) would do. For 40 general
atoms the ratio is 120 × 40 / 80 = 60×. Atom count grows with cell volume, so
this is the term that makes a large cell slow.

`d_f2_d_uaniso` (`:491`) has the same shape, and `forward.adp_intensity_grad`
reaches it through the same `_structural_intensity_grad`. An anisotropic
structure pays it per U^ij DOF, up to six per atom.

**The precedent is in the tree.** `CompiledModel.moment_f2_grads`
(`src/rietx/model/forward.py:3132`) computes "every DOF of the phase at once,
because the projected total F_⊥ they all need is the expensive half", and "the
caller caches it for one Jacobian evaluation". `_moment_column` then contracts
cached per-DOF arrays with C's coefficients. Rule 5's *Convention* says the
coordinate and ADP columns take the same shape.

**The shared expansion.** `_orbit_terms` is deliberately the one expression the
forward model and both derivative kernels share ("keeps their expansions of F
literally the same expression"), and it runs under `xp` for the traced
backends. A hoist keeps that: compute every site's orbit terms once, build A/B
from them in the **same site order** (so A is bit-identical to today's), take
each atom's (N, 3) or (N, 6) bracket once, and let the column contract it with
its coefficients. In that form the change is exact and bit-identical, since
each column's arithmetic is unchanged and only its repetition goes. Under the
WP-2313 bar bit-identity is not required. Under it the hoist is also the
change that needs no ruling.

**Biso and occupancy go by finite difference, and that is also quadratic.** The
scalar columns (scale, Biso, occupancy, cell, extinction) "pick it up from the
FD-of-`phase_peaks` chain" (`_f2_derivative_chain`'s comment). One perturbed
Biso recomputes the whole phase's |F|² (`_total_f2` → `_nuclear_f2`, all
atoms). Two exact alternatives:
- an analytic ∂|F|²/∂B_j = 2·Re(Ā·∂A/∂B_j), with ∂A/∂B_j = −s²·amp_a,j·G_j
  for an isotropic site, from the same cached terms;
- an incremental FD, A' = A − a_j G_j + a'_j G'_j, recomputing one site.

The analytic column is a new derivative branch. So, under the *analytic
Jacobian* invariant, it declares its reach (`_column_extras`), gets an exact
oracle, and adds a `test_cross_backend.py` config.

**Forward |F|² is a Python loop over atoms.** `_structure_factors_ab` loops
`for j in range(sites.n_asym)`. At 40 atoms × 4 ops × 899 reflections one
evaluation's `_nuclear_f2` is ~9 ms. The loop could run once over a stacked
(atoms × ops, N) block, as an einsum or a matmul of positions against hᵀ. That
reassociates A's sum, so it moves last bits and needs WP-2313's bar, not R1's.

**The f₀ table.** `scattering.f0(species, stol)` was 39 s of 964 760 calls.
Within a stage with the cell held, stol is fixed, so f₀ per species could be
computed once per evaluation rather than once per site per call. A cell the
stage frees moves stol, so the cache is keyed on the stol array or rebuilt per
evaluation. It is still one per species, never one per site per column.

**Invariants this touches** (root CLAUDE.md): *An analytic Jacobian branch claims
what one parameter name reaches* (a cached block must not hand a tied column a
short reach); *A branch's oracle must be exact*; *Hot-path code must not put a
frozen numpy constant on the left of a python operator* (the cache lives under
`xp`); the traced twin (`backend/traced.py`) must see the same expression.
Anomalous B rides beside A in every path (`sites.f_anom`). A magnetic phase
already uses the cached shape.

**Angles, ordered by cost and bar:**
1. **Hoist, bit-identical**: per-evaluation cache of orbit terms, A/B, and
   per-atom brackets, shared by every coordinate and ADP column. This needs no
   ruling. Expected: `_orbit_terms` calls per Jacobian from n_cols·n_asym to
   2·n_asym.
2. Analytic Biso/occupancy columns (or incremental FD) from the same cache.
3. Vectorise the atom loop in `_structure_factors_ab` and the derivative
   kernels: one (n_asym·m, N) complex exponential, one reduction per site
   segment (`np.add.reduceat`, or a matmul against a site-indicator matrix).
4. f₀ once per species per evaluation.
5. A compiled kernel (the `rietx-kernels` crate) for the orbit expansion and its
   derivatives, under `compiled.py`'s four rules: GIL released, numpy fallback
   exercised, bound stated and asserted.
6. Measure `backend="jax"` on the same case (WP-2313 task) before building 5:
   if a jitted `jacfwd` already wins, angle 5's value falls.

## Non-goals

- The peak-chain (position, width) columns: WP-1945.
- Why the `coordinates` stage needs 119 iterations: WP-2313 task 4, since it
  may be the invented model.
- Rigid bodies and Z-matrix internals (WP-1814): their columns chain through
  coordinates, so they inherit this, and they are not changed here.

## Tasks

- [ ] Re-measure: `bigcell-structural` (WP-2313) unprofiled, best of three, plus
      one profiled run for the split. Record `_orbit_terms` calls per Jacobian.
- [ ] Hoist: one structure-factor block per (phase, evaluation) for coordinate
      and ADP columns; `_structural_column` contracts the cached per-atom bracket.
      Bit-identical: assert every column equal to the pre-change column, byte for
      byte, on the bench case and the existing structural goldens.
- [ ] Biso and occupancy: analytic columns from the cache (or the incremental
      FD). Exact oracle (difference quotient at a 100 % step does not apply: B
      is not linear; use a central difference converging at O(h²) as h shrinks,
      plus the analytic identity at B = 0), the reach declared, and a
      `test_cross_backend.py` config.
- [ ] Vectorise the site loop in `_structure_factors_ab` and the derivative
      kernels. Last-bit movement measured on every golden and reported, and
      every moved number checked against its reference under WP-2313's bar.
- [ ] f₀ once per species per evaluation.
- [ ] Decide the compiled kernel on the measurement after the four above and
      `backend="jax"`'s reading. Build it only if the remaining structure-factor
      share justifies it.
- [ ] Tests: the bit-identity test for the hoist; the oracle tests; a 40-atom
      timing guard as a **runaway guard**, never a timer (root CLAUDE.md
      § Commands).
- [ ] Skill: none (no API change; the speed is the package's).

## Acceptance

`bigcell-structural` structural stages ≥ 10× faster than WP-2313's unprofiled
"before" (target; the measured factor is what gets recorded). Every structural
golden is bit-identical after the hoist. After the vectorisation and the
analytic columns, every moved number is within its reference tolerance.

```sh
.venv/bin/python examples/bench_refinement.py --cases bigcell-structural
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_moment_jacobian.py tests/test_dispersion.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Rietveld, H. M. (1969). *J. Appl. Cryst.* 2, 65-71 (structure-factor
  derivatives; already cited by `d_f2_d_xyz`).
- WP-1327's `moment_f2_grads`: the cached-per-evaluation shape this copies.

## Handover log

- **2026-11-27** — created.

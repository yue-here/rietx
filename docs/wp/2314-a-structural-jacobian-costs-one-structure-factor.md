# WP-2314 — a structural Jacobian costs one structure factor, not one per column

Milestone: unscheduled · Status: 🔄 2026-11-27 — claimed by @yue-here (ghostshift runner)
Track: A large cell
Depends on: 2317 soft (its `bigcell-structural` case and ruling R0); 1945 soft (its open task on batched Biso columns, see Context)
Priority: P2 2026-11-27 — provisional: the track the maintainer opened for a user at the wall; a 40-atom structural fit spends most of its time rebuilding one structure factor per column; re-rate when WP-2317 task 1 names the user's path

## Goal

Every structural column of a Jacobian reads one structure-factor block built once
per (phase, evaluation): coordinates, ADPs, Biso, occupancy, and any column that
reaches them through a tie, a rigid body or a distortion mode. The columns that
move only the intensity are assembled as one block product. A structural
Jacobian's cost then grows as atoms × operators × reflections, not as its square
in atoms. On `bigcell-structural` one Jacobian evaluation is at least 10× cheaper
(target, per evaluation, since the iteration count belongs to the model). Every moved number satisfies WP-2317's ruling R0.

## Context

**The bar** (WP-2317, restated because it is load-bearing): the maintainer asked on
2026-11-27 for "accuracy on par with other codes … speed as fast as possible by any
means". Under ruling R0's working reading:
- a rounding-only change (reassociation, vectorisation, a kernel computing the
  same expression) may move converged numbers within |Δ| ≤ 1e-3 esd and Rwp
  1e-7 relative, re-pinned in the same change;
- a change of method or stopping rule waits for R0 (b)'s ruling.

**The measurement** (WP-2317 probe 1, the physical model: atoms ≥ 1.5 Å apart;
Linux x86_64, 4 cores, `[dev]`, compiled tier on, one run each; 12 × 36 × 4 Å,
P2₁2₁2₁, 40 general-position atoms, 899 reflections, `mccusker_structural`):
- the fit took **75.0 s** unprofiled, against 2.8 s for the 10-atom profile-only
  fit of the same cell;
- `coordinates` took 10 LM iterations over 120 columns, and `biso` took 16 over 40.

The profiled run (84.0 s) splits as:

| call | calls | cumulative |
|---|---|---|
| `lm.minimize` (all stages) | 11 | 73.3 s |
| → Jacobian (`least_squares.py:2350`) | 83 | 72.4 s (0.87 s each) |
| → `_structural_column` | 5 280 | 53.5 s |
| → → `structure_factor.d_f2_d_xyz` | 5 280 | 46.7 s |
| `structure_factor._orbit_terms` (every caller) | 284 560 | 57.1 s |
| `_peak_chain_column` (Biso, occupancy, cell … by FD of `phase_peaks`) | 1 963 | 16.2 s |
| → `forward._total_f2` | 1 834 | 16.5 s |

So 99 % of the solve is the Jacobian, and nearly three quarters of the Jacobian
is the coordinate columns rebuilding A. The first probe drew its atoms inside a
1/15.6 sub-box (65 % of nearest neighbours under 1 Å). It took 251 s
unprofiled, with 119 `coordinates` iterations, and that model's iteration count
measured its degeneracy, not the code. Its per-call shape was the same.

**Why: the code.** `d_f2_d_xyz(hkl, d, sites, xyz, occ, biso, j, …)`
(`src/rietx/crystallography/structure_factor.py:433`) does two things in one
loop over **every** site (`:467-484`):
- it recomputes each site's `_orbit_terms`: positions, `exp(2πi h·x)` over the
  frozen op subset, f₀, Debye-Waller;
- it rebuilds A (and B under dispersion), and keeps the bracket of site j, to
  return 2·Re(Ā·∂A/∂x_j).

`_structural_column` (`src/rietx/optimize/least_squares.py:1531`) calls it once
**per column** with that column's coefficients in C. So an atom with three
coordinate DOFs pays three full rebuilds: n_asym `_orbit_terms` per column,
n_cols × n_asym per Jacobian. A hoist needs n_asym per evaluation, because the
brackets come from the same terms. For 40 general atoms (120 columns) that is
**120×** fewer expansions. `d_f2_d_uaniso` (`:491`) has the same shape, through
`forward.adp_intensity_grad`, and an anisotropic atom pays it per U^ij DOF.

**What the hoist leaves.** On the physical model, `_structural_column` minus its
kernel is 6.8 s of 53.5 s (26 s of 207 s on the first probe):
- the per-column `_f2_derivative_chain` (scale · multiplicity · P · texture ·
  Lp · extinction, per line);
- `_gather_per_line`;
- `_accumulate` onto the pattern.

Every intensity-only column is Ω·(∂I/∂θ_c): the same Ω planes, a different
per-peak coefficient. So the columns can be one dense (peaks × columns) block of
∂I, chained once through `_f2_derivative_chain` with a column axis, and laid onto
the pattern by one sparse-dense product against the compiled Ω. On the physical model
the hoist alone leaves about 26 s of the 72.4 s Jacobian: this 6.8 s, the 16.2 s
of `_peak_chain_column` (angle 3) and ~3 s else. So the ≥ 10× target needs
angles 2 and 3 together, and angle 3 is the larger share.

**Biso and occupancy go by finite difference of `phase_peaks`**
(`_peak_chain_column`), and that is also quadratic: one perturbed Biso recomputes
the whole phase's |F|² (`_total_f2` → `_nuclear_f2`, every atom). Scale already
has its analytic `_scale_column` in Rietveld mode. The options, in order:
- **analytic**: ∂|F|²/∂B_j = 2·Re(Ā·∂A/∂B_j) with ∂A/∂B_j = −s²·amp_a,j·G_j for
  an isotropic site, the B term alike, both from the cached terms;
- **incremental FD**: A' = A − a_j·G_j + a'_j·G'_j, one site recomputed.

Either is a new derivative branch, so it declares its reach under the *analytic
Jacobian* invariant. An exact oracle exists: |F|² is quadratic in occ_j, so a
central difference in occupancy is exact at any step. It is quadratic in
t_j = exp(−B_j·s²), so a central difference in t, chained through dt/dB, is exact
for Biso. That is the *"oracle exact where the branch is"* invariant's form,
stronger than an O(h²) limit.

**Overlap with WP-1945 (🔄, fold-first).** WP-1945 has an open task, "Measured
first, kept only if bit-identical: |F|² orbit sums shared across a batch's cell
columns, and Biso columns batched". Its Non-goals send a reassociating faster
|F|² ("a rank-one Biso update") to "a different WP". So the split is:
- WP-1945 keeps the bit-identical batch inside its one-pass peak-chain design;
- this WP owns the cache, the analytic or incremental Biso/occupancy branch, and
  anything that reassociates.

A successor on either WP reads the other's Tasks first. An entry in WP-1945's
`### Inherited` says so.

**Columns that reach coordinates indirectly take the full FD path.**
`_STRUCTURAL_PATH` matches only `phases.N.atoms.N.(dof|adp).N`
(`least_squares.py:97`), and `_within_atom` refuses any reach across atoms
(`:2109`). So the following all go through `scalar_chain_supported` to
`_peak_chain_column`, one full `phase_peaks` per column, every atom's |F|²
included:
- a rigid-body or Z-matrix column (WP-1814);
- a distortion mode (`test_distortion_block.py`);
- a `tie_equal` across atoms;
- a named variable driving several sites.

With the cache in place, such a column is a contraction of the cached per-atom
brackets over its coordinate reach. That is `_moment_column`'s shape
(`_moment_reach_ok`), with the reach declared and a `test_cross_backend.py`
config added.

**The precedent and the shared expansion.**
- `CompiledModel.moment_f2_grads` (`src/rietx/model/forward.py:3132`) already
  computes "every DOF of the phase at once" and "the caller caches it for one
  Jacobian evaluation". Rule 5 *Convention* says the structural columns take the
  same shape.
- `_orbit_terms` is the expression the forward model and both derivative kernels
  share, and it runs under `xp` for the traced backends.
- `solve/moves.py` also imports it, and drives the compiled
  `solve_orbit_sums` / `solve_orbit_sums_one` (per-site orbit sums on the shared
  pool, wheel ≥ 1.4.0, oracle at 1e-13 relative). So any refactor of
  `_orbit_terms` runs `solve/`'s tests too, and those kernels are a ready-made
  angle for A and every G_j.

**Vectorising the site loop.** `_structure_factors_ab` and the derivative kernels
loop `for j in range(sites.n_asym)`. One (n_asym·m, N) complex exponential and a
per-site reduction removes the loop. Two constraints:
- `np.add.reduceat` is not in `backend.api._OP_NAMES`, and the code is traced.
  So the reduction is an einsum or a matmul against a site-indicator matrix, or a
  new op implemented on every backend (`test_backend_conformance.py` fails
  otherwise).
- Reassociating A's sum moves the jax/torch goldens too (`_orbit_terms`'
  docstring warns of exactly this), so it runs the full suite, not only the fast
  selection.

**f₀.** `scattering.f0(species, stol)` is called once per site per `_orbit_terms`
call. It could be once per species per evaluation: stol is fixed while the cell
is held, and rebuilt per evaluation where the cell is free.

**Invariants this touches** (root CLAUDE.md):
- *An analytic Jacobian branch claims what one parameter name reaches*, and a
  new branch declares its reach;
- *A branch's oracle must be exact*;
- the hot-path operator rule: the cache lives under `xp`;
- the traced twin sees the same expression;
- anomalous B rides beside A in every path (`sites.f_anom`).

**Angles, ordered by cost and bar:**
1. **Hoist** (kind (a), bit-identical as built: same site order, same
   per-column arithmetic). A per-evaluation cache of orbit terms, A/B and
   per-atom brackets, shared by every coordinate and ADP column.
2. **The Ω·∂I block**: every intensity-only column in one chained block and one
   sparse-dense product.
3. **Biso/occupancy** analytic or incremental, from the cache (with WP-1945's
   split above).
4. **Cross-atom reach**: rigid bodies, Z-matrix, distortion modes, ties as
   contractions of the cache.
5. **Vectorise the site loop** (kind (a)), within the traced-op rule.
6. **f₀ once per species per evaluation.**
7. **The compiled orbit kernels**: reuse `solve_orbit_sums` for A and G_j, or a
   new kernel under `compiled.py`'s four rules. Decide on the measurement after
   1-6.

## Non-goals

- The peak-chain (position, width) columns, and the bit-identical batched Biso
  task: WP-1945.
- Iteration counts: a property of the model and the stopping rule (WP-2317 task 5, R6).
- New rigid-body or Z-matrix features (WP-1814); only their columns' cost is in
  scope (angle 4).

## Tasks

- [x] Measure main against the branch on `bigcell-structural`, interleaved, one
      machine, min-max over at least three runs, plus one profiled run for the
      split. Record `_orbit_terms` calls per Jacobian, before and after.
      *(2026-11-27, angle 1 against main: the handover log's first entry.
      Re-run it for each later angle, angle 1 as the "before".)*
- [x] Angle 1, the hoist: assert every column byte-equal to the pre-change
      column on the bench case and the structural goldens.
      *(2026-11-27: all 83 Jacobians of the bench fit hash equal;
      `test_backend_shim.py`'s 19 goldens pass.)*
- [ ] Angle 2, the Ω·∂I block. Columns within R0 (a)'s bound of angle 1's.
- [ ] Angle 3, Biso/occupancy, with the exact oracles above, the reach declared,
      and a `test_cross_backend.py` config.
- [ ] Angle 4, cross-atom reach, the same three obligations.
- [ ] Angles 5-6. The full suite, since jax/torch goldens move. Every moved number
      checked against R0 (a).
- [ ] Angle 7, decided on the remaining structure-factor share.
- [ ] Tests: the byte-equality test for angle 1; oracle tests; a timing guard on
      the bench case as a **runaway guard**, never a timer.
      *(Angle 1's landed: `tests/test_structural_hoist.py`. The timing guard
      waits for WP-2317's `bigcell-structural` bench case, which does not
      exist yet; the probe stood in for it.)*
- [ ] Skill: none (no API change).

## Acceptance

- One Jacobian evaluation on `bigcell-structural` is ≥ 10× cheaper than main's,
  measured interleaved in the same session (target; the measured min-max is what
  is recorded).
- Angle 1 is byte-equal.
- Every later moved number is within R0 (a)'s bound, or ruled under R0 (b).

```sh
.venv/bin/python examples/bench_refinement.py --cases bigcell-structural
.venv/bin/python -m pytest tests/test_jacobian.py tests/test_cross_backend.py tests/test_distortion_block.py tests/test_moment_jacobian.py tests/test_dispersion.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Rietveld, H. M. (1969). *J. Appl. Cryst.* 2, 65-71 (structure-factor
  derivatives; already cited by `d_f2_d_xyz`).
- WP-1327's `moment_f2_grads`: the cached-per-evaluation shape this copies.

## Handover log

- **2026-11-27** — Filed from WP-2317's probe. A fresh subagent reviewed the plan
  the same day, and its findings are folded in: the 120× call arithmetic, the
  Ω·∂I block, cross-atom reach, the exact oracles.
  - *Fold-first:* no open WP owns the coordinate/ADP columns' structure-factor
    cost. WP-1945 (🔄) owns the peak-chain columns and one bit-identical
    batched-Biso task. The split is recorded in Context and in WP-1945's
    `### Inherited`.
  - *Next:* angle 1, the hoist, needs no ruling and can start. Measure main
    against the branch, interleaved, first.

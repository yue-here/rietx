# WP-2314 — a structural Jacobian costs one structure factor, not one per column

Milestone: unscheduled · Status: 🔄 2026-11-28 — angles 1-4 landed (angle 2, the shared intensity chain, in PR #PRNUM at 1.2-1.35× per Jacobian, byte-equal); angles 5-7 and the rigid-body columns open
Track: A large cell
Depends on: 2317 soft (its `bigcell-structural` case and ruling R0); 1945 soft (its open task on batched Biso columns, see Context)
Priority: P2 2026-11-27 — the maintainer's large-cell track, ruled to proceed whatever the user's case shows (cells this size are met in the wild); a 40-atom structural fit spends most of its time rebuilding one structure factor per column, and the user's Rietveld stages take ~25 min each

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
means". R0 was ruled that day (WP-2317, DESIGN-RULES Rule 5 *Arithmetic accuracy*):
- a change that only regroups arithmetic is verified at fixed parameters
  (`compiled.py` rule 3), guarded on the whole fit by the measured spread
  (`test_compiled_kernels.FIT_THETA_ESD`), and re-pins its goldens in the same
  change;
- a change of tolerance, stopping rule or method holds each quantity a user
  reads as accurately as users need, the established programs being the evidence
  of what suffices, with the error read in esd (R0 clarified the same day; Claude
  settles each such trade and lists it).

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

### Inherited

- **From WP-2317, 2026-11-27 (task 2 and the cross-code timing).** The bench
  case is `bigcell-structural` in `examples/bench_refinement.py`: 10.90-11.30 s
  over two blocks on one Mac, Rwp 0.08675, coordinates 10 and biso 16
  evaluations. GSAS-II 5.8.4 on the same pattern and free set took
  18.13-20.41 s in 20 cycles at Rwp 0.08753, so after the hoist rietx is
  already 1.6-1.9× faster than GSAS-II here. WP-2317's Context has the
  protocol. (Its pointer to a runaway guard on the case is consumed: the
  guard is a count, the 2026-11-27 second-session entry.)
- **From WP-2317, 2026-11-27 (4th session): the case is now a real
  structure.** `bigcell-structural` carries Nb₁₈W₁₆O₉₃ (COD 2107344, Pbam,
  43 sites, eight co-sited Nb/W pairs tied), freeing 66 coordinate and 35 Biso
  columns over 886 reflections where probe 1 freed 120 and 40 over 913. The
  figures in the entry above are probe 1's, so this WP's "before" is
  re-measured on the new case. WP-2317's Context has the new range.

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
- [x] Angle 2, the Ω·∂I block. Columns within R0 (a)'s bound of angle 1's.
      *(2026-11-28: the intensity chain once per phase over an (N, K) block
      of ∂|F_N|², every Jacobian byte-equal, `tests/test_site_column_block.py`.
      The accumulation onto the pattern stays one call per column; the
      handover entry says why.)*
- [x] Angle 3, Biso/occupancy, with the exact oracles above, the reach declared,
      and a `test_cross_backend.py` config.
      *(2026-11-28: analytic, from the angle 1 cache. The reach is the Biso and
      occupancy rows of one phase, summed through C, so the co-sited ties take
      the branch. `test_cross_backend.py`'s `site_scalars` row; five backend
      goldens re-pinned, `tests/data/README.md` § WP-2314 re-baseline.)*
- [x] Angle 4, cross-atom reach, the same three obligations.
      *(2026-11-28: ties across atoms, named variables and distortion-mode
      amplitudes, by `_site_column`, the chain rule over the cached site
      gradients. `test_cross_backend.py`'s `site_cross_atom` row. Rigid
      bodies and Z-matrices were declined, measured; the item below.)*
- [ ] Rigid-body and Z-matrix columns from the cache, once the body block's
      partials are exact where the true partial is zero (an atom at a turn's
      centre now gets ~1e-17, which an analytic sum turns into a live noise
      column; `_site_reach_ok`'s docstring).
- [ ] Angles 5-6. The full suite, since jax/torch goldens move. Every moved number
      checked against R0 (a).
- [ ] Angle 7, decided on the remaining structure-factor share.
- [x] Tests: the byte-equality test for angle 1, and a **runaway guard**
      against the bench case's cost returning, never a timer.
      *(Angle 1's landed: `tests/test_structural_hoist.py`. 2026-11-27: the
      guard is that file's `_orbit_terms` count on its four-atom fixture, not
      a wall-clock budget on `bigcell-structural`; the docstring of
      `test_one_expansion_serves_every_structural_column` says why. A
      negative control now shows the count trips on a per-atom expansion.)*
- [x] Tests: the oracle tests for angles 3 and 4, landing with each angle.
      *(Angle 3's landed, 2026-11-28: `tests/test_biso_occ_columns.py`, the
      exact oracles plus the count guard with Biso free and its negative
      control. Angle 4's, 2026-11-28: `tests/test_cross_atom_columns.py`, the
      chain rule over single-atom kernels, a tied column as the sum of its
      untied ones, a Richardson difference, and the count guard with its
      negative control.)*
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

- **2026-11-28** (fourth session) — Angle 2 landed in PR #PRNUM (a
  ghostshift runner). Every coordinate, ADP, Biso and occupancy column now
  shares one pass through the intensity factors per phase per Jacobian.
  Before, each column rebuilt the same scale, multiplicity, Lorentz,
  preferred-orientation, extinction and absorption factors for itself. The
  arithmetic per column is unchanged, so every Jacobian of the bench fit is
  byte-equal to main's and no number moves. On `bigcell-structural` one
  Jacobian costs 1.2-1.35× less and the fit runs 1.1-1.2× faster, measured
  on a loaded machine. The largest cost left is the structure factor the
  cell columns rebuild once per column, about a quarter of the profiled fit.
  - *Picked on a profile* (this Mac, darwin arm64, `[dev]` venv, compiled
    tier on, one cProfile run of the bench fit on main cd4a461f1, loaded
    machine, so shares only; 11.1 s profiled, 6.2 s in 118 Jacobians).
    `_structural_column` and `_site_column` took 2.2 s, 20 % of the fit: the
    per-column chain and its d-spacings 1.06 s, sparse reads of C and the
    local Jacobian 0.52 s, the accumulation onto the pattern 0.47 s. The
    cell family took 1.85 s (WP-1945's). `structural_f2_grads`, the target
    of angles 5-7, took 0.83 s, 7.5 %. So angle 2 was the largest share this
    WP owns, and it needs no decision.
  - *Done:* `CompiledModel._f2_derivative_chain` and `site_intensity_grad`
    take an (N, K) block of ∂|F_N|² and broadcast each factor down the
    column axis. The two site branches of `_make_jacobian` now only build
    each column's ∂|F_N|² (`_structural_df2`, `_site_df2`) and queue it per
    phase. `_site_columns` then runs the chain once per phase, gathers the
    block onto the peak rows, and accumulates each column as before. The
    constraint directions are read off C once per run and the site
    columns' local Jacobian in one sparse read per Jacobian.
    `_structural_intensity_grad` now goes through `site_intensity_grad`, so
    the nuclear mask has one copy.
  - *Measured* (same Mac and venv; main at cd4a461f1 as a `git archive`
    snapshot first on `sys.path`, the branch at 9c8f1dd48; seven
    interleaved main/branch pairs under the suite lock, another runner's
    two processes at 100 % CPU throughout, driver
    `~/.cache/ghostshift/rietx/wp-2314-a7/jachash.py`, outside the tree):
    all 118 Jacobians of the fit hash equal to main's in every pair, and
    the refined values, esds and Rwp are equal. On the last four pairs,
    with CPU time recorded:

    | | main | branch | pairwise |
    |---|---|---|---|
    | fit wall | 7.8-9.4 s | 6.4-8.5 s | 1.09-1.21× |
    | one Jacobian | 35-43 ms | 26-35 ms | 1.21-1.35× |
    | CPU in Jacobians | 5.7-6.8 s | 4.4-5.9 s | 1.13-1.28× |

    The first three pairs ran under heavier load (main 7.4-10.5 s, branch
    8.9-9.5 s) and rank nothing.
  - *Gates* (darwin arm64, `[dev]` venv): the fast selection on main
    (300853e90) merged into the branch, 15 933 passed, 467 skipped,
    30 xfailed, none failed. The branch adds 7 cases there, all in
    `tests/test_site_column_block.py` and all passing, 0.26 s in the local
    junit. No golden moved. Ruff, Vale (0 errors) and
    `tests.reader_output` (exit 0, unchanged) are clean. The full selection
    was not run: every Jacobian of the bench fit is byte-equal to main's,
    so no measured number can move (`tests/CLAUDE.md` § Running).
  - *Review:* `/code-review high --fix` found no bug and five nits. Fixed:
    the new test's docstrings now say the oracle shares the one-column
    chain and name the five chain factors the fixture turns on; DESIGN.md
    no longer names `_structural_column`; the duplicate nuclear-mask path
    in `_structural_intensity_grad` now calls `site_intensity_grad`.
    Declined: chunking the (N, K) block for memory. The block is the size
    of the gradient cache `structural_f2_grads` already holds per Jacobian,
    and smaller than the Jacobian itself, which has a row per pattern point
    where the block has one per reflection. The generality judge was not
    dispatched: no `_audit.py` row and no heuristic was added. No rulebook
    was edited.
  - *Next:* (1) The cell columns' structure factor. Each cell column's
    `phase_peaks` rebuilds the whole |F|² at its perturbed d: 589
    `_total_f2` calls, about 3 s of the 13 s first profiled run, and nearly
    nine tenths of every `_orbit_terms` call in the fit. Angles 5-7 (the
    vectorised site loop, f₀ once per species, a compiled orbit kernel)
    cut that cost for every structure factor, with goldens re-pinned under
    R0; WP-1945's cell task cuts the number of calls, bit-identically. Do
    the one whose owner is free first. (2) The accumulation onto the
    pattern is still one compiled call per column, 0.47 s profiled. A
    batched form needs a kernel or a scatter order proved equal to the
    compiled one. (3) The rigid-body columns, as before.
- **2026-11-28** (third session) — Angle 4 is measured and in PR #1882 (a
  ghostshift runner, continuing the second session's branch). A column that
  moves several atoms' site rows no longer re-runs the whole phase's
  structure factor. That covers the co-sited coordinate ties, a named
  variable over several sites and a distortion-mode amplitude. On
  `bigcell-structural` one Jacobian now costs about half what it did after
  angle 3. The fit runs 1.5× faster than
  main. The tied columns are now exact where they were a finite difference,
  so the converged values moved, by at most 2.3e-4 of an esd. The ≥ 10×
  target is still far off. The cell columns are now the largest single cost
  left, and they belong to WP-1945.
  - *Measured* (this Mac, darwin arm64, Python 3.12.10, `[dev]` venv,
    compiled tier on; main at 02341ffdb and the branch at 90ff6f334, each a
    `git archive` snapshot first on `sys.path`; three runs each, interleaved
    main/branch, under the suite lock, on a quiet machine; driver
    `~/.cache/ghostshift/rietx/wp-2314-next/drive_plain.py`, outside the
    tree, running `examples/bench_refinement.py`'s `bigcell-structural`
    setup):

    | | main | branch |
    |---|---|---|
    | fit wall | 10.6-11.6 s | 7.2-7.4 s |
    | all Jacobians | 7.3-8.0 s (119) | 3.9-4.0 s (118) |
    | one Jacobian | 61-68 ms | 33-34 ms |
    | `_orbit_terms` calls per Jacobian, median (max) | 774 (774) | 172 (172) |
    | `_orbit_terms` calls in the Jacobians, whole fit | 62 436 | 17 114 |
    | Rwp | 0.035183632067218515 | 0.03518363207014945 |

    Each arm's three runs are bit-identical to each other. Over the 219
    parameters with an esd the largest move is 2.3e-4 esd (atom 10's Biso),
    and the median is 2.4e-5 esd. No esd changed by more than 3e-5 of
    itself, and Rwp moved by 8.3e-11 relative. Two stages took one iteration
    fewer (`biso` 33 to 32, `roughness` 14 to 13). The move is the change of
    method, a finite difference replaced by the exact column, so it is a
    kind (b) move under R0 and is judged in esd. A per-family timer run
    (same machine, one run each) puts main's tied coordinate columns at
    3.8 s of 7.3 s of Jacobians; on the branch they are 0.55 s of 3.9 s in
    `_site_column`, and the cell columns, 1.26 s on both arms, are the
    largest family left.
  - *Gates* (darwin arm64, `[dev]` venv): the fast selection on the
    branch before main was merged: 15 919 passed, 467 skipped, 30 xfailed.
    The branch adds 21 cases there: `test_cross_atom_columns.py`'s 13 pass,
    and `test_cross_backend.py`'s `site_cross_atom` row passes 3 and skips 5,
    the jax and torch rows this venv lacks. No golden moved in the fast
    selection. The full selection on main (79010c3c3)
    merged into the branch, once: 16 880 passed, 478 skipped, 49 xfailed,
    1 xpassed. The xpass is `test_surface_roughness`'s corundum case, a
    non-strict xfail. It xpasses on main's snapshot too (02341ffdb, same
    venv), so it is not this branch's; WP-2017's `### Inherited` has it. Main then moved to
    20a0fcd1a, merged here after the full selection. Its one code change
    is `optimize/bccg.py` (WP-2315), which shares no file with this branch,
    so the full selection was not rerun; CI's fast matrix runs the merged
    tree. The added tests cost 1.08 s in
    the fast run (junit, local), 1.07 s of it in
    `test_cross_atom_columns.py`, whose slowest test is the rigid-body
    decline at 0.52 s over three cases.
  - *Review:* the second session's `/code-review high --fix` stands; this
    session changed no code. No rulebook was edited. The generality judge
    was not dispatched: the branch touches no `_audit.py` row and adds no
    heuristic, since `_site_reach_ok` is a dispatch on what a column reaches.
  - *Next:* (1) angle 7 or WP-1945's cell family, now a third of a
    Jacobian on the bench case (WP-1945's `### Inherited` says so). (2) The
    rigid-body columns, once the body block's partials are exact at zero.
    (3) Angles 2, 5 and 6 as before.
- **2026-11-28** (second session) — Angle 4 is in the branch
  `wp2314-cross-atom-reach`, unmeasured end to end and with no PR yet (a
  ghostshift runner that stopped at its context cap). A column that moves
  several atoms' site rows no longer re-runs the whole phase's structure
  factor. The co-sited Nb/W coordinate ties of `bigcell-structural`, a named
  variable over several sites, and a distortion-mode amplitude now take the
  analytic chain rule over the cached site gradients. A profile picked this
  angle: those tied coordinate columns were half of the Jacobian's time,
  against a sixth for the cell columns. Rigid-body columns were declined
  after a measured failure.
  - *Why angle 4 and not angle 7:* one bench fit with a timer per column
    family (this Mac, darwin arm64, `[dev]` venv, on a loaded machine, so
    the shares hold and the seconds do not) put 10.8 s of 21.2 s of
    Jacobians in the peak-chain coordinate columns (1 050 calls, the 14
    co-sited DOF columns), 3.3 s in the cell columns (327 calls), 1.9 s in
    `_structural_column`, 1.7 s in `derivative_bases` and 1.5 s in
    `structural_f2_grads`. The last entry's reading that the cell columns
    led was wrong: the tied coordinate columns had never left the peak
    chain. Angle 7 waits, since the cell share is WP-1945's cell family and
    is now the largest peak-chain cost.
  - *Done:* `_site_scalar_column` is now `_site_column` and
    `site_scalar_intensity_grad` is `site_intensity_grad`. The branch claims
    a column when every path it moves is a site row of one phase (x, y, z,
    U^ij, Biso, occupancy) or a parameter the data rows never read (a
    site-symmetry DOF, a mode amplitude, a variable): `_site_reach_ok`.
    `_within_atom` admits only the rows `_structural_column` reads, so a DOF
    column that also reaches its atom's ADP or Biso is summed whole; it was
    short before. A rigid body stays on the peak chain: its block returns
    ~1e-17 partials where the truth is zero, the analytic sum makes a
    1e-13 noise column, and `test_rigid_body`'s `RIGID_BODY_UNSUPPORTED`
    case then lost the origin's esd. The open item above holds it. New
    `tests/test_cross_atom_columns.py`; `test_cross_backend.py` gains
    `site_cross_atom` (in `NO_FD_CONFIGS`); the distortion test now asserts
    the new dispatch.
  - *Measured* (darwin arm64, `[dev]` venv): at the bench's start θ the 14
    co-sited DOF columns moved by 2.1-7.1e-5 relative, and every other
    coordinate and Biso column is byte-equal to main's (02341ffdb). Against
    a Richardson difference the new columns sit 6e-12 to 4e-10 off, the old
    2.4e-5 to 7.1e-5. On the test fixture the chain-rule oracle holds to
    1.9e-16 and a tied column equals its untied pair to 1.7e-16. Jacobian
    rows touched pass `fd`, `jax` and `jax+fp32` in the `[dev,jax]` scratch
    venv (35 passed, 21 skipped, torch absent). The touched test modules
    pass under `[dev]` (207 passed, 210 skipped). CI's lint steps and Vale
    are clean (no warning on a changed line).
  - *Review:* `/code-review high --fix` found no correctness bug. It put the
    estimation page back under its 50 000-character cap, read the local
    Jacobian column once per site column, and fixed stale branch names.
  - *Next:* (1) read the interleaved timing, main against the branch, from
    `~/.cache/ghostshift/rietx/wp-2314-next/` (`interleave.sh`, logs
    `main_N.log`, `branch_N.log`, `fam_*.log`) or rerun it under the suite
    lock, and fill this entry's fit and per-Jacobian figures. (2) Run the
    fast suite; any golden with a cross-atom tie or a mode amplitude moves
    and is re-pinned with its move in esd (R0). (3) The full suite once,
    then `/wp-handover` from step 7 and the PR. (4) After that, angle 7 or
    WP-1945's cell family is the largest Jacobian cost left.

- **2026-11-28** — Angle 3 landed: Biso and occupancy columns from the
  cache (PR #1876, a ghostshift runner). A Biso or occupancy column no
  longer re-runs the whole phase's structure factor. It is now analytic,
  built from the one expansion per phase that the coordinate columns
  already share, and exact rather than a finite difference. On
  `bigcell-structural` one Jacobian costs about half what it did on main,
  and the fit runs 1.6× faster. Every refined value moved by at most 4e-6
  of its esd, and the stage iteration counts are identical. The ≥ 10×
  target is still far off. What remains is mostly the cell columns, whose
  finite difference re-expands |F|² at a perturbed cell.
  - *Done:* `structure_factor.d_f2_d_sites` also returns ∂|F|²/∂B_j and
    ∂|F|²/∂occ_j, from the same pass over the sites, and so a 4-tuple now.
    The real scattering amplitude is factored out of `_orbit_terms` as
    `_scattering_factor`, bit-identically, so the occupancy derivative reads
    it bare and never divides by an occupancy.
    `CompiledModel.structural_f2_grads` passes the two new atom lists
    through, and `site_scalar_intensity_grad` chains a summed ∂|F|² through
    the coordinate columns' chain with the nuclear mask. In `_make_jacobian`
    the new `_site_scalar_column` claims a column when every path it moves
    is a Biso or occupancy row of one phase (`_site_scalar_reach_ok`). It
    sums each row's gradient weighted by the column's coefficient, read from
    `ParameterTable.local_jacobian` where a formula block writes the row and
    from C elsewhere. So the co-sited Nb/W Biso ties, an occupancy remainder
    (occ_W = 1 − occ_Nb), a formula tie and a named variable over several
    sites all take the branch. A column reaching anything else, a phase with
    a moment, or a non-Rietveld mode keeps the peak chain.
    `tests/test_biso_occ_columns.py` holds the exact oracles: occupancy by a
    central difference at half the value, Biso by the quadratic in
    t = exp(−B s²) through three points, and a whole occupancy column
    against a central difference of the residual at a 100 % step
    (extinction off makes the pattern quadratic in occupancy). It also holds
    the count guard the second entry owed, with Biso free, and its negative
    control. `test_cross_backend.py` gains the `site_scalars` row
    (dispersion on, extinction at 30, the three tie shapes). The manual's
    estimation page names the new columns. WP-1945's `### Inherited` is told
    that its "Biso columns batched" half has nothing left to batch.
  - *Measured* (this Mac, darwin arm64, Python 3.12.10, `[dev]` venv,
    compiled tier on; main at 8e691ccb8 from a `git archive` snapshot first
    on `sys.path`; three runs each, interleaved main/branch, under the suite
    lock; driver `~/.cache/ghostshift/rietx/wp-2314-a3/drive_a3.py`, outside
    the tree, running `examples/bench_refinement.py`'s `bigcell-structural`
    setup with its co-sited ties):

    | | main | branch |
    |---|---|---|
    | fit wall | 17.7-18.5 s | 11.1-11.2 s |
    | all 119 Jacobians | 14.3-14.8 s | 7.5-7.6 s |
    | one Jacobian | 120-125 ms | 63-64 ms |
    | `_orbit_terms` calls per Jacobian, median (max) | 774 (2 279) | 774 (774) |
    | `_orbit_terms` calls in the Jacobians, whole fit | 146 716 | 62 436 |
    | Rwp | 0.035183632067171684 | 0.035183632067218515 |

    Each arm's three runs are bit-identical to each other. Over the 219
    parameters with an esd the largest move is 3.6e-6 esd (atom 10's Biso,
    15.4175 Å², esd 5.33). The largest relative change of an esd is 7e-7,
    and Rwp moved by 1.3e-12 relative. The stage iteration counts are
    identical on both arms (the `biso` stage 33). A profiled branch run
    (13.1 s, the profiler's overhead included) puts 6.1 s of the 8.8 s of
    Jacobians in `_chained_columns`, the peak-chain columns, with 1 645
    `_total_f2` calls. Those are the columns whose |F|² moves through d, the
    cell lengths first. The ratio is 1.9× per Jacobian, against the WP's
    ≥ 10× target over angle 1.
  - *Moved numbers, under R0.* The residual is untouched. Only the
    Jacobian's Biso and occupancy columns changed, from a forward difference
    to the exact derivative. That changes the solver's path, never the
    model, so it is a speed change under DESIGN-RULES Rule 5 *Arithmetic
    accuracy* and its error is read in esd: 3.6e-6 esd at most, beside the
    0.2-0.5 esd a 1-ulp `exp` change already moves a converged fit (WP-2317
    R0). Five backend goldens (`toy_roughness`, `toy_restraints`,
    `toy_anomalous`, `nac`, `srm660c`) were re-pinned in the same change.
    Only their Biso and occupancy columns moved, and the new columns sit
    5e-13 to 8e-10 from a Richardson-extrapolated difference where the old
    sat 0.9-4.0e-7 from it (`tests/data/README.md` § WP-2314 re-baseline).
    Every bar the new tests assert is a rounding bound, not a byte
    comparison, so Linux x86_64 OpenBLAS is held to it too.
  - *Gates* (this Mac, darwin arm64, Python 3.12.10, `[dev]` venv, under
    the suite lock): fast suite 15 903 passed, 462 skipped, 30 xfailed
    (8 min 25 s). Main's count was not measured, so the added cases are by
    construction. The six added tests cost 0.24 s together
    (`tests.added_test_times`, local seconds). Full suite once on this
    tree: 16 863 passed, 473 skipped, 49 xfailed, 1 xpassed and 1 failed
    (34 min). The failure was `test_suite_alarms`' pin: zincite gained
    `COVARIANCE_DIRECTION_DISCARDED` on the Gaussian-size, Gaussian-strain
    and W triple. A sweep of seven 1e-14 starts on W found it at k = 0
    only on this branch and at none on main, so it is the rounding-decided
    class WP-2036 already lists for fluorite, and zincite's `ROUNDING` set
    now names it. `tests/test_suite_alarms.py` then passed, 10 tests; the
    full suite was not rerun for that test-side change. `site_scalars` and
    the `families_*` rows pass `fd`, `jax` and `jax+fp32` in a scratch
    `[dev,jax]` venv (jax 0.12.1): 16 passed, 8 skipped (torch absent).
    CI's lint job run locally: ruff, the tutorials' format, Vale (0
    errors; no warning on a line this change wrote), `skill_caps`,
    `skill_surface`, `audit_delta`, `code_references --delta`,
    `rulebook_limits`, all clean. `tests.reader_output` exit 0, unchanged
    against 5a06184af. `test_docs_consistency`: 57 passed.
  - *Review:* `/code-review high --fix` found no correctness bug. It added
    the scattering-factor citations to `_scattering_factor`, named Biso and
    occupancy in `sabine_extinction_and_dx`'s docstring, and made the
    ADP-hump block reuse the one local Jacobian per call. It also found
    that `families_tied` in `test_cross_backend.py` lost coverage: its
    general affine tie now takes the new branch, so no traced row crossed
    the peak chain under a tie. The row gains an affine tie between two
    width scalars (gauss_strain = 2·lor_size + 0.001), traced to the peak
    chain; it passes the `fd`, `jax` and `jax+fp32` methods. The fast run
    found one real defect before the review: a formula tie onto a Biso
    (`2 * B_La + 0.1`) was declined while the equal matrix tie took the
    branch, so the two spellings differed by 4e-5 (`test_tie_expression`). The coefficients now come from
    `local_jacobian`, and the two agree to rounding.
  - *Settled by Claude:*
    1. A column reaching a row a formula block writes takes the branch,
       with its coefficients read from `ParameterTable.local_jacobian`.
       Declining such a column to the peak chain was the alternative.
       Settled under root CLAUDE.md, "An analytic Jacobian branch claims
       what one parameter name reaches", and `test_tie_expression`'s
       existing rule that a linear formula meets the matrix tie to
       rounding. `local_jacobian` is exact for a formula row, where C holds
       no coefficient; declining made the two spellings of one tie differ
       by 4e-5.
    2. The Biso and occupancy columns moved off the forward difference, so
       every fit freeing one moves at the 1e-6-esd level and five goldens
       were re-pinned. Settled under DESIGN-RULES Rule 5 *Arithmetic
       accuracy* and WP-2317's R0: the residual is unchanged and the move is
       read in esd. WP-1121's analytic scale column is the precedent for
       the re-pin.
    3. The occupancy derivative recomputes f₀ and exp(−B s²) for its atom
       rather than dividing the cached amplitude by the occupancy. The
       division was the alternative. Settled under Rule 4 (*A new API*): an
       occupancy at 0 is a legal start, and division there is undefined.
    4. Zincite's discarded-direction finding on the width triple left the
       alarm pin, as fluorite's did. Re-pinning `suite_alarms.json` with it
       was the alternative. Settled under WP-2036's rule that the pin holds
       what the platforms share: the finding fires at one of seven 1e-14
       starts, so Linux could read either answer.
  - *Generality:* no heuristic, threshold or default added and `_audit.py`
    untouched, so no judge.
  - *Next:*
    1. Angle 2 (the Ω·∂I block) and the cell columns are what is left of
       the Jacobian. The cell columns are WP-1945's cell family; read its
       Tasks before starting angle 7 here, because the profile says |F|² at
       a perturbed d is now the largest single cost.
    2. Angle 4 (cross-atom reach) can reuse `_site_scalar_column`'s shape:
       a contraction of the cached brackets over a declared reach.

- **2026-11-27** (second session) — The runaway guard the Tests item owed is
  a count of structure-factor expansions, not a timer (PR #1865, a
  ghostshift runner). The count landed with angle 1. This session showed
  that it trips when the hoist is undone. A timer could not do that job
  honestly. A budget that trips at the hoist's 2.6× gain is not several times
  the fit's own time, so on a loaded machine it would fail for load alone.
  The count gives the same answer on every machine.
  - *Done:* `tests/test_structural_hoist.py` gains a negative control. With
    the gradients built by the frozen pre-change kernels, one whole
    expansion per atom, the count grows with the free columns: 24 calls
    with 21 columns free, against 8 with one. The existing guard's
    docstring now states the reason and its scope. The counter now also
    replaces `_orbit_terms` in the test module, because the frozen kernels
    call it from there. Before that fix, a probe of the pre-change kernels
    counted none of their calls.
  - *Measured* (this Mac, arm64, Python 3.12, `[dev]` venv, compiled tier
    on; probe `~/.cache/ghostshift/rietx/wp-2314-guard/probe2.py`, outside
    the tree): on `bigcell-structural`'s 40-atom phase, blank pattern, one
    Jacobian over the 120 coordinate columns makes 40 `_orbit_terms` calls
    hoisted and 1 600 with one expansion per atom. It takes 0.105-0.110 s
    hoisted and 0.245-0.247 s per atom, three repeats each. With one
    coordinate column free both make 40 calls in 0.02 s.
  - *Gates:* fast suite on this tree (`[dev]`, darwin arm64, under the
    suite lock, 7 min 9 s): 15 821 passed, 452 skipped, 30 xfailed. Main's
    count was not measured, so the +1 is by construction. The added test
    cost 0.03 s locally (`tests.added_test_times`). The hoist file: 6
    passed. Ruff, `tests.rulebook_limits` and Vale (0 errors) clean;
    `tests.reader_output` exit 0, unchanged against 1aed9c404. The full
    suite did not run: the change is a test and prose, so no measured
    number can move.
  - *Review:* `/code-review high --fix` found no correctness bug. It fixed
    three wording points: the ticked item now says the guard runs on the
    four-atom fixture, it points at the test's docstring, and the docstring
    names the paths the count sees. It left the first entry's stale *Next*
    item 2 alone, since a log entry is history; this entry supersedes it.
  - *Settled by Claude:*
    1. The runaway guard is the `_orbit_terms` count per Jacobian on the
       four-atom fixture, with no wall-clock budget on `bigcell-structural`.
       The alternative was a timed bench fit in the slow tier. Settled by
       Claude under `tests/CLAUDE.md` § Budgets in tests: a budget not
       several times the serial time is a load sensor, and one that trips at
       2.6× cannot be. A runaway in iteration count is bounded one rank
       down, by the library's 400-evaluation stage budget
       (`test_budget_and_tolerance_invariance.py`). The guard's shape is
       copied from `test_one_expansion_serves_every_structural_column`.
  - *Generality:* no heuristic, threshold or default added, so no judge.
  - *Next:*
    1. WP-2317's R0 still gates angles 2-7. Angle 3 is the largest share.
    2. Angle 3 owes its own count guard on a fixture with Biso free. This
       fixture frees no Biso, so a Biso column that went back to a
       whole-phase finite difference would pass the guard above.

- **2026-11-27** — Angle 1, the hoist, landed byte-equal (PR #1862, a
  ghostshift runner). A coordinate or ADP column no longer rebuilds the
  structure factor. One pass over the sites per phase per Jacobian
  evaluation now serves every such column. On the bench fit every Jacobian
  and every refined value is bit for bit what main computes. The fit runs
  2.6-2.7× faster and each Jacobian about 3.3× faster. The 10× target
  needs angle 3: Biso and occupancy finite differences are now three
  quarters of the Jacobian. Angles 2-7 move numbers, so they wait for
  WP-2317's ruling R0.
  - *Done:* `structure_factor.d_f2_d_sites` builds A, B and the brackets of
    every requested atom in one pass, in the single-atom kernels' own
    arithmetic. `d_f2_d_xyz` and `d_f2_d_uaniso` are now that function
    asked for one atom. `CompiledModel.structural_f2_grads` wraps it. The
    Jacobian closure caches it per phase per evaluation, as it does
    `moment_f2_grads`. The atoms to build are read once from the column
    identities with the dispatch's own match, so the cache can hold an extra
    atom but never miss one. `tests/test_structural_hoist.py` keeps the two
    kernels as they stood at 94804b716 verbatim as the oracle. It asserts
    every gradient array and every Jacobian column byte-equal, with
    dispersion on and off. It also asserts that `_orbit_terms` calls per
    evaluation do not grow with the number of structural columns.
  - *Measured* (this Mac, arm64, Python 3.12, `[dev]` venv, compiled tier on,
    rietx 1.13.0.dev0; main at 94804b716 from a `git archive` snapshot on
    `PYTHONPATH`; interleaved under the suite lock; driver
    `2314-probe/drive_bigcell.py` over WP-2317's probe 1: 40 atoms,
    P2₁2₁2₁, 2θ ≤ 90°, `mccusker_structural`):

    | | main | branch |
    |---|---|---|
    | fit wall, unprofiled, 3 runs | 29.7-29.9 s | 11.2-11.3 s |
    | Jacobian, profiled, 83 evaluations | 28.9 s (0.348 s each) | 8.8 s (0.106 s each) |
    | `_orbit_terms` calls per Jacobian, median (max) | 4 920 (6 520) | 160 (1 760) |
    | `_orbit_terms` calls in the Jacobians, whole fit | 274 480 | 65 040 |
    | sha256 over all 83 Jacobians, in order | `65098e4fd0421a7b` | `65098e4fd0421a7b` |
    | digest of the 296 values and esds | `97d0a88be70d00c4` | `97d0a88be70d00c4` |

    Rwp is 0.08674923965532694 on both arms. The stage iteration counts are
    identical. WP-2317's 75.0 s for this fit was on Linux x86_64. That
    number is another machine's and is no "before" here. On the branch,
    `_peak_chain_column` (the Biso, occupancy and cell columns by finite
    difference of `phase_peaks`) takes 6.6 s of the 8.8 s. `_structural_column`
    no longer appears in the profile's top 28 rows.
  - *Gates:* `test_backend_shim.py`'s bit-identity goldens 19 passed.
    The WP's acceptance files plus the dispersion, ADP, coordinate and
    preferred-orientation files: 368 passed, 205 skipped, 2 xfailed. The
    skips are the jax and torch rows, absent in `[dev]`. Fast suite on this tree (main had not moved): 15 819 passed, 452 skipped, 30 xfailed. The five added tests cost 0.11 s locally. Main's count was not measured this session, so the +5 is by construction, not by comparison.
    The full suite did not run. Its rule is a change that could move a
    measured number, and every column is byte-equal by measurement.
  - *Review:* `/code-review high --fix` found no correctness bug. It made two
    changes. The hoist tests now declare the numpy path. A docstring was
    reflowed. It noted a third point and left it: an atom index outside the
    phase now raises `IndexError`, where the old kernels returned an
    all-zero gradient.
  - *Settled by Claude:*
    1. The single-atom kernels became wrappers of the batched function, and
       the pre-change kernels are frozen in the test file as the oracle.
       Keeping them in `src` beside the batched one was the alternative, on
       the `_phase_component_scalar` precedent. Settled by Claude under root
       CLAUDE.md § Conventions ("two things are written once"): that
       precedent stays because the traced backends run it, and these
       kernels are host-side Jacobian support only.
    2. An out-of-range atom index raises rather than returning zeros.
       Settled by Claude under Rule 4 (*A new API*: a call the code cannot
       honour raises before any work). No caller passes one.
  - *Generality:* no heuristic, threshold or default added, so no judge.
  - *Next:*
    1. WP-2317's R0 gates everything left. Angle 3 is the largest share
       (6.6 s of the fit's 8.8 s of Jacobians), then angle 2.
    2. Re-run the driver with angle 1 as the "before" for each angle. Once
       WP-2317 adds the `bigcell-structural` bench case, move to it and add
       the runaway guard the Tests item names.
- **2026-11-27** — Filed from WP-2317's probe. A fresh subagent reviewed the plan
  the same day, and its findings are folded in: the 120× call arithmetic, the
  Ω·∂I block, cross-atom reach, the exact oracles.
  - *Fold-first:* no open WP owns the coordinate/ADP columns' structure-factor
    cost. WP-1945 (🔄) owns the peak-chain columns and one bit-identical
    batched-Biso task. The split is recorded in Context and in WP-1945's
    `### Inherited`.
  - *Next:* angle 1, the hoist, needs no ruling and can start. Measure main
    against the branch, interleaved, first.

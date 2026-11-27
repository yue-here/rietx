# WP-2314 — a structural Jacobian costs one structure factor, not one per column

Milestone: unscheduled · Status: 🔄 2026-11-27 — angle 1 (the hoist) landed byte-equal, its runaway guard settled as a count; angles 2-7 wait for WP-2317's R0
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
- a change of tolerance, stopping rule or method answers to an independent
  measurement where one exists, and otherwise to the established programs' answer
  on the same pattern.

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
- [x] Tests: the byte-equality test for angle 1, and a **runaway guard**
      against the bench case's cost returning, never a timer.
      *(Angle 1's landed: `tests/test_structural_hoist.py`. 2026-11-27: the
      guard is that file's `_orbit_terms` count on its four-atom fixture, not
      a wall-clock budget on `bigcell-structural`; the docstring of
      `test_one_expansion_serves_every_structural_column` says why. A
      negative control now shows the count trips on a per-atom expansion.)*
- [ ] Tests: the oracle tests for angles 3 and 4, landing with each angle.
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

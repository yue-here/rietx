# WP-1945 — the peak-chain columns of a Jacobian built in one pass per phase

Milestone: unscheduled · Status: 🔄 2026-11-16 — task 1 in PR #1603 (memo pins the expansion point); tasks 2-9 open
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1938 soft (it rewrites `decode` and the FD step that tasks 3-5 batch; task 1 needs nothing)
Priority: P3 2026-10-11 — cost only, no user at the wall: 1.27× on trigger and 1.33× on cpd-1a with every column bit-identical, and task 1 is a bit-neutral 3 % on its own; 1938 landed (#883), so tasks 3-5 can start

## Goal

A Jacobian builds its peak-chain columns in one pass per phase over every
column that touches the phase. `CompiledModel.phase_peaks` takes a leading
column axis, and today's one-column call is the K = 1 case of it. Every column
stays bit-identical, so no golden moves, and the trigger and cpd-1a fits get
at least 1.2× faster.

## Context

### The seam

`optimize/least_squares.py::_make_jacobian` builds a Jacobian column by
column. A column whose path `model.scalar_chain_supported` claims goes to
`_peak_chain_column`, which does all of this once per column:

1. θ_c + h (`fd_step`), then one full `table.decode`.
2. For each phase `_affected_phases` names, one `phase_peaks` call at the
   perturbed values.
3. Four `BatchLayout.gather`s (position, w₁, w₂, intensity onto the rows),
   the finite-difference coefficients, `_require_basis`.
4. One `accumulate_planes` scatter, which is the kernel tier's `accum`.

`phase_peaks` (`model/forward.py`) builds its per-reflection blocks through
`_memo`, each keyed on the scalars it reads: `cell` (d and 2θ per line),
`f2` (|F|²), `aniso`, `pos`, `widths`, `lp`, `abs`. Then it assembles the
intensity once per emission line. Which blocks a column rebuilds depends on
its family:

| family | paths | rebuilds |
|---|---|---|
| width | `instrument.profile.{u,v,w,x,y}`, `phases.N.{gauss,lor}_{size,strain}` | `widths` |
| position shift | `instrument.zero_shift`, `instrument.geometry.sample_{displacement,transparency}` | `pos` |
| cell | `phases.N.cell.*` | everything downstream of d |
| Biso | `phases.N.atoms.M.biso` | `f2` |
| line weight | `instrument.source.lines.N.weight` | the intensity only |

### Why the seam costs what it does

WP-1121 § Findings 4 measured the regime. The blocks run over 98-282
reflections a phase, and a `phase_peaks` call in which every memo slot hits
still costs 562 ns per reflection. The cost is numpy dispatch, which neither
fusion nor threading reaches: WP-1115's compiled tier bought 1.03× here
against 2× and 11× on the plane seams. 1121 named the lever ("fewer, larger
numpy calls") and no WP took it. This WP is that lever.

### Measured shares, 2026-10-11

One timer around `_peak_chain_column` and one around the scatter inside it
([shareprobe.py](1945-prototype/shareprobe.py)), two fits a case after a warm
one.

| | trigger | cpd-1a | nac |
|---|---|---|---|
| fit, loaded machine | 6.8-7.2 s | 2.7-2.8 s | 0.62 s |
| peak-chain columns in the fit | 5151 | 3446 | 214 |
| their work, scatter excluded | 36.3-36.6 % | 39.6-40.0 % | 12.2 % |
| their scatter | 0.17-0.18 s | 0.06-0.07 s | 0.006 s |

The whole-fit seam split (`examples/bench_compiled_kernel.py --seams`) put
the perturbed `phase_peaks` alone at 27-28 % of trigger, 29 % of cpd-1a and
10 % of nac.

### The prototype, 2026-10-11

[batchprobe.py](1945-prototype/batchprobe.py) runs inside a real fit. At every
10th Jacobian (every 2nd on nac) it replays the fit's own peak-chain columns
two ways, interleaved three times, best of three each:

- **A, shipped**: `_peak_chain_column` once per column, the memo primed at
  the expansion point as `derivative_bases` leaves it.
- **B, batched**: one decode for every column (`table._C @ P + d`, the same
  CSR product `decode` makes, with one perturbed entry per column), then per
  phase one block build over a leading column axis for the width,
  position-shift and cell families. The cell family's |F|² is
  `structure_factors_squared` over hkl tiled K times. Every other family takes
  A's per-column call.

The scatter stays one kernel call per column in both arms and is excluded
from both times.

| | trigger | cpd-1a | nac |
|---|---|---|---|
| Jacobians sampled | 17 of 183 | 22 of 222 | 15 of 36 |
| columns compared | 514 | 356 | 110 |
| A → B | 0.233 → 0.099 s | 0.110 → 0.041 s | 0.031 → 0.028 s |
| ratio | **2.36×** (twice) | **2.67×** | 1.12× |
| largest \|A − B\| / max\|A\| | 0 | 0 | 0 |
| fit speedup, 1 / (1 − s·(1 − 1/r)) | **1.27×** | **1.33×** | 1.01× |
| ceiling if the column work were free | 1.57× | 1.66× | 1.14× |

By family on trigger:

| family | columns | A | B | ratio |
|---|---|---|---|---|
| width | 279 | 0.113 s | 0.025 s | 4.6× |
| position shift | 34 | 0.024 s | 0.005 s | 4.5× |
| cell | 160 | 0.080 s | 0.048 s | 1.7× |
| Biso and line weight, per column in both | 41 | 0.017 s | 0.018 s | — |

Four things the numbers say:

- **Every column was bit-identical**, 980 of 980, the cell family included,
  although its d comes from `einsum("ni,kij,nj->kn")` where `d_spacings`
  uses `einsum("ni,ij,nj->n")`. The builders already broadcast over a leading
  axis (`_width_block`, `_position_shift_deg`, `two_theta_deg`,
  `lorentz_polarization`, `structure_factors_squared` on tiled hkl), which is
  why the prototype is about 150 lines over them.
- **Half the batched cell time is |F|²** (0.025 of 0.048 s), and the
  prototype recomputes the orbit sums once per column. They do not depend on
  the cell. Sharing them across a batch would take trigger's columns from
  2.36× toward 3.2× (an estimate: the |F|² share set to zero).
- **A batch of one loses.** nac's cubic cell gives one column per group, and
  batching it cost 2× (0.005 → 0.010 s). Its unbatched columns, Biso among
  them, are 42 % of its column work.
- **The prototype refused**, and fell back per column on, every phase
  carrying preferred orientation, extinction, a magnetic split or a nuclear
  mask, or Le Bail or Pawley mode, every cell column whose `affected` is not
  its own phase, and any table with derived rows. Two things it did not
  handle at all: it skips surface roughness in the cell family's intensity,
  and it passes the expansion point's `aniso` to a cell column, which is
  wrong for a Stephens phase (Λ depends on d). The cell columns'
  bit-identity on all three cases says none of them carries either.

### The scalar memo never looks past two entries

`_memo`'s lookup compares `held[0]` and `held[1]` and nothing else, whatever
`_MEMO_DEPTH` is. Both the lookup and the docstring's claim that "depth 8 was
measured to build exactly the same 35 596 blocks as depth 2" landed in one
commit (08f09ad4, WP-1121). Under that lookup the measurement could not have
come out any other way.

It costs real rebuilds. A phase with two or more cell columns pushes the
expansion point out of a two-deep slot, so the next column of that phase
rebuilds every block at the expansion point. [missprobe.py](1945-prototype/missprobe.py)
prints it on trigger: at `phases.1.lor_size`, after `cell.a` and `cell.c`, the
slot holds the two perturbed cells and no third entry. Counted with
[colprobe.py](1945-prototype/colprobe.py):

| trigger, in the columns | shipped (depth 2) | lookup scans, depth 4 | lookup scans, depth 8 |
|---|---|---|---|
| `lor_size` columns rebuilding cell and \|F\|² | 402 of 536 | 134 | 0 |
| `zero_shift` phase calls rebuilding widths | 557 of 676 | 503 | 119 |
| block-build seconds, all columns | 1.438 | 1.296 | 1.239 |

On cpd-1a the column block builds go 0.520 → 0.441 s at depth 8. That is
about 3 % of each fit. It is bit-neutral by the memo's own rule: a hit returns
the array a rebuild would build. Depth 4 still misses on trigger's
monoclinic phase, which has four cell columns, and still rebuilds widths in
503 `zero_shift` phase calls. So any depth is a tuning constant again, and
pinning the expansion point's entry would not be one. The batched path removes these
rebuilds from the columns it covers, so its 2.36× and this 3 % overlap.

### Design rules, decided at filing

1. **One authority.** `phase_peaks` gains the column axis, and the
   one-column call becomes K = 1 of it. A separate batched twin would be a
   second builder of the per-reflection chain, the miss the root CLAUDE.md
   names after WP-1103, and every later correction would have to land twice.
2. **Bit-identity per family is the bar.** Goldens do not move. The cell
   family's `einsum` is held to `d_spacings` by test, as is the batched
   decode to K decodes. Both agreed on every column measured, and nothing
   here shows why, so a test is what holds them.
3. **A group of one column takes the plain path.**
4. **Numpy only.** jax and torch build their Jacobians by autodiff
   (`_jacobian_for`) and never reach `_peak_chain_column`. `phase_peaks` is
   still traced code there, so its behaviour without a column axis does not
   change, and `tests/test_cross_backend.py` and the backend conformance
   suite stay green.
5. **Expansion-point blocks come from the memo, perturbed blocks never enter
   it.** A (K, n) block keyed on K perturbed vectors is the leak `_memo`'s
   docstring warns about, and its keys must stay plain floats.
6. **Every refused correction is covered or routed per column** by a named
   predicate, each with its own bit-identity case: the refusals and the two
   omissions in the prototype section above, plus wavelength columns
   (`cell_key` carries λ).
7. **The scatter stays one kernel call per column.** A two-dimensional `accum`
   is kernel work, owned by [1940](1940-the-kernel-tier-in-a-wheel.md)'s
   crate: 0.17 s of trigger.
8. **The invariants hold by construction**: no hkl list, window or node count
   changes (frozen-per-stage discreteness), and each column keeps its
   `_affected_phases` and `_require_basis` checks (an analytic branch claims
   what one name reaches).

### WP-1938 lands first

[1938](1938-every-parameter-refined-in-its-own-units.md) (PR #883) refines
in physical units, so `decode` loses its softplus and logit steps and the
default driver becomes LM. The batched decode follows whichever `decode` is
on main. 1938 also moves evaluation counts (1292 → 1065 residual evaluations
over twelve acceptance fits), so the shares above are re-measured after it
merges and before task 4. Task 1 touches neither file's hot path and can go
first.

### Inherited

- **2026-11-28, from WP-2314 angle 3: Biso and occupancy have left the peak
  chain.** In Rietveld mode a Biso or occupancy column is now analytic, built
  from the structure-factor cache (`least_squares._site_scalar_column`), when
  every path it moves is a Biso or occupancy row of one phase. So the "Biso
  columns batched" half of this WP's open |F|² task has no Biso column left
  to batch, except one whose tie reaches something else (a cell, a
  coordinate, a derived row) or a phase carrying a moment. Those still take
  the peak chain. The cell half of the task is unchanged. Re-scope that task
  before starting it.
- **2026-11-27, from WP-2314 (filed under WP-2317): the structural columns'
  structure factor has an owner now.**
  - On a 40-atom phase, `_structural_column` rebuilds A once per coordinate
    column, n_asym `_orbit_terms` per column. Each Biso/occupancy column this
    WP's FD chain builds pays a whole-phase |F|². WP-2317 probe 1 puts every
    `_peak_chain_column` (Biso, occupancy, cell and the rest alike) at 16.2 s of
    a 72 s Jacobian, against 53.5 s for the coordinate columns.
  - WP-2314 owns the per-evaluation structure-factor cache, an analytic or
    incremental Biso/occupancy branch, and everything that reassociates. This
    WP's task "|F|² orbit sums shared across a batch's cell columns, and Biso
    columns batched" keeps the bit-identical batch inside the one-pass design.
  - Read WP-2314's Tasks before starting that task: if its cache lands first,
    the batch may read the cache instead of building its own.

## Non-goals

- A compiled per-reflection chain. 1121 § Findings 6 declined it: it would
  recompile physics that has one authority today.
- The two-dimensional scatter (design rule 7).
- [1122](1122-compiled-peaks-buffer.md)'s element-volume lever, deferred to
  FPA.
- Any change that moves a column's bits. A faster |F|² that reassociates (a
  rank-one Biso update, say) is a different WP with a re-pin.

## Tasks

- [x] The memo looks up every entry it holds, and the expansion point stops
      being evictable by a run of columns: a pinned entry, or a depth with the
      measurement that sizes it. Correct `_memo`'s docstring (the depth-8
      claim, and the "earlier Jacobian" reading of the gap to an unbounded
      cache). Extend `tests/test_scalar_memo.py` with a phase of two cell
      columns that must hit at the expansion point. Bit-neutral, asserted as
      1121 asserted it: nfev, njev and Rwp unchanged on the four bench cases.
- [ ] The A/B harness lands as `examples/bench_batched_columns.py` from
      `1945-prototype/batchprobe.py`, its arm B calling the package once
      task 4 lands.
- [ ] One decode for every column of a Jacobian: one CSR product, bit-equal
      to K decodes, on whichever `decode` 1938 left.
- [ ] `phase_peaks` takes a column axis, width and position-shift families
      first; K = 1 is today's call, a group of one takes it.
- [ ] The cell family: d over a batch of reciprocal metrics, 2θ, positions,
      widths, |F|² on tiled hkl, Lp, absorption and the intensity assembly.
- [ ] Each refused correction covered or routed per column (design rule 6).
- [ ] Measured first, kept only if bit-identical: |F|² orbit sums shared
      across a batch's cell columns, and Biso columns batched.
- [ ] Tests: `tests/test_batched_columns.py`, every family's batched column
      equal to the per-column one bit for bit on the trigger, cpd-1a and nac
      fixtures, plus one phase per refused correction. No golden is touched.
- [ ] Delete `1945-prototype/` once the bench replaces it, and point this
      file's Context at the bench.
- [ ] Skill: none. No number an agent reads moves.

## Acceptance

Bit-identity, gated:

```sh
.venv/bin/python -m pytest tests/test_batched_columns.py tests/test_scalar_memo.py tests/test_cross_backend.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Speed, reported and never gated (root CLAUDE.md: wall clock is a range):

```sh
.venv/bin/python examples/bench_batched_columns.py "$PWD" trigger 10
.venv/bin/python examples/bench_batched_columns.py "$PWD" cpd-1a 10
.venv/bin/python examples/bench_refinement.py --cases trigger,cpd-1a,nac --repeats 5
```

The column work at least 2× faster on trigger and cpd-1a. Run back to back
with main's tree, trigger and cpd-1a at least 1.2× faster, and nac inside
main's own range.

## References

- [1121](1121-per-reflection-cost.md) § Findings 4-6: the dispatch-bound
  regime, the lever, and the memo this WP corrects.
- [1115](1115-compiled-kernel-spike.md): the compiled tier, 1.03× on this
  seam.
- [1940](1940-the-kernel-tier-in-a-wheel.md): the kernels, and the scatter.
- [1938](1938-every-parameter-refined-in-its-own-units.md): `decode` in
  physical units.

## Handover log

### 2026-11-16 — task 1: the memo pins the expansion point (PR #1603)

The scalar memo now keeps the point a Jacobian expands around, so a run of
columns can no longer push it out. The lookup also checks every key it holds,
not just the newest two. Nothing a fit returns moved, to the bit, on the four
bench cases. The memo builds 15-18 % fewer blocks on cpd-1a, cpd-2 and
trigger. On trigger, the 129 `lor_size` columns that rebuilt the cell block
and |F|² at the expansion point now rebuild none of it. This is a cost-only
change: the fit's wall clock stayed inside its run-to-run range, and no
speedup is claimed. Task 1 ran in its own PR, as the filing session asked.
Tasks 2-9 are untouched.

*Done.* Three changes in `model/forward.py`:

- **A pin per slot.** Each memo slot is a `_MemoSlot`: a `pin` plus a
  `recent` trail, still capped at `_MEMO_DEPTH = 2`.
- **`derivative_bases` sets the pin.** It runs its `phase_peaks` calls under
  `_pinning_expansion_point()`, a private `ContextVar` scope. The entry each
  lookup returns there becomes the pin. Only the next expansion point replaces
  it. If that entry is already on the trail, which is the case for an accepted
  step, it moves to the pin without a rebuild.
- **The lookup scans the whole trail,** most recent first.

The `_memo` docstring is rewritten: the depth-8 claim is gone, and the
"earlier Jacobian" reading of the gap to an unbounded cache is corrected. Four
tests in `tests/test_scalar_memo.py` replace "a third state evicts":

- two cell columns cannot evict the expansion point (its builders are
  counted, and positions are checked by object identity);
- the next expansion point takes the pin;
- the lookup finds the fourth key of four;
- the trail is bounded.

Positive arm: with `_pinning_expansion_point` swapped for a `nullcontext`,
the two pin tests fail. A read-only review subagent found no bug. Its one code
nit, an unused `_MemoSlot.__len__`, is removed (baa7d8e9f). It noted that
`test_the_memo_is_allocated_and_actually_used` depends on running first in
its module. That predates this change, it is safe under loadgroup today, and
I left it.

*Measured.* The replay script is
[replay.py](1945-prototype/replay.py), committed with the review fix-ups on
2026-11-16. Rerun then on nac, it reproduced this branch's record field for
field (1752 builds). The logs are in the runner's scratch, not the repo. The
replay used `examples/bench_refinement.py`'s setups for nac,
cpd-1a, cpd-2 and trigger, with counters wrapped around `_make_residual` and
`_make_jacobian`. Main bc77a934e and this branch were run on the worktree's
`[dev]` venv, darwin/arm64, python 3.12, in place.

- **Bit-identity:** Rwp, status, residual and Jacobian evaluation counts,
  each stage's `n_iterations` and every refined value (as `float.hex`) are
  identical between main and the branch, at a trail depth of 1, 2 and 8.
  The counts are 53/48, 188/172, 284/258 and 90/82.
- **Block builds:**

  | case | main | branch |
  |---|---|---|
  | nac | 1818 | 1752 |
  | cpd-1a | 12042 | 10082 |
  | cpd-2 | 28040 | 23117 |
  | trigger | 11428 | 9724 |

  On trigger, depth 1, 2 and 8 build 9732, 9724 and 9631 blocks, so the
  trail stays at 2.
- **`colprobe.py` on trigger,** two runs per arm: `lor_size` columns
  rebuilding the cell block go from 129 of 172 to 0, and `zero_shift` width
  rebuilds from 183 to 0. Block-build seconds inside the columns:

  | case | main | branch |
  |---|---|---|
  | trigger | 0.386 s | 0.306-0.334 s |
  | cpd-1a | 0.197-0.223 s | 0.158-0.168 s |

- **Gates:**
  - ruff is clean;
  - `tests/test_scalar_memo.py` has 12 tests, 3 net new (4 written, 1
    of them replacing an old test);
  - workstation canary (`-n 4`, Linux x86_64, venv `rietx-py312`, tree 7ce7646cc):
    276 passed, 117 skipped, 4 xfailed;
  - workstation fast suite (`-m "not slow" -n 8 --dist loadgroup`, tree baa7d8e9f;
    origin/main had not moved, so this is the merged tree): 14853 passed, 280 skipped, 32 xfailed, 0 failed in 374 s (6.0 GB, 714 % on 8 cores). Main bc77a934e reads 14850 passed / 280 skipped / 32 xfailed in the other runs logged on that tree today, so passed+skipped moved by +3, exactly the net new tests. The four new tests cost 0.01 s together (`tests.added_test_times` on this run's junit);
  - `tests.reader_output` exits 0, unchanged.
- **Generality:** not triggered. `_audit.py` is untouched, and `_MEMO_DEPTH`'s
  row keeps its value and its tier ("invariant", since a hit is bit-equal).
  A pin adds no heuristic.

*Gotchas.*

- `1945-prototype/missprobe.py` reads a slot as a list and no longer runs
  against the new `_MemoSlot`.
- `colprobe.py` and `batchprobe.py` do not read slots directly. `colprobe.py`
  ran for the numbers above.
- Task 9 deletes the directory.

*Next.* Task 2, the A/B harness as `examples/bench_batched_columns.py`.
Before it, re-measure § Context's shares on main. Since 1938 the evaluation
counts are far lower: trigger's cold fit builds 82 Jacobians here, against
183 at filing. This task also removed the
expansion-point rebuilds that part of the prototype's 2.36× was recovering.
Then take tasks 3-8 in order.

### 2026-10-11 — filed from a sizing session

A session sized every speed lever left outside the kernels. This one is the
largest that nobody owns. On trigger and cpd-1a a third of the fit goes to
rebuilding per-reflection scalars once per Jacobian column, at a cost set by
numpy call overhead. A prototype built them once per phase across all of a
Jacobian's columns and reproduced every column bit for bit at 2.4-2.7×,
which projects to 1.27× and 1.33× on the two fits. The same session found
that the scalar memo has never compared more than two entries, so the
measurement its docstring cites for its depth could not have shown a
difference. Fixing that alone recovers about 3 % and moves no number.

*Why a new WP.* No open WP owns the column loop.
[1122](1122-compiled-peaks-buffer.md) is 🛑 and attacks element volume.
[1938](1938-every-parameter-refined-in-its-own-units.md) rewrites `decode`
and the driver, not the loop. [1940](1940-the-kernel-tier-in-a-wheel.md)
owns the kernels and the scatter. The memo fix shares this seam and fixture,
so it is task 1 here and not a WP of its own.

*Measured.* Every number in § Context. The worktree's `[dev]` venv,
darwin/arm64 (Apple M4), python 3.12.14, numpy 2.5.4, scipy 1.18.1,
rietx-kernels 1.2.0, `src` at b7df6a10. Another session's test suite loaded
the machine through most runs (load average 5-61), so the absolute seconds
are high. The ratios come from arms interleaved in one process, and the
trigger ratio held at 2.36× across two runs. The probes are in
`1945-prototype/`, each run from the repo root as
`.venv/bin/python docs/wp/1945-prototype/<probe>.py "$PWD" <case>`.
`colprobe.py` takes `MEMO_DEPTH=` and `MEMO_SCAN=1` from the environment.

*Next.* Task 1 on its own PR, since it needs nothing. Then wait for 1938 to
merge, re-measure the shares, and take tasks 2-8 in order.

# WP-2316 — a Le Bail partition costs what its overlaps need, not ten thousand Python cycles

Milestone: unscheduled · Status: ⬜
Track: A large cell
Depends on: 2313 soft (its `bigcell-lebail` case and rulings R1-R3)
Priority: P2 2026-11-27 — a user at the wall: Le Bail is the slowest mode on a large cell (150 s at 899 reflections, 364 s at 1 601, 96-97 % of it in the partition), slower than Pawley by 4-6×, the reverse of what practice tells a user to expect

A Le Bail partition cycle runs in compiled code at a cost of a few sparse
products, and a partition spends cycles only on the reflections still moving.
On the 1 601-reflection bench case a Le Bail fit runs at least 10× faster (target;
measure before claiming), with every Le Bail acceptance number within its
reference tolerance. How far the tolerance itself may move is the maintainer's,
put as WP-2313's R2.

## Context

**The measurement** (WP-2313 probe 1; Linux x86_64, 4 cores, `[dev]`, compiled
tier on, under cProfile; 12 × 36 × 4 Å, P2₁2₁2₁, Cu Kα doublet + FCJ,
`mccusker_default`, `mode="lebail"`):

| | 899 reflections | 1 601 reflections |
|---|---|---|
| fit wall | 150.0 s | 364.2 s |
| `lebail_update` (10 calls: two per stage) | 146.3 s | 357.9 s |
| → `_settled_partition` → `cycle` | 79 320 cycles, 143.1 s | 90 689 cycles, 352.5 s |
| per cycle | 1.80 ms | 3.89 ms |
| → `np.add.at` | 25.4 s | 59.4 s |
| → `np.add.reduceat` / `logical_or.reduceat` | 8.5 s | 19.9 s |
| → `np.zeros_like` | 7.0 s | 16.6 s |
| → `cycle` own time (array arithmetic, Python) | 99.3 s | 252.5 s |
| the least-squares solves | 2.4 s | 4.4 s |

About 8 000-9 000 cycles per update, even with SQUAREM acceleration. On these
numbers rietx's Le Bail is the slowest structure-free route on a large cell.

**The code.** `CompiledModel.lebail_update` (`src/rietx/model/forward.py:3702`)
builds per-(phase, line) terms once (`_partition_terms`), then each `cycle`
does the following:
- builds y_bragg by `np.add.at(y_bragg, line.channel, curve)` per line;
- forms each reflection's share `curve / y_bragg[channel] · net[channel]`;
- reduces it per reflection with `np.add.reduceat`;
- normalises by the reflection's mass;
- floors at `LEBAIL_INTENSITY_FLOOR` = 1e-10;
- returns the moved share Σ A_k|ΔI_k| / Σ A_k I_k and the Poisson likelihood
  (a log over every live channel).

`_settled_partition` (`:770`) wraps it in SQUAREM S3 (Varadhan & Roland 2008)
with a bounded steplength and stops at `Stage.lebail_tol` = 1e-7 under
`Stage.lebail_cycles` = 25 000 (`src/rietx/schemas/plan.py:220-223`,
`src/rietx/strategy/staged.py:145-149`). The step is Richardson-Lucy, an EM
step on a Poisson likelihood, which slows to a linear rate where reflections
overlap. That is why the count is high on a dense pattern.

**The rulings this touches** (WP-2313's R1-R3, restated):
- `lebail_tol` = 1e-7 was settled under the maintainer's delegation on 2026-11-05
  (WP-1542), against `tests/test_window_domain.py` bar 1: max|Δy|/σ ≤ 0.1 at
  fixed parameters against a 1e-10 reference. 1e-7 was "the largest decade under
  the bar on all seven from flat". FAP fails it warm at 1.23, and LaMnO₃ needs
  12 293 cycles.
- Practice (`docs/practice.md` § Structure-free fitting): GSAS-II, FullProf,
  TOPAS and RIETAN-FP extract **once per least-squares cycle** and let the
  intensities converge across the refinement. rietx holds the model frozen
  through a solve, so one partition must carry what their cycles carry. That
  is a *design* consequence of frozen-per-stage solves, and it is R2's real
  subject.
- DESIGN-RULES Rule 5: "A change to Le Bail that moves every fit's numbers waits
  for WP-2062 (ruled 2026-11-05, #1434)". This is R3. Angles 1-2 below are
  bit-identical and so clear R3 as written. Every later angle moves last bits
  and needs R3's reach answered.

**Angles, ordered by the ruling each needs:**
1. **Hygiene, bit-identical** (no ruling). Preallocate the per-cycle arrays
   (`zeros_like` alone is 7-17 s). Compute the Poisson likelihood only on the
   cycles SQUAREM reads it (the landing test), not every cycle. Hoist the
   per-line `owner`/`weight` gathers that do not change between cycles.
2. **A compiled cycle in today's association order** (no ruling). `np.add.at`
   accumulates sequentially in index order and `reduceat` sums each segment in
   order, so a serial Rust loop over the same index arrays reproduces both bit
   for bit. That meets `compiled.py`'s rule 3 ("associations as written") and
   its four rules: GIL released, numpy fallback exercised, one path per process,
   a bound stated where a transcendental enters (only the likelihood's `log`).
   This is the bulk of the per-cycle cost, and the angle with the least risk.
3. **Sparse products** (R1/R3; last bits move). Ω as one CSR matrix per
   partition (channels × reflections, line weights folded in): y_bragg = Ω·I,
   num = (Ωᵀ(net ⊘ y_bragg)) ⊙ I. Two SpMVs a cycle, at BLAS-like speed with no
   new kernel. If angle 2 lands, this is mainly a cross-check.
4. **Settle per overlap cluster** (R3; the stopping path changes, the fixed
   point does not). Reflections whose windows share no channel are independent
   problems. Decompose into connected components once per partition, and let
   each component stop at its own tolerance. An isolated reflection converges
   in one cycle, so the 8 000-cycle tail is spent only on the few clusters that
   need it, each a small problem. The global stop rule becomes the max over
   components, which is no looser than today's.
5. **A better accelerator** (R3). Anderson acceleration or SQUAREM's other
   schemes, measured in cycles to 1e-7 on the seven patterns of WP-1542's
   table plus the bench case.
6. **The tolerance** (R2). Measure what 1e-6 and 1e-5 cost against the
   established programs' own answers on the same patterns, not against a 1e-10
   reference. That is WP-2313's bar: on par with the other codes, not converged
   past them.
7. **Partition inside the solve, as every other program does** (R2, a design
   change). One partition per LM iteration, the model no longer frozen through
   a solve as far as the intensities go. Weigh this against the frozen-per-stage
   invariant (the intensities are not θ, so the hkl list, windows and FCJ nodes
   stay frozen, but the residual changes under the solver between iterations,
   and LM's acceptance test must allow for it). It is the largest change and
   the one practice supports. A maintainer decision.
8. **Or route large cells to Pawley** (WP-2062's question): on this case
   Pawley is already 4-6× faster, and WP-2315 makes it faster still.

**Related evidence.** Issue #1733 (the Le Bail wander test at 5 586-8 230 s in
the nightly) was folded into WP-2036, which fixed the test's setting, not the
partition's cost. Its `test_lebail_alternation.py` row is a natural second
timing case.

## Non-goals

- Which structure-free method is the default: WP-2062. Angle 8 is noted for it,
  not taken here.
- Le Bail's stopping across passes (`LEBAIL_CONVERGED_REL`, WP-1323): only the
  partition inside one update is in scope.
- The Pawley seed's fixed cycle count (`PAWLEY_SEED_CYCLES`) beyond what the
  faster cycle gives it for free.

## Tasks

- [ ] Re-measure `bigcell-lebail` (WP-2313) unprofiled, best of three. Record
      the cycles per update, first against second update of each stage.
- [ ] Angle 1, bit-identical: assert every partition's intensities byte-equal
      before and after on the bench case and the Le Bail goldens.
- [ ] Angle 2, the compiled cycle: same byte-equality assertion against the
      numpy cycle (the oracle), run with `RIETX_COMPILED=0` and `=1` both.
- [ ] Re-measure. Then put angles 4-7 to the maintainer (WP-2313 task 3) with the
      remaining share and each angle's measured cycle saving on WP-1542's seven
      patterns.
- [ ] The angles the maintainer rules in, each with its numbers checked against
      the reference values under WP-2313's bar.
- [ ] Tests: `test_lebail_cycles.py`, `test_window_domain.py`'s bar 1,
      `test_lebail_alternation.py`; a runaway guard on the bench case's cycle
      count.
- [ ] Skill: none for angles 1-5 (no API change). If angle 6 or 7 moves the
      default, the help entry for `lebail_tol` changes with it (`help.py`).

## Acceptance

`bigcell-lebail` at 1 601 reflections ≥ 10× faster than WP-2313's unprofiled
"before" (target; the measured factor is what is recorded). Angles 1-2
bit-identical on every Le Bail golden. Any later angle's moved numbers sit within
their reference tolerance under WP-2313's bar.

```sh
.venv/bin/python examples/bench_refinement.py --cases bigcell-lebail
.venv/bin/python -m pytest tests/test_lebail_cycles.py tests/test_window_domain.py tests/test_compiled_kernels.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Le Bail, A., Duroy, H. & Fourquet, J. L. (1988). *Mater. Res. Bull.* 23,
  447-452.
- Richardson, W. H. (1972). *J. Opt. Soc. Am.* 62, 55-59; Lucy, L. B. (1974).
  *Astron. J.* 79, 745-754 (the partition as an EM step; cited by
  `_settled_partition`).
- Varadhan, R. & Roland, C. (2008). *Scand. J. Stat.* 35, 335-353 (SQUAREM).
- Walker, H. F. & Ni, P. (2011). *SIAM J. Numer. Anal.* 49, 1715-1735
  (Anderson acceleration, angle 5).

## Handover log

- **2026-11-27** — created.

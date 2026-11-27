# WP-2316 — a Le Bail partition costs what its overlaps need, not thousands of cycles

Milestone: unscheduled · Status: 🔄 2026-11-27 — task 1 answered: the Rwp gap is a valley entered through an unseeded background, not the partition; the rest waits on WP-2317's R2-R3
Track: A large cell
Depends on: 2317 soft (its `bigcell-lebail` case and rulings R0, R2, R3); 2017 soft (group Q owns `lebail_tol`'s number); 2062 soft (Rule 5's Le Bail fence)
Priority: P2 2026-11-27 — provisional: the track the maintainer opened for a user at the wall, on the slowest mode measured (95-97 % of a large-cell Le Bail fit in the partition; the threefold Rwp was the probe's unseeded background, task 1); what may start without a ruling is narrow (R3), so re-rate when WP-2317 task 3 answers R2-R3

## Goal

A large-cell Le Bail fit costs no more than its overlaps need, through a cheaper
partition cycle and fewer cycles. On `bigcell-lebail` at 2θ ≤ 120° the fit runs at
least 10× faster (target). Every moved number satisfies WP-2317's ruling R0, and
the maintainer has ruled, under R2-R3, how far the partition's method and
tolerance may move. If the answer is "route a large cell to Pawley" (R3,
WP-2062), this WP closes on that.

## Context

**The bar** (WP-2317, restated because it is load-bearing): the maintainer asked on
2026-11-27 for "accuracy on par with other codes … speed as fast as possible by any
means". Under ruling R0's working reading:
- a rounding-only change may move converged numbers within |Δ| ≤ 1e-3 esd and
  Rwp 1e-7 relative, re-pinned in the same change;
- a change of tolerance, stopping rule or method waits for its ruling.

**Rule 5's fence, in full** (DESIGN-RULES, ruled 2026-11-05, #1434): "Pawley is
the structure-free method rietx leads with. WP-2062 carries the move to it as the
default. Le Bail gets only what a ruling already asked of it, in its smallest
correct form. A change to Le Bail that moves every fit's numbers waits for
WP-2062."
- The third sentence fences even a bit-identical Le Bail kernel unless a ruling
  asks for it, and the first argues for angle 9 (route to Pawley) over a Le Bail
  speed project.
- So **no angle here starts before WP-2317 task 3 has put R3 to the maintainer.**
  The question is whether a user at the wall on Le Bail is the ruling that asks.

**The measurement** (WP-2317 probe 1; Linux x86_64, 4 cores, `[dev]`, compiled
tier on; 12 × 36 × 4 Å, P2₁2₁2₁, Cu Kα doublet + FCJ, `mccusker_default`,
`mode="lebail"`). Unprofiled walls, one run each, atoms ≥ 1.5 Å apart:

| | wall | Rwp | Pawley on the same data |
|---|---|---|---|
| 899 reflections | 154.9 s | **0.1512** | 23.7 s, 0.0447 |
| 1 601 reflections | 351.8 s | **0.1449** | 125.4 s, 0.0420 |

**Le Bail lands at three times Pawley's Rwp.** Before any speed work, task 1 asks
whether this is a wrong valley, the background protocol (WP-1542's subject), or
the partition. A fit made faster at the wrong answer gains nothing.

*Superseded in part, 2026-11-27 (task 1).* The gap is a wrong valley, and the
probe's background protocol put the fit there. Probe 1 starts every Chebyshev
coefficient at 0, the case SKILL.md §2 rule 5 warns about. The first partition
hands the 900-count pedestal to the reflections, and the stages that follow
widen the profile to carry it. With the background seeded as the skill says,
Le Bail lands at Rwp 0.047 against Pawley's 0.044. The partition is not the
cause: settled at Pawley's parameters it gives 0.0455. So the table's walls
are of a fit at the wrong answer. The handover entry of 2026-11-27 (task 1)
has every number. **Every Le Bail run here, seeded or not, ends its last
partition at the 25 000-cycle cap**, so the speed question stands.

The split comes from the first probe (atoms in a sub-box, profiled; 150.0 s and
364.2 s):

| | 899 reflections | 1 601 reflections |
|---|---|---|
| `lebail_update` (10 calls: two per stage) | 146.3 s | 357.9 s |
| → `_settled_partition` → `cycle` | 79 320 cycles, 143.1 s | 90 689 cycles, 352.5 s |
| per cycle | 1.80 ms | 3.89 ms |
| → `np.add.at` | 25.4 s | 59.4 s |
| → `np.add.reduceat` / `logical_or.reduceat` | 8.5 s | 19.9 s |
| → `np.zeros_like` | 7.0 s | 16.6 s |
| → `cycle` own time (array arithmetic) | 99.3 s | 252.5 s |
| the least-squares solves | 2.4 s | 4.4 s |

That is about 8 000-9 000 cycles per update, even with SQUAREM acceleration.

**The code.** `CompiledModel.lebail_update` (`src/rietx/model/forward.py:3702`)
builds per-(phase, line) terms once (`_partition_terms`), then each `cycle`
(`:3781`) does the following:
- builds y_bragg by `np.add.at(y_bragg, line.channel, curve)` per line;
- forms each reflection's share `curve / y_bragg[channel] · net[channel]`;
- reduces the shares per reflection by `np.add.reduceat` (the `tol=0` path, the
  Pawley seed, by per-span `.sum()`);
- normalises by mass and floors at `LEBAIL_INTENSITY_FLOOR` = 1e-10;
- returns the moved share Σ A_k|ΔI_k| / Σ A_k I_k and the Poisson likelihood.

`_settled_partition` (`:770`) wraps it in SQUAREM S3 (Varadhan & Roland 2008),
with a bounded steplength and a likelihood landing test
(`reached >= start`, `:812-821`). It stops at `Stage.lebail_tol` = 1e-7 under
`Stage.lebail_cycles` = 25 000 (`src/rietx/schemas/plan.py:220-223`). The step
is Richardson-Lucy, an EM step on a Poisson likelihood, which slows to a linear
rate where reflections overlap.

**Arithmetic facts that bound the angles** (WP-2317 review, checked 2026-11-27,
numpy 2.5.5):
- `np.add.at` accumulates sequentially in index order: a serial loop reproduces
  it bit for bit.
- `np.add.reduceat` does **not**. Each segment is `a[s] + a[s+1:e].sum()`, the
  first element plus numpy's pairwise sum (426 of 500 random segments differed
  from a sequential loop). The same holds for every `.sum()` in the cycle
  (`held`, `share`, the likelihood).
- A compiled `log` is not numpy's `log`. The likelihood decides SQUAREM's landing
  test, so a 1-ulp change can flip a landing and change the path.
- Each cycle is ~20 vectorised numpy calls over ~223 000 window points at
  2θ ≤ 90°. It is memory-bound, not Python-bound, so a fused kernel likely buys a
  few ×. **10× needs fewer cycles**, and fewer cycles need a ruling.

**The tolerance and its owners.**
- `lebail_tol` = 1e-7 was settled under the maintainer's delegation on 2026-11-05
  (WP-1542), against `tests/test_window_domain.py` bar 1 (max|Δy|/σ ≤ 0.1 at fixed
  parameters, against a 1e-10 reference). 1e-7 was "the largest decade under the
  bar on all seven from flat". FAP fails it warm at 1.23. LaMnO₃ needs 12 293
  cycles from flat (8 495 in-fit).
- Practice (`docs/practice.md` § Structure-free fitting): GSAS-II, FullProf, TOPAS
  and RIETAN-FP extract **once per least-squares cycle**. rietx holds the model
  frozen through a solve, so one partition carries what their cycles carry.
- **WP-2017's group Q owns `StageSpec:lebail_tol`'s number** (on LaB₆ + cBN,
  `fap`, `cpd1a`). Any tolerance angle here is measured with group Q, not past it.
- WP-2062's `### Inherited` holds WP-1542's re-partition question.

**Angles, ordered by what each needs:**
1. **Hygiene** (kind (a); bit-identical where stated).
   - Preallocate the per-cycle arrays: `zeros_like` is 7-17 s of the profiled fits.
   - Hoist `weight[owner]` (only that gather; folding it into `omega`
     reassociates).
   - The likelihood is unused on one cycle in three (the `twice` cycle), so
     skipping it there saves at most a third of the `log` cost.
2. **A compiled cycle** (kind (a), not bit-identical). Two choices:
   - transcribe numpy's pairwise sum into the kernel and pin it with a test
     against numpy (an internal, not a contract), leaving `log` and the scalar
     sums in numpy;
   - accept R0 (a)'s bound.

   It may need a new kernel under `compiled.py`'s four rules.
3. **Sparse products** (kind (a)). Ω as one CSR per partition:
   y_bragg = Ω·I, num = (Ωᵀ(net ⊘ y_bragg)) ⊙ I. Two SpMVs a cycle with no new
   kernel. A cross-check for angle 2, or its replacement.
4. **A tolerance schedule** (kind (b); the cheapest cut in cycles). Loose in the
   intermediate stages, 1e-7 in the last declared stage. This is the
   `intermediate_ftol` convention (WP-2045, Rule 5 *Convention*), and it changes
   no final-stage tolerance. It is measured on group Q's families.
5. **Solve the fixed point directly** (kind (b)). With Ω frozen, the partition's
   fixed point is the Poisson maximum likelihood over I ≥ 0, a convex problem. A
   bounded Newton step on the banded ΩᵀDΩ reaches the same fixed point with
   quadratic convergence instead of EM's linear rate.
6. **The floor tail** (measure first). Count the reflections still decaying
   toward `LEBAIL_INTENSITY_FLOOR` when each partition ends. If they carry the
   tail, an active set on the floor removes it.
7. **A better accelerator** (kind (b)). Anderson acceleration or SQUAREM's other
   schemes, in cycles to 1e-7 on WP-1542's seven patterns plus the bench case.
8. **Partition inside the solve, as every other program does** (R2; a design
   change). One partition per LM iteration. The hkl list, windows and FCJ nodes
   stay frozen, since the intensities are not θ, but the residual changes under
   the solver between iterations, and LM's acceptance test must allow for it. It
   is the largest change and the one practice supports.
9. **Route a large cell to Pawley** (R3, WP-2062): on this case Pawley is already
   3-7× faster, and WP-2315 makes it faster still.

*Considered and dropped:* settling per overlap cluster. At the declared-stage
windows (`WINDOW_AREA_TOL` 2e-2, 2θ ≤ 90°) the bench case's 913 reflections form
**one** connected component, with no singletons (reviewer's count, 2026-11-27). It
returns only if a real pattern shows several components; count them before
proposing it.

**Related evidence.** Issue #1733 (the Le Bail wander test at 5 586-8 230 s in
the nightly) was folded into WP-2036, which changed the test's setting, not the
partition's cost. `test_lebail_alternation.py` is a natural second timing case.

## Non-goals

- Which structure-free method is the default: WP-2062.
- `lebail_tol`'s audited number: WP-2017 group Q (angle 4 is measured with it).
- Le Bail's stopping across passes (`LEBAIL_CONVERGED_REL`, WP-1323).
- The Pawley seed's fixed `PAWLEY_SEED_CYCLES` = 3, beyond what a faster cycle
  gives it.

## Tasks

- [x] Why Le Bail lands at Rwp 0.15 where Pawley lands at 0.045 on the same
      pattern: compare the two answers' cells, profiles, background and per-hkl
      intensities, and rerun Le Bail from Pawley's answer. Record whether the gap
      is a valley, the background or the partition, and file it where it belongs
      if it is a defect. *Answered 2026-11-27: a valley, entered through the
      probe's unseeded background. No package defect; nothing filed
      ([`2316-probe/diag_gap.py`](2316-probe/diag_gap.py)).*
- [ ] Wait for WP-2317 task 3's answer on R2-R3. If it is "route to Pawley", close
      this WP on angle 9 and say so.
- [ ] Measure main against the branch on `bigcell-lebail`, interleaved, one
      machine, min-max over at least three runs. Record cycles per update, first
      against second update of each stage, and angle 6's floor count.
- [ ] Angle 1. Byte-equal where stated, R0 (a) elsewhere.
- [ ] Angle 2 or 3: the pinned-pairwise kernel or R0 (a)'s bound, run with
      `RIETX_COMPILED=0` and `=1`.
- [ ] Angles 4-8, each as ruled, with group Q's families for any tolerance change.
      Every new or moved number gets its `rietx._audit` row and its Rule 1 kind,
      and goes to generality review.
- [ ] Tests: `test_lebail_cycles.py`, `test_window_domain.py`'s bar 1,
      `test_lebail_alternation.py`; a runaway guard on the bench case's cycles.
- [ ] Skill: none for angles 1-3, 5-7. If angle 4 or 8 moves a default, the help
      entry for `lebail_tol` changes with it (`help.py`).

## Acceptance

- `bigcell-lebail` at 2θ ≤ 120° is ≥ 10× faster than main's, measured interleaved
  in the same session (target; the measured min-max is recorded).
- Every moved number is within R0 (a)'s bound or ruled under R0 (b).
- Or the WP closes on angle 9 by ruling.

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
- Shepp, L. A. & Vardi, Y. (1982). *IEEE Trans. Med. Imaging* 1, 113-122.
- Varadhan, R. & Roland, C. (2008). *Scand. J. Stat.* 35, 335-353 (SQUAREM).
- Walker, H. F. & Ni, P. (2011). *SIAM J. Numer. Anal.* 49, 1715-1735
  (Anderson acceleration, angle 7).

## Handover log

### 2026-11-27 (2nd session) — task 1: the Rwp gap is a valley, entered through an unseeded background

Le Bail's threefold Rwp on the large-cell probe is not the partition's fault.
The probe started the background at zero, so the first partition gave the
900-count pedestal to the reflections. Every later stage then widened the
peaks to carry it, and the fit settled in a self-consistent wrong answer.
Seeded the way the agent skill already says, Le Bail lands beside Pawley. No
package code changed and nothing was filed. Two things move for the later
tasks. Probe 1's Le Bail walls timed a fit at the wrong answer. And every Le
Bail run here still ends its last partition at the 25 000-cycle cap, so the
speed question stands on a correctly seeded fit.

*Measured* (macOS arm64, `[dev]` venv, compiled tier on, `af159cf7d`; probe 1's
pattern rebuilt at `NATOMS=10`, 2θ ≤ 90°, 899 reflections;
[`2316-probe/diag_gap.py`](2316-probe/diag_gap.py), one run per row; walls are
one-run figures on a shared machine, not timings):

- **Reproduced.** Pawley Rwp 0.0447, Le Bail 0.1512, the Linux numbers to four
  digits. The generating model itself gives 0.0283, the noise floor. Le Bail's
  diagnostics: `FLOOR_HIT` (W) and `LEBAIL_CYCLES_AT_CAP`; none names the
  background.
- **The two answers.** Background c0 is 911 for Pawley and 261 for Le Bail
  (truth 900). Le Bail's background lies 677 counts under the truth on average
  (186-908). Le Bail's per-hkl intensities sum to 2.94× Pawley's, and 527 of
  910 sit at the floor. Its profile is broad: W on its floor, V 0.122 against
  0.0028, X 0.123 against 0.075. Its cell is off too: b 35.914 against
  35.991, zero shift −0.075° against −0.020°. Le Bail's banded Rwp is worst at
  low angle (0.22 at 5-20°, 0.046 at 80-90°), where the pedestal is largest
  beside the peaks. The zoom at 40-46° shows a calculated curve dipping to
  ~400 counts between peaks over an observed floor of ~950.
- **The first stage decides it.** After the `bkg` stage Le Bail stands at
  0.478 and Pawley at 0.060. The rest of Le Bail's plan only works down from
  there.
- **Rerun from the other's answer.** Le Bail started from Pawley's answer stays
  at 0.0457. Pawley started from Le Bail's answer climbs out to 0.0445. So the
  joint least-squares solve can leave the valley and Le Bail's alternation of
  partition and solve cannot.
- **The partition at fixed parameters** (25 000-cycle cap, tol 1e-7):
  | parameters | seed | Rwp after |
  |---|---|---|
  | Pawley's | Pawley's intensities | 0.0455 |
  | Pawley's | flat | 0.0455 |
  | Le Bail's | Le Bail's intensities | 0.1395 |
  | Le Bail's | Pawley's intensities | 0.1395 |
  | Pawley's + Le Bail's background | Pawley's | 0.2542 |
  | Le Bail's + Pawley's background | Le Bail's | 0.1155 |

  The answer follows the parameters, never the intensity seed, and the
  background alone breaks Pawley's set.
- **Seeded as SKILL.md §2 rule 5 says** (`rx.auto_background(data,
  seed=True)`): Le Bail 0.0469 (Chebyshev, 16 terms), 0.0484 (P-spline);
  Pawley on the same seeded Chebyshev 0.0441.
- **Cycles.** Le Bail unseeded: 76 965 in all, its last stage at the cap twice.
  Seeded Chebyshev: 84 086, all three last updates at the cap. From Pawley's
  answer: all ten partitions at the cap (250 000). The partition at the true
  parameters settles from flat in 98 cycles with 8 reflections at the floor.
  Moving b by 2e-4 there sends it to the cap with 284 at the floor.
- **The invented cell is metrically degenerate.** b = 3a exactly, so 546 of
  the 899 reflections share their d-spacing with a neighbour. Pawley's answer
  has b/a − 3 = 1.5e-4. Restoring b = 3a at Pawley's parameters still runs to
  the cap (300 at the floor), so the degeneracy is not the whole cause. What
  the slow cycles are is not measured here. The floor counts point at angle 6.

*Settled by Claude* (no maintainer trigger; R0-R8 untouched):
- The classification: a valley entered through the background seed, under the
  measurement above. The alternative, the partition, fails on the first row of
  the table.
- No defect filed, under SKILL.md §2 rule 5 ("Unseeded, every coefficient is
  0.0 and the pedestal goes to the reflections") and WP-1542's two rulings of
  2026-11-03: Q1, no finding for a background left at its seed, and Q2,
  `auto_background`'s `seed` stays `False`. The alternative is a WP for a Le
  Bail finding on this case. It would amend Q1, so it is the maintainer's.
  Q1 reopens on a statistic that separates the cases on real patterns, and
  one synthetic run is not one.
- Forward references: WP-2317's `### Inherited` (seed the `bigcell-lebail`
  case's background, and its cell's degeneracy), and a correction under
  WP-2062's entry of the same day, which said Pawley "lands at a third of" Le
  Bail's Rwp.

*Gotchas.* A probe that writes to a file buffers its stdout, so run it with
`-u` to read rows as they land. The cross step took 22 min on this
machine, mostly partitions at the cap.

*Next:* WP-2317 task 3's answer on R2-R3, as before. Then task 3 here on a
`bigcell-lebail` case whose background is seeded, recording angle 6's floor
count at each update, since the floor count tracks the slow partitions above.

- **2026-11-27** — Filed from WP-2317's probe. A fresh subagent reviewed the plan
  the same day, and its findings are folded in:
  - `reduceat` is pairwise, so no kernel is bit-identical for free;
  - Rule 5 is quoted whole;
  - per-cluster settling is dropped, since the bench case is one component;
  - the tolerance schedule and the direct Newton solve are added.

  *Fold-first:* no open WP owns the partition's cost.
  - WP-2017 group Q owns `lebail_tol`'s number. Angle 4 is measured with it,
    and a note is in its `### Inherited`.
  - WP-2062 owns the method choice; a note is in its `### Inherited`.
  - WP-1323 and WP-1542 are closed.

  *Next:* task 1, why Le Bail lands at three times Pawley's Rwp here. Then wait
  on WP-2317 task 3's answer to R2-R3.

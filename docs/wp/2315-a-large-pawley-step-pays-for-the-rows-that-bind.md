# WP-2315 — a large Pawley step pays for the rows that bind, not for every intensity

Milestone: unscheduled · Status: 🔄 2026-11-27 — claimed by @claude (ghostshift runner)
Track: A large cell
Depends on: 2317 soft (its `bigcell-pawley` case and rulings R0, R4, R5)
Priority: P2 2026-11-27 — provisional: the track the maintainer opened for a user at the wall; task 1 found real patterns on the tree reach the step once in 32 runs, so P3 if the user's pattern (WP-2317 task 1) does not cross either

## Goal

A Pawley step past `BVLS_MAX_COLUMNS` that crosses a width row costs about what a
box-only step costs, because two things change:
- the constrained solve sees only the rows and box limits that can bind;
- the work the dense route spends on the intensity block goes.

On `bigcell-pawley` at 2θ ≤ 120° the fit runs at least 3× faster (target), with
every moved number satisfying WP-2317's ruling R0.

## Context

**The bar** (WP-2317, restated because it is load-bearing): the maintainer asked on
2026-11-27 for "accuracy on par with other codes … speed as fast as possible by any
means". Under ruling R0's working reading, a step that solves the **same** problem
(pruned rows, the same LSI) is exact. A different step (a clamp, a fallback, a
profiled block) is a kind (b) move awaiting its ruling.

**The measurement** (WP-2317 probe 1, atoms ≥ 1.5 Å apart; Linux x86_64, 4
cores, `[dev]`, compiled tier on, one run each; 12 × 36 × 4 Å, P2₁2₁2₁, Cu Kα
doublet + FCJ, `mccusker_default`, `mode="pawley"`):
- 899 columns (2θ ≤ 90°): 23.7 s unprofiled, Rwp 0.0447.
- 1 601 columns (2θ ≤ 120°): **125.4 s** unprofiled, Rwp 0.0420. A profiled run
  (127.6 s) splits as below.

| call | calls | cumulative |
|---|---|---|
| `lm.minimize` (all stages) | 5 | 119.1 s |
| `lm._solve_constrained_step` | 31 | **72.8 s** (12.9 s own) |
| → `_least_distance` → `nnls` | 31 / 62 | 37.6 s / 34.6 s |
| → `numpy.linalg.eigh` | 46 | 13.2 s |
| `bccg.projected_cg` (the box-only step past 128) | 73 | 30.9 s |
| → `spilu` | 1 056 | 23.9 s |
| Jacobian | 78 | 7.5 s |

The first probe (atoms in a sub-box, profiled) read 24 crossings and 53.5 s at
1 601 columns and 18 crossings and 10.3 s at 899. Per call that is 0.57 s →
2.23 s for 1.78× the columns, an exponent of about 2.4, from one run each. At
6 477 reflections (0.459 Å to 50°) this step would dominate any fit.

**The seam.** `lm.minimize` (`src/rietx/optimize/lm.py`, the inner loop near
`:590`) takes the box-only step from `_solve_step`. Past 128 columns that step is
`bccg.projected_cg` on a sparse A preconditioned by the free block's incomplete LU
(WP-1953, WP-2011). The loop then tests `iq.crossed(x, step)` for every
`LinearInequality`. On a crossing it calls `_solve_constrained_step` (`:955`),
which takes the following route:
- it **densifies a sparse A** and takes a full `eigh` of the n × n equilibrated
  matrix;
- it builds the least-distance problem's G from an identity block for the box
  limits (Pawley intensities are bounded [0, ∞), `model.pawley_bounds()`, so
  **n** box rows) plus the inequality rows;
- it forms G·E⁻¹, about 2e10 flops a crossing at 1 601 columns, much of it
  multiplying the identity block;
- it solves the problem by `nnls`.

This happens "whatever `BVLS_MAX_COLUMNS` says" (WP-1938).

**Which rows can bind.**
- The rows come from `gaussian_width_inequalities` and
  `lorentzian_width_inequalities` (`src/rietx/optimize/least_squares.py:2761`,
  `:2888`): Γ_G² ≥ 1e-8 deg² and the Lorentzian twin, one row per (reflection,
  line) after de-duplication. Each is affine in the free profile columns.
- `_pad_inequalities` (`:3192`) widens each block's T by zero columns for the
  Pawley tail. So **every row is zero on every intensity column**, and the
  constraint lives in a ≤ ~10-dimensional subspace. Of thousands of rows in that
  space, only the hull (the extreme-θ reflections) can be active together.
- The padding stores T dense: 3 200 × 1 615 ≈ 41 MB a block at 1 601 columns.
  `crossed` costs ~14 ms a call on one thread, twice per inner step (reviewer's
  microbenchmark, 2026-11-27).

**The preconditioner.** `bccg.projected_cg` already reuses its ILU while the free
set is unchanged (`bccg.py:414-415`). The 1 056 builds in 73 solves are about 14 a
solve: free-set changes, plus a fresh factor for every call, and so for every
λ retry. The open angle is reusing a stale *superset* factor as the fixed set
grows, and keeping the factor across λ retries (λ shifts only the diagonal).

**Why it was left, and whether real data reach it.**
- WP-1938's fifth session found no Pawley fit crossing a row ("neither changed,
  because neither reaches a fit"). Forced onto FAP's 343 columns, the constrained
  step took 42-70 ms against BCCG's 0.4-1.9 ms.
- The probe reaches the step on every Pawley run. But its truth uses the
  instrument defaults U = V = Y = 0, and it starts at w = 0.010, a profile likely
  to sit near the Γ_G² floor.
- So the first task counts crossings on a **real** large-cell Pawley fit (an
  `index_pattern` validation of a large candidate; the validation fit has been
  Pawley since WP-2011) before calling the path routine.

**Task 1's count (2026-11-27, macOS arm64, `[dev]`, compiled tier on).** No real
large-cell pattern is on the tree, so the stand-ins are the real patterns whose
Pawley block passes `BVLS_MAX_COLUMNS` (FAP.XRA, 11-BM NAC), the real
`index_pattern` path (FAP.XRA's candidate validations) and two lab Cu patterns
that run to high angle (QPA round robin cpd-1a and cpd-1h). They carry real
instrument profiles, which is the probe's open question. The probe is
[`2315-probe/count_crossings.py`](2315-probe/count_crossings.py).

| case | least-squares runs | columns | crossings | constrained step | fit wall |
|---|---|---|---|---|---|
| FAP.XRA, default plan | 5 | 335-343 | 0 | 0 | 1.2 s |
| NAC, whole file | 5 | 1 492-1 499 | 0 | 0 | 11.3 s |
| FAP.XRA `index_pattern` | 12 | ≤ 375 | 1 (Γ_G² floor) | 0.05 s | 18.3 s |
| cpd-1a, cpd-1h | 5 each | 117-128 | 0 | 0 | 0.8-1.4 s |
| probe 1, 2θ ≤ 90° | 5 | ≤ 1 619 | 22 (Γ_L) | 8.6 s | 13.6 s |
| probe 1, 2θ ≤ 120° | 5 | ≤ 1 621 | 31 (Γ_L) | 36.2 s | 54.7 s |
| probe 1 + true `lor_strain` 0.03, 90° | 5 | ≤ 1 619 | 0 | 0 | 6.4 s |
| probe 1 + true `lor_strain` 0.03, 120° | 5 | ≤ 1 621 | 53 (Γ_L) | 80.2 s | 102.4 s |

- **Real data reached the step once in 32 least-squares runs**, for 0.05 s.
  Every probe crossing is in the last (`profile`) stage and on the
  **Lorentzian** rows (Γ_L ≥ 0), never the Γ_G² floor the Context above
  suspected.
- A strain term in the probe's truth does not remove the crossings at 120°.
  So the probe's zero tanθ Lorentzian is not the whole cause. Why its
  profile stage presses on Γ_L is not measured (a hypothesis: X and
  `lor_size` are both 1/cosθ terms, so their difference is a flat direction
  the LM step can overshoot along).
- `solver="trf"` is no way round: it took 159.5 s at 90° (LM 13.6 s), stopped
  its `profile` stage at the 400-evaluation cap, and ended at Rwp 0.0511
  against LM's 0.0447. At 120° it was stopped after 9 min (LM 54.7 s), and on
  NAC after 19.5 min (LM 11.3 s).
- What this re-rates: the step is as costly as filed when a fit reaches it,
  and no real pattern on the tree reaches it. Whether the user's pattern
  does is WP-2317 task 1's question.

**The ruling this touches (WP-2317's R4).** Practice (`docs/practice.md`
§ Peak-width limits) floors by value: GSAS-II per reflection, FullProf at
Γ_G = 1e-10, while RIETAN-FP rejects a step to a negative width. rietx holds the
floor inside the step because LM stalled without it:

| case | LM Rwp without the row | TRF Rwp |
|---|---|---|
| NAC | 0.18028 | 0.13375 |
| Cr₂WO₆ | 0.25458 | 0.09924 |
| LaB₆ with a width equation | 0.195 | 0.0416 |

Source: the `gaussian_width_inequalities` docstring. The same docstring says
GSAS-II's clamp works because its Marquardt takes no bounds. So a clamp is not a
free swap under LM.

**Angles, ordered by what each needs:**
0. **Bit-identical costs** (no ruling): slice `E_inv[has_lo]` rather than
   multiply an identity block; keep T on the table columns only and widen lazily,
   or let `crossed` read the table block. This is plausibly much of the profiled
   step's unattributed time (a hypothesis; the profile split says).
1. **Row and box-row pruning** (exact; no ruling). Pass the LDP only the rows the
   box step crossed, plus those within a slack of the current point, re-adding any
   the solved step violates. Pass likewise only the box rows of variables on or
   near their bound. The LDP shrinks from n + rows to tens, and the answer is the
   same problem's answer. The slack is a new number, so it gets a
   `rietx._audit` row (a tier, a reason) and goes to generality review.
2. **Cholesky instead of `eigh`** whenever λ > 0, since H is then positive
   definite. Lawson & Hanson's LSI → LDP route takes any factor of H.
3. **Block elimination** (exact if the intensity block's active set is held and
   re-checked). The rows touch only the profile block P, so solve in P with the
   intensity block eliminated (the Schur complement
   H_PP − H_PI·H_II⁻¹·H_IP), with I's box handled by the projected CG at the
   chosen P. H_II is banded plus low rank (WP-1902).
4. **Preconditioner:** a stale superset ILU and reuse across λ retries,
   measured in CG products against build cost.
5. **The fallback as the step** (kind (b)). Past 128 columns, shorten the box
   step to the first row it reaches (today's `_NoConstrainedStep` fallback).
   WP-1953's caveat applies: from a point on a face this gives τ = 0, so λ must
   rise.
6. **Clamp by value** (R4; kind (b)). It must answer the LM stalls above and
   state its Rule 1 kind. `PEAK_WIDTH_NOT_POSITIVE` reports the clamp.
7. **Profile out the intensities** (R5; kind (b), and the WP-2062
   conversation): a bounded VarPro, LM over the profile columns with the
   intensities by NNLS per evaluation.
8. **Measure `solver="trf"` first.** TRF never sees the rows, so it is angle 6's
   cost model without the ruling.

## Non-goals

- Which structure-free method is the default: WP-2062.
- The Stephens cone and texture rows, beyond what angles 0-3 give them for free.
- The Pawley restraint rows and their scale: WP-2311 (closed) and WP-1459.

## Tasks

- [x] Count crossings per stage (`truncated_by`) on a real large-cell Pawley fit,
      an `index_pattern` candidate validation, and on `bigcell-pawley`, plus
      `solver="trf"`'s wall on both. If real data never cross, re-rate this WP and
      say so. *Done 2026-11-27: one crossing in 32 real-data runs; the table is
      Context § Task 1's count.*
- [ ] Measure main against the branch on `bigcell-pawley`, interleaved, one
      machine, min-max over at least three runs, plus one profiled run for the
      split.
- [ ] Angle 0. Steps byte-equal before and after.
- [ ] Angles 1-2. The pruned/Cholesky step equal to the full step within the
      polish tolerance (`_POLISH_FEASIBLE`) on the existing constrained-step cases
      and the bench case. The audit row for the slack.
- [ ] Angle 4, measured.
- [ ] Angle 3 only if 0-2 and 4 leave the constrained step above ~10 % of the fit.
- [ ] Put angles 5-7 to the maintainer only if 0-4 miss the target, with the
      measured remainder and each one's Rule 1 kind.
- [ ] Tests: the FAP.XRA and NAC Pawley protocols within their recorded envelope;
      the bench case within R0 (a)'s bound.
- [ ] Skill: none (no API change).

## Acceptance

- `bigcell-pawley` at 2θ ≤ 120° is ≥ 3× faster than main's, measured interleaved
  in the same session (target; the measured min-max is recorded).
- The constrained step is under 10 % of the fit.
- Every Pawley acceptance number is within its envelope.

```sh
.venv/bin/python examples/bench_refinement.py --cases bigcell-pawley
.venv/bin/python -m pytest tests/test_lm_solver.py tests/test_bccg.py tests/test_pawley.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Lawson, C. L. & Hanson, R. J. (1974). *Solving Least Squares Problems*,
  ch. 23 (the LSI → LDP → NNLS route `_solve_constrained_step` takes).
- Coelho, A. A. (2005). *J. Appl. Cryst.* 38, 455-461 (BCCG; bounds inside the
  solve).
- Golub, G. H. & Pereyra, V. (1973). *SIAM J. Numer. Anal.* 10, 413-432
  (variable projection, angle 7).

## Handover log

- **2026-11-27** — Filed from WP-2317's probe. A fresh subagent reviewed the plan
  the same day, and its findings are folded in:
  - n box rows, not 2n;
  - ILU reuse already exists;
  - the exponent is ~2.4;
  - the identity-block and dense-T costs;
  - Cholesky in place of `eigh`;
  - the LM stalls behind R4.

  *Fold-first:* no open WP owns the constrained step past `BVLS_MAX_COLUMNS`.
  WP-1953 and WP-1938 are closed, and named it out of scope on a premise this
  probe breaks. WP-2062 owns the method choice, not the step.

  *Next:* task 1, count crossings on a real large-cell Pawley fit, since the
  probe's U = V = Y = 0 truth may be what puts it on the floor.

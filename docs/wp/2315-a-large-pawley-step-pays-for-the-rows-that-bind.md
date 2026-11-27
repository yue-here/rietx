# WP-2315 — a large Pawley step pays for the rows that bind, not for every intensity

Milestone: unscheduled · Status: ⬜
Track: A large cell
Depends on: 2313 soft (its `bigcell-pawley` case and rulings R0, R4, R5)
Priority: P2 2026-11-27 — provisional: the track the maintainer opened for a user at the wall, on the path the structure-free default is moving to (WP-2062) and every `index_pattern` validation already runs; re-rate when WP-2313 task 1 names the user's path and task 1 here counts crossings on real data

## Goal

A Pawley step past `BVLS_MAX_COLUMNS` that crosses a width row costs about what a
box-only step costs, because two things change:
- the constrained solve sees only the rows and box limits that can bind;
- the work the dense route spends on the intensity block goes.

On `bigcell-pawley` at 2θ ≤ 120° the fit runs at least 3× faster (target), with
every moved number satisfying WP-2313's ruling R0.

## Context

**The bar** (WP-2313, restated because it is load-bearing): the maintainer asked on
2026-11-27 for "accuracy on par with other codes … speed as fast as possible by any
means". Under ruling R0's working reading, a step that solves the **same** problem
(pruned rows, the same LSI) is exact. A different step (a clamp, a fallback, a
profiled block) is a kind (b) move awaiting its ruling.

**The measurement** (WP-2313 probe 1, atoms ≥ 1.5 Å apart; Linux x86_64, 4
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
set is unchanged (`bccg.py:414-415`). The 1 099 builds in 67 solves are about 16
free-set changes per solve, plus a fresh factor for every call, and so for every
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

**The ruling this touches (WP-2313's R4).** Practice (`docs/practice.md`
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

- [ ] Count crossings per stage (`truncated_by`) on a real large-cell Pawley fit,
      an `index_pattern` candidate validation, and on `bigcell-pawley`, plus
      `solver="trf"`'s wall on both. If real data never cross, re-rate this WP and
      say so.
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

- **2026-11-27** — created.

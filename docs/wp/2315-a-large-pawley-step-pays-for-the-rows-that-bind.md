# WP-2315 — a large Pawley step pays for the rows that bind, not for every intensity

Milestone: unscheduled · Status: 🔄 2026-11-28 — task 1, the cached |T|, Angle 9 and Angle 4 done (the 120° fit 1.8× faster); Angles 0-2 held, since the real-structure bench crosses no width row; the 3× target open
Track: A large cell
Depends on: 2317 soft (its `bigcell-pawley` case and rulings R0, R4 (settled 2026-11-28), R5)
Priority: P2 2026-11-28 — the maintainer's large-cell track, ruled to proceed whatever the user's case shows; the real-structure bench crosses no width row, so what reaches it is Angle 4, done 2026-11-28, and what it left (the CG's products and the covariance `eigh`)

## Goal

A Pawley step past `BVLS_MAX_COLUMNS` that crosses a width row costs about what a
box-only step costs, because two things change:
- the constrained solve sees only the rows and box limits that can bind;
- the work the dense route spends on the intensity block goes.

On `bigcell-pawley-120` (2θ ≤ 120°) the fit runs at least 3× faster (target), with
every moved number answering to WP-2317's ruling R0.

## Context

**The bar** (WP-2317, restated because it is load-bearing): the maintainer asked on
2026-11-27 for "accuracy on par with other codes … speed as fast as possible by any
means". R0 was ruled that day (WP-2317, DESIGN-RULES Rule 5 *Arithmetic accuracy*):
- a step that solves the **same** problem (pruned rows, the same LSI) only
  regroups arithmetic, so it is verified at fixed parameters and re-pins its
  goldens in the same change;
- a different step (a clamp, a fallback, a profiled block, Angle 9's merge) is a
  change of method, and answers to an independent measurement where one exists,
  otherwise to the established programs' answer on the same pattern.

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

| case | least-squares runs | columns | crossings | constrained step | fit wall (one run) |
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
- `solver="trf"` is no way round (one run each): it took 159.5 s at 90° (LM 13.6 s), stopped
  its `profile` stage at the 400-evaluation cap, and ended at Rwp 0.0511
  against LM's 0.0447. At 120° it was stopped after 9 min (LM 54.7 s), and on
  NAC after 19.5 min (LM 11.3 s).
- What this re-rates: the step is as costly as filed when a fit reaches it,
  and no real pattern on the tree reaches it. Whether the user's pattern
  does is WP-2317 task 1's question.

**Re-read on the real structure (2026-11-28; macOS arm64, `[dev]`, compiled
tier on, rietx 1.13.0.dev0 at 8e691ccb8).** Since WP-2317's 4th session the
bench cases carry Nb₁₈W₁₆O₉₃ (COD 2107344, Pbam) on probe 1's instrument,
broadening, start offsets and plan. Neither case crosses a width row, so the
constrained step costs nothing on either. The probe is
`count_crossings.py bench:<case>`.

| case | free columns (886 or 1 569 intensities, the rest the model's) | width rows (last stage) | crossings | constrained step | fit wall (min-max of 3) | Rwp |
|---|---|---|---|---|---|---|
| `bigcell-pawley` (2θ ≤ 90°) | 892-901 | 3 544 | 0 | 0 s | 3.84-4.03 s | 0.03088 |
| `bigcell-pawley-120` | 1 575-1 583 | 6 272 | 0 | 0 s | 14.70-15.36 s | 0.02999 |
| probe 1, 2θ ≤ 90°, same tree | 919-928 | 3 652 | 28 (Γ_L) | 9.5 s | 14.6 s (one run) | 0.04467 |

- The instrument and the start are the same as probe 1's, so the crossings
  were a property of probe 1's invented structure and intensities. The
  U = V = Y = 0 truth suspected above is shared by both and is not the
  cause.
- One profiled run of `bigcell-pawley-120` (15.4 s under the profiler):
  `spilu`'s factorisation (`gstrf`) is 7.3 s over 1 290 builds, about half
  the fit. `eigh` is 1.7 s over 15 calls, none in a step, since no
  constrained step ran. So Angle 4, the
  preconditioner, is the leading cost on the bench. Angles 0-3 wait on a case
  that crosses.

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
   *Measured 2026-11-27 (3rd session):* only the cached |T| is bit-identical
   on every BLAS. Any blockwise G·E⁻¹ changes bits under x86_64 OpenBLAS,
   so it is a rounding move under R0 like Angles 1-2. The handover log has
   the numbers.
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
   *Done 2026-11-28 for the superset half: products 5 887 → 11 481, builds
   1 290 → 67, the 120° fit 14.25-14.73 s → 7.87-8.28 s. Reuse across λ
   retries was built, measured and dropped: 3 of 300 projected-CG solves on
   five cases were retries. The handover log has the numbers.*
5. **The fallback as the step** (kind (b)). Past 128 columns, shorten the box
   step to the first row it reaches (today's `_NoConstrainedStep` fallback).
   WP-1953's caveat applies: from a point on a face this gives τ = 0, so λ must
   rise.
6. **Clamp by value** (R4; kind (b)). It must answer the LM stalls above and
   state its Rule 1 kind. `PEAK_WIDTH_NOT_POSITIVE` reports the clamp.
   *Dropped 2026-11-28: R4 settled by Claude under measurement, keeping the
   width floor inside the LM step in every mode (LM stalls without the row:
   NAC Rwp 0.180 against TRF's 0.134, Cr₂WO₆ 0.255 against 0.099; TRF took
   159.5 s against LM's 13.6 s on probe 1 at 90°). A blind review agreed.*
7. **Profile out the intensities** (R5; kind (b), and the WP-2062
   conversation): a bounded VarPro, LM over the profile columns with the
   intensities by NNLS per evaluation.
8. **Measure `solver="trf"` first.** TRF never sees the rows, so it is angle 6's
   cost model without the ruling.
9. **Merge lattice-forced coincidences** (WP-2317's R5, ruled 2026-11-27,
   "go (b)"; a change of method under Rule 5, so judged against independent
   references). Reflections whose d agree in every cell of the setting
   (cubic 333/511, hkl/khl under 4/m, -3, 6/m) become one intensity column
   carrying their sum; each member is drawn at its multiplicity's share (equal
   F²) and reports no esd. Accidental coincidences (probe 1's b = 3a) keep the
   restraint, whose target moves from equal peak intensity to equal F². A
   phase whose model reads hkl (a Stephens block, a peak equation, satellites,
   a magnetic component) keeps one column per member. *Done 2026-11-27 (4th
   session); the handover log has the numbers.* It shrinks the block on
   cubic, tetragonal, trigonal and hexagonal phases. It cannot shrink probe 1,
   whose P2₁2₁2₁ metric forces no coincidence.

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
      split. *Measured 2026-11-27 on probe 1 at 2θ ≤ 120° for a form of
      Angle 0 since withdrawn (the `bigcell-pawley` bench case is not on the
      tree yet): main 55.0-55.4 s, that branch 52.6-52.9 s, three runs each.
      The split is in the handover log. The cached |T| alone was not timed.*
      *"Before" re-read 2026-11-28 on the real-structure cases: 3.84-4.03 s
      at 90° and 14.70-15.36 s at 120°, three runs each, with no crossing
      (Context § Re-read on the real structure).*
- [x] Angle 0, its bit-identical part. *Done 2026-11-27:
      `LinearInequality.crossed` keeps |T|, bit-identical by construction.
      The blockwise G·E⁻¹ (`lm._rows_in_z`) was byte-equal on macOS
      Accelerate and arm64 OpenBLAS and not on x86_64 OpenBLAS (Linux CI,
      and Rosetta here), so it was withdrawn to the next item.*
- [ ] Angles 0 (blockwise G·E⁻¹), 1 and 2. The blockwise, pruned and Cholesky
      steps equal to the full step within the
      polish tolerance (`_POLISH_FEASIBLE`) on the existing constrained-step cases
      and the bench case. The audit row for the slack. *Held 2026-11-28:
      neither bench case crosses a row, so nothing on the tree but probe 1
      exercises the step. Start this item on a case that crosses.*
- [x] Angle 4, measured. *The leading cost on `bigcell-pawley-120` since
      2026-11-28: `spilu` is about half the fit.* *Done 2026-11-28:
      `bccg.projected_cg` keeps a sparse free block's incomplete LU while
      variables only leave the free set. The 120° fit went from
      14.25-14.73 s to 7.87-8.28 s, 1.8×, and every parameter moved under
      3e-7 esd.*
- [ ] Angle 3 only if 0-2 and 4 leave the constrained step above ~10 % of the fit.
- [ ] Put angles 5-7 to the maintainer only if 0-4 miss the target, with the
      measured remainder and each one's Rule 1 kind.
- [ ] Tests: the FAP.XRA and NAC Pawley protocols within their recorded envelope;
      the bench case verified as R0 asks of the angle's kind.
- [x] Angle 9 (R5 (b)): the merge, its detection tested on every Laue class
      against GSAS-II's identities, the exception for hkl-dependent models, the
      equal-F² restraint target, and the cascade (statistics, diagnostics,
      exporter, help, manual, skill row). *Done 2026-11-27 (4th session).*
- [ ] Skill: none (no API change). *Angle 9 rewrote the
      `PAWLEY_OVERLAP_UNRESOLVED` row in `references/diagnostics.md` to point
      at `ReflectionState.merged_groups`.*

## Acceptance

- `bigcell-pawley-120` (2θ ≤ 120°) is ≥ 3× faster than main's, measured interleaved
  in the same session (target; the measured min-max is recorded).
- The constrained step is under 10 % of the fit.
- Every Pawley acceptance number is within its envelope.

```sh
.venv/bin/python examples/bench_refinement.py --cases bigcell-pawley,bigcell-pawley-120
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

### 2026-11-28 (2nd session) — Angle 4: the incomplete LU is kept while the free set only shrinks (ghostshift runner; PR #1878)

The large Pawley fit at 2θ ≤ 120° now takes about 8 s where it took about
14.5 s. Almost all of the saving is one change. The step's conjugate-gradient
solve used to rebuild its incomplete-LU preconditioner every time an
intensity landed on its zero floor, about 33 times a solve. It now keeps the
factor it has, because a factor built on a larger free set still
preconditions a smaller one. The solve takes about twice as many cheap
matrix products and stops at the same residual floor, and every fitted
parameter on five cases moved by less than a millionth of its esd. Reusing
the factor across λ retries, the WP's other half of Angle 4, was built and
dropped: on those five cases 3 of 300 solves were retries. The 3× target is
not reached. What is left of the 120° fit is the CG's products, a dense
eigendecomposition outside the step, and the rest of the model.

*Done.*
- `bccg.projected_cg`: a sparse H's incomplete LU is rebuilt only when the
  free set gains a variable the factor was not built on. A shrink keeps it,
  and `_preconditioned` solves on the factor's set with r zero on the
  variables fixed since and drops the answer there. A failed factor is
  rebuilt on any change, as before. The dense Cholesky path is unchanged.
  `_REUSE_STALE_FACTOR` switches it off for probes, as `_PRECONDITION_DENSE`
  does for WP-2011's.
- `tests/test_bccg.py::test_a_stale_superset_factor_reaches_the_same_minimiser`:
  on the banded Pawley-shaped box QP the stale path builds once (the
  refactoring path 115 times), lands within 1e-8 of the largest component
  of the refactoring path's answer, and puts the same variables on their
  bound, inside the default 2n budget.
- The λ-retry cache (a `FactorCache` threaded from `lm.minimize` through
  `_solve_step`) was built, measured and removed before commit.
- The probe is a scratch script outside the tree: it wraps
  `_factor`, `_preconditioned` and `projected_cg` and counts builds by kind
  (first, shrink, grow), CG directions and Hessian products per solve.

*The bar.* Under R0 clarified (WP-2317) this is a speed change, and a speed
change leaves the model as it was. The CG's stopping rule is untouched
(‖r‖² ≤ `_PCG_TOL`²·‖g‖²), so a converged solve returns the same box
minimiser to that floor. A solve that spends its 2n budget returns its best
point on either path, so the bar on the fit is measured, not derived: every
parameter in esd units, the convention of
`test_compiled_kernels.FIT_THETA_ESD`. No byte-equality is claimed on any
BLAS; the move is the CG tolerance's, far above rounding.

*Measured* (macOS arm64, `[dev]`, compiled tier on, Accelerate; main is a
`git archive` of 20366d726 run by `PYTHONPATH`, the branch at a7a0b7ef6;
every run under the shift's suite lock).
- Interleaved bench, three rounds, `--configs off`, main then branch each
  round: `bigcell-pawley-120` 14.25-14.73 s → 7.87-8.28 s (1.8×);
  `bigcell-pawley` 3.76-3.83 s → 2.47-2.67 s (1.5×). Same Rwp to the
  printed digits and the same evaluations per stage (2, 8, 11, 8, 14).
- Counts, one run each (product counting on, so walls run high):

| case | solves | builds | factorisation | products | solves at budget | λ retries |
|---|---|---|---|---|---|---|
| `bigcell-pawley-120` main | 39 | 1 290 | 10.3 s | 5 887 | 1 | 0 |
| `bigcell-pawley-120` branch | 39 | 67 | 0.5 s | 11 481 | 2 | 0 |
| `bigcell-pawley` main | 39 | 707 | 1.67 s | 1 699 | 0 | 0 |
| `bigcell-pawley` branch | 39 | 63 | 0.18 s | 3 321 | 0 | 0 |
| NAC Pawley main / branch | 50 | 212 / 55 | 0.05 / 0.02 s | 700 / 731 | 0 | 0 |
| FAP.XRA Pawley main / branch | 31 | 71 / 38 | 0.02 / 0.01 s | 300 / 383 | 0 | 0 |
| FAP.XRA `index_pattern` main / branch | 141 | 326 / 172 | 0.11 / 0.06 s | 1 422 / 1 575 | 0 | 3 |

  On main 1 223 of the 120° case's 1 290 builds were shrinks, 28 grows and
  39 a solve's first.
- Fit shift, branch against main, in esd units: 120° worst 2.4e-7
  (`instrument.profile.u`), 90° 2.1e-7, NAC 1.3e-9, FAP.XRA 2.6e-8. Rwp
  relative 3.3e-10, 7.2e-10, 8.6e-14, 1.3e-13.
- Profile, 120°, one run each: main 14.9 s with `gstrf` 7.3 s over 1 290
  calls; branch 8.2 s with `projected_cg` 2.9 s (sparse products 1.35 s
  over 11 889, ILU solves 0.66 s over 9 857, `gstrf` 0.43 s over 67) and
  `eigh` 1.6 s over 15 calls from `statistics.normal_factors` and
  `discarded_directions`, outside the step.

*Tests* (macOS arm64, `[dev]`, on fb29877ac, origin/main 5a06184af merged
in): fast selection (`-m "not slow"`) 15 892 passed, 457 skipped, 30
xfailed, 8.7 min; full suite 16 853 passed, 468 skipped, 49 xfailed, 1
xpassed, 33.8 min, no failure. The one added test costs 0.06 s locally.
No main run on this machine to diff the counts against, so the count check
rests on the one added test. `tests.reader_output`: unchanged against the
merge-base. Main then moved by 11 commits, WP-2314's angle 3 among them
(`structure_factor.py`, `forward.py`, goldens), none in `bccg.py`. On
a9d61c21e, with that main merged in: fast selection 15 904 passed, 462
skipped, 30 xfailed, 8.8 min, and `test_acceptance_fap.py`'s Pawley row
passed. The full suite was not rerun on that tree.

*Review* (`/code-review high --fix`): five findings, four docstring fixes
taken (each path's rebuild rule stated exactly, the "same stop" claim
limited to a converged solve, the timing quoted as a range). One left: a
stale factor kept however far the free set shrinks could spend the 2n
budget on a case where most intensities floor in one solve. The 120° case
went from 1 to 2 budget-bound solves with the fit unchanged, and the four
other cases had none. A refactor-by-fraction rule is a new number, so it
waits for a case that needs it (Next 2).

*Not done.* WP-2317's `### Inherited` is not edited: another runner is
working in that file today, and this WP already owns the result.

*Settled by Claude* (for blind review):
- Accept the path change under R0 clarified as a speed change, on the
  measured shift (≤ 2.4e-7 esd). Alternative: hold it as a kind (b) move
  and ask for a ruling.
- Drop the λ-retry cache: 3 of 300 solves were retries, a few milliseconds.
  Alternative: keep it for the WP's completeness.
- Keep the factor however far the free set shrinks, with no threshold.
  Alternative: rebuild once the free set falls below a fraction of the
  factored set, a new number with an audit row.
- No generality review: the change adds no threshold and no automatic
  action on a result, only a solver path. Alternative: send it as an
  always-on rule.

*Next.*
1. The 3× target against what is left at 120° (about 8 s): the CG's
   products and ILU solves (about 2 s), `eigh` in the covariance (1.6 s,
   15 calls, outside the step) and the model. The eigh is in
   `optimize/statistics.py`, not in this WP's seam; say there whether it
   belongs to WP-2317 or here before building.
2. A rebuild rule by how far the free set has shrunk would cut the doubled
   products. Measure it only with a case that hits the 2n budget more than
   twice, since it needs a number.
3. Angles 0-2 as before: only once a case crosses a width row.

### 2026-11-28 — Angles 0-2 held: the real-structure bench crosses no row (ghostshift runner; PR #1875)

The expensive constrained step this WP set out to shrink is not reached by
either bench case now that they carry a real structure. Both cases ran their
five least-squares stages with no crossing of a width row, so the step cost
nothing in fits of 3.84-4.03 s and 14.70-15.36 s. Probe 1's invented structure still crosses
on today's tree, with the same instrument and start, so its crossings came
from that structure. This session wrote no solver code. Angles 0-2 would
optimise a path no case on the tree but probe 1 exercises. On the 120° case
about half the fit is now the incomplete-LU preconditioner's factorisation,
which is Angle 4.

*Done.*
- `count_crossings.py` gained `bench:KEY`, which runs a single-fit case of
  `examples/bench_refinement.py` under the crossing counter.
- Context § Re-read on the real structure carries the table, the profiled
  split and the new "before". Tasks 2, the Angles 0-2 item and Angle 4 carry
  dated notes. The Status and Priority lines say what reaches the bench.
- `### Inherited` deleted. Its first bullet's numbers are probe 1's GSAS-II
  timing and the b = 3a overlap count, both kept in WP-2317's Context, and
  R5 was built as Angle 9. Its second bullet asked for the "before" to be
  re-read on the new cases, which this entry does.
- WP-2317's `### Inherited` has a bullet for R4: no step on the bench
  crosses a width row.
- R4 settled by Claude under measurement (LM stalls without the row: NAC
  0.180 against 0.134, Cr₂WO₆ 0.255 against 0.099; TRF 159.5 s against
  13.6 s), 2026-11-28; a blind review agreed; Angle 6 dropped. Recorded at
  the shift lead's word; the Angles list marks it.

*Measured* (macOS arm64, `[dev]`, compiled tier on, Accelerate, rietx
1.13.0.dev0 at 8e691ccb8; every run under the shift's suite lock).
- Crossings: the Context table. The last stage (`profile`) carries 3 544
  width rows at 90° and 6 272 at 120°. The `profile_w` stage carries one.
  No other stage carries any.
- Bench, three runs each, `--configs off`: 3.84-4.03 s at 90°, 14.70-15.36 s
  at 120°, Rwp 0.03088 and 0.02999, five stages converged.
- Profile, 120°, one run: `gstrf` 7.3 s over 1 290 factorisations, `eigh`
  1.7 s over 15 calls (no constrained step ran), sparse matrix-vector
  products 0.7 s. The five least-squares runs took 11.6 s of the 15.1 s fit
  in the crossing probe's run; the rest is outside them and was not split.
- Probe 1 at 90° on this tree, one run: 28 crossings, all on the Lorentzian
  rows of the last stage, and 9.5 s of its 14.6 s in the constrained step
  (the 2nd session read 22 crossings and 8.6 s of 13.6 s).

*Not done.* No suite ran: the branch changes a probe script under
`docs/wp/` and the WP files, which CI's planning set treats as docs.

*Review* (`/code-review high --fix`): seven findings. Five taken: the probe
refuses an unknown or a series case and drops runs a case's build makes; the
Context table names free columns, not intensities; the Goal, Acceptance and
command name `bigcell-pawley-120`; this entry quotes ranges. Two left: the
probe 1 placeholders, since filled from the run; and whether the 3× target
still fits a 15 s fit with no crossing, which Next item 1 re-reads.

*Settled by Claude* (for blind review):
- Stop at the premise, under the brief's own rule ("if it no longer crosses
  … stop with a docs-only PR"). Alternative: build Angles 0-2 for the
  maintainer's "cells this size are met in the wild", tested on probe 1.
- Keep P2 rather than drop to P3. The maintainer ruled the track to proceed
  whatever the user's case shows, and Angle 4 reaches the bench.
  Alternative: P3, as the 2nd session's next-step said for a case that does
  not cross.

*Next.*
1. Angle 4 on `bigcell-pawley-120`: count CG products against `spilu`
   builds, then try reusing the factor across λ retries (λ moves only the
   diagonal) and a stale superset factor as the fixed set grows. Each moves
   numbers at rounding level at most, so R0 governs it. Re-read the 3×
   target against what Angle 4 can remove: `spilu` is about half the fit,
   so 3× needs more than the preconditioner.
2. Angles 0-2 only once a case crosses: the user's pattern (WP-2317 task 1),
   or a bench case whose truth presses Γ_L. The design notes in the Angles
   list stand. Pruning keeps the polish's inputs, so a pruned step that finds
   the same active rows, in the same order, gives the same polished step.
3. Why probe 1's structure presses on Γ_L is still unmeasured. The review
   of R4 left a lead: every probe 1 crossing is on the Γ_L ≥ 0 rows, and X
   and `lor_size` both go as 1/cosθ, so their difference may be a flat
   direction. If so, the crossings are a conditioning problem rather than a
   step-cost one. Test it on probe 1 by the correlation of X and `lor_size`
   in the `profile` stage, or by refitting with one of them held.

### 2026-11-27 (4th session) — Angle 9, the lattice merge (ghostshift runner; PR #1869)

A Pawley fit now refines reflections that share a d-spacing in every cell of
their space group, such as cubic 333 and 511, as one intensity. That is the
only quantity the pattern measures, and GSAS-II does the same. The fit
reports the group's sum with its esd and marks each member's own value as
unmeasured, so it no longer hands back an equal split that looks like a
measurement. Accidental overlaps keep their restraint, now towards equal F².
On the three real patterns measured, the merge removed 4 to 123 intensity
columns and moved no cell by more than 0.02 esd. It cannot speed up the
large-cell bench case, whose orthorhombic cell forces no coincidence.

Built WP-2317's R5 (b), "go (b)". Branch `wp2315-pawley-lattice-merge`,
stacked on the `wp2317-rulings` commits (through aa612fe02).

*What changed.*
- `symmetry.lattice_coincidences` finds reflections whose d agree for every
  metric the setting allows. Two orbits coincide for every allowed metric
  exactly when their orbit second moments Σ_R (Rᵀh)(Rᵀh)ᵀ agree. That sum is
  the Reynolds projection of hhᵀ onto the invariant metrics, and it is an
  integer matrix, so the test is exact.
- `forward._lattice_merge_groups` declines the merge for a phase whose model
  reads hkl: a Stephens block, a peak equation (any `peq`, since one may read
  h, k, l), satellites or a magnetic component. Texture and extinction never
  enter a Pawley fit.
- `PawleyBlock` now holds columns. A merged group is one column carrying the
  sum. Each member is drawn at m_k/Σm of it (equal F², since a Pawley
  intensity is the whole peak) and reports an infinite esd. `expand` is a
  gather on numpy and a frozen dense matmul on the traced backends. The groups
  are frozen at compile and do not depend on the cell.
- The overlap restraint's target is equal F² (m_k/Σm). Groups with equal
  multiplicities give the old rows bit for bit.
- Cascade: `n_free_parameters` counts columns; each merged group is a
  `MergedGroup` (member hkls, the measured sum, its esd) in
  `ReflectionState.merged_groups`, and `PAWLEY_OVERLAP_UNRESOLVED` stays for
  accidental overlaps (5f9a7e80e replaced the first form, where that code
  listed the merged groups); `ReflectionRow.merged_group` in the exporter;
  the series carry goes through `set_pawley_intensities`, which expands per
  phase; help, `_audit` (suggestion count 1), the manual's
  `fm-pawley-lattice` equation and the `fm-pawley-split` share,
  `reference/exports.md`, `reference/history.md`, `guides/export.md`,
  practice.md's rietx and GSAS-II rows, the skill row (copies re-synced), a
  `pawley_merged` cross-backend config, and the schema 0.62 note.
- `toy_pawley`'s golden is re-pinned: only its restraint rows moved
  (`tests/data/README.md` § backend_goldens).

*Verified.* `tests/test_pawley_lattice_merge.py`: on 18 space groups covering
every Laue class and setting, the groups equal GSAS-II's per-class identities
(GSASIIstrIO.py:955-998) to 2θ 110°; random cells drawn from
`cell_constraints` agree with the d-classes; the textbook pairs (cubic
333/511 and 410/322, tetragonal 210/120 under 4/m and not under mmm); a merged LaB6 block; the Stephens
exception with its equal-F² rows; and each of the four hkl-reading declines. `tests/test_pawley.py`'s overlapped LaB6 fit
reports the 221+300 sum within 6 % of the truth and the members as unmeasured.

*Measured* (`docs/wp/2315-probe/merge_measure.py`; macOS arm64, `[dev,jax]`,
compiled tier on; main = aa612fe02's `src`; three runs each, interleaved, on a quiet machine). References are
independent where one exists, else GSAS's answer on the same pattern.

| fit | columns main → branch | merged groups | n_free | wall main / branch (min-max of 3) | moved values |
|---|---|---|---|---|---|
| FAP.XRA (P 6₃/m) | 329 → 206 | 115 | 343 → 220 | 0.76-0.88 / 0.69-0.73 s | a 9.3716750 → 9.3716754 Å (+0.007 esd; GSAS's EXP 9.371724, gap 4.9e-5 on both); c 6.8858654 → 6.8858663 Å (+0.016 esd; EXP 6.885867, gap 1.6e-6 → 0.7e-6); esd(a) 5.90e-5 → 5.84e-5 |
| SRM 660c LaB6 (P m-3m) | 30 → 24 | 6 | 43 → 37 | 0.25-0.29 / 0.26-0.28 s | a 4.157066932 Å, unchanged to 3e-13 (CIF 4.156780; the gap is the protocol's, the same on both); esd 1.6462e-5 → 1.6452e-5 |
| corundum, SRM 676a (R-3c) | 64 → 60 | 4 | 78 → 74 | 0.38-0.42 / 0.41 s | cell unchanged to 1e-12, c/a 2.7298426 on both (certificate 2.7298468) |

Rwp moved only on FAP (0.07824420 → 0.07824007) and is not the evidence.
The wall moves are within run-to-run spread except FAP's, about 10 %
faster. These fits are too small for the column count to dominate. A large
cubic, tetragonal, trigonal or hexagonal cell is where the merge pays;
probe 1 (P2₁2₁2₁) has no coincidence to merge. The plots
`tests/output/wp2315_<case>_pawley.png` and the LaB6 overlapped fit were
looked at. Each matches main's; corundum's peak-shape residual at low angle
belongs to the protocol and is the same on main.

*Tests* (macOS arm64, `[dev,jax]`): fast selection (`-m "not slow"`) 16 066 passed, 268 skipped, 30 xfailed, 16.5 min. full suite (`-n auto --dist loadgroup`) 17 031 passed, 275 skipped, 49 xfailed, 1 xpassed, 1 failed, 53 min. The failure was `test_audit_delta.py::test_the_reader_agrees_with_the_import`, caused by an `_audit.py` prose edit landing mid-run (the reader read the new text, the import was older); alone on the final tree it passes, 16 of 16.
`tests.reader_output` exit 0 on the tree before the `MergedGroup` record.
After it, on the final tree: fast selection 16 069 passed, 268 skipped, 30 xfailed, 18 min (one test edited after the run: `test_satellites`' key list gains `merged_groups`; that file passes alone), and `tests.reader_output` exit 0. The seven added tests cost 2.6 s locally, 2.25 s of it `test_pawley_lattice_merge.py`, none in the slow tail. Count check: passed + failed moved by 4 against the earlier fast run (16 066 → 16 070, the two now-fixed failures included), where 5 tests were added since. The one-test gap was not traced. The full suite was not rerun after the record:
the record moves no fitted number (the coordinator's rule for this item).

*Review* (`/code-review high --fix`): seven findings. Five taken: the probe
refuses an unknown or a series case and drops runs a case's build makes; the
Context table names free columns, not intensities; the Goal, Acceptance and
command name `bigcell-pawley-120`; this entry quotes ranges. Two left: the
probe 1 placeholders, since filled from the run; and whether the 3× target
still fits a 15 s fit with no crossing, which Next item 1 re-reads.

*Settled by Claude* (for blind review):
- Detection by the orbit's second moment in `symmetry.py`, not by calling
  `cell_constraints`. The root CLAUDE.md makes `ParameterTable` its only
  caller. The test crosses the two. Alternative: route detection through
  `ParameterTable`.
- Any peak equation declines the merge, even one that reads no hkl.
  Alternative: parse the expression for h, k, l. The conservative form costs
  columns, never accuracy.
- A merged member reports an infinite esd, the existing "unmeasured" spelling
  (`LSQOutcome.discarded`), and keeps its share in `ReflectionState.intensity`,
  since that list is what a checkout restores. Alternative: `None` there,
  which would need a second restore path.
- The record is `ReflectionState.merged_groups` (5f9a7e80e), settled by the
  coordinator under Rule 4 (a new output; kind 1 records that it fired) and
  the generality review's finding. **It is a stored-format addition**: schema
  0.62, additive, `None` by default, refused by an older build. The
  maintainer's CLAUDE.md sends stored-format changes to him. **Ruled
  2026-11-27: "a, go ahead"**, option (a) of three: keep the stored field as
  is, over (b) a diagnostic only, which loses the sum on reload and in the CIF
  export, and (c) leaving R5 (b) unimplemented.
- The two WP-2311 restraint tests keep LaB6's 221/300 pair apart by
  monkeypatching `_lattice_merge_groups`, since that pair is now merged.
- For generality review: the merge is an automatic action the audit table
  cannot see. Its tier is the physics (a metric identity) plus GSAS-II's
  practice; it has no threshold.

*Rule 1 kind.* The merge is kind 1. The split inside a group cannot be
measured at any cell the setting allows. The dissenters checked: TOPAS, BGMN
and MAUD leave both intensities free with no stated rule (practice.md), which
is no different physical answer; GSAS-II ties them as this does. A history
node's `inf` esd round-trips as `"Infinity"` (`ser_json_inf_nan`).

*Generality review* (the `generality-review` agent, Sonnet, 2026-11-27).
Held: the merge (tier 1 detection, tier 2 share convention), the suggestion
count, the restraint target. Acted on: a test now pins each of the four
hkl-reading declines (`test_each_hkl_reading_term_declines_the_merge`), and
`PAWLEY_OVERLAP_FWHM_FRAC`'s grounds name the equal-F² target and say its
sweeps predate it. It rated the first form of the report weak: an `info`
`PAWLEY_OVERLAP_UNRESOLVED` firing on every cubic, tetragonal, trigonal and
hexagonal Pawley fit (3 of 3 here). The coordinator settled the fix, and
5f9a7e80e records the merge on `ReflectionState.merged_groups` instead; the
code is back to accidental overlaps and its suggestion count to 1. The judge
was not re-dispatched: the table's only remaining change is that row's prose.

*Code review* (`/code-review high --fix`, 5d6c743b3): five nits, all taken.
The help names the four terms that decline the merge; the diagnostics count
member reflections, not columns; a real-fit test of an unmerged overlap
(`test_an_unmerged_overlap_comes_back_flagged_with_its_split_unresolved`);
`lattice_coincidences` cites Toby & Von Dreele (2013); this entry's cascade
bullet. Its sixth point is the stored-format flag above.

*CI fix (Linux py3.11).* `test_a_pawley_fit_depends_neither_on_the_units_nor_on_a_high_background_start`
read LaB6's (2 2 1) and (3 0 0) swapped between two fits. Each member's share was
right for its hkl; the reflection list's order was not. numpy's argsort is unstable
and lattice-equal d may differ by an ulp, so the pair's order depended on the
platform and the start. `generate_reflections`, the satellite lists and both list
merges now keep d within 1e-12 relative in first-met orbit order
(`symmetry._order_by_d`, audit row tier 1). `srm660c` and `nac` goldens re-pinned:
only tied reflections' summation order moved, at most 1.6e-16 relative. Two tests
pin it, one with the pair's shares at four starts. Fast selection after it (macOS
arm64, `[dev,jax]`): 16 075 passed, 268 skipped, 30 xfailed; +5, the tests added.

*Left undone.*
- `solve/cost.py`'s nuisance columns are not merged.
- torch is not installed here, so the `pawley_merged` torch rows did not run.

*Next.* (1) Done 2026-11-27: the stored-format addition was ruled (a) and
PR 1869 merged. (2) Angles 1-2 and 4 on the bench case,
which the merge does not reach. A large cubic or hexagonal cell is where the
merge's column saving would show in the wall; no bench case has one yet.

### 2026-11-27 (3rd session) — Angle 0's blockwise product withdrawn (ghostshift runner; PR #1861)

Linux CI failed `test_the_rows_in_z_are_the_dense_product_byte_for_byte` on
all four seeds, on py3.11 and py3.14. Linux's BLAS sums the blockwise
product in a different order from the dense one. So on Linux the change
moved numbers at rounding level, which puts it under WP-2317's R0 with
Angles 1-2. This session removed `lm._rows_in_z` and its two tests. The
cached |T| in `LinearInequality.crossed` stays: `abs` is exact and T is
frozen for the run, so it reuses the same bytes. The PR now ships task 1's
probe and counts, the cached |T|, and the WP-2317 entry. It claims no
speed-up, since the 1.04-1.05× was measured with the blockwise product in.

*Measured* (`docs/wp/2315-probe/blockwise_bytes.py`, run with each BLAS's
interpreter: eight random shapes, n = 300-591, 500 width rows, 7 columns of T
nonzero, signed zeros in E⁻¹). Two blockwise forms against the dense
`G @ E_inv`: (a) the PR's, T read on its nonzero columns; (b) the box rows
sliced and T's rows multiplied whole.
- macOS Accelerate and OpenBLAS 0.3.34 arm64 (`neoversen1`): both forms
  byte-equal on all eight shapes.
- OpenBLAS 0.3.34 x86_64 (`Sandybridge` kernels, an x86_64 numpy 2.5.5
  under Rosetta): both forms differ on every shape, (a) in 727-96 905
  elements, (b) in 115-5 099. The box rows matched in every case; only T's
  rows moved. The largest difference was 2.3 ε of |T|·|E⁻¹| for (a) and
  2.0 ε for (b), so it is rounding.
- So no blockwise form is byte-equal on every BLAS. Form (b) shows that
  splitting the GEMM by rows already moves T's bits. A BLAS promises no
  reduction order, so a byte-equality test on one BLAS certifies only that
  BLAS. An x86_64 venv under Rosetta reproduces the Linux split on this Mac.
- Tests (macOS arm64, `[dev]`): `test_lm_solver.py`, `test_bccg.py`,
  `test_pawley.py` and `test_gaussian_width_floor.py` together, 115 passed,
  1 xfailed (the 2nd session's 122 less the 7 removed cases). Fast selection
  (`-m "not slow"`, this branch over main e94925ae9): 15 819 passed,
  452 skipped, 30 xfailed.

*Next.* As the 2nd session's, with the blockwise G·E⁻¹ added to Angles 1-2
behind R0.

### 2026-11-27 (2nd session) — task 1, the measurement, Angle 0 (ghostshift runner; PR #1861)

No real pattern on the tree reaches the expensive step: one crossing in 32
least-squares runs over FAP.XRA, 11-BM NAC, FAP.XRA's `index_pattern`
validations and two lab Cu round-robin patterns. WP-2317's synthetic probe
reaches it in its last stage on the Lorentzian width rows, and there the
step is 63-78 % of the fit. So the WP's cost is real but, on the evidence
here, specific to the probe until the user's own pattern says otherwise.
Angle 0 ran the same steps byte for byte on this Mac, for about 5 % less
wall on the probe. *Corrected by the 3rd session:* Linux CI's BLAS gave
different bits, so only the cached |T| ships and the 5 % does not. The rest
of the step is the nnls solve and the eigendecomposition, which only Angles
1-2 can shrink, and those move numbers at rounding level.

*Scope.* The shift held this session to task 1, the measurement and Angle 0,
until the maintainer answers WP-2317's R0-R8. Angles 1-2 and later were not
started.

*Done.*
- Task 1: `docs/wp/2315-probe/count_crossings.py` wraps `lm.minimize` and
  the constrained step and prints crossings per run and per stage. The table
  is Context § Task 1's count.
- Angle 0: `lm._rows_in_z` builds G·E⁻¹ by blocks (row slices of E⁻¹ for the
  box rows, T on the columns it reads). `LinearInequality.crossed` keeps |T|
  in a cached property. (The 3rd session removed `_rows_in_z` and both
  tests; the cached |T| stays.) Two tests, seven cases, in `tests/test_lm_solver.py`: the helper
  against the dense product on four seeds, with signed zeros and padded
  columns, and a Pawley-shaped constrained step (262 columns, a sparse A,
  the least-distance path reached) against the dense product on three seeds.

*Measured* (macOS arm64, `[dev]` venv, compiled tier on, Accelerate BLAS;
every timing under the shift's suite lock, `serial.py`).
- Byte equality: the first 8 of probe 1's 31 constrained steps at 120°
  (captured from main's run) come back byte-equal from both main and the
  branch. The whole 120° fit is byte-equal too: y_calc, the 15 values and
  esds, Rwp, every stage's iteration count. The helper's equality also held on
  40 random shapes under OpenBLAS 0.3.34 (arm64) and Accelerate. Without the
  `+ 0.0` all 40 differed in the sign of a zero. Linux CI (x86_64 OpenBLAS)
  failed the helper's test on all four seeds, on py3.11 and py3.14.
- Wall, probe 1, Pawley, 2θ ≤ 120°, unprofiled, interleaved: main 55.0-55.4 s,
  branch 52.6-52.9 s (three each), 1.04-1.05×. This machine runs the probe at
  about 0.44× the Linux wall the Context quotes (125.4 s there).
- Per constrained step, the 8 captured calls, best of 3: main 1.19-1.20 s,
  branch 1.09-1.12 s. `crossed` 5.3-5.6 ms → 3.5-3.6 ms a call for both blocks.
- Profiled split, branch (main in brackets): constrained step 34.2 s
  (36.9 s) over 31 calls, of it own time 1.3 s (4.1 s); `nnls` 23.2 s
  (23.3 s); `eigh` 7.3 s; `_equality_step` 2.3 s. `projected_cg` 11.4 s, of it
  `spilu` 8.9 s over 1 058 builds. On one captured step `nnls` is 68 % and
  `eigh` 16 %.
- `solver="trf"`, one run each: probe at 90° 159.5 s against LM's 13.6 s, its `profile`
  stage at the 400-evaluation cap, Rwp 0.0511 against 0.0447. Stopped after
  9 min at 120° and after 19.5 min on NAC.
- Tests: `test_lm_solver.py`, `test_bccg.py`, `test_pawley.py` and
  `test_gaussian_width_floor.py` together, 122 passed, 1 xfailed.
- Fast selection (`-m "not slow"`, on main 94804b716 plus this branch):
  15 821 passed, 452 skipped, 30 xfailed. The 7 added cases are passes, no
  new skip. They cost 0.50 s in one local run (`tests.added_test_times`).
  The full suite did not run. Its premise, that the change was
  byte-identical, held on this Mac only.

*Settled by Claude.*
- The stand-ins for "a real large-cell pattern", under the shift's brief (say
  which, and why) and the Context's own question, which is the instrument
  profile and not the cell. Alternative: Durham's ZrP₂O₇ (Pa-3, a ≈ 24.7 Å)
  in the local data root, dropped because its file is a multi-range VT
  series with two internal standards and the Durham input models it as a
  subcell.
- Priority stays P2 provisional, settled by Claude under the line's own
  trigger, which needed both WP-2317 task 1 and this task 1, and only this
  one is in. Alternative: P3 now, on the rubric's "a cost-only item with no
  user at the wall".
- `crossed` and `slack` still multiply the padded T. Dropping its zero
  columns there goes through a matrix-vector product, whose BLAS kernels sum
  in SIMD lanes, so the order and the last bit can change. That is a
  rounding move for Angle 1, settled by Claude under Angle 0's byte-equal
  bar. Alternative: take it as R0 (a)'s working reading allows.

*Gotchas.*
- Probe 1 takes `PROFILE=0` for a wall. A main snapshot runs from a
  `git archive` of `origin/main`'s `src/` with `PYTHONPATH`, never `-I`.
- One captured call is 82 MB pickled (two 41 MB T blocks).
- The cached |T| is a second dense copy of each block, 41 MB a block at
  1 601 reflections, for 1.8 ms a `crossed` call. Narrowing it to the
  columns T reads is Angle 1's, with `slack`.

*Review* (`/code-review high --fix`): no correctness finding. It widened
`test_the_rows_in_z_…` so odd seeds spread T's columns over the whole
problem (taken; the spread form also measured byte-equal on 40 shapes under
OpenBLAS and Accelerate). It asked for ranges on the single-run walls
(answered by labelling them one run) and flagged the |T| copy (kept, above).

*Next.*
1. The maintainer's answers to WP-2317's R0, R4 and R5, and WP-2317 task 1's
   pattern. A pattern that does not cross makes this WP P3.
2. If it crosses: Angle 1, the pruned box rows and width rows. It targets the
   nnls solve, 68 % of the step, whose problem has 1 619 box rows and 6 424
   width rows where a handful bind. Then Angle 2 for `eigh`.
3. Why probe 1's `profile` stage presses on Γ_L at 120° even with a strain
   term in its truth is unmeasured. It decides whether the probe is a fair
   stand-in for a user's lab pattern.

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

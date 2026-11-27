# WP-2315 — a large Pawley step pays for the rows that bind, not for every intensity

Milestone: unscheduled · Status: ⬜
Track: A large cell
Depends on: 2313 soft (its `bigcell-pawley` case and rulings R4, R5)
Priority: P2 2026-11-27 — a user at the wall on a path the structure-free default is moving to (WP-2062) and every `index_pattern` validation already runs: a 1 601-column Pawley fit spends 60 % of its 89.5 s in a dense step solve that grows as about the cube of the reflection count

A Pawley step that crosses a width row costs about what a box-only step costs:
the small profile block carries the rows, and the intensity block keeps its sparse,
projected solve. The ILU preconditioner is not rebuilt more often than the free
set changes. On the 1 601-column bench case the Pawley fit runs at least 3× faster
(target), at an Rwp and profile within the TRF/LM envelope WP-1953 measured.

## Context

**The measurement** (WP-2313 probe 1; Linux x86_64, 4 cores, `[dev]`, compiled
tier on, under cProfile; 12 × 36 × 4 Å, P2₁2₁2₁, Cu Kα doublet + FCJ,
`mccusker_default`, `mode="pawley"`):

| | 899 columns (2θ ≤ 90°) | 1 601 columns (2θ ≤ 120°) |
|---|---|---|
| fit wall | 23.6 s | 89.5 s |
| `lm._solve_constrained_step` | 18 calls, 10.3 s | 24 calls, **53.5 s** |
| → `scipy.optimize.nnls` (in `_least_distance`) | 36 calls, 4.1 s | 48 calls, 26.3 s |
| → `numpy.linalg.eigh` | 33 calls, 2.4 s | 39 calls, 10.5 s |
| `bccg.projected_cg` (the box-only step past 128) | 63 calls, 3.6 s | 67 calls, 15.5 s |
| → `spilu` (`bccg._factor`) | 583 calls, 2.5 s | **1 099 calls, 10.6 s** |
| Jacobian | 3.4 s | ~7 s |

The constrained step went from 10.3 s to 53.5 s (5.2×) for 1.78× the columns,
which is close to cubic. At 6 477 reflections (0.459 Å to 50°, WP-2313's
count table) it would dominate any fit.

**The seam.** `lm.minimize` (`src/rietx/optimize/lm.py`, the inner loop near
`:590`) takes the box-only step from `_solve_step`. Past
`BVLS_MAX_COLUMNS` = 128 that step is `bccg.projected_cg` on a sparse A
preconditioned by the free block's incomplete LU (WP-1953, WP-2011). It then
checks `iq.crossed(x, step)` for every `LinearInequality`. On a crossing it
calls `_solve_constrained_step` (`:955`), which:
- **densifies a sparse A** ("the route is an eigendecomposition");
- takes a full `eigh` of the n × n equilibrated matrix;
- poses the least-distance problem with **every** box limit as a row (±s_i,
  so 2n rows) plus the inequality rows;
- solves it by `nnls`.

This happens "whatever `BVLS_MAX_COLUMNS` says", as WP-1938 put it.

**Which rows bind.** The rows are `gaussian_width_inequalities` and
`lorentzian_width_inequalities` (`src/rietx/optimize/least_squares.py:2761`,
`:2888`): Γ_G² ≥ 1e-8 deg² and the Lorentzian twin, one row per (reflection,
line) after de-duplication, each affine in the free profile columns (u, v, w,
gauss_size, gauss_strain; x, y, lor_*). **Every row is zero on every
intensity column.** So the constraint lives in a ≤ ~10-dimensional subspace,
and the n-dimensional dense solve is spent on a block the rows never touch.
Most rows in a 3-5-dimensional space cannot be active together. Only the
extreme-θ rows (the hull) can bind.

**Why it was left.** WP-1938's fifth session: "neither changed, because neither
reaches a fit … neither Pawley crossed a row". Forced onto FAP's 343-column
system the constrained step took 42-70 ms against BCCG's 0.4-1.9 ms. WP-1953's
Non-goals: "measured and closed in WP-1938". This cell crosses rows 18-24 times
a fit, so the premise is gone. Also note: `index_pattern`'s validation fit is
Pawley since WP-2011, so a large candidate cell (a supercell especially) pays
this per candidate.

**What practice does** (`docs/practice.md` § Peak-width limits): GSAS-II floors
the Gaussian variance and Lorentzian width per reflection **by value**, FullProf
sets Γ_G = 1e-10, RIETAN-FP rejects a step to a negative width. None solves a
constrained step. rietx's choice (WP-1938 D8, WP-2153) is to hold the floor
inside the step. That is ruling R4 in WP-2313, and the angles below that keep
it need no ruling.

**Angles, ordered by the ruling each needs:**
1. **Row pruning** (no ruling). Pass `_solve_constrained_step` only the rows
   that can bind: those the box step crossed, plus those within a slack of the
   current point, re-adding any the solved step violates. Likewise only the box
   rows of variables on or near their bound. The LDP shrinks from 2n + rows to
   tens. The answer is the same problem's answer, so the step is exact.
2. **Block elimination** (no ruling). The rows touch only the profile block
   P, so solve the constrained problem in P with the intensity block I
   eliminated: H_PP − H_PI H_II⁻¹ H_IP (Schur), with I's own box handled by the
   projected CG at the chosen P. This is exact if I's active set is held for
   the solve and re-checked after. H_II is banded plus low rank (WP-1902's
   note).
3. **Preconditioner reuse** (no ruling). 1 099 `spilu` builds over 67 solves
   means the factor is rebuilt per restart or per λ. λ shifts only the
   diagonal. Reuse the factor while the free set is unchanged, or use a
   block-Jacobi preconditioner, and measure iteration counts against the build
   cost.
4. **The fallback as the step** (no ruling; convergence changes). Past 128,
   shorten the box step to the first row it reaches (today's
   `_NoConstrainedStep` fallback). WP-1953's caveat: from a point already on a
   face this gives τ = 0, so λ must rise.
5. **Clamp by value, as GSAS-II and FullProf do** (ruling R4). The rows leave
   the step for a Pawley block past 128. `PEAK_WIDTH_NOT_POSITIVE` (TRF's guard
   today) reports the clamp.
6. **Profile out the intensities** (ruling R5). A bounded VarPro: LM over the
   profile columns, the intensities by NNLS per evaluation. It has fewer
   columns, and the esds are marginalised over the block (the VarPro invariant's
   "correctness" half). It is a different method, so it is the WP-2062
   conversation.
7. Measure `solver="trf"` on the same case first. TRF never sees the rows, so
   it is angle 5's cost model without the ruling.

**Bar.** WP-1953's yardstick: LM and TRF answers on FAP.XRA agree to ~1.5 esd
on the profile, with the gap mostly in the intensities. Under WP-2313's bar a
change here may move Pawley numbers. The test is that the new answer is no
further from the established programs' and from the certificate (WP-2072's SRM
660c, in flight) than today's.

## Non-goals

- Which structure-free method is the default: WP-2062.
- The Stephens cone and texture rows (`strain_cone_inequalities`,
  `texture_positivity_inequalities`) beyond what angles 1-2 give them for free.
- The Pawley restraint rows and their scale: WP-2311 (closed) and WP-1459.

## Tasks

- [ ] Re-measure `bigcell-pawley` (WP-2313) unprofiled, best of three, plus
      `solver="trf"`. Record crossings per stage (`truncated_by`) and the rows
      active in each constrained solution.
- [ ] Row and box-row pruning in `_solve_constrained_step`, with the re-add
      loop. Test: on the existing constrained-step unit cases and on the bench
      case, the pruned step equals the full step to the polish tolerance
      (`_POLISH_FEASIBLE`).
- [ ] Preconditioner reuse in `bccg`: measure builds and CG products per solve,
      before and after.
- [ ] If 1 and 3 leave the constrained step above ~10 % of the fit: block
      elimination (angle 2), with the same equality test.
- [ ] Put the R4/R5 angles to the maintainer only if 1-3 miss the target, with
      the measured remainder.
- [ ] Tests: FAP.XRA and NAC Pawley protocols unchanged within their recorded
      envelope; the bench case's Rwp and profile within it.
- [ ] Skill: none (no API change).

## Acceptance

`bigcell-pawley` at 1 601 columns ≥ 3× faster than WP-2313's unprofiled
"before" (target; the measured factor is what is recorded). The constrained
step is under 10 % of the fit. Every Pawley acceptance number is within its
recorded envelope.

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
  (variable projection, angle 6).

## Handover log

- **2026-11-27** — created.

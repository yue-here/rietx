# WP-2315 — a large Pawley step pays for the rows that bind, not for every intensity

Milestone: unscheduled · Status: 🔄 2026-11-27 — task 1, the cached |T| (Angle 0) and Angle 9's lattice merge (R5 (b)) done; Angles 0 (blockwise G·E⁻¹), 1-2 and 4 open
Track: A large cell
Depends on: 2317 soft (its `bigcell-pawley` case and rulings R0, R4, R5)
Priority: P2 2026-11-27 — the maintainer's large-cell track, ruled to proceed whatever the user's case shows (cells this size are met in the wild); real patterns on the tree reach the slow step once in 32 runs, but a large Pawley cell reaches it

## Goal

A Pawley step past `BVLS_MAX_COLUMNS` that crosses a width row costs about what a
box-only step costs, because two things change:
- the constrained solve sees only the rows and box limits that can bind;
- the work the dense route spends on the intensity block goes.

On `bigcell-pawley` at 2θ ≤ 120° the fit runs at least 3× faster (target), with
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

### Inherited

- **From WP-2317, 2026-11-27 (task 2 and the cross-code timing).** The bench
  cases are `bigcell-pawley` (2θ ≤ 90°) and `bigcell-pawley-120` in
  `examples/bench_refinement.py`; their ranges are in WP-2317's Context. GSAS-II
  5.8.4 on the same patterns and free set took about 2.5-3× rietx's wall and
  landed at Rwp 0.0702 and 0.0610 against rietx's 0.0447 and 0.0420. 41-43 % of
  GSAS-II's χ² sits below 6°, the tail of (0 2 0) at 4.9°, which GSAS-II does
  not draw. The measurement that bears on angle 7 and R5: GSAS-II ties
  reflections whose d agree to 1e-4 (`GetPawleyConstr`), and this cell has
  b = 3a exactly, so it refines **352 independent intensities at 90° and 540
  at 120°, where rietx carries 913 and 1 606 columns**. rietx holds an exact
  overlap by an equal-split restraint row; GSAS-II removes it from the
  dimension.

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
- [x] Angle 0, its bit-identical part. *Done 2026-11-27:
      `LinearInequality.crossed` keeps |T|, bit-identical by construction.
      The blockwise G·E⁻¹ (`lm._rows_in_z`) was byte-equal on macOS
      Accelerate and arm64 OpenBLAS and not on x86_64 OpenBLAS (Linux CI,
      and Rosetta here), so it was withdrawn to the next item.*
- [ ] Angles 0 (blockwise G·E⁻¹), 1 and 2. The blockwise, pruned and Cholesky
      steps equal to the full step within the
      polish tolerance (`_POLISH_FEASIBLE`) on the existing constrained-step cases
      and the bench case. The audit row for the slack.
- [ ] Angle 4, measured.
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
  maintainer's CLAUDE.md sends stored-format changes to him, so it waits for
  his word before merge.
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

*Left undone.*
- `solve/cost.py`'s nuisance columns are not merged.
- torch is not installed here, so the `pawley_merged` torch rows did not run.

*Next.* (1) The maintainer's word on the stored-format addition, then merge
PR 1869 after the `wp2317-rulings` PR. (2) Angles 1-2 and 4 on the bench case,
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

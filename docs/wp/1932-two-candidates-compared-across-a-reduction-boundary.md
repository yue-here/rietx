# WP-1932 — two candidates compared across a reduction boundary

Milestone: unscheduled · Status: ✅ 2026-10-23 — dedup and `same_lattice` join one lattice's descriptions across every Niggli boundary through Selling's form, and the bethanechol benchmark's grades did not move (PR #949)
Track: What fires, and what stays silent
Depends on: — (1923 soft: the same `reduce.py` seam and the #797 cell; 1915 soft: the covariance the distance's esd reads)

## Goal

Whether two indexing candidates are the same lattice is decided by a distance
that is continuous across the Niggli reduction's boundaries (NCDIST in G6, or
the S6 distance), with the reduced cell kept as the grouping key.

## Context

Issue #834 (mustachefeeling, 2026-10-08).

**Today.** `engines.dedup_groups` (`indexing/engines.py:1430`) Niggli-reduces
each candidate's A..F and compares the reduced vectors with
`reduce.equal_reduced` (`reduce.py:414`): a χ² on Δ under the summed
covariances against `CELL_EQUALITY_CHI2` = 16.8119, or, without covariances,
every component within `CELL_EQUALITY_RELATIVE` = 5e-3. The stacked form is
`equal_reduced_many` (WP-1519). `reduce.same_lattice` (`:503`) asks the same
question for two unreduced vectors. WP-1518 fixed the frame each covariance
is read in (77-98 % of real comparisons were weighed in the wrong one).

**The problem #834 names.** Niggli reduction is a canonical form with decision
boundaries. Near one, two descriptions of one lattice can reduce to
different sides, and a comparison of reduced forms then calls them distinct.
WP-1923's #797 trace is one instance: at ε = 7.2e-5, `normalize` gives E the
opposite sign of the exact image, |E| = 1.75e-5 inside ε. 1923 makes that one
reduction an exact change of basis. This WP makes the *comparison* indifferent
to which side a reduction fell.

**Prior art.** Andrews & Bernstein (1988) define G6, where Niggli reduction is
a set of boundary reflections. Andrews & Bernstein (2014) give NCDIST, a
distance continuous across those boundaries. Andrews, Bernstein & Sauter
(2019) show the Selling/S6 form has simpler boundaries and give its distance.
A database keys records by a canonical form and matches them by a metric, for
this reason. **Licensing:** build from the papers. Before reading any
implementation, check its licence against ATTRIBUTION.md's rules.

**The proposal** (#834): keep the reduced cell as the dedup key; replace
`equal_reduced`'s χ² with NCDIST or the S6 distance; propagate the candidate
covariance into G6 (A..F are G6 coordinates up to the factor 2 on D, E, F)
and report distance over its esd; `same_lattice` uses the same test. The
engines' search is unchanged.

**Checked against the tree at `a3f9140a`:** every symbol named exists where
the issue says. Not measured, by the issue or here: whether any comparison
on the indexing acceptance corpus or the bethanechol benchmark splits one
lattice across a boundary today. That count is the first task, since the
priority rests on it.

**Consumers of the test** (grep at `a3f9140a`). `dedup_groups`, both its
pairwise (`engines.py:1543`) and stacked (`:1601`) paths; `same_lattice` in
`ambiguity.py:179` and in `priors.py:345`, which matches a candidate against
a prior cell; and WP-1921's planned `find(cell=)`, whose acceptance holds it
equal to `equal_reduced_many` on every pair.

**What this WP inherited, and where it went at the close (2026-10-23).**
WP-1923's moved sign boundary and #834's count were the first task's input,
and the recount on 2026-10-13 replaced both. WP-1930's negative χ² was fixed
there for the pair test, and here for the image test (`_psd_pinv`, PR #949).
WP-1930's F-centred hypothesis counterexample to
`test_the_reduced_cell_is_the_exact_image_of_its_input` still fails on
`12f459e`, and is [WP-2035](2035-a-reduced-cell-is-its-inputs-exact-image.md).

## Non-goals

- The #797 reduction being an exact change of basis, and the conventional
  setting a candidate is reported in: WP-1923. 1923's own non-goal keeps
  `dedup_groups`' grouping unchanged, which is why this is a separate WP.
- What the engines search.
- NaN esds from an unmeasured A..F direction: WP-1915.

## Tasks

- [x] Measure first: on the WP-1518 acceptance corpus and
      `tests/data/bethanechol_indexing.json`, count the pairs that one
      lattice's two descriptions reduce to across a boundary, and how many
      `equal_reduced` then calls distinct. Re-rate Priority from the count.
- [x] Choose NCDIST or S6, with the reason (boundary count, cost per pair
      against `equal_reduced_many`'s stacked solve), and its esd's
      propagation from `cov_af`.
- [x] Replace the test in `equal_reduced`, `equal_reduced_many` and
      `same_lattice` from one implementation.
- [x] Run `tests/test_acceptance_indexing.py` and the bethanechol benchmark
      alone (root CLAUDE.md: engine budgets are wall-clock), listing every
      group and grade that moves. **No grade moved**: global −7 on #949's
      merge and on its first parent, set for set (2026-10-23 entry).
- [x] Tests: the #797 `red` and `t @ af` at distance 0; a pair either side of
      each Niggli boundary type.
- [x] Skill: none expected, since a candidate list's shape does not change;
      say so in the handover or add the row if a field lands.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_reduce.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m tests.bethanechol_benchmark
.venv/bin/python -m ruff check src tests examples
```

No pair `equal_reduced` joined correctly is separated, and every group that
moves is listed in the handover with its cause.

## References

- Issue #834; #797 and #779 (WP-1923); WP-1518, WP-1519, WP-1921.
- Andrews, L. C. & Bernstein, H. J. (1988). *Acta Cryst.* A44, 1009-1018,
  doi:10.1107/S0108767388006427.
- Andrews, L. C. & Bernstein, H. J. (2014). *J. Appl. Cryst.* 47, 346-359,
  doi:10.1107/S1600576713031002; erratum 47, 1477.
- Andrews, L. C., Bernstein, H. J. & Sauter, N. K. (2019). *Acta Cryst.* A75,
  115-120, doi:10.1107/S2053273318015413.
- Bergmann, J. et al. (2004), the bethanechol benchmark
  (`tests/data/bethanechol_indexing.json`).

## Handover log

- **2026-10-23** — closed. The graded bethanechol benchmark ran alone on
  #949's merge (`65fc6fe`) and on its first parent (`2e5b5eb`), and no grade
  moved. Both trees score global −7 over 20 runs (default −4, manual −3).
  Every set has the same truth rank, score, `truth_found_by` and candidate
  count on both. Bb and E are at rank 1 in both modes, Db at rank 1 in
  default and rank 2 in manual, F at rank 1 in manual, and the rest are
  unfound.
  *Groups that moved.* In 5 of 20 runs the 12 listed candidates regrouped,
  and none of the five finds the truth on either tree. Aa manual: the nearest
  cell went from rank 1, 123 333 ppm to rank 5, 116 253 ppm. Ba manual: rank
  11, 197 522 ppm to rank 12, 181 468 ppm. Da manual: rank 9 to 10 (183 705
  to 183 596 ppm), and a different `low` monoclinic cell on top (V 1077.6 to
  1042.3 Å³). Cb default: the same nearest cell went from rank 9 to 10. F
  default: the same nearest cell went from rank 9 to 10, and the top went
  from a `low` monoclinic cell (V 1129.2 Å³) to a `low` triclinic one
  (V 614.8 Å³). Every listed top is `low` on both trees.
  *Acceptance file.* It was not re-run here. It ran inside the full `-m slow`
  suite on trees carrying #949: 2268e525 (WP-1343's 2026-10-15 entry) and
  `main` `1661895e` stacked with #1071 (WP-1326's 2026-10-22 entry, 326
  passed, 12 skipped, 1 xfailed, macOS arm64).
  *Measured* (`[dev]` with `rietx_kernels` 1.3.0, Linux x86-64, 4 cores,
  Intel Xeon, a cloud container with nothing else running, load ~1). Each
  tree was imported from its own extracted source. Per-run wall: default
  244.6-383.0 s on the parent and 250.9-402.5 s on the merge (merge/parent
  1.02-1.12 run by run), manual 83.8-103.3 s against 83.6-113.9 s
  (0.99-1.13). The container restarted between the two runs (parent 12:39-13:48
  UTC, merge 14:26-15:39 UTC). Same core count and CPU model, but whether it
  was the same host is unknown, so the wall ratio is not quoted as #949's
  cost. The grades need no such caveat, since they agree set for set.
  *Gotcha, for WP-1924's open question.* `indexing/qspace.py:410`
  (`cov_af = basis.T @ cov… @ basis`) printed `RuntimeWarning: invalid value
  encountered in matmul` on Aa default on **both** trees. So it predates #949,
  and it is on `main`'s lineage, not WP-1924's branch alone.
  *Inherited:* four bullets, consumed. Three were discharged here or in WP-1930.
  The fourth, the F-centred counterexample, still fails at `12f459e` (G₃₂ off
  by 1.1e-7 of max|G|) and is now WP-2035. *Next:* nothing owed here. Issue
  #834 stays open, since this WP built only its matching half (2026-10-15
  entry).
- **2026-10-15** — PR #949 (outside contributor) merged as `65fc6fe0`.
  @yue-here answered the PR's three questions in round 1 (2026-10-14). A joined
  pair reports the χ² of the description that joined it. The 1.35-1.63× dedup
  wall clock is accepted, with the boundary search on every system.
  Hand-writing Selling's reduction is within the module's rule, because
  gemmi's keeps neither the four vectors nor a step through a boundary.
  Round 1 asked for three more fixes, all made. The image test inverts Σ
  with `_psd_pinv` at `CELL_PINV_RCOND`, the stacked-form test skips where
  LAPACK rounds a stack differently, and Part 2 describes the comparison
  with Andrews, Bernstein & Sauter (2019). Tasks 1-3, 5 and 6 are done. Task
  4's acceptance half ran in the stack's slow gate (tree `2268e525`, counts
  in WP-1343's entry of today). Its graded bethanechol benchmark has not run
  on the merged tree. The contributor's 429-call dedup replay is a group
  count, not the benchmark's grades. #834 stays open: this builds its
  matching half. *Next:* the benchmark run alone, listing every grade that
  moves, then close.
- **2026-10-13** — Dedup and `same_lattice` no longer call one lattice two
  when its descriptions reduce either side of a Niggli boundary. A pair the χ²
  calls distinct is now asked again of the second cell's other descriptions in
  Selling's form, and joined when one passes the same χ². Every split #834
  counted now joins, the groups match an exhaustive oracle on all 602 logged
  dedup calls, and a pair the old test joined is answered exactly as before.
  The price is dedup's wall clock, 1.35× on the acceptance searches and 1.63×
  on bethanechol. Next: Yue's read of the three questions on the PR.

  *Done.* Tasks 2 to 5. **S6 over NCDIST, from a spike that built both from
  the papers** (no implementation opened). As exact images decided by rietx's
  χ², an NCDIST-style set (24 unrollings × one crossing of each of the 15
  boundaries) joined 595 of 608 recorded splits and missed 13 reduction-step
  ones in one bethanechol call. Selling's images (24 relabellings × one step on
  a's side and up to two on b's, 2019a § 4, 2019b § 4.1) joined 608 of 608 and
  cost 27 % less per pair. **The decision is the χ² on the matched image, not
  the distance over its esd**: projected on one direction, d/σ_d merged 76 of
  76 real distinct pairs at z ≤ 2.576 that the oracle refuses. One
  implementation, `reduce._equal_across_boundaries`, serves `equal_reduced`,
  `equal_reduced_many` and `same_lattice`. A gate on the sorted Selling
  scalars, a lattice invariant continuous across every boundary, at
  `SELLING_GATE_SIGMAS` = 1.25·√χ² of their linear esds
  (`SELLING_GATE_RELATIVE` without covariances), decides which pairs are
  searched. The same bound selects images slot by slot. Dedup hands each
  stacked solve its groups' packed gate inputs. Selling's reduction is written
  here because `gemmi.GruberVector.selling` keeps neither the four vectors nor
  a step through a boundary. Tests: `tests/test_indexing_reduce_boundaries.py`
  (42), on `tests/data/wp1932_boundary_pairs.json`, holding the 8 LaB6
  splits, 10 bethanechol ones, 6 near-boundary distinct pairs, constructed
  pairs either side of each boundary kind and moved 50-500 esds, the #797 pair
  at χ² < 1e-6, and a revert check. The skill: none, since a candidate list's
  shape does not change.

  *Measured* (Mac, `.venv-test`, other sessions' suites running; pearl
  offline). On the 2026-10-09 probe (tree 9219e886), all 4 784 bethanechol and
  8 LaB6 splits join. Of 3 000 random called-distinct pairs none joins, and of
  3 000 called-equal pairs none changes. Replaying every logged dedup call on
  this tree, every call's group count equals the oracle's: acceptance 173 of
  173 (two LaB6 calls regroup, net 0), bethanechol 429 of 429 (150 calls
  change, 178 875 → 178 301 groups). Groups that move in acceptance: LaB6's
  tetragonal (4.1568, 4.1568, 4.1517) group absorbs the (4.1559, 4.1559,
  4.1627) one, ranks 3 and 6 of 12 on 9219e886, both `low` and found by all
  three engines. `tests/test_acceptance_indexing.py`: 44 passed in 17 min.
  Bethanechol, shortest form, against a main checkout (1307cb2f3) on the same
  machine: F/default truth rank 3 twice on this branch, 4 twice on main (score
  0 both); Db/manual rank 2 on both; Ab/default and Cb/manual no truth on
  either. No truth `found_by` and no grade moved; every listed cell is `low` on
  both. F/default took 371 s twice against 328 and 352 s on main.

  *Gotchas.* A replay timing split across two processes measures the load, not
  the change: the same 51 calls took 8.7 s and 30.3 s on main an hour apart.
  Time both passes interleaved in one process. A per-vector cache of the
  two-step Selling tree was measured and not kept: it answered identically on
  24 784 pairs and ran no faster.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #834).
  Checked against the tree at `a3f9140a`: the named functions and constants
  are where the issue says. No open WP owns the equality test: 1923 shares
  the seam and fences dedup's grouping out as a non-goal; 1518 and 1519 are
  closed; 1921 is a consumer. The reporter names this the proposal they
  would take on first.
- **2026-10-14** — from the PR review (PR #949): the three questions answered
  by @yue-here. (1) A joined pair reports the χ² of the description that
  joined it. (2) Dedup's 1.35-1.63× wall clock is accepted, and the boundary
  search stays on every system. (3) Hand-writing Selling's reduction is within
  the module's rule, since gemmi's keeps neither the four vectors nor a step
  through a boundary. Round 1 at `89c5b3e2` asks for a rebase (the 1.9.0
  notes conflict after #964), `_psd_pinv` in the image path in place of
  numpy's signed `pinv`, a skip on `stacked_pinv_exact`, and the Part 2 dedup
  paragraph. *Next:* #949's round 2.

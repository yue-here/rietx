# WP-1969 — an exhaustive search that ends in no cell

Milestone: unscheduled · Status: 🔄 2026-10-24 — PR #951 (`ed1c1958`) and PR #1042 (`377c5724`) merged from outside; two measured follow-ups remain
Track: What fires, and what stays silent
Depends on: 1956 soft (the line screen, PR #941, may let the inlier rule become the default)
Priority: P2 2026-10-14 — a defect that fires wrongly: a completed search abstains on a list with three or more stray lines, and raising the count returns oversized cells; declaring the count by hand is the workaround

## Goal

A search over a list carrying more off-lattice lines than the fixed allowance
still returns the true cell when the engines can find it. Every cell says how
many driven lines it left unindexed, and which.

## Context

**Source.** Issue #933 (2026-10-13). `indexes_the_search_lines` accepts a
cell only if all but `n_unindexed` (default 2) of the driven lines index. The
issue's case is synthetic Si (F d -3 m, a = 5.4311 Å, λ 0.8257 Å, 12.1–60°)
with 12 Gaussian lines planted at 1–5 % of the strongest, 53 usable lines in
all, searched cubic under `preset="full"`. At a count of 2 the truth is absent
and rank 1 is a 15.60 Å primitive cell indexing 53 of 53. At 3 the truth is
absent and rank 1 is cP 7.68 Å. At 8 the truth ranks first, graded low by
`indexed_fraction_low` for the same 17 lines the count admitted. So the count
chooses between silence and a large cell that has a line everywhere.

The proposal is an inlier rule of the RANSAC kind (Fischler & Bolles 1981):
accept a cell whose inliers number at least max(n_dof + 4, f·N), with the k
strongest driven lines among them (f ≈ 0.6, k ≈ 5). It also asks for the
unindexed count and intensity share as numbers, the unexplained lines as a
residue list, `indexed_fraction_low` read on the intensity-weighted fraction,
and a second pass on the residue.

**Checked against the tree at `ee589bab`.** `indexes_the_search_lines` is
`indexing/engines.py:1207`, `DEFAULT_N_UNINDEXED = 2` is `engines.py:169`, and
`INDEX_IMPURITY_LINES` is `indexing/diagnostics.py:607`. The issue gives no
seed for its planted positions, so its table was not reproduced here. PR
#951's spike `synth_c4.py` reproduces it (count 3: truth absent; count 8:
rank 1).

**Decided 2026-10-14** (the maintainer, answering the PR-review batch): yes,
as PR #951 builds it, with a free hand beyond it ("go nuts"). The PR's
questions, and one from the review, answered:

1. The inlier rule is a retry when no two engines agree, not the default for
   every run. As the default it moved SRM 660c LaB6's certified cell from
   rank 1 to rank 3, because the anchors shrink the pool Borda ranks.
2. Widening the retry (brucite's case, where every agreed lattice is a
   refuted supercell), or making the inlier rule the default once WP-1956's
   line screen lands: outside #951, and welcome as a measured follow-up that
   keeps LaB6 at rank 1.
3. A window sized from the peak widths keeps `shift_allowance_assumed`. The
   shift itself is still unmeasured.
4. `"inliers"` stays API-only in #951. A GUI select is welcome as a
   follow-up.

#951 does not build the intensity-weighted `indexed_fraction_low` or the
second pass on the residue. Both are tasks below.

### Inherited

- **2026-10-14, from the issue triage: issue #933 is in PR #951 (theirs,
  head `a215e460`).** `SearchSpec.n_unindexed` takes `None` (the new
  default), `"inliers"` or an int. `None` keeps the count of 2 and, when no
  lattice has two engines agreeing, searches again under the inlier rule
  (`INDEX_INLIER_RETRY`). `SearchSpec.miss_budget` and
  `engines.search_acceptance` are the one authority every engine, the
  dichotomy prunes and the panel's trim read. `CellCandidate` gains
  `n_search_unindexed` and `unindexed_two_theta` (schema 0.51 to 0.52). The
  PR also sizes the search window from the list's lower-quartile fitted FWHM,
  capped at 0.05° (`engines.width_allowance`, its C6). On the issue's
  reproducer the default returns the truth at rank 1 from all three engines.
  Brucite's acceptance row loses its truth at a count of 2 on `main` as on the
  branch, and passes because it declares 3. It takes
  `INDEXING_THRESHOLDS_VERSION` 1.10, as five other open PRs do.

- 2026-10-31, from the issue triage (issue #1198, about draft PR #1043): the
  second pass on the residue (this WP's open follow-up, `index_residue` in PR
  #1043) was measured on 26 real runs, the IUCr CPD round robin sample 1
  (cpd-1a … 1h, Madsen et al. 2001) and the 11-BM LaB₆ + cBN mixture, each
  phase subtracted in turn with its true cell passed as `candidate=`. With the
  residue fit in Le Bail, its free widths ran away on balanced mixtures
  (fitted/measured FWHM 6.4-2692×) and the width guard refused 17 of 26 runs.
  Since PR #1043 runs that fit in `VALIDATION_MODE` (Pawley, after #1191;
  pushed `c82d9b23`), 1 of 26 is refused (cpd-1b with a 1.4 wt % trace
  subtracted, correctly) and widths sit at 0.87-1.7× on 25. So the runaway is
  gone from what `index_residue` runs. Checked against the tree at d87c8cc91:
  `index_residue` is not on `main`; `validate_by_lebail` takes no mode
  argument there and fits in `VALIDATION_MODE = "pawley"` (`workflow.py:119`,
  `:529`), so no public call on `main` reaches the Le Bail runaway. What still
  stands: with the largest phase subtracted, the second search finds the true
  minor phase in 0 of 8 CPD lab mixtures, so the miss is in the second search,
  not in the fit. With widths held, `residue_misfit` flags 0 of 103 true
  minor-phase lines, and SRM 660c alone returns LaB₆ itself as a "second
  phase" because a declared width law at 0.63× the measured one passes
  `WIDTH_MISMATCH_RATIO`. The measurement behind #1043's
  `RESIDUE_MISFIT_RATIO` is the same run (tables at PR #1043,
  issuecomment-6515145543). Whether `index_residue` may claim real-mixture use
  before the second search finds lab-Cu minor phases is the maintainer's
  decision.

## Non-goals

- The absent-line side of acceptance (WP-1956, PR #941).
- The picker's false lines (WP-1968).
- Le Bail evidence between proposed cells (WP-1511).

## Tasks

- [x] **Decision (maintainer):** the issue's proposal, whole or in part,
      recorded as `Decided YYYY-MM-DD:` here and answered on #933.
      *Decided 2026-10-14: yes, as PR #951 builds it, and a free hand
      beyond (Context).*
- [x] Review and merge PR #951.
- [ ] Follow-up, after WP-1956 lands: widen the retry's trigger or make the
      inlier rule the default, measured, with LaB6's certified cell kept at
      rank 1.
- [x] Follow-up: `indexed_fraction_low` on the intensity-weighted fraction
      of the driven set, so a truth explaining most of the intensity is not
      capped by its own impurities.
- [ ] Follow-up: a second pass on the residue, picked at the first cell's
      width law and indexed again, reported as a second result.
- [x] Tests, and `tests/test_acceptance_indexing.py` green.
- [x] Skill: the `INDEX_INLIER_RETRY` row (#951 puts it in
      `references/abstention.md`).

## Acceptance

On the issue's reproducer the default search returns cubic F 5.431 Å at
rank 1. Every indexing acceptance row ranks as on `main`.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #933; PR #951.
- Fischler, M. A. & Bolles, R. C. (1981). *Commun. ACM* 24, 381: acceptance
  by inlier count (RANSAC).
- Le Bail, A. (2004). *Powder Diffr.* 19, 249: impurity fractions under which
  the correct cell generally ranks first.

## Handover log

- **2026-10-24** — PR #1042 merged (`377c5724`, review round 3), by `/pr-review`.
  *Done*: the second follow-up. `indexed_fraction_low` now reads the share of the
  usable lines' *intensity* a cell indexes (`indexed_intensity_fraction`, falling
  back to the line count where there is none). A line count under the bar adds
  the capping caveat `indexed_lines_low` (an `IndexCaveat` member, no new
  field). On SRM 660c with three or six weak impurity lines the certified cell
  goes from `low` to `medium`; no other indexing acceptance row changes grade.
  `INDEXING_THRESHOLDS_VERSION` stays 1.11.
  *Measured*: round 2 ran the slow rows of `test_acceptance_indexing.py`,
  `test_peak_bounds.py` and `test_indexing_consensus.py` (20 passed); this round
  the whole suite on a stack including it, and the fast selection on the final
  stack `bb654fd0` (11 655 passed, macOS arm64).
  *Gotchas*: `INDEX_MIN_INDEXED_FRACTION` now gates two verdicts, the refuting
  caveat on intensity and the cap on count; its row is on
  `UNAUDITED_BASELINE` and WP-2007 should see both roles. #993 (open) adds a
  1.11 note at the same place in `schemas/indexing.py`; keeping both resolves it.
  The rebase dropped the PR's tutorial 03 edits, since main had rewritten that
  text and names neither caveat.
  Next: the residue pass is #1043 (open, rebase requested 2026-10-24); the retry
  follow-up waits on WP-1956.

- **2026-10-14** — created, from the 2026-10-14 issue triage (issue #933).
  Checked against the tree at `ee589bab`: every symbol the issue names exists
  where cited, and the cap is still an absolute count of 2. No open WP owns
  it. WP-1956 holds the absent-line side, a different seam (the line screen,
  not the engines' acceptance). WP-1511 compares cells a person or a search
  proposes, and the search itself is outside it. The maintainer decided it
  the same day (Context). *Next:* PR #951's review.
- **2026-10-17** — PR #951 merged from outside (`ed1c1958`), closing issue
  #933. Gated with PR #940 and the one-word test fix #1031 on one merged tree
  (`8b8287fb`), macOS arm64, `[dev,jax]` venv, alone on the machine: ruff
  clean; the fast suite 10 854 passed, 120 skipped, 2 xfailed and 1 failed;
  the full `-m slow` suite 321 passed and 12 skipped, which includes
  `tests/test_acceptance_indexing.py`. The fast failure was a wall-clock
  margin in `test_events_aggregator.py` missed by 5 ms under load. It passes
  alone, and neither PR touches the events code. #940 merged first, and the
  two PRs' history lines under `INDEXING_THRESHOLDS_VERSION` 1.11 then
  conflicted as adjacent text. Sync commit `c1d0a785` on the PR's branch kept
  both, #940's first, and after the merge `main` was the gated tree byte for
  byte. The merge makes it possible for a search in which no two engines agree
  to retry under the inlier rule (`INDEX_INLIER_RETRY`), and sizes a
  high-resolution list's search window from its own peak widths. It
  deliberately leaves the inlier rule off as the default (decision 1), and
  `"inliers"` stays API-only. PR #941 (WP-1956) now conflicts with `main` and
  has a rebase request.
  *Next:* the three follow-ups above, each measured with LaB6's certified cell
  kept at rank 1.

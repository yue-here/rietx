# WP-2078 — Weak lines from another phase push the true cell off rank 1

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1969 soft: the inlier rule answers the same failure by another mechanism; 2066 soft: the reporter's dichotomy rows predate it)
Priority: P2 2026-11-02 — a ranking defect with a hand workaround: on the reporter's private benchmark the true cell ranks first on 48 of 172 host and one-impurity lists under all three engines, and on 75 when the search is given only the lines at or above 1 % of the strongest; thinning the list by hand is the workaround

## Goal

On a picked list that carries weak lines the host phase does not own (a
second phase, picker noise), the indexer still ranks the true cell first. A
host whose weak lines are its own (a superlattice) keeps its true cell. A
position-only list searches exactly as it does today.

## Context

**Source.** Issue #1291 (2026-11-01), a proposal by the recurring
contributor, with a re-run on `main` posted the same day. The proposal: index
a picked list on its usable lines at or above 1 % of the strongest usable
line, beside the list as picked.

**What the reporter measured.** An internal benchmark on private patterns,
quoted as counts only. Twenty host patterns (lab, synchrotron and neutron,
including the Si, LaB₆, CeO₂ and Al₂O₃ standards). Three derived families:
imp1 (153 lists, one impurity phase injected each), thin (68 lists, lines
removed at random) and controls. The derived families are not independent of
the hosts. Picking was `pick_peaks` at `PEAK_FDR_Q` = 0.01 with every flag
kept. Truth compared by `rank_of_lattice` (band 5e-3, 0.5°). The re-run is on
`f4db776`, preset `quick`, a 120 s ceiling per list, one thread.

Truth at rank 1 on host + imp1 (172 lists with a truth):

| engine | as picked | 1 % floor | 2 % floor |
|---|---|---|---|
| svd | 40 | 67 | 57 |
| dichotomy | 53 | 71 | 62 |
| trial_error | 35 | 57 | 60 |
| all three | 48 | 75 | 63 |

- Paired against the same engine as picked, the 1 % floor gains on all three
  families and loses no host list. The exact McNemar p lies between 1.5e-8
  and 1.1e-5.
- The 2 % floor loses lists: imp1 +17/−9 under dichotomy and +23/−9 under all
  three, plus a host list under svd.
- Why not higher: two hosts carry structural weak lines (a pyrochlore's
  superlattice lines, a trirutile-type oxide). At 2 % and 5 % the floor
  removes the lines that separate the true cell, and a subcell or a wrong cell
  ranks first. On those hosts the working window is about a factor of 2 wide.
- Controls: no control gains a candidate graded `medium` under any single
  engine. Under all three engines, three controls that contain a real lattice
  gain `medium` candidates on the floored lists. The reporter reads that as a
  grading question (several descriptions of one lattice graded `medium`).
- A strongest-N cap (N = 8 to 20) came close only as five searches merged,
  and fell behind on thin (22 against 25).
- Removing broad lines, dropping tail- or bound-flagged lines, and σ×3 on
  flagged lines did not help.
- The dichotomy rows predate PR #1301 (WP-2066), which changes the dichotomy
  search. The svd and trial_error rows do not depend on it.

**Where the gain is: the searched list.** The re-run split search from
scoring with a harness wrapper. Arm X searched the list as picked, then
merged, ranked and validated against the 1 % list. Under svd it gained
nothing (g = 0.00, where g = 1 would put the whole gain in scoring); under all
three engines g = 0.15. Arm Xr also narrowed the searched systems to those the
1 % list supports, because a list under 20 usable lines searches only
`quality.systems_supported` (`workflow._restrict_to_supported`). That gave
g = 0.26 under svd. So about a quarter of svd's gain is the narrower systems,
and the rest is which lines the search is given. **The reverse split was not
measured**: search on the floored list, score on the full list. That is the
shape of the seam the package already has (below), so it is the cheapest
candidate and task 2 measures it.

**Checked against the tree at `992b7048f`.** Every name the issue cites
exists.
- `engines.search_line_order` (`indexing/engines.py:1140`) drives the search
  with the strongest `DEFAULT_SEARCH_LINES` = 20 lines (`:140`), drawn from a
  low-Q pool of `SEARCH_POOL_MULTIPLE` × 20. Scoring reads every usable line.
  WP-1039 measured that raising N bought nothing and that the rank, not the
  count, fixed `11BM_NAC.fxye`.
- `PEAK_UNDRIVEN_FLAGS = {"weak_line"}` (`schemas/indexing.py:858`) is the
  existing "scored, never driven" seam (#934): a flagged line stays in
  `usable()` and never enters the driven set. Below `DRIVEN_MIN_LINES` = 6
  unflagged lines the strongest flagged ones come back. `weak_line` is a
  significance screen (Benjamini–Hochberg on I/σ_I at `PEAK_FDR_Q` = 0.01,
  `:303`). The issue measured that the harmful lines pass it: moving the q
  from 0.001 to 0.05 moved the false-kept count only from 139 to 151.
- `DEFAULT_N_UNINDEXED` = 2 (`engines.py:173`): a cell is accepted only if
  all but two driven lines index. Reading, not measured: a third non-host line
  among the driven twenty refuses the truth, which is the failure WP-1969's
  inlier rule (`INDEX_INLIER_RETRY`) retries when no two engines agree.
- Ties in `search_line_order` fall back to Q order, and
  `PeakList.from_positions` gives every line weight 1. A relative floor
  therefore removes nothing from a position-only list, and the bethanechol
  benchmark searches unchanged.
- `consensus.grade` (`consensus.py:759`) grades `low` when
  `len(set(found_by)) < MIN_AGREEMENT`. An arm merged "like an engine" under
  its own name would let one engine on two lists count as two opinions. That
  is the hazard the arm design must close: `found_by` stays engine names.
- `rank_of_lattice` is a test helper (`tests/indexing_gallery.py:373`).
- `tests/reader_output.py` diffs a Rietveld fit's printed text. It does not
  cover `str(IndexingResult)`, so this WP shows that diff by hand.

**Prior art, recall plus one in-tree find, not yet surveyed.** The issue found
no relative-intensity floor in ITO, TREOR, DICVOL, SVD-Index, Conograph or
McMaille, whose line limits are counts (M₂₀'s first twenty). One find in this
tree: the bethanechol round robin (Bergmann, Le Bail, Shirley & Zlokazov
2004, *Z. Kristallogr.* 219, 783-790; `tests/data/README.md`) presents each
pattern raw (set A) and as "lines with I ≥ 5 % of Imax" (set B), and its
Table 5 scores eleven programs on both. That is a relative floor used as a
benchmark treatment, not a program default. Whether a GUI front end (TOPAS,
GSAS-II, WinPLOTR for FullProf) offers an intensity threshold when it builds
an indexing list is not checked. `docs/practice.md` has no indexing
line-selection section.

**Tier and the maintainer's gates.** Three gates belong to the maintainer and
none is settled by this file.
1. **The floor's value is a new constant.** Unless the survey finds it as
   established practice (tier 2), it is tier 3, rietx's own. A tier-3 `_audit`
   row needs both grounds and the maintainer's dated `approved` field
   ([generality § The rule](../milestones/generality.md#the-rule)). The
   mechanical ground asks for three unrelated dataset families against a
   reference, with a stated failing case. The reporter's benchmark is private,
   so the public evidence must be built here (task 3).
2. **The default ranking changes**, so `str(IndexingResult)` and
   `CellCandidate` ranks change for a reader. That goes to the maintainer
   before merge. It likely moves `INDEXING_THRESHOLDS_VERSION` (now 1.12).
3. **The kind of action** ([DESIGN § Rules](../DESIGN.md#rules), 1). A hard
   cut acts for every caller. A second arm whose candidates consensus ranks
   with the as-picked arm's lets the data score both. That choice is the
   judgement ground's.

**Cost.** The reporter ran each list under its own 120 s ceiling. A second
arm inside one `quick` run shares one whole-run ceiling, so it either halves
each arm's search or cuts trailing systems. That cost is unmeasured.

**Licensing.** Concepts only from papers. No program code is consulted.

## Non-goals

- The significance screen (`weak_line`, `PEAK_FDR_Q`). The harmful lines are
  real peaks.
- The picker's false lines (WP-1968, closed).
- The acceptance rule and its inlier retry (WP-1969), except as a rival
  measured on the same lists in task 4.
- The absent-line charge (WP-1956).
- The unexplained-lines diagnostics. They keep reading the full list.
- The controls' "several descriptions of one lattice graded `medium`". Task 4
  records whether it reproduces on public controls. If it does, it is filed
  on its own.

## Tasks

- [ ] Practice survey into `docs/practice.md`, a new section on which lines an
      indexing search is given. Rows: TOPAS (LSI and SVD index), GSAS-II's
      indexing, FullProf's WinPLOTR front end to DICVOL, TREOR and ITO,
      Conograph, McMaille, and the indexing literature (International Tables
      Vol. H's indexing chapter, Werner's and Shirley's guidance). Read
      Bergmann et al. (2004) Table 5 for whether the 5 % sets scored better
      than the raw ones. Mark each claim checked or inferred. The section says
      whether a relative floor is practice (tier 2) or new (tier 3).
- [ ] Synthetic fixtures, built in-test from rietx's forward model (the
      reporter offered to write them). (a) A host with an injected weak
      second phase, where the floor must move the truth to rank 1. (b) A
      superlattice host whose weak lines are structural, where the floor must
      not lose the true cell. (c) WP-1969's synthetic Si with twelve lines
      planted at 1-5 % of the strongest, which a 1 % floor mostly keeps.
      Record the truth's rank on `main` under the default.
- [ ] Public measurement families for the tier-3 mechanical ground: the
      indexing acceptance corpus (`tests/test_acceptance_indexing.py`'s
      certified rows), the IUCr CPD round-robin mixtures (`qarr/`), and the
      11-BM LaB₆ + cBN mixture. Say which are development data.
- [ ] Measure the candidates on the fixtures and the families, every engine,
      under `preset="quick"` with one shared ceiling: (1) nothing; (2) the
      floored list searched and scored (the issue's form); (3) the floored
      list driven and the full list scored, through the `PEAK_UNDRIVEN_FLAGS`
      seam; (4) a second arm merged per engine, `found_by` holding engine
      names only; (5) WP-1969's inlier rule as the default. For each: truth
      rank, grade, wall time, controls gaining a `medium` candidate, and
      SRM 660c LaB₆ at rank 1. Floors at 0.5, 1 and 2 %.
- [ ] Decision (maintainer): the design, the floor's value and its tier, from
      the brief tasks 1-4 produce. Recorded here as `Decided YYYY-MM-DD:` and
      answered on #1291.
- [ ] Build what the decision picks, with its `_audit` row and any
      `INDEXING_THRESHOLDS_VERSION` move.
- [ ] Reader-output diff: `str(IndexingResult)` on the acceptance rows before
      and after, in the PR body, for the maintainer.
- [ ] Tests: the three fixtures as rows, a test that a `from_positions` list
      searches bit-identically, obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: a row in `references/` keyed by the new name if the arm or the
      floor shows in the result, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_indexing_driven_set.py tests/test_indexing_consensus.py tests/test_indexing_inliers.py tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

Fixture (a) ranks the truth first, fixture (b) keeps it first, and every
certified row of `tests/test_acceptance_indexing.py` keeps its rank. A
position-only list returns the same candidates as on `main`.

## References

- Bergmann, J., Le Bail, A., Shirley, R. & Zlokazov, V. (2004). *Z.
  Kristallogr.* 219, 783-790. The bethanechol round robin; set B is the
  I ≥ 5 % Imax treatment.
- de Wolff, P. M. (1968). *J. Appl. Cryst.* 1, 108-113. M₂₀ on the first
  twenty lines.
- Issue #1291 and its re-run comment (2026-11-01).
- WP-1039 (the driven twenty), WP-1969 (the inlier rule), #934 (scored, never
  driven).

## Handover log

- **2026-11-02** — created, from the 2026-11-02 issue triage (issue #1291).
  Checked against the tree at `992b7048f`: every symbol the issue names
  exists, and `PEAK_UNDRIVEN_FLAGS` is an existing seam the issue did not
  measure. No open WP owns which lines drive a search. WP-1969 owns the
  acceptance rule on the same failure, and its open follow-up (the inlier
  rule as default) is measured here as a rival rather than folded, because
  it waits on WP-1956 and this does not. WP-1039, which set the driven
  twenty, is closed. The reporter's numbers are quoted from the issue and
  not reproduced; their data is private. *Next:* tasks 1 and 2, which need
  no decision.

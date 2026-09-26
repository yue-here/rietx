# WP-1449 — rank on what the screen determined, not on what the peak list shows

Milestone: unscheduled · Status: 🔄 2026-09-26 — claimed by @yue-here
Depends on: — (1446 measured the refutation; 1025 built the screen)
Priority: P2 2026-09-23 — a wrong cell ranked first on a surface every page calls provisional; 1446 already measured the refutation

## Goal

Order the candidate list using evidence that can tell a space-group absence from
an oversized cell. The peak list cannot, and WP-1446 measured that it cannot.

## Context

**This is a stub. It carries WP-1446's measurement and the questions the
literature has to answer; the design is not written yet.**

**What WP-1446 established.** The indexing panel ranks an a × 2 supercell above
brucite's certified cell, on one extra indexed line, while holding
`predicted_seen_fraction` 0.318 against the truth's 0.862. Ordering a candidate
below any derivative parent whose extra lines the pattern lacks fixes that row.
It also demotes **SRM 676a's own cell** below a c/2 subcell the search returns
beside it, because `R -3 c`'s c-glide leaves 33 of its 35 in-range extras absent.
Wiring it cost four acceptance rows, two on corundum and two on LaB6.

**Why no bar on that question works.** The two populations interleave, measured
2026-09-22 on `a1261ca1` over the captured merges:

| pair | absent-extra share | indexed-line gain over parent |
|---|---|---|
| brucite a × 2 supercell (must demote) | 0.983 | +1 |
| brucite c × 2 supercell (must demote) | 0.931 | 0 |
| **corundum truth (must not demote)** | **0.943** | **−1 … +15** |

Three variants were measured and each fires on the correct cell: any absent
extra; a share bound; a gain bounded by `n_unindexed`. The instrument is
`ambiguity._refuted_supercell`, kept private and tested, unwired, with the
numbers in its docstring.

**Re-measure the table before quoting it.** The shares above were taken before
WP-1446's review pass moved `_derivative_transform`'s enumeration into the
child's frame. Until then the verdict turned on which axis setting the engine
reported: measured on a doubled cubic cell, `(a, a, 2a)` was refuted while
`(2a, a, a)` and `(a, 2a, a)` were cleared, because `same_lattice` compares
reduced forms and the H it accepts need not map the child's own basis. The fix
only makes the instrument find **more** related pairs, so the refutation is
strengthened rather than weakened, and a pair cleared that way was a demotion
that went uncounted. The individual shares belong to pairs found either way and
should still hold. Nobody has re-run the wiring experiment to check.

**Where the answer has to come from.** CLAUDE.md already states it from the
other side — read a `predicted_but_absent` firing as "this cell predicts lines
the pattern lacks" and never as "this cell is too big", because **only the
extinction screen separates the two**. Systematic absences are not knowable
until after the cell is, which is why `index → extinction symbol → space group`
is a sequence rather than one question. `determine_extinction_symbol`
(WP-1025, `indexing/extinction.py`) is the step that has the information, and it
runs on the pattern rather than on the peak list.

**What the literature says, as far as the tree's own citations go.** De Wolff
(1968) punishes a supercell only through `N_poss` and is blind to extinctions by
construction, which `fom.m20`'s docstring already records. Oishi-Tomiyasu (2013)
reverses the asymmetry and the panel carries that as `m_rev`; on a doubled axis
it separates truth from supercell 64-74× where M₂₀ manages 1.8×, and it inherits
the same blind spot about extinctions. Smith (1977) gives the parsimony bound
(`quality.volume_envelope`) and Mighell & Santoro (1975) give the formal limit,
that distinct lattices can produce identical positions.

**The corpus was not searched.** `/Users/yue/zotero-linker` is gone as of
2026-09-22, so the paragraph above is from the package's own citations and
general knowledge, never from a paper read for this WP. **Expand this section on
a machine with the corpus before designing anything.**

### Inherited

- **From WP-1333 (2026-09-23): on Linux x86-64 the brucite strict xfail
  passes, so `main`'s full suite is red there.**
  `tests/test_acceptance_indexing.py::test_brucites_truth_is_not_ranked_first`
  reported `[XPASS(strict)]` on the 2026-09-22 nightly at `a1261ca`
  (`[dev,jax]`, 1 failed, 5709 passed, 103 skipped). It did so again in
  WP-1333's full run at `16b72c3`, which carries #414 (`[dev]`, Linux x86-64,
  py3.12). WP-1446's handover recorded it as "1 xfailed", so on at least one
  platform the truth is now ranked first and on another it is not. Either the
  ranking the xfail pins is platform-dependent, which is a finding in itself,
  or the mark needs `strict=False` with a reason. Folding the row back is this
  WP's last task in any case. Until then, every Linux nightly `full` job fails
  on this one row, and a real regression in that job would read as the same
  red.
- **From WP-1454 (2026-09-24): on one Linux machine the row flips with load,
  not with platform.** `[dev]`, Linux x86-64, py3.12, 4 cores, at `016d06c`
  (main at `8fbafe5` plus WP-1454, which touches no indexing code). The full
  suite at `-n auto` reported `[XPASS(strict)]`. The same row run alone on the
  same tree reported `1 xfailed`. So the ranking it pins moves with the quick
  preset's wall-clock budget. A fix that flips it has to be judged on a run
  alone, and a mark kept strict will stay a load sensor until then
  (tests/CLAUDE.md § Budgets in tests).
- **From the nightly investigation (2026-09-24): the XPASS comes from a
  truncated search.** The platform was a proxy for speed. On the Linux `full`
  job the brucite search reports `INDEX_SEARCH_INCOMPLETE`. The evidence is
  the gallery sidecar `indexing_brucite.gallery.json` in run 35988617175's
  `test-output-linux` artifact. The fixture's setup took 802 s, 860 s and
  848 s on the 22, 23 and 24 Sep nightlies, against a budget of 300 s per
  engine and system.

  Reproduced on macOS arm64 (`.venv` `[dev]` + numba, at `14239188`). Only
  `budget_seconds` changed between the two runs, and the machine carried a
  load of about 7 from another session:

  | `budget_seconds` | search | wall | ranked first |
  |---|---|---|---|
  | 300 | complete | 520 s | a × 2 supercell, a = 6.2950 (the xfail holds) |
  | 60 | dichotomy incomplete in both systems | 153 s | truth, a = 3.1477 (as on Linux) |

  Corroboration does not move. In both runs dichotomy and trial_error find
  the a × 2 cell, and it indexes 34 lines against the truth's 33. Within the
  corroborated tier `rank_candidates` orders by a Borda count. A Borda count
  depends on the rest of the pool, and a truncated dichotomy returns a
  different pool (145 merged lattices against 146). That is enough to flip a
  one-line margin.

  For the fold-back task, this row can assert a rank only on a search that
  finished. The one CI job that runs slow rows is the Linux `full` job. It did
  not finish this search on any of the three nights. The macOS job runs slow
  rows only when dispatched with `full_macos`. There are two options, and
  neither has been costed. One skips the row when the result carries
  `INDEX_SEARCH_INCOMPLETE`. The other raises brucite's budget until the Linux
  runner completes the search.

  The class is wider than this row. Seven of the 13 indexing searches in the
  same artifact carry `INDEX_SEARCH_INCOMPLETE`: brucite, corundum,
  corundum_shift, cpd1a, fluorite, hl2 and nac. The comment on
  `REAL_DATA_BUDGET_SECONDS` says the budget is several times the search's
  cost. On that runner it is not. Only brucite's assertion flips. Nobody has
  checked which of the other six rows assert a rank.

## Questions for the corpus

- Does Oishi-Tomiyasu (2013, *J. Appl. Cryst.* **46**, 1277-1282) address the
  space-group-extinction confound in `M^Rev` directly, and does she prescribe
  anything for it? The blind spot is the same one that sank WP-1446.
- Conograph (Oishi-Tomiyasu 2014) — how does it order candidates that stand in a
  derivative relation, and does it defer the question to a later stage?
- What do DICVOL and its dichotomy papers (Louër & Boultif) say about returning
  a supercell, and do they rank on volume parsimony explicitly?
- Is there published practice for ordering on the **extinction symbol's** verdict
  rather than on the lattice figures, or is the sequential workflow universal?
- Mighell's derivative-lattice work (NIST): does it offer a criterion for
  choosing between a lattice and its derivative from powder data alone?

## Non-goals

- Retuning the figure-of-merit panel. WP-1041 measured and refuted the
  aggregates and those refutations stand.
- Hiding supercells. They are real solutions of the metric and a reader should
  see them ranked, which is why WP-1446 rejected a tier after measuring one.

## Tasks

- [ ] Expand Context from the corpus, answering the questions above.
- [ ] Decide where the screen's verdict enters: a re-rank of the reported list
      after validation, or a caveat that reorders, or a reported field that
      leaves the order alone. **Cost is the deciding input** — the screen is
      priced per reported candidate, and WP-1446's pairwise test already cost a
      corundum search 45-50 s → 5+ min before it was reverted.
- [ ] Whether `best_or_none()`'s gate, not the order, is the right place. The
      gate already declines to promote brucite; the complaint is only about what
      a caller reads first.
- [ ] Re-measure the brucite and corundum rows, and fold
      `test_brucites_truth_is_not_ranked_first` back into the row above when it
      goes red.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- WP-1446 (the refutation and every number above), WP-1026 (the first recorded
  instance), WP-1025 (the extinction screen), WP-1041 (the refuted aggregates).
- `src/rietx/indexing/CLAUDE.md` § the reverse direction cannot order two fitted
  candidates.

## Handover log

### 2026-09-22 — filed as a stub

WP-1446 set out to make the ranking read a number it already computes, and
measured that the number cannot do the job. A cell that is twice too big and a
cell that is right but whose symmetry hides most of its reflections look the
same from the peak positions alone. Sapphire's certified cell scores 0.943 on
the test; brucite's wrong cell scores 0.983 and 0.931 either side of it. So the
question moves to the stage that has the intensities.

This file is deliberately thin. The design waits on the paper corpus, which was
unreachable from the machine that filed it.

Next: expand Context and Questions from the corpus, then decide the seam.

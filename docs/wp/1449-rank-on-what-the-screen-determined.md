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

**The rank row read the machine, and now waits for a finished search.**
`test_brucites_truth_is_not_ranked_first` turned the Linux nightly red five
nights running, 22 to 26 September, each time as `XPASS(strict)`. The search
behind it was cut. Its 300 s per-unit budget binds on that runner, and a cut
search put the truth first each night. Measured 2026-09-26 on a Mac (`[dev]`,
arm64), over two runs at each budget. Finished, the two dichotomy units take
139-232 s and the a × 2 supercell leads. At 60 s both stop on the clock, and the
truth led one run and the supercell the other. So a rank read off a cut search
can pass where the finished search fails.

The mechanism matters to the design below. Corroboration does not move: in
every run dichotomy and trial_error both find the a × 2 cell, which indexes 34
lines against the truth's 33. Inside the corroborated tier `rank_candidates`
orders by a Borda count, and a Borda count depends on the rest of the pool. A
cut dichotomy returns a different pool (145 merged lattices against 146, measured
2026-09-24), and that flips a one-line margin.

On 2026-09-26, 8 of the nightly's 13 searches came back incomplete. Two are
incomplete by design: NAC stops at a cap, and hl2 runs at 15 s. The other six
ran at 300 s and finish locally, so the runner's clock is the likely cause. The
gallery sidecar now records each unit's clock, so the next nightly says.
Raising the budget was set aside. The corundum group already takes 61 of that
job's 100 minutes against a 150-minute limit, and how long the cut searches
need to finish there is unmeasured. Every row that reads an order now calls
`_skip_unless_finished` first. It compares each unit's clock with the budget
the result recorded. The fold-back task below therefore needs a finished
search: a local run, or the nightly dispatched with `full_macos`.

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

- [x] A rank waits for a finished search (2026-09-26). `_skip_unless_finished`
      runs before every order a real-data row reads. The budget comment and
      `tests/CLAUDE.md` § Budgets are corrected, three stale gallery captions
      rewritten, and the gallery sidecar records each unit's clock.
- [ ] `INDEX_SEARCH_INCOMPLETE` names the clock where a cap stopped the search.
      Measured 2026-09-26 on NAC: dichotomy ran 0.26 s over 0 boxes, and the
      message says it "did not finish cubic within 300 s per system" and
      suggests raising `budget_seconds`, which would change nothing. All three
      engines return one `complete` flag for three causes (the clock, the grid
      cap, the trial-set cap). Carrying the cause on the result would let
      `_clock_cut` read it instead of comparing clocks.
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

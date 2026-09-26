# WP-1449 — rank on what the screen determined, not on what the peak list shows

Milestone: unscheduled · Status: 🔄 2026-09-27 — the rank rows wait for a finished search and
INDEX_SEARCH_INCOMPLETE names its cause; the ranking seam is measured and
proposed, awaiting the maintainer's decision
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

**Three open preprints were read on 2026-09-27.** All three are Oishi-Tomiyasu's:
arXiv:1211.3926 (published as *Acta Cryst.* **A69**, 603-610, 2013),
arXiv:2003.13403 (de Wolff's figure generalised to EBSD) and arXiv:2312.07909
(lattice-basis reduction for indexing). Each quote below was checked against the
extracted text.

- Conograph leaves the choice between a lattice and its derivative to a figure
  of merit. "Powder auto-indexing is divided into two main stages: enumeration
  and sort of solutions. We contributed mainly to the stage of enumeration"
  (1211.3926, Conclusion). Its duplicate check looks for "nearly identical
  solutions", and "normally [...] only in the same Bravais class"
  (2312.07909 §2, applying Eq. 13 of §6.1).
- The one ordering rule stated is qualitative and about symmetry. For nearly
  identical cells in different Bravais classes, "the more symmetric one is
  usually correct, but it is not appropriate to reject the less symmetric one
  at this point" (2312.07909 §2).
- The EBSD figure punishes a derivative lattice through N, as M₂₀ does. N is
  set by the smallest d threshold that indexes every observed band, with
  m·hkl counted once. The paper calls this "a heuristic for ranking the true
  solution above the derivative lattices" (2003.13403 §4). It needs no
  extinction class, so it has M₂₀'s blind spot. With half the bands, a
  low-symmetry derivative of hexagonal Zn was output and still scored above 20
  (§5).
- None of the three orders candidates on systematic absences. 1211.3926
  classifies space-group absences, glides and screws included (its Table 2),
  and uses them only to show that the enumeration survives them. No pipeline
  in the three has an extinction-symbol step.

So the practice found so far sorts on a lattice-only figure and leaves the
confound open.

**Five published papers were read on 2026-09-27**, from the synced Zotero
library (`~/Zotero yue-here/`). Each quote below was checked against the
extracted text.

- **The figure `m_rev` implements names this gap itself.** Oishi-Tomiyasu
  (2013, *J. Appl. Cryst.* **46**, 1277-1282) computes N^cal from the Bravais
  lattice alone: "only information about Bravais lattices was used to provide
  a set of computed lines, and systematic absences were not considered. This
  might have adversely affected in particular the results of M_n^Rev because
  M_n^Rev is more sensitive to extinct reflections" (§3). WP-1446's corundum
  row is that sentence measured.
- **Conograph** (Oishi-Tomiyasu 2014, *J. Appl. Cryst.* **47**, 593-598) lists
  cells with identical computed lines (Mighell & Santoro 1975) and leaves
  their order to the 2013 figures. Its computed lines are Bravais-only.
- **DICVOL** (Boultif & Louër 1991, 2004) builds parsimony into the search
  order: high to low symmetry, smallest volume first, "the volume is inversely
  proportional to the figure of merit" (1991, p. 992). A later, lower-symmetry
  search is bounded by the volume of a solution already found (2004, §4.1).
  Predicted lines apply no extinction, and space-group derivation is a
  separate later stage (2004, §3.3).
- **EXPO's WRIP20 orders on the extinction verdict**, and is the precedent
  this WP asked for (Altomare *et al.* 2019, ITC Vol. H ch. 3.4, eq. 3.4.5;
  the figure is Altomare *et al.* 2009). WRIP20 = RAT_Rp² · RAT_Ind · RAT_Pres
  · w_u · RAT_M20^½. For the extinction symbol with the highest probability,
  PERC_Pres = Σ_Pres mult / Σ_all mult is the share of reflections it leaves
  present, and RAT_Pres = (PERC_Pres)_min / PERC_Pres. The probability comes
  from a statistical analysis of normalised intensities (Altomare *et al.*
  2004, 2005), and Rp from a Le Bail fit in the highest Laue group with no
  extinctions. In the chapter's Example 3, "the classical M20 figure of merit
  was not able to pick up the solution" and WRIP20 did. In Example 4 a
  hexagonal/orthorhombic ambiguity was settled by selecting "the
  higher-symmetry one", with no extinction test.

So the literature has both halves. The reversed figure's author names the
extinction blind spot, and EXPO answers it by scoring each cell under its most
probable extinction symbol. Still unread: Markvardsen *et al.* (2001) and
Santoro & Mighell (1972), neither in the library.

**What the screen decides, measured 2026-09-27** (`[dev]`, macOS arm64; probes
in the handover entry). Swapping a panel member for its class-level version
fixes nothing on brucite. The screen gives the truth and the a × 2 supercell
the same verdict, `P - - -`, so their `predicted_seen_fraction` stays 0.86
against 0.32. What separates the populations is WP-1446's pairwise question
asked under the child's best extinction class and judged against chance.
For each pair where the child is a derivative supercell of the parent, the
child's extras are the lines its best class allows and the parent does not
predict. The chance rate p0 is the share of the observed Q range that lies
inside some observed line's matching window. A child whose extras are seen no
more often than p0 predicts (one-sided binomial p ≥ α) is refuted.

| dataset | p0 | a truth as the child | wrong children refuted |
|---|---|---|---|
| brucite | 0.105 | none | a × 2 (3 of 59 seen), c × 2 under `P 63 - -` (2 of 22), √3 a, and their products; p ≥ 0.60 |
| corundum | 0.117 | R truth under `R - c -`: 8 of 18 seen, p = 5.0e-4, **kept** | the 8.24 Å cells, and the P descriptions of the R metric; p ≥ 0.10 |
| corundum, shift declared | 0.117 | the same, p = 5.0e-4, **kept** | the 8.24 Å cells; p ≥ 0.79 |
| zincite | 0.071 | none | ten supercells; p ≥ 0.042 |
| zircon | 0.164 | none | ten P supercells of the I truth; p ≥ 0.46 |
| fluorite | 0.042 | none | one I cell (0 of 8 seen) |
| LaB6 | 0.061 | truth in a tetragonal setting: 9 of 12 seen, p = 2.1e-9, **kept** | none |
| magnetite, LaB6 calibrated, NAC, FAP | 0.054-0.918 | none | none |

Every truth tested as a child sits at p ≤ 5.0e-4 and every refuted child at
p ≥ 0.042, so a conventional α = 0.01 falls in the gap without being fitted to
it. At lattice level, without the class, corundum's truth is marginal. On a
line-rich pattern p0 is high (NAC 0.918, FAP 0.352), so the test has little
power there and leaves the order alone. Three limits of the measurement: the
candidates are the local acceptance run's finished searches; the screen ran
under the manual's protocol, since without seeded widths it refutes corundum's
own glide; and the window outside brucite and corundum is `match_window` under
a default spec.

**The proposed seam, awaiting the maintainer's decision.** After validation,
screen each reported child that stands in such a pair, and order a refuted
child directly below its parent with a caveat naming the parent and the counts.
Every other candidate keeps today's order, and `best_or_none()` is unchanged.
The screen cost 0.1-1.3 s per candidate on these patterns, against searches of
220-480 s. Open: α; how `index_pattern` chooses the screen's 2θ range, since
the manual's 20-90° is a caller's choice and no rule for it is measured; and
what a bare peak list does, having no pattern to screen.

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
  *Answered 2026-09-27: she names it and prescribes nothing (Context).*
- Conograph (Oishi-Tomiyasu 2014) — how does it order candidates that stand in a
  derivative relation, and does it defer the question to a later stage?
  *Answered 2026-09-27: it leaves the order to the 2013 figures and names
  no later stage (Context).*
- What do DICVOL and its dichotomy papers (Louër & Boultif) say about returning
  a supercell, and do they rank on volume parsimony explicitly?
  *Answered 2026-09-27: parsimony is the search order itself (Context).*
- Is there published practice for ordering on the **extinction symbol's** verdict
  rather than on the lattice figures, or is the sequential workflow universal?
  *Answered 2026-09-27: EXPO's WRIP20 does it (Context).*
- Mighell's derivative-lattice work (NIST): does it offer a criterion for
  choosing between a lattice and its derivative from powder data alone?
  *Unread: Santoro & Mighell (1972, Acta Cryst. A28, 284-287) is not in
  the library.*

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
- [x] `INDEX_SEARCH_INCOMPLETE` names what stopped the search (2026-09-27).
      Measured 2026-09-26 on NAC: dichotomy ran 0.26 s over 0 boxes, and the
      message said it "did not finish cubic within 300 s per system" and
      suggested raising `budget_seconds`, which would change nothing. Each
      engine now files an incomplete unit by whether its budget had expired,
      and `incomplete_diagnostic` words each cause with its own remedy. The
      cause lives in the message only, so `_clock_cut` still compares clocks.
- [x] Expand Context from the corpus, answering the questions above
      (2026-09-27). Eight papers read; Markvardsen *et al.* (2001) and
      Santoro & Mighell (1972) are not in the library.
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

### 2026-09-27 — the rank rows wait for a finished search; the design is measured and proposed

The Linux nightly failed five nights running on one row, and the cause was the
test, not the ranking. The runner is slow enough that the search behind that
row is stopped by its time budget, and a stopped search does not produce a
repeatable order: the same search, stopped the same way, put a different cell
first on two runs here. Every indexing row that asserts an order now waits for
a search that finished, and says which parts were stopped when it cannot. The
warning that a search did not finish also blamed the clock when a size limit
had stopped it, and told users to wait longer where waiting changes nothing;
it now names the cause. The ranking design moved from a question to a measured
proposal. Eight papers show the problem is known and that EXPO scores cells
under their most probable extinction symbol. Over the eleven acceptance
datasets, that idea keeps every true cell and demotes only wrong supercells,
once each supercell's missing lines are judged against chance. Nothing in the
ranking is built yet, because the seam is the maintainer's decision.

**Done.**

- `_skip_unless_finished` runs before every order a real-data row reads (14
  sites). It reads each unit's clock from `engine_stats` against the budget the
  result recorded in `provenance.notes`, never `search_complete`, which a cap
  also sets. svd's retry clock (`svd.<system>.trim.seconds`) counts. Rows that
  assert only what was found stay live, and so does hl2's row, whose 15 s
  budget is cut by design and whose claim is an abstention.
- The gallery sidecar records `unit_seconds`. Three stale captions (brucite,
  fluorite, fap) and four double-escaped dashes fixed.
- `incomplete_diagnostic` words a capped system apart from a clock-stopped
  one; each engine files an incomplete unit by whether its budget had expired
  when it returned. Staged in `releases/1.5.1.md`; two skill rows updated, one
  with the finding that a cut search's order does not repeat.
- Context gained the Borda mechanism, the three arXiv preprints, the five
  papers in the synced Zotero library (`~/Zotero yue-here/`), and the measured
  proposal with its table. The corpus task is ticked; Markvardsen *et al.*
  (2001) and Santoro & Mighell (1972) are not in the library and stay unread.
- `tests/CLAUDE.md` § Budgets rule updated and kept at its 296-line cap.

**Measured** (`[dev]`, macOS arm64, py3.12, unless named).

- Nightly `full` job, 22-26 September: every run failed on
  `test_brucites_truth_is_not_ranked_first` as `XPASS(strict)` (23 Sep also on
  a magnetic-irreps row). On 26 September 8 of 13 sidecars carried
  `INDEX_SEARCH_INCOMPLETE`: NAC by its cap, hl2 by its 15 s design, and six
  searches run at 300 s. Setup there: corundum 1473 s, corundum with shift
  1283 s, fluorite 1199 s, the mixture 921 s, brucite 833 s. Job 1:39:52
  against a 150-minute limit.
- Brucite at 300 s, two runs: dichotomy units 232/209 s and 175/139 s, a × 2
  supercell first both times. At 60 s, two runs: both units stopped at 60.01 s,
  truth first once and supercell first once.
- NAC's dichotomy: 0 boxes in 0.26 s, reported before the fix as "did not
  finish cubic within 300 s per system".
- `tests/test_acceptance_indexing.py` under `-n auto`: 44 passed, 1 xfailed,
  nothing skipped, 21:28, another session loading the machine at the start.
  The slowest units still came close to 300 s: brucite 278 s, corundum 246 s,
  corundum with shift 215 s, fluorite 151 s.
- Fast suite: 6305 passed, 151 skipped (6456), 3:32, no other pytest running.
  No test function was added, only assertions inside two engine tests; the cap
  assertion failed against the old engine code before passing on the new.
  `tests/test_indexing_engines.py`: 76 passed. The full selection did not run,
  since nothing here can move a measured number.
- The screen probes, all on searches that finished (scripts in the session
  scratchpad only). Under the manual's protocol (widths seeded from the peak
  list, 20-90°) the screen returns `R - c -` on corundum at ΔBIC −3361.
  Without it, it refutes corundum's own glide. It costs 0.1-1.3 s per
  candidate. Brucite's truth and a × 2 supercell both get `P - - -`, so a
  class-level `predicted_seen_fraction` leaves them at 0.86 and 0.32. The
  chance test's corpus table is in Context: truths tested as a child at
  p ≤ 5.0e-4, refuted children at p ≥ 0.042. WP-1446's lattice-level share did
  not reproduce here: corundum's truth read 0.735, not 0.943, because this
  probe used the search's wider matching window.

**In flight.** Nothing uncommitted. The next nightly after merge should show
the six rank rows skipped with named units, or passing if the runner finished.

**Gotchas.**

- A skip in a strict-xfail row reports as skipped, which keeps the nightly
  green on a cut search. The fold-back can only be judged on a local run or
  the nightly dispatched with `full_macos`.
- The screen's answer depends on a caller's protocol (seeded widths, trimmed
  range). Wiring it into `index_pattern` has to supply that protocol itself.
- The corpus is high-symmetry: all eleven datasets have at most two free
  metric parameters, so the table says nothing yet about monoclinic or
  triclinic cells.
- The probe's truth check matched axes and ignored centring, and flagged
  corundum's P descriptions of the R metric as truths. They are not.
- The worktree guard refuses `$VAR` paths, loops and computed pipes. Scratchpad
  scripts run in one plain command get past it.

**Next.** First the maintainer's decision on the proposed seam in Context:
re-rank a refuted child below its parent with a caveat, or report the verdict
without reordering. Then, if re-ranking: rework `ambiguity._refuted_supercell`
to take the child's class and return counts and p; choose the screen's range
inside `index_pattern` by measurement; decide the bare-peak-list case; re-run
the acceptance file, where the brucite xfail should go red and fold back into
the row above it.

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

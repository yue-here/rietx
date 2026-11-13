# WP-2112 — an engine's first cell stays in the reported list

Milestone: unscheduled · Status: ⬜ — the 2026-11-08 re-run never filled the cap of 12; next, re-run devitrite with a budget that lets all three engines build their lists
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-05 — a ranking defect on one synthetic list, seen before WP-2079 and WP-2082 changed the ranking key and not re-run; a caller's workaround is a larger `max_candidates`

## Goal

A cell that one engine ranks first is not dropped from `IndexingResult.candidates` by the reported
cap of 12, or the measurement says it no longer is. Either way the list a reader inspects when the
gate abstains holds what the engines actually offered.

## Context

**Source.** Issue #1375, carried from #780. Reported there on 2026-10-14 and not re-run since. WP-1924
recorded it and closes without owning it (PR #1373), and WP-2110 (PR #1427) names it a non-goal.

**The report.** The list is devitrite, Na₂Ca₃Si₆O₁₆ (COD 1535730, P-1, 699 Å³, Cu Kα 6-30°, 48 lines),
synthetic from the published cell. svd ranks the true cell first among its own candidates. After
consensus merges all three engines' candidates, that cell is not among the 12 that `max_candidates`
reports. The reporter's simulation called this "built, not reported" at a 300 s ceiling with the
default 30 s slice.

**Why it matters.** A cell with a single finder is floored at `low` by `grade` (`MIN_AGREEMENT`, 2). It
still belongs in the reported list. `indexing/CLAUDE.md` names this shape: a cap applied above the layer
that ranks is a ranking (WP-1046).

**The seam, read at `541f0daf7`.** `consensus.consensus` calls `rank_candidates` with
`max_candidates=reported` and `shortlist=None`, so every merged lattice is scored. `rank_candidates`
(`engines.py`) sorts on `(not corroborated(c), -borda)` and returns `(scored + unscored)[:max_candidates]`.
So every corroborated cell stands above every single-finder cell, whatever its panel score. A list with
12 or more corroborated cells reports no single-finder cell at all. The `INDEX_CANDIDATES_TRUNCATED`
diagnostic says a list was cut. It does not say whose first choice went.

**What moved since the report.** WP-2079 and WP-2082 changed how agreement is counted in the ranking key
and the grade (#1308). So the first task is the re-run. The COD cell is not in the tree, and the list is
built with `tests.test_indexing_engines.synthetic_peaks`.

**Tier.** A reserved seat per engine would be a new rule of rietx's own: tier 3, new judgement, with the
known-cell corpus as its family and each row's truth as its reference. Nothing has measured its cost.

## Non-goals

- How a ceiling shares among units: that question is with the maintainer in issue 1374, which has no WP yet.
- trial_error's memory: WP-2110.
- Raising the default of 12. That moves what every reader sees for one list's sake.

## Tasks

- [x] Re-run devitrite on current main with the published cell, at a 300 s ceiling with the 30 s slice, and record each engine's rank 1 and the reported list. (2026-11-08: reported, rank 1 of 1, but trial_error and dichotomy built no candidate, so the merged list held one cell and the cap of 12 never filled; the re-run could not see the defect. Numbers in the handover entry.)
- [ ] Re-run devitrite with enough budget for all three engines to build their lists: `preset="full"`, or a `total_budget_seconds` well over the first re-run's 271 s wall. Record each engine's rank 1 and the reported list. Close this WP only if the true cell is in the reported list once the cap of 12 is full; a one-cell list proves nothing.
- [ ] If it is still dropped: measure how often an engine's rank 1 falls outside the reported 12 on the known-cell corpus (`tests/test_acceptance_indexing.py`'s lists and `tests.bethanechol_benchmark`'s).
- [ ] Decide between a seat per engine, and a sentence in `INDEX_CANDIDATES_TRUNCATED` naming the engine whose first choice went. The second changes no answer.
- [ ] Tests: a synthetic list that fills the cap with corroborated cells, with the single finder's rank 1 asserted in the list or named in the diagnostic.
- [ ] Skill: the `INDEX_CANDIDATES_TRUNCATED` row if its text changes, or "none" if the re-run closes this.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m tests.bethanechol_benchmark        # alone, about an hour, only if the order changes
```

## References

- Issues #1375 and #780 (the reporter's 2026-10-14 table); WP-1046; WP-1924; WP-2079; WP-2082.

## Handover log

- **2026-11-08** — task 1's re-run recorded, PR #1470; the WP stays open for the filled-cap run (the maintainer's ruling, 2026-11-13). On current main, devitrite's true cell is
  in the reported list: svd builds it and ranks it first, and the merged list reports it at rank 1.
  It is the only candidate, so the cap of 12 never bites, and it grades `low` because one engine
  found it. The symptom is absent on this list, but the case that drops a cell never arose: the drop needs other engines to fill the cap of 12 with cells two engines agree on, and trial_error and dichotomy built nothing before the ceiling. So this run does not show that WP-2079 and WP-2082 changed the outcome. Nothing in the package changed. The seam
  the Context describes is unchanged: a corroborated cell still ranks above every single-finder
  cell (WP-1046's key), so a list with 12 or more corroborated cells would still report no
  single-finder cell. This run built no such list, so it says nothing either way.
  - *Measured.* Tree `63d7c120a` (origin/main; this branch differs only in this file and the WP
    index). `.venv` built in this worktree, CPython 3.12, `[dev]`, macOS arm64, 10 cores, load
    average 4.6 at start. The list is `tests.test_indexing_engines.synthetic_peaks` with
    `sg="P -1"`, the COD 1535730 cell (Ihara 1984: 10.123, 10.569, 7.117 Å, 109.71°, 98.24°,
    78.15°) and `two_theta_max=30.0` at Cu Kα1: **57 lines**, 8.95-30.01°. The issue's list had 48
    lines, and how its author thinned it is not recorded. The call was
    `index_pattern(peaks, spec=SearchSpec(total_budget_seconds=300.0))`, so `budget_seconds` 30 s,
    `max_candidates` 12, preset `custom`, no profile validation. A spy on `consensus` recorded each
    engine's own list. Wall 271 s.
  - *Each engine's rank 1.* svd: the true lattice (V 699.29 Å³), its only candidate; its
    triclinic unit completed and its orthorhombic and monoclinic units were cut by the slice.
    trial_error: no candidate, every system from orthorhombic down cut. dichotomy: no candidate,
    orthorhombic complete, monoclinic and triclinic cut.
  - *The reported list.* One candidate, triclinic P, V 699.29 Å³, `found_by=['svd']`, grade `low`.
    `INDEX_CANDIDATES_TRUNCATED` did not fire, because one lattice was merged. The diagnostics were
    `INDEX_SEARCH_INCOMPLETE` (7), `INDEX_ABSTAINED`, `INDEX_NOT_VALIDATED`,
    `INDEX_SHIFT_FROM_PAIRS`, `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`, `PEAK_POSITION_PRECISION`.
  - *Gotcha.* `synthetic_peaks` keys its defaults by system, and `CASES` has no `"triclinic"` row.
    Pass `"monoclinic"` with `sg=` and `cell=` overriding both.
  - *Not done.* Tasks 3-5 stay conditional on a filled-cap run showing the drop. No follow-up issue was filed.
  - Next: task 2, re-run devitrite with `preset="full"` or a `total_budget_seconds` well over 271 s so that all three engines build their lists. Close only if the true cell is in the reported list once the cap is full. If it is dropped, tasks 3-5 apply.

- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1375). Checked against the tree at `541f0daf7`: read the seam above, and did not re-run the list, whose cell is not in the tree; no open WP owns it: WP-1924 closes without it in PR #1373, WP-2110 fences it, and WP-2078 is about lines the host does not own. Next: the re-run, which may close this.

# WP-2112 — an engine's first cell stays in the reported list

Milestone: unscheduled · Status: 🔄 2026-11-08 — claimed by @mustachefeeling
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

- [ ] Re-run devitrite on current main with the published cell, at a 300 s ceiling with the 30 s slice, and record each engine's rank 1 and the reported list. If the cell is reported, close this WP on that measurement.
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

- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1375). Checked against the tree at `541f0daf7`: read the seam above, and did not re-run the list, whose cell is not in the tree; no open WP owns it: WP-1924 closes without it in PR #1373, WP-2110 fences it, and WP-2078 is about lines the host does not own. Next: the re-run, which may close this.

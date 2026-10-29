# WP-2063 — the FoM panel scored after the clock spends the validation reserve

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-28 — cost-only: under `quick` a heavy pattern pays 9 s of search for it (WP-2011 raised the reserve 8 → 15 % to cover it); no wrong answer

## Goal

Under `quick`, what runs between the search's stop and the first validation
fit is bounded, so the validation reserve reaches validation and
`VALIDATION_RESERVE_FRACTION` can return toward what the fits alone need.

## Context

- **Measured by WP-2011** (macOS arm64, `[dev]`, 11-BM NAC, default
  `SearchSpec()`, probes 19-21 in `docs/wp/2011-probe/`). The search was due to
  stop at 110.4 s, leaving 9.6 s (8 %):
  - trial_error's tetragonal unit returned at 114.5 s. In isolation, a unit
    under a 5 s `Deadline` returned 4.4 s late: 0.8 s finishing the base set
    in hand (the loop checks the clock once per base, `trial_error.py`
    `_search_system`), and **3.6 s in `rank_candidates` after the loop**,
    scoring the unit's 24 candidates' panels.
  - `consensus` then ran 114.5 → 120.95 s. Profiled: 5.8 s, of which
    `rank_candidates` over the whole merge (80 panels) is 4.9 s;
    `fom.lattice_reflections` 4.3 s cumulative, `fom.laue_multiplicity` 2.8 s
    (1.2 s its own), `qspace.trial_hkl` 1.2 s; about 0.06 s a panel.
  - So no validation fit started, Pawley or Le Bail.
- **Why the reserve stopped covering it.** WP-1045 sized 8 % to the
  validation fits alone (3 × 1.9 s, measured then). WP-1046 later made
  consensus score the whole merge (`shortlist=None`), which on a heavy
  pattern costs more than the reserve.
- **What WP-2011 did instead**: validation now runs cheapest first on the
  run's clock, and the reserve is 15 % (`engines.VALIDATION_RESERVE_FRACTION`,
  tier 3, its row carrying the measurement). At 15 % NAC's true cell
  validated on both specs; the cost was NAC's default spec no longer reaching
  orthorhombic.
- **The tier of each rule this WP adds**: none planned. A cheaper panel moves
  no number if it is exact; a budgeted one would add a cap, tier 3.

## Tasks

- [ ] Profile `fom_panel` on NAC's 80-candidate merge and decide between
      making `lattice_reflections`/`laue_multiplicity` cheaper (vectorised, or
      cached per reduced cell: consensus re-scores cells the units already
      scored) and bounding the post-search scoring by the clock.
- [ ] Read the clock inside trial_error's per-base loop as well, so a unit
      stops within one assignment, not one base set.
- [ ] Re-measure `quick` on NAC (`docs/wp/2011-probe/probe16_schedule.py`,
      `RESERVE=`) and, if the fits now see the reserve, lower
      `VALIDATION_RESERVE_FRACTION` with its row's evidence.
- [ ] Unit replay digests (`python -m tests.unit_replay`) and
      `tests/test_acceptance_indexing.py` unchanged, or each move named.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_scheduler.py tests/test_indexing_ceiling.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- [WP-2011](2011-a-candidate-is-judged-on-a-fit-that-converged.md) (the
  measurement), WP-1045 (the reserve), WP-1046 (whole-merge scoring).

## Handover log

- **2026-10-28** — filed by WP-2011's handover. No open WP owns the panel's
  cost: WP-1956 owns what the line screen asks, not what scoring costs, and
  WP-1509 (closed) sped up dichotomy leaves only.

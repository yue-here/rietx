# WP-2063 — the FoM panel scored after the clock spends the validation reserve

Milestone: unscheduled · Status: 🔄 2026-10-29 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-31 — was P3: issue #1231 shows a `full` run overrunning its declared `total_budget_seconds` by minutes, every candidate left unvalidated (a defect that fires wrongly, as WP-1924 rates a ceiling overrun)

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
- **Issue #1231** (folded from `### Inherited` 2026-11-01): since #1191 a
  `preset="full"` run with `total_budget_seconds=900` overran its ceiling by
  minutes on dense synthetic low-symmetry patterns (aP2 1038 s, big_mP1
  953 s), every aP2 candidate `not_validated`. Two causes. (1) A Pawley
  validation fit read its cancel only between residual evaluations, and one
  step outlasted the deadline (a 3931-reflection rival stopped 125 s late
  under `Deadline(30)`); fixed here. (2) trial_error read its budget once per
  base combination; fixed by WP-1924.
- **The tier of each rule this WP adds**: none planned. A cheaper panel moves
  no number if it is exact; a budgeted one would add a cap, tier 3.

## Tasks

- [x] Profile `fom_panel` on NAC's 80-candidate merge and decide between
      making `lattice_reflections`/`laue_multiplicity` cheaper (vectorised, or
      cached per reduced cell: consensus re-scores cells the units already
      scored) and bounding the post-search scoring by the clock. Done exactly: whole-merge scoring 3.5-6.5× cheaper in CPU, every panel bit-identical; no cap added.
- [x] Read the clock inside trial_error's per-base loop as well, so a unit
      stops within one assignment, not one base set. Done by WP-1924
      (`1f2e48e7a`), which reads it before each `_score`; this branch's own
      read one line above it was removed at the merge as a duplicate.
- [x] Issue #1231's first cause: a Pawley validation fit honours its cancel
      late. Profiled (`docs/wp/2063-probe/probe2_late_cancel.py`, NAC's cI
      metric described as tP, `Deadline(15)`): one LM step's projected CG
      refactorised 1099 times in 27 s of the 35 s. The token is now read
      before every factorisation and CG product
      (`least_squares._cancel_check` → `lm.minimize(check=)` →
      `bccg.projected_cg`): 20.18 s late before, 0.01 s after. Unset, a fit
      is bit-identical (`test_a_bounded_step_reads_the_cancel_and_changes_nothing_while_unset`).
- [x] Re-measure `quick` on NAC and see whether the fits now see the
      reserve. Counted, not clocked: the machine ran at load 50-145 on 10
      cores, where probe 16's wall clock means nothing.
      `docs/wp/2063-probe/probe1_panel_replay.py` captured one `quick`
      run's ten `rank_candidates` calls and replayed each on both trees
      (thread CPU, minimum of five, digests equal on all ten): consensus
      over 37 panels 5.59 → 1.05 s, the three trial_error units 5.80 →
      1.04 s. Scaled to WP-2011's quiet 80-panel merge, the post-stop
      scoring falls from about 10.5 s to about 1-2 s, so at 15 % (18 s) the
      fits get about 16 s where they had 7.3 s.
- [ ] Lower `VALIDATION_RESERVE_FRACTION` from a repeated `quick` sweep on
      an idle machine (probe 16, `RESERVE=0.08,0.10,0.15`, three runs each,
      NAC both specs and the four lab sets), with its row's evidence. The
      value trades validated fits for searched systems on the wall clock, so
      no count can choose it.
- [x] Unit replay digests (`python -m tests.unit_replay`) and
      `tests/test_acceptance_indexing.py` unchanged, or each move named.
      Replay: 22 of 22 digests unchanged. Acceptance: 44 passed (macOS
      arm64, `[dev]`, on d4e1fdde3).

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

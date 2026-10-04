# WP-1511 — Which of these cells does this powder support?

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1323 soft, the Le Bail call and its background protocol; 1510 soft)
Priority: P3 2026-09-28 — a workaround covers it: the agent in `solution case 1` did it by hand across six scripts

## Goal

One call takes the cells a person or a search proposes and returns, for
each, the evidence a crystallographer would use to choose between them:
Le Bail agreement under one protocol, how far the metric moved from where it
started, the lines the cell leaves unindexed, and which cell doubling, if
any, explains those lines. It ranks the cells with that evidence beside each
row and never returns a winner on its own.

## Context

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. There the blind search never found the accepted cell; the person
supplied it. Everything after that was hypothesis testing, and the agent
built each test by hand:

- A Le Bail fit of each candidate. The rival cell's Rwp came out 1.8× the
  accepted cell's, and its metric drifted 2 % *toward* the accepted one
  during the fit. The drift was the refutation. Rwp alone was not.
- The accepted cell with its monoclinic angle forced to 90°: Rwp 2.3×
  worse, so the obliquity is demanded by the profile.
- A triclinic distortion, which slid to a minimum that broke a strong line.
- A coverage table: which observed lines each cell indexes (40 of 50 for
  the accepted cell, every strong line among them).
- The ten weak leftover lines scored against all seven cell doublings. One
  doubling placed lines on 7 of the 10; another was refuted because it
  predicted strong lines that are absent.

**This is the main human use case for indexing.** A person with a cell from
electron diffraction, a single crystal of a sibling phase, or a hand fit
wants to know whether the powder agrees. `index_pattern` accepts such cells
as priors (`src/rietx/indexing/priors.py:190-264`) and checks each "the
engines' own way" (assign, refine, shift-refit,
`indexes_the_search_lines`). A prior the engines do not rediscover is then
appended after the ranked list, unconfirmed. Nothing compares cells on a
profile fit.

**Seams that exist.** The Le Bail call and its scope (WP-1323, which also
inherits this run's background finding); `supercell_refuted` and
`INDEX_SUPERCELL_REFUTED` (WP-1449), the opposite question: there a
supercell of another candidate is refuted, and here a doubling of the
accepted cell is tested as the explanation of the leftovers.

**Design questions to settle first.**

- The answer type. It belongs beside `IndexingResult`, provisional like the
  rest of `indexing/` (`PROVISIONAL_MODULES`).
- One protocol for every cell: which background, which profile terms free,
  which 2θ window. A cell must never win on a looser protocol.
- Scoring a doubling without a structure. Positions only, with a chance
  control for coincidences, the way WP-1442's ghost screen controls its own.
  The run used intensities from a structural model, which this call will
  not have.
- Two settings of one lattice are one row.

### Inherited

- **2026-10-04, from [1323](1323-lebail-stop-rule.md), closed: the Le Bail
  background protocol is [1542](1542-a-le-bail-background-left-at-its-seed.md).**
  This WP's `Depends on:` names 1323 for "the Le Bail call and its background
  protocol". The call shipped in 1.6.0 (`fit` runs the alternation with a cap
  and keep-best). The background protocol did not: a seed left too low lowers
  Rwp, so 1323's stop rule cannot see it, and it is filed as 1542, not
  started. Read 1542 before relying on a Le Bail background.

- **From WP-1449 (closed 2026-09-29): the supercell check's power below high
  symmetry.** Asked directly of the published bethanechol cell's 55
  superlattices of index 2-4 on all ten sets (`ambiguity.supercell_chance`),
  it refuted 544 and left 6 undecided, all on set F, where a chance hit is
  0.738 likely and an index-2 cell adds 9-14 extras. None was supported, but
  Aa's index-3 cell sat at p = 0.0105, one coincident line from it. The
  benchmark's own protocol cannot ask this: neither mode's volume window
  admits the truth beside a supercell of it. Untested is a *real* low-symmetry
  superstructure, where the truth is the child; no dataset here has one.

## Non-goals

- The blind search itself (1449, 1508).
- A structure-dependent superlattice test (that needs models from the
  solution milestone 1515 scopes).

## Tasks

- [ ] Design note in this file: answer type, protocol, doubling score and
      its control. Maintainer decision recorded.
- [ ] The call, on the Le Bail path WP-1323 settles.
- [ ] Metric drift and the per-cell unindexed-line list.
- [ ] Doubling scores for leftover lines, with the chance control.
- [ ] Tests on a public pattern with a known cell and a decoy that fits
      nearly as well (a sub-cell or a wrong system), plus obs/calc/diff
      PNGs per cell to `tests/output/`.
- [ ] Manual Part 1, `help.py`, and the api surface partition.
- [ ] Skill: a reference row sending "which of my cells?" to this call.

## Acceptance

The decoy fixture ranks the true cell first with drift and coverage beside
it, and the decoy's row shows why it lost.

```sh
.venv/bin/python -m pytest tests/test_indexing*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

`solution case 1` replayed privately reproduces the hand verdicts: the rival
refuted by drift, and the same doubling on the leftovers. Counts only in the
handover.

## References

- Le Bail, A., Duroy, H. & Fourquet, J. L. (1988). *Mater. Res. Bull.* 23,
  447–452. The whole-pattern fit each row runs.

## Handover log

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510 and 1512 to 1517. Nothing started.

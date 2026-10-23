# WP-2035 — a reduced cell is its input's exact image, near a right angle too

Milestone: unscheduled · Status: 🔄 2026-10-23 — built, on review
Track: What fires, and what stays silent
Depends on: — (1923, closed: the exact change of basis; 1932, closed: the boundary-free comparison that reads it)
Priority: P3 2026-10-23 — a property test fails on a reachable F-centred cell at 1.1e-7 of the metric's scale, and replays only from one machine's local hypothesis database, so CI cannot see it

## Goal

`reduce_cell` returns a cell whose metric is M·G·Mᵀ of its input under the
change of basis it records, to rounding, on every centring. This is
WP-1923's claim, and a cell near a right angle still breaks it. A test that
CI runs pins the case.

## Context

- **The case** (WP-1930 found it on 2026-10-13, macOS arm64, at `aea419b6`):
  centring F, a = 3.2, b = 16.0, c = 23.602486327493914 Å, α = 81°, β = 66°,
  γ = 65°. `test_the_reduced_cell_is_the_exact_image_of_its_input[F]`
  (`tests/test_indexing_reduce.py:350`) asserts the reduced metric equals
  M·G·Mᵀ to 1e-12·max|G|. It failed on `c4607fa0` as well, a tree without
  WP-1930's change. It was carried in WP-1932's `### Inherited` and moved
  here at 1932's close.
- **Still failing at `12f459e`** (`[dev]`, Linux x86-64, 2026-10-23, replayed
  through the test's `inner_test`). The reduced cell is (3.2, 7.388025,
  10.780972 Å, 91.049995°, 90.00001°, 101.073895°). The worst entry is G₃₂:
  −1.4595751161 from `reduce_cell` against −1.4595624988 for M·G·Mᵀ. That is
  1.26e-5 absolute and 1.09e-7 of max|G|, the same numbers WP-1930 recorded
  on macOS. So the defect is the same on both platforms and is not rounding.
- **Where to look first.** β sits 1e-5° from a right angle. WP-1923 builds the
  cell from M·G·Mᵀ only where an entry's sign disagrees with gemmi's, and
  otherwise keeps gemmi's ε-reduced cell (WP-1932's Inherited, 2026-10-11).
  A cell whose sign agrees but whose value gemmi moved within ε would take
  that second path. That is a hypothesis, not a measurement.
- **Why it matters beyond the test.** Since PR #949, `equal_reduced`,
  `equal_reduced_many` and `same_lattice` compare reduced cells through
  `reduce._equal_across_boundaries`, which assumes the reduced cell is an
  exact image of the candidate. #949's bethanechol run moved no grade
  (WP-1932's close), so no measured answer depends on this case yet.

## Non-goals

- The comparison across boundaries (WP-1932, shipped).

## Tasks

- [x] Pin the case as an `@example` CI runs, as a strict xfail first so the
      suite stays green.
- [x] Find which path in `reduce_cell` returns the non-image metric, and
      return M·G·Mᵀ there. Lift the xfail. The unit replay digests
      (`python -m tests.unit_replay`) and `tests/test_acceptance_indexing.py`
      either stay unchanged or have each move named.
- [x] Skill: none expected.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_reduce.py tests/test_indexing_reduce_boundaries.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- [WP-1923](1923-a-candidate-in-its-conventional-setting.md) (the exact
  change of basis); [WP-1930](1930-a-width-freed-on-its-floor-leaves-it-by-rounding.md)
  (where the case surfaced); [WP-1932](1932-two-candidates-compared-across-a-reduction-boundary.md).
- #1131: taken by @mustachefeeling, with the plan this WP's handover follows.
- Křivý & Gruber (1976), *Acta Cryst.* **A32**, 297-298 (the reduction's
  steps); Grosse-Kunstleve, Sauter & Adams (2004), *Acta Cryst.* **A60**, 1-6
  (the ε every comparison in it uses).

## Handover log

- **2026-10-23** — built, as planned on #1131 (taken by @mustachefeeling).
  `reduce_cell` now builds every reduced cell from M·G·Mᵀ, so the cell it
  returns is the exact image of its input under the change of basis it
  records, on every centring and near a right angle too. The defect was not
  F-specific: a primitive cell one angle 1e-5° from 90° hit it in about a
  third of random draws.
  *Done*: (1) the WP's cell pinned as an `@example` of
  `test_the_reduced_cell_is_the_exact_image_of_its_input`, strict xfail on
  C and F first (the same input fails on C too, 5.4e-8 of max|G|; P, I and R
  pass). (2) *The path*, traced step by step with gemmi's own
  `niggli_step`/`normalize` alternated (black box; it reproduces
  `niggli_reduce` to the bit on this cell). On F, after step 4 η = −1.26e-5
  (ε = 1.0e-4). A `normalize` then flipped ζ and kept η, where the basis
  change it recorded flips η too: the image's η is +1.26e-5, the signs
  disagree, G₁₃ is 1.26e-5 off. A Křivý-Gruber step (ξ ← ξ − η·sgn ζ) then
  carried that wrongly signed η into ξ. A second `normalize` flipped η back,
  so every sign agreed at the end, and ξ sat 2|η| off the image: G₃₂
  −1.4595751 against −1.4595625, 1.09e-7 of max|G|, as WP-1930 recorded.
  WP-1923's rule kept gemmi's cell wherever no sign disagreed, so this
  returned gemmi's vector. The WP's hypothesis was right in kind: a sign
  that agrees and a value gemmi moved within ε. Now the cell is always
  `_cell_from_metric(M·G·Mᵀ)`; the sign check and `_metric_of_g6` are gone.
  A primitive case, (3, 4, 5 Å, 89.99999°, 70°, 80°), does the same through
  ξ at 2.9e-7 and is pinned beside it. The xfail is lifted.
  *Measured* (macOS arm64, worktree `.venv` `[dev]`, Python 3.12). Old path
  against the image over 20 000 random cells (60-120°): none off by more
  than 1e-12 of max|G|. With one angle 90° ± {0, 1e-7, 1e-5, 3e-4, 1e-2}°,
  1500 a centring and offset: P 494 and 434 of 1500 off at 1e-7 and 1e-5
  (worst 5.6e-7), C 22 and 23, I 16 and 10, R 1 and 1, F none; none at 0,
  3e-4 or 1e-2. The new cell changes parameters by at most 2.2e-14 relative
  on generic cells, rounding. `reduce_cell` 17.2 → 19.3 µs.
  *What moved*: nothing measured. Unit replay (`python -m tests.unit_replay`,
  captured once, replayed on both trees): all 22 unit digests and the 3 pool
  digests (brucite, corundum, synthmono_ip, whose dedup runs
  `equal_reduced_many` through #949's `_equal_across_boundaries`) are
  identical. `tests/test_acceptance_indexing.py`: 44 passed on both trees.
  *Skill*: none; no name an agent calls changed. `src/rietx/indexing/CLAUDE.md`'s
  exact-image clause now says the cell is built from M·G·Mᵀ, never gemmi's
  vector. The 1.10.0 staging file has one note under `## Changed`.
  *Generality*: no `_audit` row; no code, default, module-level number or
  field is added.
  Next: review on the PR; closing moves this narrative to the release record.

- **2026-10-23** — created by WP-1932's close, from its `### Inherited` entry
  of 2026-10-13, after re-running the case on today's tree. No open WP owns
  `reduce_cell`'s exactness. 1452 replaces spglib, 1528 declines a declared
  cell's box, and 1921 indexes a user's database, and none of them changes
  the reduction.

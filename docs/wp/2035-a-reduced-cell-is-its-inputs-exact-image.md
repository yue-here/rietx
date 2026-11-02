# WP-2035 — a reduced cell is its input's exact image, near a right angle too

Milestone: unscheduled · Status: ✅ 2026-11-01 — a reduced cell is its input's exact image (PR #1136); the near-90° property judges it by the Niggli conditions at ε, closing issue #1252 (PR #1300)
Track: What fires, and what stays silent
Depends on: — (1923, closed: the exact change of basis; 1932, closed: the boundary-free comparison that reads it)

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
- [x] Issue #1252 (2026-11-01): the near-90° property compared the reduced
      cell with gemmi's ε-reduced G6 vector, which drifts from the image by up
      to 2 ε. Judge the cell by the Niggli conditions at ε instead
      (`_niggli_violation` in `tests/test_indexing_reduce.py`), and pin the
      issue's cases with `@example`. A test-only change.

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

- **2026-11-01** (ghostshift runner, PR #1300, closed) — the flaky property test is fixed, and the WP closes. The test that a reduced cell is its input's exact image used to end by comparing the cell with gemmi's own reduced vector to within ε. That vector is not exact: near a right angle gemmi fixes the sign of a near-zero parameter without recording it, and the error grows through the later steps to as much as 2 ε. So the test failed about one CI run in 40 while `reduce_cell` was right. The test now asks whether the cell meets the Niggli conditions at ε, which is what the comparison was meant to ask. No package code changed apart from one docstring.
  *Done*: (1) `_assert_exact_image` ends with `_niggli_violation(got, ε) <= 0`, a helper in `tests/test_indexing_reduce.py` that encodes Gruber (1973) eq. 3 and Křivý & Gruber (1976) steps 5-8 with ε placed as gemmi's `normalize`/`niggli_step` place it (read from gemmi 0.7.5's `cellred.hpp`). gemmi's `is_niggli` cannot serve: its normalisation test has no ε, and it rejects gemmi's own C and F output at any ε. (2) Four `@example`s on the near-90° property: the issue's (3, 3, 21, 89.99999°, 65°, 65°) and (21, 3, 3, 90.00001°, 65°, 111°), WP-2011's offset 6.905e-6 case, and an I-centred draw where gemmi's vector sat 1.99 ε off. Each fails the old reference on at least one centring (1.65, 1.14, 1.05 and 1.99 ε) and passes the new one. (3) The review pass (`/code-review high --fix`) corrected `reduce_cell`'s docstring, which claimed the image sits under ε from gemmi's vector, regenerated the index and fixed the release record's count of pinned issue cells. It also suggested a helper in `src` for ε so the test cannot drift from `reduce_cell`'s formula; declined, as a new name in `src` for a test-only fix.
  *Measured* (macOS arm64, worktree `.venv` `[dev]`, Python 3.12, gemmi 0.7.5; scripts in `~/.cache/ghostshift/rietx/wp-2035/`). gemmi's ε-vector against the image over 40 000 near-right cells a centring (one angle 90° or 90° ± 1e-7 to 1e-5°): worst 1.27 ε (P), 0.62 (C), 1.99 (I), 0.00 (F), 0.33 (R). `_niggli_violation` on `reduce_cell`'s output over 40 000 a centring of mixed near-right and generic cells: no violation, closest margin 0.012 ε (P, the shared-sign condition), at least 0.35 ε on the other centrings. The deliberate failure: an unreduced input and an image under a transposed change of basis break the conditions by 1e5 to 1e8 ε on every pinned cell. Seed stress as the reporter ran it, the near-90° property alone on an empty example database: 200 seeds (1-200), none failed, where the reporter measured 5 of 200 on the old reference. *Siblings* (the class: a test whose reference moves with ε by more than its bar): the only gemmi-at-ε comparison in `tests/` was this one. The idempotence (bar 1e-6) and unimodular-invariance (bar 1e-4) properties on 20 000 near-right cells: worst 1.4e-14 and 5.6e-7, so neither is exposed. `tests/test_restraints.py`'s `_reduced` builds inputs and compares nothing.
  *Gates*: `test_indexing_reduce.py` + `_boundaries.py` 137 passed (`-n 4`). The fast selection was queued behind this machine's suite lock (another shift's suite and a 75-min slow gate ahead) and withdrawn unrun; CI's fast matrix on the ready PR is its gate. `python -m tests.reader_output` exit 0, unchanged. `test_acceptance_indexing.py` not run: the only `src` change is a docstring.
  *Generality*: no judge dispatched; no `_audit` row moved and the package gains no heuristic (the helper is a test oracle).
  *Next*: none. Issue #1252 closes with the PR.

- **2026-10-31** (ghostshift close-batch, PR #1287, not closed) — the code is finished and the test is not. A reduced cell is the exact image of its input on main, as PR #1136 shipped. But issue #1252, a fast-suite property test that fails on main about 1 run in 40, is still open and unfixed, and it is this WP's own Inherited task. So the WP stays open.
  *Checked against main `1314c69ea`*: `tests/test_indexing_reduce.py` still ends the exact-image property by comparing `reduce_cell` with gemmi's `niggli_reduce` at ε = `NIGGLI_EPS_RELATIVE`·V^(1/3) (lines 442-452). No `@example` pins the issue's case P (3.0, 3.0, 21.0, 89.99999°, 65°, 65°), and the one commit to that file after the WP's own (`7de1da3dc`, 37 added lines) is a `bravais_screen` case, not this property. The Inherited entry of 2026-10-31 stands as written: the defect is in the test's reference, not in `reduce_cell`, and the fix is a tighter reference or a bar near 2 ε plus the `@example`. #1252 is open.
  *Next*: the #1252 task, then the close (the v1.11 record's narrative, ✅, delete `Priority:` and `### Inherited`). It is P2 because the fast check goes red on main at random.

- **2026-10-26** — merged from outside as PR #1136 (`6823e532`), after four
  review rounds; the claim issue #1131 is closed. Every task above is done, so
  a reduced cell is now the exact image of its input on main, on every
  centring and within ε of a right angle. *Gated*: #1136 and #1128 stacked onto
  main `c0d701cd` as `669ab69a`; `[dev,jax]` venv, macOS arm64, Python 3.12,
  nothing else running; fast selection 11 914 passed, 199 skipped, 28 xfailed;
  the whole `-m slow` suite, `test_acceptance_indexing.py` included, 419
  passed, 12 skipped, 15 xfailed. Main after both merges is identical to the
  gated tree. *Review's late findings*: the release note had to move from the
  released `1.10.0.md` to `1.11.0.md` and compare with 1.10.0; nothing in the
  code changed after round 2. *Next*: the close, which moves this narrative
  into the v1.11 record and sets ✅.

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
  vector. The 1.11.0 staging file has one note under `## Changed`.
  *Generality*: no `_audit` row; no code, default, module-level number or
  field is added.
  Next: review on the PR; closing moves this narrative to the release record.

- **2026-10-23** — created by WP-1932's close, from its `### Inherited` entry
  of 2026-10-13, after re-running the case on today's tree. No open WP owns
  `reduce_cell`'s exactness. 1452 replaces spglib, 1528 declines a declared
  cell's box, and 1921 indexes a user's database, and none of them changes
  the reduction.

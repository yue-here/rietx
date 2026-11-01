# WP-1804 — the derived block: a nonlinear map applied after the affine one

Milestone: rigid-bodies · Status: ✅ 2026-10-23 — built in PR #773 (`f5f35593`); closed with the chained tie-source refusal
Depends on: 1801, 1803 (the record)

## Goal

`ParameterTable` gains `derived: list[DerivedBlock]`. A block maps declared input
entries, and the cell, to declared output entries through a closed-form map in `xp`
ops. It has a `local_jacobian(θ)` and a declared `reach_pattern()`. This is chunk
R2b of issue #561.

## Context

The seam was decided by WP-1803 and is recorded in
[`docs/DESIGN.md` § Parameter system](../DESIGN.md#parameter-system), clause
"Rigid bodies: a typed `derived` block". Read that clause first. The load-bearing
parts are restated here.

- `decode` applies the blocks after the affine matmul, in declaration order. With no
  block declared it is bit-identical to today.
- `stderr_physical`, `physical_covariance` and the restraint block `(R_phys @ C)` take
  the block's **local Jacobian at θ** for derived rows. The anchor rows in C are
  2.3–2.9 % off after a 3° solve and 8–24 % after 10°, so a reader left on C is wrong.
- The five pattern readers (`moving_paths`, `column_reach`, `entry_reach`,
  `unmeasured_rows`, `_column_extras`) read the **declared** `reach_pattern()`, never
  the Jacobian's numbers. On the planar test body a rotation column's numeric reach was
  28 rows where its declared reach is 42.
- `make_traced_decode` applies the same map after its dense matmul.
- `commit` and `apply_to_models` write derived rows from the map in the slot
  `_refresh_moment_components` holds. The moment keeps its own rule; it is not migrated.
- The closed-form Cartesian frame
  M = [[a, b cos γ, c cos β], [0, b sin γ, c (cos α − cos β cos γ)/sin γ], [0, 0, V/(a b sin γ)]]
  lands here in `xp` ops. A test pins it against `crystallography.adp.cartesian_basis`,
  which keeps its Cholesky. That docstring's "no convention" disclaimer is retired.
- No new Jacobian branch. A body column takes `_peak_chain_column`, which differences
  θ through `decode`, so the data-row column is exact (8e-11 relative against the
  whole-model FD in the spike).
- `ParameterTable.set_tie` flattens a derived source into `d` today with no error. The
  table-level refusal is added here, mirroring `apply_value_scale`.

**Both body rows stay in this WP** (decided 2026-10-06, on the question in the re-cut
comment on issue #561). The change to `backend/traced.py` is a new path through jax
and torch, and root CLAUDE.md requires `tests/test_cross_backend.py`'s configs to grow
with every new derivative path. The toy C₆Br block in the PR's own tests feeds both
the cross-backend row and the stage-boundary row, so neither waits for WP-1805.

v1.6 has shipped (2026-10), so WP-1514's "waits for v1.6" no longer holds.

## Non-goals

- The `RigidBody` schema (WP-1805).
- Migrating the moment onto the block.
- Any body column in `_structural_column`.

## Tasks

- [x] `params/derived.py`: the block type, the closed-form frame and its cell derivative
- [x] `ParameterTable`: `derived`, `add_derived`, `local_jacobian`, the declared reach, the five readers switched; `add_derived` onto an unlocked row raises
- [x] `set_tie` refuses a locked or derived source, naming both paths
- [x] `optimize/least_squares.py`: `_column_extras` and the restraint block on the declared reach and the local Jacobian
- [x] `backend/traced.py`: the map after the matmul
- [x] Tests: the acceptance below, including a toy-block row in `tests/test_cross_backend.py` and a stage-boundary regeneration with a block
- [x] Skill: none. No public verb and no diagnostic code; the block is internal until WP-1805.

## Acceptance

Each is a check that can fail.

- Every `tests/data/backend_goldens/` case is bit-identical with no block declared.
- The toy C₆Br block reports coordinate esds equal to J·Cov·Jᵀ by central FD of `decode`
  to 1e-9 relative after a 3° solve. The anchor-row reader is 2.3–2.9 % off there, so a
  wrong reader fails.
- With the local Jacobian's cross-product sign flipped, the same test fails (the spike's
  planted sign gave ratios 0.17–2.5).
- The declared reach lists a row whose numeric column is zero at θ: a pivot atom of the
  toy block, under a rotation column. On the spike's planar body the same gap was 42
  declared rows against 28 numeric.
- The closed-form frame equals `cartesian_basis` to 1e-14 on 2000 random cells, and its
  `jax.jacfwd` is finite.
- `set_tie` with a locked or derived source raises, naming both paths.
- A toy-block cross-backend row agrees within the matrix's tolerance (< 5e-3).
- `tests/test_cross_backend.py`'s stage-boundary regeneration passes with a block.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_derived_block.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Coelho (2018), *J. Appl. Cryst.* 51, §3.2: TOPAS takes body-atom slopes by
  the chain rule through each atom's expression.
- Issue #561; PR #596 (the record and the proposal this WP was cut from); WP-1803.

## Handover log

- **2026-10-23** — closed. The derived block was finished before this session.
  The last unticked task, a stage-boundary regeneration with a block declared,
  had landed in PR #773's first review round. The 2026-10-07 entry called it
  open. One gap from that PR's second round remained. A tie onto a row that is
  itself tied onto a locked or derived row passed the refusal and froze its
  target with no error. That is now refused. No writer builds that shape today,
  so no fit moves.
  - **Done.** `tie_source_refusal` resolves each source through its chain, as
    `_flatten` does, and refuses when any resolved row is locked or derived
    (`c8f97968..988a5fa1`). The error names the source and the row under it.
    `_apply_ties` and `replay` word a dropped tie's warning the same way
    (`refine._tie_refusal_text`). A directly locked or derived source keeps the
    old text, which `tests/test_params_surface.py` pins.
    `test_set_tie_refuses_a_source_tied_onto_a_derived_or_locked_row` plants the
    middle link by hand, because no verb can build it. With the chain check
    disabled it fails ("DID NOT RAISE").
  - **Measured.** A probe over five space-group settings (cubic, rhombohedral,
    hexagonal, tetragonal, monoclinic) and WP-1805's `bodies` fixture found no
    tie resting on a locked or derived row. User chains heal themselves:
    `_apply_ties` drops the middle link first. Acceptance on macOS arm64,
    Python 3.12, `[dev,jax]`: `test_derived_block.py`, `test_cross_backend.py`
    and `test_params_surface.py` gave 234 passed, 70 skipped, 2 xfailed. Six
    `toy_body` and derived-block rows ran on jax, the stage-boundary row among
    them. The torch rows skip here and run in the nightly `torch` job. The fast
    selection, same venv, before the review's fix: 11243 passed, 120 skipped,
    27 xfailed, 2 failed. The added test costs 0.10 s locally.
  - **Two fast-suite failures predate this branch.** `test_examples.py`'s
    `[moment]` guide row also failed in the 2026-10-22 nightly's macOS job.
    `[qpa]` prints ±0.21 wt% where `guides/qpa.md` quotes ±2.24 (re-measured on
    2026-10-21 by `e5976784`, WP-2002). An `origin/main` snapshot run in this
    venv prints ±0.21 too. Linux CI on `main` passes. Not chased here.
  - **Review** (`/code-review high --fix`): four findings. Fixed: the drop
    warning said "structurally fixed" of a chained source; the refusal's two
    branches became one loop. Declined: the error's "would be frozen" is loose
    when some resolved rows are free, but the any-locked policy carries over
    from direct terms; `derived_paths()` rebuilt per call costs nothing at
    today's sizes.
  - **Next:** none in this WP. WP-1805 carries the body work.

- **2026-10-07** — PR #773 merged from outside as `f5f35593`, built by
  @mustachefeeling. Gated together on a nine-PR stack replayed onto `main` at
  `f99fab05` (stack `16a95cef`, macOS arm64, `[dev,jax]`). The whole suite
  gave 8912 passed, 113 skipped and 2 failed. Both failures fail identically
  on bare `main`: the `toy_anomalous` golden (#760) and
  `test_the_reduction_map_takes_a_to_f_where_the_reduction_does`. After the
  last merge, `main` at `a65dca1a` is content-identical to the gated tree.
  - `params/derived.py` holds the block and the closed-form Cartesian frame.
    `ParameterTable` gains `derived`, `add_derived`, `local_jacobian`,
    `reach_block` and `derived_paths`. The covariance and restraint readers
    take the local Jacobian. The reach readers take each block's declared
    reach. On a table without a block both readings are C, so every existing
    fit is unchanged.
  - `set_tie` refuses a locked or derived source. `tie_source_refusal` is the
    test, and `_apply_ties` and `replay` both drop such a recorded tie with a
    reason. Round 3 added the `replay` half, so a checkout and a replay of one
    node agree.
  - `toy_body` is a `tests/test_cross_backend.py` config and crosses every
    `METHODS` row. Its torch rows had not run anywhere at merge; the nightly
    `torch` job is the first place they run.
  - Still open: the stage-boundary regeneration with a block. The contributor
    puts it with WP-1805's `bodies` config, so the tests task stays unticked.
    Also open, from the round-2 review: a source that is itself tied, with
    every one of its sources locked, has an empty C row and passes
    `tie_source_refusal`. Nothing reaches that shape until the rigid-body
    writer exists.
  - Next: WP-1805, the `RigidBody` schema, which the contributor holds back
    until this merge.

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal and the
  contributor's 2026-10-06 update on #561. PR #773 builds it. The maintainer kept the
  cross-backend and stage-boundary rows here rather than in WP-1805, so #773 adds both
  before merge. Next: review #773 against this file.

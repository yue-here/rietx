# WP-2067 — The data-support count reads what drives an atom, not its name

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: — (1419 soft: the mode-amplitude family; 1805 soft: the rigid-body family)
Priority: P2 2026-10-31 — a number on the reassuring side of McCusker's band that nothing flags, on paths few fits run yet (mode amplitudes, rigid bodies)

## Goal

`DataSupport.n_structural_parameters` counts every free parameter that moves an atom, whatever its path, so the observations-per-parameter ratios a report reads against McCusker's "at least three, preferably five" band are right for mode amplitudes, rigid bodies and named variables, and for the next family that drives atoms without touching `data_support`.

## Context

From issue #1250 (mustachefeeling, 2026-10-31), raised in round 1 of PR #1107's review and recorded in WP-1419's 2026-10-30 handover as a follow-up owed by the contributor.

`optimize.statistics.data_support` (`src/rietx/optimize/statistics.py:1321`) counts structural parameters by matching free paths against `STRUCTURAL_PARAMETER_GLOB = "phases.*.atoms.*"` (`:43`, read at `:1333-1334`). Anything that drives atoms from outside `atoms.` is not counted:

- mode amplitudes (WP-1419, PR #1107): `phases.N.distortion_modes.modes.K.amplitude`, reaching x, y, z through affine rows of C (`ParameterTable._collect_mode_atom_coords`, `params/vector.py:1555`);
- rigid bodies (WP-1805/1807/1808): `phases.N.rigid_bodies.K.origin.dof.*`, `.rotation.*`, `.torsions.*.twist`, reaching atoms through a derived block (`params.bodies.RigidBodyBlock`, `params/bodies.py:155`, whose `outputs` name the atom entries it writes), not through C;
- a sibling the issue does not name: a named variable (`vars.X`, WP-1119) tied to a coordinate DOF. The free path is `vars.X` and the tied atom entry is not free, so neither is counted.

Measured at d87c8cc91 with the issue's script (`PYTHONPATH=src:.`, the three public synthetic states in `tests/test_cross_backend.py`):

| state | free structural (by hand) | `n_structural_parameters` | reflections | ratio reported | ratio true |
|---|---|---|---|---|---|
| `_state_distortion_modes` | 5 | 4 | 15 | 3.75 | 3.00 |
| `_state_bodies` | 11 | 3 | 38 | 12.67 | 3.45 |
| `_state_bodies_site` | 5 | 2 | 17 | 8.50 | 3.40 |

"By hand" is every free `phases.*` path except the cell and the scale. In the body case the reported ratio clears "preferably five" while the true one sits near three.

This is root CLAUDE.md's "A freeze resting on flatness needs the other reading of C" rule (WP-1342) applied to a count: a test on a parameter's *name* cannot see what a column reaches. The reading exists: `ParameterTable.column_reach()` (`params/vector.py:3892`) gives each free column's reached entries off C. Derived blocks are outside C, so the count also needs each block's `outputs`. `data_support` takes `(model, values, free_paths)` today, not the table, so the seam moves one argument.

`DataSupport`'s docstring (`schemas/results.py:241-243`) describes the count as the atomic entries only and changes with it.

Tier: physics (McCusker et al. 1999 §9 defines the count as structural parameters); no new judgement, no threshold.

## Non-goals

- The band itself (three, preferably five) and its report wording: unchanged.
- Counting cell, scale, profile or background parameters: McCusker §9 is about structural ones.
- Joint fits' per-histogram data-support diagnostics: WP-2028.

## Tasks

- [x] Define "structural" as a free column that is an atom entry or reaches one, through C (`column_reach`) or through a derived block's `outputs`; `data_support` reads it from the table. Retire `STRUCTURAL_PARAMETER_GLOB` or keep it as the atom-entry test only, saying which. (PR #1276: `optimize.statistics.structural_free_paths`; the glob is kept as the atom-entry test.)
- [x] `DataSupport`'s docstring and the manual's description of the count. (PR #1276: `schemas/results.py:241`, `reference/result.md:137`, `theory/estimation.md:116`.)
- [x] Tests: one state per family (plain atoms, mode amplitudes, rigid body, a `vars.X` tied to a coordinate DOF) asserting the hand counts above; a positive arm that a plain-atoms fit is bit-identical. (PR #1276: `tests/test_data_support.py`; the positive arm asserts the count path for path equal to the name test's.)
- [x] `_audit` row for the count if it has one (check `tests/audit_delta.py`). (None: `DATA_SUPPORT_LOW` has its row, and the count is not a heuristic.)
- [x] Skill: none; the count is the package's own output.
- [x] `add_derived` refuses a `frame_inputs` name that is not an input (the follow-up PR #1276's merge entry left).
- [x] The purpose table's sibling: a warning naming a mode amplitude or a rigid body keeps its level wherever a coordinate's does (`purposes._ATOM_DRIVERS`), held to `structural_free_paths` by `tests/test_summary_levels.py`.

## Acceptance

The three states above report 5, 11 and 5 structural parameters; every plain-atoms fixture's `DataSupport` is unchanged.

```sh
.venv/bin/python -m pytest tests/test_data_support.py tests/test_cross_backend.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker, L. B., Von Dreele, R. B., Cox, D. E., Louër, D. & Scardi, P. (1999), *J. Appl. Cryst.* 32, 36–50, §9.
- Issue #1250; PR #1107's review (round 1).

## Handover log

- **2026-11-01** (`/pr-review`) — merged from outside as PR #1276 (`3c1e3ad7`), closing #1250. The data-support count (McCusker 1999 §9) reads what each free column reaches through `table.column_reach()`. A variable that drives an atom now counts as structural, and one that drives only a scale does not. `DerivedBlock.frame_inputs`, with `RigidBodyBlock` as its one writer, keeps a body's cell input from counting as structural. `DATA_SUPPORT_LOW` fires on more fits as a result. No audit row changed. The diff touches `optimize/statistics.py`, the `DataSupport` docstring, `reference/result.md`, `theory/estimation.md`, `tests/test_data_support.py` and the 1.11.0 release note. That covers tasks 1 to 3, and task 4 needed no row. The PR ticked nothing, so the boxes stay for the maintainer. Follow-up, not blocking: nothing asserts that `frame_inputs` is a subset of `inputs`. What ran: the PR was replayed in a stack of nine with the other round's merges onto `main` `276fe91d` and run at `635d25e3` (Mac arm64, Python 3.12, `[dev,jax]`). Full suite 14 161 passed, 235 skipped, 50 xfailed, 0 failed. The manual `-W` build was green.

- **2026-10-31** — created, from the issue triage (issue #1250). No open WP owns the count: WP-1071, which built it, is closed; WP-1419 and WP-1805 each own one family, and the fix belongs in the one statistics authority rather than per family; WP-2028 is about joint fits.

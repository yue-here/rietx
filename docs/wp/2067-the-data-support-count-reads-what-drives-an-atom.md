# WP-2067 — The data-support count reads what drives an atom, not its name

Milestone: unscheduled · Status: ✅ 2026-11-01 — the count reads what each free column reaches (#1276); the purpose table's sibling and the frame-input guard close it (#1289)
Track: What fires, and what stays silent
Depends on: — (1419 soft: the mode-amplitude family; 1805 soft: the rigid-body family)

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
- [x] The purpose table's sibling: a warning naming a mode amplitude or a rigid body keeps its level wherever a coordinate's does (`purposes._ATOM_DRIVERS`), held to `structural_free_paths` by `tests/test_data_support.py::test_the_count_reads_what_a_column_reaches`.

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

- **2026-11-01** (ghostshift runner, PR #1289) — closed. The count itself had already landed from outside in #1276, and this session checked each of its claims at its line before ticking the boxes. The same name test lived in a second place. The purpose table decides whether a warning prints in full under a declared deliverable, and it matched paths by name. So a warning on a mode amplitude printed as a one-line info under structure, qpa and magnetic, and one on a rigid body's origin, rotation or twist did so under qpa and magnetic. A warning on the coordinates those parameters move printed in full. Both families now bear wherever a coordinate does. A derived block that names a frame input it does not read is now refused. No fitted number moves.

  *Done.* Verified at `feedcc23`: `optimize.statistics.structural_free_paths` reads `table.column_reach()` and drops a block's `frame_inputs`. `STRUCTURAL_PARAMETER_GLOB` is kept as the atom-entry test (`statistics.py:46`). The docstring and both manual pages carry the new definition (`schemas/results.py:241`, `reference/result.md:137`, `theory/estimation.md:116`). The four family states report 5, 11, 5 and 2, and the plain-atom states count path for path what the name test counted. Tasks 1-5 ticked on that evidence. Added: `ParameterTable.add_derived` refuses a `frame_inputs` name outside `inputs` (`test_add_derived_refuses_a_frame_input_that_is_not_an_input`). Added: `purposes._ATOM_DRIVERS` (`phases.*.rigid_bodies.*`, `phases.*.distortion_modes.*`) spliced into the `structure`, `qpa` and `magnetic` globs. Its guard sits inside `test_the_count_reads_what_a_column_reaches`, so a family state in `_FAMILY_COUNTS` is built once and checked for both. Both guards were failed on purpose once: the subset check disabled gave `DID NOT RAISE`, and `_ATOM_DRIVERS` without bodies failed the two body states.

  *Siblings swept.* `grep` over `src/rietx` for name tests on `atoms.` paths. `refine.mode_fixed_path` lists bodies and modes and has its column-reach twin `mode_fixed_column` (WP-1342). `least_squares._INTENSITY_ONLY` is an allow-list whose miss costs work and is verified at use. Neither is the defect. Not generalised: `vars.` paths already bear on every purpose (`schemas.results._bears_on`), and joint-fit data support stays WP-2028's.

  *Review.* `/code-review high --fix` found no bug and made three fixes, all committed: the guard reads the count's family list, the WP-1419 caveat names both misreadings, a docstring line rewrapped. Its fourth finding, a duplicate 6 s state build, was taken here by folding the purpose check into the count test.

  *Measured* (Mac arm64, Python 3.12, `[dev]`, branch with `origin/main` merged at `6fd5d056`, through the shift's suite lock). Fast selection: 13 163 passed, 310 skipped, 32 xfailed, 0 failed. This session added one test (0.01 s, `tests.added_test_times`), and the folded check added no test. Full selection not run: the change moves a printed level and a construction-time refusal, never a fitted number. Acceptance rows `tests/test_data_support.py tests/test_cross_backend.py`: 161 passed, 153 skipped before the fold.

  *Forwarded.* WP-1419 `### Inherited`: if its metric-subspace task puts a cell-driving path under `distortion_modes`, narrow `_ATOM_DRIVERS` to `…modes.*.amplitude` and list that path under `cell` and `phase_id`.

  *Generality* (the `generality-review` agent, unedited).

  > **Item 1: `purposes._ATOM_DRIVERS`. Verdict: holds.** The case for acting is much stronger. It makes the purpose table agree with what the two families move. Against it the judge found nothing beyond the extra attention a warning costs, which applies equally to the coordinate rows already in the table. Kind of ambiguity: Rule 1's first kind (the data settle it); `RigidBodyBlock.outputs` holds only atom x, y, z (`params/bodies.py:186`), and a mode amplitude reaches coordinates only through affine rows of C. Tier and source: **weak (the tier label and the test's claim).** Tier 1 (physics or arithmetic) fits; `invariant` does not, since that class covers answer-invariant efficiency settings with a margin-asserting invariance test. The test's docstring overstated its reach: it fails for a new family only once that family's state joins the parametrize list. What would change the verdict: a path under `rigid_bodies` or `distortion_modes` that moves something other than an atom coordinate, such as a future cell-strain mode, which would wrongly bear on `magnetic`.
  >
  > **Item 2: `add_derived` refuses a `frame_inputs` name that is not an input. Verdict: holds.** A consistency check on an internal declaration; it decides nothing about the answer. Tier 1, not a heuristic. Without it, a typo would leave the real frame input counted as structural with no error. What would change the verdict: a public path that lets a caller build their own `DerivedBlock`, which would need a manual entry.

  Author's answer to item 1's *weak*: the tier is physics (tier 1), as the judge recommends. The docstring now says a family is checked once its state joins `_FAMILY_COUNTS`.

  *Settled by Claude.* Closing the WP rather than leaving the boxes for the maintainer, under protocol step 2 (a task is ticked by the commit that verifies it) and the merge entry's own "close owed once the tasks are ticked". The purpose-table fix went in this WP rather than a new one, under the user's standing rule to fix the class.

  Next: none in this WP. The maintainer merges #1289.

- **2026-11-01** (`/pr-review`) — merged from outside as PR #1276 (`3c1e3ad7`), closing #1250. The data-support count (McCusker 1999 §9) reads what each free column reaches through `table.column_reach()`. A variable that drives an atom now counts as structural, and one that drives only a scale does not. `DerivedBlock.frame_inputs`, with `RigidBodyBlock` as its one writer, keeps a body's cell input from counting as structural. `DATA_SUPPORT_LOW` fires on more fits as a result. No audit row changed. The diff touches `optimize/statistics.py`, the `DataSupport` docstring, `reference/result.md`, `theory/estimation.md`, `tests/test_data_support.py` and the 1.11.0 release note. That covers tasks 1 to 3, and task 4 needed no row. The PR ticked nothing, so the boxes stay for the maintainer. Follow-up, not blocking: nothing asserts that `frame_inputs` is a subset of `inputs`. What ran: the PR was replayed in a stack of nine with the other round's merges onto `main` `276fe91d` and run at `635d25e3` (Mac arm64, Python 3.12, `[dev,jax]`). Full suite 14 161 passed, 235 skipped, 50 xfailed, 0 failed. The manual `-W` build was green.

- **2026-10-31** — created, from the issue triage (issue #1250). No open WP owns the count: WP-1071, which built it, is closed; WP-1419 and WP-1805 each own one family, and the fix belongs in the one statistics authority rather than per family; WP-2028 is about joint fits.

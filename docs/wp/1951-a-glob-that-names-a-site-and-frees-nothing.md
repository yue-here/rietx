# WP-1951 — a glob that names a site and frees nothing

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-11 — a request to free one site's coordinates, or an unknown path on `set_vary`, frees nothing and says nothing; the caller can read `freed` or the return value

## Goal

A plan glob whose fixed segments name one concrete site, and which matches
no row, is reported. So is an unknown literal path on `set_vary`, with the
near-miss `STAGE_PATH_UNKNOWN` already gives a stage. A wildcard-index glob
that matches nothing stays silent, as WP-1414 decided.

## Context

**The report (issue #896).** An application lets a person flag parameters to
refine and wants to say why one will not move. The person flags Ti's
position on rutile (P4₂/mnm, Ti at 0,0,0). The app frees
`phases.0.atoms.0.dof.*`, which matches nothing, and nothing says so. The
reporter also asks for a reason on each parameter row (`held_by:
"symmetry" | "tie" | "lock"`).

**The per-row reason exists, checked at `d80ca5f4`.**
`Refinement.parameters()` (`refine.py:2290`) returns `ParameterRow`s.
`ParameterRow.held_because` (`schemas/params.py:173-203`) gives a sentence,
ordered by what the caller can do: rigid body, `locked` ("structurally
fixed by symmetry or by the model"), a tie with its sources, `mode_fixed`,
a `hold()`, a held wavelength cell. The fields it reads (`body`, `locked`,
`tie` with `tie.user`, `mode_fixed`, `held`, `needs_held_cell`) are on the
row, so a program needs no enum. The sentence gives no subject for
"symmetry or the model". `rietx.gui.symmetry.held_causes`
(`gui/symmetry.py:357`) supplies it: "a site symmetry of order 8 allows no
displacement at all".

**The silence, ran at `d80ca5f4`.**
- On rutile, Ti's `x`, `y`, `z` are locked and it has **no `dof` rows at
  all**. Only O has `phases.0.atoms.1.dof.0`.
- `ref.set_vary("phases.0.atoms.0.dof.*")` returns `[]` with no warning.
- A stage with `turn_on=["phases.0.atoms.0.dof.*"]` gives `freed=[]`,
  `unknown_paths=[]` and no diagnostic.
- A literal is already covered. `phases.0.atoms.0.x` fires
  `STAGE_PATH_NOT_FREE` with "nothing to free: every coordinate of this
  site is fixed by its site symmetry" (`refine.py:6075`).
  `phases.0.atoms.0.dof.0` fires `STAGE_PATH_UNKNOWN` with "did you mean
  'phases.0.atoms.1.dof.0'".
- `STAGE_FREED_NOTHING` exists only for a joint fit (`multi.py:1513`).

**Why globs are silent.** WP-1414 (✅) decided that "a single glob that
matched nothing on its own stays silent", because shipped plans carry globs
some models do not have (`phases.*.microstrain.dof.*` on a model without a
Stephens block). `params.vector.unknown_paths_among` (`:357`) implements it,
and two tests pin it: `tests/test_params_surface.py::
test_a_path_that_is_free_or_not_a_phase_literal_stays_silent` (its
`dof-glob` and `pattern` cases) and
`::test_a_hump_glob_on_a_model_without_a_hump_stays_silent`. The skill's
`references/surprises.md` § 8.28 tells an agent to read `StageResult.freed`.

**A narrower rule leaves that decision whole.** A glob whose fixed leading
segments name an existing site (`phases.0.atoms.0.`), and which matches no
row, cannot be a shipped plan's healthy miss. None of the 29 distinct
`turn_on` entries in `PLAN_PRESETS` has a numeric segment (counted at
`d80ca5f4`). WP-1414's `dof-glob` test case must be read before choosing:
if it is a concrete-site glob, the rule changes what it pins, and that
needs the maintainer.

**The verb half is 1414's named leftover.** Its closing entry: "`Refinement.
set_vary("instrument.zero")` returns `[]` silently, while `hold` raises
'unknown parameter path' with no near-miss. Both are one call to
`rietx._nearmiss` away, and are unowned."

**The tier of each rule this WP adds** (written 2026-11-01). The site-glob
branch of `STAGE_PATH_NOT_FREE` is tier 1, ambiguity 1: it is arithmetic on
the table (does any matched row move?), with no threshold. `set_vary`'s
warning and the verbs' near-miss are the same tests on a second surface.

## Non-goals

- A `held_by` enum on `ParameterRow`. The row's fields already say it.
  Adding the symmetry subject from `held_causes` to the sentence is in
  scope only if it is a one-line import.
- Globs with a wildcard index (1414's decision stands).
- A `PlanSpec` validator refusing unknown literals before a fit (1414 left
  it to the maintainer).

## Tasks

- [x] Read 1414's two pinned tests and say whether any case is a
      concrete-site glob. If one is, put the question to the maintainer and
      record the answer as `Decided YYYY-MM-DD:`.
      *Done 2026-11-01:* the `dof-glob` case (`phases.0.atoms.1.dof.*` on
      LaB6) is a concrete-site glob, but it matches B's free `dof.0` and is
      the test's positive arm. The rule fires only when the glob frees
      nothing, so that case still passes unchanged. The `pattern` case and
      the hump test have no numeric segment. No question for the maintainer.
- [x] `STAGE_PATH_NOT_FREE` (or a sibling code) for a concrete-site glob
      that matches no row, naming the site and why (site symmetry, from the
      same text the literal case uses).
      *Done:* `refine._site_glob_diagnostics`, the same code. It fires when
      no row the glob matches can move (`_frees_for_request`), which also
      covers a glob matching only locked or symmetry-tied rows.
- [x] `Refinement.set_vary` and `hold` on an unknown literal: the
      near-miss message `STAGE_PATH_UNKNOWN` gives a stage. `set_vary`
      warns. Whether `hold` keeps raising is recorded.
      *Done:* `set_vary` warns (`UserWarning`) on an unknown literal, and
      when freeing on a declined phase literal or site glob, with the
      stage's text. `hold` keeps raising, since it always has and a hold on
      nothing is a claim; the refusal now names the nearest path, as do
      `unhold`, `untie`, `tie`, `set_values` and `profile_interval`.
- [x] Tests: rutile Ti's `dof.*` fires, `phases.*.atoms.*.dof.*` on the same
      model stays silent, every preset on the acceptance fixtures fires
      nothing new.
      *Done:* `tests/test_params_surface.py`. The preset half is structural
      (`test_no_preset_names_one_site`): the rule needs a concrete site
      index, and no preset glob has one.
- [x] Skill: `surprises.md` § 8.28 gains the concrete-site case. The
      diagnostics reference row if the code is new.
      *Done:* § 8.28, trimmed to stay inside the file's byte budget. The
      code is not new, so the row stands; `help.py`'s entry gains the case.

## Acceptance

On rutile, freeing `phases.0.atoms.0.dof.*` reports Ti as fixed by site
symmetry. `set_vary` on an unknown literal warns with the nearest path.
Every shipped preset fires nothing new on the acceptance fixtures.

```sh
.venv/bin/python -m pytest tests/test_params_surface.py tests/test_skill.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #896.

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #896).
  Checked against the tree at `d80ca5f4`: `held_because` and the row's fields
  already give the reason, Ti on rutile has no `dof` rows, and a glob naming
  it frees nothing with no diagnostic. No open WP owns it: WP-1414 (the
  turn-on report) and WP-1435 (holds) are closed, and WP-1341 inherits only
  the joint fit's `STAGE_PATH_NOT_FREE`. *Next:* task 1.

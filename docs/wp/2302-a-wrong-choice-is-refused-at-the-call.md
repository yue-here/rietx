# WP-2302 — A wrong choice is refused at the call, and a requested window has one name

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-23 — a defect that fires wrongly: a misspelt `mode` raises late with an error naming an internal schema, and `Refinement.parameters(mode=...)` answers silently

## Goal

Every public call that takes a choice refuses a value outside it before any work is done,
with a message that names the argument and the valid choices. A meta-test holds that across
the public surface. Every argument that requests a 2θ window is spelled `two_theta_limits`.

## Context

**The rule this WP applies.** [DESIGN § Rules](../DESIGN.md#rules), 4, "A new API", amended
2026-11-23: "Otherwise a literal the call cannot honour raises before any work, naming the
argument and the fix." Rule 5's convention clause, amended the same day: a convention that
lets a caller's likeliest mistake pass in silence is a convention found wrong. The survey is
[`../practice.md`](../practice.md) § How an API meets a caller's mistake (Bloch's fail fast,
Russell's misuse scale). The review, the probe and both plans are in
[`2302-batch/plans.md`](2302-batch/plans.md).

**What a misspelt `mode` does today** (measured 2026-11-22 on `f9adf0e57`, NAC example,
`tests/data/11BM_NAC.fxye` with `cod_1000236.cif`). `mode` is typed `Mode`, a `Literal`
(`schemas/common.py`), and nothing checks it on entry:

| Call | Result |
|---|---|
| `refine(mode="rietvled")` | raises a pydantic `ValidationError` about `RefinementResult.mode` after 2.8 s of a 4.1 s fit |
| `refine`, `refine_sequential` with `"lebial"` | the same error, within 0.3 s |
| `Refinement.fit`, `Refinement.run_stage` | raises at once, an error about `RefinementState` |
| `refine_multi` | raises at once: "unknown mode 'lebial'; a joint fit runs 'rietveld' or 'pawley'" |
| `Refinement.parameters(mode="lebial")` | returns a list, no warning |

`Refinement.suggest(mode=)` and `SequentialRefinement.fit(mode=)` take it too and were not
probed. `refine_multi`'s message is the form to copy.

**The wider class.** 22 more public arguments take a choice as a plain `str`. Among them are
`solver`, `backend`, `refit`, `direction`, `kind` (`auto_background`), `prefer` (`merge`),
`metric` (`RefinementTree.best`), `on_error` and `nuclear_group`. `solver` and `backend`
already refuse at the call and name their choices (`backend/api.py`). Check each against its
registry where one exists: `least_squares.SOLVERS`, `backend.api.BACKEND_NAMES`,
`PLAN_PRESETS`, `get_args(Mode)`. Never type an argument as a `Literal` that copies a registry,
since that is a second authority. Free text (`label`, `title`, `header`, `x_label`) is not a
choice.

**M1, the meta-test.** A new `tests/test_api_choices.py`. It passes every choice argument of a
public callable a bad value and asserts a `ValueError` whose message names the argument. It
patches `model.forward.compile_model` to fail if reached, so "before any work" is checked. The
valid members come from the live registries. A table in the test gives each callable a cheap
example call; a choice argument with no row fails, naming the callable. Add one entry for M1
to the project CLAUDE.md § Invariants.

**The window names** (measured 2026-11-22). `two_theta_limits` is used by 10 public calls.
`two_theta_range` is used for a requested window by `pick_peaks`, `fit_peaks`,
`rx.viz.plot_result` (`viz/plots.py`) and `indexing.pick.pick_peaks_with_state`. GSAS-II's own
term is "Limits". `DataRef.two_theta_range` (`schemas/project.py`) is different: it describes
the span the data covers and is stored in `project.json`, so it keeps its name. The split this
WP writes into the docstrings is that "limits" requests a window and "range" describes one.
The fields in `schemas/indexing.py` and `report/schemas.py` named `two_theta_range` are
measured against that split before anything moves. No compatibility shim: a shim needs `**kw`
or a sentinel, and rietx's few users are in direct contact. The changelog names each rename.

**The "how many" family.** `top_n` (`build_report`, `Refinement.suggest`), `top_k`
(`solve_magnetic`), `max_classes` (`determine_extinction_symbol`) and `check_top`
(`index_pattern`). They may not mean the same thing. Measure what each counts before renaming
any.

**`path` keeps both meanings** (settled by Claude 2026-11-23, at the maintainer's instruction
"you make the calls … only about building the best api"). `path` names a file in every writer
and a parameter dot-path in `tie`, `help_for` and `profile_interval`. The dot-path is rietx's
one term for a parameter's address, in arguments (`path_globs`, `paths`) and in fields
(`ParameterRow.path`, `free_paths`), and a hierarchical address that globs match is a path
across fields (a JSON or XML path, Python's dotted import path). Renaming only the arguments
to `param` would spell one idea two ways, arguments against fields (Rule 5, convention), and
renaming the concept would take a name ("parameter name") rietx already uses for variables,
phases and atoms. Python's word for a file argument is also `path`. So each `path` argument's
docstring and type say which: a file is `str | os.PathLike`, a dot-path is `str` and its
docstring names it a parameter dot-path.

Tier of what this WP adds: none. A refusal of a value outside a declared set is not a
heuristic, so `_audit` gains no row.

## Non-goals

- Glob verbs that return `[]` in silence: WP-2303.
- Reader repairs that reach no one: WP-2304.
- `set_vary(path, False)` undone by a plan: WP-2300 (its `### Inherited`, 2026-11-23).
- Replacing the `**kw` forwarders (`refine_sequential`, `Project.fit`, the `report` methods).
  They already raise `TypeError` at binding, naming the bad keyword, and explicit copies would
  break `Project.fit`'s `kw.setdefault` (2302-batch/plans.md, Plan 2 F).
- The 209-name top-level namespace, long keyword-only lists, paired function-and-method
  spellings (plans.md § Not done, with reasons).

## Tasks

- [ ] `mode` checked on entry in every public call that takes it, through one helper with
  `refine_multi`'s message form; `Refinement.parameters(mode=)` refuses too.
- [ ] Survey the other choice arguments: list which refuse at the call today, and check the
  rest against their registry on entry.
- [ ] M1: `tests/test_api_choices.py`, registry-driven, `compile_model` patched; the CLAUDE.md
  Invariants entry.
- [ ] `two_theta_range` → `two_theta_limits` on the four calls that request a window; the
  docstrings state the describe/request split; the two schema fields measured against it.
  Manual, skill, examples and GUI callers follow.
- [ ] Each `path` argument says which it is, in its type and its docstring's first mention.
- [ ] Measure the "how many" family and rename only where two names count the same thing.
- [ ] Tests for each refusal (the message names the argument; no compile reached).
- [ ] Skill: none expected. The refusals name their own fix, and the renamed arguments reach
  the generated `api.md`. Re-check at handover.

## Acceptance

`refine(mode="rietvled")`, `Refinement.fit(mode="lebial")` and
`Refinement.parameters(mode="lebial")` each raise `ValueError` naming `mode` and its three
choices, with no compile. M1 passes and fails on a choice argument added without a check.

```sh
.venv/bin/python -m pytest tests/test_api_choices.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
```

## References

- Bloch, J. (2006), "How to Design a Good API and Why it Matters", OOPSLA 2006 slides.
- Russell, R. (2008), "How Do I Make This Hard to Misuse?", ozlabs.org/~rusty, 30 March.
- NumPy NEP 52 (2023), Python API cleanup for NumPy 2.0.

## Handover log

- **2026-11-23** — created from the API review (2302-batch/plans.md). No open WP owns
  refusing a choice at entry: WP-2005 tiers refine.py's codes and literals, and WP-2103 gives
  the joint fit the single fit's verbs. Next: the `mode` helper, then the survey.

- **2026-11-23** — the `path` question settled by Claude at the maintainer's instruction:
  keep `path` for both meanings, with each argument's type and docstring saying which
  (§ Context). A task is added for it.

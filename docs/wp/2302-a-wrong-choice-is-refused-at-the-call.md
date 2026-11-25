# WP-2302 — A wrong choice is refused at the call, and a requested window has one name

Milestone: unscheduled · Status: ✅ 2026-11-25 — PR #1845
Track: What fires, and what stays silent
Depends on: —

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

- [x] `mode` checked on entry in every public call that takes it, through one helper with
  `refine_multi`'s message form; `Refinement.parameters(mode=)` refuses too.
- [x] Survey the other choice arguments: list which refuse at the call today, and check the
  rest against their registry on entry.
- [x] M1: `tests/test_api_choices.py`, registry-driven, `compile_model` patched; the CLAUDE.md
  Invariants entry.
- [x] `two_theta_range` → `two_theta_limits` on the four calls that request a window; the
  docstrings state the describe/request split; the two schema fields measured against it.
  Manual, skill, examples and GUI callers follow.
- [x] Each `path` argument says which it is, in its type and its docstring's first mention.
- [x] Measure the "how many" family and rename only where two names count the same thing.
- [x] Tests for each refusal (the message names the argument; no compile reached).
- [x] Skill: none expected. The refusals name their own fix, and the renamed arguments reach
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

- **2026-11-25** — closed (PR #1845; ghostshift runner, one session). A misspelt choice now
  fails at the call that took it, before any work, with a message that names the argument,
  every valid choice and the nearest one. Before, `refine(mode="rietvled")` ran most of a
  fit and then raised a pydantic error about an internal schema, and `parameters(mode=...)`
  answered without a word. A test now finds every choice argument on the public surface by
  itself and calls each with a bad value, so a new one cannot arrive unchecked. The window
  argument is `two_theta_limits` everywhere it requests a window. Both issues the triage
  folded in are fixed: the did-you-mean hint quotes each suggestion on its own (#1837), and
  an origin-2 operation list under the bare symbol is refused naming `F d -3 m:2` (#1835).
  Next: nothing in this WP. If #1838 (WP-2305) merges first, `tests/test_api_choices.py`'s
  three joint-fit keys need its new names, and the test's failure message says so.

  *Done.*
  - One helper, `_nearmiss.check_choice(argument, value, choices)`, with
    `schemas.common.check_mode` and `backend.api.check_backend` over it. `mode` is checked
    on entry by `refine`, `Refinement.fit`, `run_stage`, `parameters`, `suggest`,
    `SequentialRefinement.fit`, `Project.create` and the joint `parameters`.
  - Survey (probe with `compile_model` patched to raise): `refit`, `direction`, `on_error`,
    `solver`, `plan`, `deliverable`, `radiation`, `p1_expand` and `Structure.from_cif`'s
    `nuclear_group` already refused at the call. These did not: `mode` (seven calls);
    `auto_background(kind)` (after the pattern diagnosis, listing no choices);
    `index_pattern(preset)` (after picking peaks) and `engines` (no check);
    `merge(prefer)` (after resolving the other branch); `RefinementTree.best(metric)`
    (answered "no node carries statistics yet" for a misspelt metric);
    `solve_magnetic(nuclear_group)` (late, inside `magnetic_supercell`);
    `GuardFinding.nonpositive_resolution(width)` (any other word gave the Gaussian
    finding). All now refuse at entry through the helper. An unknown backend is a
    `ValueError`, not `NotImplementedError`; the manual's sentence moved with it.
  - M1: `tests/test_api_choices.py`. A choice argument is a `Literal` annotation, or a
    name in `CHOICE_NAMES` whose type admits `str`; 52 rows, one `NOT_CHOICES` entry
    (`FitReport.action(kind)`, a lookup). Failed on purpose once (the `parameters` and
    `suggest` checks removed: 3 failures, `CompileReached` among them). CLAUDE.md
    § Invariants gained one entry; the 1.0.2 sentence was shortened to pay for it.
  - #1837: `_nearmiss.quoted` joins `'a', 'b' or 'c'`. Its sibling, an unexported name
    answered with the nearest spelling (`rx.structure_from_cif` → `MicrostructureTerm`),
    now names the defining module ("import it from rietx.crystallography.cif"), read
    off the already-imported submodules.
  - #1835: `schemas.structure._setting_matching` compares the list with every gemmi
    setting of the symbol's number; a match is named in the refusal. The constructor
    still refuses, because the schema has no channel to record a relabel (settled by Claude
    2026-11-25 under CLAUDE.md § Invariants, "a silent correction is a reader's to make").
  - `two_theta_limits` on `pick_peaks`, `pick_peaks_with_state`, `fit_peaks`,
    `detect_peaks`, `rx.viz.plot_result`, `plot_pattern`, and the `plot` methods that
    forward to them. Measured against the split: `ExtinctionScreen.two_theta_range`,
    `SuggestedAction.two_theta_range`, `DataRef.two_theta_range`, a reader scan's and
    `GsasHistogram`'s each describe a span, so they keep the name. The GUI's stored
    `pick_options` key and the `/api/peaks` body key stay `two_theta_range`: renaming
    them is a stored-format change. Release note `docs/releases/unreleased/1845.code-to-check.md`.
  - `path`: file arguments are typed `str | Path` (the untyped writers, the `plot`
    methods and `plot_trajectory` gained it); dot-path arguments say "dot-path" in their
    docstrings. `test_every_path_argument_says_which_path_it_is` holds both;
    `GuardFinding`'s factories are exempt with a reason.
  - "How many" family, measured: `top_n` counts the rows returned or listed in full
    (`build_report`'s misfit regions, `suggest`'s groups), the same thing under one name
    already. `check_top` (cells given ambiguity and validation), `top_k` (propagation
    vectors carried to trial fits) and `max_classes` (extinction classes fitted) each cap
    the candidates given expensive work in a different search. No rename (settled by
    Claude under this WP's rule, "rename only where two names count the same thing").
    `top_k` is on the magnetic path, which is Mike's to rename if ever.
  - Skill: no row named the old messages or `two_theta_range`; `api*.md` regenerated and
    the two copies re-synced.

  *Measured.* Fast suite `[dev]` venv, darwin/arm64: 15789 passed, 452 skipped, 30 xfailed, 3 failed in 9.5 min (a stale generated API index, a docstring naming a non-name, a test matching the old nuclear_group message); fixed in `2cf2e1821` and those files re-run green (557 passed). The review's fixes re-ran their files (405 and 258 passed).
  This session adds 56 tests (55 in `test_api_choices.py`, one in
  `test_operator_list_phase.py`). `python -m tests.reader_output`: exit 0, unchanged.
  CI's lint steps run locally: ruff, format, skill caps, skill surface, audit delta (no
  row changed), code references, rulebook limits, release notes, Vale (0 errors).

  *Review* (`/code-review high --fix`, seven findings, four fixed in `f5cee3a99`):
  `Project.create`/`open` now check backend and solver before writing the directory (a
  bad backend had left a half-made project that refused a retry); the joint `fit` and
  `refine_multi` call `check_mode`; the module hint never names a private module;
  `engines="dicvol"` is refused as a string, not letter by letter. Declined: the GUI
  console's `session.pick_peaks(two_theta_range=...)` echo is the GUI session's own verb
  and wire key, kept with them; no shim for the old keyword (the WP's ruling, the release
  note names it); `viz`'s choice arguments are off the derived surface (adding their names
  to `CHOICE_NAMES` found nothing) and already refuse by name.

  *Gotchas.* Rebuilding tutorials 01, 04 and 06 on this machine changed text outputs that
  the rename did not touch (04: a `FLOOR_HIT` row gone, a stage at 18 evaluations, not 3),
  so the outputs on `main` have drifted from the code. Only the source cells were edited
  here; `build.py --check` compares cells, not outputs, so nothing flags the drift.
  Not deliberately generalised: `viz`'s `style`, `y_scale`, `x_axis` and
  `render_structure`'s `disorder` take choices but sit outside the derived surface; each
  already refuses with "must be one of".

- **2026-11-23** — created from the API review (2302-batch/plans.md). No open WP owns
  refusing a choice at entry: WP-2005 tiers refine.py's codes and literals, and WP-2103 gives
  the joint fit the single fit's verbs. Next: the `mode` helper, then the survey.

- **2026-11-23** — the `path` question settled by Claude at the maintainer's instruction:
  keep `path` for both meanings, with each argument's type and docstring saying which
  (§ Context). A task is added for it.

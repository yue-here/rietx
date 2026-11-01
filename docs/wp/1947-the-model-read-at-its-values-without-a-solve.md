# WP-1947 — the model read at its values, without a solve

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-10-11 — an application reads statistics, ticks and the background before a fit through an undocumented empty stage or by mutating its own refinement; each has a workaround

## Goal

A caller can evaluate a refinement at its current values, read its
reflection list and read its background, all before any fit and without
changing the refinement's state. Each is a documented call with a test
that says what it returns.

## Context

**The reports (issues #890, #891, #894).** One application developer
embeds rietx in a desktop app and needs three things before a fit:
- #890: the statistics (and for Pawley the extracted intensities) at the
  starting values. They pass `RefinementPlan(stages=[Stage("evaluate", [])])`
  and ask whether that is meant to stay, or for `evaluate(pattern)` or
  `max_iter=0`.
- #891: a reflection list (hkl, d, 2θ, multiplicity, line) to draw ticks.
  `reflection_table()` refuses before a fit, so they run their own gemmi
  extinction code, which could disagree with rietx's.
- #894: the background alone. They set `phases.0.scale` to 0, call
  `predict`, and restore it in a `finally`.

All three read the compiled model at fixed values:
`compile_model` → `ParameterTable.decode(x0())` →
`CompiledModel.{evaluate, background, phase_peaks}`
(`model/forward.py:1955`, `:815`, `:1518`). Today the only public way to fill
`Refinement._model` and `result_` without a solve is the empty stage.

**What the tree does, checked at `d80ca5f4`** (scripts in the 2026-10-11
triage's scratchpad; numbers from a synthetic LaB6 pattern):
- **The empty stage works and nothing documents it.** `fit(plan=
  RefinementPlan(stages=[Stage("evaluate", [])]))` returns `status=
  "converged"`, `n_free_parameters=0`, stage `n_iterations=0`, values
  unchanged, and no esds. It writes two history nodes, and a run directory
  unless `telemetry=False`. The package itself uses it: `io/recipe.py:1363`
  builds `Stage("recipe", [])` and says so with `RECIPE_NOTHING_REFINED`.
  `tests/test_qpa_multimodal.py:141` runs it and the skill's `judging.md`
  uses it. No manual page documents it, and no test asserts what the result
  holds.
- **Under Pawley or Le Bail the empty stage is not "nothing fitted".** Pawley
  ran 10 iterations on the intensity block and Le Bail runs its update
  cycles. That is the extraction #890 asks for at the start values, so
  `max_iter=0` cannot serve those modes.
- **`max_iter=0` is refused by scipy, not by rietx.** A stage that frees
  anything with `max_iter=0` raises `` `max_nfev` must be None or positive
  integer. `` (`optimize/least_squares.py:1716`, `max_nfev = max_iter *
  NFEV_PER_ITERATION`). The message does not name `max_iter`.
  `schemas/plan.py` and `strategy/staged.py` put no lower bound on it. An
  empty stage with `max_iter=0` is accepted, through the `len(x0) == 0` early
  return. Under `solver="lm"` it is accepted as one evaluation with status
  `max_iter`. WP-1938 makes LM the default, so the refusal would turn into
  a quiet `max_iter` result. Its Inherited has a note.
- **A zero-stage plan is refused**, and its message sends the caller to
  `ref.predict(pattern)`.
- **`predict` returns only an ndarray** (`refine.py:4954`). It has no
  `components=`, and it refuses Le Bail and Pawley before a fit
  (`refine.py:5002`), since their intensities come from a fit.
- **Reflections.** `Refinement.reflection_table()` raises `call fit()
  first` (`refine.py:5327`), as do `report`, `summary` and `write_cif`. The
  exported `rx.reflection_table(model, values, structure)` gives the same
  rows from a `CompiledModel`, which only `compile_model` builds, and neither
  is exported. With one, the rows (hkl, line, 2θ) match an empty-stage fit's
  `reflection_table()` exactly. `crystallography/symmetry.py:1320
  generate_reflections` uses the same gemmi absence test and is not
  exported. For drawing, `PatternData.plot(model=ref)` already draws ticks
  with no fit, from `viz/snapshot.py stage_ticks`, which applies
  `zero_shift` and not the displacement. That defect is WP-1908's, so a new
  rows function builds on `phase_peaks`, as `reflection_table` does.
- **Background.** `Refinement(Structure(phases=[]), instrument).predict(data)`
  equals the scale-zero workaround to 0.0 and touches nothing. The manual
  mentions it in passing (`using/files.md`, § the NO_PHASES block). After a
  fit, `result.y_background` matches too. On a fitted refinement the
  workaround's `set_values` writes two `set_value` nodes and clears
  `result_` (`refine.py:2452-2459`).

**Two neighbours decide part of what this returns.** WP-1512 (⬜) decides
what belongs in `y_background`, so a background accessor over
`CompiledModel.background` inherits that. WP-1421 (⬜) owns which compile
an evaluation reports, which matters if an evaluate verb and `predict`
differ.

**The rule this meets.** The python API is the one integration surface
(root CLAUDE.md, WP-1303). These are methods on it, so no second surface
is in question. A verb that reports must not write: no history node and no
run directory unless asked, because an evaluation is not a fit.

### Inherited

- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: two `lebail_cycles` slips.** A node's `api_call` drops `lebail_cycles` (`schemas/history.py:126-135`), so a stage run with a non-default value renders a call that runs a different stage; this WP's replay already reads `lebail_cycles or 3`. And `rietx.help`'s `lebail_cycles` text, shown on `docs/docs/reference/settings.md`, says Pawley mode ignores it, where `refine.py:3916-3920` uses it to seed the Pawley intensities.

- **2026-10-11, from WP-1938 (PR #883): LM refuses `max_iter=0` now, in
  scipy's words.** `lm.minimize` raises "`max_nfev` must be None or positive
  integer." for a budget under one evaluation, on the single and the joint
  fit (`tests/test_lm_solver.py`, both drivers). So the refusal this WP
  rewords is the same on either driver. Two findings from that change's
  review are this WP's. `Refinement.cherry_pick` rebuilds a stage with
  `max_iter=node.action.max_iter or 100` (`refine.py`, the `Stage(...)` call),
  so a node recorded with `max_iter=0` replays as 100 iterations, silently;
  `lebail_cycles or 3` has the same shape. And `Stage.max_iter` has no
  `ge=1`, so a plan with 0 is stored and fails only mid-fit, after compile.

## Non-goals

- A public objective and gradient for an outside optimiser (issue #899):
  WP-1948, which builds on this one.
- Tick positions with the displacement shift (WP-1908).
- What `y_background` contains (WP-1512).

## Tasks

- [ ] Decide the spelling, and record it here as `Decided YYYY-MM-DD:`. One
      option is a named verb, `Refinement.evaluate(data, mode=...)`,
      returning a `RefinementResult` with no esds, no history node and no
      run directory, and keeping the Le Bail and Pawley extraction. The
      other documents the empty stage as the spelling, with a test pinning
      what its result holds. Read the four call sites above before choosing.
- [ ] `max_iter=0`: a refusal rietx owns, naming `max_iter` and the
      evaluation spelling, on both drivers (`ge=1` on the field, or a check
      in the runner). Coordinate with WP-1938 if its LM default has landed.
- [ ] Reflections before a fit: `Refinement.reflection_table(data)` (or the
      verb's result) built on `phase_peaks`, the same rows as after a fit.
      Test: the rows before a fit equal the rows of an empty-stage fit.
- [ ] Background without mutation: an accessor over
      `CompiledModel.background` (`predict(data, component="background")`
      or `Refinement.background(data)`). Test: it equals the scale-zero
      `predict`, and the history and values are unchanged.
- [ ] Manual (`using/refining.md` or `using/exports.md`) and the generated
      skill API index: the three calls, with the phase-free `predict` named
      as the workaround it replaces.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for the evaluated
      pattern.
- [ ] Skill: WP-1532's `api.md` row (a reflection table without a fit)
      changes to the new call. Nothing else expected.

## Acceptance

Before any fit, on a synthetic pattern, the evaluation's statistics, the
reflection rows and the background are each one call. None writes a history
node or a run directory, and a test asserts each equals what an empty-stage
fit reports.

```sh
.venv/bin/python -m pytest tests/test_refine_synthetic.py tests/test_manual_api.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #890, #891, #894.

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issues #890,
  #891, #894). Checked against the tree at `d80ca5f4`: `max_iter=0` raises
  scipy's `max_nfev` message, the empty stage evaluates without moving
  anything, `reflection_table()` refuses before a fit, and a phase-free
  `Refinement` predicts the background alone. No open WP owns it: WP-1444
  (the pattern drawn before a model) is closed, WP-1532 only carries a skill
  row, WP-1512 and WP-1908 own what the background and the ticks contain,
  and nothing names an evaluate verb. *Next:* task 1.

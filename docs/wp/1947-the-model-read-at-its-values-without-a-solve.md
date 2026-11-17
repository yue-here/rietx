# WP-1947 — the model read at its values, without a solve

Milestone: unscheduled · Status: 🔄 2026-11-17 — claimed by @mustachefeeling
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

**Superseded in part, 2026-11-17 (checked at `6f704aaa5`).** The four call
sites above moved; what changed: `predict` is now `predict(two_theta=None)`, a
grid or a `PatternData` (`refine.py:6749`), and still refuses Le Bail and
Pawley before a fit (`:6823`). `reflection_table()` is at `:7233` and reads the
answer frozen with the result (WP-1421, ✅). The empty stage now runs the
plan's appended closing stage too: on the synthetic LaB6 it returns
`converged`, stages `evaluate` and `closing` at 0 iterations, nothing moved,
no esds, and three history nodes. Under Pawley each of the two stages ran 2
iterations on the intensity block (19 intensities), not 10. LM is the default
driver (WP-1938 landed): a freeing stage with `max_iter=0` raises scipy's
`max_nfev` wording on both drivers, and an empty one with `max_iter=0` is
still accepted. `cherry_pick` now passes `max_iter` and `lebail_cycles`
through unchanged, an explicit 0 included (`refine.py:4895`). The
displacement tick defect is fixed (WP-1908, ✅).

### Inherited

*(Pruned 2026-11-17 on arrival; what each entry became is in the handover
entry of that date.)*

## Non-goals

- A public objective and gradient for an outside optimiser (issue #899):
  WP-1948, which builds on this one.
- Tick positions with the displacement shift (WP-1908).
- What `y_background` contains (WP-1512).

## Tasks

- [x] Decide the spelling, and record it here as `Decided YYYY-MM-DD:`. One
      option is a named verb, `Refinement.evaluate(data, mode=...)`,
      returning a `RefinementResult` with no esds, no history node and no
      run directory, and keeping the Le Bail and Pawley extraction. The
      other documents the empty stage as the spelling, with a test pinning
      what its result holds. Read the four call sites above before choosing.
      **Decided 2026-11-17: the named verb.** The empty stage writes three
      history nodes and a run directory unless told not to, which the rule
      above refuses for a verb that reports, and the acceptance asks for none.
      `Refinement.evaluate(data, *, mode="rietveld", two_theta_limits=None)`
      runs exactly the empty stage, on the private history-free working tree
      `Refinement._trial(record=False)` already builds for the package's own
      discarded fits, with `telemetry=False`. So it returns the object the
      empty-stage fit returns, by construction rather than by a second
      implementation, keeps the Le Bail and Pawley extraction, and leaves the
      caller's values, history, `result_` and compiled model untouched.
      `reflection_table(data)` takes the same route, so its rows are the
      empty-stage fit's in every mode. `background(two_theta)` is
      `predict`'s twin over `CompiledModel.background`: one compile, no fit,
      no extraction, so it serves Le Bail and Pawley before a fit too.
- [x] `max_iter=0`: a refusal rietx owns, naming `max_iter` and the
      evaluation spelling, on both drivers (`ge=1` on the field, or a check
      in the runner). Coordinate with WP-1938 if its LM default has landed.
      (It has. `Stage.max_iter` still has no lower bound, so a plan holding
      0 is built and fails only mid-fit, after compile.) **Landed
      2026-11-17:** `Stage.__post_init__` refuses `max_iter < 1` where the
      stage is built, naming `max_iter` and `ref.evaluate(data)`, so a stored
      `StageSpec` holding 0 is refused when `fit` or `refine_multi` converts
      it, before any compile or history write, on either driver. The empty
      stage with 0 is refused too, since it has the verb now. `rietx.help`'s
      `max_iter` entry says so. `StageSpec` keeps no bound, so a stored plan
      still loads (a schema change was not needed for the refusal).
- [x] Reflections before a fit: `Refinement.reflection_table(data)` (or the
      verb's result) built on `phase_peaks`, the same rows as after a fit.
      Test: the rows before a fit equal the rows of an empty-stage fit.
      **Landed 2026-11-17:** `reflection_table(data, *, mode=None,
      two_theta_limits=None)`; with no pattern it is the last fit's rows as
      before, and the refusal now names the pattern form. Rows equal the
      empty-stage fit's in all three modes
      (`test_reflections_before_a_fit_are_the_empty_stage_rows`).
- [x] Background without mutation: an accessor over
      `CompiledModel.background` (`predict(data, component="background")`
      or `Refinement.background(data)`). Test: it equals the scale-zero
      `predict`, and the history and values are unchanged.
      **Landed 2026-11-17:** `Refinement.background(two_theta=None)`, with
      `predict`'s two forms; bit-equal to the scale-zero `predict`, the
      phase-free twin's `predict` and, after a fit in each mode,
      `result.y_background` (`test_background_without_mutation`). The
      no-phase refusal now names it.
- [x] Manual (`using/refining.md` or `using/exports.md`) and the generated
      skill API index: the three calls, with the phase-free `predict` named
      as the workaround it replaces. **Landed 2026-11-17:** the manual tree
      moved (WP-1986), so `docs/docs/reference/exports.md` § Evaluating the
      model gains "The result at the current values" and "The background
      alone", and § The reflection list the pattern form;
      `reference/history.md` says the stage line now carries the two
      partition settings. `make_api_index.py` lists the three methods.
- [x] Tests + obs/calc/diff PNGs to `tests/output/` for the evaluated
      pattern. **Landed 2026-11-17:** five tests (nine cases) in
      `tests/test_refine_synthetic.py` § the model read at its values;
      `tests/output/evaluate_before_any_fit.png` (looked at: the perturbed
      start, peaks offset in the difference curve, as expected).
- [x] Skill: the `api.md` row "a reflection table without a fit", written
      new for the documented call (WP-1532 dropped it, issue #1381; nothing
      under `docs/skill/rietx/` teaches the `run_stage` spelling). Nothing
      else expected. **Landed 2026-11-17:** generated rows for
      `Refinement.evaluate`, `.reflection_table` (its first docstring line
      now says "after a fit or from a pattern") and `.background`, and one
      sentence in the Refinement section's prose; `api.md` 35 780 → 36 558 B
      of the 39 000 B ceiling; both committed copies re-synced.
- [x] `NodeAction.api_call` renders `lebail_cycles` and `lebail_tol` when
      they differ from the `Stage` default (from WP-1986): today a stage run
      with a non-default value renders a call that runs a different stage
      (`schemas/history.py`, the `extras` tuple). **Landed 2026-11-17:**
      compared with `StageSpec`'s field defaults, never `NodeAction`'s 3 and
      0.0 (an old node's, which now render, since they are what it ran).
      `report.apply.api_call` passes the stage's two values, so an Apply
      tooltip and the node's line still agree
      (`test_a_stage_call_carries_its_partition_settings`).

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

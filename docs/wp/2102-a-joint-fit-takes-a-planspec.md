# WP-2102 — a joint fit takes a PlanSpec

Milestone: parametric · Status: ✅ 2026-11-05 — every plan form reaches a joint fit and each report through `resolve_plan` (PR #1413)
Depends on: —

## Goal

`refine_multi` accepts every form of plan that `Refinement.fit` accepts, and each
`report` reads a plan the way the fit that made the result did.

## Context

`refine_multi(plan=PlanSpec(...))` raises `AttributeError: 'PlanSpec' object has no
attribute 'run_stages'`. Found on 2026-11-03 while probing the joint surface as an
expert would. The workaround is a `RefinementPlan` built from `Stage`s.

Root CLAUDE.md § Plans states the rule: a mirror is crossed at the two authorities that
own it, never at a call site, and `resolve_plan` (`strategy/staged.py:801`) converts the
spec outbound. `Refinement.fit` (`refine.py:5374`) and the series path
(`sequential.py:1470`) call it. Three call sites instead test `isinstance(plan, str)`
and look the preset up by hand:

- `multi.py:1431`, `MultiHistogramRefinement.fit`.
- `multi.py:1550`, `MultiHistogramRefinement.report`.
- `refine.py:6493`, `Refinement.report`.

Both signatures in `multi.py` are annotated `RefinementPlan | str`.

The two sites differ. `fit` crashes. Both `report` methods accepted a `PlanSpec` in a
review's probe of 2026-11-04, because `apply_strategy_veto` reads only what the two
types share. What they skip is `resolve_plan`'s mode substitution, and neither has a
`mode` argument, so a report passes `result_.mode`. `project._as_plan_spec`
(`project.py:477`) converts the other way, toward a spec, and is a fourth place to read.

## Non-goals

- Any other change to what a joint fit accepts: [2103](2103-a-joint-fit-has-the-verbs-a-single-fit-has.md).

## Tasks

- [x] Route `fit` through `resolve_plan`, passing `mode`, and widen the annotations.
- [x] Route both `report` sites through it with `result_.mode`. Check whether a report
  on a Le Bail or Pawley result changes, since the substitution then applies. If it
  does, that is a reader-output change and goes to the maintainer.
- [x] Test: a `PlanSpec` and the `RefinementPlan` it converts from give bit-identical
  answers on `refine_multi`.
- [x] Grep for a fourth site and say in the handover what was checked.
- [x] Skill: "none" and why, unless the skill names the limit.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1110 (the mirror rule).

## Handover log

- **2026-11-05** — A joint fit now takes a `PlanSpec`, the plan form a project file,
  a history header and an agent each hold, and answers exactly as it does for the
  plan the spec was built from. The crash came from a preset name looked up by hand
  at the call site. The same lookup sat in five more places, and each skipped the
  rule that `"mccusker_default"` in a Le Bail or Pawley fit runs as that mode's own
  plan. All six now go through `resolve_plan`. One reading changes for a reader: a
  Le Bail report given `plan="mccusker_default"` now equals its report under
  `profile_only`, so a scale suggestion is no longer marked "already refined". That
  change waits on the maintainer (below). PR #1413.

  *Done.* `MultiHistogramRefinement.fit` and `.report`, `Refinement.report` and the
  public `build_report` cross the mirror at `resolve_plan` with the result's mode.
  `Project.create`'s `_as_plan_spec` and the text document's plan delta store a
  preset expanded through the project's mode, as the GUI's preset route
  (`gui/session.py`, `set_plan`) and `PlanSpec.preset_name`'s docstring already
  required: a project's plan runs verbatim. Public signatures that reach
  `resolve_plan` (`Refinement.fit`/`report`/`summary`, `refine`, `refine_multi`,
  `SequentialRefinement.fit`) name `PlanSpec`. The skill's generated `api.md` is
  regenerated; the skill names no PlanSpec limit, so no row changed. The manual's
  `reference/joint.md` and `reference/report.md` name the spec form.

  *The fourth-site grep* (`PLAN_PRESETS[`, `isinstance(plan, str)`, `plan:`
  annotations, `getattr(plan, "stages"`) over `src/`. Fixed: the five above.
  Already right: `Refinement.fit`, `sequential.py`, `gui/session.py`,
  `indexing/extinction.py`. Left alone: `textdoc.py`'s membership check on a typed
  name (validation only), `report/apply.api_call` (reads two fields off a plan
  already resolved), and `apply_strategy_veto`'s `getattr` (every caller now hands
  it a `RefinementPlan`). The Context's line numbers had moved by ~200-240 lines;
  the sites were the ones named.

  *Not generalised.* A **mode-only edit** leaves the stored plan expanded for the
  old mode, in both the text document and the GUI's settings route
  (`gui/session.py`, `p.doc.mode = body["mode"]`): a project switched from Rietveld
  to Le Bail keeps `mccusker_default`'s scale stage, and the reverse keeps
  `profile_only`, which never refines the structure. Re-expanding is a design
  call, because `profile_only` is also a legitimate Rietveld plan and the stored
  spec carries no preset name. Found by `/code-review`; no WP owns it.

  *Measured.* On a synthetic LaB6 Le Bail fit (Rwp 0.042), `report()` and
  `report(plan="profile_only")` offer `refine_scale` and `refine_biso`, both on
  paths the mode force-fixes; `report(plan="mccusker_default")` vetoed the scale
  one by accident before this change. The Pawley report did not change. Filed
  into WP-1998's `### Inherited`. New tests, each shown red on `origin/main`'s
  source except the unknown-preset guard: 5 in `test_multi_histogram.py`, 3 in
  `test_project.py`, 2 in `test_textdoc.py`, 2 in `test_fitreport_layers.py`.
  Fast suite on the tree merged with origin/main at `8217a78ed`, `[dev]` venv,
  darwin/arm64 (macOS 26.7.2), run through ghostshift's `serial.py` queue: 13 847
  passed, 319 skipped, 36 xfailed, none failed, 12:50 wall clock. The 12 added cases
  cost 10.0 s locally, 8.1 s of it in `test_multi_histogram.py` (the shared joint
  fixture is 2.2 s); none joins the slow tail.

  *Review.* `/code-review high --fix` fixed the two manual tables and a missing
  plot, and found `build_report`'s shape read, fixed here as its own commit. It
  also named the mode-only edit above and the reader-output change below.

  *For the maintainer.* `python -m tests.reader_output` exits 0: its standard fit
  is Rietveld, which no change here reaches. What does change for a reader: a Le
  Bail report built with a preset name, through `Refinement.report`, the GUI's
  report route or `build_report`, now vetoes against the plan the fit ran, so a
  scale suggestion the hand-read name had marked "already refined by the staged
  plan" is active. A Le Bail project created with `plan="mccusker_default"` records
  a first stage named `bkg` rather than `scale_bkg`. Approve or reject before merge.

  *Generality.* No row of the audit table changed and no heuristic was added; the
  judge was not dispatched.

  Next: the maintainer's call on the reader change above; then WP-2103, whose soft
  dependency this discharges (its `### Inherited`).

- **2026-11-04** — Filed from the expert-surface probe of 2026-11-03. No open WP owned
  it. It stands alone because it can land in one sitting ahead of everything else in
  the milestone. Next: the first task.

# WP-1208 — Plan panel: the gentle introduction

Milestone: v1.2 · Status: ✅ 2026-08-27 — the ladder, and what a plan will free
Depends on: WP-1203

## Goal

A crystallographer who has only ever refined one step at a time understands,
from the panel alone, that a plan is an ordered list of stages, that each
stage frees a named set of parameters on top of the last, and what the next
click will do.

## Context

The user: "the kind of plan we're implementing here is a new concept to most
crystallographers. Most refinement software just refines a single step at a
time."

Findings (2026-08-25, `gui/src/panels/Plan.svelte`, 358 lines):

- The panel offers a preset `<select>` (`:144-156`), a draggable stage list
  with a name input, a `Run` button and `×` per stage (`:173-218`), one
  comma-separated glob input per stage (`:195-200`, placeholder `dot-path
  globs freed here — phases.*.cell.*`), Advanced fields (`:201-215`) and
  Save/Revert (`:157-160`).
- The only visible prose is `when_to_use` (`:163-169`); `description` is a
  hover `title`; nothing says what a plan is. The panel's own source comment
  (`:2-16`) explains it to a code reader.
- Globs are never resolved against the live table: a stage shows its glob
  string, not which parameters it will free, how many are held and why.
- `PLAN_INFO` (`strategy/staged.py:446-467`) carries `title, description,
  modes, when_to_use` and reaches the panel through `capabilities()` →
  `GET /api/plans` (`session.py:639-646`).
- **Cumulative staging**: an intermediate stage's parameters keep refining
  in every later stage, and only the last stage converges
  (`RefinementPlan.intermediate_ftol`, WP-1123). That is the thing to draw.
- Per-stage results exist: `fit(stage_reports=True)` → `stage_reports_` and
  the `trajectory` companion (WP-1058), default off since WP-1003.
- `Params.svelte`'s bulk verbs send the glob and the client matcher is a
  preview held to Python by the committed fnmatch corpus (WP-1011).

Design: a `GET /api/plan/resolve` route returning, per stage, the paths its
globs match on the live table, which of those are new this stage, the
cumulative free count, and the held matches with `held_because`; the panel
renders the plan as a ladder ("stage 3 · +4 · 11 free"), each stage
expandable to its list. After a run, the ladder carries each stage's Rwp
from the stage reports (the GUI passes `stage_reports=True`; the answer is
bit-identical). An explainer line plus the preset's `description` visible,
under `/yue-docs-style`; `StageSpec` field help from the corpus.

## Non-goals

- Plan authoring beyond what exists (globs, order, per-stage fields).
- Suggesting a plan (`Refinement.suggest()` is a parameter, WP-1050).

## Tasks

- [x] `GET /api/plan/resolve` in `GuiSession` (a `ParameterTable` build per
      call; matched with `fnmatch` the way `set_vary` matches); tested
      against the fnmatch corpus vocabulary.
- [x] The ladder rendering, the per-stage disclosure, cumulative counts, held
      matches with their reason; the explainer and `description` visible;
      corpus help on every stage field; "Run this stage" / "Run all" named.
- [x] Stage Rwp on the ladder after a run — off the **history nodes**, not a
      `stage_reports=True` run verb: the two numbers are bit-identical (pinned
      by `test_the_node_rwp_is_the_trajectory_rung_rwp`) and the trajectory
      costs 7.7× the fit to rebuild, so the run verb is untouched.
- [x] Browser pass on the NAC example: read the ladder cold; dist rebuilt.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "plan"
npm --prefix gui test && npm --prefix gui run check
```

## References

- McCusker et al. (1999) §3, the turn-on order the presets encode.
- WP-1123 (cumulative staging), WP-1058 (stage reports).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**The plan as a ladder** (WP-1208, `GET /api/plan/resolve`,
`panels/Plan.svelte`) is the stage list saying what it will *do*: per stage the
paths its globs reach, the ones it frees on top of the last, the held ones
carrying the row's own `held_because`, and the running free count. Four rules.
**The resolution is the real verb** — `ParameterTable.set_vary` on the table
`fit` builds, so the tied/locked skip, the free-cell wavelength rule and the
intensity mode's force-fix are the shipped ones; `lib/fnmatch.ts` stays the
*parameter table's* bulk-edit preview and matches nothing here. **A plan
replaces the vary flags, it does not continue them**: `fit` starts from
`_prepare_table(restore=False)`, which holds everything, so a hand-freed row no
stage names is dropped by a staged Refine and kept by `Run this stage` (measured
both ways) — `set_aside` is that difference named. **A stage's Rwp is its history node's**, never a
`fit(stage_reports=True)` trajectory: bit-identical, both read off the model the
stage compiled and the θ it landed on, and the trajectory costs 7.7× the fit to
rebuild, so the run verb is untouched — the **last** run's node is matched to a
rung by position **and** by that stage's name and `turn_on`, anything else
leaving the number absent rather than a neighbour's or an older run's. An **edited plan keeps the facts of the
stages above its first change only** (WP-2127, `lib/plan.ts:resolvedPrefix`),
and is **one pending edit in the shell's action bar**, never a Save of its own. Beside them, the advanced boxes loop over `lib/rxt.ts`'s stage
words — pinned to `StageSpec` from python with the two properties a box needs —
so a new schema field reaches this form as well as the `.rxt` document.

## Handover log

### 2026-08-27 — closed: the plan now says what it will do

A crystallographer opening the Plan panel reads a plan the way it behaves.
Three sentences at the top say what a staged plan is. Each stage is a rung
carrying what it frees on top of the last (`+4 → 11 free`), the paths its
globs reach and cannot free with the row's own reason, and the Rwp that stage
reached the last time it ran. The two verbs are named beside each other, and
the difference between them is stated where it costs something: `Run all`
starts every plan from a table where nothing is free, so a parameter someone
freed by hand and no stage names is set aside, while `Run this stage` keeps
it. That asymmetry was in the code and in nothing anyone could read; the
comment in `Refinement.fit` said the opposite of what the line under it does,
and this WP measured it and rewrote it.

*Done.* `GET /api/plan/resolve` (`GuiSession.plan_resolve` + `_stage_rwp`):
per stage `turn_on`, the three buckets `frees`/`already`/`held` that partition
its matched paths, `n_matched`, the cumulative `n_free`, and `rwp`; beside
them `mode`, `n_parameters`, `n_free_final`, `set_aside`, `head`, `live`. The
simulation is `ParameterTable.set_vary` itself, run on `_prepare_table(
restore=False)` — the table `fit` builds — plus `_run_stage`'s own
`mode_fixed_path` drop, so no rule is restated here. `Plan.svelte` is rebuilt
around the ladder: the explainer, the preset's `description` visible with
`when_to_use` moved into the popover, a per-stage disclosure listing the
paths, `held_because` on each held row through `<Help text=…>`, and `Run all`
/ `Run this stage`. The advanced boxes are a loop over `lib/rxt.ts`'s stage
words rather than four typed-out fields, which brings `ftol`,
`restraint_weight_scale` and `window_slack_deg` into the form (reachable only
through the `.rxt` document before) — `STAGE_INT_WORDS` and
`STAGE_NULLABLE_WORDS` join `STAGE_WORDS` there, all three pinned to
`StageSpec` from `tests/test_textdoc.py`. `gui/CLAUDE.md` takes four rules,
cap 710 → 733.

*Measured* (`[dev]` only — no jax, no torch — python 3.12.12, numba 0.67.0,
darwin/arm64):

- **`stage_reports=True` costs 7.7× the fit and buys nothing the history has.**
  4200-channel synthetic LaB6, five-stage `mccusker_default`, best of three:
  history off + reports off **0.075 s**, history off + reports on **0.577 s**,
  history on + reports off **0.076 s**, history on + reports on **0.582 s**.
  A tree costs ~0.001 s because the statistics are computed for the node
  either way. And every stage node's cached Rwp is **bit-identical** to the
  WP-1058 rung's, all five stages — both are `_build_result` over the model
  the stage compiled and the θ it landed on. So the ladder reads the node and
  the GUI's run verb is untouched (task 3 as written is not what shipped).
- **A fit replaces the vary flags; a single stage continues them.**
  `set_vary("phases.*.atoms.*.biso")` then `fit(plan="profile_only")` refines
  no biso, while `run_stage` on the same state refines both. This is what
  `set_aside` reports.
- **Browser** (playwright-core, cached chromium-1223, four passes on the
  11-BM NAC example). Cold, the ladder reads `+8 → 8`, `+1 → 9`, `+2 → 11
  free · 10 held` (two cubic cells, one edge free each), `+1 → 12`, `+4 → 16`,
  `+8 → 24 of 95`. Fitted, the same column carries **79.62 → 60.57 → 11.56 →
  11.43 → 9.71 → 9.32 %**, which is the staged descent in one glance.
  One defect jsdom cannot see: **freeing a parameter blanked every Rwp**,
  because a `set_vary` node sits between the head and the fit's stages and the
  walk stopped at the first non-stage node. `_RWP_TRANSPARENT` names the three
  parameter-surface kinds that may sit there; `edit_model` stays opaque and
  ends the run, since a number measured on a replaced model describes nothing
  on screen. Both directions are tested.
  Two register repairs came from looking at it: `Run all` is a ghost (the app
  header's Run is the same verb, and two filled buttons read as two actions)
  with `Save plan` taking the fill while there is something to save; and the
  stage number moved off the name row onto the ladder line, which also lets
  `name` and `frees` share a label column.
- **The route costs 2.5-8.2 ms and 1.9-3.3 kB** on the two shipped examples
  (NAC, 8 atoms / 95 parameters / 6 stages; FAP, 7 / 82 / 6), best of 20 —
  cheap enough for the per-head-move fetch it is. Scaling on synthetic P1
  models under `mccusker_structural` (10 stages, best of 10): 190 / 510 / 990
  parameters at **5.0 / 13.4 / 25.7 ms** in Rietveld mode, and **6.8 / 26.5 /
  75.8 ms** at 4.2 / 27 / 53 kB in Le Bail, where every `.atoms.` row is a
  mode-fixed held match repeated per stage. The Le Bail arm is superlinear and
  left alone: `mccusker_structural` declares `modes = ("rietveld",)`, so that
  case is a plan the mode does not admit, and "360 matched, all held by the
  intensity mode" is the answer the panel exists to give. The one thing worth
  doing was done — the mode-fixed drop is **one** `set_vary` call rather than
  `_run_stage`'s per-path loop, since a path is a glob that matches itself and
  N calls are N table rebuilds.
- **Counts.** Fast suite `-m "not slow"`: **3090 passed / 117 skipped**;
  without this WP's ten tests, **3080 / 117** — +10, exactly the ten added.
  The post-close review round put it at **3091 / 117** (+1) and vitest at
  **461** (+1). vitest 458 → 460 → **461** across the WP, 21 files. `npm --prefix gui run check` clean, `ruff` clean, dist rebuilt.
  Merged `origin/main` at `d6f36c69` (the strain/size soft cap, PR #144, which
  adds 373 lines to `params/vector.py`) before quoting any of these; it touches
  `ParameterTable.bounds` and not the free set, so the resolve is unaffected.

*Gotchas for whoever touches this next.* `_working_table()` is `run_stage`'s
starting table and **not** `fit`'s — the first cut of the route used it and
every rung came back with the same cumulative count, because after a fit the
restored free set already contains everything the plan frees. The three
buckets are decided held-first on purpose: a mode-fixed row a user freed is
both held and already free, and what the stage does with it is drop it. And
the dynamic held-reason is reached by setting `needs_held_cell` on a copy of
the row rather than by spelling its sentence again, which works because
`ParameterRow.refinable` promises the four reasons are all there are — a fifth
dynamic rule inside `set_vary` would be mislabelled, and would need this
line changed with it.

*Post-close, `/code-review medium --fix`.* Two defects, both in this WP's own
code and both reproduced before accepting the fix. **The ladder read the
*first* run, not the last**: a fit commits only `stage` nodes, so two
back-to-back runs of one plan leave 2N contiguous stage nodes with nothing
between them to mark the seam, and the walk collected the whole block. The
docstring had promised "the last run" all along. Measured on the synthetic
fixture: after two `mccusker_default` fits the route returned run 1's
`[0.953, 0.729, 0.446, 0.041, 0.041]` under run 2's ladder, whose nodes read
`[0.041]×5`. The walk now stops at `len(plan.stages)` nodes; a complete run
plus a partial one aligns with neither and goes absent. Every other test here
runs the plan once, which is why nothing caught it —
`test_running_the_same_plan_twice_shows_the_second_run` is the pin.
**Both run buttons ignored `noPhases`**, so in the pattern-only project this
WP's own test puts the panel on screen for, a click posted `/api/run` and
surfaced a `NO_PHASES` refusal in the console instead of a disabled control
with a reason. The repair spelled the sentence a second time ("add one in the
Model tab") against the shell's own ("index a pattern, adopt a cell") — two
instructions for one state — so the panel now takes `noPhasesReason` and the
shell stays the one authority; a vitest holds all three buttons to the same
string. The `already` bucket's docstring was corrected in passing: under
`restore=False` it can only mean an earlier stage of this plan, never the
caller.

*Next:* WP-1209 (the peaks table's numbers and flags).

- **2026-08-25** — created from the v1.2 triage.

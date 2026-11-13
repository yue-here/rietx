# WP-2208 — a plan stage that fixes as well as frees

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — built and ruled; PR #1520 approved for merge (a stored-format change)
Depends on: 2127 (the Plan tab)
Priority: P2 2026-11-10 — a feature the open gui-overhaul milestone was opened for, ruled required 2026-11-09

## Goal

A stage of a plan can fix parameters as well as free them. `StageSpec.turn_off` lists dot-path
globs the stage fixes after it frees its `turn_on`, `.rxt` writes them as a `fix` clause, and the
Plan tab lets a person mark a parameter fixed in a stage. The maintainer's case runs end to end:
a Pawley fit settles the profile, and a Rietveld plan then refines the structure with the
profile fixed, its closing stage included.

## Context

### The ruling

The maintainer ruled on 2026-11-07 that a stage may fix as well as free, and on 2026-11-09 that
the functionality is required, verbatim: "specifically, I'm thinking of a common case where the
profile will be fixed with a pawley refinement, then locked; after that, the structural
parameters are released. Also the case for series refinements (as will be decided soon in the
series wps). The mechanism can be left to your best judgement but the functionality is
required." WP-2127 § Ruled: a stage that fixes records it, with the brief's candidate fields.

### How a plan sets the vary flags today

A plan **replaces** the vary flags (WP-1208): `fit` starts every plan from a table where
nothing is free, and each stage calls `table.set_vary(stage.turn_on, True)`
(`Refinement._run_stage`, `src/rietx/refine.py`; `MultiHistogramRefinement.fit`,
`src/rietx/multi.py`). The flags carry from stage to stage, so a plan is cumulative. After the
declared stages, `RefinementPlan.closing_stage()` (`src/rietx/strategy/staged.py`, WP-2002)
appends one more stage that frees every glob any declared stage freed and re-solves at tight
windows. Nothing in a plan can fix a parameter once a stage has freed it, and the closing
stage frees everything again.

`StageSpec` (`src/rietx/schemas/plan.py`) is the one authority for a stage's fields. The
`Stage` dataclass mirrors it and the two cross only at `StageSpec` validation and
`resolve_plan` (root CLAUDE.md § Plans). A history node's `NodeAction` already carries a
`turn_off` list, written today by `set_vary` nodes, so a stage node needs no new field.

### Precedence (root CLAUDE.md § A hold)

Locked and `mode_fixed` outrank a hold, and a hold outranks a glob. A fix only ever sets
`vary = False`, so it never contradicts any of them: fixing a held, locked or force-fixed row
changes nothing. `set_vary(..., False)` skips tied and locked rows as it does today.

### Practice

`docs/practice.md` § A stage that fixes a parameter (surveyed 2026-11-10 for this WP). GSAS-II's
scripted refinement is the one program whose steps declare both: a step dict has `set` and
`clear`, applies every `set` before every `clear`, and keeps the flags in the project, so a flag
cleared in one step stays cleared until a later step sets it again. TOPAS, FullProf and RIETAN-FP
keep the recipe outside the program as edits between runs, and all three document Pawley or Le
Bail then Rietveld as two runs of an edited input. RIETAN-FP's `NAUTO = 1` list is the one
built-in schedule in which a later cycle leaves an earlier group fixed.

### The design

1. **`turn_off` follows GSAS-II's `clear`.** A stage frees its `turn_on`, then fixes its
   `turn_off`, so `free phases.*` with `fix phases.*.atoms.*.biso` frees everything of the
   phases but the displacements. The flags carry to the next stage, so a fix lasts until a
   later stage's `turn_on` frees the path again. Each stage line then does at its place in the
   recipe what it says, which is how a person reads the Plan tab (WP-2127, ruled 2026-11-07).
2. **The closing stage re-solves the end state of the declared stages.** It frees every glob a
   declared stage freed, as today, and fixes every path whose last matching glob, read stage by
   stage, was a `turn_off` (`staged.fixed_at_end`). That set needs the model's paths, since two
   globs that overlap cannot be compared without them, so a runner passes the table's paths to
   `run_stages(paths=…)` and the closing stage's `turn_off` holds literal paths. A plan with no
   `turn_off` builds the closing stage it built before, bit for bit.
3. **Pawley then Rietveld is two fits, and needs nothing beyond (2).** `StageSpec` has no mode;
   the mode is the fit's. A Rietveld plan starts from nothing free, so the profile a Pawley fit
   left stays where it is unless a stage frees it. A person who keeps a preset whose stage frees
   the profile adds `fix instrument.profile.*` there, and the closing stage keeps it fixed. A
   person who wants the profile fixed across every later plan uses `hold` (WP-1435), the
   padlock in the Parameters panel.
4. **A series refits stage by stage when its plan fixes.** The default `refit="single"` collapses
   the plan into one stage freeing every glob (`sequential._collapse`). One stage cannot replay a
   fix that a later stage undoes, so a plan with any `turn_off` is not collapsed: its warm refit
   is the staged plan, as under `refit="stages"`. The series WPs define series refinement
   further; this keeps the answer right meanwhile.
5. **The record.** `StageResult.fixed` lists the paths a stage's `turn_off` fixed, and the stage's
   history node writes `turn_off` beside `turn_on`, so a replay or a cherry-pick fixes what the
   run fixed. `StageResult.blocked_by_hold` leaves out a path the same stage fixes, since the
   stage did not want it free. `StageResult.unknown_paths` reads both lists, since a mistyped
   literal in a fix is the same mistake as one in a free.
6. **`.rxt` and the GUI.** A stage line takes a `fix <globs>` clause after its frees
   (`src/rietx/gui/textdoc.py`; `gui/src/lib/rxt.ts` follows by pin). `GET /api/plan/resolve`
   carries a per-stage `fixes` list beside `frees`. The Plan tab shows a stage's fixes as chips
   beside its frees, with an add field of their own.

A file carrying `turn_off` does not open in an older rietx (`extra="forbid"`), which makes this
a stored-format change. Old files open unchanged: the field defaults to an empty list.

### The tier of each rule this WP adds

None reads the data or decides for a fit. `turn_off` is the caller's declaration, and the
closing stage's fixes are its replay. Design 4 changes how a series refits a plan that fixes,
which is machinery choosing a route to the same answer, not a judgement about the data.

### Inherited

- From WP-2217 (2026-11-13): GSAS-II's scripting docs (`GSASIIscriptable.rst` § Refinement recipe) do
  not state that `set` runs before `clear`; only its source does. `staged.py`'s `turn_off` comment and
  practice.md's rietx row now ground the order on free-then-fix (a narrow fix inside a broad free acts
  only in that order), with GSAS-II's source as agreement. Design item 1's "follows GSAS-II's `clear`"
  should say the same when this WP is next handed over.

## Non-goals

- A mode per stage. Pawley then Rietveld stays two fits (design 3).
- Series semantics beyond design 4: the series WPs decide them.
- A fix that lasts for the rest of the plan whatever a later stage frees. That is `hold`'s job.

## Tasks

- [x] File the WP; the practice survey in `docs/practice.md`.
- [x] Schema and runners: `StageSpec.turn_off` and `Stage.turn_off`; `fixed_at_end` and the
  closing stage; both runners, `run_stage`, `replay`; `StageResult.fixed`; the stage node's
  `turn_off`; `blocked_by_hold` and `unknown_paths`; the series collapse; tests, including the
  maintainer's case and a fix a later stage undoes.
- [x] `.rxt` `fix` clause; `/api/plan/resolve` `fixes`; the GUI's run-stage matching.
- [x] `help.py`, the audit table, the manual; `capabilities()` needs nothing (it lists plans and
  versions, not stage fields).
- [x] The Plan tab: fix chips and their add field, `lib/plan.ts`, `lib/rxt.ts`, vitest, the dist,
  the layout browser test.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_plan_turn_off.py tests/test_textdoc.py tests/test_gui_server.py
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/*_browser.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m tests.reader_output
```

A Pawley fit followed by a Rietveld plan whose profile stage carries
`turn_off=["instrument.profile.*"]` ends with the profile at the Pawley values, the closing
stage included.

## References

- WP-2127 § Ruled: a stage that fixes; WP-1208 (a plan replaces the vary flags); WP-1435
  (hold); WP-2002 (the closing stage).
- `docs/practice.md` § A stage that fixes a parameter.

## Handover log

- **2026-11-10** — stewarded by a ghostshift runner. Yue ruled the same day on PR #1520's five
  decisions: all five stand as built (each marked in the entry below), and approved merging the
  stored-format change. Main merged in (WP-2211 and WP-2212 filed there, no conflict in code).
  Next: the lead merges #1520 once CI is green; the series WPs revisit the collapse (decision 2).
  - *2026-11-11, after #1517 and #1523 merged*: the GUI frontend job failed 1 of 737 vitests,
    "fixes in a stage …", reading `body.plan` off `undefined`. The test took the first PUT of any
    path, and #1523's recovery copy is a `PUT /api/recovery` on a 500 ms timer, so on a slow
    runner it came before Apply's. The lookup now names `/api/plan`, as its two siblings do.
    Reproduced by shortening the recovery delay to 1 ms: the old lookup fails with CI's error,
    the new one passes. The plan-ladder screenshots were retaken on the merged build.

- **2026-11-10** — built end to end by a ghostshift runner; PR #1520. A stage of a plan can now
  fix parameters as well as free them, in python (`Stage(..., turn_off=[...])`), in the `.rxt`
  document (`stage NAME free ... fix ...`) and on the Plan tab (a `Fixes` row under each stage's
  `Frees`). The maintainer's case runs: a Pawley fit settles the profile, and a Rietveld plan
  whose stage fixes `instrument.profile.*` refines everything else with the profile left at the
  Pawley values, the closing stage included. A file that uses the field does not open in an older
  rietx, so the merge waits on the maintainer; every older file opens unchanged.

  *Done.* `StageSpec.turn_off`/`Stage.turn_off`; `staged.fixed_at_end` and
  `closing_stage(paths)`/`run_stages(paths)`; both runners (`refine._run_stage`,
  `multi.MultiHistogramRefinement.fit`, with `MultiParameterTable.row_names()` so a fix matches
  a joint row by either name), `run_stage`, `replay` and `cherry_pick` through the stage node's
  `turn_off`; `StageResult.fixed`; `blocked_by_hold` leaves out what the stage fixes and
  `unknown_paths` reads both lists; `sequential` refits a plan that fixes stage by stage
  (`warm_staged`); the magnetic strategy passes the table's paths. `.rxt` `fix` clause
  (`textdoc.STAGE_FIX_WORD`, `lib/rxt.ts` follows). `GET /api/plan/resolve` carries per-stage
  `turn_off`/`fixes` and `closing.fixes`. Plan tab: a `Fixes` row drawn once the stage fixes something or
  `+ Fix` opens it, its own add field, undo, the rung's `−N` and a "fixed here" list, the closing row's "keeps N fixed";
  `lib/plan.ts:sameStage` reads an empty `turn_off` as an absent one. `help.py` entries, the
  audit rows (`StageSpec:turn_off` default, `StageResult.fixed` in `OTHER_RECORD_FIELDS`), the
  manual (`guides/plan.md` § Fix parameters in a stage, `guides/hold.md`, `gui-guide.md` § Plan,
  `gui-power.md`, `refinement.md`), the plan-ladder screenshot pair, `docs/practice.md` § A
  stage that fixes a parameter.

  *Decisions for the maintainer* (each settled by the runner on the practice named; the PR body
  repeats them). **Ruled by Yue 2026-11-10: all five stand as built.**
  1. A later stage's `turn_on` frees a path an earlier stage fixed (GSAS-II's `set`/`clear`
     carry, `docs/practice.md`). Alternative: a fix sticky for the rest of the plan, which `hold`
     already gives across plans. *Ruled by Yue 2026-11-10: stands.*
  2. A series whose plan fixes is refit stage by stage, never collapsed into one stage, so its
     warm fits cost more iterations. Alternative: collapse with literal paths from a template
     table, which a member whose table differs would get wrong. *Ruled by Yue 2026-11-10: stands; the
     faster collapse is left to the series WPs.*
  3. The closing stage's `turn_off` holds literal paths (the replayed end state), so its history
     node records paths rather than the declared globs. Alternative: record the globs and replay
     at checkout. *Ruled by Yue 2026-11-10: stands.*
  4. Visual, open: a stage draws its `Fixes` row only when it fixes something, as the
     workshop prototype (`renderPlan`) draws its `Fix` row; a `+ Fix` ghost button at the end of
     the frees opens it with the cursor in its field. The prototype adds through one `+ Add`
     popover with a Free/Fix toggle, which this panel has no equivalent of. An always-drawn row
     was built first and dropped: it added a line to every stage and pushed the closing row out
     of the plan-ladder screenshot. *Ruled by Yue 2026-11-10: stands (the row on demand, `+ Fix`).*
  5. The report's veto (`apply_strategy_veto`) no longer marks a suggestion on a path the plan
     leaves fixed as "already refined by the staged plan", so a suggestion to refine a profile
     the caller fixed stays active. A `hold` still vetoes it. Alternative: a deliberate fix
     silences suggestions on its paths, as a hold does, with its own reason. *Ruled by Yue
     2026-11-10: stands; only a hold silences a suggestion.*

  *Review.* `/code-review high --fix` found ten; eight fixed in one commit: `StageResult.fixed`
  names only free paths a fix took (it had listed rows already fixed or held); the plan checks
  (`_stage_order_diagnostics`, `_held_moment_diagnostics`) and the report veto read `turn_off`;
  the magnetic nuclear reference keeps the caller's `turn_off`; `STAGE_PATH_UNKNOWN` says
  "nothing was fixed" for a mistyped fix; the GUI's closing count takes only free literals; the
  `.rxt` `fix` clause parses anywhere among the stage keys; the skill copies re-synced. Not
  fixed: the series collapse (decision 2), and the `.rxt` error for a malformed clause still
  lists only the numeric keys.

  *Measured* (darwin/arm64, worktree venv `[dev]` plus playwright, one run each, on 64416ece2):
  fast suite 14634 passed, 410 skipped, 32 xfailed, 0 failed, 11:55 through `serial.py` (with
  playwright installed the browser files run inside it too); all eight `tests/*_browser.py`
  files 153 passed, 0 skipped; vitest 720 passed (32 files, +3); svelte-check 0 errors, 0
  warnings; ruff clean. 15 tests added, 4.81 s in all on this machine, the slowest
  `test_a_pawley_profile_stays_fixed_through_a_rietveld_plan` at 1.79 s, so none joins the
  slow tail. `tests.reader_output` exit 0, unchanged; `StageResult.fixed` is the one new reader
  field, an empty list unless a stage fixes. The full suite did not run: the change moves no
  measured number of a plan without `turn_off`, which every golden and acceptance protocol is.

  *Gotchas.* `StageSpec` gaining a field changes the typo hint ("did you mean 'turn_on'" now lists
  `turn_off` too). `reference/refinement.md` sits at the 50 000-character page cap, so the prose
  went to `guides/plan.md`.

  *Generality* (the `generality-review` agent, 2026-11-10, sections as returned):

  - `StageSpec:turn_off` default — **holds.** The empty list reproduces every earlier fit; no
    preset sets `turn_off`; tier 1 like `StageSpec:turn_on`. Would change: a preset or GUI default
    shipping a non-empty `turn_off`.
  - `StageResult.fixed` in `OTHER_RECORD_FIELDS` — **weak.** On a declared stage it reports the
    caller's own fix, as `freed` does; on the closing stage it records the package's replay
    (`fixed_at_end`), an action with no row. Would change: an action row for it, or the
    `PlanSpec:closing_window_tol` row's evidence extended to say the closing stage keeps the
    end-state fixes (that row also still said "all free"). *Author:* done the second way: the
    `closing_window_tol` row's evidence now says the closing stage keeps the paths the declared
    stages leave fixed and records them in `StageResult.fixed`.
  - 3a, a series refits a fixing plan stage by stage — **holds.** The collapse as written frees
    what the caller fixed. Unweighed: a per-member collapse built with `closing_stage(member
    paths)`, FullProf `CYC`'s shape; the iteration cost on a fixing plan is unmeasured (1.8-1.9×
    per warm pattern on round-robin sample 1, a plan with no fix). *Author:* left as decision 2
    for the maintainer; the series WPs own the cheaper route.
  - 3b, the closing stage keeps the end-state fixes — **holds.** BGMN's and RIETAN-FP's
    all-free closing runs have no in-step fix verb, so the dissent is weak; every solve passes
    the table's paths, and the no-paths union reaches only names and counts.
  - 3c, `apply_strategy_veto` reads the last matching glob — **holds.** A fixed path is not
    refined, so "already refined by the staged plan" was false for it. Weak side: a `hold` still
    vetoes (predates this WP), so the two ways to fix a parameter get opposite verdicts; a
    literal fix of `instrument.profile.w` lifts the veto on an action over `instrument.profile.*`.
    *Author:* recorded for the maintainer as decision 5; not changed here.

  Next: the maintainer rules on decisions 1-5 and merges #1520; the series WPs revisit decision 2.

- **2026-11-10** — filed by a ghostshift runner as piece 3's follow-up in the gui-overhaul
  milestone, numbered 2208 in the milestone's 22xx block by the shift lead. No open WP owns the
  fixing stage: WP-2127 lists it as a non-goal and records the ruling for a follow-up. Next:
  build the checklist.

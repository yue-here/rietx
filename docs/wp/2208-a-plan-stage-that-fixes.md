# WP-2208 — a plan stage that fixes as well as frees

Milestone: gui-overhaul · Status: ⬜
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

## Non-goals

- A mode per stage. Pawley then Rietveld stays two fits (design 3).
- Series semantics beyond design 4: the series WPs decide them.
- A fix that lasts for the rest of the plan whatever a later stage frees. That is `hold`'s job.

## Tasks

- [x] File the WP; the practice survey in `docs/practice.md`.
- [ ] Schema and runners: `StageSpec.turn_off` and `Stage.turn_off`; `fixed_at_end` and the
  closing stage; both runners, `run_stage`, `replay`; `StageResult.fixed`; the stage node's
  `turn_off`; `blocked_by_hold` and `unknown_paths`; the series collapse; tests, including the
  maintainer's case and a fix a later stage undoes.
- [ ] `.rxt` `fix` clause; `/api/plan/resolve` `fixes`; the GUI's run-stage matching.
- [ ] `help.py`, `capabilities()`, the audit table, the manual.
- [ ] The Plan tab: fix chips and their add field, `lib/plan.ts`, `lib/rxt.ts`, vitest, the dist,
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

- **2026-11-10** — filed by a ghostshift runner as piece 3's follow-up in the gui-overhaul
  milestone, numbered 2208 in the milestone's 22xx block by the shift lead. No open WP owns the
  fixing stage: WP-2127 lists it as a non-goal and records the ruling for a follow-up. Next:
  build the checklist.

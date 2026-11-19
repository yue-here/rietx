# WP-1207 — A project without a CIF, part 2: pattern-only projects

Milestone: v1.2 · Status: ✅ 2026-08-26 — a pattern is a project; the refusal is on the verb
Depends on: WP-1206

## Goal

`Project.create(structure=None)` is legal: a project with zero phases in
which peak picking and indexing work, the parameter table holds the instrument
and background, and `fit` refuses before compile with a named reason.

## Context

User decision (2026-08-25): a pattern-only project is in scope (WP-1017 named
the user with a pattern and no CIF as the audience least served). It is a
library change, which is why it is its own WP.

What assumes at least one phase today (the audit starts here, and is not
complete): `Structure._nonempty` (`schemas/structure.py:491`);
`refine.py:1798, 1941, 2391, 2470, 2549` (`range(len(model.phases))`);
`model/forward.py:1268, 1301`; `Project.create`'s signature
(`project.py:107-116`, `structure` keyword-only, no default); the `.rxt`
renderer's phase blocks (`gui/textdoc.py`); `tree_payload` and the history
diff's table rebuild (`history/tree.py:267-273`); the Model panel's structure
section and the 3D viewer (`GET /api/structure3d` on no phase); the
`RefinementResult` fields indexed by phase (`ticks`, `phase_support`, QPA).

Seams WP-1206 left, verified against the tree on arrival (2026-08-26):

- **The wizard's step 2 is already a `.segmented` with two answers** —
  `lib/wizard.ts`'s `StructureSource = "cif" | "cell"` and
  `useStructureFrom(state, source)`, which is where "this route implies a mode"
  already lives (it moves `rietveld` ↔ `lebail` and disables what the route
  refuses). A pattern-only project is a **third member** of that union and a
  third button, not a fourth mechanism: `structureArgument(state)` is the one
  place `createBody` reads, and `blocked()`/`typedCellReady()` branch on the
  same field.
- **`POST /api/project/new` tells its `structure` forms apart by disjoint
  keys** (`session._is_typed_cell`, dispatched in `_as_structure`:
  `space_group` / `cif`+`upload` / `phases`). `structure: null` falls through
  to the *inline* branch and reaches `_validate(Structure, None, …)` today, so
  this WP's "legal" has to be a branch decided **before** that one, not a
  `None` falling through.
- **`schemas.structure.lebail_scaffold(space_group, cell, *, name)`** is the
  one Le Bail scaffold builder (`DUMMY_SPECIES` beside it, re-exported from
  `indexing.workflow`), and **`crystallography.symmetry.free_cell_names` /
  `complete_cell`** decide which cell parameters a *setting* leaves free. A
  pattern-only project that later gains a phase — from Adopt, or from a typed
  cell — arrives through those, so zero phases must be a state those can be
  applied *to*.
- **`GET /api/spacegroup?space_group=` is project-free**, beside `/api/help`
  and `/api/capabilities`, and is not behind the in-flight 409.
- **`gui/CLAUDE.md`'s size cap now stands at 691** (`tests/test_docs_consistency.py`,
  raised again by 1206's review round — the mailbox said 687); a rule from this
  WP means raising it with the comment that test asks for.

Rules that bind: **a declared name is a claim** (WP-1076): an empty
`phases` list must not read as an answer anywhere a consumer counts phases;
`SCHEMA_VERSION` and the project format bump by one each with the reason
beside the constant (the preview promise); the compatibility direction is
"old files must always open" (memory: break by direction).

## Audit — every `phases` consumer at zero phases

Measured on the pre-change tree by lifting `Structure._nonempty` *at runtime*:
dropping the entry from `Structure.__pydantic_decorators__.model_validators`
and force-rebuilding every model that embeds a `Structure`. Both halves are
needed — `RefinementState` revalidates, so a subclass overriding the validator
does not get through, and a model embedding `Structure` inlines its compiled
core schema, so rebuilding `Structure` alone changes nothing. Synthetic LaB6
pattern (`tests/test_refine_synthetic.synthesize`), `mccusker_default`,
`[dev,jax]` / darwin-arm64.

**The finding that shapes the rest of the WP: nothing crashes.** Every `phases`
consumer in the core is iteration-driven — `for ip, cp in enumerate(model.phases)`,
`range(len(structure.phases))` — so at zero phases they do nothing and the
pipeline runs to the end. `Structure._nonempty` is the *only* thing standing
between a caller and a background-only refinement reported as **`converged`**
at Rwp 0.9637, GoF 23.89, ten instrument and background parameters refined.
So the work is not "stop it breaking"; it is "make it refuse, and make the
empty answers honest".

### Must refuse

| consumer | at zero phases today | wanted |
|---|---|---|
| `Refinement.fit` / `run_stage` / `refine` | every stage `converged`; `MODEL_FAR_FROM_DATA` fires as a *diagnostic* while `status` still says `converged` | refuse before compile, `NO_PHASES` |
| `POST /api/run {"kind":"fit"}` | 200, then `run.status == "converged"` | refused with that reason; Run disabled |
| `agent.refine_json({"task":"refine"})` | refuses `INVALID_REQUEST` — but only because the *schema* still rejects `phases: []` | the same `NO_PHASES` once the schema allows it |

The third row is the trap: today's refusal is a side effect of the validator
this WP removes, so it disappears silently unless `refine_json` is given the
refusal in its own right.

### Already the honest empty answer — no change

`ParameterTable` builds (19 entries, all instrument and background;
`free_paths`, `moving_paths` `[]`; `x0()` shape `(0,)`); `compile_model` builds
in `rietveld` *and* `lebail` and `evaluate` returns the background over all
4200 points; `RefinementResult.ticks` → `{}`; `data_support` → 0 unique
reflections and `n_effective_observations` `None`; `count_unique_reflections`
→ 0; `effective_observations` → `None`; `reflection_table` → `[]`;
`phase_support` fires no `PHASE_UNCONSTRAINED`; `identifiability.background_absorption`
→ `{}`; `phase_agreement` → `[]` through its own `not model.phases` guard
(`refine.py:2034`). The **FitReport** is the best-behaved consumer of the lot:
`layer1_available=False`, abstained `immature`, and **36 unmatched observed
peaks** — it already says the pattern has peaks the model does not.
`Project.create`/`open`, `textdoc.render` and `GET /api/project|params|structure|peaks|history|plan|textdoc|capabilities|settings`
all answer 200; `GET /api/report` is 409 `NO_RESULT` before a run.

### Empty containers that read as answers (WP-1076)

- **`RefinementResult.qpa`** → `QuantitativePhaseAnalysis(phases=[], method="zmv",
  crystalline_only=True)`: "QPA was done, the specimen holds no crystalline
  phase". The mechanism is a two-way test with three cases:
  `compute_qpa` finds Σ zmv·s ≤ 0, then asks `len(structure.phases) > 1`, so
  zero phases falls into the **single-phase** branch — "one phase is 100 %
  whatever its scale did" — and builds an empty table instead of the `None`
  that branch's own docstring reserves for "the scales cannot form fractions at
  all". Wanted: `None`.
- **`RefinementResult.geometry`** → `GeometryTable(distances=[], angles=[],
  bond_slack=0.4, contact_max=3.5, notes=[])`, from a function that *already*
  returns `None` outside Rietveld for the same reason. Wanted: `None`.
- **`io.exporters.qpa_table_csv`** renders the whole Hill & Howard scope header
  over zero rows, and **`refinement_cif_doc`** returns a gemmi `Document` with
  **0 blocks** — an empty CIF written without complaint. Both follow their
  inputs, so both are fixed by the two `None`s above.

### Refuses already, message to revisit

`GET /api/structure3d` → 404 `no phase 0 (this structure has 0)`: accurate, but
phrased for a bad index rather than for a project that has no phase yet — the
message behind the hidden 3D column (task 3). Every other phase-indexed GUI
verb guards with `IndexError` → 404 and needs no change
(`gui/symmetry.py:345, 379, 692, 721`; `gui/session.py:1169`).

### Not reachable from a pattern-only project

`viz/compare.py:197` divides by `len(structure.phases)` — a `ZeroDivisionError`,
but `compare`'s standards always carry phases; `indexing/workflow.py:420` reads
`structure.phases[0]` off a scaffold `structure_from_candidate` has just built.
`multi.py` and `sequential.py` are iteration-driven like the core and inherit
whatever `fit` decides.

## Non-goals

- Fitting with no phases: `fit` refuses (`NO_PHASES`), and the GUI's Run is
  disabled with that reason.
- Multi-phase indexing on a residual (v2 fence).

## Tasks

- [x] The audit: every `phases` consumer listed with its behaviour at zero
      phases (§ Audit above). Measured, not read: nothing crashes, because
      every core consumer is iteration-driven, so `Structure._nonempty` is the
      only thing between a caller and a background-only fit reported
      `converged` at Rwp 0.9637. `ticks` `{}` and the absent `phase_support`
      diagnostic are already right; `qpa` and `geometry` are empty containers
      that read as answers, and `refine_json`'s current refusal is a side
      effect of the validator this WP removes.
- [x] `Structure` allows `phases=[]` (the class docstring says why the refusal
      cannot live there); `Project.create(structure=None)` builds one;
      `fit`/`run_stage`/`refine_multi`/`refine_sequential` and the GUI's
      `POST /api/run` raise `NoPhasesError` (`code = "NO_PHASES"`) *before*
      the tree or the first event, and `refine_json` answers with a **fourth**
      envelope code rather than folding it into `INVALID_REQUEST` — the
      request is well-formed and the model is legal, so re-checking fields
      finds nothing and retrying reproduces it. `SCHEMA_VERSION` 0.8 → 0.9,
      `PROJECT_FORMAT_VERSION` 1.2 → 1.3, each with its reason beside the
      constant. The audit's two empty containers are now absences:
      `compute_qpa` and `geometry_table` return `None` at zero phases.
- [x] GUI: `StructureSource` gains `"none"` and step 2 a third `.segmented`
      button, which sends `structure: null` — an **answer**, where the key's
      absence stays a refusal, since `dict.get` cannot tell them apart and only
      one of the two should create a phase-free project quietly. It is the one
      route that moves the mode nowhere: with no phase there is nothing for a
      mode to govern, and Adopt sets it on the way out. `project_doc` gains
      `n_phases` (a derived summary beside `head`, not a second authority) and
      `moved()` reloads it, so Run, Run-one-stage and the series command
      disable with the reason wherever the last phase arrives or leaves. The
      Model panel's structure column says what to do instead, the 3D column and
      its toggle are hidden with it, and `structure3d`'s refusal is phrased for
      the state rather than for a bad index. The `.rxt` gains a comment where
      the phase blocks would be — a document with neither reads as one whose
      phases went missing.
- [x] Tests: the whole loop over the wire in `test_gui_peaks.py` — a
      pattern-only project refuses the run by name, picks peaks, adopts a
      candidate and *then* fits to Rwp < 0.2. On the module's synthetic LaB6
      rather than the corundum example, and with the candidate injected the way
      every other adopt test here does it: what is under test is the loop, and
      a real search belongs to the acceptance suite. Beside it: the library
      round trip and `NoPhasesError` vs `predict` (`test_project.py`), a 1.2
      and a 1.0 document still opening unmigrated, the wizard's `structure:
      null` against the required key (`test_gui_server.py`), emptying a
      structure through `PATCH`, the `NO_PHASES` envelope code on all three
      refining tasks (`test_agent_surface.py`), and four vitest cases.
- [x] Manual: `using/files.md` § A project with no structure (the state, what
      works over it, and `NoPhasesError.code` printed rather than described),
      `quickstart.md` § Not even a cell beside 1206's § With no structure at
      all. AGENT_PROTOCOL: the §6 row, and `NO_PHASES` named in §9c's envelope
      paragraph. `gui/CLAUDE.md` 691 → 710 with the four rules and the cap
      comment. Browser pass: four things jsdom cannot see, all correct —
      below.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_project.py tests/test_gui_server.py tests/test_gui_peaks.py tests/test_textdoc.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- WP-1076 (declared names), WP-1117 (the preview promise).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**A project without a phase** (WP-1207) is the *third* answer to step 2 and the
fifth `structure` form, `null` — decided ahead of the inline branch, where it
used to fall through and be refused as a malformed model. Four rules.
**Null is an answer; an absent key is not**: `dict.get` cannot tell them apart,
so `project_new` requires the key and only the explicit null creates a
phase-free project. It is the one route that **moves the mode nowhere** — a CIF
implies `rietveld` and a typed cell `lebail` because each says what can be
refined, and with no phase the run is refused whatever the mode says, so Adopt
sets it on the way out. **`n_phases` rides on `project_doc`** — a derived
summary beside `head`, never a second authority — because a client must know a
run is refused *before* it offers one, and `moved()` reloads the document as
well as the curves, since a move can add or remove the last phase (Adopt, a
structure replace, a checkout across either). And the refusal is **on the verb,
never on the model**: `Structure` takes `phases=[]`, so peak picking, indexing
and `PATCH /api/structure` all work over one, while every run route raises
`NoPhasesError` (`code = "NO_PHASES"`, the agent envelope's fourth) **in the
route rather than the worker** — a run started is a 200 whose failure reaches
only the event stream, and the caller asked a question that has an answer now.

## Handover log

- **2026-08-26** — **Closed.** A pattern is already a project. `Project.create`
  no longer needs a `structure=`, and a project with zero phases is a *state* —
  a pattern whose phase you have not found yet — rather than an unfinished one.
  Peak picking, indexing and the instrument and background parameters all work
  over it, which is the whole point: the routes out of that state (adopt an
  indexed candidate, type a cell) all need a project to arrive in, and before
  this the person WP-1017 named as least served had nowhere to start.

  *The audit is the part a successor should read first, because it inverted the
  work.* The plan assumed things would break at zero phases and the job would be
  to stop them. Nothing breaks. Every `phases` consumer in the core is
  iteration-driven, so at zero phases they do nothing and the pipeline runs to
  the end: the fit came back **`converged` at Rwp 0.9637, GoF 23.89** against a
  pattern with 36 clear peaks, with `MODEL_FAR_FROM_DATA` firing as a diagnostic
  beside a status that contradicts it. `Structure._nonempty` was the only guard
  there was. It was measured rather than read — dropping the validator from
  `Structure.__pydantic_decorators__` and force-rebuilding every model that
  embeds a `Structure`; both halves are needed, since `RefinementState`
  revalidates (a subclass does not get through) and an embedding model inlines
  the compiled core schema (rebuilding `Structure` alone changes nothing).

  *Done.* `Structure` takes `phases=[]` and its docstring says why the refusal
  cannot live there. `NoPhasesError` (`code = "NO_PHASES"`) is raised by `fit`,
  `run_stage`, `refine_multi`, `refine_sequential` and `POST /api/run`, each
  before a tree or an event. `compute_qpa` and `geometry_table` answer `None` at
  zero phases. `refine_json` gains a **fourth** envelope code. The wizard gains
  a third route, `project_doc` an `n_phases`, the Model panel an empty state,
  and the `.rxt` a comment where the phase blocks would be. `SCHEMA_VERSION`
  0.8 → 0.9, `PROJECT_FORMAT_VERSION` 1.2 → 1.3, `gui/CLAUDE.md` 691 → 710.

  *Measured* (`[dev,jax]`, python 3.12.12, darwin/arm64, the main checkout's
  venv). Fast suite on the merged tree **3097 passed / 72 skipped**, 4m45s —
  against 3m00s for the same selection pre-merge, and the difference is machine
  state, not the change: another session's `work/final_series.py` was running
  beside it, which is why this is a range and not a figure. The ladder:
  branch base 3087, +6 for this WP's tests → 3093 pre-merge, +4 for main's own
  new reader tests (PR #149) → 3097. `npm --prefix gui test` **458 passed**
  (454 at the branch point, +4 for the third route); `npm --prefix gui run
  check` clean; `ruff` clean; sphinx `-W` clean; dist rebuilt at `dd5807dda669`
  and `test_gui_dist.py` green.

  *Decisions taken past the WP's own text, three, all deliberate.* (1)
  `NO_PHASES` is a **fourth agent envelope code**, not an `INVALID_REQUEST`.
  The request is well-formed and the model is legal, so an agent told
  `INVALID_REQUEST` re-reads its field names and one told `REFINEMENT_FAILED`
  retries; neither helps, and the AGENT_PROTOCOL row therefore leads with **do
  not retry**. (2) `structure: null` is an answer and an **absent key stays a
  refusal** — `dict.get` cannot tell them apart, and a client that forgot the
  key should be told rather than handed a phase-free project. (3) `PATCH
  /api/structure` with `{"phases": []}` is now a 200. That is WP-1206's
  review-round rule arriving as a consequence rather than a decision — a change
  at `_as_structure` reaches every verb crossing it — and on reading it, it is
  right: taking a wrong phase back out lands in exactly the state the wizard's
  third route creates, and the run is what refuses. The test that pinned it as
  a 400 now pins an atomless phase, with the pattern-only path asserted beside
  it.

  *Gotchas for whoever is next here.* The end-to-end test injects a candidate
  rather than running a real search, like every other adopt test in
  `test_gui_peaks.py` — the **loop** is what is under test, and a real search
  over that pattern belongs to the acceptance suite. `test_acceptance_indexing.py`
  was **not** re-run: nothing here touches an engine (the indexing rulebook's
  gate is about engine changes), and `structure_from_candidate` is untouched.
  The browser pass found no defects, but it produced one lesson worth keeping:
  I read a downscaled screenshot as showing an enabled Run button and was
  wrong — the computed style (opacity 0.45, cursor default) is what settled it,
  and a screenshot is evidence about layout, not about state. Finally, the
  Model panel's structure column keeps its full half-width holding one
  paragraph when there is no phase; it reads acceptably and the splitter is the
  user's control, so it was left alone rather than special-cased.

  *Not this WP's.* The closing commit `a24f599e` also carries the PreToolUse cd gate (`.claude/hooks/no_top_level_cd.py`), the pr-review corrections and the `.claude/settings.json` change — a concurrent session's uncommitted tooling work, swept in by a broad `git add -A` here and left in place rather than force-pushed apart; `5bbc0a43` records it. The same `git add -A` put 1.2 MB of that session's scratch run output (`obs.npy`, `events.json`, `grid.npy`, `series.json`) at the repo root in `fb4f8732`; a code-review round removed them, and they stay recoverable from that commit.

  *Next.* [WP-1208](1208-plan-introduction.md) (the Plan panel). Nothing is
  pushed into its `### Inherited`: this WP left no seam a Plan WP has to know
  about, beyond `n_phases` on the project document, which is already a
  `gui/CLAUDE.md` rule.

- **2026-08-25** — created from the v1.2 triage.

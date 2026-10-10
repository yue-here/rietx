# CLAUDE.md — rietx

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64 core, pydantic v2
schemas, gemmi for CIF/symmetry. Import name `rietx`, aliased `rx` (`import rietx as rx`).

**This file is for changing the package.** To *use* it (refine someone's data):
`docs/skill/rietx/SKILL.md` (the agent skill) + `docs/manual/` Part 1. Nothing here
substitutes for either.

Each rule below is stated with its identifiers and its measured anchor; the derivation, the
run that found it and the numbers behind it stay in the WP file, module docstring or milestone
record the clause names.

## Commands

```sh
uv venv --python 3.12 && uv pip install --python .venv/bin/python -e ".[dev]"   # setup (once); a WORKTREE needs its own venv, and --python stops an inherited VIRTUAL_ENV retargeting main's (tests/CLAUDE.md)
uv pip install --python .venv/bin/python -e ".[dev,jax,torch]"   # + optional jax/torch backends
.venv/bin/python -m pytest -n auto --dist loadgroup    # full suite ~15-30 min, incl. real-data acceptance (counts: § Numbers)
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # skip acceptance, ~1-3 min
.venv/bin/python -m pytest tests/test_cross_backend.py # Jacobian agreement matrix; rows self-skip without their backend
.venv/bin/python -m tests.bethanechol_benchmark        # the graded indexing benchmark (~1 h; run it ALONE — engine budgets are wall-clock)
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html  # theory manual
.venv/bin/rietx gui my_sample.rex [--scratch]      # the refinement GUI (localhost:8731); --scratch works on a temp-dir copy
npm --prefix gui ci && npm --prefix gui run build      # rebuild the GUI's committed dist
npm --prefix gui test && npm --prefix gui run check    # vitest (jsdom mount, fnmatch parity, panel/text-sync/model-edit/3D-scene/splitter/theme/plot/peaks logic; count: § Numbers) + svelte-check
.venv/bin/rietx watch <live-dir>                     # live viewer for a LiveSession run
.venv/bin/rietx compare --open                       # settings-comparison UI on the standards
```

`-n` deliberately not in `addopts`: a bare `pytest tests/x.py::y` stays serial, so `-s`/pdb
keep working. `--dist loadgroup` is not optional — it honours the `xdist_group` marks keeping a
shared fixture on one worker, and ignoring them is silent, so `tests/conftest.py` refuses a run
without it.

Testing headlines (operating detail — xdist group ordering, budget narrowing, quoting counts —
`tests/CLAUDE.md`; dated measurement diary `docs/milestones/v1.0.md` § Appendix):

- **Quote wall clock as a range, never a figure**: machine state moves it further than most
  changes do. Compare runs, not records.
- **A wall-clock budget in a test is a runaway guard, never a timer**; may live one rank down,
  in the library.
- **Say which numbers moved**: +N tests → passed+skipped +N exactly in the fast selection; a
  new skip ≠ a new pass.
- **Full suite fires once, on the final tree**, only when the change could move a measured
  number — never mid-edit, never on `main` for a baseline (`tests/CLAUDE.md` § Running).

### Numbers

Measure, never quote. Fast counts: the `-m "not slow"` command above, verbatim — never add
`-q` (`addopts` has one; `-qq` prints no summary at all). Full-suite counts + `--durations`:
latest nightly `full` job log (`gh run list --workflow nightly.yml`; `[dev,jax]`, Linux,
~90-day retention, ≤1 day stale). Quote every count with its venv **and** platform
(`tests/CLAUDE.md` § Quoting numbers); a session's own go in its WP handover.

`rietx compare` answers "does this new correction actually help?": pick a standard, tick
variants, read the **cumulative Δχ² vs reference** panel — it localises *where* a change acted,
not just whether Rwp moved. Registry+runner `viz/compare.py` (headless
`compare.run(standard, variant)`); server `compare_app/`, page its `static/`. Its standards are the
acceptance suites' protocols, asserted field by field by `tests/test_compare_ui.py` — **add a
row there whenever a new correction lands.**

## Data flow

```
Structure/Instrument/PatternData (schemas/, pydantic, JSON round-trip)
  → ParameterTable (params/vector.py): tree → flat fp64 θ, dot-paths
    ("phases.0.cell.a", "instrument.profile.w", "instrument.background.c2"),
    crystal-system cell ties (b←a etc.), softplus/logit transforms
  → CompiledModel (model/forward.py): per-stage frozen state — reflection list
    (crystallography/symmetry.py, gemmi), per-atom symmetry-op subsets
    (structure_factor.py), per-(emission line, reflection) point windows,
    FCJ quadrature node counts (profiles/fcj.py), background design matrix
    (+ P-spline penalty rows); derivative_bases() serves both the analytic
    Jacobian and FitReport Layer 1 from one expansion
  → run_least_squares (optimize/least_squares.py): scipy TRF, bounds,
    analytic peak-chain Jacobian (FD fallback), esds from χ²·(JᵀJ)⁻¹ ×
    Bérar-Lelann inflation
  → staged runner (strategy/staged.py) loops stages, guards, recompiles
  → RefinementResult (schemas/results.py) → FitReport (report/, 3 layers)
    → plot / plot_for_vlm / write_html (viz/)
  → history DAG (history/, schemas/history.py): every stage auto-commits an
    immutable restorable node; checkout/run_stage/branch to fork a strategy,
    merge/cherry_pick to recombine, replay to recompute a node evaluate-only,
    append-only JSONL to persist; history/events.py streams per-iteration
    events, viz/live.py + watch/ render them live
```

**Telemetry/cancel.** `fit`/`run_stage`/`refine` take `events=` and `cancel=` (an
`optimize.cancel.CancelToken` another thread sets). Cancellation is **cooperative, read between
residual evaluations**, never an interrupt, so frozen-per-stage discreteness holds; the
in-flight stage is *abandoned* — no node, no commit, models restored to pre-stage values (a
seeding stage writes before solving). `RefinementCancelled` carries `.completed_stages` and
`.node_id`, the last completed node the working state stands at. Event `data` is an **open
dict**: a new field in a kind is no `EVENT_SCHEMA_VERSION` bump, a new kind is
(`history/events.py`). The **run state is not an event** — `EventKind` is closed, so a run's
status travels **beside** the stream, in `status.json` and a held `run.lock`. WP-1401 carried
that one rank out, across a process boundary needing a channel the OS maintains (a dead writer
writes nothing), so `watch` reads meta, status and snapshot too; `runs.liveness_of` weighs them.

**Series** = N refinements chained by warm start (in-situ ramp, parametric sweep, tray of
related specimens). `sequential.py` (`SequentialRefinement`/`refine_sequential`) →
`SeriesResult`: per-pattern summaries + parameter *trajectories*, one history tree per pattern
(pinned by `TreeHeader.data_fingerprint`), linked by annotation notes. Not `multi.py`, which
stacks patterns into **one joint residual**. Chaining buys ≈3× in iterations and nothing in
accuracy, and its trajectory is path-dependent by construction → `direction="both"` runs the
chain each way and flags parameters the two disagree on (`SEQUENTIAL_PATH_DEPENDENT`), the only
check separating a measured trajectory from an ordering artefact. A rejected warm fit
**escalates a rung at a time**, keeping the best attempt (`entry.rung`); still diverged after
the last rung → **quarantined** (`SEQUENTIAL_UNRECOVERED`): seeds no successor, joins no median
(WP-1051). **The first rung is a bet, budgeted from what a winning bet costs on this chain**
(WP-1127): `first_rung_factor` × the dearest *converged* first rung, nothing until several have,
never another fit's cost. `_prefer` ranks a truncated attempt below any completed one, so a bound
only shortens work already being discarded and accepted values stay bit-identical. Set it for
**margin**: win/lose rung gap ~6×. `events=`/`cancel=` are **per pattern** (WP-1016): `data`
carries `series_index`/`…_label`/`…_n`/`…_pass` (+`…_rung`/`…_cold` on a *restart*), so no
`EventKind` is new; a cancelled series **returns** what completed with `SEQUENTIAL_CANCELLED`
(WP-1006's rule one rank up; `sequential.py` docstring). **A `RefinementState` fact that is not
in the models crosses no pattern boundary until someone builds it one** (WP-1441, #376): `carry`
moves `Structure`/`Instrument` values and `prepare` runs a line before the per-pattern
`Refinement` exists, so `_ties` and `_variables` reached pattern 1 and nothing after — an
*absence*, never a drop, and a ninth such fact inherits it. The two halves differ: a tie is
**re-declared** per pattern by `constrain=(index, ref)` and never carried, since `tie_equal`
resolves globs against a live table and each pattern has its own — so the hook fires once per
**fit**, ladder rungs and the `verify_discontinuities` refit included — while a variable's
*value* is carried under the same globs (`vars.<name>` is an ordinary dot-path), **after** the
hook, the only order in which the name exists.

**Parameter surface** (WP-1004) — the table without running a fit.
`Refinement.parameters() → list[ParameterRow]` lists *every* entry (fixed, locked, tied), esds
from the last fit
merged in, each held row naming which of the three reasons holds it (`.refinable`,
`.held_because`). `set_vary(globs, vary)` / `set_values({path: value})` edit and auto-commit
`set_vary`/`set_value` nodes. Three load-bearing rules: `ParameterRow` mirrors
`params.vector.Entry` field for field (pinned by `dataclasses.fields`; `esd`/`mode_fixed` the
declared extras); a **tied** path refuses an edit and names its sources; `mode_fixed`
(lebail/pawley force-fix every `.atoms.` path, `.scale`, `.source.lines.`) is *not* `locked` —
that keeps a Le Bail phase's mandatory dummy atom from looking editable.

**User constraints** (WP-1070) sit beside the derived ties: `tie`/`tie_equal`/`untie`,
auto-committing `set_tie` nodes. `Refinement._ties` is the one authority for *which* ties are
the user's (every `ParameterTable` build rederives the symmetry ties and knows nothing of a
user's); `RefinementState.ties` is why a checkout restores the parameter *count*. Symmetry
outranks a user tie, enforced in `_apply_ties` and not only in the verbs' refusals — a model
edit can make an already-tied path symmetry-tied after the fact.

**A hold** (WP-1435, #211) is that construction over `vary` rather than over ties, and it
exists because **`vary=False` does not keep a parameter fixed**: a plan *replaces* the vary
flags (WP-1208), so any stage whose `turn_on` matches frees it — a certified cell pinned for
`lab_calibrate` refined 185 ppm while the model still read `False` and nothing said so.
`hold`/`unhold` (`set_hold` nodes), `Refinement._user_holds` the authority,
`RefinementState.holds` why a checkout restores it, and `Entry.held` read by
`ParameterTable.set_vary` beside `locked` — **in the table, never at the call sites**, or
only the callers that remembered would honour it. Precedence: locked/`mode_fixed` outrank a
hold, a hold outranks a glob, and `held_because` reports them in that order because only the
middle one `unhold` can lift. A blocked glob is **reported**, not silent
(`StageResult.blocked_by_hold`, `HOLD_BLOCKED_PLAN`) — and that report is keyed on the hold
because it cannot be keyed on `vary`, which 38 of 46 LaB6 entries carry by default. Two
consequences for a new caller: `set_vary` **can now refuse**, so read its return rather than
the list you offered it; and `_user_holds` is not `_held`, which is WP-1301's stage-scoped
reading of what the data can see.

**Plans.** Exactly **one** `StageSpec`/`PlanSpec`, in `schemas/plan.py`; `schemas/history.py`
and `agent.py` re-export. `PLAN_INFO` (`strategy/staged.py`) carries
title/description/modes/when-to-use per preset, in bijection with `PLAN_PRESETS` by meta-test.
**A mirror is crossed at the two authorities that own it, never at a call site** (WP-1110):
`PlanSpec`/`StageSpec` validate the `RefinementPlan`/`Stage` dataclass inbound, `resolve_plan`
converts the spec outbound, so no surface is picky about which it gets. Dispatch by
`isinstance`, never by shape — they share *every* field name, which let a `PlanSpec` run through
`fit(plan=…)` to a bit-identical answer under an annotation that does not admit it, and a
structural test would have certified that accident.

**`capabilities()`** (WP-1007, `capabilities.py`) — the one call saying what a build can do:
backends *with whether each optional dependency imports here*, solvers, plans from `PLAN_INFO`,
modes, anodes, formats `read_pattern` opens, and the **six** versioned contracts (schema /
report-thresholds / event-schema / project-format / textdoc-format / indexing-thresholds), in
the arm and not prose — a client reads the field list, and a meta-test fails on a `*_version`
field that is not the constant it claims to quote. **Every arm is quoted from a live registry;
a meta-test fails on a member missing from its arm.** `features` flags are *derived predicates*
(a schema field's presence, a top-level export's existence), never literal `True`, so a flag
flips by itself when its feature lands. **A derived flag still rots, silently** — the `hasattr`
name and the real export drift apart while the test asserts the flag's own expression, which kept
`features["indexing"]` `False` for its whole life (WP-1037) — so each surface flag's export name
is *data* (`_SURFACE_FLAGS`), and a meta-test checks every name in it against `__all__`.

**Guards.** Hits are `GuardFinding(code, paths, value, message)`; `GuardReport`'s six fields
hold those; `str(finding)` is the pre-v1.0 text byte for byte (pinned by test — the diagnostics'
messages are built from it); every guard `Diagnostic` carries its paths in `where`,
`HIGH_CORRELATION` included. New guard = new `GuardFinding` constructor there; `code` is
deliberately an open vocabulary, not a `Literal`.

**Project** (WP-1005) = a `.rex/` **directory**: `project.json`, the pattern file copied
byte-for-byte, `history.jsonl`, `live/`, `exports/`, via `Project.create/open/save`
(`project.py`, `schemas/project.py`). Directory, not archive: crash safety is append-only writes
by one writer. **One authority per fact** — `project.json` holds *settings* (selected
plan/mode/limits, excluded regions, the GUI's own `ui` keys); `history.jsonl` holds model state
and its head *is* the working state, so no parameter value is duplicated and **saving is about
settings, not durability** (the tree exists from `create`). The pattern is a file, not a
`PatternData`, so: the bytes are the contract (readers' esd column never overridden), and the
**reader call** is part of the reference — `DataRef` records which `io.readers.PATTERN_FORMATS`
entry claimed the file plus its options, a pdCIF with a `_meas` and a `_calc` block being a
different pattern per `block`. It carries sha256 of the bytes *and* the parsed-array fingerprint:
agreeing bytes + disagreeing fingerprint = a reader change, not a corrupt project.
`excluded_regions` live in the document, being protocol in neither the file nor
`RefinementState`. Two rules (WP-1033): `project.fitted_mask` is the one authority for **which
channels the next run fits** (`compile_model`'s first act; a function, so a pattern the project
does not own — a series member — asks the same question); and an inverted or empty interval is
**refused, not reordered** by `schemas.project.check_interval`, one sentence the verb, the
`.rxt` parser and the document's validators all quote. **There is no read-only way to open one**:
every verb writes into the directory and `Project.open` appends a head annotation before any verb
runs, so looking without changing means a copy — `rietx gui --scratch` (byte-for-byte, temp dir).

**Entry points**: `Refinement.fit()` / `refine()` in `refine.py`. Modes: `"rietveld"`;
`"lebail"` (intensity partitioning in `CompiledModel.lebail_update`); `"pawley"` (per-hkl
intensities as an off-table θ block — `model.forward.PawleyBlock`, appended in
`run_least_squares`; overlapped groups get equal-split restraints and come back flagged
`PAWLEY_OVERLAP_UNRESOLVED` rather than confidently split).

**There is one integration surface and it is the python API** (WP-1303, which deleted WP-0602's
JSON-in-JSON-out second one after measuring zero use): call `Refinement.fit`, dump with
`model_dump(mode="json")`, and a failure *raises*. The rule to carry: **a dedicated tool surface
earns its place only where it gates, renders, audits or parallelises** — none of which a
shell-equipped agent needs here — and one a process boundary does want takes **paths**, never
inline payloads. Two shape rules outlived it. (1) The four answers are different *types* —
`RefinementResult`/`SeriesResult`/`IndexingResult`/`SuggestionResult` — and an indexing answer
carries no `cell` key. (2) **A companion rides beside an answer, never inside it**:
`IndexingResult.evidence()` (WP-1043) and the stage trajectory (WP-1058) — **the report at every
stage boundary, because a run's last state is routinely its least informative** (a plan absorbs
an error it cannot free and converges suggesting nothing, while its first stage named the cause).
Default-off since WP-1003/1064: `fit(stage_reports=True)` → `stage_reports_`, called in loops;
rungs are states the plan already visits, so the answer is bit-identical.

### GUI

`rietx gui [PROJECT.rex]` — stdlib `http.server` on 127.0.0.1 serving a committed Svelte 5 dist,
**documented** since WP-1017 (`using/gui-quickstart|guide|power.md`) with its **routes still
provisional by declaration**. Rulebook — session/wire split, server contract (the 409 while a run
is in flight), `.rxt` document, editors, the nine panels, 3D viewer, theming, the example
projects: `gui/CLAUDE.md`, loaded under `gui/`.

## Invariants (do not break)
- **Frozen-per-stage discreteness**: hkl list, symmetry-op subsets, FCJ quadrature node counts,
  window index ranges are computed at stage compile and NEVER change during a least-squares run;
  regenerate only between stages. Keeps the residual smooth for FD/autodiff Jacobians. (FCJ node
  *positions* follow the parameters smoothly, quadrature split at the overlap-trapezoid kink —
  `profiles/fcj.py`.)
- **fp64 everywhere** in the core; a GPU backend may compute Jacobian *columns* in fp32, but the
  residual used for cost/statistics and the solve stay fp64 on host — `backend/linalg64.py` is
  that boundary. Holds on real hardware: an all-fp32-column Apple-MPS refinement lands 3.5e-8 Å
  from the numpy fp64 cell, because the trust region re-measures each step against an fp64 cost.
- **No pydantic in the hot loop**: `ParameterTable.decode()` returns a plain dict; the forward
  model consumes floats/arrays only.
- **An analytic Jacobian branch claims what one parameter *name* reaches.** `_make_jacobian`
  dispatches on the free path's name and each branch computes only the rows it was written for,
  so a tie that moves rows outside that reach returns the column **short** rather than raising.
  `_column_extras` reads off C what each column also moves, every branch declares its reach, and
  anything beyond takes the whole-model FD column (exact: it decodes through C like the
  residual). A new branch, or a new way to widen C, extends that gate;
  `test_cross_backend.py`'s `families_tied` row is where other backends check it. Un-gated, a
  background column measured wrong by 49 % of its own scale (WP-1070).
- **A branch's oracle must be exact where the branch is; the whole-model FD is not.** It
  perturbs θ, so on a transformed parameter it carries the transform's O(h) curvature and
  certifies the FD column it is a copy of — a phase scale's FD column sat 4.6e-6 from the truth
  while agreeing with the whole-model FD to 2e-11 (WP-1121). Check where the check is exact
  instead: where the model is *linear* in the parameter (phase scale, Pawley intensity) a
  difference quotient in **physical** space has no truncation error at any step, so the bar is
  agreement at a **100 % step** (3.6e-16 there) and error growing as the step shrinks is
  cancellation, not a defect. Such a column's equivalence bar is exactness, not bit-identity,
  and it moves every converged fit that frees the parameter.
- **"Can this parameter move?" is `moving_paths`, never `free_paths`** — the rule above one rank
  up, governing every *structural* freeze. A tied entry is not a column of θ yet changes while θ
  does, so `ParameterTable.moving_paths` (free ∪ its ties, read off C's nonzero rows) licenses
  any freeze resting on "this cannot change during the stage": `compile_model` takes that set,
  and `None` means *no claim made* and gates nothing, since an empty set claims nothing moves.
  Two freezes rest on it — FCJ node sizing, and skipping a correction sitting at its off state
  (`CompiledPhase.skip_extinction`). Third rule keeping them honest: **a claim about what a name
  reaches is verified where it is used** — `_peak_chain_column` checks the scalars it
  finite-differences anyway against the bases it was told to skip and raises naming the path, so
  a wrong claim costs work, never a short column (WP-1109).
  **A freeze resting on *flatness* needs the other reading of C — which column moves it**
  (WP-1342): `column_reach`, and `entry_reach` where the entry is not a column. Testing the free
  path's **name** could not see a `vars.X` driving it, so the absent-phase hold and the Le
  Bail/Pawley force-fix each reported success on a set they could not see into, silently and at
  Rwp identical to 1.7e-15. Three rules for a new consumer. **All, never any** — one visible
  phase gives a shared column real gradient, and holding it anyway cost 10 441 ppm on that
  phase's cell. A **variable is dropped before the test**, the forward model never reading one
  (`is_variable_path`, third rule); left in, every tied column fails on its own name. And the
  record takes the **column** while its reach rides beside it (`StageResult.held_reach`), since
  `where` keyed on the reach made one finding about a phase into one per tied cell parameter.
- **A staged plan does not converge its intermediate stages; the one that does is the last**
  (WP-1123, flipping what 1113 measured). `RefinementPlan.intermediate_ftol` (1e-6 vs the
  solver's 1e-9) is the schedule; `stage_ftols()` the one authority applying it, since the plan
  alone knows which stage is last — no runner reads `Stage.ftol` itself. **Cumulative staging
  bounds the cost**: an intermediate stage's parameters keep refining in every later stage, so
  1.2-1.6× fewer evaluations costs ≤ 0.03 esd on every non-degenerate parameter — a bound for
  **one fit**, not for a *chain*, where the effect is unbounded and not even fixed in sign
  (measured both ways, 1.12× better and 1.04× worse). A series is measured, never assumed.
  `intermediate_ftol=None` is the bit-identical way back and what a golden declares; the record
  says what a stage **ran** at, never what it declared (`StageResult.ftol`, `NodeAction.ftol`),
  or a cherry-pick replays what never happened.
- **An unconstrained linear block is already solved jointly; profiling it out cannot buy an
  evaluation** — VarPro's win is over alternation, never done here (measured 1.00× on 34 of 34
  pure-Gauss-Newton stages, 0.79× overall). What survives: *correctness* (esds marginalised over
  the block, not conditional on it) and Pawley **dimension**, a per-step cost not a count. A
  **bounded** block (scales, Pawley intensities) leaves the identity the moment a bound goes
  active. WP-1125, `docs/solver-survey.md` §2.A1.
- **A phase the data cannot see is a flat direction, held for the stage rather than bounded**
  (WP-1301). It reaches the pattern only through `scale × |F|² × profile`, so at a floored scale
  nothing of it moves Rwp while its cell leaves the physical range; a bound narrows that walk, is
  never free, and is suppressed by a caller's own (`params.vector.cell_window`). `_run_stage`
  holds every free structural path of such a phase — never its `scale`, the one direction that is
  not flat — and `StageResult.held` records it. **Support is a fact about the values and a stage
  moves them** → re-measured at the answer: a phase that appeared is *released*; one that
  **collapsed** while solving is restored to where the stage found it and held (one extra solve,
  never a third). **A value that is not a measurement is the caller's**: held paths leave
  `RefinementResult.parameters`, a trajectory starts at the onset. Which phases: a scale under 3σ
  of its counting-noise esd (`refine._answer_significance`, WP-1523), never the fitted curve an
  absent phase's cell fits to noise; zero limit `phase_line_counts`. Both feed `PHASE_UNCONSTRAINED`,
  which says what was done; `SEQUENTIAL_PERSISTENT_FINDING` what no one pattern can: "42 of 68".
- **Pydantic knows no crystallography, so a whole-model swap is checked by building its table.**
  Every symmetry refusal is raised in `ParameterTable.__init__`, and the snapshot
  `Refinement.edit` commits performs none of it, so `edit` builds the **proposed** pair's table
  and refuses rather than recording (WP-1035).
- **A specimen has one crystallite size, and exactly three of the seven sample-broadening
  quantities are not one number across wavelengths** (WP-1131, WP-1343). A size coefficient is
  (180/π)·K·λ/L and the Gaussian one its square, and the magnetic coherence length's Lorentzian one
  (`magnetic_lor_size`) goes as λ like `lor_size`; both strains, the magnetic strain and Stephens'
  Λ(hkl) are λ-free and stay shared. `params.multi.SIZE_LAMBDA_POWER` is that list **as data**, and
  `MultiParameterTable` hands histogram h the factor λ_h/λ_0, so **a joint fit shares the size,
  never the degrees** (unfixed: 363.3 Å against 623.9 Å for one specimen, `converged`, Rwp ×1.8 on
  the long-λ histogram and ×4.7 for `gauss_size`). The seam is `ParameterTable.apply_value_scale`,
  a factor folded into **C** — because `_peak_chain_column` finite-differences θ *through*
  `decode`, no derivative branch is touched and the analytic and FD columns cannot disagree.
  Sharing happens in **internal** coordinates, so a writer that touches one entry per histogram
  inherits nothing: shared bounds are **intersected**, not last-write-wins, and a **seed is in
  column units** — a physical one puts two histograms at different coordinates for one column and
  the last write silently wins.
- **A derived quantity of one parameter needs no covariance; one of two correlated
  columns does** — WP-1072 one rank down. `model/microstructure.py` reports each
  mechanism's Gaussian and Lorentzian readings separately with exact single-parameter
  esds and *compares* them (`size_agreement`), rather than combining them into a number
  whose esd it could not honestly give. Conversions stay in `caglioti.py`; the answer is
  a **coherent domain size**, never `particle_radius_um`, quoted as an order of magnitude
  with its K and beside its separability verdict.
- **Weights**: the file's esd column when present (readers), Poisson √max(y,1) only as fallback.
  Never subtract an estimated background — hold it additively (`BackgroundFixedPlusChebyshev`) or
  co-refine it under a smoothness penalty (`BackgroundPSpline`).
- **The observation count is reflections, not points — and it gates nothing** (WP-1071).
  `n_points` is the algorithm's N; McCusker §9's warning is that refining against it outruns the
  data in silence (22 003 points against 132 reflections on 11-BM NAC). `optimize.statistics` is
  the one authority: `count_unique_reflections`, `effective_observations` (Altomare 1995,
  overlap-corrected, a float). Its two bands, like `background.diagnostics`' five-to-ten steps
  per FWHM, are **quoted from the papers, never tuned**: they set a diagnostic's *level*, nothing
  else.
- **A derived quantity's esd goes through the whole covariance; one that cannot be measured is
  absent rather than zero** (WP-1072, McCusker §10). `model/geometry.py` propagates J·Cov·Jᵀ off
  the final Jacobian and carries the diagonal-only number beside it (`qpa.weight_fractions`'
  precedent) — dropping the correlations moves an esd ×0.71 to ×1.15, in *both* directions, so a
  diagonal esd is not the conservative choice. `None` covers all four ways a number is
  unavailable: no covariance; no free source; a quadratic form reaching zero by cancelling (a
  symmetry-fixed 90° angle); a straight angle, where linear propagation does not hold at all.
  Two rules for anything built on it: a geometry row **is** a restraint row (σ = weight = 1), so
  `model/restraints.py` stays the one derivative chain; and a neighbour search is proved complete
  by **orbit counting** (|A_ij|·m_i = |A_ji|·m_j), never by the distances looking right.
- **The normal matrix is equilibrated before inversion, and a direction the data does not move has
  no esd rather than a small one** (WP-1110 item 14; `statistics.normal_covariance`'s docstring).
  `pinv` cuts every eigenvalue under `rcond × |λ|max`, so the *largest* column sets the cutoff for
  all of them and a flat direction returns at **zero** variance — the confident wrong singleton
  wearing an esd. Jacobi-scale first (van der Sluis 1969); the test needs no dataset, since an esd
  must not depend on another parameter's units. A gradient-free column is then infinite variance,
  true and unpropagatable, so `_cov_free` drops it and `ParameterTable.unmeasured_rows` names what
  it reached — and **consumers mark, never clamp**: a tie inherits its source's blindness, a
  geometry row only if its own partials touch one, QPA the *whole* block since W normalises by a
  sum. **A tiny column is live** (WP-1463): square one only via `statistics.column_rescale`.
- **A declared name is a claim, and an absent writer fails no test** (WP-1076, the rule above one
  rank up). Two shapes: a field whose empty state reads as an *answer*
  (`RefinedParameter.at_bound` was `bool = False`, so every result said "not at a bound" about
  parameters nothing had checked); a `Literal` member no code produces (`StageResult.status`'s
  `"skipped"`; `NodeKind`'s `"lebail_update"`, whose `api_call` rendered a method that does not
  exist). Nothing raises and nothing goes red → a new field's **default** and a new vocabulary
  member each need their writer named at review. Where the fact already has a computing authority
  the second surface is a *projection* of it: `staged.bound_findings` is one bound test feeding
  both the `BOUND_HIT` diagnostics and `at_bound`, pinned **set-equal** rather than re-derived.
  **That test asks whether the limit *carried load*, never whether the value is near one**
  (WP-1434): TRF keeps its iterates strictly feasible, so a distance measures when the solver
  stopped, and it went silent on nine of 32 binding cases. It is a conjunction — within a
  hundredth of an esd of the limit *and* the residual not orthogonal to that column
  (`LSQOutcome.residual_cosine`, zero on every free column at a stationary point by the normal
  equations) — because the angle cannot separate a stage that stopped early en route and the
  distance cannot separate a free optimum that lands nearby. Neither threshold is tunable by
  eye; both docstrings carry the window they were measured into.
  Where it has none the honest empty state is `None`, which cannot regress into a lie the way a
  defaulted `False` can. All nine of 1076's surfaced while writing a manual chapter over the type,
  never by reading the code. **A message that names its discriminator makes the same claim**, one
  rank along: `SPACE_GROUP_SETTING_ASSUMED` quoted the composition each setting implies, which is
  the right evidence until the sites that swap carry one species — on Mn₃O₄ it printed `Mn12 O16`
  twice and still asserted a ZMV that had not moved. So evidence is computed, *then* checked that
  it separates, and falls back to what does (WP-1118).
- **A position correction belongs to a geometry, and so does the action that names it** (WP-1073,
  McCusker §5 eq 3/4). `sin 2θ` is flat-plate transparency on a plate and the along-beam
  capillary offset on a capillary → `report/layer1.POSITION_TEMPLATES` and
  `layer2._POSITION_ACTIONS_BY_GEOMETRY` are keyed by `Geometry.kind` and meta-tested against
  each other *and a real* `ParameterTable`; geometry-blind, the map suggested a force-fixed
  parameter and the route answered 409. Three rules for a new aberration: a parameter the forward
  branch skips is **force-fixed, not merely unfree** (else a free entry is a dead column); "this
  instrument has no such error" ≠ "refine it and get zero" (on 11-BM that pair is a degeneracy the
  fit rides to a bound while Rwp *improves* and the cell moves 1117 ppm); its evidence is a
  **rung**, never the endpoint.
- **A stage weights the restraints, and the scalar stops at the row build** (WP-1074, McCusker §8
  eq 7). `Stage.restraint_weight_scale` = c_w in S = S_y + c_w·S_G, frozen onto `CompiledModel`
  at stage compile, so a schedule changes it *between* stages, never inside one. √c_w multiplies
  the **assembled** rows (`CompiledModel.restraint_residual`, reached by every backend through
  `rows.assemble`, and the analytic block in `least_squares`) and never the compiled items or
  `restraint_partials`, whose *second* consumer is `model/geometry.py` calling it at
  σ = weight = 1 for the unweighted partials every reported esd is built from. Default 1.0 is the
  identity (bit-identical on a restrained five-stage fit); 0.0 silences the rows without removing
  them, so the count the statistics exclusion rests on cannot move mid-plan. Two tests cover this
  and neither covers the other: the geometry Monte Carlo catches an unconditional error in `pref`;
  only a restraints-plus-c_w fixture catches a leak conditioned on the model.
- **A pattern reader may repair a file only where it can say that it did** (WP-1047).
  `read_pattern(..., diagnostics=[])` is `structure_from_cif`'s channel one layer down; four
  consequences reach a caller outside `io/`. (1) A multi-range file's ranges are **scans selected
  by `scan=`, never concatenated** (GSAS-II concatenates, mixing two weighting regimes). (2) A
  reader raises `ValueError`/`OSError` **naming the file**, never its parser's exception. (3)
  **Intensities and σ need not be the file's numbers** — an attenuator is applied or not by
  *measured* vendor convention (four formats, three answers), σ goes through it either way, and
  an unestablishable scale **withholds** σ (`PATTERN_INTENSITY_SCALED`; the fallback is wrong by
  √t on a rate). (4) The scanned **axis** is never trusted — most vendor files are not powder
  scans, so a non-2θ one is refused by name and an unknown one says so. Dispatch, repairs,
  options, how to add a format: `src/rietx/io/CLAUDE.md`.
- **Every weighted residual in the package divides by `RefinementResult.sig()`** — every renderer
  and both GUI windows — a peer of `PatternData.sig()`, where the esd-column/Poisson choice was
  already made: `CompiledModel` stores `pattern.sig()` — widened once at compile by a measured
  background's own counting statistics, σ² + s²·σ_f², and by nothing else (WP-1309) — and `refine`
  copies it to `result.sigma` verbatim, so a result's σ is a *lookup*, never a re-derivation
  (WP-1029). σ is therefore **a function of the declared scale**, so an Rwp column down a scan of
  scales ranks nothing until one σ is chosen for all of it (7.2 % of one arm's is weighting; 1309).
  **`weighted` is
  `DataRef.has_sigma`** (σ *measured*, not σ *present* — what `textdoc` renders as "σ from
  file"); `delta` is always Δ/σ, because Δ/σ is what the fit minimised either way, and the flag
  changes only the axis title. A test that recomputes a residual cannot catch this class of bug:
  the pin compares what each renderer **drew** against what the route **sent**.
- **Background flexibility is a correctness question, not a cosmetic one.** A background able to
  imitate the peaks biases ADPs up and scales (hence QPA fractions) down while Rwp *improves*.
  Measure it **once**, as the block projection R² of a structural Jacobian column onto the
  background column span (`optimize.statistics.background_absorption`; pairwise ρ misses it), and
  carry the whole table to `FitReport.background` — whose other half, a too-stiff background,
  Layer 0's peak-cluster regions are blind to (WP-1055). **The screen's targets are anchored at
  `phases.`, never on a `.scale` suffix**: a background parameter is *in* the span it would be
  projected onto, so a free measured-background scale scored R² = 1.00 about itself and fired the
  guard on every fit until WP-1309. `optimize.statistics._structural_targets` is the one list both
  screens read. **A penalty's λ is weighed against the data's, never in intensity units**
  (√(λ·m)/σ̄, frozen at compile): the too-stiff side has no guard; a unit moved Biso 28 % (WP-1454).
- **Reciprocal-space symmetry action is Rᵀ** (transposed rotation) — matters for non-cubic
  orbit/multiplicity counting (`symmetry.py` comment). **This is about hkl; applying it to a
  *tensor* is the opposite mistake**: a quantity contracting with h twice (G\*, or the U\* form of
  an ADP) is invariant under U → R·U·Rᵀ with R **untransposed**, since (Rᵀh)ᵀU(Rᵀh) = hᵀ(RURᵀ)h.
  So `wyckoff.adp_basis` takes untransposed rotations for a metric or an ADP basis. The trap: the
  transposed set is a group too, so the invariant subspace's *dimension* is identical in every
  crystal system and a degrees-of-freedom test passes — WP-1020 built the whole indexing metric
  subspace from Rᵀ and satisfied its own 1/2/2/2/3/4/6 criterion. Only asserting that the true
  metric lies in the span catches it.
- **Cell ties follow the space-group *setting*, never the crystal system** —
  `crystallography.symmetry.cell_constraints(sg)` is the one authority, `ParameterTable` its only
  caller. Three settings disagree with the system alone: monoclinic has three unique-axis choices
  (`monoclinic_unique_axis()`); an R lattice on **rhombohedral** axes (`sg.ext == "R"`) needs
  a = b = c with α = β = γ free, not `b ← a` with c free; the `:1`/`:2` extensions are origin
  choices leaving the metric alone. **`read_small_structure` picks the R setting from the cell**,
  so a bare `R -3 c` over a rhombohedral cell arrives as `:R` — no non-standard symbol needed.
  This is the Rᵀ trap one rank down, failing the same way: the free-parameter *count* is right in
  every broken case (2 for both R settings, 4 for all three monoclinic ones), so assert **which**
  angle is held and **which** length follows which, never how many — 79 of gemmi's 564 settings
  were served wrong under a correct count. A symmetry-fixed angle disagreeing with its symmetry is
  **refused**, not normalised: the table has no diagnostics channel, so the correction could not be
  made visible, and the value is held as stored.
- **A silent correction is a reader's to make, never a table's — and only where the deviation is a
  *report* rather than a contradiction.** The rule above fixes *where*: `ParameterTable` has no
  diagnostics channel, `structure_from_cif` does, so a stranger's file is repaired at read with
  the substitution recorded as a `Diagnostic` (species `CIF_SPECIES_NORMALISED`, cell angle
  `CIF_CELL_ANGLE_CORRECTED`) while both lookups and the table stay strict. *Whether* is decided
  by magnitude, because the reader cannot see intent: up to `cif.CIF_ANGLE_CORRECT_MAX_DEG` a
  fixed angle is an experimenter quoting a refined value (β = 90.002(3) under `P m m m`) and
  snapping costs ≤ 830 ppm in d; past it symbol and angle contradict each other (β = 93.2 under an
  orthorhombic symbol), one of the two is wrong, and choosing is the caller's — so the value is
  left byte-for-byte and still raises (WP-1028).
- **A softplus `min=0.0` is safe wherever zero is the *off state*, and a bug wherever the physics
  divides.** `internal_bounds` maps any lower bound ≤ 1e-12 to −∞, and `log(1+e^u)` underflows to
  exactly 0.0 below u ≈ −745, so "strictly positive" is a promise the transform does not keep.
  Thirteen of the fourteen parameters declaring it are fine (a zero width is no broadening,
  extinction 0 is E ≡ 1) because their identity *is* zero; `PreferredOrientation.r`'s identity is
  interior (r = 1) with a pole at the bound, and it fed the solver NaNs for a whole budget without
  raising. So the pattern to check on a new parameter is not "softplus with min=0" but "softplus
  with min=0 **and** a pole at zero", which needs a real floor (`MARCH_R_MIN`) plus a validator,
  because a stored `min: 0.0` outlives the default.
- **Every physics function cites its reference** (author, year, journal) in the docstring, and
  documents conventions by physics not letters (e.g. size↔1/cosθ, strain↔tanθ; GSAS and FullProf
  swap X/Y labels).
- **The FitReport must never return a confident wrong singleton.** Every Layer-1 statement passes
  four gates: resolvability on the *scale-normalised* Gram, 0.4·FWHM validity radius,
  local-χ²_red significance, share-based global maturity. Collinear angular templates are compared
  as *nested single fits* and reported non-separable. Confidence weights importance (share of χ²),
  not just statistical significance.
- **A new correction ships with a record field or a diagnostic stating what it changed — never an
  Rwp comparison as its evidence.** Of v0.5's eight corrections, two provably cannot move Rwp, one
  moves it the wrong way when it is right, and the two largest accuracy wins are invisible in it
  (`docs/milestones/v0.5.md`). **Nor an R_Bragg comparison** (WP-1069): I(obs) is I(calc) times
  the reflection's own obs/calc count ratio, so it flatters whatever model partitioned it.
- **Licensing**: port code only from permissive sources, with ATTRIBUTION.md updates.
  BGMN/Profex/xrayutilities are GPL — concepts only, never code. TOPAS/FullProf are closed —
  papers only. ChimeraX's source is never opened, only its user docs (WP-1537, 1538). **Data carries its own fence, per file**: a PyPI upload publishes harder than a
  repository does, so a file entering the *wheel* (`src/rietx/data/`) states its status where it
  ships — `qarr/*.prn` have none, which is why the four round-robin standards cannot be example
  projects however small (WP-1204). **A private corpus is cited by number, never by name**
  (2026-09-18 audit): nothing lacking a peer-reviewed citation is public, so TOPAS's and FullProf's
  corpora are `archive file N`/`corpus file N`, private `yue-here/rietx-corpus-map` holds the map,
  and a fixture carries synthetic numbers at the file's own column widths. A public teaching
  download keeps its name; a physics citation keeps its measurement and drops only the specimen.

## Conventions

- **Never spell the distribution name, a format token or the state dir — import it from
  `_about.py`** (WP-1062; 1066 renamed the brand again, format tokens unmoved): its docstring says
  which is which, and why no test can enforce it.
- **What a name *is* is written in `src/rietx/help.py` and nowhere else** (WP-1202) — parameters,
  peak flags, stage fields, reader options, instrument preset fields, with unit, default and
  typical range. Every arm is crossed against its live vocabulary **both ways**, so a new member
  fails `tests/test_help.py` and a rename cannot leave an entry describing a name that is gone.
  `unit`/`default` are the schema's own through `UNIT_DISPLAY`; `typical` and `label` (the short
  words a chip carries, WP-1209) are the only authored fields. A `ParameterRow` carries
  `help_key`, the family glob, never the entry: an entry describes a *family*, so inlining one
  repeats a paragraph once per atom (3.4× the `/api/params` payload).
  `docs/manual/using/glossary.md` is generated from it in `conf.py`, and every `anchor` is checked
  against the built HTML, not the sources. **A family has a second consumer and only node sees
  it**: `gui/src/lib/history.ts`'s `PLACES` declares a print format per family and its vitest holds
  the table equal to the live vocabulary (`gui/CLAUDE.md`), so adding one means
  `npm --prefix gui test` and a rebuilt dist (WP-1309).
- Parameter paths are dot-separated, glob-matched with fnmatch in stage plans
  (`"phases.*.cell.*"`). No brackets in paths (fnmatch treats `[..]` as a class).
- Schemas: `extra="forbid"`, `ser_json_inf_nan="strings"` (±inf bounds must survive JSON
  round-trip — tested).
- Angles in degrees throughout; Caglioti U,V,W in deg²(2θ); Biso in Å² (= 8π²·Uiso); wavelengths
  in Å; s = sinθ/λ = 1/(2d).
- **sinθ/λ is `s` in maths and `stol` in python** (WP-1436). Neither half is a style choice. `s`
  is the paper's letter and the IUCr core dictionary's normative one, while `s` as an identifier
  is already taken in `structure_factor.d_f2_d_uaniso`, so python follows cctbx. It was `k` until
  v1.4, copied from the DABAX file's editorial preamble rather than from the paper that file
  reproduces. `k` is the wavevector to every reader outside the package, and the propagation
  vector to the magnetic track landing inside `crystallography/`.
- **Hot-path code must not put a frozen numpy constant on the left of a python operator against a
  θ-derived value**: `ndarray * tensor` raises on the torch backend, and `tensor * ndarray` routes
  through numpy's deprecated `__array_wrap__`, then fails under a functorch transform. Route it
  through `xp.matmul` or lift it with `xp.asarray(c, dtype=np.float64)`; both are no-ops on numpy.
  Same rule for a *new op*: add it to `_OP_NAMES` and implement it on every backend —
  `tests/test_backend_conformance.py` fails, for every registered backend at once, if you don't.
- **An additive non-Bragg term is a *member* of `Instrument.extra_components`, never a new field**
  (WP-1102 — GSAS-II, FullProf and TOPAS each ship several kinds at once). The union discriminates
  on `kind`; its docstring carries the six-clause member contract, whose last clause — **state,
  never code** — admits an **expression** member (text serializes, traces, and is a legal `str`
  under `extra="forbid"`; Coelho 2018) and fences a **callable**. A member's aggregate membership
  is **data**, never read off the class name — two members now, so that axis is *tested* and
  **evaluator shape** is the one still untested (a Debye term proves it). WP-1103's cost was not
  its evaluator: seven counts, claims and builders were right only while the union had one kind
  (`n_extra_components`, a CIF description, a reopened result, an analytic branch's declared reach,
  two of three absorption statistics, **one of the two tick builders**), none red because every
  test until then declared one kind. **A third member audits every reader of the list before
  writing an evaluator**; a second builder of anything (`multi.py` keeps its own) is the miss.
- **A renamed dot-path is migrated on the document *text*, at the read points** (WP-1102,
  `schemas/migrate.py`, `READ_POINTS`). A stored **value** under a vanished name fails loudly; a
  stored **glob** loads clean and frees nothing — that asymmetry is why the repair is textual and
  anchored on the bare name (`.rxt` strips the block prefix, so `instrument.` is not in the row).
- **A live view is numbers a viewer draws, never a page the fit builds** (WP-1402).
  `viz/snapshot.py` writes `snapshot.json` per stage and imports no plotting library, so a
  base install can record one; `viz/live.py` is a shim over it and `rietx watch` draws it
  with the chart module every browser chart shares (`viz/static/rxplot.mjs` over a vendored
  uPlot, WP-1461), redrawing in place so the zoom survives a stage. The page it replaced cost
  the fit's thread 4.51-6.03 MB a stage; `rietx html` writes one on demand, module inlined.
- **A display reads fields and never computes; a designed view is a `__str__` override** (WP-1544;
  the three rules and the figure rule are `_display.py`'s docstring and `viz.plots._pyplot`'s).
- **A per-stage charge is judged on the shortest fit, never the typical one** (WP-1413): it is
  near-constant, so `nac` at 0.354 s spends 50 ms on six snapshots against a 17.7 ms budget.
  **That one is paid** (WP-1438): a ratio is the wrong test where the absolute charge is 50 ms,
  and thinning would cost the live view its redraws on the fits somebody is watching. A
  throttle, if the number ever moves, is by time and never by count.
- **Every fit records itself, and telemetry never breaks a fit** (WP-1403). `runs.py` holds
  both halves of one contract: the reader `rietx watch` is built on, and `RunRecorder`, which
  writes the `meta.json`/`run.lock`/`status.json` it looks for. `runs.attach` hangs the
  recorder *beside* a caller's stream, never inside it, so `fit`'s `stream is not events`
  close rule is untouched, and **once per job, through the `_inner` chain** — a series hands
  each pattern a fresh `_SeriesStream`, so a stamp read off the object handed in makes sixty
  directories for one job. **The failure boundary is who asked**: a callback reached through
  `events=` is the caller's and runs outside every try block, while the recorder was attached
  unasked, so its every method latches one-shot on `BaseException`, records why in
  `status.json` and warns once a process (`KeyboardInterrupt` re-raises — that is the person
  at the keyboard). `events.py`'s "a monitoring hook that crashes the refinement is a bug you
  want to see" is the same rule from the other side; both halves are written down, or someone
  reconciles them the wrong way. Two corollaries: **whatever a recorder needs before it exists
  is outside its own latch** (a root and a directory are `attach`'s, and an unguarded
  `PermissionError` there took a whole fit down); and the status is a **projection**, its
  stage read off `stage_start.index` and never counted, since a released phase emits a second
  `stage_start` (WP-1301) and a counter then says "stage 6 of 5". (4) **An internal trial
  passes `telemetry=False`**: a fit whose result the *package* discards is not a run — a
  suggestion's verify stage, a rival fit, an extinction screen, a Le Bail validation — while
  one whose result a *caller* reads is, so `viz/compare.py` records and `report/layer2.py`
  does not. Un-gated, one report build wrote four run directories. The suite declines
  recording (`conftest`, `RIETX_TELEMETRY=0`), and `test_telemetry.py` owns the meta-test
  that a plain `fit()` under it writes nothing.
- **Retention deletes by age and size, never by count** (WP-1403). "Keep the newest N" would
  delete run 1 of a 200-candidate batch while the batch was still running. So: a byte ceiling,
  a week's floor, oldest terminal run first, and over the ceiling with nothing old enough
  **warns and keeps**, because using someone's disk beats deleting their evidence. Three
  guards before any `rmtree`, two re-asked at the call rather than trusted from the scan: a
  run-id name, a direct child of the root the recorder itself chose, and a `meta.json`
  carrying `RECORD_TAG` — which a legacy directory has not got, and so is never pruned.
- **The reader has two verbs and neither touches the project a fit is writing** (WP-1405
  stop, WP-1428 GUI). Stop writes into the *run* directory; the GUI verb spawns
  `rietx gui --scratch` on a **copy**, there being no read-only way to open a project, and
  `--read-only` clears both. **Which project a run is in is `runs.project_of`** — two live
  layouts, `<name>.rex/live/<run id>` and `<name>.rex/live` itself, and three readers had
  open-coded one each until one offered a GUI command `None` for every recorded run.
- **Stop's seam**: `runs.CANCEL_FILE` is the whole cross-process seam, a **request rather than a
  flag**: an unknown word in it is declined into `RunStatus.declined`, because an old recorder
  meeting a newer watcher's `pause` must not stop the fit. The probe hangs on the **unthinned
  evaluation boundary**, through the token the solver already reads, since the recorder gets
  control only at an event and WP-1404's thinning would leave it firing once a *stage*. A recorded
  fit therefore always carries a token, ending `_abandon_on_cancel`'s "an ordinary fit pays
  nothing" (1.002-1.004×, measured before it was spent; that docstring holds the numbers). **Who
  asked is a fact about the record** (`RunStatus.cancelled_by`) and never about the exception —
  downstream, a human's stop and the caller's own `token.cancel()` are one cooperative read.
- **A poll asks for what the reader can hold, and a row carrying a clock can never be
  told it has not changed** (WP-1427). Two rules from measuring one page. The console is a
  tail over a pane of `MAX_LINES`, so the **page** names that cap on the route (`limit`) and
  `runs.tail_events` drops the oldest of the slice *before parsing* — uncapped, opening a run
  whose log already held 60 000 events built that many `<div>`s to keep 2000, 997 ms of
  frozen main thread and three long tasks. And `/api/runs` carries an `ETag`, which could
  never have matched while every row carried `liveness.heartbeat_age` = `now - heartbeat`: a
  field computed from the clock makes every idle answer a different one, and nothing read it
  (WP-1076's rule from the reader's side). Behind both, the walk is cached per run on the
  files a row reflects (`read_run(cache=)`), 1.7× at 200 runs and at the 500 of `MAX_RUNS`.
  **What the numbers dismissed stays in the WP**, and two of them are the reflex: gzip on the
  snapshot loses by 27× against a 3365 MB/s loopback, and SSE moves the walk into a thread
  rather than removing it, the stdlib having no file watcher.
- **A page that is javascript is a *file*: `node --check`ed, its DOM-free half run by `node
  --test`** (WP-1430 `watch/static/`, WP-1461 `compare_app/static/`, each with a `*_core`
  case file in `tests/`, out of the wheel). Quoted inside python it is unlinted and
  unimportable, and one stray escape cost a page while every test stayed green (WP-1402).
  `.mjs`, since `node --check` reads a `.js` as CommonJS. A page directory takes its own `!`
  line in `.gitignore`, whose `*.html` has swallowed eight committed files. **No file check
  sees layout** (WP-1405): an id selector outranks `[hidden] {display:none}`, so a closed
  dialog was a sheet swallowing every click — `test_watch_browser.py` drives chromium. **Nor a
  cut** (WP-1424): a `table-layout:fixed` column's declared width is the cell's whole *box*,
  so one sized for its content is short by its padding and elides, and an ellipsis is what
  fitting and not fitting look the same amount of. Measure ink against room, never
  `scrollWidth`, which is `clientWidth` wherever overflow is visible.
- **A pane that cannot meet its floor beside its neighbour stacks, and the breakpoint is the
  stylesheet's** (WP-1438). `rietx watch` gave the list its declared `80ch` and the run pane
  whatever was left, which at 420 px was nothing and 863 px of horizontal document scroll. The
  width where side by side stops being *possible* is computable from the floors already
  declared — the list's 71ch, the 340 px of picture the run pane keeps, the grip — so it is
  measured, not chosen. It lives once, as a `--stacked` custom property a media query sets, and
  the page asks whether it is met; spelled twice it is two layouts disagreeing about which one
  the page is in. A seam that turns keeps a **size per arrangement**: a px width is not a px
  height, and one number hands the reader a pane they never asked for. A table sheds the
  columns the page answers elsewhere before it sheds the one the row is *for*, by zeroing the
  `<col>` — never `display:none` on the cells, which shifts every later cell a place left into
  the colgroup, and never `visibility:collapse`, which took the flexible column with it (both
  measured).
- **Three browser surfaces, one set of colour values, and they are Python** (WP-1429,
  `viz/theme.py`). The GUI, `rietx watch` and `rietx compare` each answered "which colour is
  the calculated curve" for itself, on two different darks. The values cannot live in
  `gui/src`, which is a build input the wheel does not ship, so the module owns them, the two
  Python servers render a `/tokens.css` route, `gui/src/tokens.css` is **generated and
  committed** and a test holds it equal to the emitter. A page's extra roles — a hover, a
  focus ring, a state pill — are `color-mix` over the nine chrome tokens, never a token of
  their own: one the GUI never reads is a declared name with no writer. The **theme** has one
  home and every page that shows it may set it (`state_dir/settings.json`, through
  `theme.theme_choice`/`set_theme_choice`; WP-1438 widened 1429's GUI-only writer, which left
  the choice unreachable for a fit driven from a script and watched in a browser). A change
  reaches an open watcher on the poll it already makes and an open GUI on its next load. The
  glyphs and titles are the module's too, `App.svelte` held equal to it by meta-test. The
  **figure** palette (`viz/plots.PALETTES`) is not in this story and stays where it is.
- **Two things are written once and consumed everywhere; never restate either.** (1) The residual
  **row layout** `[data | background-penalty | Pawley-restraint | soft-restraint]` lives in
  `model/rows.py` (`BLOCK_ORDER`, `layout()`, `assemble()`) — the numpy residual, the numpy
  Jacobian's row offsets and every traced residual build from it, so a new block is one edit. (2)
  The **traced twin** of `decode`/residual lives in `backend/traced.py`, parameterised by `xp`;
  jax and torch share it and a new backend inherits it. Adding a backend = a name in
  `backend.api.BACKEND_NAMES` + a row in `test_cross_backend.METHODS`; the conformance suite's
  meta-test fails if you do the first without the second.
- **Two functions build Ω, 1-2 ulp apart on purpose, and each caller owns which one it
  reproduces**: the residual `_profile`, and the derivative bases `_profile_basis` (the derivative
  form without the partials, so the bases cannot shift under a caller's choice of partials). Code
  batching, compiling or reusing one path for the other passes the spelling **in**
  (`_omega_batch`'s `spell`, `compiled.SPELL_*`) rather than sharing the build — lifting the wrong
  one moves every converged fit for nothing (WP-1120). The whole difference is one association,
  `-4ln2·(x/Γ)²` against `((-4ln2)·u)·u`; the Lorentzian is common to both, because multiplying by
  a power of two is exact. So the numpy forward is batched while the
  per-reflection loop stays as `_phase_component_scalar`: the traced backends' path *and* the
  oracle every batched claim is measured against. The phase sum scatters **once per phase** —
  addition is not associative, so one bincount across all phases regroups each shared point into a
  different double; a guard for that builds the regrouped variant, never reverses the phase order,
  which passes whatever the code does.
- **The numpy path has a compiled tier and it is what a default install runs** (WP-1115, WP-1940;
  `model/compiled.py` owns the tier, the `rietx-kernels` crate in `kernels/` the arithmetic). *Not*
  a fourth backend: jax and torch keep the traced twin, and nothing above `compile_model` may branch
  on whether the kernels ran. Four rules. (1) The **fallback is mandatory and must stay exercised**.
  The wheel is a hard dependency with no markers and no sdist, so pip fails where none exists; the
  import is still soft, every entry point declines rather than raising, a decline warns once and
  reaches `capabilities()`, and `RIETX_COMPILED=0` / `compiled.set_enabled` is the switch the
  goldens and `test_compiled_kernels.py` run the numpy side through. (2) A **new kernel is a serial
  loop over a row range that releases the GIL**, on the shared pool and split on estimated work; it
  ships as a minor wheel release that raises rietx's floor (`compiled.KERNEL_ABI` is the major).
  (3) Its **equivalence bar is per kernel, stated and asserted**: no library call in it means the
  bit, an `exp` in it means 1e-13 relative, and the numpy builder stays the bit-identity oracle
  against `_phase_component_scalar`. (4) **One path per process**, never decided per call.
- **Traced code runs inside `backend.traced.active(xp)`** — it makes `xp` the globally-bound
  backend *and* opens the backend's `full_precision()` scope. jax's fp64 is scoped, so a constant
  (or a θ vector) materialised outside it is silently float32 (it once cost the Pawley aux columns
  four orders of accuracy), which is why constants are lifted inside the traced call, not at
  closure build.
- **Specimen absorption is one seam, three geometries, and their "off" states disagree**
  (`model/absorption.py`, `CompiledModel._absorption`). Capillary: `Geometry.mu_r`, Rouse (1970),
  off at µR = 0, and *exactly* a reparameterisation of {scale, Biso} — Rwp provably cannot move,
  the whole content is ΔB = c(µR)·λ²/2 (measured on 11-BM SRM 660a to the predicted digit;
  ROADMAP's v0.5 row). Flat plate: `Geometry.mu_t`, ITC Table 6.3.3.1 case (2) under
  `bragg_brentano`, case (3a) under `flat_plate_transmission`, **off at µt = ∞** (thick specimen,
  ITC (1a)) — so `mu_t` absent ≠ `mu_t = 0`, a specimen of no thickness, which raises. It is *not*
  an exact reparameterisation (1-40 % of ln A survives the projection), so it moves Rwp, its ΔBiso
  is an order of magnitude larger and negative, and on a genuinely thick specimen declaring a
  thickness correctly makes the fit worse. Neither µR nor µt is refinable: µR is exactly singular,
  µt merely ill-conditioned and knowable from the specimen.
- **Instrument ⊕ sample profile split**: Gaussian *variances* add (instrument U,V,W + phase
  `gauss_size`/`gauss_strain`), Lorentzian *FWHMs* add (instrument X,Y + phase
  `lor_size`/`lor_strain`). Workflow: `lab_calibrate` on a standard with its **certified cell held
  fixed** (that is what decorrelates zero/displacement/cell) → `save_instrument_profile` →
  `load_instrument_profile` (everything `vary=False`) → `lab_sample_refine`.
- Atomic coordinates refine as site-symmetry DOFs: `ParameterTable` wires
  `phases.i.atoms.j.dof.k` (one per allowed direction from `crystallography/wyckoff.py`) and
  affine-ties x/y/z to them; free them with the `phases.*.atoms.*.dof.*` glob (the
  `mccusker_structural` plan does). Fully fixed special positions get locked coords — `vary=True`
  there raises. **A coordinate DOF is *relative*, so the invariant is that a rebuild reproduces
  the coordinate** (WP-1432): the row is x = x_stored + Σ Bₖθₖ with the DOF rederived to zero, so
  a tie onto one from a source that does not reset (a named variable) anchored on a coordinate
  that had already absorbed the displacement and added it again per build, silently.
  `ParameterTable.rebase_anchored_dofs` takes it back out; **which entries are anchored is data
  built where the anchor is**, never a name read at a call site (ADP and Stephens DOFs spell theirs
  the same way and are absolute). `_apply_ties` and `replay` call it, so **a third consumer of
  `_ties` calls it too**. **The DOF's *value* is a step from where its fit began** (WP-1333): a
  chain carries the coordinate as a displacement, so any judgement across fits (the fences, the
  GUI's disagreement column) skips `anchored_dof_paths` and reads the coordinate rows.
- **Anisotropic ADPs are opt-in per atom** (`Atom.aniso`, CIF U^ij in Å²), refining the same way:
  `phases.i.atoms.j.adp.k` patterns from `wyckoff.adp_basis`, freed by the
  `phases.*.atoms.*.adp.*` glob every displacement stage carries alongside `…biso`. Unlike
  coordinate DOFs they are **absolute** (U = Σₖ θₖ·Bₖ), enforcing the site symmetry exactly; a
  tensor outside the allowed subspace raises rather than being symmetrised. Three representations,
  all named in `crystallography/adp.py`: the stored CIF **U^ij**; the fractional-space **U\*** =
  U^ij·a\*ᵢa\*ⱼ that the structure factor uses (U\* is what transforms as R·U·Rᵀ, making `Rᵀh` on
  the parent *identically* the image's tensor); **U_cart**, where eigenvalues and U_eq are
  physical. Isotropic limit: U^ij = Uiso·G\*ᵢⱼ/(a\*ᵢa\*ⱼ), **not** Uiso·δᵢⱼ except for orthogonal
  reciprocal axes. Non-positive-definite tensors raise `ADP_NOT_POSITIVE_DEFINITE` (the
  Debye-Waller factor diverges at high Q — not cosmetic); the constraint couples all six
  components, so it cannot be a bound. `structure_from_cif(..., aniso=True)` is opt-in: several
  test CIFs carry aniso loops, and reading a file must not silently change what a plan frees.
- **Anisotropic strain is opt-in per phase** (`Phase.microstrain`, Stephens 1999), the first width
  depending on hkl rather than only on θ: σ²(M) = 10⁻¹²·Σ S_HKL h^H k^K l^L adds Λ(hkl)·tanθ to
  the *Lorentzian* FWHM. Same shape as the ADP story one rank up — the Laue-allowed S_HKL patterns
  are **derived** from the operators (`crystallography/stephens.py`, sharing
  `wyckoff._nullspace_int`), refine as absolute DOFs `phases.i.microstrain.dof.k`, and an
  out-of-subspace set raises. Three load-bearing conventions, stated in that module: √Σ·d²·10⁻⁶ is
  the **FWHM** (not σ) of the ΔM/M distribution; coefficients are in **10⁻¹² Å⁻⁴** (physical values
  ~10⁻⁸ would be finite-differenced with a step 100× their own size); they multiply the **literal**
  monomials, where other codes fold symmetry multiplicities in. A block **locks `lor_strain`** (its
  isotropic direction is identically that column), so the block subsumes it and must itself be
  freed *in* the sample-broadening stage, not after. The isotropic limit S = ε²·[M²] is both the
  seed and the only legal start: at S ≡ 0 the √ has unbounded slope, so `Stage.strain_seed`, not
  `Stage.seed`, which reaches softplus
  entries only. σ²(M) ≥ 0 is a *cone* coupling all fifteen, so it cannot be a box bound: under the
  default TRF driver it is a guard (`STEPHENS_STRAIN_NOT_POSITIVE`); under `solver="lm"` (WP-0601)
  it is a linear inequality and the guard falls silent. Read a firing as "these coefficients are
  not quotable", never as evidence *of* anisotropy. **Zero is on the cone, not outside it** — the
  guard's test is one-sided; v0.6's record has the ≤ 0 form's withdrawn claim and the re-measured
  brucite and corundum cone counts.
- **Anomalous scattering is ON by default since v1.0** (`Source.dispersion`, f = f₀ + f′ + i·f″
  from bundled Cromer-Liberman `data/f1f2_CromerLiberman.dat`). The load-bearing part is *not* that
  f goes complex — F always was — but that `generate_reflections` merges ±h into one Laue orbit and
  evaluates a single representative, exact only while f is real: with f″ ≠ 0 in a
  non-centrosymmetric group |F(h)|² ≠ |F(−h)|², and both land in the *same* powder peak. So
  `structure_factors_squared` returns the **Friedel average** ⟨|F|²⟩ = |A|² + |B|² over the *same*
  orbit sums (A: f₀+f′, B: f″); B ≡ 0 recovers |F|² bit-identically, which constrains the fp
  *association order* in `_orbit_terms`. f′/f″ are frozen at stage compile onto
  `PhaseSites.f_anom` — species and λ only, and λ is frozen per stage (WP-1134) — so they can never
  be a function of θ. One |F|² is shared across emission lines, *guarded* rather than smeared:
  `dispersion.resolve` raises when a line differs from the primary by more than 1 % of Z, and an
  edge inside the range is refused too, `Dispersion.overrides` taking measured pairs. It is the
  **only** correction needing no information the caller lacks (species and λ suffice), which is why
  WP-1001 made it the default; `dispersion = None` declines it, reproduces every ≤ v0.6 number
  bit-identically, and says so through `DISPERSION_NEGLECTED`. **Every test that pins a number
  declares this setting explicitly rather than inheriting it** — a suite whose numbers move when a
  default moves is not pinning a protocol (`tests/test_validation_matrix.py` enforces it for the
  acceptance suites). Ions resolve to the element (core-level effect), unlike ionic f₀.
- History nodes store **state, not curves** (~10 kB a node; embedding y_calc → ~1.24 MB). Cached
  metrics are *as-optimised*, measured on a model frozen at the values each stage *started* from,
  so `refine.replay` — recompiling at the values the stage *ended* on — can differ marginally: a
  staleness signal, not a bug. Le Bail extracted intensities live outside θ and are path-dependent,
  so they are serialized per node (`ReflectionState`); Pawley will reuse that container rather than
  adding one dot-path per reflection to `free_paths`.
- Emission-line weights are relative to line 0, structurally locked at 1 (degenerate with phase
  scales); `set_vary` globs can never free locked entries (this also protects symmetry-fixed cell
  angles).
- `RefinementResult.ticks` carries **every emission line's** positions, not just the primary —
  otherwise Layer 0 flags each Kα2 peak as an unindexed impurity (a real bug, caught by the
  misfit-injection suite). **Which reflection each tick is rides beside it, built where the
  positions are** (WP-1438): `tick_hkl` and `stage_ticks`' `hkl` are pinned to their positions by
  index and carried through the same filter, sort and cap, because a second derivation of the
  pairing could come apart with nothing able to say which half was lying. `ticks` keeps its shape
  — four readers want a list of positions and none of them wants this. Two reflections land at the
  same 2θ to every decimal, so a **position is not a key**: pair by index or not at all.
- Tests, timing, budgets, CI, and what each key dataset can prove: `tests/CLAUDE.md` (loads under
  `tests/`; provenance and every reference value in `tests/data/README.md`); headline rules in
  Commands above.
- Comparing against another code means **adopting its protocol**, not just its numbers: mirror its
  refine flags, held parameters and excluded regions, then check the channel count matches before
  believing any Rwp comparison. **Two references are an envelope, not a second tolerance**
  (WP-1306): two engines' answers in one fixture may disagree by more than any bar worth setting
  (2665 ppm on a cell against the FAP suite's ±300), and agreement with both is then
  arithmetically impossible, so the gate is the span they bracket and the spread itself is
  reported. **A foreign format's unit is measured against that format's own reference output, never
  adopted from its prose**, and a row the format states two ways is **refused** rather than chosen,
  exactly as a CIF whose angle contradicts its symbol is.
- The **manual** (`docs/manual/`) is one `-W` Sphinx tree in two parts, guarded differently because
  each fails differently. **Part 2 — Theory** (`tests/test_manual.py`): fenced constants are MyST
  substitutions injected from the live package in `conf.py`, every displayed equation carries a
  `*Source:*` line whose symbol must import, every bib entry is cited — so renaming a physics
  symbol or retuning a fenced constant means touching the manual in the same change, and **a WP
  that adds physics adds its equation there**, never only Part 1 prose (WP-1067). **Part 1 — Using
  rietx** (`docs/manual/using/`, `tests/test_manual_api.py`): its failure mode is a *name*, so
  every dotted
  name and dot-path must resolve, every python block parses and either executes or carries a
  written reason, and the public call surface is partitioned into documented /
  excluded-with-a-reason / generated-deferred. That surface is **derived**
  (`tests/api_surface.py`'s docstring has the rules), never listed, so **adding a public method or
  field fails the partition until documented or deferred** — a coverage gate, not a freeze
  (WP-1117). Under-development subsystems declare themselves (1078): `PROVISIONAL_MODULES` keys a
  module prefix to a reason and the tier derives from each name's **defining** module, so a new
  type inherits it and a re-export is reached; indexing is the one entry, promised in
  `using/compatibility.md` § Provisional by declaration, `{ref}`d not restated. **A green build is
  not a rendered page**: `-W` cannot see a paragraph that printed its own TeX, so
  `test_no_unrendered_math_survives_the_build` scans the *built* HTML, and diagrams and themed
  figures are checked by looking. Part 1's figures are **committed** light/dark pairs from
  `docs/manual/make_figures.py` (the one authority for how each was drawn); agent-facing prose
  carries the `agent` admonition. **GUI chapters** (WP-1017) add a third guard, for routes and
  panels rather than importable names: `test_gui_manual.py` **partitions** both vocabularies and
  tightens each way, so adding or renaming a route or tab fails until a chapter covers it, and
  naming one the server does not serve fails too; screenshots from
  `docs/manual/make_screenshots.py`.
- **The site root is the landing page, and `docs/landing/README.md` is its rulebook**
  (WP-1331). Two consequences reach a session that never opens that directory. `/` is the
  page and the manual is `/manual.html` — sphinx's `root_doc` is `manual.md`, so a link
  meaning "the manual" is never the site root. And `conf.py` copies the page in through
  `html_extra_path` **only if `docs/landing/site` exists** (`-W` makes a missing entry an
  error, and the suite builds the manual on every run), so the build output holds pages
  Sphinx never rendered and a guard walking it must exclude them, not widen itself.
- **A walkthrough has one authority, and it is `examples/`.** The manual `{literalinclude}`s those
  scripts and `tests/test_examples.py` runs them, so a worked example is code that ran. Never write
  a third copy. The tutorial notebooks are a generated projection of `examples/tutorials/NN_*.py`
  (`build.py` there; edit the script, never the `.ipynb`), executed by `tests/test_tutorials.py`.

## Roadmap & how to work on it

Planning docs are split so a session loads only what it needs; do not read all:

- `docs/ROADMAP.md` — session protocol, a "Current focus" capped by `CURRENT_FOCUS_CAP`, milestones, and
  each WP section's prose. The WP index is `docs/wp/README.md`, **generated** (`wp_index.py`, WP-1507).
- `docs/wp/NNNN-*.md` — one **self-contained** WP per task (context, commit-sized checklist,
  acceptance command, handover log); its header lines are what the index reads, never hand-copied.
- `docs/DESIGN.md` — design record; read only the section a WP links.
- `docs/milestones/vX.Y.md` — one record per release: the measured ship block, plus (while in
  flight) the running "How vX.Y is getting here" narrative; `<name>.md` holds a named milestone's
  scope and acceptance (WP-1540). `v1.6.md` is the live one.
- The **paper corpus** (location and unread list) is maintainer-local, outside this repo;
  `AGENTS.md` names the split and the maintainer's memory holds it. **Search it before asking for a
  paper or re-deriving a published constant.**
- `docs/skill/rietx/` — the **agent skill** (agentskills.io), consumer-facing: `SKILL.md` the
  judgement core read whole, `references/` the lookups read on demand. **What a session learns has
  three destinations** (WP-1330): a rule an agent *driving* rietx needs goes in the skill, a rule for
  *changing* the package in a CLAUDE.md, a measurement in the WP handover. **Inside the skill a
  feature's guidance takes the cheapest place that holds it** (WP-1338): the package's own output
  (`Diagnostic.suggestion`, `help.py`), which no upgrade leaves stale; a reference row keyed by a name
  the agent already holds (a code, a verb, a suffix); a routing row only for a task *shape* no name
  identifies, one `references/` file per shape numbered under the body section it specialises (`9b`,
  `9c`) and citing it by §; the body last, for what **every** fit needs. **A shape's entry points
  render to a generated `api-<shape>.md`, never `api.md`**, which every session about to call rietx
  loads whole (`make_api_index.py`'s docstring). A reference written from runs tags every row
  `(Measured: …)` or `(Hypothesis: …)`. **Sizes are `tests/skill_caps.py`'s**: a ceiling per file and
  a budget below it that fails only growth, so concurrent PRs land in the gap; the body's budget is
  the spec's 5 000 tokens, so while over it a body sentence is paid for by a cut. A diagnostic code
  adds its row; `rietx skill --install . --copy` re-syncs the two committed copies; the recipe is
  `CONTRIBUTING.md` § The agent skill.
- `docs/RELEASING.md` — how a version reaches PyPI, and the one rule governing it: never
  `twine upload` by hand, because the workflow builds from the tag and a by-hand build cannot be
  held to it (measured on 1.0.1).
- `gui/`, `tests/`, `src/rietx/io/`, `src/rietx/indexing/` each hold a `CLAUDE.md`: subsystem
  rulebooks, loaded with their subtree, never restated.

**Protocol**: `docs/ROADMAP.md` § Session protocol is the one authority
(`tests/test_docs_consistency.py` enforces the mechanical parts). Three clauses to carry
everywhere: commit per checklist item prefixed `WP-NNNN:`; a CLAUDE.md takes **rules, not
findings**; and a session **ends by invoking `/wp-handover`, never by reproducing its
checklist** — writing the entry and opening the PR by hand skips the review and verify steps and
still reads as done, so `.claude/hooks/handover_owed.py` (Stop) holds one stop open when a WP
branch is clean and pushed and the command never ran.

**A session works in a worktree, never in the main checkout.** Concurrent sessions in one checkout
share its HEAD, index, stash and tree, so the first act of any session that will edit is
`EnterWorktree` (named after the WP; or `claude -w <name>` from the terminal) — the venv is built by
the `WorktreeCreate` hook — and `.claude/hooks/worktree_only.py` refuses an edit or a HEAD-moving
git verb in the main checkout. `/pr-review` enters its persistent bench the same way.

**And one WP per session** — the same rule one rank out, since two sessions in two proper trees
still duplicate a day and find out at handover (WP-1422). **A claim is held by a worktree, and a
worktree is live when a session sits in it**: every part is observable, so `.claude/hooks/wp_claim.py`
*derives* it from `git worktree list` and the live processes, and its store on the git common dir
only sharpens that where a tree is resumed for another WP. A claim dies with its worktree, pruned on
read — a stale one is the false alarm that teaches the reader to skip the line. `/wp-start` step 2
reads `wp_claim.py status` (**`dormant` is work to resume, `held` is taken**); `worktree_create.py`
is the workflow's **one refusal rather than a report**, because its trigger is a live process rather
than a leftover branch and git already refuses the narrower half of the same accident.

**A contributor is on another machine, so the second half of that answer is GitHub's.** No local
claim can see them, and the branch cannot either — measured 2026-09-15, all three open contributor
PRs were on **forks**, absent from `git ls-remote origin`, naming no WP in branch, title or body.
**They key on issues and so must this**: `wp_claim.py status` maps open PRs to WPs through the issue
numbers the WP files already cite (PR → issue → WP), which needs no new convention from anyone;
assignees are not a signal (0 of 78 open issues carried one). Two rules. **An issue link is evidence
of overlap, never proof of a clash** — one issue is cited by five WPs here — so this tier reports and
`EnterWorktree` never refuses on it. And it needs the network, so it lives in `/wp-start` and **never
in the SessionStart hook**, which stays stdlib-only, offline-safe and 0.25 s.

**An issue reaches the roadmap through `/issue-review`**, which tests each report against the tree
before placing it (a close, a comment, a fold into a WP's `### Inherited`, a new WP, a fence, a
milestone), docs-only, with every public act batched to the person. The `#N` a WP file cites is the
whole triage record: the command's table reads it, and so does `wp_claim.py` above.

Shipped: **v0.1 … v1.6**, one record each in `docs/milestones/`; ROADMAP's table carries the
acceptance one-liners, restated in neither place. Since WP-1117 the compatibility promise
(`docs/manual/using/compatibility.md`) is a **preview**: anything may change in any release,
versions bumping per observable change. **1.0.2 was written and never published**, folded into v1.1
(2026-08-23), so 1.0.1 is what anyone upgrades *from* and `docs/releases/1.0.2.md` describes a
release that never existed. **A milestone is named, a release is numbered at its cut** (WP-1540,
ROADMAP rule 6), so `pyproject.version` is the next release's `.dev0` except on the tree a tag is
cut from. Every `RefinementResult.provenance` and history node stamps it; it moves after each cut.

**Indexing.** Full dossier `src/rietx/indexing/CLAUDE.md` (auto-loads when a session works there);
measured stories in the v1.0 record's appendix. **A new indexing rule lands there; it earns a
clause here only if it changes behavior outside `indexing/`.** Three do:

- **Never a confident singleton**: `IndexingResult` has no `.cell`/`.best`, only a gated
  `best_or_none()`; `determine_extinction_symbol` returns ranked classes each carrying a *list* of
  space groups — the extinction symbol, not the space group, is what a powder measures.
- **`quick` is `index_pattern`'s default** (WP-1042): all engines, all requested systems under a
  whole-run ceiling, with progress and a graded shortlist streamed on the event ladder, so GUI, CLI
  and agent inherit a bounded, anytime first click. A caller's own `total_budget_seconds` is never
  overridden (the result records `preset="custom"`); `preset="full"` is the unbounded pre-1.0 run,
  and a test asserting a complete search declares it explicitly.
- **Run `tests/test_acceptance_indexing.py` before closing anything that touches an engine** — a
  real ranking regression once sat under 115 green fast indexing tests (WP-1030).

**Backends (v0.4).** `backend=` takes `"numpy"` (the default and the only one anyone needs),
`"jax"`, or the **experimental** `"torch"` (CPU fp64) / `"torch-mps"` (Apple GPU, necessarily fp32)
— never installed by default, kept as an independent opinion in the agreement matrix. Every backend
is held to per-column agreement with the analytic Jacobian in `tests/test_cross_backend.py` —
**whose configs must grow whenever a new derivative path does**, or no backend row covers it.
Apple-GPU execution is *slower* than numpy (46-182×, launch-latency-bound): `torch-mps` buys
precision validation, not speed (the v0.4 record). Also since v0.4: true Voigt (`shape="voigt"`,
TCHZ still the default), soft restraints, the Bérar-Lelann esd inflation. v2 fence: FPA, neutron
**TOF**, spherical-harmonics texture, MCP server — and the **peaks buffer with FPA**, never before:
shape reuse needs > 2.8-4.2 FCJ images a window point (WP-1122).

# WP-1012 — History worktree, report panel, one-click suggestions

Milestone: v1.0 · Status: ✅ 2026-07-30
Track: The human GUI
Depends on: WP-1010

## Goal

The differentiator no competitor has: a git-like history DAG panel
(checkout/branch/compare from the browser) plus the first interactive
FitReport view anywhere — typed suggestions carrying predicted Δχ² that
apply in one click, echo as API calls, land as history nodes, and are
undoable by checkout.

## Context

- History DAG panel: Rwp badges, head marker, tags; verbs already exist —
  `checkout` (`refine.py:182`), `branch` (`:202`), `merge` (`:250`),
  `cherry_pick` (`:309`) on `Refinement`; `annotate` (`history/tree.py:120`),
  `tag` (`:140`), and the two-node read-side `compare`
  (`history/tree.py:231`) / `diff` (`:249`) on `RefinementTree`. The panel
  is a view over `GET /api/history` + the POST verbs (WP-1008 routes); no
  new history semantics.
- Nodes store **state, not curves**, and their cached metrics are
  *as-optimised* — `replay` recompiles at the values the stage ended on and
  can differ marginally; that gap is a staleness signal, not a bug
  (CLAUDE.md). The panel must not present cached-vs-replayed deltas as
  regressions.
- Report panel: Layers 0–2 rendered from the pydantic `FitReport`
  (`report/schemas.py:331`); worst regions click-zoom the plot
  (`two_theta_range` is already on the report's region entries and on
  `SuggestedAction`).
- **`SuggestedAction` is already fully typed** (`report/schemas.py:296`):
  `kind` (closed `ActionKind` enum), `confidence`, `rationale`,
  `parameter_paths`, `expected_delta_chi2` (predicted, an optimistic upper
  bound — `predict_then_verify` in `report/layer2.py` measures the real one
  and rolls back), `alternatives`, `two_theta_range`, `vetoed_by`. **The
  strategy engine holds the veto** — a vetoed action renders greyed with
  `vetoed_by` as the reason, never hidden.
- `report/apply.py`: map each `ActionKind` to concrete session verbs
  (`set_vary` globs, plan edits, run_stage) — server-side, so the mapping is
  testable without a browser. `POST /api/report/apply` executes one action;
  every application is echoed as API calls in the console and recorded as
  history nodes, so undo is checkout.

### Inherited

From **WP-1011** (landed 2026-07-30) — the sidebar this panel plugs into now
exists, and three of its rules are not obvious:

- **The sidebar is a tab strip in `App.svelte`, and every tab stays mounted**
  (`.panel.hidden { display: none }`). Add `History` and `Report` as tabs; do
  *not* mount on demand, because switching tabs must not throw away a filter, a
  pending edit or an unsaved stage list. Adding a tab is one `<button>` and one
  wrapper div.
- **`head` is the one reload signal.** The head node *is* the working state
  (WP-1005), so panels take `head` as a prop and reload in an `$effect` keyed on
  it — that covers a run, a checkout and an edit made in another panel with one
  subscription. A checkout from this panel will therefore refresh the parameter
  table by itself, provided the state frame's `head` moves.
- **A `ResizeObserver` stub lives in `gui/src/test-setup.ts`** because
  `bind:clientHeight` throws in jsdom *during mount* — the blank-page failure the
  component test exists to catch. jsdom also has no `DragEvent`, and reports every
  measurement as 0. Any panel that measures itself must still work at zero height.

And one contract fact: **`"Infinity"` crosses the wire as a string.** WP-1011
found that `json.dumps` writes a bare `Infinity` token, which `JSON.parse`
rejects outright — so `gui/server.py` now spells non-finite floats as the schemas
do. A report payload carrying an infinite bound or a NaN statistic is therefore a
*string* on the client side; run it through `lib/table.ts`'s `num()` before
comparing it to anything.

From the **v1.0 GUI plan** (2026-07-29): not every `ActionKind` maps to an
automatable verb (`collect_better_data` cannot be a button that does
something). `report/apply.py` must declare per-kind applicability and the
panel renders unapplicable kinds as advice — decide the split explicitly in
the first commit rather than discovering it kind by kind.

From **WP-1007** (landed 2026-07-30): **the diagnostics panel needs no regex.**
Every guard `Diagnostic` now carries its parameter paths in `where` — including
`HIGH_CORRELATION`, which had an *empty* `where` until then, so the degenerate
pair could only be recovered by parsing `"a ~ b (ρ=+0.994)"`. Read `d.where` to
make a finding clickable, and `d.code` to branch; never split `d.message`.

One limitation to design around rather than discover: **the headline *number* is
still only in the message text.** `GuardFinding` carries it as `.value` (ρ, a
block R², a min eigenvalue), but `Diagnostic` was fenced out of scope in WP-1007
and has no numeric field, and `GuardReport` is transient — it is converted to
diagnostics inside `_run_stage` and never stored, so it does not reach a client at
all. If this panel wants to *sort* or *threshold* on ρ rather than display it,
that is either an additive optional `value` on `Diagnostic` (a freeze decision —
raise it in WP-1003) or a server-side arm on the run response. Do not parse the
message for the number.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): one of those
kinds stops being advice. **`reindex_or_recheck_cell` becomes automatable** —
`report/layer2.layer0_actions` has emitted it as an `alternatives` member since
v0.2 with nothing behind it, and WP-1024 gives it `rietx.pick_peaks(...)` /
`index_pattern(...)`. Put it on the applicable side of the split and wire its
button to launch an indexing run through the WP-1006 run state machine (it is
long-running, unlike every other applicable action). No `ActionKind` change is
involved, so `THRESHOLDS_VERSION` does not bump.

From **WP-1008** (GUI server, landed 2026-07-30):

- `GET /api/history` returns the shape, not the states: per node `id`, `parents`,
  `children`, `kind`, `action`, **`api_call`** (the node's equivalent public-API
  line — the "show me the code" affordance for free), `label`, `tags`, `rwp`,
  `gof`, `n_free`, `status`, `n_iterations`, `diagnostics`, `scores`, `notes`.
  A node's ~10 kB `state` is deliberately **not** in the payload; if a panel
  needs one node's parameter values, `GET /api/history/diff?a=&b=` answers the
  question it actually has.
- `POST /api/history/branch` is **checkout + tag**, not a new ref: this DAG has
  only `head` and tags, and a fork appears when you run from a node that already
  has a child. Label lanes from `tags`; do not draw a branch that does not exist.
- **A `checkout` clears the result.** `/api/result`, `/api/report` and every
  export answer `NO_RESULT` (409) afterwards until the next run — so "select a
  node" cannot repaint the report panel from a result, and the panel needs that
  empty state. Re-running or `replay` is the only way back to curves.
- `GET /api/report[?plan=preset]` is **idle-only** (Layers 1-2 read the compiled
  model a stage would be rewriting) and 409s with `RUN_IN_FLIGHT` mid-run; it
  defaults the Layer-2 veto to the project's own effective plan, so a panel need
  not pass one. `POST /api/report/apply` is reserved for this WP and 404s naming
  it.

From **WP-1010** (frontend scaffold, landed 2026-07-30): the app shell, `api.ts`
(with `history`, `checkout` and `report` already wired) and the console panel are
in place; add panels beside `panels/Plot.svelte` and delete the matching row from
`panels/Stubs.svelte`. Two shell behaviours to build on rather than duplicate:
the shell refetches `/api/result` whenever the run state returns to `idle` (any
way it ended) and holds the single `state` frame every control's `disabled`
derives from, and `ApiError.empty` already marks `NO_RESULT` — which is exactly
the state a history panel puts the app into every time it checks out a node.
Rebuild the committed dist in the same commit as any `gui/src/**` edit.

## Non-goals

- No new Layer-2 statistics or thresholds — render and apply what the
  report already says (`THRESHOLDS_VERSION` untouched).
- No mermaid/graphviz dependency — the DAG is small; draw it in Svelte.
- No auto-apply loops — one click, one action, human in the loop
  (`predict_then_verify` remains the API-side batch story).

## Tasks

- [x] History panel: DAG render (Rwp badges, head, tags), checkout / branch /
      annotate / tag wired to the WP-1008 routes.
- [x] Two-node compare/diff view from `RefinementTree.compare`/`diff` —
      side-by-side parameter deltas, changed-only filter. *(The diff route
      returns only what changed, so there is nothing to filter out and the panel
      says so instead of offering a toggle that does nothing; the filter it does
      offer is over paths.)*
- [x] Report panel: Layers 0–2; worst-region click-zoom; suggestion strip
      with confidence, predicted Δχ², veto reasons.
- [x] `report/apply.py`: per-kind applicability + verb mapping;
      `POST /api/report/apply`; applications echo + record as nodes.
- [x] `tests/test_report_apply.py`: every applicable `ActionKind` maps to
      verbs that execute on a synthetic misfit; unapplicable kinds are
      declared, not silently skipped; applied action is undone by checkout.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_report_apply.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- `report/schemas.py` — `ActionKind`, `SuggestedAction`,
  `VerificationOutcome`; `report/layer2.py` `predict_then_verify`.
- CLAUDE.md FitReport invariant (never a confident wrong singleton) — the
  panel renders abstentions and non-separability as such.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **history and report panels** (WP-1012) are the GUI's read-and-act half, and
the module that carries them is `report/apply.py` — the *how* beside Layer 2's
*what*, in a separate file because the two version differently (the vocabulary is
a contract; the mapping onto verbs changes when a verb arrives). Four rules.
**An applicable action is one stage**: `stage_for` returns a `StageSpec` and runs
nothing, so applying a suggestion travels the path the per-stage Run button
travels — one `run_stage`, one history node, the same 409 — and *undo is a
`checkout`*, not an inverse verb. **The action's own `parameter_paths` are the
globs**; `RECIPES` declares only how each `ActionKind` is carried
out (`stage`, `index` or `advice`, pinned complete against `get_args`), and
the four advice notes *are* the deliverable — the background-flexibility pair is
advice because it changes what the background can absorb rather than which
parameters move, and the statistic that catches the cost (the block projection R²
behind `BACKGROUND_ABSORPTION`) is not in the report. **Applicability and
reachability are different questions**: `unreachable` separates a glob matching
*nothing* (a `preferred_orientation` block not declared) from one whose every match
is *held*, quoting `held_because`, and `GET /api/report` serves the answer as an
`apply` arm **parallel to** `suggested_actions` — positional, because a kind is not
unique — so a button's enabled-ness and the route's willingness to act are one
answer. And **`expected_delta_chi2` is one number per report, not per action**:
`build_report` stamps the same figure on every Layer-1-derived action and it bounds
only the misfit attributed inside the *gated* regions (measured 16.19 predicted
against 16.33 observed), so the panel prints it once and says what it is. Two
traps a browser found and jsdom could not: the two `unmatched` kinds are opposite
diagnoses (an observed peak with no reflection is an impurity; a calculated peak
with no intensity is what a *mispositioned* model produces at every peak — 15 of
them read as "unindexed" once), and a `checkout` clears the result server-side
while `Plot` still holds it, so the panel redraws from the curves route, which
then sends the pattern alone.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.

- **2026-07-30 — landed.** Two commits: `report/apply.py` + `POST
  /api/report/apply` + `tests/test_report_apply.py` (12 tests), then the two
  panels + `gui/src/lib/{history,report}.ts` + the rebuilt dist, then four small
  corrections found by re-reading rather than by a test. On a numpy-only `[dev]`
  venv: fast suite **1145 passed / 107 skipped in 53 s** (1133 before), full suite
  **1215 passed / 116 skipped in 12:40** (1203 before) — both counts moved by
  exactly the twelve tests this WP added. vitest **85** (was 51);
  `svelte-check` clean; ruff clean. The 12:40 is at the top of the recorded range
  because the machine was concurrently running a headless browser, three vite
  builds and a second pytest; compare runs, not records.

  **Done.** The applicability split, decided once: 11 of the 16 `ActionKind`s are
  one stage, 1 is a search, 4 are advice — `missing_kinds()` is pinned empty
  against `get_args(ActionKind)` and the counts are asserted, so a new member
  cannot land silently on the advice side. `GET /api/report` gained an `apply` arm
  **parallel to** `suggested_actions` (positional, because a kind is not unique —
  two textured phases emit two `refine_preferred_orientation`s). The history panel
  draws the DAG with lanes, badges, tags and HEAD, and wires checkout / branch /
  tag / annotate / diff / compare. The report panel renders all three layers,
  click-zooms a region through the window route, and applies a suggestion in one
  click with Undo.

  **Design decisions worth not re-litigating.**

  1. **An applicable action is one stage.** `stage_for` returns a `StageSpec` and
     executes nothing, so an applied suggestion goes through the same `run`, the
     same 409, the same event stream and the same single history node as the
     per-stage Run button — and *undo is a `checkout`*, needing no inverse verb.
  2. **The action's own `parameter_paths` are the globs**; `RECIPES` declares only
     *how*. Layer 2 wrote the paths, sometimes with a phase index in them.
  3. **The two background-flexibility kinds are advice on grounds, not for want of
     effort.** They change what the background can *absorb* rather than which
     parameters move, and the statistic that catches the cost — the block
     projection R² behind `BACKGROUND_ABSORPTION` — is not in the report. A
     one-click flexibility increase would be a button whose own evidence cannot
     see what it did. If a later WP puts that measurement *in* the report, the
     kind moves to the applicable side and nothing else changes.
  4. **`reindex_or_recheck_cell` is declared applicable and refused by a derived
     predicate.** `capabilities().features["indexing"]` is False today; the
     refusal names WP-1024 and expires by itself.
  5. **Reachability is not applicability**, and its two halves are separate: a
     glob matching *nothing* (a `preferred_orientation` block not declared) reads
     differently from one whose every match is *held*, and the reason quoted is
     `held_because` verbatim.
  6. **The veto outranks every other refusal** — a vetoed action that is also
     unreachable still reads as vetoed, because the engine's judgement is the one
     a user has to argue with.

  **Findings, all measured, all corrected in place.**

  - **`expected_delta_chi2` is one number per *report*, not per action.**
    `build_report` computes `estimate_delta_chi2` once and stamps it on every
    Layer-1-derived action: measured 16.19 on all eight suggestions of a fit whose
    entire χ² is 16.96. It ranks nothing, and a per-row column would imply a
    per-action prediction that does not exist — so the panel prints it once, and
    the docstrings on `SuggestedAction` and `estimate_delta_chi2` now say so.
  - **It is not the "optimistic upper bound" both docstrings claimed.** It bounds
    the misfit attributed inside the *gated* regions; applying an action also moves
    regions that failed a gate. Measured for `refine_cell`: predicted 16.19,
    **observed 16.33** (0.8 % over). For `refine_zero_shift` on the same fit it is
    an over-estimate (13.80 observed). Not a bound in either direction.
  - **Layer 2 proposes Bragg-Brentano aberrations whatever geometry was
    measured.** On the Debye-Scherrer fixture the *highest*-confidence suggestion
    (1.000, `refine_sample_transparency`) names a path `params/vector.py`
    force-fixes off `bragg_brentano`. It is now unreachable-with-a-reason rather
    than a button that frees nothing. **Not fixed in Layer 2** — the WP's non-goals
    forbid changing what the report emits, and suppressing it would need Layer 2 to
    know the table. Left as a forward reference to WP-1003.
  - **`headline` called 15 `unmatched_calc` peaks "unindexed"** beside a summary
    saying "0 unmatched observed peak(s)". Opposite diagnoses; counted apart now.
    Found by looking at a real report in a browser, not by a fixture.
  - **`Plot.draw`'s window fetch was unguarded** and a checkout makes it 409, so
    `NO_RESULT` escaped as an unhandled page error. jsdom never reached the fetch
    because it does not load the runtime plotly script — now stubbed in
    `test-setup.ts`, which is also what makes the click-zoom assertable at all.
  - **The shell's end-of-run detection required having *seen* a non-idle frame**,
    so a stage that starts and finishes between two state frames left the previous
    fit's curves and χ² on screen. Keys on the run's outcome now. WP-1010's bug,
    surfaced by a fast applied stage.

  **Measured in a real browser** (Chrome for Testing via `playwright-core`,
  installed *outside* the workspace so `package.json` — and therefore the dist
  digest — is untouched; the browsers were already in
  `~/Library/Caches/ms-playwright`): **boot-to-interactive 104–200 ms** over three
  runs (load → the parameter table's first row), which is the figure WP-1010 left
  unmeasured. Dist 104.6 kB JS / 37.0 kB gzip, against 48.7/19.1 at WP-1010. The
  whole loop: report → Apply `refine_cell` → predicted 16.19 / observed 16.33 →
  Rwp 21.609 % → **4.155 %** → the suggestion list is then empty. Zero page
  errors. A region click took the plot from 4129 points over 3–24° to 54 points
  over 17.060–17.325°.

  **Not done / deliberately left.**

  - The DAG is **not virtualized** — a project's tree is tens of nodes, and the
    scroller is plain. A tree of thousands would want `windowSlice` (it is already
    exported from `lib/table.ts`).
  - `merge` and `cherry_pick` have **no panel affordance**. `merge` needs two
    selected nodes and a strategy argument, `cherry_pick` needs a target; both are
    on `Refinement` and neither has a WP-1008 route. Reserved-route work, not a
    frontend gap.
  - **`gate_failures` is parsed** — shallowly, for the gate's *name* only, because
    `RegionAttribution` carries no code field beside the formatted string. One
    place, `lib/report.ts`'s `gateName`, nothing branches on it. An additive field
    is a freeze decision (WP-1003).
  - The applied-suggestion banner survives only until the next apply or an Undo;
    it is **not persisted** to `ProjectDoc.ui`, because "what I applied last" is a
    property of this browsing session, not of the project.
  - `report/apply.py` is **not exposed on the agent surface** (`agent.py`). An
    agent already has `predict_then_verify`, which is the better batch story; a
    `{"task": "apply_action"}` arm would be a second one.

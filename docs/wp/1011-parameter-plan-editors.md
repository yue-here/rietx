# WP-1011 — Parameter editor, plan editor, run controls, disclosure

Milestone: v1.0 · Status: ✅ 2026-07-30
Track: The human GUI
Depends on: WP-1010

## Goal

The editing core of the GUI: a virtualized grouped parameter table, a plan
editor fed by `PLAN_INFO`, Run / Run-stage / Cancel controls, and the
Simple/Advanced progressive-disclosure toggle persisted to the project.

## Context

- Parameter table: virtualized (a Pawley fit can have thousands of rows),
  grouped by dot-path prefix — value edit, vary checkbox, esd column,
  locked/tied rows greyed with the reason as tooltip (the reason text comes
  from `ParameterRow.tie`/`locked`, WP-1004 — the server verb's refusal
  message, never a frontend guess). Glob filter box + free/fix-selection
  bulk ops → `PATCH /api/params` with globs, which delegates to
  `Refinement.set_vary` — one round trip, one history node.
- **fnmatch parity is cross-language anti-drift**: a pytest writes
  `tests/data/gui/fnmatch_cases.json` from Python's `fnmatch` (the
  authority — stage plans glob with it), vitest consumes it for
  `lib/fnmatch.ts`. The client-side matcher only *previews* selection; the
  server match is authoritative.
- Plan editor: preset picker fed by `PLAN_INFO` (WP-1004; title,
  description, intended mode, when-to-use), stage list with drag-reorder,
  per-stage `free` globs, advanced fields (max_iter, lebail_cycles, seed,
  strain_seed) behind disclosure. PUT `/api/plan` stores the unified
  `PlanSpec`.
- Run controls: Run / Run-stage / Cancel with optimistic status (<50 ms
  feedback; the server 409s a second run — surface that as "already
  running", not an error dialog).
- Progressive disclosure: **Simple mode (default)** hides bounds,
  transforms, solver/backend pickers, stage seeds, and
  Pawley/Stephens/ADP blocks unless the structure declares them; the
  FitReport suggestion strip (WP-1012) is the novice's "what next".
  Persisted in `ProjectDoc.ui` (WP-1005 — untyped dict, GUI owns the keys).
- Keyboard: Cmd/Ctrl-K command palette where every entry shows its API
  echo; `r` run, `.` run-stage, `Esc` cancel, `f`/`x` free/fix selection.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): `set_vary` can never free locked
entries (emission-line weight 0, symmetry-fixed cell angles) — the table
must render those rows without a vary checkbox at all, not with one that
errors on click.

From **WP-1004** (landed 2026-07-30): **do not re-derive the greying rule.**
`ParameterRow.refinable` is the single predicate over all three reasons a row
cannot be freed — `locked`, `tie`, and `mode_fixed` — and
`ParameterRow.held_because` is the tooltip text, already written. Three
consequences for this table: (a) there are **three** greyed states, not two, and
`mode_fixed` (lebail/pawley force-fixing every `.atoms.` path, `.scale`, the
line weights) must not be rendered as `locked`, because it comes back when the
mode changes — a Le Bail phase's mandatory dummy atom is the case that matters;
(b) a **tied** row's value cell is read-only and its tooltip should offer the tie
sources, since `set_values` on it raises naming them (`TieSpec.sources` /
`.describe()`); (c) `set_values` takes a **dict of several paths** on purpose —
batch the grid's edits into one call, because each call is one history node, and
per-keystroke nodes would bury the log. Bounds and transform are on the row too,
so the value editor can validate before the round trip (`set_values` refuses an
out-of-bounds value).

From **WP-1008** (GUI server, landed 2026-07-30) — the routes this WP edits
through are live:

- `GET /api/params` returns every row with `refinable` and `held_because`
  **added** to the `ParameterRow` dump (they are properties, so `model_dump`
  drops them), plus `n_free`, `mode`, `head` and `live`. Render the three held
  reasons from `held_because`; do not re-derive them from `locked`/`tie`/
  `mode_fixed`, which is the same rule spelled twice.
- `PATCH /api/params {"values": {...}, "vary": {"glob": bool}}` applies **values
  first, then vary in object order**, and each commits its own history node — so
  one editor "apply" is two or three nodes, and the history panel will show them.
- **A refused edit is the useful answer.** A tied path comes back 400 with the
  verb's own message naming its sources (`'phases.0.cell.b' follows
  'phases.0.cell.a' as an affine tie; set that instead`) and `where` = the path
  edited. Show the message; the GUI is the only place it is ever read.
- `GET /api/plan` gives the expanded stages plus a **derived** `preset` name
  (`null` when edited) and `selected`. `PUT /api/plan` takes either
  `{"preset": name}` or `{"plan": spec}`; a preset is stored **expanded through
  the mode** (`mccusker_default` + `lebail` → `profile_only`'s stages), so the
  editor shows exactly what will run. An empty stage list is refused.
- Every one of these 409s with `RUN_IN_FLIGHT` during a run, and the state
  refusal deliberately outranks body validation — disable the editor off the
  `state` SSE frame rather than letting a user retype a value into a 409.

From **WP-1009** (text document, landed 2026-07-30): use **`Project.parameters()`**
(or `GET /api/params`, which now does), not `Refinement.parameters()` directly.
The refinement's carried mode is what its last stage *ran* in — `"rietveld"`
before the first run — while the document says what the next run will use, so
calling the refinement directly reported `mode_fixed=False` on a Le Bail
project's `.atoms.` rows and would have rendered the mandatory dummy atom's
`biso` as editable. `Refinement.parameters(mode=…)` takes the override;
`Project.parameters()` supplies `doc.mode`. Also: `PlanSpec.preset_name()` is now
a schema method (was a private in the session), so the plan editor's "custom"
label and the text document's `plan` line cannot disagree.

From **WP-1010** (frontend scaffold, landed 2026-07-30) — the workspace exists and
`npm --prefix gui run build` writes the committed dist. What a panel author needs:

- **Add a panel, then delete its row.** `gui/src/panels/Stubs.svelte` lists every
  owed panel by name and WP; a landing panel replaces its row rather than a
  placeholder component, so you start from an empty file.
- `gui/src/api.ts` is the only place a route is named, and `ApiError` carries
  `code`/`where`/`details` with `.busy` (`RUN_IN_FLIGHT`) and `.empty`
  (`NO_RESULT`/`NO_PROJECT`) already spelled out — **branch on those, not on
  status codes or message text.**
- Controls derive `disabled` from the **`state` frame** the stream pushes
  (`App.svelte` holds it in one rune), never from what the last click hoped. A
  parameter table is the panel where that matters most: a PATCH during a run is a
  409 by design.
- `gui/src/App.test.ts` is a **jsdom mount test** against a stubbed `fetch`; copy
  its shape. It exists because no browser automation was available, and it catches
  the failure a Python test cannot: a mount-time error rendering a blank page.
  Note `resolve.conditions: ["browser"]` in `vite.config.ts` — without it
  `mount()` comes from svelte's server build and throws.
- Rebuild the dist in the same commit as any `gui/src/**` change, or
  `tests/test_gui_dist.py` fails with "run `npm --prefix gui run build`".

## Non-goals

- No structure/instrument *object* editing (WP-1014) — this WP edits θ-table
  entries and plans only.
- No text pane (WP-1013), no report strip (WP-1012) — the palette and
  disclosure land here; those panels plug in later.
- No undo stack of its own — undo is history checkout (WP-1012's panel);
  edits are history nodes already.

## Tasks

- [x] Virtualized grouped parameter table: value edit, vary checkbox, esd,
      locked/tied greyed + tooltip; glob filter; bulk free/fix via PATCH
      globs.
- [x] fnmatch parity fixture: pytest writes
      `tests/data/gui/fnmatch_cases.json`; vitest consumes it against
      `lib/fnmatch.ts`.
- [x] Plan editor: `PLAN_INFO` preset picker, stage list, drag-reorder,
      disclosure for advanced stage fields.
- [x] Run / Run-stage / Cancel with optimistic status; 409 surfaced as
      state, not failure.
- [x] Simple/Advanced toggle persisted to `ProjectDoc.ui`; command palette +
      shortcut keys with API echo.
- [x] Server-side: params PATCH (incl. bulk glob) rows in
      `tests/test_gui_server.py`; vitest for table selection logic and
      fnmatch parity.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1004's `ParameterRow` / verbs; CLAUDE.md path conventions (fnmatch, no
  brackets in paths).

## What landed

- `gui/src/lib/table.ts` — grouping, filtering, the virtual window, pending
  edits, esd-aware formatting; `lib/fnmatch.ts` — Python's `fnmatchcase`,
  ported; `lib/palette.ts` — command ranking and the shortcut-target rule.
  All four asserted in vitest without a DOM.
- `gui/src/panels/Params.svelte`, `Plan.svelte`, `Palette.svelte`; the shell
  grew a three-tab sidebar (Parameters / Plan / Build), a Simple↔Advanced
  segmented control and a keyboard layer.
- `tests/test_gui_fnmatch.py` writes the committed
  `tests/data/gui/fnmatch_cases.json`; `tests/test_gui_server.py` gained the
  bulk-glob row and the strict-JSON row.
- `src/rietx/gui/server.py` — `_finite`/`_dumps`, the defect below.
- `gui/src/test-setup.ts` — a `ResizeObserver` stub, with the rule for what
  may go in it. Every future component test inherits it.

## The defect this WP found

**`JSON.parse` rejects a bare `Infinity`, and every parameter row has one.**
`json.dumps` emits `Infinity`/`NaN` as bare tokens — a Python extension, not
JSON — and `json.loads` accepts them back, so the whole of `/api/params` was
unparseable in a browser while every Python test that read it passed. WP-1010
shipped because it only ever fetched the curves. The fix spells a non-finite
float the way the schemas already do (`ser_json_inf_nan="strings"`, CLAUDE.md's
"±inf bounds must survive JSON round-trip"): the GUI server was the one place
in the package re-serialising already-dumped dicts with stdlib `json`, and so
the one place that convention was being lost. It applies to the SSE frames too,
since an event's `data` is an open dict. The scan is a substring test on the
*output*, so an ordinary response pays one C-level search rather than a
recursive walk of a 4000-point payload. Pinned by `parse_constant` wired to
raise, over seven routes.

## Decisions worth carrying

- **The filter box *is* the selection.** There is no per-row multi-select,
  because `set_vary` takes one glob and records one node for it — N ticked rows
  would be N globs and N nodes. `asGlob` wraps a bare word as `*word*` so the
  string previewed and the string sent are the same one, and `selection()`
  counts only rows `set_vary` could actually move (locked and tied excluded,
  `mode_fixed` included, since that one *is* freeable and merely dropped again
  when a stage runs).
- **A typed number is compared to the rendered value**, not the stored float —
  WP-1009's rule, needed here for the same reason: values display at the
  precision their esd justifies (`4.1568(2)`), so comparing against 4.156783
  would turn "clicked into a cell and out again" into a `set_values` that
  truncates the parameter.
- **An invalid cell blocks Apply** rather than being dropped from the body. The
  point of carrying bounds on the row is to refuse before the round trip; a
  partial apply is a worse answer than none. Revert stays offered — an invalid
  edit is *counted* as pending precisely so it can be undone.
- **Simple mode hides held rows and the bounds/transform columns**, and says how
  many it hid. The charter also asked it to hide "Pawley/Stephens/ADP blocks
  unless the structure declares them" — those rows *only exist* when declared
  (`microstrain.dof.k`, `adp.k` are absent from the table otherwise), so no
  filter was written for a predicate the parameter table already enforces.
- **Group = the path minus its leaf, minus one more when the leaf is a bare
  index.** That is what puts an atom's coordinate DOFs, ADP components and
  `biso` under one heading instead of scattering one atom across three called
  `dof`, `adp` and the atom.

## Acceptance (measured 2026-07-30)

```
.venv/bin/python -m pytest tests/test_gui_server.py -q   →  33 passed
.venv/bin/python -m pytest tests/test_gui_fnmatch.py -q  →   4 passed
npm --prefix gui test                                    →  51 passed (4 files)
npm --prefix gui run check                               →  0 errors, 324 files
.venv/bin/python -m ruff check src tests examples        →  clean
fast suite (numpy-only [dev] venv)     → 1133 passed / 107 skipped in 63.6 s
full suite (same venv, busy machine)   → 1203 passed / 116 skipped in 11:52
dist: 76.8 kB JS (28.8 kB gzip), 8.9 kB CSS — was 48.7/19.1 at WP-1010
```

The fast count moved by exactly the six tests this WP added; the full count moved
by seven against the figure recorded the day before, on identical skip counts.
That one test is a gap between two sessions' runs rather than anything reproduced
here — both trees were green — and chasing it costs a 12-minute suite to settle a
number that changes no decision. Recorded rather than quietly rounded.

Driven end to end against a real server (`GuiSession` + `build_server` on an
ephemeral port), in the order the GUI performs them: 38 rows with 11 locked and
3 tied; `instrument.profile.*` freeing 5 parameters in **one** history node;
`phases.*.cell.*` freeing exactly `a` on a cubic cell; a tied edit refused with
`'phases.0.cell.b' follows 'phases.0.cell.a' as an affine tie; set that
instead`; `set_values` on `a` carrying `c` with it; one stage run through
`POST /api/run {kind:"stage"}` to Rwp 0.596, then the full plan to **Rwp
0.04153** (WP-1010's figure, unchanged); 13 rows coming back with esds; and
`ui.simple` surviving a `Project.open`.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **editors** (WP-1011) are the parameter table and the plan editor, and their
logic is in `gui/src/lib/` as pure functions (`table.ts`, `fnmatch.ts`,
`palette.ts`) so it can be asserted without a DOM. Four rules. **The filter box
is the selection**: a bulk free/fix sends the *glob*, because `set_vary` takes one
and records **one** history node for it — a per-row multi-select would be N globs
and N nodes — and `asGlob` wraps a bare word as `*word*` so the string previewed
and the string sent are the same one. **A held row gets no vary checkbox at all**,
with `held_because` as its tooltip and every reason it has drawn as its own
mark (`mode_fixed` is not `locked`; five — WP-1214, and WP-1435's `held`). **A typed number is compared to the *rendered*
value**, WP-1009's rule reused, so a cell showing `4.1568(2)` cannot truncate a
parameter on a click-in/click-out. And the client's matcher is a **preview only**
— it is `fnmatch.fnmatchcase` ported, held to Python by a committed corpus
(`tests/test_gui_fnmatch.py` writes `tests/data/gui/fnmatch_cases.json` from the
live parameter vocabulary; `fnmatch.test.ts` replays it), so a divergence is a
wrong count, never the wrong parameters freed. **`JSON.parse` rejects Python's
bare `Infinity`**, which `json.dumps` writes by default and every parameter row
carries: `gui/server.py` spells non-finite floats as the schemas do
(`ser_json_inf_nan="strings"`) on responses *and* SSE frames, and the client reads
them back with `lib/table.ts`'s `num()`. jsdom lacks `ResizeObserver` (which
`bind:clientHeight` compiles to, so its absence throws *during mount*);
`gui/src/test-setup.ts` is the one place that gap is filled. jsdom lacks
`DragEvent` too, so a drag test dispatches a plain `Event` (`App.test.ts`). It
has no canvas either, and uPlot draws in its constructor, so `test-setup.ts`
mocks `uplot` with `test-uplot.ts`'s `StubPlot`: uPlot's state, the chart
module's hooks fired, and every stroke recorded with the style it was made in,
so **a drawn colour is asserted from the record, never from the option handed
in** (WP-1461). What uPlot paints from it is `tests/test_gui_browser.py`'s
question.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
- **2026-07-30** — **landed.** Done: all six checklist items, in two commits
  (`0c2eec3` the logic + glob fixture, `6882e87` the components + the JSON
  fix). In flight: nothing. Next: WP-1012 (history worktree, report panel),
  which plugs into the sidebar's tab strip.

  Gotchas for whoever touches this next:

  * **Rebuild the dist in the same commit** as any `gui/src/**` change or
    `tests/test_gui_dist.py` fails. Still true, still the most likely trip.
  * **jsdom lacks browser APIs the panels use.** `bind:clientHeight` compiles to
    a `ResizeObserver`, and its absence throws *during mount* — the blank-page
    failure. `gui/src/test-setup.ts` stubs it; `DragEvent` is also absent, so
    the plan editor's reorder test dispatches a plain `Event` of the same type.
    Add to the setup file only what a real browser always has.
  * **jsdom reports every measurement as 0**, so the virtual window renders only
    its overscan there. That is why `windowSlice` must stay correct at
    `viewport = 0` — a test asserting "all rows are in the DOM" would be
    asserting a coincidence.
  * The client-side matcher is a **preview only**. If a glob shape ever
    disagrees with Python, add the case to `tests/test_gui_fnmatch.py`'s
    `_EDITOR_GLOBS` and let the parity test locate it. Python *repairs* an
    inverted range (`[z-a]`) and the port does not; the corpus says so in its
    own `_comment`, and no path in this package contains a bracket.
  * `Refinement.parameters()` is answered for the **document's** mode via
    `Project.parameters()` — do not call the refinement directly (WP-1009).

  **Not yet visually confirmed.** WP-1010's page was looked at by the user the
  same day; these panels have been driven by a jsdom mount test (20 cases,
  including the three held states, the PATCH bodies, drag-reorder and the
  palette) and end to end over real HTTP, but **nobody has looked at them in a
  browser.** No browser automation was available in this session either, so the
  gap is the same one WP-1010 recorded and closed by asking: what jsdom cannot
  catch is layout — a sidebar too narrow for the table's five columns, a
  virtualized list whose row height disagrees with the CSS (`ROW_HEIGHT = 22`
  must equal the `.row`/`.group` height, or the scroll drifts), or a palette
  that opens off-screen. Run `rietx gui` on any `.rex` and look before
  building anything on top.

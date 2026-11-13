# CLAUDE.md — the GUI: gui/ (frontend) and src/rietx/gui/ (server)

Scope: the refinement GUI's rulebook. It loads when a session works under `gui/`;
`src/rietx/gui/CLAUDE.md` points here. The root CLAUDE.md holds the pipeline and the
package-wide invariants. Sections follow the files a session edits.

Each rule names its WP. The measurement, story or example behind it is in that WP file:
its § "Moved from gui/CLAUDE.md" holds the paragraph this file carried until WP-2134,
verbatim. A rule enters here only as a standing rule with its identifiers and anchor
(`docs/milestones/process.md` § The rule); its evidence goes to the WP.
`tests/test_docs_consistency.py::test_gui_rulebook_paths_resolve` fails on a path written
here with a directory (`lib/plot.ts`, `gui/session.py`) that no longer exists, and on a
`file:symbol` whose symbol has left the file. Write paths that way, so a rename breaks the
test and never silently the rule.

How the GUI looks and behaves, with each rule's motive, is `gui/STYLE.md` (WP-2142):
read it before changing either.

## Defaults

- **Every choice the GUI offers ships a default that suits most phases; a setting is for
  the rest** (the maintainer's rule, WP-1462). A user who never opens a drawer sees the
  conventional picture (ellipsoids at 50 %, bonds at 1.15×(rᵢ+rⱼ)). A default is measured
  across phases, and the measurement is kept where the choice is made. A setting most
  users would change means the default is wrong.

## Build, dist and toolchain

`gui/package.json`, `gui/scripts/`, the committed dist under `src/rietx/gui/static`.

- **The dist is committed, so installing the wheel never needs node** (WP-1010).
  `tests/test_gui_dist.py` holds it in the node-free suite: the digest is recomputed,
  nothing may gitignore the dist, the built files are in the wheel, and no built file
  names a remote host. The digest lives once, in `gui/scripts/build_info.py`, called by
  the build and the test. `build-info.json` carries no timestamp, so
  `git diff --exit-code src/rietx/gui/static` means stale and never merely rebuilt.
- **`build_info.py` hashes `gui/src/**/*`, test files included** (WP-1425). Editing any
  file there, a test too, marks the dist stale and costs `npm run build`.
- **The chart module, uPlot, svgcanvas and CodeMirror are chunks off the boot path**
  (WP-1461, WP-1013), fetched on first draw, first SVG export and first Text tab. A panel
  imports them dynamically or by type alone. `test_gui_dist.py` fails on one inlined
  into `app.js`, since a byte count would not say so.
- **No GUI page loads plotly** (WP-1462). uPlot and svgcanvas are vendored into
  `src/rietx/viz/static` by `gui/scripts/vendor.py`, the build's first step, which records
  each copy's version in `VENDORED.json`: bump the pin in `gui/package.json`, then build.
- **The node floor is the strictest `engines` entry in `gui/package-lock.json`**
  (WP-1442; re-read 2026-11-09 by WP-2134: jsdom 30 asks `^22.22.2 || ^24.15.0 || >=26`).
  Under an older node, rolldown fails at import with a message naming neither node nor
  a version. A `node_modules` installed under the old node fails under the new one, so
  `npm ci` again after switching.
- **The rebuild is `gui/src/next/`, a second page built in a second pass**
  (`vite build --mode next`, served at `/next`, WP-2215): one multi-entry pass makes
  today's page load a shared chunk. A shared panel the new page must change moves
  into `gui/src/next/` first; its tabs stay out of `panels.json` until the swap.
- `npm run build` needs `python3`. `vitest` needs `resolve.conditions: ["browser"]`, or
  `mount()` comes from svelte's server build. `@sveltejs/vite-plugin-svelte` must be v7
  for Vite 8 (WP-1010).

## Tests: vitest, shared corpora and the real browser

- **jsdom gaps are filled in `gui/src/test-setup.ts` and nowhere else** (WP-1011,
  WP-1461, WP-1462). It supplies `ResizeObserver` (`bind:clientHeight` compiles to one,
  and its absence throws during mount). It mocks `uplot` with `gui/src/test-uplot.ts`'s
  `StubPlot`, which records every stroke with the style it was made in, so **a drawn
  colour is asserted from the record, never from the option handed in**. It mocks
  `lib/gl3d.ts`'s `createRenderer` with `gui/src/test-gl3d.ts`, which records every scene
  and view and counts a renderer made on a dead canvas. jsdom has no `DragEvent`: a drag
  test dispatches a plain `Event`.
- **What a canvas paints is a real browser's question**: `tests/test_gui_browser.py`.
  Pictures are compared by looking, never by a sha256 of one.
- **Python owns a vocabulary; TypeScript replays a committed corpus of it** (WP-1011, the
  "fnmatch mechanism"). A pytest writes the JSON under `tests/data/gui/` from the live
  vocabulary and a vitest replays it, so a divergence is red on one side. Instances:
  `fnmatch_cases.json` (`tests/test_gui_fnmatch.py` → `lib/fnmatch.test.ts`),
  `index_controls.json` (→ `lib/controls.test.ts`), `help_keys.json` (→ `lib/help.ts`),
  `scene_cases.json` (`tests/test_render_structure.py` → `lib/structure3d.test.ts`).
  Where no Python object knows the fact, the direction reverses: `lib/tabs.test.ts`
  writes `panels.json` and pytest reads it, which keeps the python suite node-free.
- **A case ported to a non-TypeScript page is compared as text** (WP-1425). `rietx watch`
  ports `clampSize`/`dragged`/`axisOf`, and `tests/test_watch_app.py` holds
  `lib/resize.test.ts`'s `ported cases` block equal to `tests/watch_core.test.mjs`,
  comments included. Edit one and the other fails until it follows.
- **Drive a real browser for any layout, cursor, hover or paint change.** jsdom has no
  layout, no hover and no cursor; most traps in this file were found only in a browser.
  The chromium binaries are cached even without playwright: `npm i playwright-core` in a
  scratch directory, never in `gui/` (the lockfile is committed), and point it at the
  cached executable. When a browser pass reports the impossible, suspect the harness
  first (headless playwright auto-dismisses dialogs).

## Server and wire

`src/rietx/gui/server.py`, `src/rietx/gui/session.py`.

- **`GuiSession` holds every verb as a plain method that knows nothing of HTTP**
  (WP-1008). `gui/server.py` parses a path, calls one, serialises the answer, and is the
  layer a Tauri host would replace. Its route table plus `RESERVED_ROUTES` (settled
  paths whose behaviour a later WP owes, a 404 naming it) are the complete wire surface,
  held disjoint by test.
- **A mutating verb returns 409 while a run is in flight** (WP-1008). The refusal
  outranks body validation. It enforces frozen-per-stage discreteness structurally.
- **Settings persist on the verb, never on save** (WP-1008), so closing has nothing to
  warn about.
- **A `ui` key belongs to whatever it is about** (WP-1044). A width or Simple/Advanced is
  the project's (`ProjectDoc.ui`, `POST /api/project`). The theme is the person's:
  `GET`/`POST /api/settings` over `state_dir/settings.json`, beside the recent list,
  with `ProjectDoc.ui`'s grammar (top-level merge, `null` drops, persisted on the verb)
  and not refused mid-run. Root CLAUDE.md § Conventions owns where the theme lives.
- **The run state travels beside the events as its own SSE frame type** (WP-1008; the
  rule is root's § Telemetry). `live/events.jsonl` stays the one stream `watch` tails.
- **`/api/result` omits the curves; `/api/result/curves` sends every channel once as
  float64** (WP-1461). Past `CURVES_CEILING` it decimates through
  `viz.compare.decimation_index`, the comparison UI's, whose count is a budget. Which
  points a payload carries is the server's; the chart paints each pixel column's
  extremes of them (WP-1461) and the readout reads the payload.
- **The curves route sends three residuals and a `weighted` flag** (WP-1029).
  `cumulative_chi2` is summed over every fitted channel, so a client cannot derive it; a
  zoom re-bases that one sum (`rxplot.chi2Base`) and never sums what it holds. Residuals
  are drawn through `viz.packed.curve_arrays`, one σ policy for every drawer (WP-1016).
- **A multi-verb route is all or nothing** (WP-2126): its verbs run on
  `session.rehearse`'s copy first.
- **Non-finite floats are spelled as the schemas spell them** (WP-1011).
  `JSON.parse` rejects Python's bare `Infinity`, which every parameter row carries, so
  `gui/server.py` writes `ser_json_inf_nan="strings"` on responses and SSE frames, and
  the client reads them with `lib/table.ts`'s `num()`.
- **A run route refuses in the route, never in the worker** (WP-1207). A run started is a
  200 whose failure reaches only the event stream. `NoPhasesError`
  (`code = "NO_PHASES"`) is raised before the worker starts.
- **Uploads are two-phase and the one non-JSON route family** (WP-1014). A file is staged
  and read before anything is created, and only an opaque token crosses back, never a
  path. The body is raw bytes, filename and reader options in the query string
  (`UPLOAD_ROUTES`).
- **A name or path from a request is checked by membership or containment, never
  sanitised** (WP-1204, WP-1205). An example `name` is checked against the example list.
  `GET /api/fs` resolves `path` (symlinks included) and checks it against `Path.home()`
  and the process's cwd, the shape `GuiSession._export_target` uses. `/api/fs` is
  read-only and not behind the 409.
- **An export is gated on what it describes** (WP-1214). `instrument_profile` is
  answered from the project; the rest of the family needs a result. `_EXPORT_MODEL_ONLY`
  declares the exception, so the stricter gate stays the default.
- **A memoised answer may be fetched automatically, and its route stays split** (WP-1215).
  The Wyckoff search is keyed on (space group, positions), the content tuple. A miss
  still costs milliseconds an atom, so it is not folded into `GET /api/structure`.
- **`n_phases` rides on `project_doc` as a derived summary beside `head`** (WP-1207), so a
  client knows a run is refused before offering one. `moved()` reloads the document as
  well as the curves.
- **Opening another project replaces the session's, with no prompt** (WP-1034): nothing
  is unsaved, and a run in flight is refused by `project_open`'s 409. There is no
  read-only way to open a project (root § Project); look through `rietx gui --scratch`.
  `--state-dir` moves the recent list. `*.rex/` is in `.gitignore` (WP-1204).
- `strategy.staged.resolve_plan` (preset name + mode → plan) is the one resolver the GUI,
  `fit` and `sequential` share (WP-1008).

## The `.rxt` document

`src/rietx/gui/textdoc.py` (`rxt 1`), `lib/rxt.ts`, `lib/sync.ts`, `panels/Text.svelte`.

- **A delta is diffed against the live project, never against the old text** (WP-1009).
  `render` → `parse` → `changes` → `apply`. An untouched document emits no verbs. A
  read-only field is an error only when it differs. A typed number is compared to the
  rendered value, so values may render at 12 significant digits.
- **Everything applies through the verbs a form calls**, with the same history nodes,
  and a refusal is the verb's own words (`held_because`, `TieSpec.describe`) with a line
  number (WP-1009).
- **Grammar** (WP-1009): a `tie` renders last on its line, since `=` runs to end of line;
  column widths are per block, aligned so a rectangular selection hits one field; a stage
  line's keys are `textdoc.STAGE_KEYS`, derived from `StageSpec` and pinned by
  `test_textdoc` against `model_fields`, so a new schema field reaches renderer, parser and
  `lib/rxt.ts`. An added key is no `FORMAT_VERSION` bump. Comments parse and do not survive
  a re-render; storing one would be a second authority.
- **The head is the reload signal** (WP-1013); there is no third SSE frame type.
- **There is no merge and no force-apply** (WP-1013). A stale buffer re-reads and
  re-applies, as the server's 409 `STALE_REVISION` says. Applying a loser's document
  would revert every row it did not touch.
- **Only the server decides validity** (WP-1013). `lib/rxt.ts` has no `error` token, its
  vocabulary pinned to `textdoc._KEYWORDS` and `StageSpec.model_fields` by
  `test_the_highlighter_quotes_the_parsers_words`. Indentation is the parser's dispatch.
- **A response carrying an older `seq` is dropped** (WP-1013): the 300 ms debounce puts two
  validations in flight.
- **The editor's document and its diagnostics are `$effect`s over the sync state, never
  pushed** (WP-1013).
- The pane stays mounted while hidden and builds its editor on first entry (WP-1013).
- **`.rxt` peaks block**: only `2theta` and `flags` are editable; the rest is derived and
  regenerated (WP-1027).

## Svelte and browser traps

Each was found in a browser, and jsdom cannot see it.

- **`structuredClone` throws on a `$state` proxy**: use `lib/model.ts:clone` (WP-1014).
- **A payload replaced whole is `$state.raw`** (WP-1213). A plain `$state` proxies it,
  making the held value and the drawn one two identities.
- **A `$derived` off `project` is a new object on every settings PATCH** (WP-1212). Key
  an effect by value (`extent` beside `protocolKey`), or on a boolean `$derived`
  (`panels/Series.svelte`'s `hasProject`, WP-1027): an effect reading the project object
  refires on every ui-only PATCH.
- **Two `$state` assignments either side of an `await` are two flushes** (WP-1212). Read
  what both need before publishing either (`gui/src/App.svelte:readPeaks`).
- **A style read synchronously in an effect races the shell's `applyTheme`** (WP-1027).
  `lib/pattern.ts`'s `retheme` and `panels/Structure3D.svelte`'s `rebuild` wait one
  microtask before `getComputedStyle`.
- **An effect that owns a resource depends on that resource alone** (WP-1462). The 3D
  mount effect depends on the canvas and calls `rebuild` under `untrack`, or every
  payload tears the WebGL context down.
- **Instrument before the library loads**, through an init script (WP-1032). A `$state`
  rune caches a namespace's properties on first read, so a probe patched in after boot
  counts nothing.
- **A verb's refusal and a panel's load error never share one field** (WP-1014).
- **Concurrent fetches keep their answers in separate fields; a stale response is
  dropped** (WP-1215). An effect keyed on a local write keys on `stamp`, not `head`.
- **Measure latency, not frame rate** (WP-1032): work behind an un-coalesced
  `ResizeObserver` lands late at a steady 60 fps. The chart module's `setSize` runs in
  the observer's frame and the viewer asks for one `requestAnimationFrame`.
- **A fix that does not remove the symptom is evidence about the cause** (WP-1032).
  `opacity` below 1 promotes an element to z-index 0, over a sticky `th` at `auto`.
- CodeMirror's chrome is an `EditorView.theme`, never a stylesheet rule: CM's own
  `.ͼ1 .cm-gutters` wins on specificity (WP-1029).

## House style and help

`gui/src/app.css`, `gui/src/tokens.css`, `gui/src/Help.svelte`, `lib/help.ts`. The
visual rules in this section are listed in WP-2134 for the GUI style guide.

- **The token values are Python and `gui/src/tokens.css` is generated** (WP-1429;
  root § Conventions). Regenerate with `python -m rietx.viz.theme > gui/src/tokens.css`,
  then rebuild. `app.css` imports it and keeps everything that is not a colour.
  `tests/test_gui_palette.py` holds the committed file equal to the emitter byte for byte.
- **One token layer and nine registers; size, padding and radius belong to the register,
  never the call site** (WP-1201). A panel wanting a smaller button wants a different
  register. `lib/style.test.ts` fails on a panel declaring any of the three on a register,
  and on a `font-size` that is not a step of the scale.

  | Register | Means |
  |---|---|
  | `button` | the one state-changing action in its region |
  | `button.ghost` | any other action; same size, only the fill differs |
  | `.segmented` | choose one of N views or modes |
  | `.tab` | choose one of N panels |
  | `.chip` | a fact: a flag, a tag, a grade. Never acts; a verb on a chip sits beside it |
  | `.pill` | a live mono readout |
  | `.pick` | select this row: a button that gave up its box, because the row is the target |
  | `.link` | inline navigation, at the size of the line it sits in |
  | `.help` | an explanation one click away; the cursor is the whole mark |

- **Three type steps** (WP-1201): `--text` prose; `--text-sm` a control and everything on
  its row; `--text-xs` a chip and a section heading. Secondary is `.muted`, never a size.
  Mono is a family, not a size. `lib/style.test.ts` refuses `.small` and `.tiny`. A
  chip's tone is one of `note` (default), `ok`, `warn`, `bad`, `accent`; `lib/peaks.ts`'s
  tone functions return members of it.
- **The theme is three-way and resolved once**, stamped as `data-theme` on the root by
  `lib/theme.ts` (WP-1029): following the system is a choice.
- **A `.pick` row carries its own hover background** (WP-1204), or it reads as prose.
- **A register's width is the call site's** (WP-1206): `.segmented` is `display: flex`
  and stretches in a block parent.
- **A placeholder is a word, never a plausible number** (WP-1206). A number reads as a
  filled value, so the instrument form's say `default`; with no default, no placeholder.
- **Chrome is not a palette** (WP-1210). A plot mark takes a `--plot-*` token of its own.
  `tests/test_gui_palette.py` holds every one 0.13 OKLab from every other plot colour
  (`structure3d._oklab_distance` is the package's one distance) and names the pairs the
  shipped set misses. No free hue is left for a further mark that carries a quantity
  (WP-1211).
- **State rides on the mark's shape, never a second colour** (WP-1210): one ink per layer,
  hollow for unusable, diamond for human-placed. A mark that is not data never borrows
  the recessive `--muted`.
- **A mark carrying no quantity takes chrome ink** (WP-1213): the pointer line is solid
  `--fg`, since dotted `--muted` is the excluded-region edge. `rxplot.panes` sets
  `.u-cursor-x` inline for every chart on every page.
- **Only the Rwp badge may be green** (WP-1217); a parameter difference has no good
  direction.
- **Two cascade traps** (WP-1201): a state like `button.on` is `(0,1,1)`, so a more
  specific rule still loses every property it does not declare; `text-transform` and
  `letter-spacing` inherit into a button unless its register says otherwise.
- **A `ch` column holds only while every cell in it is one font at one size** (WP-1217):
  put the family and the size on the row.
- **A `td` that is not `display: table-cell` is not a cell** (WP-1209): adjacent flex
  `td`s merge into one anonymous cell.
- **GUI prose is written under `/yue-docs-style`** (WP-1201): help entries, wizard lines,
  empty states, error text.
- **What a name means is an entry in `rietx.help`, reached through `<Help>`** (WP-1203).
  One instance in `App.svelte`. A key is `arm:name`, crossed against
  `tests/data/gui/help_keys.json`. A field inventory derives its key from the field's
  name where the arm shares the vocabulary (`lib/controls.ts`, `lib/wizard.ts`) and
  carries it as data otherwise (`lib/model.ts`). `<Help text=…>` is for a sentence the
  server wrote about one row (`held_because`, a refutation).
- **`title=` is what is left over** (WP-1203): a value the layout truncated, or a verb
  phrase on a `<button>`, never authored prose. `lib/help.test.ts` holds an exact
  per-file count, failing both ways.
- **A term is a `<span role="button">`** (WP-1203): focusable, answers Enter and Space,
  hittable (give a flex item a minimum width), named by its children and never by an
  `aria-label`, with `aria-haspopup="dialog"`. The popover takes focus.
- **A chip's words are the corpus's** (WP-1209). `HelpEntry.label` is the short form, the
  chip says `labelFor(corpus, key)`, and the popover restores the name. `peak_flags` and
  `peak_origins` carry a label on every entry, held by `tests/test_help.py` to three
  words and unique.
- **No mute fields** (WP-1032, WP-1203): every `PresetField` and every
  `instrumentFields()` entry has a corpus key, pinned by a meta-test over every geometry.

## Shell and layout

`gui/src/App.svelte`, `lib/resize.ts`, `lib/tabs.ts`, `panels/Splitter.svelte`.

- **The tab strips are data in `lib/tabs.ts`** (`TABS`, nine panels; `GRAPH_TABS`,
  WP-2123), written into the panel corpus so the manual must name each.
- **Both side panels collapse, each from a button on its own side; one always shows**
  (WP-2123, replacing WP-1034's `Split | Full`). The layout is session-local and
  unpersisted: a view choice, not a setting.
- **`Model` is mounted exactly once in `App.svelte`**, never per branch of
  `{#if project}` (WP-1205), and **every opener settles what is drawn over the project
  in the shell's `open`/`opened`** (WP-2131).
- **A stored size is not a settled size** (WP-1029): `fitColumns` re-clamps at render.
- **A splitter reports a size and never writes one** (WP-1029): `onsize(size, done)`,
  persisted to `ProjectDoc.ui` on the verb, with an `inline` flow inside `overflow: auto`.
- **A chart is sized by the `ResizeObserver` the chart module keeps on its host**
  (`rxplot.panes`, WP-1029). A panel sizes the host, never the chart.
- **A panel's minimum width is measured, not chosen, and stated once** (WP-1034,
  WP-1215, WP-1216): `MODEL_MIN` in `lib/resize.ts`. A width written in several places
  (a table's `min-width`, a column's `flex-basis`, `MODEL_MIN`) is crossed by
  `lib/resize.test.ts`; `MODEL_MIN.form` is the form's column arithmetic, handed to CSS
  as `--col-min`. A stacking threshold counts the grips inside the row it measures.
- **A column that must not lose gets a flex basis, not a share** (WP-1034).
- **Overflow wraps, never truncates, the header included** (WP-1034). No tab label is
  shortened and buttons do not grow. Anything meant to ellipsise needs `flex-basis: 0`.
- **A statistic outlives the thing it describes** (WP-1034): the run frame is the Rwp's
  source only while a run is in flight.
- A `colspan` cell's grid is part of the table's min-content: floor a track there with
  `min(210px, 100%)` (WP-1215).

## Plot

`panels/Plot.svelte`, `lib/plot.ts`, `lib/pattern.ts`, `src/rietx/viz/static/rxplot.mjs`.

- **A redraw never moves the axes** (WP-1044, WP-1212). A knob or layer change repaints
  and fetches nothing; a payload over the same channels keeps the view
  (`lib/pattern.ts:sameGrid`); the knob effect reads the payload untracked.
- **Arming is the figure's mode (`setMode`) and repaints nothing** (WP-1212).
- **A new pointer meaning ambiguous at every distance is a mode, not an arbitration**
  (WP-1033). Arming a region drag is explicit, hands the drag to the chart's select mode
  (x only), suspends the peak verbs and disarms after one selection.
- **An armed range gesture says so under the pointer** (WP-1044): `col-resize` on
  `.u-over`.
- **A mask is invisible in a picture of its own output** (WP-1033), so masked channels
  travel beside the fitted ones (the curves payload's `kept`). `Project.fitted_mask` is
  the one authority, pinned to `compile_model` by a test asserting
  `len(result.two_theta)` against it.
- **Protocol is not a drawing choice** (WP-1033). The residual selector and scale are
  session-local; a region changes Rwp, persists on the verb and lives in its own strip
  with typed fields and the channel count.
- **Between a settings change and a run, the route says `stale`**, comparing fitted 2θ
  values, not their count (WP-1033).
- **Shading spans every pane's full height and is clipped to the measured extent**
  (WP-1033). `viz/` does not shade: an exported figure shows exclusion as absence.
- **A tick belongs to the model** (WP-1032): its own band between pattern and residual.
- **A pattern pane's hooks draw clipped to its plot area, at one seam** (`rxplot.clipped`, WP-2200).
- **Hiding a curve is by exception** (WP-1032): `curveToggles`/`hidden`, unpersisted.
- **A layer is drawn where it can be edited** (WP-1210): peak markers and their curve
  only while the Peaks tab is up, so `peaksActive` is a drawing input of the repaint.
- **A curve that cannot be drawn is listed, disabled, with its reason** (WP-1210):
  `CurveToggle.absent`; `dataOnlyHidden` covers absent ids too.
- **A hover link never repaints the pattern** (WP-1032): the ring is a DOM mark.
- **The hover readout is a strip, never a box** (WP-1213). A new fact about a mark goes
  in the strip; the chart takes neither of uPlot's boxes, held by `App.test.ts`.
- **The strip's shape follows payload, tab and curve toggles, never the pointer**
  (WP-1213). Every slot that varies under a sweep keeps its place and empties, values
  are sized in `ch`, so the canvas above never resizes.
- **The pointer's 2θ is the cursor's pixel through the chart's x** (WP-1213). A curve is
  read at the nearest drawn channel; a nearby thing is hit-tested against the pointer.
  Hover and the non-destructive verbs use the coarse `PICK_RADIUS_PX`
  (`panels/Plot.svelte`), so the ring, the lit table row and the strip name one peak; the
  move gesture uses `lib/peaks.ts:grabToleranceDeg`.
- **A masked channel is in no result, so the readout reads two arms** (WP-1213): fitted
  ∪ excluded.
- **One reflection has one spelling on every browser surface** (WP-1213):
  `lib/peaks.ts:formatHkl` and the wheel's `watch-core.mjs` `hklLabel`, held equal by
  `lib/plot.test.ts`.
- **Prose takes `−`, numbers take `-`** (WP-1213).
- **A candidate's lines carry its own `shift_template`, inverted, never
  `instrument.zero_shift`** (WP-1211), on `structure_from_candidate`'s lattice group.
- **A cap says that it capped** (WP-1211): past `MAX_CANDIDATE_TICKS` lines are thinned by
  rank in 2θ, with `n_total` beside them.
- **A layer whose control is a row gets no `CurveToggle`** (WP-1211); the status line
  under the plot says what the toggle would have.
- **A preview is not a selection; they are two props** (WP-1211). A hover draws lines;
  only a selection clears the plot to the data, through the `data only` button's own
  press and one flag saying whose press it was.
- **Candidate lines span the data pane's height on a layer of their own, drawn under
  everything** (WP-1211).

## Peaks and indexing

`panels/Peaks.svelte`, `lib/peaks.ts`, `lib/controls.ts`, `src/rietx/gui/peaks.py`.

- **A peak list is a project artifact** (`peaks.json`, keyed by `data_fingerprint`,
  refused against the wrong pattern; WP-1027). Every edit refits one group through the
  picker's solver; `origin` and `excluded` carry across refits.
- **A cross-group mark follows an edit by its judgement's change alone** (WP-2030); a new
  cross-group flag joins `_follow_cross_group_marks`.
- **The plot is an editing surface only while the Peaks tab is active, and every pointer
  verb has a non-pointer route** (WP-1027). The gestures are stated while the tab is up.
  Right-click removes a peak (WP-1032).
- **The move gesture's grab radius is min(10 px, 1.5× median fitted FWHM)**
  (`grabToleranceDeg`, WP-1027). A drawn σ whisker is capped at 3×FWHM.
- **`/api/index` and `/api/index/extinction` are run kinds on the one machine** (WP-1027).
  A cancelled search returns what it has; its status is read off the token. The screen is
  gated on neither the adopt verdict nor a phase.
- **Any candidate can be adopted** (the maintainer's ruling B, 2026-11-08, WP-2124). The
  arm's `picked` is the gate's pick; its `why` is written into the `edit_model` node when
  another row is adopted. Badges follow the server (`adopt`, `best`). The panel enables
  Adopt on every row, prints `why` under the grade and badges only `picked` (WP-2130).
- **What a search covered is said above the list whatever it found** (WP-2130, WP-1042's
  "not reached is loud"): `systems_searched`, `search_complete`, and the run-level
  diagnostics with their `where`.
- **The search form is `ProjectDoc.indexing`, the `SearchSpecSpec` an agent request
  carries, committed whole on the verb** (WP-1045),
  and re-synced from the document on every head move, refusals included.
- **Vocabularies come from `/api/capabilities`**, never literals (WP-1045).
- **`lib/controls.ts` declares every field** with widget kind, label and help key, replayed
  against `index_controls.json` (WP-1045).
- **A prior cell is parsed locally; a prior space-group symbol is validated by the
  server** in gemmi's words (WP-1045). The form's error field is its own.
- **Streamed shortlists are the shell's to fold** (WP-1045): `consensus:<system>`
  `stage_end` frames collect in `App.svelte`, cleared on `index_start`, kept after the
  run. A streamed grade can rise, never fall.
- **A column is scanned, so its places are fixed** (WP-1209): 2θ at four places
  (`formatPosition`), I as `I/Imax × 100` over the strongest measured line
  (`formatIntensity`, `—` under `no_intensity`/`fit_failed`), and an esd from 1° up is not
  printed.
- **An esd that has swallowed its value is not a precision** (WP-1209):
  `esdSwallowsValue` (≥ 1 and larger than the value) makes `formatValue` print the value
  at its own precision and `formatEsd` write `±` beside it, for every caller.

## Parameters and plan

`panels/Params.svelte`, `lib/table.ts`, `lib/fnmatch.ts`, `panels/Plan.svelte`,
`lib/plan.ts`.

- **The filter box is the selection** (WP-1011). A bulk free/fix sends the glob, one
  `set_vary` and one node; `asGlob` wraps a bare word as `*word*`, so the glob previewed
  is the glob sent.
- **The client's matcher is a preview only** (WP-1011): `lib/fnmatch.ts` ports
  `fnmatch.fnmatchcase`, held to Python by `fnmatch_cases.json`.
- **A held row gets no vary checkbox** (WP-1011). `held_because` is its tooltip, and
  each reason draws its own mark from `lib/table.ts:heldGlyph`: locked, tied, mode-fixed,
  hold, degenerate (`needs_held_cell`). An unknown reason still draws a mark.
  `tests/test_gui_server.py` reads `ParameterRow.refinable`'s fields and `lib/table.ts`'s
  branches, so a sixth fails on both sides (WP-1214).
- **A typed number is compared to the rendered value** (WP-1011, WP-1009's rule).
- **A flag is set beside the value it is about** (WP-1214), in the same
  `PATCH /api/params` as the value edits and before the model patches.
- **A vary key is a path or a glob** (WP-1215): a site's DOFs are freed together as
  `phases.i.atoms.j.dof.*`, one node; a group that disagrees draws `indeterminate`.
- **A field's parameter path is not always its model path prefixed** (WP-1214):
  `Field.param` carries it and `fieldParam` is what every lookup asks.
- **The plan resolution is the real verb** (WP-1208): `GET /api/plan/resolve` runs
  `ParameterTable.set_vary` on the table `fit` builds. `lib/fnmatch.ts` matches nothing
  here.
- **A plan replaces the vary flags, it does not continue them** (WP-1208). A staged
  Refine drops a hand-freed row no stage names; `Run this stage` keeps it. `set_aside`
  names that difference.
- **A stage's Rwp is its history node's** (WP-1208), matched to a rung by position and by
  the stage's name, `turn_on` and `turn_off` (WP-2208), else absent.
- **An edited plan keeps the facts of the stages above its first change only**
  (WP-2127, `lib/plan.ts:resolvedPrefix`), and is one pending edit in the shell's action
  bar, never a Save of its own.
- **The advanced boxes loop over `lib/rxt.ts`'s stage words** (WP-1208), so a new schema
  field reaches the form as well as the `.rxt` document.

## Model: projects, import, structure and forms

`panels/Model.svelte`, `lib/model.ts`, `lib/wizard.ts`, `panels/Browse.svelte`,
`panels/Start.svelte`, `panels/NewProject.svelte`, `panels/FileMenu.svelte`,
`lib/filemenu.ts`, `src/rietx/gui/imports.py`, `src/rietx/gui/symmetry.py`,
`src/rietx/examples.py`.

- **If the parameter table has the path, the parameter table owns it** (WP-1014). A
  value goes through `PATCH /api/params`; a species, label, atom added or removed,
  geometry, wavelength or background family goes as a whole validated model.
- **The editor offers DOFs, never x/y/z** (WP-1014). A site-symmetry violation is
  unrepresentable; a fully fixed site gets no control. `GET /api/structure`'s `sites`
  arm says which, without the Wyckoff letter.
- **A coordinate is typed and the site answers** (WP-1215). `POST
  /api/structure/position` least-squares a whole position onto the site's basis and
  refuses an unreachable one, naming the allowed directions and the nearest position;
  never snapped. It is a `set_value` node. The client computes none of it.
- **A preview is a judgement where it can be** (WP-1014): a pattern names its reader in
  the reader's words; `aniso_available` is measured by a second read with `aniso=True`;
  `instrument_hint` is matched server-side (`imports.suggest_instrument`) and is `null`
  when name and wavelength disagree, leaving the form alone.
- **What costs a second walk gets its own route**, fetched when the control opens:
  `GET /api/upload/pattern/scans` (WP-1014).
- `POST /api/structure/aniso` exists because both directions are physics (WP-1014).
- `axialWarning` stays silent on the shipped 0-and-held S/L = H/L default (WP-1014).
- **The `structure` argument's forms are told apart by disjoint keys at one boundary**
  (WP-1206, WP-1207): `phases`, `cif`/`upload`, `space_group`, and `null`. A new form is
  added at `_as_structure`, which reaches `project_new` and `PATCH /api/structure` alike.
- **A typed cell builds the Le Bail scaffold Adopt lands**
  (`schemas.structure.lebail_scaffold`, shared with `structure_from_candidate`), and
  **carries only what the setting leaves free** (WP-1206):
  `crystallography.symmetry.free_cell_names` decides, the route serves it, the form draws
  those boxes. A determined parameter is refused, never tolerance-checked or ignored.
  `mode` is refused at `rietveld`, never overridden; the form disables that option.
- **Null is an answer; an absent key is not** (WP-1207). `project_new` requires the key,
  and only explicit `null` makes a phase-free project. Its mode moves nowhere; Adopt sets
  it. The refusal is on the run verbs, never on the model: `Structure` takes `phases=[]`, so
  peak picking, indexing and `PATCH /api/structure` work on one.
- **An example project is a `compare.py` standard** (WP-1204). `list_examples()` is
  `STANDARDS` filtered by `src/rietx/data/examples/`. The open verb ends in
  `project_open`. Examples build into `state_dir/examples/`. `example_reset` is the one
  destructive verb; `built` rides on the listing.
- **Browse is one modal, two jobs** (WP-1205): `mode="open"` opens a `.rex`,
  `mode="pick"` hands a directory to New project's Where field (a browser can say where
  a project lives, never name it).
- **The start screen keeps a moved recent project listed as `missing`**, with Locate…
  and Remove (`POST /api/recent/remove`) (WP-2131).
- **New project's mode follows the phases, never asked** (WP-2131): a typed cell gives
  Le Bail, so WP-1206's `rietveld` refusal stays unreachable.
- **An assumed instrument is tagged `assumed` wherever it is shown** (WP-2131): unmarked,
  a wrong anode moves every cell.
- **A File-menu rename or move keeps the session's `Project`** and repoints the two paths
  a live one holds, `Project.path` and `RefinementTree.path` (WP-2133). A third such
  field joins `src/rietx/gui/session.py:GuiSession._relocate`.
- **A File-menu destination passes `GuiSession._browsable_folder` and `_project_name`**,
  never sanitised, and an existing folder is refused, never replaced (WP-2133).
- **Close is a `closed` mark on the recent list's head**, which
  `src/rietx/gui/session.py:GuiSession.reopen_last` reads (WP-2133).
- **Symmetry has two tiers, split by cost** (WP-1035). Phase facts ride on
  `GET /api/structure` as `symmetry` + `causes`; Wyckoff letters are on
  `GET /api/structure/symmetry`.
- **`causes` names the symmetry and is silent where symmetry is not the subject**
  (WP-1035).
- **A space-group preview is a diff of two `ParameterTable`s and duplicates no rule**
  (WP-1035); per-atom probes run one atom at a time against a real table.
- **The gate is `Refinement.edit`'s** (WP-1035; root § Invariants). `GuiSession._edit` adds
  only the address: the refusal's leading dot-path.
- **The notes cover what a table diff cannot see** (WP-1035): a setting or centring change,
  `_free_paths` casualties, an orbit collision, the orbit multiplicity. A blocked preview
  has no consequences. A shared orbit is judged as a group by summed occupancy over the
  coincidence relation's connected components; over 1 blocks, and at or under 1 it is a
  legal mixed site. An occupancy the user typed is never rescaled to fit (TOPAS's
  `occ_merge` is declined).
- **A form's column count is a promise nothing else decides** (WP-1216): three, from
  `PROFILE_ROWS`; a control whose content is a word takes the row (`.fullrow`).
- **Which group a field is in is data, never its path's prefix** (WP-1216). A group with
  no field is not drawn, which is why the background is not one.
- **A cell is a `subgrid` of its group's rows** (WP-1216), spanning by content
  (`:has(.varyline)`), never by a class on the grid.
- A rule aimed at a value reaches the control beside it (WP-1214).

## Structure viewer

`src/rietx/gui/structure3d.py`, `lib/structure3d.ts`, `lib/gl3d.ts`,
`panels/Structure3D.svelte`, `src/rietx/viz/figure3d/scene.py`.

- **The viewer is the Model pane's third column**, never a tab (WP-1015).
- **Everything hard stays on the server** (WP-1015). The payload is Cartesian points,
  3×3 matrices and index pairs; the browser draws `pos + M·v` over one unit sphere.
- **`symmetry.expand_orbit` returns the operation with the position** (WP-1015): an image
  drawn with its parent's tensor is wrong on every non-cubic site.
- **gemmi has no colour table** (WP-1015). Colours are the CPK convention with values
  chosen here (ATTRIBUTION.md), never transcribed.
- **A radius-sum bond rule needs a chemical predicate and a floor** (WP-1015, WP-1466,
  WP-1468). Bond a metal to a cation only when the phase has no non-metal (cations are
  `_cation_sites`). `structure3d.split_floor` reads `SPLIT_FLOOR` and
  `METAL_SPLIT_FLOOR`; below it two atoms are one split site.
- **A non-positive-definite tensor draws its non-positive axes at zero on the server**;
  the client keeps such a column at `FLAT_AXIS` (WP-1015).
- **Bond segments complete their partners exactly one level** (WP-1015).
- **Drawing thresholds are on the query string, never in `ProjectDoc`** (WP-1015,
  WP-1468): `probability`, `bond_tolerance`, `disorder`, `centres`, `ligands`.
- **Polyhedra are chemistry, so the server builds them** (WP-1466). A rule change re-runs
  `docs/wp/1466-measure/measure.py`, which writes the picture the tests hold. A legend
  switch is as fine as the default it restores; a hidden polyhedron hides its
  `vertex_only` atoms.
- **Where principal values are equal the server pins the free axes**
  (`structure3d._pin_axes`, WP-1462), once per site, turned by each image's M·R·M⁻¹.
- **The scene rules have a Python twin** (WP-1470): `rietx.viz.figure3d.scene` ports
  `buildScene`, `shownPolyhedra`, the views and `LOOK`, held equal by `scene_cases.json`.
  Change both in one commit.
- **The look is crystallography's** (WP-1015): parallel projection; no Cartesian axis
  box, the cell's a/b/c edges labelled at a clearance in Å; two-tone bonds in Å, a half
  belonging to its atom; `STICK_RADIUS` a lower bound on `BALL_FRACTION`, pinned by test;
  a trackball with no up vector (`cartesian_basis` puts c ∥ ẑ); three principal ellipses
  for an anisotropic site in ellipsoid mode, none for an isotropic one.
- **An exaggeration is not a probability** (WP-1029): `caption()` states the level and
  the multiplier separately. `stickRadius` returns half the smallest semi-axis in
  ellipsoid mode.
- **Distinguishability is a property of the set drawn** (WP-1029): `_CPK` is an element
  table, `phase_palette` picks a picture's colours in OKLab (anchors → table → derived).
- **The renderer draws a `Scene` from a `View`, both pure functions of
  `lib/structure3d.ts`** (WP-1462). Rules: every atom and bond half is a ray-cast quadric
  on one instanced quad; hover solves the shader's equations on the CPU (`pickAtom`,
  `pickHalf`) and names the hit in a readout line; impostor outlines go through
  alpha-to-coverage, so the canvas is opaque and a transparent export renders twice (on
  black and on white); a line is a quad with a width in CSS pixels; the PNG is its own
  render at `EXPORT_LONG_SIDE`, letters drawn in; one context for the canvas's life;
  faces blend back to front, never through coverage (WP-1466).
- **A first-show time is read off screenshots, never off the draw call** (WP-1462):
  Firefox presents after compiling the shaders.
- `--line` is invisible in a 3D scene, so the cell frame takes `--accent` (WP-1462).

## History and report

`panels/History.svelte`, `lib/history.ts`, `panels/Report.svelte`,
`src/rietx/report/apply.py`.

- **An applicable action is one stage** (WP-1012). `stage_for` returns a `StageSpec`, so
  applying travels the per-stage Run path: one `run_stage`, one node, the same 409.
  Undo is a `checkout`.
- **The action's own `parameter_paths` are the globs** (WP-1012). `RECIPES` declares only
  how each `ActionKind` is carried out (`stage`, `index` or `advice`), pinned complete
  against `get_args`.
- **Applicability and reachability are different questions** (WP-1012). `unreachable`
  separates a glob matching nothing from one whose every match is held.
  `GET /api/report` serves `apply` positionally parallel to `suggested_actions`.
- **`expected_delta_chi2` is one number per report** (WP-1012): print it once, saying it
  bounds only the misfit inside the gated regions.
- **The two `unmatched` kinds are opposite diagnoses** (WP-1012): an observed peak with no
  reflection is an impurity; a calculated peak with no intensity is a mispositioned model.
- A `checkout` clears the result server-side; the panel redraws from the curves route
  (WP-1012).
- **An edge holds a lane for its whole span** (WP-1217, `edgeSegments`); only a second
  parent is dashed.
- **Lanes are half a palette in each place** (WP-1217): `LANE_HUES` in `lib/history.ts`,
  lightness and chroma per theme in `app.css`, the distance in `test_gui_palette.py`.
- **A format is declared per family and its width is a promise the formatter keeps**
  (WP-1217). `PLACES` is keyed by `rietx.help.PARAMETER_HELP`'s globs and crossed against
  `help_keys.json` both ways; `formatSide` goes exponential past `VALUE_CHARS`. The widths
  are stated once in TypeScript as `--w-val`/`--w-pct`/`--w-path`. Below the sidebar's
  clamp the row scrolls; the path column gives, drawn `rtl` so its leaf survives.
- **A difference is given twice and the percentage is of |a|**, at three significant
  figures (WP-1217).

## Series

`src/rietx/gui/series.py`, `panels/Series.svelte`, `lib/series.ts`, `lib/stream.ts`.

- **A series lives beside the project, not inside it** (WP-1016). Its protocol is quoted
  from `project.json`, never offered. A persisted series needs a document (WP-1003's).
- **The order is the series** (WP-1016): every edit is a whole-list `PUT`, each new file
  read there; a member already described is not re-read.
- **The walks' disagreement is the record's number, read and never recomputed** (WP-2003):
  `SeriesResult.direction_gaps`; `series.trajectories` serves each path's largest.
- **The list opens in the series' own order; a gap ranking is the reader's choice** (the
  maintainer's ruling 2026-11-04, `lib/series.ts:rankTrajectories`).
- **A per-pattern tree is read-only here** (WP-1016); the root's
  `series_warm_start_node` note makes the chain navigable. `session.tree_payload` is the
  shared tree serialiser.
- **`_SeriesStream` stamps keys onto existing event kinds** (WP-1016; root § Series):
  `series_index`/`series_label`/`series_n`/`series_pass` on every event, and
  `series_rung`/`series_cold` on a restart. `EVENT_SCHEMA_VERSION` does not move.
  `lib/stream.ts` folds them into one `[T300 1/3 ↩]` prefix.
- **A rotated axis title shares the fixed left margin, so the axis takes the leaf**
  (WP-1016).
- **The staged table's floor is per column**, reflowed by `lib/resize.ts:seriesCompact`
  (WP-1016).

## The manual

`docs/docs/**/gui-*.md`, `tests/test_gui_manual.py`, `docs/docs/make_screenshots.py`.

- **The GUI is documented; its routes stay provisional by declaration** (WP-1017).
- **Routes and panel names are partitioned both ways** (WP-1017): every route documented
  or excluded with a reason, every tab named, and a chapter naming a route the server
  does not serve fails too.
- **A screenshot is generated by `make_screenshots.py`** (WP-1017), driving this server
  over a shipped example. Its `SHOTS` table is what a chapter may reference. A picture is
  judged by looking. The `*.png` negation in `.gitignore` is asserted.
- **A first-run aid states what is true** (WP-1017): the checklist's steps are derived
  from the project; only the dismissal persists.

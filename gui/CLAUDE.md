# CLAUDE.md — the GUI: gui/ (frontend) and src/rietx/gui/ (server)

Scope: the refinement GUI's rulebook — server contract, `.rxt` text document,
editors, panels, 3D viewer, theming. Loads when a session works under `gui/`;
`src/rietx/gui/CLAUDE.md` is a pointer here. The root CLAUDE.md holds the
pipeline and package-wide invariants; `docs/milestones/v1.0.md` holds the
narrative of how these panels landed; the WP files (1008…1015, 1029) hold the
measured detail behind each rule below.

## Defaults

**Every choice the GUI offers ships a default that suits most phases, and a
setting is for the rest** (the maintainer's rule, recorded in WP-1462). A user
who never opens a drawer sees the conventional picture, such as ellipsoids at
50 % and bonds at 1.15×(rᵢ+rⱼ). A default
is measured across phases and the measurement is kept where the choice is
made. A setting most users would change means the default is wrong.

## House style

**The token *values* are Python and `gui/src/tokens.css` is generated**
(WP-1429, `src/rietx/viz/theme.py`; regenerate with `python -m rietx.viz.theme >
gui/src/tokens.css`, then rebuild the dist). `rietx watch` and `rietx compare`
ship inside the wheel and this workspace does not, so a colour the two Python
pages serve cannot live in `gui/src`; they link a `/tokens.css` route rendered
from that module. `app.css` imports the file and keeps everything that is not a
colour, and `tests/test_gui_palette.py` reads the palette from the module and
holds the committed file equal to the emitter byte for byte.

**One token layer and nine registers** (WP-1201, `gui/src/app.css`). A register
means one thing and is drawn one way everywhere, so **size, padding and radius
belong to the register and never to the call site**: a panel wanting a smaller
button wants a different register, and `app.css` is the one place that argument
can be had. `lib/style.test.ts` fails on a panel that declares any of the three
on a register, and on a `font-size` that is not a step of the scale.

| Register | Means |
|---|---|
| `button` | the one state-changing action in its region |
| `button.ghost` | any other action — same size, only the fill differs |
| `.segmented` | choose one of N views or modes |
| `.tab` | choose one of N panels |
| `.chip` | a fact: a flag, a tag, a grade. **Never acts** — a chip that would is a `button.ghost`, and a verb *on* a chip sits beside it, not inside |
| `.pill` | a live mono readout |
| `.pick` | select this row: a button that has given up its box, because the row is the target |
| `.link` | inline navigation, at the size of the line it sits in |
| `.help` | an explanation is one click away, and the cursor is the whole mark (popover: WP-1203) |

Three type steps and no fourth: `--text` is prose, `--text-sm` is a control
**and everything on its row** (a field's label, a count beside a button, a table
cell), `--text-xs` is a chip and a section heading. "Secondary" is said by
`.muted`, once — `.small`/`.tiny` were saying it as a *size*, in eleven files
at three values. Mono is a family, not a size. A chip's tone comes from one
vocabulary (`note` the default, `ok`, `warn`, `bad`, `accent`) and
`lib/peaks.ts`'s tone functions return members of it. Two cascade traps, both
found in a browser and neither visible to jsdom: a *state* like `button.on` is
`(0,1,1)`, so a more specific rule still loses every property it does not
declare (a selected `.tab` wore the segmented fill); and `text-transform` and
`letter-spacing` inherit into a button, so a label inside a heading wears the
heading's case unless its register says otherwise.

Two rules for anything a person reads here (v1.2, WP-1201/1202/1203):
**GUI prose is written under `/yue-docs-style`** (help entries, wizard lines,
empty states, error text), and **what a name *means* is an entry in
`rietx.help` reached through `<Help>`; `title=` is what is left over.** The
popover is WP-1203 (`Help.svelte`, `lib/help.ts`, one instance in `App`), with
six rules. A key is **`arm:name`**: the arms' vocabularies overlap, so a
bare key would resolve by declaration order; each is crossed against
`tests/data/gui/help_keys.json`. A field inventory **derives** its key from the
field's own name where the arm is keyed by the same vocabulary (`controls.ts`,
`wizard.ts`) and carries it as **data** where it is not (`lib/model.ts`). `<Help
text=…>` is for a sentence the **server** wrote (`held_because`, a refutation, a
maturity message), which no corpus can hold because it is about one row rather
than one name. What may still be a `title=` is a **value the layout truncated**,
or a verb phrase on a `<button>`, never authored prose — `lib/help.test.ts`
holds that to an exact per-file count failing both ways, so the debt stays
countable and its list cannot outlive it. And a term is a `<span
role="button">` because it wraps running text: sound only while it stays
focusable, answers Enter and Space, and is **hittable** — a flex item's
automatic minimum is its content size, which left `.path` at zero width in a
340 px sidebar (v1.2's record has the numbers). It is **named by its
children, never by an `aria-label`**, which renames the `<label>` or `<th>`
enclosing it; `aria-haspopup="dialog"` carries the role hint instead, and the
popover **takes focus**, a `role="dialog"` nobody is in announcing nothing.

The **GUI** (WP-1008, `gui/`) is `rietx gui [PROJECT.rex]` — stdlib
`http.server` on 127.0.0.1, the third such app here after `watch` and `compare`.
`gui/session.py` holds `GuiSession`, where **every verb is a plain method and
nothing knows about HTTP**; `gui/server.py` parses a path, calls one, serialises
the answer, and is the layer a Tauri host would replace. Its route table plus
`RESERVED_ROUTES` (paths settled here, behaviour owed by a later WP, 404 naming
it) are the complete wire surface, held disjoint by test. Four rules: mutating
verbs return **409 while a run is in flight** — frozen-per-stage discreteness
enforced structurally rather than by discipline, and that refusal outranks body
validation; **settings persist on the verb**, not on `save`, which is what keeps
WP-1005's "nothing to warn about on close" true; the **run state is not an
event** (a failed fit emits no `fit_end`, and `EventKind` is closed) so it
travels beside them as its own SSE frame type while `live/events.jsonl` stays the
one stream `watch` tails; and `/api/result` omits the curves, which
`/api/result/curves` sends once over every channel as float64 arrays (WP-1461,
D4), decimating past `CURVES_CEILING` through the *same*
`viz.compare.decimation_index` the comparison UI uses — whose count is a
budget, not a ceiling. `strategy.staged.resolve_plan` (preset name + mode → plan)
is likewise one function, previously inline in `fit` and duplicated in
`sequential`.

The **text document** (WP-1009, `gui/textdoc.py`, `rxt 1`) is the line-oriented
view of a project — settings, plan, and every parameter row, where `@` frees and a
bare value holds. `render` → `parse` → `changes` → `apply`, and the rule that
makes it safe is that **a delta is diffed against the live project, never against
the old text**: an untouched document emits no verbs, a read-only field is an
error only when it *differs* (so everything can be shown without a "look, don't
touch" syntax), and a typed number is compared to the **rendered** value, which is
what lets values render lossily at 12 significant digits. Everything applies
through the same verbs a form calls — same history nodes — and every refusal is
the verb's own words (`held_because`, `TieSpec.describe`) with a line number
attached, never restated. Three grammar facts are load-bearing: a `tie` renders
**last** on its line (it contains spaces, so `=` runs to end-of-line); column
widths are **per block** (a fixed width made the renderer emit
`polarization 0.99min 0`, which its own parser refused); and a **stage line's
keys are derived from `StageSpec`** (`textdoc.STAGE_KEYS`), never listed, so a
new field on the schema reaches the renderer, the parser and — via
`test_textdoc`'s pin against `model_fields` — `lib/rxt.ts` too. Listed, it was
the same tuple in two places, and a field missing from both is not a rendering
gap but a value dropped on every save. An added key is not a `FORMAT_VERSION`
bump, on the events precedent: no line's *meaning* changed. Comments parse but do not
survive a re-render, on purpose: storing one would be a second authority.

The **frontend** (WP-1010) is a Svelte 5 + Vite + TS workspace in `gui/` whose
build output is **committed** under `src/rietx/gui/static`, so installing the
wheel never needs node — and `tests/test_gui_dist.py` is what keeps that honest:
the dist's digest is recomputed in the ordinary (node-free) suite, nothing may
gitignore the dist (the repo-wide `*.html` rule matched its `index.html` once),
the built files must be *in* the wheel, and no built file may name a remote host.
The digest itself lives once, in `gui/scripts/build_info.py`, called by both the
build and the test; `build-info.json` deliberately carries no timestamp, because
`git diff --exit-code src/rietx/gui/static` has to mean "stale", not "rebuilt".
**Which points a payload carries is the server's** (`viz.compare.decimation_index`, past
`CURVES_CEILING` in the curves routes); the chart module paints
each pixel column's extremes of them (WP-1461 D5), what is drawn and never what the
readout reads. No GUI page loads plotly (WP-1462); uPlot and svgcanvas are vendored, into
`src/rietx/viz/static` by `scripts/vendor.py`, the build's first step: bump the pin, build.
**The chart module, uPlot and svgcanvas are chunks off the boot path**, fetched on the first
draw and the first SVG export, so a panel imports them dynamically or by type alone:
`test_gui_dist.py` fails on one inlined into `app.js`, which one static `import {download}`
did without anything else going red (WP-1461).
`npm run build` needs `python3`, `vitest` needs
`resolve.conditions: ["browser"]` or `mount()` comes from svelte's server build,
`@sveltejs/vite-plugin-svelte` must be v7 for Vite 8, and the toolchain needs
**node ≥ 20.12** — rolldown imports `styleText` from `node:util`, an older node
fails at *import* naming neither node nor a version, and `npm ci` under it
leaves a `node_modules` the newer one cannot use (WP-1442).

**`lib/resize.ts`'s cases are copied out, and `gui/src` is hashed whole**
(WP-1425). `rietx watch` cannot import TypeScript, so it ports
`clampSize`/`dragged`/`axisOf` and `tests/test_watch_app.py` compares
`resize.test.ts`'s `ported cases` block against `tests/watch_core.test.mjs` **as
text**, comments included: edit them here and the copy fails until it follows.
`build_info.py` hashes `gui/src/**/*`, test files included, so editing any test
here marks the committed dist stale and costs an `npm run build`.

**Driving a real browser: the chromium binaries are already cached even when
playwright is not installed**, so a browser pass costs an
`npm i playwright-core` **in a scratch directory, never in `gui/`** (it must not
reach the committed lockfile) pointed at the cached executable. Worth the setup
every time: the streak of "every browser session finds a defect jsdom
structurally cannot" is what the traps recorded below are made of. And when a
browser pass reports something impossible, **suspect the harness first** — a
"missing" `window.prompt` echo was headless playwright auto-dismissing the
dialog, not the app.

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
`bind:clientHeight` compiles to, so its absence throws *during mount*) and
`DragEvent`; `gui/src/test-setup.ts` is the one place that gap is filled. It
has no canvas either, and uPlot draws in its constructor, so `test-setup.ts`
mocks `uplot` with `test-uplot.ts`'s `StubPlot`: uPlot's state, the chart
module's hooks fired, and every stroke recorded with the style it was made in,
so **a drawn colour is asserted from the record, never from the option handed
in** (WP-1461). What uPlot paints from it is `tests/test_gui_browser.py`'s
question.

The **history and report panels** (WP-1012) are the GUI's read-and-act half, and
the module that carries them is `report/apply.py` — the *how* beside Layer 2's
*what*, in a separate file because the two version differently (the vocabulary is
a contract; the mapping onto verbs changes when a verb arrives). Four rules.
**An applicable action is one stage**: `stage_for` returns a `StageSpec` and runs
nothing, so applying a suggestion travels the path the per-stage Run button
travels — one `run_stage`, one history node, the same 409 — and *undo is a
`checkout`*, not an inverse verb. **The action's own `parameter_paths` are the
globs**; `RECIPES` declares only how each of the sixteen `ActionKind`s is carried
out (11 `stage`, 1 `index`, 4 `advice`, pinned complete against `get_args`), and
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

The **text pane** (WP-1013, `gui/src/panels/Text.svelte`, `gui/src/lib/`) is the
`.rxt` document in CodeMirror 6, and it is a **mode over the whole window rather
than a sixth tab** — five tabs already fill the sidebar, and this is the one panel
whose content is line-oriented, the format's columns being aligned precisely so a
rectangular selection can hit one field. It stays mounted while hidden (a typed
buffer survives a look at the parameter table) and builds its editor on first
entry. Four rules. **The head is the reload signal** — no third SSE frame type was
added, because the head already moves for every writer and the parameter table
already reloads on it. **There is no merge and no force-apply**: a stale buffer
re-reads and re-applies, which is also what the server's 409 `STALE_REVISION`
says, and the reason is sharper than "merging is hard" — the loser's document
carries the winner's *old* values for every row it did not touch, so applying it
would silently revert them. **Only the server decides validity**: `lib/rxt.ts` has
no `error` token to emit (asserted from both sides, with the shared vocabulary
pinned to `textdoc._KEYWORDS` and `StageSpec.model_fields` by
`test_the_highlighter_quotes_the_parsers_words`), and *indentation is the parser's
own dispatch*, so an indented `plan` is a parameter named `plan`. And **a response
carrying an older `seq` is dropped** — a 300 ms debounce puts two validations in
flight across one pause and they can land out of order. CodeMirror is a separate
committed chunk (`assets/vendor-cm.js`, 328 kB) imported *dynamically*, so it
stays off the boot path; `tests/test_gui_dist.py` asserts the split, because a stray static import would
inline the library and no byte count would say so. The editor's document and its diagnostics are `$effect`s
over the sync state, never pushed — pushing let a head move wipe a squiggle while
the problem list still named the line.

**Import and model editing** (WP-1014, `src/rietx/gui/imports.py`,
`gui/src/panels/Model.svelte`, `gui/src/lib/{model,wizard}.ts`) is how data gets
*in* from a browser and how the model is edited once it is. Its founding rule is a
split: **if the parameter table has the path, the parameter table owns it** — a
cell edge, an occupancy, a Biso, a profile term, a coordinate DOF go through
`PATCH /api/params`, where the tie/lock/mode/bound rules already live, while a
species, a label, an atom added or removed, a geometry, a wavelength or a
background family go as a whole validated model, because each changes what the
table *contains*. Coordinates are therefore never typed as x/y/z (they are affine
ties onto `…dof.k`); the editor offers the DOFs, so a site-symmetry violation is
unrepresentable rather than refused, and a fully fixed special position gets no
coordinate control at all — `GET /api/structure`'s **`sites` arm** is what says
which is which, deliberately without the Wyckoff letter (spglib per atom on a
route that refetches on every head move). Uploads are **two-phase** — a file is
staged and read before anything is created, and only an opaque token crosses back,
never a path — and they are the one route family whose body is not JSON (raw
bytes; filename and reader options in the query string, `UPLOAD_ROUTES`). Two
previews are judgements rather than descriptions: a pattern names the *reader*
that claimed it in the reader's own words, and a CIF's `aniso_available` is
**measured** by reading it a second time with `aniso=True`. A pattern preview
also carries an `instrument_hint` — the anode and goniometer radius its header
already states, matched **server-side** (`imports.suggest_instrument`) because
deciding that 1.5418 Å is a Cu doublet is a physics judgement against the
package's radiation table, and a client-side match would be a second copy of that
table in TypeScript; a header whose name and wavelength disagree sends **null**,
and the form is then left alone, because a wrong pre-fill looks like it was read.
The scan picker splits the same way for a different reason: `scan_count` rides
along in the preview's metadata from the read that already happened, while
*labelling* the scans costs a second walk of the ranges, so it is its own route
(`GET /api/upload/pattern/scans`) fetched when someone opens the control. `POST
/api/structure/aniso` exists because both directions are physics
(`AnisoU.isotropic` on, U_eq → Biso off). Three browser-only traps are recorded in
code: `structuredClone` **throws on a Svelte 5 `$state` proxy** (use
`lib/model.ts:clone`), a verb's refusal and a panel's load error **must not share
one field** (the reload after a failed apply wiped it), and `axialWarning` stays
silent on the S/L = H/L pair that is 0-and-held, because that is the shipped
default and a warning on every fresh lab instrument is a warning nobody reads.

The **structure viewer** (WP-1015, WP-1462; `src/rietx/gui/structure3d.py`,
`gui/src/panels/Structure3D.svelte`, `gui/src/lib/structure3d.ts`,
`gui/src/lib/gl3d.ts`) is the model as drawable geometry, served by
`GET /api/structure3d` and drawn by the viewer's own WebGL2 renderer, **no
library** (plotly cost 4.8 MB for it, three.js would have cost 139 KB gzip, this
costs 6.2 KB). A third column of the model pane rather than a sixth tab. Its
founding rule is that **everything hard stays on the server**: the payload is
Cartesian points, 3×3 matrices and index pairs, and the browser's whole job is
`pos + M·v` over one unit sphere, which is also why a ball and an ellipsoid are
one code path. That forced the one new crystallography verb:
**`symmetry.expand_orbit` returns the operation as well as the position**,
because U\* → R·U\*·Rᵀ means an image drawn with its parent's tensor is right on
a cubic site and wrong on every other one; `expand_positions` now delegates to
it. Four rules. **gemmi has no colour table** — it supplies radii and
`is_metal`, and the colours are the CPK convention with values chosen here
(ATTRIBUTION.md), never transcribed. **A radius-sum bond rule needs a chemical
predicate**: bond a metal to a cation only when the phase has no non-metal in
it, or LaB6's cell edges become La–La sticks and forsterite grows Mg–Si ones
(a cation is `_cation_sites`', WP-1466), and **a floor, between non-metals only**
(`SPLIT_FLOOR`: a split pair sits under it, and uranyl's U=O would too). **A non-positive-definite tensor draws its non-positive axes at
zero** on the server (a √ of a negative is a NaN), and the client keeps such a
column at `FLAT_AXIS` = 1 mÅ because the ray-caster solves through M⁻¹. And
**bond segments complete their partners exactly one level** — a bond to a
translated image is correct and *reads* as broken — which is the line between a
coordination and the packing diagram this WP declined. `probability` and
`bond_tolerance` are drawing thresholds on the query string, never in
`ProjectDoc`. **Polyhedra are chemistry, so the server builds them** (WP-1466):
cation centres, anion ligands (`_cation_sites`). A rule change re-runs
`docs/wp/1466-measure/measure.py`, writing the default picture the tests hold.
**A legend switch is as fine as the default it restores** (per formula, since
P5 is per shell size), and a hidden polyhedron's `vertex_only` atoms hide too.

Its **look** (the second pass, 2026-07-30, read against VESTA, Jmol and
3Dmol.js) is crystallography's rather than a plotting library's. **Parallel
projection** (perspective converges a cubic cell's far edges), **no Cartesian
axis box** (the cell's own a/b/c edges are labelled instead, at a clearance in
Å set by the largest ball — a percentage of the edge put every letter inside a
corner atom), and **bonds as two-tone cylinders in Å**, which settles the legend
rule *a half belongs to its atom*. `STICK_RADIUS` = 0.08 Å is a lower bound on
`BALL_FRACTION` = 0.40 (VESTA's fraction, on covalent rather than atomic radii),
pinned by test so hydrogen cannot become a lump on a rod. **The trackball has no
up vector to pin**: `cartesian_basis` is upper-triangular, so c ∥ ẑ for every
orthogonal cell, and a turntable's +z would make "view down c" degenerate — the
free rotation and the a/b/c buttons are one decision. In ellipsoid mode an
anisotropic site draws its **three principal ellipses**, one unit-frame
coordinate near zero since T's columns are the principal axes, and an isotropic
site draws none, its axes pointing nowhere. **Where principal values are equal
the server pins the free axes** (`structure3d._pin_axes`), because `eigh`
chooses them per LAPACK build: a Mac and an x86 runner drew one uniaxial site's
rings as an X and a + (WP-1462's gate). It pins a site once and turns that T by
each image's M·R·M⁻¹, so equivalent atoms wear equivalent rings.

The **renderer** (WP-1462) draws a `Scene` from a `View`, both built by pure
functions in `structure3d.ts`, and knows nothing else. Eight rules.
**Every atom and bond half is a ray-cast quadric** on one instanced quad, exact
at any zoom and export size (the practice of Mol\* and NGL; WP-1462 § The field).
**Hover solves the shader's own equations on the CPU** (`pickAtom`, `pickHalf`,
12-61 µs an event), and says what it hit in a readout line under the canvas,
WP-1213's rule for the pattern carried over. **An impostor's outline is a
`discard`, which MSAA does not smooth**, so each shader computes its coverage
and hands it to alpha-to-coverage — which writes coverage into the samples, so
**the canvas is opaque**, cleared to the panel's own background, and a
**transparent export renders twice**, on black and on white, taking alpha from
the difference. **A line is a quad with a width in CSS pixels** (`gl.LINES` is
one device pixel: half a CSS pixel at DPR 2, a hairline in an export). **The PNG
is a render of its own**, offscreen at `EXPORT_LONG_SIDE` = 3000 px and
multisampled, and the a/b/c letters, which are DOM on screen, are drawn into it.
**One context for the canvas's life**: the mount effect depends on the canvas
and nothing else, calling `rebuild` under `untrack` — called bare, it read the
geometry, every payload re-ran the effect, and its cleanup's `loseContext` left
the canvas holding a dead context that drew Chrome's sad face (jsdom's stand-in
loses nothing, so `test-gl3d.ts` now counts a renderer made on a dead canvas).
**Firefox presents the first frame only after compiling the shaders**, some
hundreds of ms after the draw call, so a first-show number is read off
screenshots, never off the call. And **faces blend, never through coverage**,
whole polyhedra back to front; only a translucent export pixel proves a face
painted (WP-1466). Under test, `test-setup.ts` mocks
`lib/gl3d`'s `createRenderer` with `test-gl3d.ts`, which records every scene
and view; `--line` is invisible in a 3D scene, so the cell frame takes
`--accent`; and pictures are compared, never a sha256 of one.

**Usability** (WP-1029, `gui/src/lib/{resize,theme,plot}.ts`,
`panels/Splitter.svelte`, `gui/structure3d.py`) is the pass that made the eleven
correct panels one program, and its findings are rules rather than repairs.
**A stored size is not a settled size**: a drag clamps against the extent it
happens in, and nothing clamps a width that outlives its window — so
`fitColumns` re-clamps at *render* (widths chosen at 1500 px reopened at 1000 px
left the 3D column 24 px wide). The splitter itself carries `Console.svelte`'s
rule generalised — **report a size, never write one**, `onsize(size, done)`,
persisted to `ProjectDoc.ui` on the verb — with an `inline` flow because an
absolute grip inside `overflow: auto` scrolls away from the edge it is meant to
be. **Distinguishability is a property of the set being drawn**: `_CPK` is an
element table, `phase_palette` decides what a *picture* uses, anchoring the
famous CPK assignments and rotating the rest in **OKLab** hue at constant L and
C — sRGB has no distance, and F `#48d860` against Ca `#40c060` (both in NAC) is
0.070 apart against a 0.13 floor. Placement is anchors → table → derived, so the
hue nobody chose is the one that moves. **An exaggeration is not a
probability** — k(p) = √χ²₃(p) diverges as p → 1, so `caption()` states the
level and the multiplier separately or the picture claims a surface it is not
drawing — and **a stick knows which mode it is drawn in**: `stickRadius` returns
half the smallest semi-axis in ellipsoid mode (0.080 Å ball → 0.065 at p = 0.5 →
0.032 at p = 0.1, where the fixed stick had been *wider than the atom*), which
turns `unitCylinder`'s uncapped justification into a proof. The theme is
three-way and resolved **once**, stamped as `data-theme` on the root, because
"follow the system" is a choice and not the absence of one; CodeMirror's chrome
must be an `EditorView.theme` rather than a stylesheet rule, since CM injects
its own as `.ͼ1 .cm-gutters` and wins on specificity. The curves route sends
**three** residuals and a `weighted` flag: two are derivable in a client and
`cumulative_chi2` is not, because it is summed over every fitted channel, and a
zoom re-bases that one sum (`rxplot.chi2Base`) rather than summing what it
holds. A chart is sized by the `ResizeObserver` the chart module keeps on its
host (`rxplot.panes`), because uPlot has no autosize: a panel sizes the host
and never the chart.

**Repairs found by use** (WP-1032, `lib/resize.ts`, `lib/plot.ts`,
`panels/{Plot,Peaks,Structure3D}.svelte`) is the pass that measured what the
eleven panels *feel* like, and its rules are about how to find such things.
**A trailing canvas is not a dropped frame**: chunked work behind an
un-coalesced `ResizeObserver` costs *latency*, not jank. Under plotly a drag
issued one ~111 ms resize per pointer move and the last landed 1.10 s late at a
steady 60 fps, so measure when the final size lands, not the frame rate. The
chart module's `setSize` runs in the observer's own frame and the viewer asks
for one `requestAnimationFrame`, so neither queues, and `resize.ts:coalesce`
went with plotly (WP-1461). **Instrument before the library loads**: a
`$state` rune proxies a namespace and caches each property on first read, so a
probe patched in after boot counts nothing while the chart redraws (it was
`window.Plotly`) — use an init script. **A fix that does not remove the symptom is evidence about the cause**:
the sticky peak header's backdrop is opaque and the panel column's missing
surface was a real, separate mismatch; what paints a row over the header is
`opacity: 0.55`, which promotes it to z-index 0 while the sticky `th` sat at
`auto`. Three rules about what a plot may say: **a tick belongs to the model,
not the residual** (a band of its own between the two — on the residual's axis
its visibility was a property of which residual was chosen), **hiding a
curve is by exception** (`curveToggles`/`hidden`, unpersisted, so a curve a
later build adds arrives drawn), and **a hover link never repaints the
pattern** — the ring is a DOM mark over the canvas (WP-1461; under plotly it
was one `restyle` of a two-point trace). Right-click **removes** a
peak (refit stays on the table's `↻`; the `window.prompt` is gone), and the
gestures are stated whenever the Peaks tab is up, each naming its non-pointer
route. **No mute fields**: every `PresetField` and every `instrumentFields()`
entry is described, pinned by a meta-test over every geometry — ten were mute
the day it was written. WP-1203 retargeted it from `title=` to a corpus key.

**What is fitted, shaded and selectable** (WP-1033, `lib/plot.ts`,
`panels/Plot.svelte`, `session.result_curves`, `Project.fitted_mask`) is the fit
range and the excluded regions made visible, and its founding measurement is
that **a mask is invisible in a picture of its own output**: `compile_model`
masks before a result exists, so both payloads carried only the surviving
channels — a band would have shaded a hole, and a fit range had no *outside* at
all, the axis autoranging inside it. So the masked channels travel beside the
fitted ones (the curves payload's `kept`) and `Project.fitted_mask` is the one
authority for which channels the next run fits, pinned to `compile_model` by
asserting `len(result.two_theta)` against it. Four rules. **Protocol is not a
drawing choice and may not wear its clothes** — the residual selector and the
scale are session-local and unpersisted, while a region changes Rwp and persists
on the verb, so it lives in a strip of its own with typed fields and chips, and
that strip carries the **channel count**, because a band drawn over points still
in the residual is worse than no band. **Settings persist on the verb and curves
move only on a run**, so between the two the picture contradicts the setting: the
route says `stale` by comparing the fitted 2θ *values*, not their count. **The
shading spans every pane's full height and is clipped to the measured extent**
— full height because a rectangle in log space is not the rectangle in linear
space, and an excluded channel is missing from the residual too; clipped
because outside the measured pattern there is nothing to exclude (under plotly
a shape took part in the autorange, and bands drawn past the data *became* the
range: −40 to 100 on a 0.5–59.99° pattern). And **a new pointer
meaning that is ambiguous everywhere is a mode, not an arbitration**: WP-1027
could make the peak grab radius readable because the ambiguity was local, but a
region drag is a zoom drag at every distance — so arming is explicit, hands the
drag to the chart's select mode (x only, zooming nothing), *suspends* the peak
verbs, and disarms after one selection. `viz/` deliberately does not shade (grounds in the WP): a result
cannot say what was excluded, so the exported figure shows it as absence.

**One column, eight panels** (WP-1034, `App.svelte`, `Model.svelte`,
`lib/resize.ts`) is where the panels live: Model and Text stopped being modes
over the window and became tabs beside the plot, and the full-window surface
they had is now **the column expanding, tab strip and all** — one hatch for
eight panels instead of two, with the header's `Split | Full` the only control
for it (session-local: a layout is a view choice, not a setting). Five rules,
each a measurement in the WP. **A panel's minimum width is measured, not
chosen** — the atom table's `min-content` is 448 px (+24 padding), the `.rxt`
document's *editable* columns end at 546 px with the gutter and its trailing
comments at 756, against a sidebar that clamps at 340–560 and drags to 72 %: so
WP-1013's "a narrow sidebar undoes the alignment" is true at the floor and false
at the ceiling. **A column that must not lose gets a flex *basis*, not a share**
— equal `flex: 1 1 0` gave the structure column 306 px of a 1000 px pane while
the columns needing less had plenty, and a basis is not a maximum, so a drag
still overrides it. **Overflow is wrap, never truncation, and it applies to the
header too**: no tab label is shortened, the buttons do not grow (a lone wrapped
tab stretched into a banner), and the header wraps because at 860 px it had
pushed `Cancel` and `⌘K` past the window's edge — a wrapping row breaks on its
items' *bases*, so anything meant to ellipsise instead needs `flex-basis: 0`.
**A statistic outlives the thing it describes**: an edit discards the curves
server-side, but the run frame keeps its Rwp, so the header printed a fit's Rwp
beside a plot saying there was none — the frame is the source only while a run
is in flight. That class of bug is invisible until two panels share a screen,
which is the argument for tabs restated as a defect. And **opening another
project replaces the session's** with no prompt and no dialog: settings persist
on the verb and the log is on disk, so there is nothing unsaved, and a run in
flight is already refused by `project_open`'s 409. **There is no read-only way
to open one** — every verb writes into the directory and `Project.open` appends
a head annotation before any verb runs — so looking without changing means a
copy: `rietx gui --scratch` (byte-for-byte, temp dir), `--state-dir` to put the
recent list somewhere else, and `*.rex/` in `.gitignore` (WP-1204).

The **examples** (WP-1204, `rietx.examples`; `GET /api/examples`, `POST
/api/examples/open`, `POST /api/examples/reset`) are the empty state's other
list, for the person who has nothing of their own to open. Six rules. Upstream
of the route, **an example project *is* a `compare.py` standard**
(`src/rietx/examples.py`), so no protocol is restated here —
`tests/test_compare_ui.py` already pins those to the acceptance suites, and
`list_examples()`'s membership is `STANDARDS` filtered by what is in
`src/rietx/data/examples/`, so a file added to the wheel adds an example. An
**example is a project like any other from the moment it exists** — the open
verb *ends in* `project_open` and returns exactly what it returns, so nothing
downstream can tell. They build into **`state_dir/examples/`**, for the reason
`recent.json` lives there: an example is a project the person then edits, while
package data is read-only, shared between environments and replaced by the next
upgrade. `name` arrives in a request body and is joined into a path, so it is
**checked against the example list, never sanitised** — a membership test
cannot be escaped, and `example_reset` is the one destructive verb on this
surface. `built` rides on the listing because a first click is not free (the
11-BM example copies and re-reads 2.5 MB) and the empty state has to be able to
say so. And **a `.pick` row has to carry its own hover**: the register gives up
its box because the row is the target, so a list that gives the row no
background reads as prose that happens to be clickable — found in the browser,
and invisible to jsdom, which has neither hover nor cursor.

**The filesystem browser** (WP-1205, `GET /api/fs`, `Browse.svelte`) is the
empty state's third way to reach a project, beside the recent list and the
examples: read-only, confined to `Path.home()` and the process's cwd, and not
behind the 409 like `/api/recent`. **The gate is containment, not a
blocklist** — `path` is resolved (symlinks included) before it is checked
against the two roots, the same shape `GuiSession._export_target` already used
for the exports directory. Browse is **one modal, two jobs**: `mode="open"`
opens a `.rex` entry, `mode="pick"` hands a plain directory back to the
wizard's path field, keeping whatever basename was already suggested (a
browser cannot name a new project, only where it lives). **`Model` is mounted
exactly once in `App.svelte`**, never one instance per branch of
`{#if project}`: two instances is two independent `wizardOpen`s, and opening a
*different* project from the tab-mounted instance's wizard used to leave it
painted over the freshly-opened one, because `project` stayed truthy the whole
time and Svelte never tore the stale instance down. And **every opener settles
`wizardOpen` on success through one function**, `Model.svelte`'s `openPath()`
— the recent list's own handler never did, which is what let the bug ship.

**A project without a CIF** (WP-1206, `GET /api/spacegroup`,
`session._typed_cell_structure`, `lib/wizard.ts`) is the wizard's second answer
to step 2: a symbol and a cell, built into the same Le Bail scaffold Adopt lands
(`schemas.structure.lebail_scaffold`, shared with `structure_from_candidate`).
Four rules. The `structure` argument has **four forms told apart by disjoint
keys** — `phases`, `cif`/`upload`, `space_group` — and the typed one's `cell` is
an **object keyed by parameter carrying only what the setting leaves free**:
`crystallography.symmetry.free_cell_names` decides, the route serves it, and the
form draws the boxes it names, so a `b` under `P 4/m m m` is unrepresentable
rather than refused — WP-1014's coordinate-DOF rule one parameter family over,
and TOPAS's `Tetragonal(a, c)` shape (concept only). A determined parameter is
**refused, never tolerance-checked and never ignored**: a tolerance on a *length*
is a constant nothing else here needs, and ignoring is what a six-number route
does — under `P 4/m m m` a typed `b` was tied away by `ParameterTable` and the
number read back was never the one entered. `mode` is **refused at `rietveld`,
not overridden**, the form disabling the option so the refusal is unreachable —
Adopt sets the mode because there the caller chose a *candidate*; here they chose
a mode — and it is refused at **both** routes `_as_structure` serves, since a new
form added at that one boundary reaches every verb crossing it (`project_new` and
`PATCH /api/structure`, where a scaffold would otherwise leave a rietveld project
refining a dummy carbon). And two browser facts about drawing a form, both
invisible to jsdom: a
**register's width is the call site's** (`.segmented` is `display: flex`, so in a
block parent it stretches to the whole column — every other use in the app sits
in a flex row already), and a **placeholder that is a plausible number reads as a
value somebody filled in**, which is why the instrument form's say `default`, a
word; where there is no default to name, the honest placeholder is none.

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

**Symmetry, surfaced and editable** (WP-1035, `src/rietx/gui/symmetry.py`,
`gui/src/lib/symmetry.ts`) is the phase's space group stopping being one
read-only string quoted in three places while everything it *does* — a tied `b`,
a locked angle, two DOFs instead of three — showed in the parameter table as an
effect with no named cause. Five rules. **Two tiers, split by a measurement**:
the phase facts are one `get_spacegroup` call, so they ride on `GET
/api/structure` beside `sites` as `symmetry` + `causes`, while a Wyckoff letter
is spglib per atom (**1.8-8.7 ms**, measured, and an orbit expansion is another
0.4-1.3) and lives on the deliberately-opened `GET /api/structure/symmetry` — the
escape that route's own docstring had already named. **`causes` names the
symmetry and stays silent where symmetry is not the subject**: it supplies the
missing subject of `held_because`'s "structurally fixed by symmetry **or by the
model**", so a locked `lor_strain` (the Stephens block's) keeps the anonymous
version rather than getting a wrong cause. **The preview is a diff of two
`ParameterTable`s and duplicates no rule** — the raises *are* the incompatibility
list, nearest-allowed values included, and since a table stops at the first bad
item the per-atom pass probes one atom at a time against a *real* table rather
than parsing a sentence this package owns elsewhere. **The gate is
`Refinement.edit`'s, not this layer's** — the failure was never a GUI one, so it
was fixed where it lived (root CLAUDE.md), and all `GuiSession._edit` adds is the
**address**: the refusal's leading dot-path, which a form needs to highlight the
field. And **the notes are for what a table diff structurally cannot see**: a
setting change, a centring change, `_free_paths` casualties (dropped *and*
renumbered — `…dof.k` is positional), an orbit collision, and the **orbit
multiplicity**, which a browser found by taking NAC from `I 21 3` to `I 41 3 2` —
same orders, same DOFs, same ties, same centring, empty diff, and 84 atoms in the
cell becoming 168. Two corollaries: a **blocked** preview is given no
consequences at all, since they would be computed from operators the model cannot
carry; and **a shared orbit is judged as a group, by its occupancies**. Atoms the
symmetry merges are one *site*, so the members are the connected components of
the coincidence relation and the verdict is the sum over the whole group — three
atoms at 0.4 are over-occupied where no pair of them is, which makes pairwise not
a coarser answer but a wrong one. Over 1 blocks; at or under it the same geometry
is a legal mixed site and F is right for it. **No prior art to copy, checked**:
GSAS-II recomputes every site symmetry on a space-group change
(`G2spc.UpdateSytSym`) and runs no such check, and TOPAS's `occ_merge` rescales
occupancies continuously during *structure solution* rather than refusing an edit
— deliberately not copied, because it silently rewrites a number the user typed,
which is the objection that made `check_cell_angles` refuse rather than
normalise.

The **series panel** (WP-1016, `src/rietx/gui/series.py`,
`panels/Series.svelte`, `lib/series.ts`) is the ninth tab and the only one whose
subject is a *method* rather than a model: N separate refinements chained by a
warm start, so **a smooth curve is exactly what a poisoned chain produces** and
the presentation is built around that. Five rules. **A series lives beside the
project, not inside it** — staged uploads, in-memory trees, a session-scoped
answer, `ProjectDoc.patterns` still length 1 — and its protocol (mode, plan,
limits, exclusions) is *quoted* from `project.json` rather than offered, because
one protocol over N specimens is what makes their trajectories comparable. That
is not a shortcut: an upload token dies with the session, so a persisted series
needs a document, which is WP-1003's to decide. **The order is the series**, so
every edit is a whole-list `PUT` and every file is read *there* (WP-1014's
two-phase property at N files) — with a member already described not re-read,
since a staged upload is immutable and re-reading forty patterns per keystroke
proves nothing. **`SEQUENTIAL_PATH_DEPENDENT` is a banner, and its magnitude is
computed rather than carried**: a `Diagnostic` has `where` and no number (the
wall WP-1012 hit), and both chains' trajectories are in hand, so
`series.trajectories` recomputes the fence's own combined-σ distance and serves
it — a panel ranks by disagreement with no schema change. **Ranking stops where
the fence stops**: on a clean ramp nothing is flagged and every distance is under
5e-4 σ, so sorting the unflagged ones by it ordered fifteen parameters by noise
and put `phases.0.cell.a` eighth. And **a per-pattern tree is read-only here** —
one tree per pattern, pinned by `data_fingerprint`, so a node cannot be checked
out into this project; what makes the chain navigable is the root node's
`series_warm_start_node` note. Two shared authorities came out of it rather than second copies: `curve_arrays`, in
`viz.packed` since the file `write_html` writes became a third drawer (so no two pictures draw
residuals under two σ policies), and `session.tree_payload`.

Its **five keys on every event** are the thing to know outside the panel:
`SequentialRefinement.fit` takes `events=`/`cancel=` (since this WP — WP-1008's
charter said it already did), and `_SeriesStream` stamps
`series_index`/`series_label`/`series_n`/`series_pass`/`series_cold` onto
existing kinds, so `EVENT_SCHEMA_VERSION` does not move and "pattern k of N"
reaches the run record through the *existing* `stage`/`stage_index`/`n_stages`.
The console pays for that: five fields on every `eval` pushed the cost off the
right edge, so `lib/stream.ts` folds them into one `[T300 1/3 ↩]` prefix.
Measured browser facts: the plot is the chart module's canvas since WP-1461, in
a host that clips it, and its `ResizeObserver` refits it 539 → 1480 px when the
column takes the window, so no canvas overhangs a control (WP-1015's trap was
plotly's); a *rotated* y-axis title shares the fixed left margin with the tick
labels, so `phases.0.cell.a` clipped to `aes.0.cell.a` and the axis takes the
**leaf** (the heading above carries the path); and the staged table's floor is
per column — core 308 px, detail 231 — reflowed by `lib/resize.ts:seriesCompact`
beside `modelStacks`, because the reorder buttons are the last column and the
panel's main verb.

**The view, the armed cursor and the theme's scope** (WP-1044, `Plot.svelte`,
`session.settings`) is the pass that answered four defects reported from use,
and three rules came out of it. **A redraw is not a reason to move the axes.**
Under plotly it was one: `react` re-autoranged over everything drawn, the peak
markers and the mask shapes included, so a zoom lasted until the next peak edit
(measured in Chrome: a drag to 9.97-14.66° came back 4.57-24.85 with a peak
list). The chart zooms in the browser over a payload that is every channel
(WP-1461), so the rule is kept by what the panel does not do: a knob or a layer
change repaints and fetches nothing, a payload over the same channels keeps the
view (`lib/pattern.ts:sameGrid`), and the knob effect reads the payload
**untracked**, or every fetch costs a second paint (counted under plotly: 2 per
zoom drag, 6 at boot). **An armed range gesture must say so under the
pointer**: a select drag and a zoom drag are pointer-identical, so `col-resize`
goes on the chart's plot area (`.u-over`), where an inherited cursor loses to
it without a specificity fight. And **a `ui` key belongs to whatever it is about**
— a width or Simple/Advanced is the project's (four phases, so the table wants to
be wide), a theme is the *person's*, so it lives in `GET`/`POST /api/settings`
over `state_dir/settings.json` beside the recent list, with `ProjectDoc.ui`'s
exact grammar (top-level merge, `null` drops, persisted on the verb) at app
scope. In `ProjectDoc.ui` it was re-read per project, so dark lasted until the
next `Open…`; out of there it also stops being refused mid-run, which is the
finding WP-1029 recorded and could not fix from inside `POST /api/project` (the
project's *other* `ui` keys still ride that route).

The **search controls** (WP-1045, `gui/src/lib/controls.ts`, the Peaks
panel's disclosure) are `ProjectDoc.indexing` rendered as a form — the same
`SearchSpecSpec` the agent request carries, so the two chairs are two views
of one spec. Five rules. **The document is the authority and the commit is
whole-object**: every change POSTs the entire `indexing` block on the verb (a
partial merge could let two half-specs disagree), and the draft re-syncs from
the document on every head move — including after a refusal, so the form
never shows a value the server refused. **Vocabularies come from
`/api/capabilities`** (`indexing_engines`, `crystal_systems` in search order,
`centrings`, `shift_templates`, `search_presets`), never from literals — a
fourth engine appears with no GUI change. **The field inventory is the
bijection's GUI leg**: `controls.ts` declares every field with its widget
kind, label and `title` (WP-1029's no-mute-fields rule, pinned), and
`controls.test.ts` replays the committed corpus
`tests/data/gui/index_controls.json` (the fnmatch mechanism — python owns the
model, TS proves the form states it). **A prior cell is parsed locally**
(six numbers, refused with a reason in the form's own error field — which is
deliberately not the peak verbs' failure field), while a prior space-group
symbol is validated server-side and refused in gemmi's words. And **the
streamed shortlists are the shell's to fold**: `consensus:<system>`
`stage_end` frames collect in App (cleared on `index_start`, kept after the
run so the anytime answer stays readable beside the final one) and render
with the conservative-grade caveat in the tooltip — a streamed grade can
rise, never fall.

The **peak picker and indexing panel** (WP-1027, `src/rietx/gui/peaks.py`,
`panels/Peaks.svelte`, `lib/peaks.ts`, the plot's peak layer) is where the
indexing line meets the GUI line. Peak lists are a **project artifact**
(`peaks.json`, keyed by `data_fingerprint` and refused against the wrong
pattern); every edit refits exactly one group through the picker's own solver,
and the human-owned facts (`origin`, `excluded`) carry across refits. The plot
is an editing surface **only while the Peaks tab is active**, and every pointer
verb has a non-pointer route (typed 2θ, the `.rxt` peaks block — whose only
editable columns are `2theta` and `flags`; everything else is derived and
regenerated). Two pointer rules are measured, not aesthetic: the **move
gesture's grab radius is `grabToleranceDeg` — min(10 px, 1.5× median fitted
FWHM)** — because a pixel radius alone is ±1.9° at the survey view, where a
zoom drag starting 0.9° from a marker silently moved a line 11° (the coarse
10 px stays for shift-toggle and click-to-add, whose precision comes from the
group refit); and a drawn **σ whisker is capped at 3×FWHM**, because a
degenerate component reports σ in tens of degrees (111° measured) and an
uncapped error bar spans the pattern (under plotly it owned the autorange). `/api/index` and
`/api/index/extinction` are run *kinds* on the one machine — a cancelled
search or screen **returns** what it has and its status is read off the token.
The candidate table's Adopt follows the server's `adopt` arm (one answer with
the route), the extinction table's badge follows the served `best` the same
way, and the screen itself is **not** gated on the adopt verdict — it is a
read-only measurement and `best_or_none() is None` is the normal real-data
state — while adoption stays gated, and a space-group chip acts only when the
adopt arm allows and its class is unrefuted. A right-click refit prompts via
`window.prompt`, which a headless driver must answer (`page.on("dialog")`) or
the verb silently never fires — round 1's false "missing echo".

Its second pass (2026-07-31) added three browser facts; the one about plotly's
screen-relative `lightposition` left with plotly (WP-1462), whose renderer lights
from a fixed direction in view space, so the key follows every rotation by
construction. **A style sampled synchronously inside an effect races the
shell's `applyTheme` effect in the same flush** — `Plot.svelte` and the 3D
panel's `rebuild` each await one microtask before `getComputedStyle`, or the
first dark repaint wears light ink. And **an effect that reads the project
*object* refires on every ui-only PATCH** — Model reloads on a boolean
`$derived` (`hasProject`), or a theme click refetches three routes plus the 3D
geometry with the head unmoved.

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
stage names is dropped by `Run all` and kept by `Run this stage` (measured both
ways) — `set_aside` is that difference named, and it is why the two buttons are
on screen together. **A stage's Rwp is its history node's**, never a
`fit(stage_reports=True)` trajectory: bit-identical, both read off the model the
stage compiled and the θ it landed on, and the trajectory costs 7.7× the fit to
rebuild, so the run verb is untouched — the **last** run's node is matched to a
rung by position **and** by that stage's name and `turn_on`, anything else
leaving the number absent rather than a neighbour's or an older run's. And a **dirty plan
has no resolved facts and cannot be run**, because the ladder describes the plan
the server holds. Beside them, the advanced boxes loop over `lib/rxt.ts`'s stage
words — pinned to `StageSpec` from python with the two properties a box needs —
so a new schema field reaches this form as well as the `.rxt` document.

**The peak table's numbers and chips** (WP-1209, `lib/peaks.ts`, `lib/table.ts`,
`panels/Peaks.svelte`). Four rules. **A column is scanned, so its places are
fixed**: 2θ at four with the esd in the last place (`formatPosition`), I as
`I/Imax × 100` over the strongest *measured* line (`formatIntensity`, `—` under
`no_intensity`/`fit_failed`), and an esd from 1° up is not printed — wider than
any peak, it is a flat direction, and the row's flag says why. **An esd that has
swallowed its value is not a precision** (`esdSwallowsValue`: ≥ 1 and larger
than the value): `formatValue` then shows the value at its own precision and
`formatEsd` writes `±110` beside it, where `35(111)` was printed for a 2θ with a
degenerate σ; `12346(56)` keeps the convention, and this holds for every caller.
**A chip's words are the corpus's**: `HelpEntry.label` is the short form, the
chip is a `<Help>` term saying `labelFor(corpus, key)`, and the popover restores
the name a label hid (`Name · position_at_bound`) — so `peak_flags` and
`peak_origins` carry a label on every entry, held by `test_help.py` to three
words and unique. And **a `td` that is not `display: table-cell` is not a cell**:
two adjacent flex/inline-flex `td`s are wrapped into *one* anonymous cell, so a
class shared with a flex label put the chips under the intensity in a column
headed by nothing — found in Chrome, invisible to jsdom, and why the intensity
column is `.rel` rather than the form's `.num`.

**The peak layer** (WP-1210, `lib/plot.ts`, `panels/Plot.svelte`, `app.css`).
Four rules. **A layer is drawn where it can be edited** — the markers and their
fitted curve are on the plot only while the Peaks tab is up, which is already
the only tab a click there means anything on (WP-1027); `peaksActive` is
therefore a *drawing* input and belongs in the repaint effect, or leaving the
tab redraws nothing. **A curve that cannot be drawn is listed and disabled
carrying the reason**, never dropped: `CurveToggle.absent` is that sentence, and
`dataOnlyHidden` covers absent ids too, or a hidden layer arrives drawn the
moment its tab comes up. **Chrome is not a palette**: `--accent` and `--bad` are
`--plot-diff` and `--plot-calc` **exactly** on the light theme, which is how the
picked-peak fit and the model came to be one red line, so a plot mark takes a
`--plot-*` token of its own — `tests/test_gui_palette.py` holds every one to the
phase palette's 0.13 OKLab floor against every other plot colour, in Python
because `structure3d._oklab_distance` is the one distance this package has. It
also names the two pairs the shipped set already misses rather than exempting
them quietly. And **state rides on the mark, not on a second colour**: one ink
for the whole layer with hollow for unusable and diamond for human-placed, so
it spends two colours and the palette stays separable — measured while
choosing, the free hue space is magenta and green alone (violet is 0.10-0.12
from `--plot-diff`, `--warn` 0.053 from `--plot-calc`). The corollary is where
that rule was broken and caught in review: a mark that is **not** the data may
not borrow the recessive `--muted`, which is 0.032 from `--plot-obs` on the
dark theme — fine for the masked points, which *are* measured data, and wrong
for a marker sitting on top of them.

**An indexing candidate on the plot** (WP-1211, `GET /api/index/ticks`,
`lib/plot.ts`, `panels/{Peaks,Plot}.svelte`). Five rules. **Two shifts exist and
one of them belongs on these lines**: not `instrument.zero_shift`, because
indexing fits the metric to the peak list's *raw* 2θ and the cell therefore
already reproduces observed positions; yes the candidate's own `shift_template`,
inverted, because `refine_candidate` fits to `2θ_obs − c·T(θ)`. The symbol is
`structure_from_candidate`'s lattice group, quoted rather than restated, so what
is drawn is what the Le Bail validation was scored against. **A cap says that it
capped**: `max_d_axis` admits a cell predicting 92 103 lines over 5-120° at a Cu
doublet, so past `MAX_CANDIDATE_TICKS` the answer is thinned **by rank in 2θ** —
density is what this picture is read for — with `n_total` beside it, because a
head-of-list truncation leaves the high-angle half empty, which reads as "this
cell predicts nothing there". **A layer whose control is a row gets no
`CurveToggle`**: a toggle would be a second control for one selection, and
pressing it would leave a row looking selected with nothing drawn — so the
status line under the plot says what the toggle row would have. **A preview is
not a selection**, and they are two props for that reason: a hover draws lines,
only a selection clears the plot to the data, or running the pointer down the
candidate table strobes the model on and off once per row. That clear goes
through the `data only` button's own press, one saved list and a flag saying
whose press it was, because two slots is four interleavings and no rule a reader
could state. And **the lines span the data pane's full height**, drawn by a
layer of their own and never on the tick band, since a tick states a fitted
model's position while this is a hypothesis laid over the data. Drawn
**under** everything: 426 predicted lines over the FAP example's 115° is
~3.7 per pixel, and on top they buried the pattern the overlay exists to be
compared with. Green was the last free hue (WP-1210 measured the rest); the plot
palette now has no room for a further mark that carries a quantity.

**A redraw never moves the axes** (WP-1212, `panels/Plot.svelte`,
`App.svelte:setProtocol`). Its plotly repairs went with plotly in WP-1461: the
axis pinning, reading `ax._rl`, `movedAxes`, the hover ring kept out of the
WebGL scene, and the `.select-outline` override. Three rules outlived them.
**Arming is the figure's mode** (`setMode`) and repaints nothing; under plotly
`dragmode` was a layout key, and routing it through the repaint cost two of the
four reacts an exclude drag took. **A `$derived` off `project` is a new object
on every settings PATCH**, so an effect keyed on `extent` repaints for two
numbers that did not change — key it by value, beside `protocolKey`. **Two
`$state` assignments either side of an `await` are two flushes**, which is why
`setProtocol` reads the peak list before publishing either (`readPeaks`); one
exclude drag is one fetch and moves no axis.

**The hover readout** (WP-1213, `lib/plot.ts:readout`, `panels/Plot.svelte`).
The tooltip covered the data, and plotly offered no positioning for the unified
box beyond `hoverlabel.align` — so the box was **deleted rather than moved**,
and a strip of the plot's control rows says what the box said plus the three
things it could not — the candidate's `hkl`, which emission line that line is,
and d. **A new fact about a mark goes in the strip**: the chart takes neither
of the boxes uPlot offers (a legend, a point per series), and `App.test.ts`
holds every pane to that. Under plotly a label on one trace drew a second box
of plotly's own beside it (WP-1438).
So **one reflection has one spelling on all three browser surfaces** —
`peaks.ts:formatHkl` here, `watch-core.mjs:hklLabel` in the wheel — held equal
by `plot.test.ts`, since neither can import the other.
**The strip's shape follows the payload, the tab and the curve toggles — never
the pointer**: one row per *drawn* curve, so `data only` empties it to the
points, while everything that varies under one pointer sweep keeps its slot and
empties it, the resting state included, and the values are sized in `ch` so the
wrap points hold. A strip that grew a field on hover would resize the canvas
above it once per entry — WP-1212's jitter arriving through the repair for it
(measured on NAC: plot 776 px, strip 23 px, unchanged over ten positions).
**A masked channel is in no result, so the readout reads two arms** — nearest
over fitted ∪ excluded (WP-1033), and a masked one has no model to quote, which
is also how the strip says the pointer is inside a region without a field that
changes width to say it. **The pointer's 2θ is the cursor's pixel through the chart's
own x**, never a point some trace matched: the ticks ride on reflection
positions and the markers on peak positions; the line under the pointer is
`nearestPeak` at the **coarse** 10-px radius the non-destructive
verbs aim with (`PICK_RADIUS_PX`, WP-1027's fine `grabToleranceDeg` is the
*move* gesture's, because a drag edits), so the ring, the lit table row and the
strip name one peak rather than `hoverdistance` naming another. **A curve is
read at the nearest drawn channel and a nearby thing is hit-tested against the
pointer**, which are two positions on purpose: a channel is not the pointer, and under
plotly's decimated window it was up to ~0.03° away at a survey view — wider than
the tolerance — so the pointer sat on three picked lines in a row while the row
read `—`. **The pointer's line is chrome, so it is solid and takes `--fg`**: dotted in
`--muted` is `maskShapes`' excluded-region edge exactly, and the pointer drew a
line indistinguishable from a protocol boundary (uPlot's own is dashed
`#607d8b`, and `rxplot.panes` sets `.u-cursor-x` inline for every chart on every page, since a
page stylesheet that forgot the rule left `rietx compare` dashed) — a mark carrying no quantity
needs no `--plot-*` token (WP-1210), it needs the one ink no plot colour is
near. **Prose takes `−`, numbers take `-`**, which this app followed unwritten
until a typographic minus in the tick offsets sat beside `formatValue`'s
`toPrecision` output in one row; `formatHkl` shows where the line is, an index
standing in for an overbar rather than a measurement. And a curves payload is
**`$state.raw`** — a plain `$state` proxies it, so `held` and the payload a
draw was handed are two identities for one object (svelte says so in dev; it
was true before this WP surfaced it).

**The refine flag where the model is read** (WP-1214, `Model.svelte`,
`lib/table.ts`, `session.export`). Four rules. **A flag is set beside the value
it is about**: the Model panel draws the parameter table's own vary control on
every value it shows, one `set_vary` node per path, in the *same* `PATCH
/api/params` as the value edits and **before** the model patches — a whole-model
PATCH carries whatever `vary` the model it was built from had, so a flag set
after that read is reverted by it. **The held marks are one vocabulary and there
were four**: `heldGlyph` is in `lib/table.ts` because two panels draw it, and the fourth
(`needs_held_cell`) had worn the mode-fixed mark since it arrived, the glyph being a ternary
whose last arm caught everything — so an unknown reason still draws a mark, an
empty box reading as a control that failed to render, and
`test_gui_server.py` reads the fields `ParameterRow.refinable` tests **and `lib/table.ts`'s
own branches**, so a sixth fails on both sides (it checked only python until WP-1435's `held`
tripped the wire with nothing behind it). **A field's parameter path is not always its model path prefixed** — `source.polarization` is `instrument.polarization` in θ — so
`Field.param` carries it and `fieldParam` is what every lookup asks; unprefixed,
that field rendered off the model, applied past `set_values`' bounds, and had no
row for a flag to act on. And **an export is gated on what it describes**:
`instrument_profile` is answered from the project where the rest of the family
needs a result, `_EXPORT_MODEL_ONLY` declaring the exception so the stricter
gate stays the default. One more browser trap and it is a width: a rule aimed at
the value reaches the control beside it, and `.cellrow input { width: 100% }`
drew the esd next to the box at zero width.

**One row per atom, and the coordinate is a cell in it** (WP-1215,
`Model.svelte`, `lib/model.ts:positionEdits`, `gui/symmetry.py:position_values`).
Four rules. **A coordinate is typed and the site answers**: `POST
/api/structure/position` takes a whole position — the projection is a whole
position, since a `[1 1 0]` site cannot say what x should be without y — least-
squares it onto the site's own basis, and **refuses** an unreachable one naming
the directions it allows and the nearest position they reach. Never snapped:
that would move the atom to a *different site* than the one asked for, which is
`check_cell_angles`' objection one rank up. It is a `set_value` node, not an
`edit_model` one, because a position changes what the table holds and never what
it contains — the line `structure_aniso` is on the other side of. The client
computes none of it; a second copy of the DOF basis there is `symbolChanged`'s
trap. **A vary key is a path *or a glob***: a site's DOFs are freed together
("per-axis intent does not map onto rows such as [1,1,0]"), so the position's one
box says `phases.i.atoms.j.dof.*` and records one node, and a group that
disagrees with itself answers `null` and draws the DOM's `indeterminate` —
`false` over a half-freed site is untrue about the other half. **A memoised
answer may be asked for automatically, and the route it is on stays split**: the
Wyckoff search is keyed on (space group, positions) — the content tuple, not a
digest, and not the label, which cannot change a letter — so the `site` column
fetches itself, but a *miss* still costs 2.0-5.5 ms an atom, so it is not folded
into `GET /api/structure` and not awaited with it. Three client rules ride with
that and each is a bug the other two do not cover: the effect keys on `stamp`,
not `head`, because a local write calls `load()` and moves no head prop; the
better `causes` are held in their own field, because merged, two concurrent
fetches would let arrival order decide the sentence; and a stale *response* is
dropped rather than a fresh request. And **a width written in three places has
one test**: the atom table's floor is the table's `min-width`, the structure
column's `flex-basis` and `MODEL_MIN`, and only the third had one — the basis
was still WP-1034's number, so at exactly the stacking threshold the column came
out short and side-scrolled the table the threshold exists to give room to. Two
corollaries, both found by looking: a `colspan` cell's grid **is** part of the
table's min-content, so a track floor there must be `min(210px, 100%)` or opening
a disclosure widens the whole table; and the threshold must count the **grips
inside the row it is measuring**, which no version of it had.

**The form is one grid of three columns** (WP-1216, `Model.svelte`,
`lib/model.ts:instrumentFields`). Four rules. **A form's column count is a
promise, so nothing else may decide it**: a wrapping row lets its widest item
pick the break, which is how one `<select>`'s longest option moved every field
after it, and an auto-fill count lets the container pick it, which gave Source
five columns while Profile had three in the same form. Three is the profile's
own row — U V W over X Y, the rows declared by `PROFILE_ROWS` — and the whole
panel is read against it; a control whose content is a *word* takes the row
rather than a track (`.fullrow`: the selects, and a phase called
`fluorapatite`). **A declared column count is a declared minimum**, so
`MODEL_MIN.form` became its arithmetic (3 x 92 + 2 x 10 + 24 = 320, the
threshold 1136 → 1256) — stated once, with `COL_MIN` reading it and the CSS
basis taking it as `--col-min`, and `resize.test.ts` crossing it against the
panel's own `--w-num`/`--grid-gap`/padding, because WP-1215's stale width was a
comment where a test belonged. **Which group a field is in is data, never its
path's prefix** — the axial apertures are `geometry.axial_*` and shape the peak,
the zero shift is top-level and belongs beside the displacement it is refined
against — and a group with no field would be a heading over nothing, which is
why the background is not one. And **a cell is a `subgrid` of its group's
rows**, so a label wrapping to two lines no longer pushes its own input below
its neighbours': the span follows the content (`:has(.varyline)`) rather than a
class on the grid, since a subgrid clamps a child past its last track *into* it
and would draw the refine flag on top of the value with nothing failing.

**A git graph, and a table whose numbers hold their columns** (WP-1217,
`lib/history.ts`, `panels/History.svelte`, `app.css`). Five rules. **An edge
holds a lane for its whole span** — a *lane* rule, not a drawing one. A
tip-following pass frees a lane the moment its node is drawn, so a later fork
could be handed a lane an edge was still travelling down, and the only way to
draw that edge was a diagonal across the whole gap: the shallow line the user
reported. Reserved, `edgeSegments` steps sideways in exactly one row, and which
end it steps at needs no second rule — the edge leaves the lane that goes on
without it, so a fork crosses below its parent and a merge above its child.
Only a **second** parent is dashed: the first is the lineage `rwpDelta` reads
against, and dashing both put three dashed rows in the middle of the trunk.
Lanes are half a palette in each place — the rotation is `LANE_HUES` (five at
72°, a sixth landing inside the phase palette's floor at `--lane-c`), the
lightness and chroma are `app.css`'s per theme, and `test_gui_palette.py` owns
the distance. **A `ch` column is one column only while every cell in it is one
font at one size**: `ch` is the element's own zero, so a `--text-xs` header sat
inside its own tracks by a growing offset and a non-mono `Δ` widened one by
4 px — the family and the size go on the **row**. **A format is declared per
family and the width is a promise the formatter keeps**: `PLACES` is keyed by
`rietx.help.PARAMETER_HELP`'s own globs and crossed against `help_keys.json`
both ways, so a new family fails until it is given one, and `formatSide` writes
exponentially rather than anything longer than `VALUE_CHARS` — which is why the
three widths are stated once in TypeScript and handed down as
`--w-val`/`--w-pct`/`--w-path` with no arithmetic to cross. Below the sidebar's
clamp the row scrolls rather than squeezes, the path being the column that
gives because it is drawn `rtl` and its leaf survives. **A difference is given
twice and the percentage is of |a|** — measured on a Caglioti V refining from
−0.0002 to +0.0024, a signed denominator printed `+0.002601` beside `-1.30e+3%`,
two marks disagreeing about which way a parameter went — at three significant
figures, because 12 ppm on a cell length is a result and `0.00%` is not a way to
say it. And **only the Rwp badge may be green**: `.better` was on every compare
row with a non-zero delta, and a parameter difference has no good direction.

**The manual is held to this app, and two of its vocabularies by test**
(WP-1017, `docs/manual/using/gui-*.md`, `tests/test_gui_manual.py`). The GUI is
documented and no longer beta; its **routes stay provisional by declaration**,
which is the half of that status the chapters did not retire. Four rules.
**Routes and panel names are partitioned** the way `tests/api_surface.py`
partitions the call surface — every route documented in a chapter or excluded
with a written reason, every tab in the strip named — and each tightens **both
ways**, so a chapter naming a route the server does not serve fails too: that is
WP-1037's bug pointed at the reader. **Where no python object knows the fact,
the authorities swap**: nothing here knows the panels exist, so the strip is
data in `lib/tabs.ts`, `tabs.test.ts` writes `tests/data/gui/panels.json` and
pytest reads it — the fnmatch mechanism run backwards, and it keeps the python
suite node-free. **A screenshot is generated**, by `docs/manual/
make_screenshots.py` driving this server in-process over a shipped example;
that script is the one authority for how each was taken, its `SHOTS` table is
what a chapter may reference, and a picture is judged by **looking at it** —
never by a digest, which a re-render breaks. Note `*.png` in `.gitignore` has
swallowed a committed image family three times now, so the negation is asserted
rather than remembered. And **a first-run aid states what is true, not what was
remembered**: the checklist's steps are derived from the project, so an undone
fit un-ticks `Run`, and only the dismissal is persisted — nothing is written
when the last step completes, because a surprise write is the wrong thing to do
during a first session.

# WP-1205 — New project: open any project, browse, sensible defaults, the wizard bug

Milestone: v1.2 · Status: ✅ 2026-08-26 — browse, one mount, the wizard settles
Depends on: WP-1201, WP-1203, WP-1204

## Goal

The empty state can open any project on the machine; the wizard reads like a
form for a person, with defaults visible and the registry's prose behind help;
opening a recent project no longer leaves the wizard painted over the Model
panel.

## Context

The user's notes, and what the code does (2026-08-25):

- **"Information overload."** The three quoted strings are: (1) `claimed by
  bruker_raw — <sniff>. σ: <sigma>` at `Model.svelte:692-695`, a client
  literal joined to `PatternFormat.sniff`/`sigma` served by `preview_pattern`
  (`imports.py:274-275`; the Bruker prose is `io/formats/bruker_raw.py:724-
  738`); (2) the `scan` option's `help` from `READER_OPTIONS`
  (`io/formats/base.py:141-155`) rendered verbatim at `Model.svelte:729`;
  (3) `Required, and not defaulted: Instrument has no default source…` at
  `Model.svelte:790-794`, a client literal paraphrasing the server's refusal
  at `session.py:2655-2658`. All were written for `capabilities()` consumers.
- **Scan field.** A picker only when `scan_count > 1` (`Model.svelte:696-
  731`); the count is never shown; labels load on `focus`/`pointerdown` via
  `GET /api/upload/pattern/scans` (`session.py:257-285`), so before a click
  the control reads `scan 0`. Default scan 0 is the reader's own, with
  `PATTERN_MULTISCAN_DEFAULTED` in the diagnostics list.
- **Project directory** is a text input pre-filled from `suggested_project`
  (`Model.svelte:843-846`, `:208`); the browser cannot give a path. No route
  lists the filesystem (`RESERVED_ROUTES` is empty, `session.py:105`).
- **Instrument is mandatory** at every level: `blocked()` (`lib/wizard.ts:
  234-236`), `Project.create` (`project.py:107-116`), `_as_instrument`
  (`session.py:2654-2658`), `Source._nonempty` (`schemas/instrument.py:126-
  130`). `bragg_brentano()`/`flat_plate_transmission()` default to Cu Kα;
  `debye_scherrer(wavelength)` has no anode to read. The header hint
  (`imports.suggest_instrument`, `imports.py:532-550`) pre-fills anode and
  radius when the file states them, and sends `null` when name and
  wavelength disagree.
- **No way to open a project.** `Open…` (`App.svelte:707-711`) is inside
  `{#if project}`; the empty state offers only the recent list
  (`Model.svelte:660-678`), populated by projects this machine has opened.
  `POST /api/project/open {path}` exists (`session.py:341-358`).
- **The wizard sticks.** `showWizard = !project || wizardOpen`
  (`Model.svelte:166`); the recent-list button (`Model.svelte:666-668`)
  calls `onopen` and never clears `wizardOpen`, so after `Open…` → recent
  the Model tab shows the wizard over the opened project until `Back to the
  project` is found. `Model` is mounted twice (`App.svelte:758-759` empty
  state, `:807-809` tab column) with independent state.

Decisions: the API keeps its refusal (an anode nobody chose must not become
a wavelength in every cell); the **wizard pre-fills a visible default**
(header hint, else Bragg-Brentano Cu Kα) and says in one line what it
assumed, so the choice is made by seeing it. A directory browser is a
read-only server route on a localhost server; roots are the home directory
and cwd, and a listing never leaves them.

Inherited from [1204](1204-developer-mode-example-projects.md) (2026-08-25,
verified still current on arrival) — half of "sensible defaults" already
landed, and the empty state now has two lists:

1. **The suggested project path is no longer the working directory.**
   `imports.default_project_dir()` is the one authority and answers
   `~/rietx-projects` (`_about.PROJECTS_DIR_NAME`); `preview_pattern`'s
   `suggest_in=` is still the seam for a caller with a better idea, and
   `session.upload` still does not pass it. Nothing is created at preview time
   — `Project.create` makes the parents — so if this WP adds a *browse*
   control, "the directory does not exist yet" is the normal case rather than
   an error to report.
2. **The empty state is no longer wizard-only.** `Model.svelte`'s wizard now
   carries a `section.examples` beside `section.recent`, both fetched by the
   shell (`App.svelte`: `loadRecent`, `loadExamples`) because opening either is
   the shell's verb. This WP's "Open any project" control lands as a third
   thing in that block, and the ordering question (Recent / Examples / Open /
   New) is now a real design choice rather than an implicit one.
3. **`rietx gui --scratch` and `--state-dir` exist**, which changes what this
   WP has to solve. "Open a project without messing it up" is answered at the
   CLI; what is *not* answered is opening one from inside the app without
   changing it, and the honest options are to leave that to the CLI or to add a
   scratch checkbox to the Open control. `gui.server.scratch_copy` is the
   function either way.

Also worth knowing: the wire surface gained `GET /api/examples` and
`POST /api/examples/open|reset`, and `POST /api/examples/reset` is the only
destructive verb on the GUI surface. Its `name` is checked against the example
list rather than sanitised — the same shape any `GET /api/fs?path=` this WP
adds will need, except that a filesystem path has no list to check against, so
the confinement has to be a real containment test.

Inherited from [1203](1203-help-popover.md) (2026-08-26, verified still
current on arrival) — the wizard's fields now explain themselves from the
package, not from the form:

- `PresetField` carries **no `title`**. `wizard.ts:presetHelp(field)` derives
  the key `instrument_fields:<name>`, and the sentence lives in
  `rietx.help.INSTRUMENT_FIELD_HELP`. So a field this WP adds to
  `PRESET_FIELDS` needs an entry there — `tests/test_help.py` crosses the arm
  against `INSTRUMENT_PRESETS` both ways and fails without one, and
  `wizard.test.ts` fails if the key does not resolve. A new `title=` is not
  the way to describe it.
- The same holds for the instrument editor, whose `lib/model.ts:Field` carries
  `help` as **data** (its paths are three different kinds of thing) plus
  `title` as an escape held to a named list of exactly two —
  `geometry.kind` and `profile.shape`, the two model *choices* the corpus has
  no vocabulary for. Adding a third fails `wizard.test.ts` until it is either
  described or added to that list deliberately.
- The wizard's remaining authored tooltips are inside a **counted budget**
  (`lib/help.test.ts`): `panels/Model.svelte` is allowed exactly 3. Adding one
  fails, and so does removing the last one without deleting the file's row.
- `GET /api/help` is fetched once at boot beside `/api/capabilities` and is
  not behind the in-flight 409. A new panel needs no fetch of its own.

## Non-goals

- The CIF requirement (WP-1206, WP-1207).
- Reader-registry prose: it stays as the `capabilities()` contract; only
  what the wizard *shows* changes.

## Tasks

- [x] `GET /api/fs?path=`: directories and `.rex` entries under a root,
      refusing paths outside the roots; `tests/test_gui_server.py`
      confinement tests (`..`, symlinks out, absolute paths elsewhere).
- [x] `Browse.svelte`: one modal used for opening a project and for picking
      the project directory; a typed path field beside it; `Open…` in the
      empty-state header; `startImport` and the recent-list arm both settle
      `wizardOpen`; `Model` mounted once.
- [x] Wizard prose: one docs-style line per step; `sniff`/`sigma`/option
      `help` behind the popover (WP-1203 keys); the `Model.svelte:790-794`
      literal deleted; `blocked()` sentences rewritten; instrument pre-fill
      with its one-line reason; the Create button's line rewritten.
- [x] Scan control: "this file holds N scans; reading scan 1 of N (label)",
      labels fetched eagerly when N > 1; the default stated, not implied.
- [x] Browser pass from a blank state: open a project by browsing, create a
      project without the CLI argument, open a recent one and confirm the
      Model tab shows the editor; rebuild the dist.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_dist.py -q
```

## References

- WP-1014 (two-phase uploads, the `instrument_hint` rule), WP-1047 (reader
  options and the scan picker).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

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

## Handover log

- **2026-08-25** — created from the v1.2 triage.
- **2026-08-26** — Closed. A person can now open any project on the machine
  from the empty state — not only the ones this build already knows about —
  by browsing to it, confined to their home directory and wherever the
  server was launched from. Creating a project no longer requires the CLI
  argument either: the whole wizard (pattern, CIF, instrument, directory)
  works from a cold, project-less GUI, with a directory picker for the
  create step too. And the reported bug — opening a project from the
  wizard sometimes left the wizard's form painted over the panel instead of
  showing the new project — is fixed at its actual cause, not patched at the
  symptom: `Model` was mounted twice in `App.svelte` (the empty-state wizard
  and the Model tab were two separate component instances, each its own
  `wizardOpen`), so an open that left `project` truthy the whole time never
  tore the stale instance down to reset it. `Model` now mounts exactly once.

  **Done**, in landing order: `GET /api/fs` (home + cwd, symlink-safe
  containment, `GuiSession.fs`/`_fs_roots`); `Browse.svelte` (one modal,
  `mode="open"`/`mode="pick"`) wired into the wizard's header and its
  directory field, with `openPath()` as the one place a successful open
  settles `wizardOpen`; the `App.svelte` single-mount merge; three client
  literals moved behind the help popover or deleted outright (pattern
  `sniff`/`sigma`, the reader option's redundant `.help` span, the
  paraphrased "instrument is required" paragraph, replaced by a one-line
  statement of what was actually assumed); the scan picker now states the
  count and which one is being read, with labels fetched the moment a
  multi-scan file stages rather than on first focus; a real-browser pass
  (playwright-core + the cached chromium-1223, scratchpad-only) confirmed
  the fix live, including the exact regression shape (open a *different*
  project from the tab-mounted wizard's own Browse).

  **Measured** ([dev], macOS arm64): `tests/test_gui_server.py` 143 passed
  (6 new, the `/api/fs` confinement cases); `npm --prefix gui test` 448
  passed (was 444 before this WP's own tests — the delta is exactly the 4
  new App.test.ts cases); `npm --prefix gui run check` 0 errors/0 warnings;
  `tests/test_gui_dist.py` passes on the rebuilt dist. No python test outside
  `test_gui_server.py` and `test_docs_consistency.py` runs — nothing here
  touches the refinement core, so the full suite does not apply (root
  CLAUDE.md's ladder).

  **Gotchas for a reader of the diff**: `gui/CLAUDE.md`'s size cap moved
  645 → 663 (`tests/test_docs_consistency.py`, justified inline) for the
  mount-once invariant and the browse/settle rules — a stranger touching
  `App.svelte`'s layout needs to know that invariant exists, or the same bug
  is one refactor away from shipping again. No `### Inherited` note was
  pushed to WP-1206/1207/1214/1215/1216: none of what changed here bears on
  their planned work (1206/1207 touch the CIF requirement and library-side
  phase handling; 1214/1215/1216 touch the post-creation model/structure/
  instrument editors, not the wizard's own preset form) — checked, not
  assumed, by reading each file's current Context.

  **Next**: WP-1206 (a typed cell, no CIF) per ROADMAP's Current focus —
  `blocked()`'s CIF refusal and the wizard's structure step are exactly what
  it touches, so re-read `lib/wizard.ts` and `Model.svelte`'s step 2 rather
  than trusting this WP's own line-number citations, which have already
  drifted once this session and will again.
- **2026-08-26** — `/code-review medium --fix` found `_fs_roots`' collapse
  condition was `home == cwd` only, so the docstring's claimed common case —
  launching from an ordinary project directory *under* home — actually kept
  two roots and showed a redundant "Current directory" button in Browse.
  Fixed to `cwd.is_relative_to(home)`. `tests/test_gui_server.py`: 143
  passed (the `fs_tree` fixture keeps home/cwd disjoint on purpose, to leave
  the genuine two-roots path tested, so it is unaffected); ruff clean.

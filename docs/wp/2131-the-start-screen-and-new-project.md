# WP-2131 — the start screen and the New project dialog

Milestone: gui-overhaul · Status: ✅ 2026-11-10 — the start screen and the New project dialog merged in #1498; sentence case app-wide is the milestone's row
Depends on: 2123

## Goal

`rietx gui` with no project opens on a start screen: the wordmark and version, New project…,
Open…, links to the manual and the tutorials, then the recent projects and the shipped examples.
A launch with no project named reopens the last project instead, and the start screen shows only
when there is none to reopen. New project… opens one dialog with four rows (Pattern, Phases,
Instrument, Project), creates nothing until Create, and asks for neither mode nor plan. It
replaces the old empty state, which was a recent list, examples with Reset, "Browse for a
project…" and a numbered four-step wizard, all drawn inside the Model tab's column.

## Context

### Where it is today

With no project open, `App.svelte` gives the panel column the whole window and mounts
`panels/Model.svelte`, whose `showWizard` branch draws the empty state: a recent list (name and
path), the examples with a Reset button, "Browse for a project…" (`panels/Browse.svelte`, the
server-side folder browser of WP-1205), and the wizard's four numbered steps (`lib/wizard.ts`):
pattern, structure (CIF, typed cell or none), instrument (preset form or a saved profile) and
project (directory, mode and plan). With a project open, the header's Open… shows the same
wizard over the Model tab.

The routes exist and stay as they are: `POST /api/project/new`, `POST /api/project/open`,
`GET /api/recent`, `GET /api/examples`, `POST /api/examples/open`, `POST /api/examples/reset`,
`GET /api/fs`, the upload previews (`POST /api/upload/{pattern,cif,instrument}`,
`GET /api/upload/pattern/scans`) and `GET /api/spacegroup`. Three facts limit the port:

- `GET /api/recent` drops a project whose folder has moved, so the list cannot show one as "Not
  found", and no route removes an entry.
- `project_new` takes one structure argument: one CIF upload, one typed cell, an inline model or
  `null`. A dialog that lists several phases needs a list of those.
- A browser upload carries a file's bytes and name, never its folder. The dialog cannot default
  the project's place to the pattern's folder, and a TOPAS, FullProf or GSAS project file cannot
  bring the data file it names along with it.

### The designs, and the rulings they rest on

The maintainer reviewed the round-9 prototype on 2026-11-08 and said "looks good". Ten calls
Claude had settled there drew no objection. One fix was asked for: the instrument form's
"Wavelength" label ran into its box. The prototype is not published, so each design is restated
here.

1. **The start screen** shows New, Open, Recent, Examples, and links to the manual and the
   tutorials. No tour and no news. Practice: the four-part screen in VS Code, JetBrains, Xcode and
   Blender, and the advice of Apple's HIG, Fluent 2 and NN/g to keep onboarding short and
   optional (`docs/practice.md` § The start screen and the New project flow). Left column: the
   wordmark and version, New project… (the one filled button), Open…, then the two links. Right
   column: Recent, then Examples. A first run shows Examples only. Below 640 px the two columns
   stack.
2. **A recent row** reads the name and the date, then each phase with its space group and the
   folder. A "⋯" button and a right-click give its menu. A project that has moved stays listed as
   "Not found", with Locate… and Remove from list. Practice: JetBrains (recall).
3. **An example row** reads its title and description. Its menu offers Open and a fresh copy,
   which is the old Reset.
4. **At launch the app reopens the last project**, and the start screen shows when none was open.
   Practice: VS Code and JetBrains. The alternative was always starting on the start screen, as
   Xcode does.
5. **The bars stay on the start screen** with their panel toggles disabled, under the
   maintainer's rule that the bars never change (WP-2123).
6. **New and Open replace the window's project**, one project per window. Under the autosave
   ruling of 2026-11-07 nothing is lost. Several windows wait for the desktop app.
7. **New project is one dialog with four rows**, not a stepped wizard. Practice: Profex's single
   dialog, and NN/g's warning that wizards slow expert users. Nothing is written until Create.
8. **Pattern row**: an empty dashed slot, then the file with rietx's own summary (the reader,
   points, 2θ range and step, whether the esds come from the file or from counts) and a
   square-root sparkline.
9. **Phases row**: Add phase › From a CIF…, From a TOPAS, FullProf or GSAS project…, Space group
   and cell… (the free cell boxes follow the symbol; a cell-only phase is a Le Bail scaffold). No
   phase is allowed: the project opens for peak picking and indexing. The reader's notes sit
   under a disclosure.
10. **The instrument falls back to Bragg-Brentano, Cu Kα1/Kα2, tagged "assumed".** The Instrument
    row is a one-line summary with its source ("from the file's header", "from <profile>",
    "assumed") and Change… for the geometry, the anode with rietx's wavelengths, the radius, or a
    saved instrument profile. Practice: GSAS-II gives Cu Kα lab defaults when its parameter-file
    dialog is cancelled. The round-9 record names this the call most worth a second look, since a
    wrong anode shifts every refined cell.
11. **Name and place are asked before Create.** Practice: folder projects ask first (JetBrains,
    Xcode, Obsidian).
12. **Mode and plan are not asked.** Rietveld when the phases have atoms, Le Bail when they are
    typed cells, the default plan; both change later. Practice: Profex generates a default
    control file. The old wizard asked both.
13. **The "Wavelength" label fix** (the maintainer, 2026-11-08): the dialog's label column is
    6.5em, wide enough for its longest label, and a check measures the gap between every label
    and its control.

Three rules from the design rounds bind this work. No permanent explanatory text: an
explanation lives in a tooltip or a help box (ruled 2026-11-07, repeated 2026-11-08). No click
may move the layout unless it asks to (2026-11-07; interaction rule 8). Right-click on an object
opens its menu (interaction rules, adopted 2026-11-08).

### Rulebook seams

- **One filled primary per view** (2026-11-06; `lib/style.test.ts`). New project… is the start
  screen's, and Create project is the dialog's, as the folder browser's pick is its own.
- **Registers** (`gui/CLAUDE.md` § House style): size, padding and radius belong to `app.css`.
  The wordmark is the one new size, so it is a class there.
- **Routes** (WP-1017): a new route needs its line in a GUI chapter, which
  `tests/test_gui_manual.py` holds both ways.
- **A first-run aid states what is true** (WP-1017): the examples-only first run is the recent
  list being empty, nothing remembered.

### Tier

Nothing here reads the data or decides for a fit, so no row joins `rietx._audit`. The mode rule
(Le Bail when a phase is a typed cell) is WP-1206's refusal made unreachable, as the old wizard
made it.

## Non-goals

- The File menu (Save a copy, Rename, Move to, Export, Close) is a later WP. Without Close, the
  last project opened is always the last one open, so reopening reads the recent list's head.
- Dragging files onto the window, multiple windows, and Show in Finder wait for the desktop app.
  A browser page cannot reveal a folder.

## Tasks

- [x] `GET /api/recent` keeps a moved project as `missing`, carries each project's phases, and
  `POST /api/recent/remove` drops one entry; `project_new` takes a list of structure forms.
- [x] `rietx gui` with no project reopens the recent list's head, and starts empty when it cannot.
- [x] The start screen (`panels/Start.svelte`): the two columns, the row menus, Locate…, Remove,
  the example's fresh copy, and the header's Open… showing it over an open project.
- [x] The New project dialog (`panels/NewProject.svelte`) on `lib/wizard.ts`: the four rows, the
  instrument's source tag, the 6.5em label column, mode from the phases, no plan asked.
- [x] The old wizard and empty state leave `Model.svelte`; vitest moves to the new components.
- [x] The layout browser test drives the start screen and the dialog with real clicks; the dist
  rebuilt, the GUI chapters and the empty-state screenshot updated.
- [x] `docs/practice.md` § The start screen and the New project flow.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_server.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-08, restated above with their dates.
- `docs/practice.md` § The start screen and the New project flow.

## Moved from gui/CLAUDE.md

On 2026-11-10 WP-2134 folded this WP's additions to `gui/CLAUDE.md` into the
condensed rulebook as standing rules, each still naming this WP. The text below is
the paragraph that file carried for this WP until then, verbatim. Where it and the
rulebook disagree, the rulebook is current.

**The filesystem browser** (WP-1205, `GET /api/fs`, `Browse.svelte`) is the empty
state's third way to reach a project, beside the recent list and the examples:
read-only, confined to `Path.home()` and the process's cwd, and not behind the
409 like `/api/recent`. **The gate is containment, not a blocklist** — `path` is
resolved (symlinks included) before it is checked against the two roots, the same
shape `GuiSession._export_target` already used for the exports directory. Browse
is **one modal, two jobs**: `mode="open"` opens a `.rex` entry, `mode="pick"`
hands a directory to New project's Where field (a browser can say where a project
lives, never name it). **`Model` is mounted once in `App.svelte`**, never per
branch of `{#if project}`, and **every opener settles what is drawn over the
project in the shell's `open`/`opened`**: a second instance or a self-settling
opener once left a wizard over a freshly opened project. **The start screen and
the New project dialog** (WP-2131, `panels/Start.svelte`, `NewProject.svelte`)
keep three rules. A moved recent project stays listed as `missing`, with Locate…
and Remove (`POST /api/recent/remove`). The mode follows the phases, never asked:
a typed cell gives Le Bail, so WP-1206's refusal stays unreachable. An assumed
instrument is tagged `assumed` where shown: unmarked, a wrong anode moves cells.

## Handover log

- **2026-11-10** — closed. PR #1498 merged on 2026-11-10, so `rietx gui` with no project shows
  the round-9 start screen, and New project is one dialog of four rows that asks for no mode and
  no plan. The File menu this WP named next has also merged, as WP-2133. Close took over settled
  call 9, so "the last project" now means the one open at quit.

  *Leftovers, and where each went.* Sentence-case headings app-wide (ruled 2026-11-09, option
  A) is the row "Sentence-case headings" in `docs/milestones/gui-overhaul.md` § Designed, not
  yet filed. Adding a phase from a TOPAS, FullProf or GSAS-II project file (settled call 2) went
  to § Owed to the port: a browser upload cannot bring the data file such a project names.
  Dragging a file onto the window and Show in Finder (calls 3 and 10) wait for the desktop app,
  the milestone after this one, and are not carried here. The layout flake recorded in the
  second round needs a second failure with the same message before a probe; nothing carries it.
  The settled calls were reviewed with the PR at its merge. The narrative went to
  `docs/milestones/v1.12.md`.

  Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
  Next: none here.

- **2026-11-09, ruling** — Yue Wu ruled on the app-wide heading register, by choosing option A.
  Sentence-case headings apply to the whole app. One `app.css` rule carries them at this WP's
  register: 13 px, weight 600, full-colour text. The app's other `h2`/`h3` rules and the Model
  panel's two table-header rules follow it. A follow-up WP does that work; this one implements
  nothing more. The question below is ruled.
  The merge of main that round put `gui/CLAUDE.md` one line over its 1060-line cap, since
  each side had added one. The filesystem-browser paragraph is rewrapped and four phrases
  shortened. No fact was dropped.

- **2026-11-09, second round** — a fix round on PR #1498, by a ghostshift runner. Four items.

  *Done.* (1) The start screen's and the dialog's headings are sentence case at the
  prototype's size. Settled call 15 below gave them the app's uppercase section register, and
  that contradicted the maintainer's ruling of 2026-11-06, "Sentence-case headings". A written
  ruling outranks a settled call, so call 15 is withdrawn. The empty-state screenshot pair is
  regenerated. (2) Review finding 8, declined last round, is fixed: two unnamed typed cells in
  one create were both `phase`. In the list form an unnamed typed cell is now `phase_N`, N being
  its place in the joined list, the form the CIF reader gives an unnamed block (settled call 16).
  (3) A test covers the list form's species-check path: the refusal names `phases.1`, the atom's
  place in the project. (4) The layout flake is recorded and the test left unchanged, below.

  *For Yue* (ruled 2026-11-09, option A: see the ruling entry above). Every other panel still
  draws `h2`/`h3` in `app.css`'s uppercase register, so the app-wide heading register conflicts
  with the 2026-11-06 ruling. This round changed only the two screens it owns. Whether the
  ruling covers the whole app was a follow-up for Yue; the workshop's `visual-language.md` asks
  the same as open question 12.

  *The flake, recorded.* `test_a_pending_edit_moves_nothing_in_the_action_bar[stacked]` failed
  once in the first round under `-n 4`, and passed alone. Its message was `'pending' in ''`: the
  typed key never reached the value box, so no edit registered. It was not a box that moved.
  This round it passed serially once and in four reruns of the four GUI files under `-n 4`, at
  load averages 25-31. The repo has no code remedy for a browser test under shared load:
  `tests/test_watch_browser.py` carries no retry, rerun or slow mark, and the recorded practice
  is to rerun a lone red row alone and treat it as real only if it fails there. So the test is
  unchanged. A second failure with the same message would point at focus being lost between the
  click and the keystroke, which is worth a probe.

  *Measured* (`[dev]` venv plus playwright, darwin/arm64): fast
  selection 14484 passed, 410 skipped, 32 xfailed in 10 min 21 s, through `serial.py` with no
  other suite running. That is the first round's count plus the two added server tests. vitest
  626 passed; svelte-check 396 files, 0 errors, 0 warnings. The four GUI files
  (`test_gui_layout_browser.py`, `test_gui_manual.py`, `test_gui_server.py`, `test_gui_dist.py`)
  220 passed serially. `npm run build` leaves the committed dist unchanged; ruff clean;
  `tests.reader_output` exit 0, unchanged against the merge-base.

  Next: Yue reviews the settled calls below, the visual ones first. The app-wide heading
  register is ruled (2026-11-09, option A), and a follow-up WP carries it.

- **2026-11-09** — all seven tasks landed, by a ghostshift runner; PR #1498. With no project open, `rietx
  gui` now shows the round-9 start screen: New project…, Open…, the recent list, the examples, and
  links to the manual and the tutorials. A bare launch reopens the last project instead. New
  project is one dialog of four rows (pattern, phases, instrument, project) that asks for no mode
  and no plan; the instrument is assumed as Bragg-Brentano Cu Kα1/Kα2 where the file's header names
  none, and the row says `assumed`. The old wizard is gone from the Model panel. What this rules
  out: a project made from a foreign program's project file, which a browser upload cannot carry
  with its data file.

  *Done.* Server: the recent list keeps a moved project as `missing` and records each project's
  phases at open; `POST /api/recent/remove`; `project_new` takes a list of structure forms, joined
  before the species check; `rietx gui` with no project reopens the list's head, and any `OSError`
  on open leaves the start screen up. Frontend: `panels/Start.svelte`, `panels/NewProject.svelte`,
  `SpaceGroup.svelte` (a typeset symbol, `lib/symmetry.ts:symbolTokens`), `lib/wizard.ts`'s state
  rewritten for the dialog, the wizard and empty state out of `Model.svelte`. Manual: the
  quickstart's two sections, the header table, the route table, the empty-state screenshot (taken
  from a server per theme now, or the dark pass had a project open). `docs/practice.md` § The
  start screen and the New project flow. `gui/CLAUDE.md`: the WP-1205 opener rule restated for the
  shell, and three rules for the new screens.

  *Review.* `/code-review high --fix` found eight; seven fixed in `2b265cc76` (symbol labels kept
  their case, a replaced pattern dropped the last file's header anode, Windows separators, a typed
  cell blocked while its lookup is in flight, species-check paths in a list, any `OSError` on open,
  the resolved symbol on a typed-cell row). Declined: two typed cells in one create are both named
  `phase`; naming typed cells is a design call, and every path is keyed by index. No test covers
  the list form's species-check path.

  *Measured* (`[dev]` venv, darwin/arm64, another session's suite not running per `serial.py`):
  fast selection 14482 passed, 410 skipped, 32 xfailed in 10 min 22 s, the seven added
  tests 5.1 s together (`tests.added_test_times`). vitest 626 passed; svelte-check 0 errors, 0
  warnings; `test_gui_layout_browser.py` 16 passed serially (one older test,
  `test_a_pending_edit_moves_nothing_in_the_action_bar[stacked]`, failed once under `-n 4` beside
  three other files and passed alone); ruff clean; `tests.reader_output` exit 0, unchanged
  against the merge-base.

  *Settled by Claude, reversible* (for Yue; the call, then the alternative):
  1. The project's default folder is the server's suggestion, since a browser upload carries no
     folder; the pattern's own folder waits for the desktop app.
  2. Add phase "From a TOPAS, FullProf or GSAS project…" is deferred: no upload kind brings the
     data file the project names.
  3. Show in Finder is omitted: a browser page cannot reveal a folder.
  4. The header's Open… shows the start screen over the open project, with Back to the project;
     the alternative is the File menu, out of scope here.
  5. A CIF beside a typed cell makes a Le Bail project; the alternative refuses the mixed set.
  6. The instrument form shows geometry, anode or wavelength, and radius; the other preset fields
     wait under Advanced. The alternative is the whole preset form at once.
  7. The anisotropic-ADP checkbox sits on the CIF's phase line, shown only when the file has a
     U^ij loop; the alternative is under Advanced.
  8. The wordmark is a 30 px class in `app.css`, the one type size outside the scale.
  9. "The last project" is the head of the recent list; there is no Close verb yet.
  10. Drag-and-drop of a file onto the window is deferred.
  11. A recent row's phases are a label written at last open, not re-read.
  12. An example's "Open a fresh copy" is the old Reset, offered only once built, with no confirm.
  13. The `assumed` tag is a neutral chip; the alternative is the warn tone.
  14. A space group is set in "STIX Two Text", then Times: no font is bundled.
  15. ~~Headings take the app's section-heading register (small capitals, muted).~~ Withdrawn in
      the second round: it contradicted the maintainer's ruling of 2026-11-06 ("Sentence-case
      headings"), and a written ruling outranks a settled call. The two screens' headings are
      now sentence case, at the prototype's size. Every other panel still wears `app.css`'s
      uppercase `h2`/`h3`, so the app-wide register conflicts with the ruling. Yue ruled it on
      2026-11-09 (option A): sentence case app-wide, one `app.css` rule at this WP's register,
      carried by a follow-up WP (`visual-language.md` open question 12 in the workshop asked the
      same).
  16. (Second round.) An unnamed typed cell in a create of several phases is named `phase_N`,
      N being its place in the project, as the CIF reader names an unnamed block; a lone typed
      cell stays `phase`. The alternative is a name field on the typed-cell form.

  *Gotchas.* The layout test's label check was made to fail once: with the label column at 3em
  it reported `Geometry` ink 59.75 px in a 39 px column. `make_screenshots.py` regenerates every
  picture; only the two empty-state files were committed, the rest being pixel noise.

  Next: Yue reviews the settled calls above, the visual ones first (13-15, 6, 7). Then the File
  menu (Save a copy, Rename, Move to, Export), which needs a WP of its own and would take over
  call 4. A Close verb would let call 9 mean "the project open at quit".

- **2026-11-09** — filed by a ghostshift runner. No open WP owned the start screen or the New
  project flow: the milestone's five pieces (2123 and the open 2125-2130) are the shell, the
  Parameters panel, the Plan tab, previews and the Background tab, and 2123 lists the start screen
  as designed but not in them. Next: start the checklist.

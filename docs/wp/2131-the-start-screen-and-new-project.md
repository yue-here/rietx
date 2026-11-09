# WP-2131 — the start screen and the New project dialog

Milestone: gui-overhaul · Status: ⬜
Depends on: 2123
Priority: P2 2026-11-09 — a piece of the open gui-overhaul milestone, the maintainer's round-9 design; the window a person first meets

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

- [ ] `GET /api/recent` keeps a moved project as `missing`, carries each project's phases, and
  `POST /api/recent/remove` drops one entry; `project_new` takes a list of structure forms.
- [ ] `rietx gui` with no project reopens the recent list's head, and starts empty when it cannot.
- [ ] The start screen (`panels/Start.svelte`): the two columns, the row menus, Locate…, Remove,
  the example's fresh copy, and the header's Open… showing it over an open project.
- [ ] The New project dialog (`panels/NewProject.svelte`) on `lib/wizard.ts`: the four rows, the
  instrument's source tag, the 6.5em label column, mode from the phases, no plan asked.
- [ ] The old wizard and empty state leave `Model.svelte`; vitest moves to the new components.
- [ ] The layout browser test drives the start screen and the dialog with real clicks; the dist
  rebuilt, the GUI chapters and the empty-state screenshot updated.
- [ ] `docs/practice.md` § The start screen and the New project flow.

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

## Handover log

- **2026-11-09** — filed by a ghostshift runner. No open WP owned the start screen or the New
  project flow: the milestone's five pieces (2123 and the open 2125-2130) are the shell, the
  Parameters panel, the Plan tab, previews and the Background tab, and 2123 lists the start screen
  as designed but not in them. Next: start the checklist.

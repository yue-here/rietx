# WP-2203 — the Structure tab

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — in review, PR #1519; the merge waits on the maintainer's look (row 10) and four visual questions
Depends on: 2123 (the graph column and its tab strip)
Priority: P3 2026-11-10 — a view moved, nothing it draws changes; the milestone's designed pieces are P3 until one blocks another

## Goal

The 3D structure viewer is one of the graph tabs on the left of the window, beside Pattern,
Single peaks and Background, rather than the Model panel's third column. Everything it drew and
every control it had stay as they were, and every panel and route reachable before stays
reachable.

## Context

### The designs, and the rulings they rest on

The prototypes are not published, so each design this WP builds is restated here with its ruling.

1. **The structure is a graph tab.** Ruled 2026-11-07 (sixth review): "A **3D structure** tab as
   one of the graphical views." The fourth review of the same day had put the graphs on the left
   in tabs and the model panel on the right (WP-2123). `gui/STYLE.md` § Layout and panels lists the
   graph tabs as Pattern, Peaks, Background and Structure.
2. **The graphs say what they show.** Ruled 2026-11-07 (fourth review): each graph carries a title
   line, so a preview never reads as a changed fit (WP-2123, acceptance row 6). The prototype's
   Structure title read "Last fit", or "Preview, not refined" while a position or cell edit was
   pending.
3. **A panel moves into the new shell as it is, and is redesigned by its own piece**
   (`docs/milestones/gui-overhaul.md` § Scope). The prototype draws the structure with a "Look down
   a b c" group, an Atoms | Polyhedra choice and a species legend on the title row. Those are a
   redesign of the viewer's controls and stay out of this WP.
4. **The 3D look is crystallography's** (`gui/STYLE.md` § Plots; WP-1015, WP-1462). Nothing in the
   scene changes here.

### What the tree holds today (origin/main e0405b2d6)

- `gui/src/panels/Model.svelte` mounts `panels/Structure3D.svelte` as a third column behind a
  header `3D` toggle, with a splitter between the instrument column and the view and a stacked
  `3D` section under a narrow pane. `Model.svelte`'s `stamp` (bumped by every `load()`) is the
  viewer's refetch signal.
- `gui/CLAUDE.md` § Structure viewer opens with the rule "The viewer is the Model pane's third
  column, never a tab (WP-1015)". The 2026-11-07 ruling replaces it.
- `gui/src/lib/resize.ts`: `MODEL_MIN.view` and `modelThreshold()` count the 3D column and two
  grips. With the view gone the Model pane needs one grip and two floors.
- `gui/src/lib/tabs.ts:GRAPH_TABS` holds three tabs. `tabs.test.ts` writes it into
  `tests/data/gui/panels.json`, and `tests/test_gui_manual.py` fails until a GUI chapter names a
  new one.
- `docs/docs/reference/gui-guide.md` § Model carries "### The 3D view" as "A third column of this
  panel". `docs/docs/start/gui-quickstart.md`'s tab table describes Model with "a 3D view of the
  cell".

### Tier

No flag, threshold or automatic action is added. The one rule this WP adds is where a view sits.

## Non-goals

- The prototype's title-row controls for the structure (look down a, b, c; Atoms | Polyhedra; the
  species legend). The viewer's controls move as they are.
- A structure preview at pending edits. The prototype scaled the cell frame under an unapplied cell
  edit; previews are the WP-2125 and WP-2128 route and sliders, and no route serves a structure at
  unapplied values.
- The Peaks graph tab (the "Peaks and indexing" piece).

## Tasks

- [x] The Structure graph tab: `GRAPH_TABS` gains it, `App.svelte` mounts the viewer in its own
      view, refetching on the head and on the Model pane's reloads while it is shown, and the title
      line says what it draws.
- [x] The Model pane loses its 3D column, toggle and splitter; `MODEL_MIN`, `modelThreshold()`
      and the stored column widths follow two columns.
- [x] Tests: the vitest viewer block opens the tab, a hidden tab asks for nothing, and the layout
      test presses the viewer's controls; `tests/test_structure3d_browser.py` opens the tab.
- [x] The manual: the graph tabs name Structure, § The 3D view moves under the graph tabs, a
      `structure-tab` screenshot, and every shot showing the graph strip regenerated.
- [x] `gui/CLAUDE.md` § Structure viewer: the third-column rule replaced.
- [x] The dist rebuilt.
- [x] Skill: none. The agent skill drives the python API, and nothing an agent calls moves.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build && git diff --exit-code src/rietx/gui/static
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_manual.py tests/test_gui_dist.py tests/test_gui_palette.py tests/test_gui_style_guide.py
.venv/bin/python -m pytest tests/*_browser.py    # playwright installed; CI runs none of them
```

Milestone rows 1 (no click moves the layout), 2 (every panel and route reachable), 10 (the
maintainer looks) and 11 (screenshots beside the prototype's in the PR).

## References

- `gui/STYLE.md` § Layout and panels, § Plots.
- `docs/milestones/gui-overhaul.md` § Designed, not yet filed (the "Structure tab" row this WP files).

## Handover log

- **2026-11-10** — the 3D structure is a graph tab. The viewer that sat in the Model panel's
  third column now opens from a fourth tab, Structure, beside Pattern, Single peaks and
  Background. It draws and controls exactly what it did. It fetches only while its tab is shown,
  and a look at another tab keeps its WebGL context, so returning costs no request when nothing
  moved. The Model panel keeps two columns, and its stacking width drops from 1256 px to 991 px.
  Four visual choices wait on the maintainer's look (below). The merge waits on that look anyway
  (milestone row 10). PR #1519.
  - *Done.* `GRAPH_TABS` gains `structure`; `App.svelte` mounts `Structure3D` in its own `.gview`
    with a title line ("Structure at the current values", "Structure, refining" during a run;
    `lib/structure3d.ts:structureTitle`). The viewer keys its fetch on the project path, the head,
    `Model`'s reload after its own write, and its own choices, and asks nothing while `active` is
    false. `Model.svelte` lost the toggle, the view column and its splitter; `model_columns`
    stores one width, and an older two-width entry still opens (the second is read past).
    `MODEL_MIN.view` is gone and `modelThreshold()` is 666 + 320 + 5 = 991 px. Manual: the
    graph-tab list, a new § The structure in `gui-guide.md`, the quickstart's Model row, a new
    `structure-tab` screenshot pair, and the five pairs that show the graph strip retaken.
    `gui/CLAUDE.md`'s "never a tab" rule replaced.
  - *Review* (`/code-review high --fix`, 280e8048f): six findings, all taken. A phase-free
    project showed the server's 404 as a red error and kept the last project's picture (the old
    column was unmounted there); it is now the viewer's grey empty state, with a vitest that
    fails without the fix. A project switch now resets the phase and the chemistry choices.
    `Model`'s head-driven reload no longer signals the tab, which follows the head itself (one
    edit made three requests, now two). The instrument column's floor now counts the grip. One
    stale comment.
  - *Measured* (venv `[dev]` + playwright 1.65.0, darwin arm64, node 24.22.1): vitest 719
    passed (32 files; +1 over main's 718 at the branch's first run, the review's empty-state
    test); svelte-check 416 files, 0 errors; every `tests/*_browser.py` (eight files) 154 passed, none failed or skipped, after the review fixes and the probe fix (42 in the four GUI files, 112 in compare, html, rxplot and watch); the committed dist rebuilds byte-identical after `npm ci`; fast selection (`-m "not slow"`, through the machine's suite lock) 14621 passed, 410 skipped, 32 xfailed in 15 min 33 s, the branch adding two cases (the new layout test, wide and stacked, 4.86 s together in this run) and no skip; sphinx `-W` exit 0;
    `tests.reader_output` exit 0 ("unchanged against the merge-base"); ruff clean. The new
    layout test, `test_the_structure_tab_holds_still_under_its_choices[wide|stacked]`, clicks
    each view button (ellipsoids, balls, a, b, c, reset) and compares the landmark boxes.
  - *Gotchas.* The viewer's canvas sits inside a `.plot`, now mounted (hidden) on every page, so
    a probe counting `.plot canvas` for the pattern plot must exclude `.viewer`
    (`test_gui_browser.py`'s `PANES` did not, and failed with four panes). In a stacked window
    the viewer's 300 px canvas floor overflows its half-height tab, so `.gview.structure`
    scrolls; the layout test scrolls each button into view before it snaps.
  - *Generality.* Not dispatched: `_audit.py` is untouched and the branch adds no refinement
    heuristic (a view moved).
  - *Open visual questions* (taken nearest the prototype or the rules; screenshots beside the
    prototype's at 1440×900 and 700×900 are local to the runner's machine,
    `~/.cache/ghostshift/rietx/wp-2203/compare/side-by-side-{1440x900,700x900}.png`):
    1. Title wording. Taken: the Background tab's form, "Structure at the current values". The
       prototype's "Last fit" is untrue after an applied edit, since a result survives a
       `set_value`. Alternative: "Last fit" / "Preview, not refined".
    2. The viewer's controls moved as they were: the "View" header with balls | ellipsoids above
       the canvas, the legend, view-down and PNG buttons below. The prototype puts "Look down
       a b c", Atoms | Polyhedra and the species legend on the title row, and has no "View"
       heading under the title line. Ruled out of scope here (§ Context 3); the redundant
       heading is the smallest piece of it.
    3. Stacked (700 px wide): the view scrolls inside its half-height tab and the legend and
       buttons sit below the fold. Alternative: a smaller canvas floor under a stacked window.
    4. The Model panel's instrument column takes all the width the view freed. Alternative: cap
       it and leave the space empty.
  - *Settled.* `model_columns` keeps one width, older entries read past (a `ui` key, never a
    schema field; `gui/CLAUDE.md` § the document's `ui` keys). The tab is present with no phase
    and says so, since a tab that appears with the first phase would move the strip (row 1).
    ROADMAP's prose left alone: three sibling runners edit the milestone files today. Only the
    screenshots that show the graph strip were retaken; the rest showed no change and were
    reverted.
  - *Next.* The maintainer looks (row 10) and answers the four questions; then close this WP
    ✅. A redesign of the viewer's controls (question 2) is its own piece; no WP owns it yet.
- **2026-11-10** — created by a ghostshift runner, number assigned by the shift lead in the
  gui-overhaul 22xx block. No open WP owns the move: the milestone record lists it under
  § Designed, not yet filed.

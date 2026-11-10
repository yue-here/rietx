# WP-2203 — the Structure tab

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — claimed by a ghostshift runner
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
- [ ] The manual: the graph tabs name Structure, § The 3D view moves under the graph tabs, a
      `structure-tab` screenshot, and every shot showing the graph strip regenerated.
- [ ] `gui/CLAUDE.md` § Structure viewer: the third-column rule replaced.
- [ ] The dist rebuilt.
- [ ] Skill: none. The agent skill drives the python API, and nothing an agent calls moves.

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

- **2026-11-10** — created by a ghostshift runner, number assigned by the shift lead in the
  gui-overhaul 22xx block. No open WP owns the move: the milestone record lists it under
  § Designed, not yet filed.

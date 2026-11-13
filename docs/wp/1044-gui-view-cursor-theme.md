# WP-1044 — GUI defects found by use: the view, the armed cursor, the theme

Milestone: v1.0 · Status: ✅ 2026-08-06 — all four landed, each against a browser
measurement; three of the four reports named a cause and only one was right
Track: The human GUI
Depends on: 1029 (theming), 1032–1033 (`Plot.svelte`, the armed gesture), 1027 (peaks)

## Goal

Four defects reported from a use session are fixed, each with the browser
measurement that found it: a horizontal zoom survives an excluded region, a peak
edit does not throw the view away, an armed range gesture says so at the pointer,
and a theme chosen once stays chosen when another project is opened.

## Context

The four, as reported:

1. *Theme does not persist on loading a project.*
2. *Horizontal zoom does not work when there are excluded regions.*
3. *When selecting range/regions, the cursor changes to the zoom cursor.*
4. *On selecting/deselecting peaks, the zoom immediately resets.*

**2 and 4 are one defect** and neither is about the thing it was reported
against. Every redraw handed `Plotly.react` a layout with no `range`, so plotly
re-autoranged over *everything drawn* — and what is drawn is not only the fetched
window: the peak markers span the whole pattern (the list is not windowed), and
so do the mask shapes, which are `xref: "x"` and therefore take part in the
autorange, the same property `maskShapes` was already clipping against
(WP-1033). Measured in Chrome on a fitted synthetic project, a drag to
**9.97–14.66°** came back as:

| also on the plot            | axis after the refetch |
|-----------------------------|------------------------|
| nothing                     | 9.97–14.66 ✓           |
| a peak list                 | 4.57–24.85             |
| an excluded region at 4–5°  | 3.99–24.88             |
| an excluded region at 20–21°| 4.57–24.85             |
| a fitted range of 8–18°     | 3.00–24.94             |

So the zoom worked only on a plot with nothing else on it. The same react is
what threw the view away on a peak edit — and on the **raw** view (no fit) there
is not even a window fetch to land back in, so a shift-click went 9.97–14.66 →
the full 1.74–25.25 in one gesture.

The repair is WP-1015's rule for the 3D camera, one panel over: **`react`
rebuilds the scene, so the view must be handed back on every draw**, read off
`_fullLayout` immediately before the call rather than tracked in a variable.

3 is measured too: plotly's `updateFx` gives the drag layer `cursor-crosshair`
for every dragmode that is not `pan`, so `dragmode: "select"` and
`dragmode: "zoom"` are pointer-identical — arming changed the mode and nothing
under the pointer said so.

1 is a design question rather than a bug in the code that implements it.
WP-1029 persisted the theme in `ProjectDoc.ui` "like every other GUI setting",
and `readUi()` therefore *re-reads it per project*: measured, choosing dark and
then opening a second project comes back `system`. A width or Simple/Advanced is
plausibly the project's; a theme is a fact about the person and the room they
are in.

## Non-goals

- The GUI manual and onboarding — WP-1017.
- Persisting anything else at app level; `/api/settings` opens the store with
  one key in it and the same open-dict rule `ProjectDoc.ui` has.
- Migrating a stored `ui.theme` out of existing projects: the key is simply no
  longer read (the frontend owns those keys, and an unread one is inert).

## Tasks

- [x] The view is handed back on every draw (`lib/plot.ts:heldRanges`/`span`,
      `Plot.svelte`) — fixes 2 and 4, and the window a redraw refetches follows
      the axis instead of falling back to the whole pattern.
- [x] An armed range gesture gets its own cursor (`col-resize` on the plot-area
      rect, which beats an inherited one with no specificity fight).
- [x] The theme is the person's, not the project's: `GET`/`POST /api/settings`
      over `state_dir/settings.json`, beside `recent.json`.
- [x] Tests: vitest over `heldRanges`/`span` and the panel's own draw;
      `test_gui_server.py` over the settings store.
- [x] Docs: `gui/CLAUDE.md` rules, root CLAUDE.md's GUI paragraph, ROADMAP row
      and focus, the v1.0 narrative, and the inherited mailboxes of 1003 (a second
      `ui` scope to freeze; the "a `ui`-only patch is not model state" question
      is now only about four keys) and 1017 (three manual sentences made wrong).

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
npm --prefix gui run build && git diff --exit-code src/rietx/gui/static
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py
.venv/bin/python -m ruff check src tests examples
```

and, in a real browser against a fitted project (the pass this WP was built
from): a drag zoom holds with a peak list, an excluded region and a fitted range
on the plot; one drag costs exactly one `/api/result/window` fetch; a peak
toggle keeps the view and refetches *that window*; a double-click still resets
to the whole pattern; a panel's zoom request still moves the axis, twice in a
row for the same region; the armed cursor is `col-resize` and returns to
`crosshair` on Esc.

## References

- WP-1015 — "`react` with fresh trace objects resets the gl3d camera, so the
  view must be handed back on every draw"; the rule this reuses.
- WP-1033 — `maskShapes`, and the measurement that a data-referenced shape takes
  part in the autorange (bands drawn past the data *became* the range).
- WP-1029 — the three-way theme and `ProjectDoc.ui`; this WP moves one key out.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

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

## Handover log

- **2026-08-06** — **all four items landed; WP closed.**

  **Done.** (1) `lib/plot.ts:heldRanges`/`span` + `Plot.svelte`: the view is
  handed back on every draw, the window a redraw refetches follows the axis,
  `doubleClick: "autosize"`, and two reactivity repairs the browser count forced
  — the repaint effect reads `held` **untracked** (a fetch cost two identical
  reacts: 2 per zoom drag, 6 at boot; now 1 and 3) and `view()` compares the
  knobs untracked (or the *fetch* effect takes a dependency on the residual
  selector). (2) `col-resize` on the plot-area rect while armed. (3) the theme
  moved to `GET`/`POST /api/settings` over `state_dir/settings.json`, the
  control left the `{#if project}` block, and `ProjectDoc.ui.theme` is now
  unread rather than migrated. (4) tests: vitest 376 → 390 (6 pure + 6 panel),
  `test_gui_server.py` +2 and its in-flight 409 row now also says what is *not*
  refused.

  **Measured green twice.** Before merging `main`: fast **1729 / 108** in 5:04,
  full **1821 / 117** in 37:14, where passed+skipped moved by exactly the two
  tests added, in both selections — the closing-sum check, within one lineage.
  After merging `main`'s 1041/1040 (which is what the numbers block now quotes):
  fast **1750 / 108** in 2:56, full **1845 / 117** in 23:17, both uncontended and
  both venv `[dev]`. The wall clock more than halved on the same tests, which is
  the range rule's whole point — the first pair shared the machine with another
  worktree's suite.

  **The WP was renumbered from 1043 to 1044 at the merge**: the indexer session
  opened its own `1043-agent-and-human-indexing.md` while this branch was in
  flight. The five commits before the renumber still carry `WP-1043:` subjects;
  history rewriting was not available, so the number is settled by the renumber
  commit and by every file it touched.

  **Gotchas for whoever is next in this file.**
  - **The fixture's fit is in memory.** A freshly opened `.rex` has no result,
    so the plot draws the *raw* pattern — where the relayout handler returns
    early and nothing refetches, so every zoom "works". Five mask configurations
    came back green that way before a network count showed **zero**
    `/api/result/window` fetches at boot. Run a fit over HTTP first, and count
    the requests before believing the pixels.
  - **Instrumenting plotly from the page is unreliable**: a `$state` rune proxies
    the namespace and caches each property on first read, so a poll that patches
    `window.Plotly.react` after boot silently counts nothing (it caught
    `relayout` and no reacts at all). Wrap it from a **setter** on
    `window.Plotly` in an init script.
  - **The modebar was checked and is fine**: pinning a range does *not* make
    `Reset axes` a no-op, because `_rangeInitial` is only captured at
    `newPlot` and a `react`'s range never becomes "initial" — both it and
    `Autoscale` still go 9.97–14.66 → the full 1.74–25.25. Only the
    *double-click* needed the config change.
  - **On the Peaks tab a double-click is two add-peak verbs**, and the redraw
    they cause can land after plotly's autorange and re-pin the window. Left
    alone: click-to-add is WP-1027's choice and the interaction is only visible
    on that one tab. If it is ever fixed, it belongs beside the arming rule
    (a pointer meaning that is ambiguous everywhere is a mode).
  - The scratchpad drivers that measured all of this:
    `zoomcheck.mjs` (six mask configurations), `verify.mjs` (drag → one fetch,
    peak toggle, double-click, cursor), `request.mjs` (a panel's window, twice),
    `rawview.mjs` (no fit), `count.mjs` (reacts per drag), `theme.mjs`,
    `empty.mjs`. They are not committed — a browser pass is a measurement, not a
    fixture — but the harness is three lines around the cached chromium.

  **Next**: nothing on this WP. [1017](1017-gui-manual-onboarding.md) and
  [1003](1003-api-freeze-pypi.md) have been told what changed under them.

- **2026-08-06** — created; the plot's view fix and the armed cursor landed
  against a browser pass (`scratchpad/{zoomcheck,verify,request}.mjs`).

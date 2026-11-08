# WP-2123 — the layout shell

Milestone: gui-overhaul · Status: 🔄 2026-11-08 — claimed by a ghostshift runner
Depends on: —
Priority: P2 2026-11-08 — the first piece of the open gui-overhaul milestone; pieces 2-5 build inside it

## Goal

`rietx gui` opens on the redesigned window: the graphs on the left in tabs, each with a title
line saying what it shows; the model panel on the right in tabs with a sash; a collapse button
for each side that never moves; a one-row action bar ending in Apply and refine; segmented
choices that no longer look like actions; and a one-column layout below a measured width.
Every panel of today's GUI sits inside the new shell unchanged, and a browser test shows that
no click moves the layout unless it asks to.

## Context

### Where the shell is today

`gui/src/App.svelte` draws a header (the name and version, the project line, Rwp and GoF, then
Open…, a `Split | Full` segmented pair, `Simple | Advanced`, the theme, the run pill, Run,
Cancel and ⌘K), and under it `main`: the pattern (`panels/Plot.svelte`) in `.plotcol` on the
left and the panel column `.side` on the right. The column holds a `Splitter` on its left edge,
the first-run checklist, the strip of nine tabs from `lib/tabs.ts` (Parameters, Plan, Peaks,
Model, Text, Series, Report, History, Build), every panel mounted and hidden by class, and the
Console at its foot. `Split | Full` hides the plot and gives the column the whole window. The
column's width is `ProjectDoc.ui.side_width`, persisted on the verb; `null` means the CSS clamp
`clamp(340px, 38%, 560px)` decides. Value edits in Parameters gather until its own footer's
Apply, a footer that appears on the first edit (`panels/Params.svelte`, `editState`).

The refinement verbs the action bar needs exist. `POST /api/run {"kind": "fit"}` runs the
project's plan (`App.svelte:start`). `POST /api/run {"kind": "stage", "stage": StageSpec}` runs
`Project.run_stage` on the working free set plus the stage's `turn_on`, so a stage with an
empty `turn_on` refines exactly what is ticked (WP-1208 measured that `run_stage` keeps a
hand-freed row and `fit` drops it). `PATCH /api/params` applies values and vary flags in one
call. Both run kinds answer 409 while a run is in flight.

### The designs, and the rulings they rest on

The maintainer designed the overhaul with Claude in twelve rounds of prototypes between
2026-11-06 and 2026-11-08 and reviewed each on screen. The prototypes are not published, so
each design this WP builds is restated here with its ruling.

1. **Graphs on the left, in tabs.** Ruled 2026-11-07 (fourth review): the graphs sit on the
   left in tabs and the parameter panel on the right. The third review the same day had already
   put graph views in tabs of the main panel ("should probably be a tab in the main panel,
   along with peaks"). The Peaks preview, the Background view and the Structure view join as
   tabs in later pieces.
2. **A title line on every graph.** Ruled 2026-11-07 (fourth review): the graphs carry a title
   saying what the view shows, so a preview never looks like a changed fit. The bar merge the
   maintainer approved on 2026-11-07 ("go") puts the title on one row with the view's own
   controls: the controls take the width they need from the panel's width alone, and the title
   takes the rest and shortens with an ellipsis, so a longer title never rewraps the controls.
3. **The right panel's tabs are modes.** Ruled 2026-11-07 (fourth review): the right panel's
   tabs switch mode, and two modes never show at once. Today's nine tabs already behave so.
4. **A sash between the two.** Ruled 2026-11-07 (fifth review): the panels are adjustable,
   following the practice of VS Code and the Claude Code pinnable panel. In the prototype, as in
   VS Code, the sash drags, answers the arrow keys when focused, and a double-click resets it.
5. **Both side panels collapse, and each button sits on its own side and never moves.** Ruled
   2026-11-07 (sixth review). The prototype puts the graphs' toggle at the far left of the top
   bar and the model panel's at the far right, in a bar whose contents never change, and refuses
   to hide one panel while the other is hidden. Claude agreed in that review, citing the layout
   toggles at the two ends of the Xcode and VS Code title bars.
6. **One action bar, one row.** Ruled 2026-11-07 (fourth review): the panel ends in Apply and
   "Apply and refine", and refine offers one cycle, with a keyboard shortcut, or the staged plan.
   The bar merge approved the same day ("go") makes the action bar one row. In the prototype it
   reads, left to right: the refine choice (One cycle, or Staged plan with its stage count),
   then a pending count in a slot reserved at its widest so its appearance moves nothing, Revert,
   Apply, and the filled primary, which reads "Refine" with nothing pending and "Apply and
   refine" otherwise (⌘Enter). One filled primary per view, every other button outlined (settled
   2026-11-06, the maintainer having left it to Claude).
7. **A choice never looks like an action.** Ruled 2026-11-07 (fifth review), after the
   maintainer found a two-way toggle and a Delete button drawn alike. Fixed as a class: every
   segmented choice is a sunken track with one raised option, and actions are outlined or icon
   buttons. Today's `.segmented` fills the chosen option with the accent, which is how the
   primary button is drawn, so the register itself is what changes.
8. **One column below a width.** Ruled 2026-11-07 (sixth review): below a width the window drops
   to a single column, graphs above or below the model, as the Claude app drops to one panel.
   The prototype stacks graphs above the model below the sum of the two panels' floors, with a
   horizontal sash. The root CLAUDE.md rule for `rietx watch` applies: the width where side by
   side stops being possible is computed from floors already declared, stated once, never
   chosen.
9. **No click may change the layout unless it asks to.** Ruled 2026-11-07 (third review) as a
   general rule ("this happens quite a lot at the moment"), and adopted as interaction rule 8 on
   2026-11-08. Expanding, collapsing, switching a tab and jumping ask for a layout change.
   Editing a value, ticking a box, holding a term and choosing a mode do not. The maintainer
   asked for a probe that clicks every control and compares element boxes, and the prototype's
   probe did that on a fresh page per control.
10. **No permanent explanatory text.** Ruled 2026-11-07 (sixth review): an explanation lives in
    a tooltip or a help box, never as a line on the page.

Two working rules from the design rounds bind the checks here. A browser check clicks as a
person does (`page.click`, `page.mouse`, `page.keyboard`); a check that cannot click an element
has found a page defect, and switching it to a script click hides it (found 2026-11-08, when
rows a global rule had made unclickable passed a script-clicked check). And the server serves
the committed dist, so every browser pass about a source change follows `npm --prefix gui run
build`.

### Rulebook seams

- **Registers** (`gui/CLAUDE.md` § House style): size, padding and radius belong to the register
  and never to the call site, and `lib/style.test.ts` fails a panel that declares them. The
  segmented change is one edit to `.segmented` in `gui/src/app.css`, and every use inherits it.
- **Colours** (root CLAUDE.md, WP-1429): values live in `src/rietx/viz/theme.py`, and
  `gui/src/tokens.css` is generated (`python -m rietx.viz.theme > gui/src/tokens.css`) and held
  equal by `tests/test_gui_palette.py`. The same rule says a page's extra roles are `color-mix`
  over the chrome tokens, never a token of their own. The track and the raised option are two
  new *surface* levels below and above `--panel`, which the nine chrome tokens do not have,
  so they are added as tokens; the conflict is recorded for the maintainer below.
- **Layout state** (`gui/CLAUDE.md` § One column): a layout is a view choice, session-local and
  unpersisted, while a width is a setting persisted on the verb in `ProjectDoc.ui`. The collapse
  state follows the first and the sash width the second.
- **Tabs** (WP-1017): `lib/tabs.ts` is the strip as data and `tabs.test.ts` writes
  `tests/data/gui/panels.json`, which `tests/test_gui_manual.py` holds to the GUI chapters. A new
  graph tab joins that corpus and needs its chapter in the same change.
- **Screenshots** (WP-1017): `docs/docs/make_screenshots.py` is the one authority for each, and
  a picture is judged by looking at it.

### Tier

No rule this WP adds is a heuristic in the sense of `docs/milestones/generality.md` § The rule:
nothing here reads the data or decides for a fit. The stacking width is arithmetic over declared
floors.

## Non-goals

- The Parameters panel, the Plan tab, the previews and the Background tab are pieces 2-5. Their
  panels move into the shell as they are.
- The Structure view stays the third column of the Model tab. Moving the 3D viewer into a graph
  tab reflows the Model panel's three-column widths (`MODEL_MIN`, `modelStacks`), which is a
  redesign of that panel.
- The workflow menu, the File menu on the project name, the settings dialog, the bottom panel
  with Console and History, the status bar and the start screen were designed too, and are not
  in the five pieces yet.
- No new route. The action bar calls `PATCH /api/params` and `POST /api/run`.

## Tasks

- [ ] `.segmented` redrawn app-wide: a sunken track with one raised option, from two new surface
  tokens (`--sunken`, `--raised`) in `theme.py`, `tokens.css` regenerated.
- [ ] The top bar: the graphs' collapse button first and the model panel's last, in a row whose
  middle wraps while the two buttons keep their places; `Split | Full` retired, since collapsing
  the graphs is the full-width column. One panel always shows. Palette commands for both.
- [ ] The graph column: a tab strip (Pattern, from a `GRAPH_TABS` array in `lib/tabs.ts` written
  into the panel corpus) and a title line saying what the view shows, with Rwp, GoF and the
  not-a-fit chip moved there from the header.
- [ ] The action bar at the foot of the model panel: the refine choice (One cycle = one stage on
  the ticked set; Staged plan = the project's plan), the pending count in a reserved slot,
  Revert, Apply, and the filled Refine / Apply and refine (⌘Enter), wired to the Parameters
  panel's pending edits; the header's Run button and the Parameters footer retired. The sash
  resets on double-click.
- [ ] The one-column layout below the width computed from the two panels' floors and the grip,
  graphs above the model, the sash turned horizontal.
- [ ] The layout-shift browser test: every control clicked on a fresh page in each starting
  state, element boxes compared before and after, real clicks only.
- [ ] Vitest for the shell's logic, the dist rebuilt, the GUI chapters and the screenshots the
  shell changes regenerated.
- [ ] Skill: none expected. The agent skill drives the python API, and the GUI's routes are
  unchanged.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_manual.py tests/test_gui_palette.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The layout-shift test reports no unasked-for movement in any starting state, every panel of
today's GUI opens from the new shell, and the page does not scroll sideways at 420 px.

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-08, restated above with their dates.
- VS Code user interface, https://code.visualstudio.com/docs/getstarted/userinterface: the
  layout of side bars, panel and title-bar layout controls.
- `docs/practice.md` § The window layout of a GUI.

## Handover log

- **2026-11-08** — filed by a ghostshift runner as the first piece of the gui-overhaul milestone,
  which this session opened. No open WP owned the GUI shell. The number 2123 was claimed by the
  shift before the milestone claimed 22xx for its later pieces. Next: start the checklist.

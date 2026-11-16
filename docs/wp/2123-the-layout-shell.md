# WP-2123 — the layout shell

Milestone: gui-overhaul · Status: ✅ 2026-11-09 — the layout shell merged in #1476; the fit statistics' home with the graphs hidden is the milestone's action-bar row
Depends on: —

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
  over the chrome tokens, never a token of their own, so the track and the raised option are
  mixes in `app.css` and `theme.py` is untouched (settled call 11).
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

### Calls settled by Claude

No ruling covered these, so each took the smallest neutral option. Each is marked "settled by
Claude, reversible", with its alternative, and waits for the maintainer's review of the PR.

1. Settled by Claude, reversible: the header's `Run` is retired and the action bar's `Refine`
   is the one way to start a fit from the window, defaulting to `Staged plan`, so a first
   press does what `Run` did. The pill and `Cancel` stay in the header. Alternative: keep `Run`
   in the header beside the action bar.
2. Settled by Claude, reversible: Rwp, GoF and the not-a-fit chip move from the header to the
   Pattern title line, which design 2 gives the view's own facts. Alternative: keep them in the
   header.
3. Settled by Claude, reversible: the graph strip holds `Pattern` alone. The Structure view
   stays the Model tab's third column until the piece that moves it. Alternative: move the 3D
   viewer into a graph tab now.
4. Settled by Claude, reversible: the action bar shows under every right-hand tab and applies
   the Parameters tab's pending edits only. The Model and Text panels keep their own Apply,
   outlined since the second round so the bar's Refine is the one filled button in every view
   (design 6); folding their edits into the bar is owed to piece 2. Alternative: show the bar
   under the Parameters tab only.
5. Settled by Claude, reversible: the title reads `Observed pattern` before any fit, `Last fit`
   after one and `Refining` during a run. Alternative: name the model or the stage.
6. Settled by Claude, reversible: the refine choice is labelled `One cycle`, the ruling's word,
   though a rietx stage runs least squares to convergence on the ticked set rather than one
   iteration. `Staged plan` carries no stage count yet. Alternative: `One stage`, and a count.
7. Settled by Claude, reversible: `⌘⏎` (`Ctrl+Enter`) presses the primary everywhere except in
   the Text document, whose editor binds the same chord to its own Apply. No `⌘1`/`⌘2` panel
   shortcuts, since browsers reserve them; the palette carries both collapse commands and a
   one-cycle command. Alternative: other chords.
8. Settled by Claude, reversible: the collapse state and the stacked sash height are
   session-local and unpersisted, as `Split | Full` was. The side-by-side sash width stays
   persisted per project, and a double-click resets it. Alternative: persist the collapse state.
9. Settled by Claude, reversible: the floors are 420 px of graph and 340 px of panel, so the
   window stacks below 760 px. The panel floor is the sidebar's old clamp raised from 300 to
   340, the Splitter's minimum; the graph floor keeps a readable 2θ axis. Alternative: other
   floors, which move the threshold with them.
10. Settled by Claude, reversible: the collapse icons are the prototype's panel glyphs, drawn
    inline, with the filled half showing the side the button hides; stacked, they turn to
    top and bottom halves. Alternative: text labels.
11. Settled on the written rule (root CLAUDE.md, WP-1429: a page's extra roles are `color-mix`
    over the nine chrome tokens, never a token of their own). The track and the raised option
    are mixes of `--fg` into `--panel`, and `light-dark()` picks the dark pair through the
    `color-scheme` that `tokens.css` sets with each palette. The first round added `--sunken`
    and `--raised` as tokens instead, on a workshop handover suggestion that was not a ruling;
    they are gone. The percentages match the prototype's luminances, so the rendered contrast
    is the prototype's to the third decimal: track against option 1.183 light and 1.502 dark.
12. Settled by Claude, reversible: while the model panel is hidden, the action bar moves to the
    foot of the graph column, so Refine stays a visible button with either side collapsed. The
    move is part of the collapse click, which asks for a layout change. Alternative: one bar
    across the whole window, under both sides.
13. Settled by Claude, reversible: while an edit is invalid, the pending slot reads `invalid
    edit`, and the reason (`w: above the upper bound 1`) rides in that slot's tooltip and in the
    invalid cell's own. The slot stays 16ch, which a browser test measures against its longest
    message, so no message is cut and none moves the row. Alternative: a popover above the bar
    that shows the reason without a hover.
14. Settled on the maintainer's ruling of 2026-11-06 (one filled primary per view, every other
    button outlined), with two calls of Claude's, reversible. The wizard's Create project stays
    filled while no project is open, when the wizard is the whole view and no action bar shows.
    The folder browser keeps its filled pick, being a dialog over the window. Alternative:
    outline both.

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

- [x] `.segmented` redrawn app-wide: a sunken track with one raised option, each a `color-mix`
  of `--fg` into `--panel` (the first round's two tokens were withdrawn in the second).
- [x] The top bar: the graphs' collapse button first and the model panel's last, in a row whose
  middle wraps while the two buttons keep their places; `Split | Full` retired, since collapsing
  the graphs is the full-width column. One panel always shows. Palette commands for both.
- [x] The graph column: a tab strip (Pattern, from a `GRAPH_TABS` array in `lib/tabs.ts` written
  into the panel corpus) and a title line saying what the view shows, with Rwp, GoF and the
  not-a-fit chip moved there from the header.
- [x] The action bar at the foot of the model panel: the refine choice (One cycle = one stage on
  the ticked set; Staged plan = the project's plan), the pending count in a reserved slot,
  Revert, Apply, and the filled Refine / Apply and refine (⌘Enter), wired to the Parameters
  panel's pending edits; the header's Run button and the Parameters footer retired. The sash
  resets on double-click.
- [x] The one-column layout below the width computed from the two panels' floors and the grip,
  graphs above the model, the sash turned horizontal.
- [x] The layout-shift browser test: every control clicked on a fresh page in each starting
  state, element boxes compared before and after, real clicks only.
- [x] Vitest for the shell's logic, the dist rebuilt, the GUI chapters and the screenshots the
  shell changes regenerated.
- [x] Skill: none expected. The agent skill drives the python API, and the GUI's routes are
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

- **2026-11-10** — closed. The maintainer merged PR #1476 on 2026-11-09, so the layout shell
  is on `main` and every later piece of the port builds inside it. Nothing of the shell is left
  undone. Its one open question was where Rwp, GoF and the not-a-fit chip go while the graphs
  are hidden (item 6 of the second round). The maintainer ruled on 2026-11-09 to try the action
  bar beside Refine. That build is the row "Fit statistics in the action bar" in
  `docs/milestones/gui-overhaul.md` § Designed, not yet filed, which now names this WP.

  *Leftovers, and where each went.* Item 6 went to that row. Two owed items were already in
  the milestone's § Owed to the port: the Model and Text panels' own Apply beside the bar's,
  and the runs from the Report or Series panel or the `.` key that skip the bar's pending
  edits. The fourteen settled calls were reviewed with the PR at its merge. The narrative went
  to `docs/milestones/v1.12.md` § How v1.12 is getting here.

  Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
  Next: none here. The milestone's next piece is the palette, in the milestone's order.
- **2026-11-09, second round** — a fix round on PR #1476, on the open items the first round
  reported. Five of six are fixed; one is left for the maintainer.

  *Done*, one commit each: (1) the segmented track and raised option are `color-mix` of `--fg`
  into `--panel`, picked per theme by `light-dark()`, and the `--sunken`/`--raised` tokens are
  gone, so `theme.py` and `tokens.css` match `main` again (call 11). The painted colours, read
  in chromium under system, forced-light and forced-dark themes, are 235.8 grey track on white
  light and 44.0 track under a 71.0 option dark, the prototype's luminances. (2) While the model
  panel is hidden, the action bar renders at the foot of the graph column, so Refine stays a
  visible button (call 12). (3) Every panel button is outlined, so the bar's Refine is the one
  filled button in any view: Model's two Apply buttons, Text's Apply and Re-read, Plan's Save
  plan, six in Peaks, Report's Apply, History's Checkout and Series' run. The wizard's Create
  project and the folder browser keep theirs (call 14). `lib/style.test.ts` fails on any other
  filled button, and failed when one was put back on purpose. (4) The pending slot reads
  `invalid edit` and the reason rides in its tooltip and the cell's (call 13). (5) The `r` key
  is the bar's Refine on the staged plan: it applies pending edits first, and an invalid edit
  blocks it. The text and history screenshots were retaken for (3); the other fourteen
  re-rendered with only console timestamps changed and were left alone.

  *Left for the maintainer* (6): with the graphs hidden, Rwp, GoF and the not-a-fit chip are
  hidden too. No ruling places them, and the two candidate homes are both visual calls: back in
  the header while the graphs are hidden, or in the action bar beside Refine.

  *Deliberately not generalised*: a run started from the Plan, Report or Series panel, or by the
  `.` key, still runs without the Parameters edits waiting in the bar. Each is its own panel's
  verb, and routing every run through the bar is a design for the Plan tab's piece. It is in
  the milestone's owed list.

  *Measured* (macOS arm64, worktree venv `[dev]` plus playwright 1.64.1, node 24.22.1): vitest
  612 passed (610 before; +2, the one-filled-primary guard and the `r`-key test); svelte-check 0
  errors; the layout browser test 12 passed (8 before; +4, Refine on screen with either side
  hidden and the invalid-edit slot, each wide and stacked); `test_gui_manual.py` 10 passed; the
  five GUI files of the acceptance line together 73 passed; fast suite (`-m "not slow"`, `-n auto`, queued alone through serial.py)
  14472 passed, 410 skipped, 32 xfailed (14468 before; +4, the new browser cases); ruff clean;
  `python -m tests.reader_output` exit 0, unchanged against 63d7c120a.

  The milestone's owed list now quotes WP-2124's measured 8 of 12 fluorapatite candidates with a
  supercell relation, where it said 2 of 12.

  Next: the maintainer reviews the PR, its fourteen calls and item (6).
- **2026-11-09** — the layout shell landed, in PR #1476, whose merge waits for the maintainer's
  review. The window now has the overhaul's shape: graphs on the left under their own tab strip
  and a title line saying what the graph shows, the nine panels on the right, and one action
  bar under them that applies edits and refines (one cycle on the ticked parameters, or the
  staged plan, on ⌘⏎). Each side collapses from a button at its own end of the header, and a
  window under 760 px stacks the two. Every segmented choice is now a sunken track with one
  raised option. A browser test now clicks every shell control and fails on any box that
  moves; its first runs found four layout shifts, all fixed. Eleven calls no ruling covered are
  listed under *Calls settled by Claude* above, with one rule conflict, for the maintainer.

  *Done*: `.segmented` and two surface tokens; the top bar's collapse buttons (`Split | Full`
  retired); `GRAPH_TABS` and the title line, with Rwp and GoF moved onto it; `ActionBar.svelte`,
  with the header's Run and the Parameters footer retired and Params exposing `apply`,
  `revert` and `onpending`; the sash's double-click reset; the stacked layout from
  `shellThreshold()`; `tests/test_gui_layout_browser.py`; the quickstart and the panel guide;
  `test_gui_manual.py` reads the graph tabs too; every screenshot regenerated and looked at.
  The checklist and the plot's empty state now say Refine where they said Run.

  *Measured* (macOS arm64, worktree venv `[dev]` plus playwright 1.64.1, node 24.22.1): vitest
  610 passed (609 before; +1, the action bar's apply-then-refine test, and the Split | Full
  test rewritten for the collapse buttons); svelte-check 0 errors; the layout browser test 8
  passed; fast suite (`-m "not slow"`, `-n auto`, queued alone through serial.py) 14468 passed, 410 skipped, 32 xfailed; the 8 new browser cases cost 49.7 s locally, the sweep 35.5 s of it. They stay out of `slow` like their siblings `test_gui_browser.py` and `test_watch_browser.py`: the module skips wherever playwright is not installed, CI included, so the tail they join is local only; ruff clean; `python -m tests.reader_output` exit 0 (unchanged against
  63d7c120a). The layout test went red on each of the four real shifts before its fix, naming
  the landmark that moved: stacked, the panel column covered the graph tab; the empty pending
  slot grew 17 px on the first edit; reading the report moved the tab strip 25 px.

  *Review* (`/code-review high --fix`): five fixes landed (a refused apply from another tab
  brings Parameters forward; the palette's one-cycle command no longer flips the bar's choice;
  a double press during the apply starts nothing twice; the one-cycle run reuses `runStage`;
  the layout test's refine case waits for the run's echo). Five were declined as design
  questions for the maintainer. With the graphs hidden, Rwp, GoF and the not-a-fit chip are
  hidden too. With the panel column hidden, no visible button starts a fit (⌘⏎, `r` and the
  palette still do). Model and Text edits do not ride the action bar (owed to piece 2, in the
  milestone's owed list). The invalid-edit reason is cut by the bar's reserved 16ch slot and
  read in full on hover. The `r` key still runs the plan without applying pending edits.

  *Gotchas*: the layout test scopes the header as `#app > header`, since the Model panel has a
  `<header>` of its own. A column flex item needs `min-height: 0`, or its content height is its
  floor. `.panel` now clips, which is safe because every panel scrolls inside itself.

  Next: the maintainer reviews the PR, the eleven settled calls and the two hidden-side
  questions above. Piece 2 of the milestone, not yet filed, inherits the Model tab's two filled
  buttons.
- **2026-11-08** — filed by a ghostshift runner as the first piece of the gui-overhaul milestone,
  which this session opened. No open WP owned the GUI shell. The number 2123 was claimed by the
  shift before the milestone claimed 22xx for its later pieces. Next: start the checklist.

# WP-2216 — the refinement window: the Pattern graph, Parameters and the action bar at `/next`

Milestone: gui-overhaul · Status: 🔄 2026-11-11 — #1535 and the readout follow-up #1536 merged; the menus-and-axes PR open (#1537)
Depends on: 2215 (the frame)
Priority: P2 2026-11-11 — a feature the open milestone was opened for: the screen a person spends most time in

## Goal

The rebuilt GUI at `/next` becomes a window a person can refine in. The Pattern graph draws the
fit with its controls hidden as the prototype hides them. The Parameters tab edits values, and
the action bar applies them and refines. Edits a person leaves unapplied come back through the
recovery offer. Structural edits (rename a phase, change its space group, add, delete or
retype an atom) move from today's Model tab to a menu on the phase and a menu on the atom. The
window is judged whole beside the prototype at 1440 × 900, light and dark.

## Context

WP-2214 is the plan; its § The pieces names R2 and the inventory rows it owns: 25-58 (the
Pattern graph), 83-97 (the Parameters tab) and 118-138 (the Model tab, which dissolves). R1
(WP-2215) moved two of its own rows here, the action bar (18-24) and the recovery offer, because
both act on edits and `/next` had none. Five rulings bind it, restated from WP-2214 § Questions
and the maintainer's review of WP-2215:

- **The Model tab dissolves** (2026-11-11, question 1). Values stay in Parameters; structural
  edits go to the phase band's ⋯ menu and the atom row's context menu; source and geometry go to
  an Instrument dialog, which is R3's.
- **The status bar's right half shows the report's count of findings** (2026-11-11, question 3),
  never the mode or the σ source.
- **The hover readout moves to the status bar's right half while the pointer is over a plot**
  (2026-11-11, question 5), and the maintainer looks at it built: "Yes, but check it looks good
  when you build it". The piece's screenshots show it with the pointer on a peak.
- **The idle status bar's left half stays empty** (2026-11-11, on WP-2215).
- **Chrome text goes where it serves no decision** (2026-11-10, the "infoslop" ruling; WP-2214
  question 4, "work it out as you go"). Each row on the audit list that R2 owns is settled while
  it is built and listed in the PR.

How the Pattern graph reads, restated from the prototype and the design the graph-window branch
(`wp2213-the-graph-window`, head eaabe834f) wrote down before WP-2214 folded it in:

- **The title line** holds what the graph shows on the left ("Last fit", or "Not a fit yet" in
  the danger colour) with Rwp and GoF after it, and the view's controls on the right:
  "Intensity" with Linear, Square root and Log on one segmented track, Show all while zoomed, and
  ⋯, the view menu. The title gives way first, with an ellipsis (`gui/STYLE.md` § Layout).
- **The view menu** holds the rarer choices: the difference as Δ/σ, Δ or cumulative χ²; Show
  only the data; Set the fitted range…; Exclude a region…; Fit the whole pattern.
- **The legend** sits in a gutter at the plot's right, each label beside the pane its curve is
  drawn in, and each label is its curve's switch (`gui/STYLE.md` § Plots).
- **The fitted range and the excluded regions are objects on the plot** (interaction rules 1, 3,
  4 and 12). A click on an excluded region's shading, or on the shading outside the fitted range,
  selects it; its selection bar holds the typed bounds, the channel count and Delete; Delete or
  Option-click removes a region; right-click opens its menu.
- **The plot's context menu** holds the exports (Copy image, Copy data, Save as PNG, Save as SVG)
  and the two range gestures, as Origin's and Igor's plot menus do.

## Tasks

- [x] File the WP; WP-2214's checklist names it.
- [x] The Pattern graph at `/next`: title line, view menu, legend gutter, context menu, the
  fitted range and excluded regions as plot objects, the hover readout in the status bar's
  right half and the findings count at rest. Vitest mount cases.
- [x] The Parameters tab mounted, and the action bar with one Apply (rows 18-24, with Rwp and
  GoF beside Refine while the graphs are hidden), ⌘Enter, and the recovery offer.
- [x] Settings' About version set in the mono face (`gui/STYLE.md` § Type: numbers are mono).
- [x] Browser cases in `tests/test_gui_layout_browser.py` against `/next`: no click on the new
  controls moves the layout.
- [x] Screenshots at 1440 × 900, light and dark, under `docs/wp/2216-screenshots/`, the hover
  readout boxed with a zoomed crop.
- [x] The hover readout as the maintainer ruled it ("try b", 2026-11-11), and the consent
  list's Parameters, scale and findings items (§ Rulings). A follow-up PR.
- [x] The phase band's ⋯ menu and the atom row's context menu (rows 121-131): Rename…, Change
  space group… with its preview, Replace from CIF…, Add atom…, Rename…, Change species…,
  Anisotropic ADPs, Delete. With them, Parameters' Free and Fix buttons move into a menu.
  A third PR, since the first is already a whole screen.
- [x] The axes as ruled on 2026-11-11 (§ Rulings): no titles, a muted unit hint by each axis's
  ticks, an explanation on hover, the axis's choices on a click, each kept in the project.
  The same third PR.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py tests/test_gui_style_guide.py
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## Rulings

The first PR's three questions, answered on 2026-11-11.

- **The hover readout: option (b), "try b"** (the maintainer, 2026-11-11, after a mock-up of
  exactly this). With the pointer on a peak the status bar's right half reads
  `2θ 31.860°   d 2.806 Å   Observed 19693   Last fit 20307   Background 175   Difference −4.4σ
  fluorapatite (3 −1 1) +0.012°`. The labels are the legend's own words, in the text face and
  the muted colour; the numbers are in the mono face and the ink. 2θ, d and a reflection's
  offset take three decimals. Counts are whole and ungrouped, because the mono grouping space
  looked wide. The difference takes one decimal in σ. The nearest reflection keeps its offset.
  A narrow window drops items from the right: the reflection first, then Background.
- **Settled by Claude, Yue did not object, 2026-11-11** (a consent list sent with the readout
  question):
  - Parameters' filter reads "Filter, for example biso or Ca1", as the prototype's does.
  - Units read `° 2θ` and `°² 2θ`, never `deg 2θ`.
  - The broadening rows read "Lorentzian size", "Lorentzian strain", "Gaussian size" and
    "Gaussian strain", each on one line.
  - Parameters' Free and Fix buttons move into a menu. They wait for the phase and atom menus'
    PR.
  - The intensity scale opens on square root.
  - "N findings" counts errors plus warnings, as VS Code's Problems count does.
- **The axes: "Yes, build it"** (the maintainer, 2026-11-11, answering § Questions 1 with a
  proposal). The three axis titles go. A muted hint sits by each axis's tick labels: the x
  unit; `√` or `log` for the intensity, nothing for linear; `σ` for the difference. Hovering a
  hint explains it, and the σ one says Δ/σ and where σ came from (the curves route's
  `weighted` flag: "σ from the file", else Poisson counting statistics). A click on an axis
  opens its choices: the intensity offers Linear, Square root and Log; the difference offers
  what today's page draws; x offers only the units supported today, so it opens nothing.
  The Intensity segmented control leaves the title line. Each choice is kept per project in
  `project.json`'s `ui` keys (`intensity_scale`, `difference`), with no Settings entry. The
  menu is reachable from the keyboard, and Esc closes it.
  - *Amended 2026-11-11 by the lead*: the ruling's words offered the difference as "Δ/σ and
    cumulative χ² only". That rested on the lead's wrong premise that today's page draws no
    Δ in counts. Today's page draws all three (`lib/plot.ts`'s `RESIDUAL_KINDS`: Δ/σ, Δ, Σχ²),
    and the rule is to offer what is drawn today. So the difference axis offers all three in
    the view menu's former words, and its hint reads `counts` when Δ is chosen.
- **Structural edits land at once**, each through its own menu row or dialog, as one undoable
  history node. Settled by Claude, accepted by the lead on 2026-11-11 pending Yue's look: a
  pending structural edit would leave pending values pointing at atoms or a symmetry it
  changes, and today's Model tab also applies at once. This departs from row 21's wording.
- **Free and Fix live in the filter row's ⋯**, settled by Claude under the consent list above
  ("move into a menu") and gui/CLAUDE.md's "the filter box is the selection" (WP-1011): the
  verbs act on what the filter matches, so they sit at its row's end. The rows read "Free N
  matching" and "Fix N matching" while a filter is typed, and "Free all N" and "Fix all N"
  otherwise.

## Questions

Filled in by the session that builds each PR.

1. **Axis titles on the Pattern graph.** The prototype draws none; `/next` drew today's
   (`intensity (√)`, `(obs−calc)/σ`). Keep them, or drop them as the prototype does?
   Answered 2026-11-11: drop them for unit hints with menus (§ Rulings, "Yes, build it").

## References

- [WP-2214](2214-the-gui-rebuild-plan-and-inventory.md), the plan and the inventory;
  [WP-2215](2215-the-frame.md), the frame; `gui/STYLE.md`; `gui/CLAUDE.md`; the milestone record
  `docs/milestones/gui-overhaul.md`.

## Handover log

- **2026-11-11** — a ghostshift runner built the third PR, #1537: the phase and atom menus,
  Free and Fix in a menu, and the axes as ruled.
  - *Done*: `gui/src/next/Params.svelte` gains a ⋯ on each phase band (Rename…, Change space
    group…, Add atom…, Replace from CIF…), a context menu on each atom row (Rename…, Change
    species…, Anisotropic ADPs, Delete) and the filter row's ⋯ (Free, Fix), all on R1's one
    `next/Menu.svelte`. A typed value opens `next/Ask.svelte`, a small floating form; the space
    group opens `next/SpaceGroup.svelte`, the old page's preview in a dialog. Each structural
    edit is one whole-model verb (`PATCH /api/structure`, `POST /api/structure/aniso`,
    `POST /api/structure/symmetry`) that lands at once, and waits while a run is in flight or
    an edit is pending. `next/Pattern.svelte` draws no axis titles: a muted hint by each axis,
    a tip on hover or focus, a radio menu on a click, kept through `Frame.svelte`'s `saveUi`.
    An SVG export keeps the titles. `menus.test.ts` (12 vitest cases); two browser cases in
    `tests/test_gui_layout_browser.py` (one rewritten for the axis menus, one new for the
    structural menus and the σ hint). Today's `app.js` is byte-identical.
  - *Not generalised*: the Instrument dialog is R3's. U^ij rows are not placed under their
    atom.
  - *Restored after review*: the PR first dropped Δ in counts, as the ruling's words said; the
    lead traced those words to a wrong premise, and the difference axis offers all three
    (§ Rulings, the amendment).
  - *Measured* (macOS arm64, worktree `.venv` `[dev]` plus playwright, Python 3.12): see the
    PR body. No Python outside `tests/` changed, so the fast suite was not run.
  - *Gotchas*: R1's `Menu.svelte` focused its anchor after `onclose`, by which time the
    opener's props getter read cleared state and threw; it reads the anchor first now. The
    difference axis and the legend's Difference label were both buttons named "Difference";
    the axis is "Difference axis". A hint right-aligned over the y axis's top tick label
    collided with it, so the y hints sit in the strip left of the labels.
  - *Next*: the maintainer's look at the screens (`docs/wp/2216-screenshots/r2b-*.png`) and
    the PR's questions.

- **2026-11-11** — a ghostshift runner built the readout follow-up, PR #1536. The status bar's
  hover readout reads as ruled ("try b"), Parameters at `/next` takes the prototype's filter
  text, units and row names, and the intensity opens on square root.
  - *Done*: `gui/src/next/readout.ts` formats the reading: `lib/plot.ts:readout`'s questions
    (nearest drawn channel over both arms, rows only for drawn curves, the nearest tick per
    phase by index) with the ruled digits, and `dropsFor`, the narrow-window rule, measured as
    ink against room in `Frame.svelte`. `gui/src/next/words.ts` holds the legend's words, which
    the readout reads. `gui/src/panels/Params.svelte` moved into `gui/src/next/Params.svelte`
    under gui/CLAUDE.md's rule for a shared panel the rebuild changes, so today's `app.js` is
    byte-identical. The copy differs in the placeholder, the filter's text face, `unitText`
    (`deg` becomes `°` wherever it stands as a word, so cell angles read `°` and Caglioti U, V
    and W read `°² 2θ`), `shortTitle` (a trailing " broadening" goes, magnetic rows included),
    and the space-group symbol's 0.015 em tracking, which the rebuild's style test refuses.
    `readout.test.ts` holds the mock-up's line verbatim.
  - *Not generalised*: today's strip (`lib/plot.ts:readout`) keeps today's labels and digits
    until the swap. The help popover still prints the corpus's own unit (`deg 2θ`), since
    `Help.svelte` is shared and its words are `rietx.help`'s.
  - *Difference under the other two views*: the readout follows the difference the plot
    draws. Δ/σ reads to one decimal with σ (the ruling); Δ in counts reads whole; cumulative χ²
    reads to one decimal from the view's left edge.
  - *Measured* (macOS arm64, worktree `.venv` `[dev]` plus playwright, Python 3.12): vitest
    782 passed in 39 files (+12); svelte-check 0 errors in 441 files;
    `tests/test_gui_layout_browser.py` with `tests/test_gui_browser.py` at `-n 4`: 39 passed.
    The readout drops the reflection at 880 px and Background at 800 px, with the model panel
    hidden. No Python outside `tests/` changed, so the fast suite was not run.
  - *Gotchas*: the readout's two faces made the status bar's right half 1 px taller than the
    findings count, which the region browser case caught; the half now stretches to the bar.
    Counts first shared one slot, which set "Background 175" in a five-digit slot; each count
    now takes its own curve's widest value.
  - *Next*: the phase and atom menus PR, with Free and Fix into a menu; the axis-titles
    question.

- **2026-11-11** — a ghostshift runner built the first of R2's two PRs. The rebuilt page can
  now be refined in: the Pattern graph draws the fit with Rwp and GoF on its title line, a ⋯
  view menu, a legend beside the panes, and the fitted range and excluded regions as objects a
  click selects and a key deletes. Parameters edits values, the action bar applies and refines,
  and unapplied edits come back through the recovery offer. The hover readout takes the status
  bar's right half while the pointer is on the plot, and the findings count holds it at rest.
  The phase ⋯ menu and the atom right-click menu (rows 121-131) are the second PR's, split
  under WP-2214 rule 3 because this one is already a whole screen.
  - *Done*: `gui/src/next/Pattern.svelte`, `ActionBar.svelte` (a copy of today's, plus the Rwp
    and GoF slots while the graphs are hidden), `lib/exports.ts` (lifted from the graph-window
    branch at eaabe834f), the wiring in `Frame.svelte`, About in mono. `Window.test.ts` (8 vitest
    cases) and four browser cases in `tests/test_gui_layout_browser.py`. Today's `app.js` is
    byte-identical; only the `next*` chunks and `build-info.json` moved.
  - *Review*: `/code-review high --fix` found ten; nine fixed in one commit (Parameters stays
    mounted while the model column is hidden; a run's end read off its outcome; the shared
    recovery copy keeps today's Interactive and Plan arms; opens flush the writer; typed bounds
    send only a change and follow the region's new index; Delete defers to
    `isShortcutTarget`; zoom judged on the drawn payload; Apply refetches nothing; `exports.ts`
    loses an unused list). Declined: switching today's `panels/Exports.svelte` to the shared
    helper, since a shared panel is not edited for `/next` (gui/CLAUDE.md).
  - *Measured* (macOS arm64, worktree `.venv` `[dev]`, Python 3.12): fast suite 14720 passed,
    415 skipped, 32 xfailed in 21 min, with other sessions' work on the machine; the four added
    browser cases cost 14.2 s in that run. vitest 770 passed in 38 files (+8);
    svelte-check 0 errors; every `tests/*_browser.py` at `-n 4`: 160 passed, 2 failed, one
    fixed in the branch (a kept recovery copy behind a frame toggle) and one
    (`test_structure3d_browser.py`, today's page) passing alone, a load flake.
  - *PR*: #1535.
  - *Gotchas*: the first browser run caught the status bar's right half growing 756 px when the
    readout replaced the count; it is now `flex: 1 1 0` with `justify-content: safe flex-end`, so
    a narrow window loses the reading's right end rather than 2θ. A browser driver that applies
    an edit before taking the other theme's hover shot sees the new node; take the hover shots
    first.
  - *Next*: the second PR, rows 121-131: the phase band's ⋯ menu and the atom row's context menu,
    with the space-group preview reusing `GET /api/structure`'s `causes`. Then the maintainer's
    answers to § Questions.

- **2026-11-11** — filed by a ghostshift runner from WP-2214's piece R2. No open WP owned the
  refinement window: WP-2214's plan names it as the second piece and leaves it to be filed. The
  number was checked against `origin/main`, the remote branches and the open pull requests.

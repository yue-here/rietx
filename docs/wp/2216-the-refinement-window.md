# WP-2216 — the refinement window: the Pattern graph, Parameters and the action bar at `/next`

Milestone: gui-overhaul · Status: 🔄 2026-11-11 — first PR open (Pattern graph, Parameters, action bar, recovery); the phase and atom menus follow in a second
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
- [ ] The phase band's ⋯ menu and the atom row's context menu (rows 121-131): Rename…, Change
  space group… with its preview, Replace from CIF…, Add atom…, Rename…, Change species…,
  Anisotropic ADPs, Delete. A second PR, since the first is already a whole screen.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py tests/test_gui_style_guide.py
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## Questions

Filled in by the session that builds each PR. The first PR's three, each built the plainest
way and waiting on the maintainer's look:

1. **The hover readout in the status bar** (the ruling asked to check it built). With the
   pointer on a peak the right half reads `2θ 31.8600°  d 2.8064 Å  obs 19693  calc 20307.2
   bkg 174.975  Δ/σ -4.3765  fluorapatite (3 −1 1) +0.0121°`, set from the right end. Picture:
   `2216-screenshots/next-hover-statusbar-light.png`. Does it look good?
2. **The readout's words and digits are today's.** The labels are today's short forms (obs,
   calc, bkg, Δ/σ) and each number carries today's digits, from the shared plot module. Keep
   them, or should the rebuild spell the labels out and cut the digits (for example
   `calc 20307`, `Δ/σ −4.38`)?
3. **"2 findings" at rest counts the report's errors and warnings, not its notes**, and shows
   "No findings" when a fit has none, and nothing before a fit. It is text, not yet a button:
   opening the report from it is the report piece's. Is that the count wanted?

## References

- [WP-2214](2214-the-gui-rebuild-plan-and-inventory.md), the plan and the inventory;
  [WP-2215](2215-the-frame.md), the frame; `gui/STYLE.md`; `gui/CLAUDE.md`; the milestone record
  `docs/milestones/gui-overhaul.md`.

## Handover log

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

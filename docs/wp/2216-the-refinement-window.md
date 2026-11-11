# WP-2216 — the refinement window: the Pattern graph, Parameters and the action bar at `/next`

Milestone: gui-overhaul · Status: 🔄 2026-11-11 — filed; the first PR builds the Pattern graph, the Parameters tab, the action bar and the recovery offer
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

- [ ] File the WP; WP-2214's checklist names it.
- [ ] The Pattern graph at `/next`: title line, view menu, legend gutter, context menu, the
  fitted range and excluded regions as plot objects, the hover readout in the status bar's
  right half and the findings count at rest. Vitest mount cases.
- [ ] The Parameters tab mounted, and the action bar with one Apply (rows 18-24, with Rwp and
  GoF beside Refine while the graphs are hidden), ⌘Enter, and the recovery offer.
- [ ] Settings' About version set in the mono face (`gui/STYLE.md` § Type: numbers are mono).
- [ ] Browser cases in `tests/test_gui_layout_browser.py` against `/next`: no click on the new
  controls moves the layout.
- [ ] Screenshots at 1440 × 900, light and dark, under `docs/wp/2216-screenshots/`, the hover
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

Filled in by the session that builds each PR.

## References

- [WP-2214](2214-the-gui-rebuild-plan-and-inventory.md), the plan and the inventory;
  [WP-2215](2215-the-frame.md), the frame; `gui/STYLE.md`; `gui/CLAUDE.md`; the milestone record
  `docs/milestones/gui-overhaul.md`.

## Handover log

- **2026-11-11** — filed by a ghostshift runner from WP-2214's piece R2. No open WP owned the
  refinement window: WP-2214's plan names it as the second piece and leaves it to be filed. The
  number was checked against `origin/main`, the remote branches and the open pull requests.

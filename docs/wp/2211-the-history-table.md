# WP-2211 — the History table: Compare on the pattern, Restore as pending edits

Milestone: gui-overhaul · Status: ⬜
Depends on: 2214 (the rebuild's plan: it builds on piece R1's bottom panel)
Priority: P3 2026-11-11 — P2 (a feature the open milestone was opened for), down a rung: it builds on the bottom panel, so nothing starts until the rebuild's R1 lands (re-pointed 2026-11-11 by WP-2214)

## Goal

The History tab of the bottom panel is a table of nodes, newest last, and its tab label carries
the node count ("History 8"). Each row can overlay its fit on the pattern (Compare) and load its
values into the action bar as pending edits (Restore). Every verb the History panel has today
stays reachable.

## Context

### Where it starts

WP-2206 (PR #1521, not yet merged on 2026-11-10) moved the History panel into the bottom panel
whole and left this redesign as its follow-up. After that PR, `gui/src/panels/History.svelte`
(WP-1012, WP-1217) is a tab of `panels/Bottom.svelte`, laid out in two columns: the node graph
with lanes on the left, and on the right a selected node's details, its verbs (Checkout, Tag,
Branch, Label) and a two-node compare table (`⇄`). The tab strip is `BOTTOM_TABS` in
`gui/src/lib/tabs.ts`, and its label carries no count. Read WP-2206's handover entry on `main`
once it lands; its open visual question 1 is this WP's subject.

### The design, and the rulings it rests on

The prototypes are not published, so the design is restated here.

- **The rulings.** A History tab and a collapsible console (the maintainer's sixth review,
  2026-11-07). Work saves itself, so "going back is History's Restore" and there is no revert
  to saved (the file and project I/O ruling, 2026-11-07). The history panel is one of the
  first GUI's elements that "come over one at a time, each checked with" the maintainer (fifth
  review, 2026-11-07; `gui/STYLE.md` § Layout and panels). Port acceptance (2026-11-09): a
  piece hews close to the prototype through `gui/STYLE.md`, and completes what the prototype
  left unfinished by the guide's motives. Where the motives are unclear, the question goes to
  the maintainer.
- **The tab label** reads `History 8`: the word, then the node count in the muted register.
- **The table**, one row per node, oldest first, the newest at the bottom. Columns: Node (the
  id), Step (the stage's display name; "Start" for the root), Rwp (in %, two decimals), GoF
  (two decimals), Free (the number of free parameters), When (the time of day, `HH:MM:SS`), and
  an unlabelled column of row actions. A missing number shows `—`. Numbers are right-aligned.
  Rows are 30 px with a rule between them, and the header row is sticky. The head's row is
  tinted with the accent's soft fill and carries a "current" mark after its Step. The row
  being compared takes the third surface tint. Hovering a row shows its `api_call` (the public
  call that made the node) as the row's tooltip.
- **Compare** (a toggle button on each row but the root, tooltip "Overlay this fit on the
  pattern") draws that node's calculated curve on the Pattern graph as a dashed line in the
  secondary ink. The legend gains an entry named after the node's step, and the curve hides
  and shows like any other. One node is compared at a time, and a second press clears it.
- **Restore** (a button on each row but the root, disabled on the head, tooltip "Load this
  fit's values as pending edits") puts every value that differs between that node and the
  working state into the action bar as pending edits. Nothing is written until Apply. Revert
  drops them, as it drops any pending edit. The Parameters panel and the Text tab show them as
  they show any other pending edit.
- **The help box** for the tab says: each refinement adds a row; Compare overlays that fit on
  the pattern; Restore loads its values as pending edits (the panel's `?`, no permanent text).

### What the prototype does not settle

The prototype drew one straight run of eight nodes, from the fluorapatite example's fit. A real
tree branches, and a real node can differ from the head by more than values. Four questions
follow. The first two are visual or naming questions, so they go to the maintainer with the
options drawn before the panel is built (the maintainer's standing rule of 2026-11-06 that
visual questions go to him first).

1. **Branches and the verbs the table has no place for.** The table is linear. Today's graph
   draws lanes for forks, and Tag, Branch and Label act on a node. Milestone acceptance row 2
   requires each to stay reachable. Options to draw: a lane gutter at the table's left edge; a
   row's context menu holding Checkout, Tag, Branch and Label (the interaction rules give
   right-click the object's bar actions, 2026-11-08); the graph kept as a second view of the
   tab.
2. **`Restore` against `Checkout`.** The prototype says Restore and means pending edits. The
   server's `POST /api/history/checkout` moves the head at once (`Refinement.checkout`). WP-2206
   gave this WP the naming. One reading keeps both: Restore for the values, and Checkout in the
   row's menu for the whole state.
3. **A node Restore cannot express as pending edits.** Pending edits carry parameter values.
   A node can also differ in vary flags, ties, holds, the plan, or the model itself (an atom
   added, a phase removed). `GET /api/history/diff` names every differing path. Claude's lean,
   to be measured on the shipped examples first: Restore offers the values when the diff is
   values only, and otherwise names what else differs and offers Checkout.
4. **Compare on such a node.** `POST /api/preview` (WP-2125) evaluates the working model at
   other values and refuses a path the working table lacks. A node whose model differs needs
   its own curve. `refine.replay` recomputes a node evaluate-only. In Le Bail and Pawley
   mode a node's extracted intensities live in the node (`ReflectionState`), so its curve comes
   from replay as well.

### Seams

- **Routes.** `GET /api/history` (`tree_payload` in `src/rietx/gui/session.py`) already serves
  every column: `rwp`, `gof`, `n_free`, `created_utc`, `kind`, `name`, `label`, `api_call` and
  `n_nodes` for the tab's count. `GET /api/history/diff?a=&b=` gives a node's differing values
  against the head. `POST /api/preview` draws the pattern at them for a values-only node.
  Question 4 may need one new route serving a node's curve through replay. A new route joins
  `tests/test_gui_manual.py`'s partition and a GUI chapter.
- **Pending edits** are the action bar's store (WP-2123, WP-2126). Restore writes into it and
  adds no second store. WP-2209 (PR #1523) keeps pending edits across a close or a crash; a
  restored set then survives a crash like any other.
- **The plot.** The Pattern graph's curves and legend (`gui/src/lib/plot.ts`,
  `panels/Plot.svelte`). A compared curve is one more series, hidden and shown from the legend
  like the others (the maintainer's fourth review, 2026-11-07: every curve can be hidden).
  Its colour is a role, so it is a token in `src/rietx/viz/theme.py` (milestone acceptance row
  4), and the dashed line in the secondary ink is the prototype's choice to confirm with the
  maintainer.
- **The console.** Restore echoes the calls Apply will make, as every verb does. Compare
  echoes nothing, because it changes nothing.
- **No click moves the layout** (milestone row 1): Compare and Restore are actions on a row,
  so neither may move another element. The layout browser test sweeps the table.

### Tier

Nothing here reads the data or decides for a fit, so no row joins `rietx._audit`.

### Inherited

- **2026-11-11, from WP-2214** (the rebuild's plan). The maintainer ruled the same night to
  rebuild the GUI's front end beside today's instead of porting it piece by piece. PR #1521
  (WP-2206, WP-2207) closes as a source and never merges, so this WP builds in the new front
  end, on the bottom panel its piece R1 builds, as part of piece R5. The design above stands;
  what it says about `panels/History.svelte` and `panels/Console.svelte` describes today's GUI,
  which the new page replaces at the swap. WP-2214's inventory gives the homes this WP must
  keep reachable.

## Non-goals

- Console lines tagged by kind and the console exported as a script: WP-2212.
- The bottom panel itself, its toggle and its sash: WP-2206 and WP-2207.
- Any change to the history tree or its stored format. Restore composes existing verbs.

## Tasks

- [ ] Questions 1 and 2 drawn as options and brought to the maintainer; the rulings recorded
  here with their dates.
- [ ] Questions 3 and 4 measured on the shipped examples: how many nodes differ from their head
  by more than values, and the replay cost of a node's curve. The decision written here.
- [ ] The tab label carries `n_nodes`; `BOTTOM_TABS` and the panel corpus follow. Vitest.
- [ ] `panels/History.svelte` as the table, with the verbs placed as ruled. Vitest over the
  rows a branched tree produces.
- [ ] Compare: the dashed curve on the Pattern graph, its legend entry, its token. A browser
  test that Compare draws the node's curve and moves no element.
- [ ] Restore: the node's values into the action bar's pending edits, the refusal or the
  Checkout offer for a node that is more than values, the console echo. Vitest and a browser
  pass: Restore, then Apply, reaches the node's values; Restore, then Revert, changes nothing.
- [ ] The GUI chapter on History, the screenshot driver, the screenshots retaken, each beside
  the prototype's at 1440 by 900 in the PR (milestone row 11).
- [ ] Skill: none. The GUI is a human surface, and an agent drives the python API.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The browser files skip in CI (no playwright there), so the PR quotes their local counts.

## References

- The maintainer's rulings of 2026-11-07 (fifth and sixth reviews, file and project I/O),
  2026-11-08 (the interaction rules) and 2026-11-09 (port acceptance), restated above.
- WP-1012 and WP-1217 (the History panel), WP-2125 (the preview route), WP-2206 (the bottom
  panel), WP-2209 (edit recovery).

## Handover log

- **2026-11-10** — created by a ghostshift runner from WP-2206's follow-ups. No open WP owns the
  History panel: a search of the open WPs for History, Restore and pending edits found none,
  and WP-1012 and WP-1217 are closed. The four questions above are for the session that builds
  it; nothing waits on the maintainer before then. Next: once PR #1521 merges, bring questions 1
  and 2 to the maintainer.

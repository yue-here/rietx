# WP-2211 — the History tab at `/next`

Review pictures for `../2211-the-history-table.md`. Each whole-window picture shows the rebuilt
page at 1440 × 900, one device pixel per CSS pixel, on the `fap` example. The example ran its
staged plan (nodes n0001 to n0006, the last named `plan`), was made current at `cell` (n0003),
and ran one more stage, `biso` (n0007), so the tree has a fork. The matching prototype pictures
stay outside the repository; the pull request names where they are.

## The pictures

- `history-graph-*.png`: the tab at rest, in the Graph view it opens in. The console was dragged
  120 px taller so all eight rows show. The fork leaves the trunk at `cell` with a rounded
  corner in the second lane's colour. The head's row is tinted and carries "current"; the node
  named `plan` shows its name after its step. Since the maintainer's look, every column is as
  wide as its widest cell, so Rwp, Compare and Restore follow the step name: from the step's
  first letter to the end of Rwp is 292 px, where it was 1170 px. The head's Restore is
  disabled.
- `history-graph-1000-*.png`: the same at 1000 × 900. The rows keep the same widths, since
  nothing in them depends on the window's width.
- `alt-graph-capped-*.png`: the candidate not taken. The old layout with each row capped at
  760 px, so the step name still takes the spare width up to the cap and Rwp sits 503 px from
  it. The tint stops at the cap.
- `history-table-*.png`: Table pressed in the Graph | Table choice at the strip's right. The
  columns are Node, Step, Rwp, GoF, Free and When, with the row actions last.
- `history-compare-*.png`: in the Graph view, Compare pressed on `sample_lor` (n0004). Its curve
  is drawn dashed on the Pattern graph and its step name joins the legend last, so no other
  label moves. The row takes the third surface tint and its Compare reads as pressed.
- `history-restore-*.png`: in the Graph view, Restore pressed on the same row. The node's
  differing values wait as pending edits, drawn in the Parameters panel as any typed edit is.
  The action bar counts them and offers Revert, Apply and "Apply and refine". Nothing is
  written yet.
- `history-menu-*.png`: a right-click on the head's row. The menu reads Make current, Branch
  from here…, Name… and Note…. Each tooltip's second line is the Python call. The row sits at
  the window's foot, so the menu opens above the pointer.
- `history-help-*.png`: the strip's `?` box. It opens above its button, since the strip is at
  the window's foot, and its link goes to the GUI chapter's History section.
- `alt-compare-prototype-ink-dark.png`: the alternative to `history-compare-dark.png`, with the
  compared curve in the prototype's dark ink, `#d2c9bd`. That ink is the observed points' own
  colour, which is why the shipped dark value differs (open item 1 below).

The `history-table`, `history-menu`, `history-help` and `alt-compare` pictures predate the
maintainer's look and show the Table view. Taken 2026-11-22 on macOS (arm64) with the cached chromium, against the dist this branch
commits, with `RIETX_STATE_DIR` pointed at a temporary directory. Every click and drag was a
real pointer event. The pointer was then moved to the status bar, so no tooltip shows.

## The maintainer's look, 2026-11-22

Recorded in `../2211-the-history-table.md` § Rulings. The compared curve's dark ink, the
switch's place and the stage's own step names are kept. The Graph view was tightened (above).
The manual stays as it is until the swap.

## Where each of today's features lives

Rows are WP-2214's inventory rows 152-160 (the bottom panel's History).

| Row | Today's feature | Where it lives at `/next` | Picture |
|---|---|---|---|
| 152 | The history graph with lanes | the Graph view, the default; the Table view on request; the node count on the tab | `history-graph`, `history-table` |
| 153 | Select a node; its API call | the call in the row's tooltip | not pictured (a tooltip) |
| 154 | ⇄ compare | Compare on the row overlays its fit on the pattern | `history-compare` |
| 155 | The selected node's details | not built in this PR | — |
| 156 | Checkout, Tag, Branch, Label | the row's context menu in plain words; Restore loads a node as pending edits | `history-menu`, `history-restore` |
| 157 | The checkout warning | removed; Restore is undone by Revert | `history-restore` |
| 158 | The diff panel | not built in this PR (Compare values… on the menu, per row 154) | — |
| 159 | "No history yet" | unreachable: a project always has its root node | — |
| 160 | `h` opens History | dropped (rows 238-240) | — |

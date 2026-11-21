# WP-2231 — the Plan and Text tabs at `/next`

Review pictures for `../2231-the-plan-and-text-tabs.md`. Each whole-window picture shows the
rebuilt page at 1440 × 900, one device pixel per CSS pixel, on the `fap` example after one
staged fit. The matching prototype pictures stay outside the repository; the pull request names
where they are.

## The pictures

The Plan tab (the first PR, #1755), re-shot on the second PR's tree:

- `plan-rest-*.png`: the tab at rest. One block per stage: the grip, the numbered badge, the
  name, the free count and the stage's Rwp at the right, the ⋯ menu and the delete icon, then
  the Free row of named chips and `+ Add`. "Never freed" closes the plan.
- `plan-lists-*.png`: stage 3's free count clicked open. The disclosure lists what the stage
  frees and holds.
- `plan-picker-*.png`: stage 2's `+ Add`. The picker offers Free or Fix, a search box, then
  Groups and Parameters, each option saying where it stands in the plan.
- `plan-stagemenu-*.png`: stage 2's ⋯ menu: Run this stage, Stage settings… and Delete stage.
- `plan-settings-*.png`: Stage settings… from that menu, a floating form.
- `plan-menu-*.png`: the plan menu on the plan's name: the presets, Revert to the saved plan
  and Plan settings….

The Text tab (the second PR):

- `text-rest-*.png`: the tab at rest. The title line names the file, `fap.rxt`, with the sync
  word "in sync" at the right. The editor fills the tab. There is no Apply in the tab and no
  footer.
- `text-edited-*.png`: line 35 retyped as `atoms.0.biso 0.5` with real keys. The line's text
  is marked as edited. The sync word reads "edited", and the action bar counts one pending
  edit and offers Apply and "Apply and refine".
- `text-invalid-*.png`: the same line retyped as `atoms.0.biso banana`. The line is underlined
  with a gutter mark, the problem is listed under the editor with its line number, and the sync
  word reads "1 line not read". The bar says "invalid edit", with the reason in its tooltip,
  and refuses Apply and Refine.
- `text-offer-*.png`: the recovery offer for a Text buffer kept from an earlier session,
  typed against an older rendering.
- `text-stale-*.png`: that buffer restored. The stale notice carries Re-read, the one place it
  appears. A second one-line notice says the added comment will not survive Apply.

Taken 2026-11-21 on macOS (arm64) with the cached chromium, against the dist this branch
commits, with `RIETX_STATE_DIR` pointed at a temporary directory. Every click and keystroke
was a real pointer or key event. In the Text pictures the editor was scrolled back to its left
edge after typing, because Shift+End had scrolled the long line's comment column into view.

## Where each of today's features lives

Rows are WP-2214's inventory rows 104-117 (the Plan tab) and 139-146 (the Text tab).

| Row | Today's feature | Where it lives at `/next` | Picture |
|---|---|---|---|
| 104 | The preset select | the plan menu on the plan's name: presets, Revert, Plan settings…. No Save as new plan or Delete (§ Settled 3) | `plan-menu` |
| 105 | + Stage | `+ Stage` at the bar's right | `plan-rest` |
| 106 | Drag handle, ↑ and ↓ reorder | the three-line grip on each stage; ↑ and ↓ when it has focus | `plan-rest` |
| 107 | Run this stage, `.` | the stage's ⋯ menu and its context menu; `.` runs the selected stage | `plan-stagemenu` |
| 108 | Remove a stage | the stage's delete icon, and Delete stage on its ⋯ menu | `plan-rest` |
| 109 | The globs a stage frees, and an add field | the Free row of named chips, each with ×, and `+ Add` opening the grouped picker; a typed glob is offered as itself | `plan-rest`, `plan-picker` |
| 110 | The globs a stage fixes | the Fix row, drawn only when the stage fixes something; the picker's Fix side | `plan-picker` |
| 111 | "+N → N free, N held, Rwp" with its lists | the free count and Rwp at the stage's right; the lists in a disclosure | `plan-lists` |
| 112 | "not applied" past the first edit | kept, as words at the stage's right | not pictured |
| 113 | Iterations, tolerances, seeds, restraint weight | Stage settings… on the stage's ⋯ menu, a floating form | `plan-settings` |
| 114 | The closing stage | its own block with a dashed ✓ badge, when the plan has one; "Never freed" under it | `plan-rest` (this plan has no closing stage) |
| 115 | "N you freed by hand, held by the plan" | kept, a disclosure at the plan's foot | not pictured |
| 116 | The correlation guard's threshold | plan menu › Plan settings… | `plan-menu` |
| 117 | Undo and redo a plan edit | ⌘Z and ⇧⌘Z inside the tab; the palette's Undo and Redo the plan edit | not pictured |
| 139 | "Project text" and ".rxt" | the file's name on the tab's title line, from the project's name | `text-rest` |
| 140 | The sync state | a word at the title line's right | `text-rest`, `text-edited`, `text-invalid`, `text-stale` |
| 141 | Apply, ⌘Enter | the action bar's Apply, one pending edit; ⌘Enter inside the editor applies and never refines | `text-edited` |
| 142 | Re-read | inside the stale notice only | `text-stale` |
| 143 | The editor | kept, with each edited line's text marked | `text-edited` |
| 144 | The stale, sync, boot and comments notices | one-line notices over the editor | `text-stale` |
| 145 | Problems, each linked to its line | the gutter mark and underline, and the list under the editor | `text-invalid` |
| 146 | The footer's prose (Alt-drag, verbs) | removed; the words wait for the `?` box (§ Settled 11) | `text-rest` |

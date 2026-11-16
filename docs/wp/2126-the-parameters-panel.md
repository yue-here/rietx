# WP-2126 — the Parameters panel

Milestone: gui-overhaul · Status: ✅ 2026-11-09 — the Parameters panel merged in #1484; its five follow-ups and a duplicated space-group typesetter are in the milestone's owed list
Depends on: WP-2123

## Goal

The Parameters tab reads as a crystallographer reads a refinement: per phase, single parameters
as rows and each family of parameters for one effect as a group, in the order a refinement frees
them; the cell as a group with its symmetry folded into one line; one row per atom; numbers that
hold their columns whatever their format; a padlock that holds; and a floating editor for a value
with its limits and a restraint. No click on the panel moves the layout unless it asks to.

## Context

### Where the panel is today

`gui/src/panels/Params.svelte` draws the parameter table as a virtualised list of 22 px rows, one
per entry of `GET /api/params`, headed by its dot-path prefix (`phases.0.cell`,
`instrument.profile`). Each row has the path's leaf, an always-open text input, the esd, the
bounds in Advanced mode, and a vary checkbox, or a held mark where the row cannot be freed. A
filter box above is the selection for a bulk Free/Fix, which sends the glob in one `set_vary`
call (WP-1011). Edits gather until the action bar's Apply (WP-2123), which sends one `PATCH
/api/params` with `values` and `vary`.

The server already serves everything the new panel draws: each row's `value`, `esd`, `lo`/`hi`,
`tie`, `locked`, `held`, `mode_fixed`, `held_because` and `help_key`; the phase's space group,
crystal system and each atom's site DOFs on `GET /api/structure`; Wyckoff letters and
multiplicities on `GET /api/structure/symmetry`; units in the help corpus.

Three engine verbs the panel needs have no route. `Refinement.hold`/`unhold` (WP-1435) exist,
but `PATCH /api/params` takes only `values` and `vary`. No verb sets a parameter's limits or adds
a value restraint; both are model edits (`Param.min`/`max` and `Phase.restraints`), recorded by
`Refinement.edit`. This WP adds three arms to `PATCH /api/params` (`hold`, `limits`,
`restraints`), each a server-side call of an existing verb, so the panel's Apply stays one round
trip and every refusal stays the engine's own words.

### The designs, and the rulings they rest on

The maintainer designed the panel with Claude in prototype rounds between 2026-11-06 and
2026-11-08 and reviewed each on screen. The prototypes are not published, so each design is
restated here with its ruling.

1. **One atom, one row.** Ruled 2026-11-06 (first Parameters review): a crystallographer reads an
   atom as one row (identity, site, positions, occupancy, Biso, multiplicity), never split across
   groups or a vertical list. Corrected 2026-11-07: the review's "hkl" meant multiplicity. Label
   and species are separate columns (second review).
2. **Grouping B.** Ruled 2026-11-07: a family of parameters for one effect is a group, a single
   parameter is a row. Rows come first, then groups in refinement order, with a gap above each
   group. Per phase: Scale, then Extinction, then the Cell group, Size and strain, the atom table.
   The instrument: zero shift and displacement as rows, then Peak shape, Axial divergence, and
   Source and geometry. The cell lengths sit in a Cell group with the symmetry line inside.
3. **The folded symmetry line.** Ruled 2026-11-06: rows that cannot be freed fold into one line in
   the crystallographer's notation, `a = b = c, α = β = γ = 90°`, built from the symmetry for every
   crystal system. Only rows that cannot be freed fold; a fixed row keeps its checkbox.
4. **Group toggles follow the McCusker plan's stages**, beside the individual rows (first review).
   A group's checkbox ticks every member the user may free, and shows mixed when some are free.
5. **The background is one group.** First review: its coefficients are meaningless to switch one
   by one, so the group has one checkbox and no coefficient rows. Its preview is piece 5.
6. **Numbers.** Third review, 2026-11-07: scientific notation by default with aligned decimals;
   units on the number side, after the value. Fifth review: switching between scientific and plain
   moves nothing; atom numbers stay plain; very small and large numbers must read easily. Claude's
   reading, built in the prototype and not objected to: scientific below 0.01 and from 10 000 up,
   plain between. Round 6 (accepted 2026-11-07): one value-box width per panel, so units form one
   column.
7. **Editable numbers are tinted** (second review), with the whole cell as the click target.
8. **The padlock is a hold.** Fourth review, 2026-11-07: its cell has a checkbox cell's geometry,
   so locking moves no number, and there is no "Hold" heading. The prototype's padlock holds one
   atom's position, which answers the third review's question of how to hold one atom's position
   but not the others'; in rietx it is `Refinement.hold("phases.i.atoms.j.dof.*")`.
9. **Occupancy has an all/none box** in its header, like Position and Biso (fourth review).
10. **A checkbox sits by the parameter it controls, never by a follower** (second review). A
    coordinate is a follower of its site's DOFs, so a position box sits beside the first
    coordinate each DOF moves, and a coordinate the symmetry fixes has none.
11. **Space groups are typeset** (first review), in a serif face with no comma (second review):
    `P6₃/m`, `Fm3̄m`, `I2₁3`.
12. **Selection.** Round 6, built and kept: shift-click sets a range of checkboxes from the last
    one clicked (in the atom table the range stays in one column); ⌘-click (Ctrl elsewhere) adds a
    value to a selection, shift-click a range; clicking a selected value opens one editor, reading
    "Mixed" when the values differ, and Enter writes the number into all of them. Fixed in round 8
    from the maintainer's use: modifier clicks act on mouse-down, so an editor's commit cannot
    swallow them and the browser's blue text selection never flashes.
13. **The floating editor.** Fourth review: an edit field is wide enough to show the whole number
    while typing. Constraints round, 2026-11-08: limits and restraints are set from the value's
    popover; a value nearing a limit shows it by text colour (round 10b: red text and a 2 px bar
    on the limit's side, in the atom table too); clicking the word "Restrain" ticks its box and
    keeps the popover open. Round 10b added an "=" button opening the formula editor; formulas
    reach rietx only through `add_variable` and `tie`, which no route serves, so the button is
    not here (Non-goals).
14. **No click moves the layout unless it asks to** (third review), and **no permanent explanatory
    text** (sixth review), as WP-2123 restates. The atom table is fully visible by default (fifth
    review), with the panel resizable.

### Rulebook seams

- **A held row gets no vary checkbox** (`gui/CLAUDE.md` § editors, WP-1214): the five reasons
  stay distinct, and `held_because` is the mark's help text. A hold is the one reason the user can
  lift, so its mark is the padlock, pressed, and pressing it unholds.
- **A typed number is compared to the rendered value** (WP-1009), so opening the editor and
  leaving it moves nothing.
- **A vary key is a path or a glob** (WP-1215): a site's DOFs free together through
  `phases.i.atoms.j.dof.*`.
- **Registers** (`gui/CLAUDE.md` § House style): three type steps; size, padding and radius belong
  to the register. New marks are `color-mix` over the chrome tokens (root CLAUDE.md, WP-1429).
- **Help**: a row's name is a `<Help>` term on its `help_key`; `title=` holds only a value the
  layout truncated or a verb phrase on a button.

### Tier

No rule here reads the data or decides for a fit: the thresholds are display rules. The `limits`
and `restraints` arms are model edits the user typed.

### Calls settled by Claude

Each took the smallest neutral option, is reversible, and waits for the maintainer's review.
Each is "settled by Claude, reversible", with the alternative after it.

1. **Every band and group opens expanded**; the folded symmetry line starts folded. Alternative:
   remember each group's state in the project's `ui` keys.
2. **The thresholds are 0.01 and 10 000** (design 6 reads them as Claude's, unobjected). A slot
   reserves the exponent's width only where a column holds a value that needs one. Alternative:
   per-family formats from `lib/history.ts`'s `PLACES`.
3. **`Simple | Advanced` no longer touches this panel.** Every row is shown, and a held one sits
   behind its group's fold or carries its mark. Alternative: Simple hides held rows again.
4. **No virtualisation.** The panel draws every row, as a grouped tree does. Its cost on a large
   structure is not measured. Alternative: window the atom table past some atom count.
5. **A plain row shows its padlock only while held** (or while a hold is pending), in the box's
   place; an atom with a free site always shows one. A plain row is held from the console
   (`ref.hold`) or the `.rxt` text. Alternative: a padlock column on every row.
6. **A family no fixed rule places** (preferred orientation, a later build's) goes between Size and
   strain and the atom table: a family of one as a row, of more as a group. Alternative: a "More"
   group.
7. **Every group with a freeable member gets a box**, Source and geometry included.
   Alternative: boxes only on the groups a McCusker stage frees.
8. **Mult is the atom table's last column.** Alternative: beside the Wyckoff letter.
9. **Restrain seeds its target at the current value to 4 significant figures and σ at the esd,
   or 5 % of the value without one.** Alternative: an empty target the user types.
10. **The limits arm applies first** in one `PATCH`, then unholds, values, vary and holds, so a new
    limit admits the value typed beside it. Alternative: refuse a value outside the stored limits
    even when the same Apply widens them.
11. **A long label wraps to a second line** (the GUI's "overflow is wrap, never truncation").
    Alternative: a wider label column.
12. **The atom table's gaps are tight** (2 px), measured to fit the 546 px panel a 1440 px window
    gives, with fluorapatite's six-decimal coordinates: 533 px of table before its positions
    refine and 526 px after. A table wider than the panel scrolls sideways with the Atom column
    pinned. Alternative: widen the panel's default while Parameters is the open tab.
13. **Two members of a group with one title carry their path's index**, counted from 0 as the
    help corpus counts emission lines: "Emission line weight 0", "… 1". Alternative: the
    wavelength beside each line's weight.
14. **A mode-fixed value stays editable**, as the old table had it; only a tied or locked value is
    bare. Alternative: bare as well.
15. **A coordinate edit is echoed as a comment**, `# phases.0.atoms.1 moved to [...]`, since no verb
    of that name exists: the server projects the position onto the site's DOFs (WP-1215).
16. **`lib/style.test.ts` admits `.ink` as a non-primary button**: the number itself, tinted, not
    a filled accent. Alternative: a tenth register in `app.css`.

## Non-goals

- The formula editor and its "=" button: rietx formulas are `add_variable` plus expression ties,
  and no route serves either. The next WP after this one adds the routes and the editor.
- Constraints and bond or angle restraints authored from an atom's popover, the Restraints group,
  user variables, plan-stage badges on the group toggles (piece 3), and the background group's
  preview (piece 5).
- Folding the Model and Text panels' edits into the action bar (WP-2123's owed list).

## Follow-ups

- **Formula routes and the "=" editor**: routes for `add_variable` and expression ties, then the
  popover's "=" button (design 13). The next WP.
- **Limits on a coordinate DOF**: a `…dof.k` entry stores no `min`/`max` in the model, so the
  popover offers none for a coordinate. The engine would need a home for them first.
- **Limits on a path stored elsewhere in the model**: the limits arm walks the parameter path
  through the dumped model. It maps `instrument.polarization` to `source.polarization` (WP-1214's
  `Field.param`), but a texture or background coefficient still refuses by name. The table's
  path-to-model map lives only inside `ParameterTable`'s write-back; exposing it would serve both.
- **Positions after the PATCH**: the panel's Apply sends `PATCH /api/params`, then one
  `POST /api/structure/position` per moved atom. A refused position leaves the PATCH applied,
  across two requests. A `positions` arm on the PATCH would make the whole Apply one rehearsed
  request. The Model panel's value-then-model sequence is the same shape.
- **Plan-stage badges on the group toggles** (piece 3).

## Tasks

- [x] `PATCH /api/params` takes `hold`, `limits` and `restraints` arms, each an engine verb, with
  server tests.
- [x] Pure functions with vitest: the number slots (`lib/numslot.ts`), the space-group typesetting
  (`lib/spacegroup.ts`), the panel tree and symmetry line (`lib/paramtree.ts`).
- [x] `Params.svelte` rebuilt: phase bands, rows and groups under grouping B, the Cell fold line,
  the atom table, the padlock, tinted values, the group toggles.
- [x] The floating editor and popover: limits, Restrain, limit cue, multi-select typing.
- [x] Shift-click ranges and modifier selection, acting on mouse-down.
- [x] The layout-shift browser test extended over the Parameters panel.
- [x] Vitest updated, the dist rebuilt, the GUI chapter and screenshots that show the panel.
- [x] Skill: none expected; the agent skill drives the python API.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_server.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The layout-shift test clicks every control of the Parameters panel on a fresh page and finds no
unasked-for movement; one atom is one row; switching a number's format moves nothing (milestone
acceptance row 7).

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-08, restated above with their dates.
- `docs/practice.md` § The window layout of a GUI.

## Handover log

- **2026-11-10** — closed. PR #1484 merged on 2026-11-09, so the rebuilt Parameters panel and
  the all-or-nothing `PATCH /api/params` are on `main`. Five things this WP named as follow-ups
  had no WP, and one duplicate appeared after it merged. All six are now items in
  `docs/milestones/gui-overhaul.md` § Owed to the port, so they wait where the port's next
  pieces look.

  *Leftovers, and where each went* (all to § Owed to the port):
  (1) the formula routes for `add_variable` and expression ties, then the popover's "=" button;
  (2) limits on a coordinate DOF and on a texture or background coefficient, one item, since
  both need the path-to-model map that lives inside `ParameterTable`'s write-back;
  (3) a `positions` arm on the PATCH, so the panel's Apply is one rehearsed request;
  (4) plan-stage badges on the group toggles, which this WP left to the Plan tab and WP-2127
  left back to this panel, so neither built them;
  (5) `gui/src/lib/spacegroup.ts:typesetSpaceGroup` (this WP) and
  `gui/src/lib/symmetry.ts:symbolTokens` (WP-2131) parse a Hermann-Mauguin symbol by the same
  rules into two token types, and should be one function. Read on the tree at `ddabab7d3`. The
  sixteen settled calls were reviewed with the PR at its merge. The narrative went to
  `docs/milestones/v1.12.md`.

  Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
  Next: none here. The formula routes are the largest of the owed items above.

- **2026-11-09, fix round** — one `PATCH /api/params` now applies whole or not at all. Before,
  each arm committed its own node in the route's order (limits and restraints, unholds, values,
  vary, holds), so a refusal in a later arm left the earlier nodes in the history and their
  changes in the model. A held path freed beside a value edit did that: the value landed and the
  freeing was refused.

  *Done.* No engine verb can be asked in advance whether it will refuse, and the arms' refusals
  interact (a limit admits a value; an unhold lets a path be freed). So the route runs its arms
  first on a history-free copy, `session.rehearse`, built on `Refinement._trial(record=False)`:
  the copy the package already makes for a fit it discards, carrying the models, ties,
  variables, holds and free set. A refusal there leaves the model, the head and the history as
  they were. It answers with the verb's own sentence, the path in `where` and the arm in
  `details` (`{"arm": "vary", "where": [path]}`). The panel already keeps its pending edits on a
  refusal, so no client code changed. Three siblings share the mechanism and are fixed:
  `textdoc.apply` runs `set_values` then `set_vary`, which can refuse since WP-1435, and now
  rehearses both; `POST /api/project` wrote each setting into the live document in turn, so a
  refused region left the mode sent with it in memory for the next save, and now validates a
  draft document first (a bad `mode` is a 400 too, where it was a 500); `POST
  /api/history/branch` checked out before tagging, so a refused name moved the head, and now
  tags first. One test per route asserts the head, the node count, the refs, both models, the
  holds and the free set are unchanged after a refused request. Each of the four failed on the
  old code, run from a snapshot of the previous head.

  *Not generalised, deliberately.* Peak edits are functional (a document in, a document out,
  one save), so they cannot half-apply. `index_adopt`'s second step, setting the mode, cannot
  refuse. `example_reset` removes and rebuilds a directory, which is a filesystem sequence and
  not engine verbs. The panel's positions travel as separate requests after the PATCH, which no
  server-side rehearsal can reach (follow-ups above).

  *Measured* (arm64 macOS, this worktree's `[dev]` venv plus playwright). The rehearsal costs
  2 ms on the FAP example and 7 ms on NAC, against 9-10 ms and 43-44 ms for the whole PATCH.
  Fast selection through ghostshift's `serial.py`: 14482 passed, 410 skipped, 32 xfailed,
  which is the last round's 14478 plus this round's 4 tests. The GUI server, textdoc,
  manual, peaks and help files: 244 passed. Ruff clean; `python -m tests.reader_output`
  exit 0. No client code changed, so vitest and the dist were not rerun.

  PR #1484, stacked on #1476. Next: the maintainer reviews the sixteen calls in § Calls settled by Claude.

- **2026-11-09** — the Parameters panel is rebuilt on the designs above, against the real routes.
  A person now reads each phase as a band with its space group typeset, single parameters first,
  then the Cell group with the setting's held edges folded into one line, Size and strain, and one
  row per atom. They can hold a parameter with the padlock, set its limits and a restraint from a
  popover under the value, and edit many values at once. Nothing they press moves the layout,
  which a browser test now checks control by control. The formula editor is not here: no route
  serves `add_variable` or an expression tie, so it is the next WP.

  *Done.* `PATCH /api/params` gained three arms, `hold`, `limits` and `restraints`, each an
  existing engine verb (`Refinement.hold`/`unhold`, and `Refinement.edit` for the model's
  `min`/`max` and a `ValueRestraint`), with two server tests. Three pure modules carry the logic
  under vitest: `lib/numslot.ts` (the number slots), `lib/spacegroup.ts` (typesetting) and
  `lib/paramtree.ts` (the tree and the fold line). `Params.svelte` is rewritten on them, and
  `App.test.ts`'s parameter-table block with it. The layout-shift sweep
  (`test_no_parameters_control_moves_the_layout`) presses every box, number and padlock at both
  widths. The GUI guide's Parameters section and its screenshots are rewritten; `first-run` and
  `first-fit` show the panel too, so they moved with it.

  *Measured* (arm64 macOS, this worktree's `[dev]` venv plus playwright, on the tree with
  origin/main `5ae35232c` merged; no other suite running). Fast selection, through ghostshift's
  `serial.py`: 14478 passed, 410 skipped, 32 xfailed. This WP adds 4 pytest cases there: two
  server tests and the sweep's two widths. vitest 635 passed; svelte-check 0 errors, 0 warnings;
  `tests/test_gui_layout_browser.py` 14 passed alone; `test_gui_dist.py` 15 and
  `test_gui_manual.py` with `test_gui_server.py` 185 passed; ruff clean;
  `python -m tests.reader_output` exit 0. `tests.added_test_times` on that run puts the sweep at
  107 s for its two widths under `-n auto` (29 s each when run alone). It joins the fast tier's
  local tail and is not marked `slow`, because the module skips wherever playwright is missing,
  CI included, so it costs CI nothing. The sweep was made to fail once on purpose: a rule
  padding a ticked row's label moved the rows below 6-24 px, and every unticked box failed. The
  atom table measures 533 px before fluorapatite's positions refine and 526 px after, in the
  546 px panel of a 1440 px window.

  *Review.* `/code-review high --fix` found ten. Eight are fixed in one commit: limits typed in
  the popover now feed the value check, a crossed or non-numeric limit blocks Apply, the maps a
  landed PATCH sent are cleared before a position call can fail, a verb's refusal has its own
  field, a swallowing esd is scaled to the exponent, the server returns 400 for a malformed body,
  `instrument.polarization`'s limits reach `source.polarization`, and a restraint keeps its
  stored weight. Two are follow-ups above: a PATCH can half-apply, and texture and background
  coefficients still refuse limits.

  *Generality.* Not dispatched: the branch leaves `_audit.py` alone, and its thresholds (0.01,
  10 000) are display rules that read no data and decide nothing for a fit.

  *Gotchas.* A `bind:value` hanging off an object that the same keystroke sets to `null` throws
  after the event (Svelte 5 writes the binding late), so the editor's text is its own `$state`.
  The atom table and the Model panel both used `table.atoms`, and the plan editor's test reads
  every `.name`, so this panel's classes are `atomtab` and `aname`. `npm --prefix gui exec` run
  from the repo root leaves a `node_modules/.vite` there.

  PR #1484, stacked on #1476. Next: the maintainer reviews the sixteen settled calls above, the visual ones first (1, 5, 8,
  11, 12, 13). Then the formula routes and the "=" editor, as their own WP.
- **2026-11-09** — filed by a ghostshift runner as piece 2 of the gui-overhaul milestone, on top
  of WP-2123's branch (PR #1476, not yet merged). Next: the checklist.

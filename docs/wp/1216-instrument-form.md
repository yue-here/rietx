# WP-1216 — Model: the instrument form

Milestone: v1.2 · Status: ✅ 2026-08-28 — three groups, one grid of three columns, and the form column's floor measured
Depends on: WP-1214

## Goal

The instrument section is a grid in the order a crystallographer expects,
with U V W over X Y as two parallel rows (there is no Z — see Design), aligned
inputs, and the geometry select where it cannot move the other fields.

## Context

The user: "The instrument parameter fields are not aligned. The geometry box
is slightly narrower than the other ones, putting the first row off. The
instrument parameters should be arranged in a more logical way. For example,
UVW and XYZ are usually arranged in two parallel rows."

Findings (2026-08-25):

- `instrumentFields()` (`lib/model.ts:240-326`) returns a flat list:
  `geometry.kind`, `zero_shift`, `polarization`, per-line `wavelength`
  (+`weight` for i > 0), `profile.shape` (advanced), `u v w x y`,
  `axial_sl`, `axial_hl`, `sample_displacement`, then a geometry-dependent
  tail (`goniometer_radius_mm`, `sample_transparency`, `mu_t`,
  `thickness_mm` / `mu_t`, `thickness_mm`, `packing_fraction` / `mu_r`,
  `capillary_radius_mm`, `packing_fraction`). Every entry carries a `title`
  (WP-1029's pinned rule, `wizard.test.ts`).
- The renderer (`Model.svelte:1127-1154`) is `.grid`, a **wrapping flexbox**
  (`display: flex; flex-wrap: wrap; gap: 4px 10px`, `:1443-1448`) of
  `.cell` columns with `min-width: 92px` (`:1450-1456`). `input` and
  `select` share one rule with no width (`:1474-1485`); the geometry
  `<select>`'s longest option (`flat_plate_transmission`) makes it
  intrinsically wider and moves the wrap point, which is the misalignment
  the user saw. U V W X Y Z are six equal cells in that wrapping row. The
  cell edges, by contrast, get a real grid (`.cellrow`, `:1458-1463`).
- The background section (`:1156-1172`) and the FCJ `axialWarning`
  (`:1122-1126`) sit outside the grid.

Design: `Field` gains `group: "source" | "geometry" | "profile"`; the panel
renders one grid per group with fixed track widths (`--w-num`): **Source**
(λ per line with weights, polarization), **Geometry** (kind on its own row;
zero, displacement, transparency, radius, µ terms, packing), **Profile**
(shape; then `U V W` over `X Y` in one 3-column grid, `S/L H/L` on the row
under them). The FCJ warning renders inside Profile. The wizard's preset
fields reuse the same grid.

Two departures from the sketch this WP was written with, both because the
sketch named something that does not exist. There is no **Z**: this profile's
Lorentzian terms are X and Y, so the second row is two wide and its third slot
is empty rather than invented — which also puts `S/L H/L` on a row of their own
rather than beside, there being no fourth and fifth column at the 200 px floor.
And there is no **background** group: the family is not offered as an edit here
and the term count is a shape change with its own verb, so neither is a
`Field`, and a fourth member of the union would be a name with no writer
(CLAUDE.md, WP-1076). The background keeps its own heading and its one control.

Three widths this form has to survive, measured by WP-1215 and WP-1034:
`MODEL_MIN.form` is **200** px, which is what this column gets at the 1136 px
stacking threshold, and the `Instrument` heading already clips `Save profile…`
there because WP-1214 put two controls in that `h2`. Stacked, the column is the
panel's own width, so 340 px at the sidebar floor. And a width stated in more
than one place needs a test on the statement, or the stale one is the one that
draws (the atom table's floor was written three times and tested once).

Three rules carried in from the two WPs before this one. Every field has a
refine flag under it in a `<span class="varyline">` that renders whether or not
the field is in θ, so any regrouping keeps the flag with its field, and **a
width rule aimed at the value reaches the control beside it** — `.cellrow input
{ width: 100% }` drew an esd at zero width until the flag was excluded by name.
`Field.param` carries the parameter-table path where it is not the model path
prefixed (`source.polarization` alone), and `fieldParam` is what every lookup
asks — including any new field. And what a field *is* comes from
`rietx.help` through `<Help>`: the `title` on a `<label>` here is the **held
reason**, `geometry.kind` and `profile.shape` are the two fields the corpus has
no entry for and are held to a named list in `wizard.test.ts`, and
`panels/Model.svelte` is allowed exactly **3** authored `title=` literals by
`lib/help.test.ts`, a budget that fails both ways.

## Non-goals

- New instrument parameters or geometries.

## Tasks

- [x] `lib/model.ts`: `group` on every field; `model.test.ts` asserts every
      field has one, that all three groups are written, that a group is what
      the field *is* rather than its path's prefix, and that the profile rows
      are `[U,V,W]` / `[X,Y]` / `[S/L,H/L]` with the row starts to match.
- [x] `Model.svelte`: the three grids; fixed tracks; the selects on their own
      row; the warning inside Profile and the background under it; the esd
      decision WP-1214 left (it is drawn, in the slot the cell row and the
      phase grid already use); the wizard's preset step on the same grid.
- [x] Browser pass at the sidebar floor and ceiling (WP-1034's 340-560 px
      and 72 %), both themes; dist. Nine configurations, and it found the
      defect jsdom cannot: an auto-fill track count gave Source five columns
      while Profile had three, and at the old 200 px floor the profile's
      tracks came out at 53 px with a value clipped inside one. The form is
      one three-column grid now and `MODEL_MIN.form` is 320.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
```

Screenshots at floor and ceiling show every numeric input the same width
and U V W directly above X Y Z.

## References

- WP-1014, WP-1029 (no mute fields), WP-1034 (measured widths).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**The form is one grid of three columns** (WP-1216, `Model.svelte`,
`lib/model.ts:instrumentFields`). Four rules. **A form's column count is a
promise, so nothing else may decide it**: a wrapping row lets its widest item
pick the break, which is how one `<select>`'s longest option moved every field
after it, and an auto-fill count lets the container pick it, which gave Source
five columns while Profile had three in the same form. Three is the profile's
own row — U V W over X Y, the rows declared by `PROFILE_ROWS` — and the whole
panel is read against it; a control whose content is a *word* takes the row
rather than a track (`.fullrow`: the selects, and a phase called
`fluorapatite`). **A declared column count is a declared minimum**, so
`MODEL_MIN.form` became its arithmetic (3 x 92 + 2 x 10 + 24 = 320, the
threshold 1136 → 1256) — stated once, with `COL_MIN` reading it and the CSS
basis taking it as `--col-min`, and `resize.test.ts` crossing it against the
panel's own `--w-num`/`--grid-gap`/padding, because WP-1215's stale width was a
comment where a test belonged. **Which group a field is in is data, never its
path's prefix** — the axial apertures are `geometry.axial_*` and shape the peak,
the zero shift is top-level and belongs beside the displacement it is refined
against — and a group with no field would be a heading over nothing, which is
why the background is not one. And **a cell is a `subgrid` of its group's
rows**, so a label wrapping to two lines no longer pushes its own input below
its neighbours': the span follows the content (`:has(.varyline)`) rather than a
class on the grid, since a subgrid clamps a child past its last track *into* it
and would draw the refine flag on top of the value with nothing failing.

## Handover log

- **2026-08-28** — shipped: **the instrument section is a form rather than a
  list**. Its fields sit under Source, Geometry and Profile, in the order the
  quantities are decided in, and U V W stand directly above X Y as the two
  parallel rows a crystallographer reads them as. Every number in the panel is
  the same width and in the same three columns, at every window size and in
  both themes, so nothing shifts when a column is dragged; a refined value now
  shows its esd beside its refine flag, which this form had never done although
  the cell row and the phase grid next to it always had. It cost one number the
  panel had inherited rather than measured: a form with a *declared* column
  count has a declared minimum width, so the model pane becomes one stacked
  column below 1256 px instead of 1136.

  **Done** (four commits).

  - **Which group a field is in is data** (`InstrumentField.group`), because two
    of them disagree with their own path and the crystallographer is right both
    times: the axial apertures are `geometry.axial_*` and shape the peak, the
    zero shift is top-level and belongs beside the displacement and
    transparency it is refined against. `PROFILE_ROWS` is the one authority for
    the profile's order *and* where each row begins, so nothing downstream can
    put U over anything but X.
  - **The panel is one grid of three columns** — not a wrapping flex, whose
    widest item picked the break (that is how one `<select>` moved every field
    after it), and not an auto-fill count, which the container picks. A control
    whose content is a word takes the row rather than a track (`.fullrow`): the
    geometry select, the anode, mode, plan, and a phase named `fluorapatite`
    that a 92 px box was too small for. Each cell is a `subgrid` of its group's
    rows, so a label wrapping to two lines no longer pushes its own input below
    its neighbours'.
  - **`MODEL_MIN.form` is 320** = 3 x 92 + 2 x 10 + 24, stated once: `COL_MIN`
    reads it and the CSS basis takes it as `--col-min`. `resize.test.ts`
    crosses it against `--w-num`, `--grid-gap` and the column's padding read
    out of `Model.svelte`, which is WP-1215's stale-width lesson turned from a
    comment into a test.
  - Two decisions the WPs before this one left here: the **esd is drawn**, in
    the slot and by the call the cell row and phase grid already use, and the
    `h2` **wraps** rather than clipping `Save profile…` at the column's floor.

  **Two departures from the WP's own design sketch**, both because it named
  something that does not exist. There is no **Z**: this profile's Lorentzian
  terms are X (strain, tanθ) and Y (size, 1/cosθ), so the second row is two wide
  and its third slot is empty rather than invented — which also puts S/L and H/L
  on a row of their own rather than beside. And there is no **background**
  group: the family is not offered as an edit and the term count is a shape
  change with its own verb, so neither is a `Field`, and a fourth member of the
  union would have been a name with no writer (CLAUDE.md, WP-1076).

  **Measured** (`[dev]`, darwin/arm64; browser pass on Chrome for Testing 1223,
  the fluorapatite example fitted *through* the server, Rwp 9.70 %).

  - vitest **567 → 572** (three in `model.test.ts`, one in `App.test.ts`, one in
    `resize.test.ts`); `svelte-check` 378 files, 0 errors.
  - fast python **3201 passed / 122 skipped**, exactly WP-1215's — no python
    test was added and no python behaviour moved. The full selection did not
    run: nothing outside `gui/` changed but a docs cap, and the dist's own
    freshness test (`tests/test_gui_dist.py`) and `tests/test_gui_server.py`
    (153 passed) were run directly.
  - Nine browser configurations — the sidebar floor (form column 341 px) and
    ceiling (559), Full at 1600 and 2200 (426 and 610), and both sides of the
    new threshold (323 above, stacked below) — in light and dark. At every one:
    every numeric input **92 px**, U directly above X, no control out of line
    with its row, no clipped value, no column side-scrolling, `Save profile…`
    unclipped.
  - What the pass found, and jsdom cannot: at the 559 px ceiling the auto-fill
    count gave Source and Geometry **five** columns against Profile's three, so
    two groups of one form did not line up; and at the old 200 px floor the
    profile's tracks came out at **53 px** with `-0.0002` clipped inside one.
    Both are why the grid is fixed at three and the floor is 320.
  - `gui/CLAUDE.md` 938 → 962 lines, with its reason beside the cap in
    `tests/test_docs_consistency.py`.

  **Gotchas.**

  - **The server serves the committed dist, not the working tree.** The first
    browser pass reported "no `.grid.profile` on the page" — a stale dist, not
    a defect. `npm --prefix gui run build` before every pass that is about
    source changes.
  - A cell's row span follows its content (`:has(.varyline)`) rather than a
    class on the grid, because a grid told the wrong number fails nothing: a
    subgrid clamps a child past its last track *into* it, drawing the refine
    flag on top of the value.
  - The structure column shares `.grid`, so the phase's five numbers are three
    columns now too, and the phase name takes a row. Looked at, both themes; it
    is tidier, not a regression.

  **The review pass** (`/code-review medium --fix`) raised five and four were
  fixed, one of them a real defect this session introduced. **The focus
  paragraph I rewrote deleted `origin/main`'s v1.3 queue**: the sentence I
  carried over was copied from the ROADMAP read at session start, in the *main
  checkout*, which was three commits behind — PR #173 had filed v1.3 (agents and
  programs, 1301-1307) and pushed free-standing peaks to v1.4 that same day, so
  Current focus contradicted the milestone table two screens below it and seven
  WP files were left with no milestone. Restored verbatim. The lesson is small
  and expensive: **a worktree is cut from `origin/main`, so read the file you
  are about to rewrite in the worktree, not in the checkout the session started
  in**. Two more were stale numbers of exactly the kind this WP is about —
  `modelStacks`'s own docstring still said 1136, and `.column.structure`'s
  `flex-basis` still restated `MODEL_MIN.structure` as a literal, which is
  WP-1215's defect still sitting in the sibling of the column this WP fixed; it
  is handed down as `--structure-min` now, the way `--col-min` is. The fourth
  was a duplicated `select` rule, folded in. Declined: the `320px` fallback in
  `flex: 1 1 var(--col-min, 320px)`, because dropping it makes the declaration
  invalid-at-computed-value-time if the style directive is ever absent, which is
  a worse failure than a stale fallback. One more stale sentence of my own went
  with them — the comment above the width rule still described a `max-width`
  that the three-column grid had replaced. The nine browser configurations and
  the structure column were re-measured on the reviewed tree: identical at every
  one.

  **Next**: [1217](1217-history-graph-compare.md), the history graph and the
  compare table, then [1017](1017-gui-manual-onboarding.md), the manual, last.
  1217 is the last of the maintainer's triage; nothing here blocks it.

- **2026-08-25** — created from the v1.2 triage.

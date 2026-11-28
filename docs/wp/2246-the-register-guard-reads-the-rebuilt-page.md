# WP-2246 — the register guard reads the rebuilt page: `lib/style.test.ts` scans `gui/src/next/`

Milestone: gui-overhaul · Status: 🔄 2026-11-25 — the guard reads next/ (PR #1840); waits on the maintainer's three style-guide questions, then one short session closes it
Depends on: —
Priority: P3 2026-11-24 — a workaround covers it: acceptance row 3's other measure, a look at each piece's screenshots, still runs; the guard gates the milestone's completion, not any fit

## Goal

The house-style guards in `gui/src/lib/style.test.ts` read the rebuilt GUI's components in
`gui/src/next/` as well as `App.svelte` and `panels/`. The milestone's acceptance row 3 ("a
choice never looks like an action", measured by `lib/style.test.ts`) is then measured on the
new page, which the milestone record says it must be for every rebuild piece.

## Context

- **What the guard does.** `styledFiles()` (`gui/src/lib/style.test.ts`) lists the files three
  assertions read: (1) no file gives a register (a control kind drawn once, in `app.css`: the
  `REGISTERS` table, `button`, `.chip`, `.pill`, `.segmented`, `.tab`, `.link`, `.file`) its
  own size, padding or radius; (2) every `font-size` names a type-scale step (`var(--text…)`);
  (3) one filled primary per view, counted per file against an `ALLOWED` table. Today
  `styledFiles()` returns `App.svelte` and `panels/*.svelte` only. The emoji and sentence-case
  checks already read `next/`.
- **Measured at `ce9f2de00`** with a python copy of the three assertions over the 24
  `next/*.svelte` files (script kept by the 2026-11-24 issue triage; re-measure, the counts
  grow with each piece):
  - (1) 4 geometry overrides under today's `REGISTERS`; 6 with `.ib` (icon button) and `.mbtn`
    (menu button) added. `next/Plan.svelte`: `.ib.words { padding; font-size }` and
    `button.op { padding; border-radius; font-size }`. `next/Params.svelte`:
    `.jump .link { padding: 2px 0 }`.
  - (2) 2 literal font sizes, both in `next/Params.svelte`: `calc(var(--text) * 1.06)` and
    `0.87em`.
  - (3) 69 buttons across 18 files that the test's rule counts as filled (a bare `<button>`
    without `ghost`, `tab`, `pick`, `link`, `help` or `ink` in its class). WP-2231's session
    measured 45 across 13 files at its handover and reported that the rebuild draws a bare
    button differently from `app.css`. `next/main.ts` loads `app.css` then `next.css`, and
    `next.css`'s `button:not(.pick, .tab, .link, .ib, .mbtn, .step)` rule sets only geometry,
    its comment saying the registers keep their meaning from `app.css`. So find out first
    which buttons `/next` actually draws filled, then restate the one-filled-primary check
    for the new page from that.
- **What `gui/STYLE.md` settles.** Its Components table lists the icon button as a kind, so
  `.ib` is a register under principle 3 ([Yue, WP-1201]) and joins `REGISTERS`. It has no
  menu-button row, so whether `.mbtn` is a register is open. STYLE.md also says "the drawings
  live in `gui/src/app.css`", while the rebuild draws `.ib` and `.mbtn` in `next/next.css`.
  Both are style-guide questions, and visual questions go to the maintainer: bring them with
  the overrides listed, never settle them here.
- **The fix's shape**, from the issue and WP-2231's measurement: extend `styledFiles()` to
  `next/*.svelte`; add `.ib` (and `.mbtn` once ruled) to `REGISTERS`; name `next.css` beside
  `app.css` as a place a register's geometry may be declared until the swap; move the six
  overrides there as named variants (moving a rule between stylesheets changes no pixel where
  specificity is kept; check with the piece screenshots); replace the two literal sizes with
  type-scale steps or bring them as a visual question; restate the filled-primary table for
  `/next`.
- Rulebook: `gui/CLAUDE.md` and `gui/STYLE.md`. Commands: `npm --prefix gui test && npm
  --prefix gui run check`, then rebuild the committed dist if any `.svelte` or `.css` moved.

### Measured (2026-11-25, at `0e79e455f`)

- (1) and (2) over the 26 `next/*.svelte` files reproduce the counts above: 4 geometry
  overrides, 6 with `.ib`, and the same 2 literal sizes. Adding `.mbtn` to `REGISTERS` adds
  none, since no piece sets a menu button's size, padding or radius.
- (3): a browser pass over `/next` (example `fap`, every Graphs, Model and bottom tab)
  read the computed background of 188 distinct buttons. Two drew the accent fill: the start
  screen's New project… and the action bar's Refine, both bare buttons. Every classed button
  it saw drew no fill: `.ib`, `.mbtn`, `.step` from `next.css`, and the pieces' own classes
  (`.pname`, `.axis`, `.gut`, `.x`, `.term`, `.entry`, `.facts`, `.reset`, `.num`), each
  with a background rule of its own. The test's old reading counted 69 of these as filled.
  Read the way the page draws them, 16 buttons in 10 files are filled. Each is a step's or
  a form's own primary, mostly in `{#if}` branches of each other (list in
  `lib/style.test.ts`'s `ALLOWED`).
- The old check skipped `class:on=…` but not the shorthand `class:on`, so Candidates'
  time-limit options, a segmented choice, counted as filled.

### Questions for the maintainer

1. **Is the menu button (`.mbtn`) a register?** `gui/STYLE.md` § Components has no row for
   it. It is a word and a chevron on the top bar (`next/Frame.svelte`, the workflow menu) and
   the Plan's name (`next/Plan.svelte`). Making it one adds a Components row and one line to
   `REGISTERS`, and today fails nothing.
2. **Where do the rebuild's drawings live?** STYLE.md says "The drawings live in
   `gui/src/app.css`". The rebuild draws `.ib`, `.mbtn` and `.step` in `next/next.css`, and
   this WP moved three variants there: `.ib.words` (the Plan's "+ Stage", from
   `next/Plan.svelte`), `button.op` (the Plan add dialog's option rows, from
   `next/Plan.svelte`) and `.jump .link` (Parameters' links row, from `next/Params.svelte`).
   Either the sentence names `next.css` until the swap, or these drawings move into `app.css`
   now. Neither changes a pixel.
3. **Two type sizes are off the scale**, both in `next/Params.svelte`. The space group after
   a phase's name (`.bt .sg`, line 1583) is `calc(var(--text) * 1.06)`, 14.8 px beside 14 px
   words. A unit beside its number (`.unit`, line 1712) is `0.87em`, about 12.2 px beside a
   14 px number. Moving them to `--text` (14 px) and `--text-sm` (13 px) changes what is
   drawn, so they wait on `OFF_SCALE` in `lib/style.test.ts`.

### Inherited

## Non-goals

- The swap of `/next` into `/` (WP-2214 § The swap), which retires `panels/` and may merge the
  two stylesheets. This WP measures the page as it stands.
- Redrawing any control. Where an override is a deliberate new look, it becomes a named
  variant or a question, never a change of pixels.

## Tasks

- [x] `styledFiles()` reads `next/*.svelte`; the parse-coverage assertion counts them.
- [x] `.ib` joins `REGISTERS`; `.mbtn` and the `app.css`-only sentence of STYLE.md go to the
      maintainer as questions, with the overrides listed.
- [x] The geometry overrides and literal font sizes found are moved or ruled, so (1) and (2)
      pass over `next/`. The six geometry overrides moved to `next.css`; the two font sizes
      sit on the test's `OFF_SCALE` list until the maintainer rules (§ Questions 3).
- [x] The one-filled-primary check restated for `/next` from what the page draws, with its
      `ALLOWED` table.
- [x] Tests: the vitest suite and svelte-check green; a deliberately added override in a
      `next/` file fails the guard (run red once).
- [x] Skill: none. The guard is a test over the GUI's source and changes nothing an agent
      driving rietx reads.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
```

`lib/style.test.ts` reads every `next/*.svelte` file and passes. The milestone record's
acceptance row 3 names this WP.

## References

- Issue #1656 item 2 (WP-2215's review, 2026-11-11), and the maintainer-side triage comment
  of 2026-11-22 on it.
- WP-2231 § Inherited (the 2026-11-21 fold) and its handover's *Not done* bullet.
- `gui/STYLE.md` § Components; WP-1201 (the guard's origin).

## Handover log

- **2026-11-25** — The house-style guard now reads the rebuilt page, so the milestone's
  acceptance row 3 is measured on `/next` as the record requires. A piece that gives a
  button, a chip or an icon button its own size, padding or radius now fails the test, and
  so does a type size off the scale or a new filled button. Nothing on screen moved: three
  overrides changed files, and a browser read the same computed styles before and after.
  Three style-guide calls are left for the maintainer (§ Questions), and two type sizes wait
  on an explicit list in the test until then. PR #1840.

  *Done.* `styledFiles()` reads `next/*.svelte` (26 files), and the parse check floors each
  directory. `.ib` joins `REGISTERS`; `.mbtn` stays out pending question 1. `.ib.words`,
  `button.op` (with its disabled and hover rules) and `.jump .link` moved unchanged from
  `next/Plan.svelte` and `next/Params.svelte` into a commented block at the end of
  `next/next.css`. The test's header names `next.css` beside `app.css` as exempt until the
  swap, which is question 2's provisional answer, not a ruling. The two off-scale sizes
  are `OFF_SCALE`, an exact list that fails both ways. The filled-primary check now reads a
  class as unfilled where its own rule (in the file, or in `next.css` for a `next/` file)
  sets a non-accent background or `all: unset`, through `groundedClasses()`, which has its
  own fixture test. The shorthand `class:on` now counts as a segmented option, like
  `class:on=…`. `ALLOWED` gains 16 buttons in 10 `next/` files; the six `panels/` rows are
  unchanged. Milestone row 3 names this WP.

  *Measured.* Browser pass (chromium 1255, example `fap`, 1600 × 1000): § Measured above.
  Computed padding, radius, font size and weight, height, width, colour, background, border,
  underline, opacity and line height of every `.jump .link`, `.ib.words` and `button.op`
  (59 rows, with hover and disabled states) were identical before and after the move. A
  planted `.chip.zz { padding; font-size: 11px }` and `.ib.zz { border-radius }` inside
  `@media` in `next/Plan.svelte` turned the geometry and size checks red (3 + 1 findings),
  then were removed. Gates, node v24.22.1 on macOS arm64: vitest 72 files, 1076 tests
  passed (one new); svelte-check 510 files, 0 errors, 0 warnings. No python changed, so the python
  suite did not run beyond `tests/test_gui_dist.py`, `tests/test_gui_style_guide.py` and
  `tests/test_docs_consistency.py`.

  *Review.* `/code-review high --fix` made one fix: the class match in the filled check is
  `(?<![\w-])class="`, so `data-class="…"` no longer reads as a class. It also led to one
  comment in `next.css` saying the moved rules now hold page-wide. Declined, each a
  deliberate limit: the moved overrides are moved rather than resolved (that is question 2);
  `groundedClasses()` grounds a class through a descendant selector anywhere on the page
  (tightening it would count `.steps .step`, `.chips .term` and `.pt .x` as filled, which
  the browser showed they are not); `class:on` outside a `.segmented` track would be
  skipped though filled (none exists); the guard checks no `height`/`width` (WP-1201's
  choice for every register); a quoted string inside `class="{…}"` is misread (none exists).

  *Not generalised.* The geometry check sees only a selector that names a register. A
  button drawn through its own class is invisible to it, and `/next` has seven such
  classes that set their own radius, in eight rules: `.pname` 6 px and `.num` 4 px (Interactive), `.axis`
  and `.gut` 4 px (Pattern, SeriesTrends), `.pt .x` 10 px (Plan), `.chips .term` 5 px
  (Background), `.entry` 3 px (Structure). Each is a deliberate look in a piece, so
  closing that class would be seven visual questions; it is left for the maintainer's
  screen review (row 10).

  *Generality.* Not dispatched: the branch touches no `_audit.py` row and adds no package
  heuristic; the guard is a test over GUI source.

  Next: the maintainer answers § Questions 1-3. Then one short session applies them: add
  `.mbtn` to `REGISTERS` (and STYLE.md's table) if it is a register; rewrite STYLE.md's
  "drawings live in `app.css`" sentence or move the `next.css` drawings, per question 2;
  replace the two `OFF_SCALE` sizes, rebuild the dist and empty the list. That closes the WP.

- **2026-11-24** — created, from the 2026-11-24 issue triage (issue #1656 item 2; PR #1827). Checked
  against the tree at `ce9f2de00`: `styledFiles()` still lists `App.svelte` and
  `panels/*.svelte` only, and the measurement above reproduces WP-2231's geometry and
  font-size counts exactly (6 and 2) while the filled-button count has grown from 45 to 69
  as R6 and R7 landed. No open WP owns it: WP-2231 (R4, 🔄) held it in § Inherited from
  2026-11-21, but its handover left it listed as "more than this PR's fix", every task is
  ticked, and its next step, the maintainer's look, closes it. No other open gui-overhaul WP
  (2211, 2227, 2243, 2245) touches the style guard. Milestone gui-overhaul, since its
  acceptance row 3 is measured by this guard. Next: the first task.

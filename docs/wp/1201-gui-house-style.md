# WP-1201 — GUI house style: tokens and registers

Milestone: v1.2 · Status: ✅ 2026-08-25 — one token layer and **nine** registers (the plan named eight; the inventory found `.pick`), no size at any call site, and three register misuses repaired
Depends on: —

## Goal

One token layer and eight control registers, each register meaning one thing
and drawn one way everywhere; a test that no panel redeclares a size; the
header rebuilt as the exemplar. Every other v1.2 GUI WP builds on this one, so
it lands first (user rule, 2026-08-25: "before making any other changes").

## Context

The rule the user set: **a style element communicates one specific thing, and
that thing is consistent throughout the interface.** Size is a property of a
register, never of a call site. The 2026-08-25 inventory (three read-only
passes over `gui/src`) found:

- **The header carries five button geometries** (`App.svelte:672-748`):
  `button`/`button.ghost` at 13px / `5px 12px` (`app.css:114-126`), the
  `.segmented` controls at 11.5px / `3px 9px` (`app.css:151-160`), the theme
  segmented re-sized to 12px / `3px 7px` (`App.svelte:912-916`), `⚠ not a fit
  yet` as `ghost tiny warn` at 11px / `0 5px` (`App.svelte:698-701, 899-903`),
  and the status `.pill` at 12px mono (`app.css:175-181`). The tab strip
  (`App.svelte:994-1009`) is a sixth, undeclared register.
- **Sizes are literals.** `app.css:13-40` defines colour, plot-colour and one
  typographic token (`--mono`); there is no font-size, spacing or radius token.
  Panels use eight literal font sizes (10, 10.5, 11, 11.5, 12, 12.5, 13, 15px;
  68 `font-size` declarations). `.small` (11.5px) is redeclared in nine panels,
  `.tiny` in five, and `Report.svelte:345-348` redeclares `button.tiny` at
  10.5px against the global 11px; `Console.svelte:130-133` has a 10px button.
- **Chips have three geometries**: mono 10px / `0 4px` / radius 8
  (`History.svelte:447-455`, `Report.svelte:393-401`), 10px / `0 5px` / radius
  7 (`Peaks.svelte:989-996`, `Series.svelte:917-924`), and a border-less
  `inline-flex` chip sized by `.tiny` (`Structure3D.svelte:461-466, 340`).
- **A specificity collision is the "different-sized chips" the user saw**:
  `Peaks.svelte:989` `.chip { font-size: 10px }` and `Peaks.svelte:1039`
  `.note { font-size: 12px }` are equal specificity, so `class="chip note"`
  (the tone `flagTone` gives `position_at_bound`, `Peaks.svelte:485,500,526,
  658` and the flags cell) renders at 12px while `excluded` (`chip out`) and
  `manual` (`chip origin`) render at 10px. Same shape in `Series.svelte:917`
  vs `:936`. The register rule fixes it by construction.
- **Chips act**: `button.chip.act` (`Peaks.svelte:1002-1003`, the space-group
  adopt chips at `Peaks.svelte:773-777`) and `button.chip.warn`
  (`Series.svelte:926-931`) give a chip a cursor and hover.
- `Text.svelte:297-302` redeclares `.pill` without `--mono`; `Text.svelte:356`
  declares `button.link`, a link-shaped button.

The design (from the plan, 2026-08-25):

| Register | Means | Folds in |
|---|---|---|
| `button` | the one state-changing action in its region (Run, Create, Apply) | — |
| `button.ghost` | any other action; **same size** as primary | `h2 button`, every `.small`/`.tiny` button |
| `.segmented` | choose one of N views or modes | the theme control's own size |
| `.tab` | choose one of N panels | one size, no growth |
| `.chip` | a **non-interactive** fact (flag, tag, status); tone by colour token | the three geometries; `button.chip.*` become `button.ghost` |
| `.pill` | a live mono readout (status, Rwp) | `Text.svelte`'s copy |
| `.link` | inline navigation | `button.link` |
| help | `cursor: help` + click popover | landed by WP-1203 |

Tokens, all in `app.css`: a type scale `--text` 13px, `--text-sm` 11.5px,
`--text-xs` 10.5px; a space scale `--s1..--s4` = 2/4/8/12px; radii
`--r-control` 5px, `--r-chip` 8px; the existing colour and plot tokens. Chips
get one tone set: `note`, `warn`, `bad`, `ok`, `accent`.

Rules carried from earlier WPs that this one must not break: **overflow is
wrap, never truncation, and the buttons do not grow** (WP-1034; the header
wraps at 860px); a **stored size is not a settled size** (WP-1029); the theme
is three-way and resolved once (`data-theme` on the root). Prose a user reads
in the GUI is written under `/yue-docs-style`; a button's `title=` is a verb
phrase (this WP writes that rule into `gui/CLAUDE.md`).

## Non-goals

- No new help mechanism (WP-1202/1203); `title=` strings stay where they are.
- No panel content changes; layout inside a panel only where a deleted local
  rule needs a register in its place.
- No change to the plot's own palette (`--plot-*`).

## Tasks

- [x] `app.css`: the type/space/radius tokens; the registers written
      once (**nine**, not the eight planned — see the handover entry), each with a one-line comment saying what it means; delete
      `.small`/`.tiny`; chip tones as one set.
- [x] `App.svelte`: the header on the registers (`Open…` ghost, the three
      segmented controls at register size, the status pill, `Run` primary,
      `Cancel`/`⌘K` ghost, `⚠ not a fit yet` as a `chip bad`); the tab strip
      as `.tab`.
- [x] Every `panels/*.svelte` `<style>`: delete local `button`, `.chip`,
      `.pill`, `.small`, `.tiny` rules and literal font sizes; replace call
      sites (`class="ghost tiny"` → `class="ghost"`, `button.chip.act` →
      `button.ghost`, `chip tiny` → `chip`), keeping every existing tone.
- [x] `gui/src/lib/style.test.ts`: reads every `panels/*.svelte` and
      `App.svelte` `<style>` block (a regex over the file, no compiler) and
      fails on `font-size`, `padding` or `border-radius` declared on a
      selector containing `button`, `.chip`, `.pill`, `.segmented` or `.tab`,
      and on any `font-size:` whose value is not `var(--text`; a second
      assertion greps `gui/src` for `.small`/`.tiny` selectors and class
      names and expects none.
- [x] `gui/CLAUDE.md` § House style: the register table compressed to one
      rule per register, the token rule, the docs-style rule for GUI prose.
- [x] Browser pass (playwright-core in the scratchpad, `gui/CLAUDE.md`):
      light/dark screenshots of the header and of each panel at the sidebar
      floor and ceiling (WP-1034's widths), compared by eye against the
      register table; rebuild the committed dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
npm --prefix gui run build && git diff --exit-code src/rietx/gui/static || echo "dist rebuilt: commit it"
.venv/bin/python -m pytest tests/test_gui_dist.py tests/test_docs_consistency.py -q
grep -rn "\.small\b\|\.tiny\b" gui/src --include=*.svelte --include=*.css | wc -l   # 0
```

The header screenshot shows at most three control geometries (button,
segmented, pill); the style test is green.

## References

- WP-1029 (usability), WP-1032 (repairs), WP-1034 (panel layout): the layout
  rules restated above.
- The user's notes of 2026-08-25 (the plan file for this milestone's opening).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**One token layer and nine registers** (WP-1201, `gui/src/app.css`). A register
means one thing and is drawn one way everywhere, so **size, padding and radius
belong to the register and never to the call site**: a panel wanting a smaller
button wants a different register, and `app.css` is the one place that argument
can be had. `lib/style.test.ts` fails on a panel that declares any of the three
on a register, and on a `font-size` that is not a step of the scale.

| Register | Means |
|---|---|
| `button` | the one state-changing action in its region |
| `button.ghost` | any other action — same size, only the fill differs |
| `.segmented` | choose one of N views or modes |
| `.tab` | choose one of N panels |
| `.chip` | a fact: a flag, a tag, a grade. **Never acts** — a chip that would is a `button.ghost`, and a verb *on* a chip sits beside it, not inside |
| `.pill` | a live mono readout |
| `.pick` | select this row: a button that has given up its box, because the row is the target |
| `.link` | inline navigation, at the size of the line it sits in |
| `.help` | an explanation is one click away, and the cursor is the whole mark (popover: WP-1203) |

Three type steps and no fourth: `--text` is prose, `--text-sm` is a control
**and everything on its row** (a field's label, a count beside a button, a table
cell), `--text-xs` is a chip and a section heading. "Secondary" is said by
`.muted`, once — `.small`/`.tiny` were saying it as a *size*, in eleven files
at three values. Mono is a family, not a size. A chip's tone comes from one
vocabulary (`note` the default, `ok`, `warn`, `bad`, `accent`) and
`lib/peaks.ts`'s tone functions return members of it. Two cascade traps, both
found in a browser and neither visible to jsdom: a *state* like `button.on` is
`(0,1,1)`, so a more specific rule still loses every property it does not
declare (a selected `.tab` wore the segmented fill); and `text-transform` and
`letter-spacing` inherit into a button, so a label inside a heading wears the
heading's case unless its register says otherwise.

## Handover log

### 2026-08-25 — one control vocabulary, and the three defects it exposed

The GUI now has exactly one place where a control's size is decided. Before
this it had fourteen: each panel styled its own buttons and chips, which is why
one header row carried five button geometries and why the same "flag" chip
rendered at two different sizes inside a single table — every one of them
locally correct, and none of them a decision anybody took. `app.css` now holds
nine registers, each meaning one thing and drawn one way everywhere, plus a
test that fails a panel which gives one its own size, padding or radius.
Applying the vocabulary turned out not to be tidying: it exposed three real
defects, the plainest being that a two-phase model drew *every* phase button in
the primary register, so nothing on screen said which phase you were looking
at. One thing was deliberately given up — `⚠ not a fit yet` was a click-through
to the Report tab (WP-1029) and is now a chip, because a chip is a fact and
does not act.

**Done** — all six tasks.

- `app.css`: a three-step type scale (`--text` 13, `--text-sm` 11.5, `--text-xs`
  10.5), a three-step space scale, two radii, and mono as a *family* so a mono
  chip is chip-sized. The registers, each with a sentence: `button`,
  `button.ghost`, `.segmented`, `.tab`, `.chip` (+ five tones), `.pill`,
  `.pick`, `.link`, `.help`. Also `.file > span`, the label-as-button that two
  panels had drawn with two geometries.
- **`.pick` is the ninth register and was not in the plan.** The inventory
  found "a button that has given up its box, because the row is the target"
  written out by hand in History, Params, Report and the command palette. It
  had to be named: without it the style test is satisfied by dropping `button`
  from the selector, which is a textual dodge rather than a rule.
- Every panel's local `button`/`.chip`/`.pill`/`.small`/`.tiny` rule deleted,
  and all 166 class attributes that named a size. `.small` is not replaced by
  another size — a control is control-sized by *being* a control, and
  "secondary" is said by `.muted`, once.
- `lib/style.test.ts`, three assertions, each checked against a deliberate
  violation before it was believed. `lib/peaks.ts` gained `Tone` and
  `confidenceTone` so the three tone functions return members of the one
  vocabulary (`flagTone`'s `"out"` was the last private word).
- `gui/CLAUDE.md` § House style; cap 580 → 612 with the reason beside it.

**Three register misuses the vocabulary exposed**, none cosmetic:

1. `nav.phases` drew N *primary* buttons and `class:on` added nothing visible,
   so a multi-phase model showed no selection. It is `.segmented` now.
2. The structure viewer's `a b c reset` were four filled primaries in one row,
   which cannot each be "the one action in its region" → ghosts.
3. A chip and a pill each *contained* a button (drop-this-prior,
   stop-excluding) — two registers in one box. The verb now sits beside the
   fact.

**Three defects only the browser found** (jsdom cannot see cascade):

1. Every tab strip rendered as a segmented group. `.tab.on` (0,2,0) beats
   `button.on` (0,1,1) on what it declares — but it did not declare
   `background`, so the accent fill survived. **A state selector loses every
   property a more specific rule does not restate.**
2. `Replace from CIF…` read as REPLACE FROM CIF…: `text-transform` and
   `letter-spacing` inherit into a button, and both file labels sit inside an
   uppercase-tracked `h2`. The register resets both; `Console`'s caret opts
   back in, because there the button *is* the heading.
3. Two panels put the size back at the call site by another route — `font:
   inherit` on `input`/`select` (Plan) and an explicit `font-size` (the command
   palette) both beat the global control size. The rule is now written in both
   places: **a field is control-sized with no exception; prominence is width
   and padding.**

**Measured** (`[dev]`, darwin/arm64, node 26.3.1):

- `font-size` declarations in `gui/src`: **69 across 15 files → 34 across 10**,
  and the *values* went from seven literals (10, 10.5, 11, 11.5, 12, 13, 15 px)
  to the three tokens. Eleven files declared `.small`/`.tiny`; none do.
- Panels + `App.svelte`: **331 added / 594 deleted**; `app.css` +278 / −35.
- `npm --prefix gui test`: **20 files / 411 tests**, against 19 / 407 at session
  start — +1 file and +4 tests (three in `style.test.ts`, one tone-vocabulary
  test in `peaks.test.ts`), which is exactly the arithmetic.
  `svelte-check`: 373 files, 0 errors, 0 warnings.
- Fast python selection: **2640 passed, 117 skipped** on the branch before it
  took `main`, and **2761 passed, 117 skipped** after — the +121 is PR #108's
  (WP-1134, constant-wavelength neutron), which landed on `main` mid-session.
  No python test was added or removed *here*: the only python change this WP
  makes is the `SIZE_CAPS` constant, so nothing moved by construction, and the
  skips are unchanged across the merge.
- `npm run build` then `git diff --exit-code src/rietx/gui/static` is clean:
  the committed dist is the tree.

**Gotchas for a successor**

- `rietx gui` binds **8731 by default and the maintainer may be on it** — check
  before binding, and pass `--port`. `#app > header .pill` is the header's
  pill; the Text pane has a `header` and a `.pill` of its own.
- The browser fixture that made the pass worth doing: a two-phase 11-BM NAC
  project with an excluded region, fitted, so tables, chips, tones, a phase nav
  and a mask are all on screen. A one-phase unfitted project shows almost none
  of it — the phase-nav defect is invisible without a second phase.
- **An "on" state that is the default reads as a wall of fill.** The Peaks
  search form has twelve centring toggles, all engaged out of the box, and they
  are now twelve filled accent buttons. It is what the register says and it is
  loud; filed into WP-1209.

**Review addendum (same day)** — a review agent re-measured the branch in a
real browser (a 2529-element computed-style census against `main`'s dist) and
found one blocker the session's own screenshot pass had looked straight at and
missed, plus four ways the guard failed open. All fixed on the branch:

- **`nav.phases` filled the column with 394 px of empty bordered strip.**
  `.segmented` is `display: flex`, the `nav` is a block-level child of a
  *block* column, and the `align-self: flex-start` written against that was
  inert — there is no flex parent to align in. `width: fit-content` takes it to
  143 px against 141 px of buttons (measured). The lesson generalises: **giving
  a block-level element a flex register hands it the container's width**, and
  the screenshot shows it as an empty box that reads like a background.
- **The style guard failed open four ways**, each reproduced then re-checked:
  `<style lang="css">` made the block regex miss and the file was skipped in
  *silence* (every assertion is "this list is empty"); `padding-left` and
  `border-top-left-radius` dodged the property list; the `font` shorthand sets
  a size and was invisible to both assertions; and `.file` was a register in
  `app.css` with no entry in the guard's list. All eight violations now fire,
  and the file-parse itself is asserted.
- Smaller: `.mono` losing its size left three sizes on one Params row (the row
  is control-sized now); `--s4` was declared and used nowhere (deleted — a
  claim with no writer); two `<span class="ghost">` had a class that matches
  nothing on a span; `button.ghost` had no hover anywhere in the app after the
  one panel that owned it was cleaned out (the register owns it now); `.hint`
  was a fresh triplicate at two values (hoisted).

**`main` moved under the branch** (PR #108, WP-1134) and the PR went `DIRTY`
with no CI run at all — GitHub does not run `pull_request` workflows it cannot
compute a merge commit for, so *green checks on an older head* was the only
signal on screen and it was stale. The conflict was one hunk: both sides had
bumped a cap in `SIZE_CAPS`, measured against different parents. Resolved by
taking `main`'s ROADMAP history and cap (482, its two new index rows) beside
this WP's `gui/CLAUDE.md` 612; the merged files measure 482 and 610.

Two review findings were **not** changed, and both are now stated in `app.css`
so the next reader does not re-raise them: `.pick` renders at two sizes across
panels *by contract* (it takes the row's), and chips lost their mono family in
History and Report on purpose (a chip is a label; `.mono` at the call site is
the way back for content that really is code).

**Next**: WP-1204 (developer mode and shipped example projects) is next in the
v1.2 order — it depends on 1201 only softly, so it can start immediately.
1202/1203 follow and attach the popover to the `.help` register this WP
declared (`cursor: help`, no visible mark, as decided at the opening).

- **2026-08-25** — created from the v1.2 triage.

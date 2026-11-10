# WP-2201 — Headings in sentence case

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — claimed by a ghostshift runner
Depends on: 2131, 2142
Priority: P2 2026-11-10 — a piece the open gui-overhaul milestone was opened for, ruled 2026-11-09

## Goal

Every heading, tab label, panel title and table column head in `rietx gui` reads in sentence
case, as the start screen and the New project dialog (WP-2131) already do. One `app.css` rule
sets the heading register; no panel uppercases or tracks a heading, a column head or a label.

## Context

**The ruling.** The maintainer ruled sentence-case headings on 2026-11-06 ("Sentence-case
headings", on the Parameters prototype) and, on 2026-11-09, chose option A for the whole app:
one `app.css` rule at the start screen's register, app-wide. WP-2131's ruling entry records the
register as 13 px, weight 600, full-colour text, and says the app's other `h2`/`h3` rules and
the Model panel's two table-header rules follow it. The design prototypes set column heads in
sentence case too ("Cell", "Lattice", "Started from"), and `gui/STYLE.md` § Type infers the
same for column heads.

**Where the case comes from today** (measured on `origin/main` at e0405b2d6):

- `gui/src/app.css`'s `h2, h3` rule: `--text-xs`, `text-transform: uppercase`,
  `letter-spacing: 0.08em`, `--muted`. Every panel heading wears it.
- `gui/src/panels/Model.svelte`: `table.atoms th` and `.sublabel` are uppercase and tracked.
  The atom table's markup is lower case (`label`, `species`, `occ`), so removing the transform
  alone would leave it lower case.
- Local copies of the old register or overrides of it: `panels/Interactive.svelte` `h3`
  (`--text-xs`, muted), and the `text-transform: none` overrides in `panels/Start.svelte`,
  `panels/NewProject.svelte`, `panels/FileMenu.svelte`, `panels/Model.svelte` `h3`, the
  `.popover h2` rule in `app.css`, and the Console caret that inherits the heading's case.
- Markup: every heading and tab label is already written in sentence case. A few table column
  heads are written lower case and show lower case today: Peaks (`flags`, `use`, `cell`,
  `lattice`, `absent`, `engines`, `class`, `testable`, `refuting`, `space groups`) and Series
  (`label`, `file`, `pts`, `parameter`, `between`, `step`, `cold ratio`, `status`, `iter`).

Proper nouns and symbols keep their case: Rwp, GoF, Biso, Le Bail, Pawley, Chebyshev, hkl, 2θ,
d, I, Z, σ, x, y, z, ΔBIC, space-group and element symbols.

**Coordination.** PR #1517 (the palette, WP-2200) also edits `gui/STYLE.md`, `app.css` tokens
and the manual's screenshots. This WP keeps its diff to case-related lines and does not
regenerate the manual's screenshots, so the later merge resolves cleanly; the next
`make_screenshots.py` run picks up both.

### The tier of each rule this WP adds

None in the package. The change is a display rule in the GUI's stylesheet and markup, and the
one test added checks the stylesheets for an uppercase or tracked heading, which is a style
check, not a heuristic.

## Non-goals

- Button labels, chips, segmented options, curve toggles and form-field labels. Their case is
  already the markup's; a pass over them is a separate piece if the maintainer wants one.
- Heading sizes beyond the register the ruling names, and any new heading hierarchy.
- `rietx watch` and `rietx compare` pages, whose layout is outside `gui/STYLE.md`.
- Regenerating the manual's screenshots (see Coordination).

## Tasks

- [ ] `app.css`'s `h2, h3` rule at the ruled register; the local overrides that only undid
      the uppercase drop those lines
- [ ] The Model atom table's heads and `.sublabel` in sentence case, at the column-head
      register; lower-case column heads in Peaks and Series written in sentence case
- [ ] A vitest in `gui/src/lib/style.test.ts` failing on an uppercase or tracked heading,
      column head or label in any stylesheet
- [ ] `gui/STYLE.md` § Type's heading rule names the rule and the test, with its motive
- [ ] Dist rebuilt; vitest, svelte-check and every `tests/*_browser.py` run locally
- [ ] Before/after screenshots in the PR
- [ ] Skill: none. The agent skill drives rietx from Python and quotes no GUI heading.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build && git diff --exit-code src/rietx/gui/static
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_style_guide.py tests/test_gui_dist.py tests/test_gui_manual.py
.venv/bin/python -m pytest tests/test_gui_browser.py tests/test_gui_layout_browser.py tests/test_gui_peaks_browser.py tests/test_structure3d_browser.py
```

The maintainer looks at the before/after pair before the merge (milestone acceptance row 10).

## References

- WP-2131's ruling entry of 2026-11-09 (the register) and settled call 15.
- WP-2142 and `gui/STYLE.md` § Type.

## Handover log

- **2026-11-10** — created, by a ghostshift runner from the milestone's row "Sentence-case
  headings" (§ Designed, not yet filed). No open WP owns the work: WP-2131 and WP-2142 are
  closed and both hand it to this row.

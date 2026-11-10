# WP-2201 — Headings in sentence case

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — built; in review as PR #1522, the merge waits on the maintainer's look
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

- [x] `app.css`'s `h2, h3` rule at the ruled register; the local overrides that only undid
      the uppercase drop those lines
- [x] The Model atom table's heads and `.sublabel` in sentence case, at the column-head
      register; lower-case column heads in Peaks and Series written in sentence case
- [x] A vitest in `gui/src/lib/style.test.ts` failing on an uppercase or tracked heading,
      column head or label in any stylesheet
- [x] `gui/STYLE.md` § Type's heading rule names the rule and the test, with its motive
- [x] Dist rebuilt; vitest, svelte-check and every `tests/*_browser.py` run locally
- [x] Before/after screenshots in the PR
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

### 2026-11-10 (2nd entry) — built, in review as PR #1522

Every heading in the GUI now reads in sentence case, at the register the maintainer chose on
2026-11-09. Section headings were small grey capitals. They are now the size of body text,
set apart by weight and full ink. Column heads follow, so a table says `Flags` and `Cell`, not
`FLAGS` or `flags`. Symbols keep their case. A test now fails if a stylesheet brings capitals or
tracking back. The merge waits on the maintainer's look at the before/after pairs in
`2201-screenshots/`.

*Done.* `app.css`'s `h2, h3` rule is now `--text`, weight 600, `--fg`, with no transform. The
overrides that only undid the old capitals are gone: NewProject, FileMenu, the popover, the
Model `h3`, Console, Interactive and Browse. The start screen keeps its round-9 list label,
weight 500 and muted, stated locally where it used to come from the app rule. The Model atom
table's `th` and `.sublabel` lost their capitals. Their markup and the lower-case heads in
Peaks and Series are now written in sentence case. The new case in
`lib/style.test.ts` refuses `text-transform: uppercase|capitalize`, positive
`letter-spacing` and `small-caps`. It exempts `::first-letter` and `.sg`. A mutation that put
the old rule back failed it, naming both declarations. `gui/STYLE.md` § Type and § Checks, and
`gui/CLAUDE.md`'s type steps, say where each step now goes. `/code-review high --fix` found
no bugs. It removed two more redundant overrides, tightened the guard and aligned the step
wording, all in 48b5635e6. Its markup-check suggestion was declined: which lower-case symbols
to allow is a design call for the test, and it would come back as a false positive on `x`,
`d` and `esd`. Its Console-colour finding went to the PR as a question.

*Measured* (macOS arm64, worktree venv `[dev]` plus playwright 1.65, node v24.22.1).
vitest 718 passed: 717 on main plus the new case. `npm run check`: 416 files, 0 errors.
`tests/*_browser.py`, all eight files: 32 + 8 + 112 passed before the review fixes.
After the review fixes, `test_gui_browser.py` and
`test_gui_layout_browser.py` passed again (32). The fast selection gave 14619 passed, 410 skipped and
32 xfailed, in 12:22 on a machine whose load fell from 25 to 4 during the run. The count
includes the browser files, because playwright is installed. This WP adds no Python test. `python -m tests.reader_output` exited 0, so no printed output
changed.

*Calls taken for the maintainer* (also in the PR body). `esd` stays lower case. `Pts` and
`Iter` are capitalised and stay abbreviations. `Occ` and `Aniso` follow the Parameters panel's
`Occ`. The start screen keeps weight 500 and muted ink. Column heads in Peaks and Series were
brought into scope. A phase name used as a heading, and the FOM names the server sends, are
data and keep their case.

*Gotchas.* `lib/resize.ts`'s `SERIES_MIN` was measured with lower-case Series heads. A
capitalised head is a few px wider, so where a head sets its column's width the floor may now
be short. The layout browser tests pass. Nobody re-measured the floor. The manual's screenshots
were not regenerated, because #1517 regenerates the same files.

Next: the maintainer looks at the pairs and answers the calls above. Then merge, and close
this WP in the port's next batch close-out.

- **2026-11-10** — created, by a ghostshift runner from the milestone's row "Sentence-case
  headings" (§ Designed, not yet filed). No open WP owns the work: WP-2131 and WP-2142 are
  closed and both hand it to this row.

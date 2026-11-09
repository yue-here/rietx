# WP-2130 — the Peaks panel's gaps: the search coverage always said, Adopt on every row, the peak-mark colour

Milestone: gui-overhaul · Status: 🔄 2026-11-09 — filed and started by a ghostshift runner
Depends on: 2123, 2124 (the shell it draws in, and the adopt arm's `picked` and `why`)
Priority: P2 2026-11-09 — three of the gui-overhaul record's "owed to the port" defects, all in the existing Peaks panel

## Goal

The existing Peaks panel (`gui/src/panels/Peaks.svelte`) says how much of the search ran,
whatever the run found. Every candidate row can be adopted, and a row the gate did not pick
says its grade and caveats beside Adopt. The peak marks get the colour the maintainer settled,
or the conflict that colour has with the shipped palette goes to the maintainer with numbers.

This is not the Peaks and indexing redesign (round 11 of the workshop: four steps, the
candidate table's eight columns, lens marks, per-line curves). That is a later piece.

## Context

### Where this comes from

The GUI overhaul was designed between 2026-11-06 and 2026-11-08 in twelve rounds of
prototypes the maintainer reviewed on screen (`docs/milestones/gui-overhaul.md`). Round 11
built the indexing workflow on rietx's own output for fluorapatite (`FAP.XRA`, the shipped
lab Cu Kα pattern). It found three defects in today's Peaks panel and left them for the port,
by the maintainer's ruling of 2026-11-08 that the design work changes nothing on `main`. The
record lists them in § Owed to the port. WP-2124 fixed the server half of the indexing step
and named these three as frontend work "not here".

1. **The panel hides the search's coverage whenever there are candidates.** The panel shows
   `systems_searched`, `search_complete` and the run-level `INDEX_*` diagnostics only in its
   no-candidate branch. With candidates, a run that stopped at its time limit before reaching
   orthorhombic, monoclinic and triclinic reads exactly like a finished one. WP-1042's rule is
   that what was not reached is said loudly (`src/rietx/indexing/CLAUDE.md` § The scheduler,
   the presets and the stream; `INDEX_BUDGET_EXHAUSTED` names the three states searched,
   truncated and not reached in its `where`). Measured by the workshop on FAP's default search:
   cubic, hexagonal and trigonal searched, trigonal stopped early, orthorhombic, monoclinic and
   triclinic not reached, 12 candidates, none graded `high`.
2. **Adopt follows the gate.** The panel enables Adopt only on the row `best_or_none()`
   picks, through the adopt arm's `allowed`. On FAP nothing reaches `high`, so no row can be
   adopted, the right cell included.
3. **The peak marks lose to the data.** `--plot-peak` (purple, `#8c257e` light and `#e687d5`
   dark, `src/rietx/viz/theme.py`) is hard to see over the observed points in the high-angle
   peak forest.

### The rulings this rests on

- **Adopt: option B (Yue, 2026-11-08).** A person may adopt any candidate cell. One the gate
  (`best_or_none()`) did not pick shows its grade and caveats beside Adopt, and the history
  node records them. This reverses WP-1027's gated Adopt for the GUI, on WP-1043's governing
  sentence (the maintainer's, 2026-08-06): give a person "all the information, and let the
  user, human or machine, be the judge". WP-2124 built the server half: every row of `GET
  /api/index/result`'s `adopt` arm carries `picked` (the gate's pick) and `why` (the sentence
  an adoption of any other row writes into its `edit_model` node), and `index_adopt` takes any
  row. `allowed` stayed as `picked` under its old name for this panel until it was redrawn.
- **Never a confident singleton** (root CLAUDE.md § Indexing; `src/rietx/indexing/CLAUDE.md`).
  The candidate list is the answer and the gate's pick is a badge on one row of it. Enabling
  Adopt everywhere must not make any row read as "the answer".
- **Not reached must be loud** (WP-1042, above).
- **The peak-mark colour (Yue, 2026-11-08, round 11b and 11c).** Peak marks must read in the
  high-angle peak forest: lenses that echo the hkl ticks, larger, higher above the peak and in
  a more eye-catching colour than the thin bars. The workshop drew them in Okabe-Ito blue,
  `#0072B2` light and `#56B4E9` dark, "the complement of the orange fits". The maintainer
  closed round 11 on 2026-11-08 with every call standing.

### What the colour would collide with (measured 2026-11-09)

The workshop's palette is not rietx's. In the prototype the difference curve is grey
(`#6b6259`/`#8f8f8f`) and the accent orange; in rietx both are blue (`--plot-diff` and
`--accent` are `#1f5fa8` light). `tests/test_gui_palette.py` holds every plot layer to the
phase palette's 0.13 OKLab floor against every other plot colour (WP-1210), because the peak
layer once borrowed `--accent` and `--bad`, which are the difference and calculated curves to
the last digit on the light theme. Distances from `structure3d._oklab_distance`, the package's
one colour distance:

| Mark colour | to `--plot-diff` | to `--accent` | to the nearest phase colour | to `--plot-obs` |
|---|---|---|---|---|
| `#0072B2` (light, ruled) | 0.053 | 0.053 | 0.187 | 0.166 |
| `#56B4E9` (dark, ruled) | 0.078 | 0.038 | **0.000** (it is `--phase-2`) | 0.143 |
| `#8c257e` (light, shipped) | 0.197 | 0.197 | 0.227 | 0.242 |
| `#e687d5` (dark, shipped) | 0.199 | 0.168 | 0.082 | 0.179 |

So the ruled blue fails the floor three ways: on the light theme it sits 0.053 from the
difference curve (the floor is 0.13), and on the dark theme it is the third phase's tick
colour exactly. The free hue space WP-1210 measured is magenta and green alone, and green is
the candidate overlay's. A measurement contradicts a ruling here, so the colour goes to the
maintainer rather than being changed on a runner's judgement (§ Decision for the maintainer).

### The pieces

- `gui/src/panels/Peaks.svelte`: the indexing section (the candidate table, the extinction
  table's space-group buttons).
- `gui/src/lib/peaks.ts`: `AdoptVerdict` and a pure helper for the coverage line, tested in
  `lib/peaks.test.ts`.
- `src/rietx/gui/session.py` `index_result`: drops `allowed`, which nothing reads once the
  panel reads `picked` (a declared name with no reader, WP-1076). A one-line edit inside one
  function, because other runners edit this file.
- `src/rietx/viz/theme.py`, `gui/src/tokens.css` (generated), `tests/test_gui_palette.py`: the
  colour, if the maintainer rules on it.
- `tests/test_gui_layout_browser.py`: a Peaks-panel case with real clicks.

### The tier of each rule this WP adds

None. The coverage line quotes the result's own fields and diagnostics; the Adopt button reads
the server's arm.

## Non-goals

Not here, left for the piece that redraws the Peaks panel or a WP of its own:

- Per-line peak curves (`PeakEditor.curves` serves each group's sum only; round 11b toggles
  each line's curve). Needs a route.
- A right-click context menu on plot objects (adopted interaction rule 12, 2026-11-08). Today
  right-click removes a peak (WP-1032).
- Undo for peak edits (agreed 2026-11-08). Peak edits live in `peaks.json`, outside the
  history tree, so undo needs its own record there.
- The lens mark shape, its height above the peak and the stacking of near-duplicate marks
  (round 11c). This WP changes at most the colour.
- The candidate table's eight columns, related rows marked ("c doubled of #2"), the four-step
  workflow, the Le Bail check's absent lines as tick indices.

## Tasks

- [ ] 1. The coverage is said whatever the run found. Above the candidate list (and in the
  no-candidate branch, as before): the systems searched, the ones whose search did not
  complete, and every run-level diagnostic with its `where`, so `INDEX_BUDGET_EXHAUSTED`'s
  "not reached: …" reaches the screen. Vitest: a result with candidates still shows them.
- [ ] 2. Adopt on every row, reading `picked` and `why`. The `best_or_none()` badge follows
  `picked`; a row it does not pick shows the server's `why` beside Adopt; the extinction
  table's space-group buttons are enabled for any screened candidate. `index_result` drops
  `allowed`. Vitest and `test_gui_peaks.py` updated.
- [ ] 3. The peak-mark colour: measured above; goes to the maintainer. If ruled, change it in
  `theme.py`, regenerate `tokens.css`, adjust `test_gui_palette.py` as ruled, and read the
  drawn colour in the browser.
- [ ] 4. The layout browser test gains a Peaks-panel case: a served indexing answer, real
  clicks on the Peaks tab, a row's disclosure and Adopt, with the coverage line and the
  history node asserted, and no shell landmark moved.
- [ ] Tests: `npm --prefix gui test`, `npm --prefix gui run check`, the dist rebuilt,
  `tests/test_gui_manual.py` (screenshots where changed), `tests/test_gui_palette.py`.
- [ ] Manual: the GUI guide's indexing section says any row can be adopted.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build && npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_peaks.py tests/test_gui_manual.py tests/test_gui_palette.py tests/test_gui_dist.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1027 (the GUI peak picker and the gated Adopt), WP-1042 (not reached must be loud),
  WP-1043 (let the user be the judge), WP-1210 (the peak layer's palette and its floor),
  WP-2124 (the adopt arm's `picked` and `why`), WP-2123 (the layout shell).
- The gui-overhaul milestone record, `docs/milestones/gui-overhaul.md` § Owed to the port.

## Handover log

- **2026-11-09** — filed by a ghostshift runner from the gui-overhaul record's § Owed to the
  port. No open WP owns these: WP-2124 named them "not here", and the open gui-overhaul runners
  own the Background tab (2129), the Parameters panel (2126), the Plan tab (2127) and the
  Interactive tab (2128), none of which edits `Peaks.svelte`. Stacks on WP-2123's branch
  (PR #1476), which carries the shell and the milestone record.

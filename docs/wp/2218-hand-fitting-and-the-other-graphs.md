# WP-2218 — hand fitting and the other graphs: the Interactive tab, the Peaks, Background and Structure graphs, and the Instrument dialog at `/next`

Milestone: gui-overhaul · Status: 🔄 2026-11-18 — the second PR (the Peaks and Background graphs) up as #1680; Structure and Instrument PRs to follow
Depends on: 2216 (the refinement window)
Priority: P2 2026-11-17 — a feature the open milestone was opened for: R3, the next piece after R2

## Goal

The rebuilt GUI at `/next` gains its hand-fitting tab and its three other graphs. The
Interactive tab moves the model by hand, and the Pattern graph draws the preview beside the
last fit. The Peaks graph frames single reflections. The Background graph shows the
background with its band and its controls. The Structure graph draws the 3D structure. Source
and geometry move into an Instrument dialog. The piece is judged whole beside the prototype at
1440 × 900, light and dark.

## Context

WP-2214 is the plan. Its § The pieces names R3 and the inventory rows it owns: 57 (the
legend's Preview slot), 59-82 (the Peaks, Background and Structure graphs), 98-103 (the
Interactive tab) and 133-136 (the Instrument column). Acceptance rows 6 and 9 of the milestone
are partly R3's: the graphs say what they show, and a preview is drawn at the last fit's scale.

Every route R3 needs already exists. The preview is `POST /api/preview`. The Background graph
reads `/api/background`. The Structure graph reads `/api/structure3d`. The Instrument dialog
reads and writes `/api/instrument` and exports through `/api/export/instrument_profile`. So R3
is front-end work and changes nothing a fit prints or returns.

R2 built what R3 reuses: the frame's two tab strips, the Pattern graph's copy in
`gui/src/next/` with its title line, legend gutter and chart module, the action bar's pending
count and one Apply, and the recovery offer with its params arm. Today's panels for the same
jobs (`panels/Interactive.svelte`, `panels/PeakWindows.svelte`, `panels/Background.svelte`,
`panels/Structure3D.svelte`) were built to earlier prototype rounds. Each moves into
`gui/src/next/` before R3 changes it, so today's page does not move (gui/CLAUDE.md, the rule
for a shared panel).

The rulings R3 rests on, restated:

- **The prototype is the ruling for every visible difference** (the maintainer, 2026-11-11,
  "Merge, then polish"). Where it would break a written rule, the rule wins (`gui/STYLE.md`
  principle 9), and the difference is listed in § Rulings.
- **Chrome text that serves no decision goes** (2026-11-10, the "infoslop" ruling). Each
  candidate is listed for the maintainer before it is cut.
- **The slider's name opens its range and scale, and a click on the number types it**
  (2026-11-07, inventory rows 99 and 100).
- **The Structure view is a graph tab** (2026-11-07). PR #1519 (WP-2203) closes as a source.
  R3 takes its fetch-while-shown key and its empty state for a project with no phase.
- **The hover readout sits in the status bar's right half** (2026-11-11, WP-2216 question 5).
  On the Structure graph it names the atom or bond under the pointer (row 74).
- **Source and geometry go to an Instrument dialog** (2026-11-11, WP-2214 question 1). It is
  opened from the Instrument group's ⋯ menu and draws the form New project already draws.

How each screen reads in the prototype, restated:

- **Interactive.** A help box says "Move the model by hand and watch the graphs. Nothing is
  refined until you choose to." Sliders sit in groups. Each group's header is a tinted band
  32 px tall: Instrument first, then one band per phase under the phase's name. A row is 65 px.
  Its first line holds the name as a button with a chevron, then the value in a tinted mono box,
  then a ↺ whose slot is kept while it is hidden. Its second line is the track with a mark at
  the last fit. A changed value turns the accent ink on a soft accent fill. Dragging within
  0.5 % of the mark snaps back and drops the edit. The name opens a pop-up 300 px wide: the
  title with its unit, "Last fit X", From and To, a Scale choice of Linear or Logarithmic, and
  Default and Done. Logarithmic is disabled below zero ("Needs a range above zero").
- **The preview on the Pattern graph.** The title reads "Preview, not refined" in the accent
  ink, then "Rwp 30.01 %, last fit 9.28 %" muted. At rest it reads "Last fit" and its Rwp. The
  last fit turns grey, 1.2 px, and the preview takes the calculated curve's colour, 1.4 px. The
  y scale stays at the data and the last fit. The legend reserves the Preview slot and shows it
  only while a preview exists.
- **Peaks.** The title line holds "Show" with Data and model, or Peak shape alone. Three
  windows sit in a grid that fills 240 px columns, each titled with ‹, the 2θ in mono, the hkl
  and phase muted, and ›. Each window draws crosses, the last fit and any preview, at the last
  fit's scale times 1.1, over a 44 px residual strip with a ±3 esd band. A help box says the
  scale stays at the last fit, so a preview that grows a peak runs off the top.
- **Background.** The title reads "Background preview" while the background is free and
  "Background of the last fit" while it is held. The title line holds Type (Chebyshev,
  P-spline, Points) and "Band drawn" (×1, ×5, ×20). The data are grey min-max bars, the band is
  an accent fill and the curve is the accent ink. A 72 px block under the plot holds Terms with
  "Hold at last fit" chips for Chebyshev, or Stiffness for a P-spline.
- **Structure.** The title reads "Last fit", or "Preview, not refined" while an edit is
  pending. The title line holds "Look down" a b c, Atoms or Polyhedra, and the colour key. The
  canvas fills the graph. Drag rotates and the wheel zooms. The prototype draws one phase and
  no selection, menu or empty state; the inventory adds those (rows 71, 73, 79-82).
- **Instrument.** The prototype draws no dialog. It draws the New project form's Instrument
  row (geometry, anode or wavelength, radius, "Load an instrument profile…") and File ›
  Export › Instrument profile…, with the written path in a toast.

## Tasks

- [x] File the WP; the milestone's R3 row names it.
- [x] The Interactive tab at `/next` (rows 98-103) and the preview on the Pattern graph (row
  57): the title line's three states, the reserved Preview slot, the last fit in grey, slider
  edits counted in the action bar and carried by the recovery offer. A vitest mount case for
  the title (acceptance row 6) and a browser pass with a real drag (row 9). The first PR.
- [x] The Peaks and Background graphs (rows 59-68). The second PR.
- [ ] The Structure graph (rows 69-82), from #1519's source. The third PR.
- [ ] The Instrument dialog (rows 133-136) and File › Export › Instrument profile…. The fourth
  PR.
- [ ] Screenshots at 1440 × 900, light and dark, under `docs/wp/2218-screenshots/`, for each
  PR's screens. The last PR waits on the maintainer's look.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py tests/test_gui_style_guide.py tests/test_gui_palette.py
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## Rulings

Filled in as the maintainer answers § Questions.

1. **The last fit under a preview stays a solid line.** Yue, 2026-11-18: "not dashed, otherwise
   you choose". This answers § Questions 3. `/next` keeps STYLE.md's solid line in its own
   ink, on the Pattern graph and in each Peaks window.
2. **The dark last-fit colour: a cool blue-grey was asked for, and no such colour passes the
   palette tests.** Settled by Claude under Yue's 2026-11-18 ruling, then reopened by
   measurement. The ruling asked for a blue-grey matching light mode's hue (`#849499`), on
   condition that it pass `tests/test_gui_palette.py`. A search of the dark sRGB gamut found
   none. Every candidate near that hue with low chroma lands within 0.13 OKLab of another
   plot colour: `#5d6c71` sits 0.069 from the peak-fit curve, and `#7f8f94` sits 0.023 from
   the difference curve. The only passing colours near the hue are a saturated cyan
   (`#5ccbeb`, chroma 0.11 or more). The lowest-chroma passing colours are olive, which is
   what `#776849` already is. So `#776849` stays, and the choice returns to Yue as § Questions
   5.
3. **The refusal words stay.** "Preview refused" and "No value here can be moved by hand."
   are kept as written. Settled by Claude; this answers § Questions 2.
4. **Review pictures drag 0.3 of the slider track**, so the compared curves separate. Yue,
   2026-11-18. The Interactive pictures in `docs/wp/2218-screenshots/` are re-shot that way.
5. **The dark last fit is the light blue-grey `#7f8f94`.** Yue, 2026-11-19, on § Questions 5:
   option (d), "since they never intersect". The difference curve sits in its own strip below
   the pattern, so the last fit never draws beside it. The muted ink draws observed points
   only inside an excluded region, where no model curve draws (Yue's #1538 ruling). So the
   two pairs under the palette's 0.13 floor are named in `tests/test_gui_palette.py` at their
   measured distances: 0.023 from `--plot-diff` (in `NAMED_PAIRS`) and 0.056 from `--muted`
   (in `LAST_FROM_MUTED`). Naming them keeps each pair from coming closer unnoticed. Every
   other plot colour is at least 0.131 away, and the contrast on `--panel` is 5.25:1. Light
   mode is unchanged.
6. **The peak-shape choice moves into the Instrument dialog.** Yue, 2026-11-19, on § Questions
   12: option (a). The dialog's Axial divergence row becomes Peak shape, and the profile's
   shape sits in it under an Advanced disclosure. Built on the fourth PR, #1684.
7. **The R3 look: "mostly good".** Yue, 2026-11-19. Three things were asked for, built on this
   PR: the range pop-up's From and To read in the value box's digits; the Peaks graph shows
   as many windows as fit; and an overview strip of the whole pattern sits at the top of the
   Peaks graph, shading each shown window's range. Yue also asked whether the Interactive
   sliders move the Structure graph. They already do: the third PR, #1683, draws unapplied
   values through `POST /api/structure3d`. A cell value moves the frame, a coordinate moves
   its atom, and an instrument value moves nothing.

## Questions

Filled in by the session that builds each PR.

1. **The first PR: what `/next` draws differently from the prototype, each by a written rule.**
   - The last fit's grey is `#849499` in light and `#776849` in dark. The prototype's
     `#a79f94` and `#6f675b` fail the plot palette's 0.13 OKLab floor against the background
     curve and the peak fit, and the light one reads at 2.5:1 on the page against the 3:1 the
     palette test asks (`tests/test_gui_palette.py`, WP-1210). Each value is the nearest colour
     that clears both.
   - The Scale choice offers Linear and Logarithmic only. The prototype's third choice, "Even
     in peak width", needs the peak-width probe that WP-2128 left out (a call settled by
     Claude, its item 12). So Caglioti U's value reads in scientific notation where the
     prototype's reads plain.
   - Slider names are the help corpus's words ("Specimen displacement", "Phase scale",
     "Lattice parameter a"), where the prototype says "Sample displacement", "Scale" and
     "Cell a". gui/CLAUDE.md (WP-1203) makes `rietx.help` the one source of a name.
   - Rwp stays in the mono face (`gui/STYLE.md` § Type).
2. **The first PR: what `/next` draws that the prototype lacks.**
   - "Preview refused" on the title line, when the preview route refuses a value. The route's
     words are in the title's tooltip. The prototype draws no refusal.
   - The empty state "No value here can be moved by hand." (row 103). The prototype draws
     none.
3. **A rule reconciled.** gui/CLAUDE.md (WP-1210) says state rides on a mark's shape and never
   on a second colour, and today's page dashes the last fit under a preview. `gui/STYLE.md`
   § Plots and the prototype turn it grey. `/next` follows STYLE.md.
4. **The last fit is hard to see in dark under a preview.** In
   `interactive-preview-zoom-crop-dark.png` the grey line sits close to the orange preview
   and reads faintly against the plot's ground. The prototype's dark grey is darker still. A
   lighter grey would need to clear the palette's floor against the observed crosses and the
   difference curve. It is also olive brown (`#776849`) more than grey, so beside the
   background curve it can read as part of that family. Keep it, or ask for a lighter grey?
   *Answered by § Rulings 2, which could not be carried; see Question 5.*
5. **The dark last-fit colour, again.** Yue asked for a cool blue-grey (§ Rulings 2), and no
   blue-grey clears the plot palette's tests. The test holds every plot colour at least 0.13
   apart in OKLab, a perceptual colour distance, and at least 3:1 in contrast on the page.
   Four options, each measured with `structure3d._oklab_distance`:
   - (a) Keep `#776849`, the olive grey shipped by the first PR. It passes every test. In
     `interactive-preview-zoom-dark.png` it reads faintly and sits near the background
     curve's family.
   - (b) `#5ccbeb`, a light cyan. It passes every test: 0.136 from the observed crosses and
     0.065 from phase 2's colour against a floor of 0.063. It reads clearly, but it is a
     saturated colour, where the light theme's is a grey.
   - (c) `#5d6c71`, the blue-grey asked for, at 3.23:1 contrast. It misses one pair: 0.069
     from the peak-fit curve. Taking it means naming that pair in the test's `NAMED_PAIRS`.
     The two curves never share a graph today. The peak fit draws only while the peak list
     is being edited (gui/CLAUDE.md, WP-1210), and `/next` does not draw it yet. The last fit
     draws only under a preview.
   - (d) `#7f8f94`, a lighter blue-grey. It sits 0.023 from the difference curve, which it
     always shares a graph with. Dropped as unreadable beside it.
   Claude leans to (c), since the named pair never draws together. This is a visual choice,
   so it waits for Yue's look.
   *Answered by § Rulings 5: (d).*
6. **The second PR: what the Peaks and Background graphs draw differently from the
   prototype, each by a written rule.**
   - The background curve and its band are drawn in `--plot-bkg`, the background curve's own
     ink. The prototype uses the accent. gui/CLAUDE.md (WP-1210) gives each plot mark its
     own `--plot-*` token and keeps chrome colours off the plot.
   - Neither graph draws gridlines. `gui/STYLE.md` § Plots draws none.
   - The window arrows ‹ and › are borderless icon buttons, by `gui/STYLE.md`'s icon-button
     rule.
   - Type offers Chebyshev and P-spline only. rietx has no "Points" background kind.
   - A Type switch commits at once and starts the new background at zero coefficients. It is
     a whole-model edit (gui/CLAUDE.md, WP-1014), so it cannot wait in the pending set.
     Terms and Stiffness commit at once for the same reason.
   - The term chips are pending holds that share the Parameters panel's pending set, and
     Apply commits them (`gui/STYLE.md`: an edit is pending until Apply). The band is
     fetched with those holds, through the new `?hold=` argument on `GET /api/background`,
     so it shows what Apply would give.
   - The title reads "Background preview" only while a background hold is pending, and
     "Background at the current values" otherwise. The prototype's "Background of the last
     fit" would be wrong after a value edit, since the band is computed at the current
     values.
   - Peak shape alone draws the model minus its background. Neighbouring reflections inside
     a window therefore still show.
   - The residual strip keeps the last fit's scale, so a large preview residual is clipped
     at the strip's edge.
7. **The second PR: what the Peaks and Background graphs draw that the prototype lacks.**
   - "Band refused" on the Background title line, with the server's words in its tooltip,
     when the band cannot be computed.
   - "Edit refused" on the Background title line when a Type, Terms or Stiffness edit is
     refused, with the server's words in its tooltip. It is a field of its own beside the
     band's refusal (gui/CLAUDE.md, WP-1014). The words follow "Preview refused" (§ Rulings 3).
   - Stiffness is drawn but disabled on a P-spline whose λ is in intensity units, with its
     unit beside the value. The slider's stops are dimensionless, so a stop would move such a
     spline's stiffness by orders of magnitude.
   - "waiting for the run" on the Background title line while a refinement runs.
   - The empty state "No fitted peaks to frame yet." on the Peaks graph before a fit.
13. **The look's three items (§ Rulings 7): the details Claude chose to build them.** Each is
    a visual value the ruling did not fix, so each waits for Yue's look at
    `peaks-rest-*.png`, `peaks-stepped-*.png` and `interactive-rangepop-*.png`.
    - *Window height.* The ruling asked for 240 px columns and six windows at the default
      split, two columns of three. Three rows of today's 240 px plots do not fit the graph's
      height at 1440 × 900. So the windows share the height, each at least 190 px with its
      caption, about 160 px of plot. At the default split each plot is about 200 px tall. A
      taller window adds a row. Holding 240 px instead would show four windows.
    - *Overview height.* 36 px of plot, with 12 px below it before the windows.
    - *Overview ink.* The observed pattern in the observed points' ink, `--plot-obs`, 1 px.
      Each pixel column draws the extremes of the points under it, as the Pattern graph does.
    - *Window bands.* An accent wash, `color-mix` of `--accent` at 22 %, full height. The
      accent marks a selection on a plot (`gui/STYLE.md` § Colour). `--plot-mask` was not
      used, because it is the excluded-region wash.
    - *Range digits.* A computed range is rounded outward to the value box's digits, so it
      can widen by up to one digit of the box. Caglioti U opens on 0.2772×10⁻³ to
      4.4362×10⁻³. The fields write the box's ×10ⁿ in superscript digits, and also read
      `1.5e-3` and `1.5x10^-3`.

## Handover log

- **2026-11-19** — Yue's rulings of 2026-11-19 applied to the second PR, PR #1680.

  Yue looked at R3 and called it "mostly good". This branch carries the three things the look
  asked for and the dark last-fit colour Yue chose. The dark last fit is now the blue-grey
  `#7f8f94` (§ Rulings 5). The range pop-up's From and To read in the value box's digits:
  Caglioti U opens on 0.2772×10⁻³ to 4.4362×10⁻³, where it read 0.000277258872224. The Peaks
  graph shows six windows at the default split, two columns of three, under an overview strip
  of the whole pattern that shades each window's range. § Rulings 5-7 record the rulings, and
  § Questions 13 lists the visual values Claude chose to build the three items, for Yue's look.

  - *Done*: `viz/theme.py`'s dark `--plot-last` and its docstring, `tokens.css` regenerated,
    and the two pairs under the floor named in `tests/test_gui_palette.py` (`NAMED_PAIRS`, and
    `LAST_FROM_MUTED` with a new test, made to fail once first). The rounding is at the
    range, not only at the display: `lib/interactive.ts:roundRange` rounds a computed range
    outward to the value box's digits where `/next` builds or restores one, so the fields
    show the slider's real ends. `rangeText` writes them in the box's ×10ⁿ, `readNumber`
    reads that back, and an end left as shown keeps the slider's own value, so a typed range
    round-trips to the last digit. Today's page keeps its ranges. `lib/peakwin.ts` gained
    `gridShape` (columns of at least 240 px, rows of at least 190 px) and `firstPicks` for
    any count, which gives the prototype's three unchanged. `next/Peaks.svelte` sizes the
    grid from the graph's measured size and draws the overview. Tests: vitest
    `lib/interactive.test.ts` (3), `lib/peakwin.test.ts` (2), `next/Graphs.test.ts` (1); the
    browser cases for the pop-up's digits and for the overview's bands, stepped by a real
    click on ›, extend two existing cases. Pictures re-shot, light and dark: every
    `interactive-*.png` and `peaks-*.png`, plus the new `peaks-stepped-*.png`.
  - *Review*: `/code-review high` against the previous head (43eddfb48) returned ten. One was
    on this round's code and is fixed: the Peaks graph rebuilt the preview's net curve per
    window on every frame, six times now. The other nine are on the earlier commits of this
    PR, mostly the Background graph, and are left for the PR's review: committed holds that
    survive a Type switch or a Terms cut and land on the new background's coefficients of the
    same name; pending value and vary edits on removed terms that make the next Apply
    refused; the "Background preview" title read from the client's holds rather than the
    answer's; a pending hold on a vanished path refusing every band fetch; glob holds left
    out of the band; the TypeScript port of `for_range` with no corpus replay; the band cache
    keeping one answer; a console echo that does not match the Terms edit; and `.vg` copied
    into three files.
  - *Measured* (macOS arm64, worktree `.venv` `[dev]` plus playwright 1.65.0, Python 3.12):
    fast suite 14948 passed, 424 skipped and 32 xfailed in 9:55, through the shift's serial
    lock: two more than this PR's last count, the new palette test in each theme. Vitest 831
    of 831, six more than 825. svelte-check 0 errors in 453 files. Ruff clean. GUI python
    files (`test_gui_palette`, `_dist`, `_server`, `_manual`, `_style_guide`,
    `_background`): 267 passed. Every browser file by glob (`tests/*_browser.py`),
    serially: 169 passed. CI's Vale steps, run as `ci.yml` runs them: 0 errors.
  - *Gotchas*: in jsdom an element is never measured, so the grid falls back to the
    prototype's three windows until its size is known; the vitest cases see three. A
    canvas cannot take `role="img"` under svelte-check, so the overview is `aria-hidden`
    and the windows' captions carry the positions.

  Next: Yue's look at § Questions 13 and the re-shot pictures. The same rulings reach the
  third and fourth PRs by merge, and the fourth PR builds § Rulings 6.

- **2026-11-18** — the second PR of R3, PR #1680: the Peaks and Background graphs at `/next`.

  A person on the rebuilt page can now open the Peaks graph and see three windows of the last
  fit, each with its residual strip. A slider preview draws in each window beside the last
  fit, which stays solid. The Background graph draws the background and its esd band over the
  data. Its term chips hold a term until Apply, and the band is redrawn at once for what Apply
  would give. Yue's dark last-fit colour ruling could not be carried. No cool blue-grey passes
  the palette tests, so `#776849` stays and § Questions 5 brings four measured options back.
  A bug from the first PR is fixed: the Pattern graph drew empty when it came back from
  another graph tab under a preview.

  - *Done*: `gui/src/next/Peaks.svelte`, `Background.svelte` and `background.ts`, written
    for `/next` rather than moved, since today's panels stay until the swap. `Frame.svelte`
    mounts both. `Params.svelte` shares its pending holds with the Background chips
    (`setHold`, `onholds`). The shared title-line styles moved to `next.css`.
    `lib/peakwin.ts` gained the peak-shape helpers. Server: `GET /api/background?hold=`
    holds the named paths for that answer alone and refuses an unknown one with a 400
    naming it (`background.UnknownHold`); the manual's `gui-power.md` row says so. Tests:
    vitest `next/Graphs.test.ts` (6) and `next/background.test.ts` (5), a peak-shape case in
    `lib/peakwin.test.ts`; pytest `test_a_pending_hold_is_held_for_that_answer_alone`; the
    browser case `test_the_rebuilt_peaks_and_background_graphs_move_nothing`. That case also
    makes the Pattern-Peaks-Pattern trip under a preview, and it failed on the old dist:
    the main pane painted 447 pixels against 6396 at rest. § Rulings 1-4 recorded;
    § Questions 5-7 added. Pictures re-shot at a 0.3 drag, and the new graphs added, light
    and dark, in `docs/wp/2218-screenshots/`.
  - *Review*: `/code-review high --fix` found ten; seven fixed, three declined. Fixed: a Type
    switch or a Terms cut drops pending holds on the paths it removes, and the chips wait
    while such an edit is in flight; P-spline knots round a half to even, as `for_range`
    does; the hold refusal names only the missing paths; the header reads the head from a
    named key; an edit refusal reads "Edit refused" in its own field (gui/CLAUDE.md,
    WP-1014); Stiffness is disabled on a λ kept in intensity units. Declined: the console
    echo `with_terms(n)` after a Terms edit, since the same line is in `panels/Model.svelte`,
    which the swap deletes; a glob hold the band leaves out, since Params never produces one
    over background paths; the net curve computed twice in Peaks, since sharing
    `netModel` would edit a file today's page uses.
  - *Measured* (macOS arm64, worktree `.venv` `[dev]` plus playwright, Python 3.12):
    fast suite 14946 passed, 424 skipped and 32 xfailed in 17 min, through the shift's
    serial lock at load average 40-75 from other sessions; this branch adds two python tests
    (5.54 s for the browser case, 0.35 s for the server case, local junit). Vitest 825 of
    825; svelte-check 0 errors in 453 files. GUI python files
    (`test_gui_server`, `_dist`, `_manual`, `_style_guide`, `_palette`, `_background`): 265
    passed before the review fixes; `_background` and `_dist` 27 with the graphs browser case
    after them. Browser files by glob: layout + gui 42 passed, peaks + recovery 7,
    structure3d + rxplot 49. Vale 0 errors. `python -m tests.reader_output`: exit 0,
    unchanged.
  - *Gotchas*: a chart built while a preview is up takes it without keeping a view
    (`setPreview(p, false)`); keeping one drew an empty plot. No generality review: the
    branch adds no package heuristic and leaves `_audit.py` alone.

  Next: Yue's look at § Questions 5-7 and the pictures. Then the third PR, the Structure
  graph (rows 69-82) from #1519's source, then the Instrument dialog (rows 133-136). The
  screenshots row closes with the last PR.

- **2026-11-18** — the first PR of R3: hand fitting works at `/next`.

  A person on the rebuilt page can now drag a slider in the Interactive tab and watch the
  Pattern graph redraw. The title line says "Preview, not refined" with both Rwp values, the
  last fit turns grey under the preview, and the legend's Preview slot fills. Nothing is
  refined until Apply, and an unapplied slider edit comes back through the recovery offer as a
  Parameters edit does. Today's page did not move: its bundle changed only by one unused
  colour token. Four visual questions wait on Yue (§ Questions 1-4), the dark last-fit grey
  being the one most worth a look.

  - *Done*: `gui/src/next/Interactive.svelte` is a copy of today's panel, drawn to the
    prototype (tinted group bands, value box, reserved ↺ slot, 0.5 % snap, the range pop-up
    with its last fit in the slider's format and Scale above its choice). `Frame.svelte`
    mounts it, counts slider edits in the action bar and carries them in the recovery copy.
    `Pattern.svelte` and `pattern.ts` draw the preview, its title states and the reserved
    legend slot. New token `--plot-last` (`viz/theme.py`, `tokens.css`, `lib/plot.ts`), held
    by `tests/test_gui_palette.py`. Vitest `next/Preview.test.ts` (four title and hand-off
    cases); browser case `test_a_slider_drag_previews_in_the_rebuilt_window_and_moves_nothing`.
    Pictures in `docs/wp/2218-screenshots/`, listed in its README.
  - *Review*: `/code-review high` found ten. Six fixed in one commit: a failed curves fetch
    now clears the frame's curves; the snap holds only while the last fit is on the track;
    Show only the data hides the preview; the rows' load error has its own field; the sliders
    rebuild only on a change in value, so no second preview is sent; a stale comment. Four
    declined: two are visual questions for Yue (§ Questions 3 and 4); sharing `rangeContext`
    with `App.svelte` would edit today's page, which the swap deletes; the group heading's
    size and the buttons' padding follow the prototype, and `lib/style.test.ts` does not scan
    `next/`, as WP-2215's leftover on issue #1656 already records.
  - *Measured* (macOS arm64, worktree `.venv` `[dev]` plus playwright, Python 3.12, load
    average 67-85 from other sessions): fast suite 14910 passed, 424 skipped, 32 xfailed and
    23 errors in 49 min. The 23 errors are one fixture: the manual's sphinx build hit its
    300 s runaway guard under the load. `tests/test_manual.py` and `tests/test_help.py` rerun
    alone: 102 passed. Every `tests/test_gui_*.py` and `tests/*_browser.py` serially: 507
    passed. Vitest 799 of 799; svelte-check 0 errors. The new browser case drew 24 preview
    redraws at 33-131 ms each, and took 56 s alone. No junit run: a second 49-minute suite
    under this load would time nothing usefully, so the cost line is that single timing.
    `python -m tests.reader_output`: unchanged.
  - *Gotchas*: `src/lib/structure3d.test.ts`'s scene-corpus case timed out once at 5 s in a
    full vitest run under load and passes alone; unrelated to this diff. A `{@const}` must sit
    directly under its `{#if}`.

  Next: the second PR, the Peaks and Background graphs (rows 59-68). Move
  `panels/PeakWindows.svelte` and `panels/Background.svelte` into `gui/src/next/` first, then
  draw each to the prototype (§ Context). Yue's answers to § Questions may land on this PR
  first.

- **2026-11-17** — filed by the session that opened R3, after the maintainer's "go" on
  2026-11-17. R3 splits into four PRs by screen, each a whole screen for review; the first
  builds the Interactive tab and the preview on the Pattern graph.

# WP-2218 — hand fitting and the other graphs: the Interactive tab, the Peaks, Background and Structure graphs, and the Instrument dialog at `/next`

Milestone: gui-overhaul · Status: 🔄 2026-11-17 — the first PR (the Interactive tab and the preview on the Pattern graph) open
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
- [ ] The Interactive tab at `/next` (rows 98-103) and the preview on the Pattern graph (row
  57): the title line's three states, the reserved Preview slot, the last fit in grey, slider
  edits counted in the action bar and carried by the recovery offer. A vitest mount case for
  the title (acceptance row 6) and a browser pass with a real drag (row 9). The first PR.
- [ ] The Peaks and Background graphs (rows 59-68). The second PR.
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

## Handover log

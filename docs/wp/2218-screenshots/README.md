# WP-2218 — hand fitting and the other graphs at `/next`

Review pictures for `../2218-hand-fitting-and-the-other-graphs.md`. Each whole-window picture
shows the rebuilt page at 1440 × 900, one device pixel per CSS pixel. The matching prototype
pictures stay outside the repository; the pull request names where they are.

The first PR's pictures, the Interactive tab and the preview on the Pattern graph:

- `interactive-rest-*.png`: the `fap` example after one staged fit, on the Interactive tab.
  Each slider sits at the last fit, on its mark. The legend keeps a blank slot for Preview.
- `interactive-preview-*.png`: Lattice parameter a dragged 0.3 of its track by the mouse, so
  the preview and the last fit separate (§ Rulings 4). The title reads "Preview, not refined"
  with the preview's Rwp beside the last fit's. The legend shows Preview. The value box turns
  the accent colour and its ↺ shows. The action bar counts one pending edit. Re-shot by the
  second PR, which also visited the Peaks graph first.
- `interactive-preview-zoom-*.png`: the same preview zoomed to 30.6-35.3° 2θ by a drag on the
  plot.
- `interactive-preview-zoom-crop-*.png`: part of that zoom at twice the size. The last fit is
  the thin line beside the preview, in `#849499` (light) and `#7f8f94` (dark, § Rulings 5).
- `interactive-rangepop-*.png`: the range pop-up, opened by a click on Caglioti U's name. From
  and To read 0.2772×10⁻³ and 4.4362×10⁻³, in the value box's digits (§ Rulings 7).
- Every `interactive-*.png` was re-shot on 2026-11-19, after the rulings of that day.

The second PR's pictures, the Peaks and Background graphs:

- `peaks-rest-*.png`: the Peaks graph after the fit. Six windows, two columns of three, each
  titled with its 2θ, hkl and phase, draw the data, the last fit and the residual strip. The
  overview strip above them draws the whole pattern and shades each window's range
  (§ Rulings 7).
- `peaks-stepped-*.png`: the preview below, with the second window stepped up by its ›. Its
  band on the overview moves from 49.5° to 56.1°.
- `peaks-preview-*.png`: the same graph under the 0.3 drag above. The last fit stays solid in
  its own ink and the preview takes the calculated curve's colour (§ Rulings 1).
- `peaks-shape-*.png`: Show set to "Peak shape alone": the model minus its background, last
  fit and preview.
- `background-rest-*.png`: the Background graph at the current values, the band at ×1.
- `background-hold-*.png`: the band at ×5 with terms 4 and 5 held by their chips. The title
  reads "Background preview" and the action bar counts two pending edits.

The third PR's pictures, the Structure graph, on the fluorapatite example after one fit:

- `structure-rest-*.png`: the graph at the current values, balls, with the colour key under
  the title line. The CaO₅ and CaO₆F polyhedra start off, so their entries are struck through.
- `structure-ellipsoids-*.png`: Ellipsoids, looking down c. The title states the probability.
- `structure-selected-*.png`: an atom clicked after a drag. The ring and its bar name it, and
  the status bar names what is under the pointer.
- `structure-coordination-*.png`: Show coordination on that atom.
- `structure-drawing-*.png`: the view menu's Drawing… popover.
- `structure-preview-*.png`: Lattice parameter a dragged 0.3 of its track in the Interactive
  tab. The title reads "Preview, not refined".

Taken 2026-11-18 and 2026-11-19 on macOS (arm64) with the cached chromium, against the dist this branch
commits, with `RIETX_STATE_DIR` pointed at a temporary directory. Every drag and click was made
by a real pointer move or click.

# WP-2200 — the palette beside the prototype

Review pictures for `../2200-the-palette.md`, required by the gui-overhaul milestone's
acceptance row 11. Each pair shows the built GUI and the workshop prototype at the same
window size, 1440 × 900 at one device pixel per CSS pixel, light and dark.

- `gui-pattern-*.png` beside `prototype-pattern-*.png`: the `fap` example project after one
  run, on the Pattern tab.
- `gui-peaks-*.png` beside `prototype-index-*.png`: the picked-peak marks. The GUI shows the
  same project after a peak search, on the Peaks tab. The prototype shows its "Peaks and
  indexing" workflow after "Pick peaks", reached by clicking through its workflow menu.

Taken 2026-11-10 on macOS (arm64) with the chromium that `docs/docs/make_screenshots.py`
finds, against the dist this branch commits. The theme was set through the GUI's own
setting, with `RIETX_STATE_DIR` pointed at a temporary directory.

The pictures are a review aid, not a pixel test. The prototype draws a fit it exported from
the same fluorapatite pattern at an earlier commit, and its panels are laid out by the later
pieces, so the colours and the chrome compare and the layout does not.

# WP-2201 — headings before and after

Review pictures for `../2201-headings-in-sentence-case.md`, for the gui-overhaul milestone's
acceptance row 10. Each pair shows the same view on `origin/main` (`before-*`) and on this
branch (`after-*`).

- `*-model.png`: the Model tab's panel column, with the section heading `Structure` and the
  Console bar's heading.
- `*-model-atoms.png`: the Model tab's atom table, whose column heads were uppercase and
  tracked.
- `*-report.png`: the Report tab, with its `Fit diagnostics` heading.
- `*-interactive.png`: the Interactive tab, with the slider groups' headings.

Taken 2026-11-10 on macOS (arm64) with the chromium that `docs/docs/make_screenshots.py`
finds, in a 1400 × 900 window at one device pixel per CSS pixel, light theme. The `fap`
example project was opened and its plan run once, with `RIETX_STATE_DIR` pointed at a
temporary directory. The panel pictures are cropped to the panel column.

# WP-2240 — the four steps beside the prototype

Review pictures for `../2240-the-peaks-and-indexing-workflow.md`, task 9. Each pair shows
the rebuilt page at `/next` and the workshop prototype at the same step and the same window,
1440 × 900 at one device pixel per CSS pixel, light and dark.

- `gui-1-pick-*.png` beside `prototype-1-pick-*.png`: the Pick step after Pick peaks.
- `gui-2-fit-*.png` beside `prototype-2-fit-*.png`: the Fit step with its third group
  chosen, the Peaks graph showing the windows from that group on. The GUI shows All groups.
  The prototype shows To look at.
- `gui-3-index-*.png` beside `prototype-3-index-*.png`: the Index step after a search, its
  first candidate chosen and drawn on the Pattern graph. `gui-3-index-running-light.png`
  shows the search under way.
- `gui-4-judge-*.png` beside `prototype-4-judge-*.png`: the Judge step after Screen
  extinctions, scrolled to the space-group table. `gui-4-judge-top-*.png` shows the top of
  the same step.

The GUI ran the `fap` example project (the GSAS-II fluorapatite tutorial pattern) through
`rietx.gui.GuiSession`, and every step was reached by clicks in chromium. The prototype is
`rietx-gui-workshop/prototype/app.html?wf=index`, with its own fluorapatite export. Taken
2026-11-23 on macOS (arm64) with the chromium that `tests/test_watch_browser.py` finds,
against the dist this branch commits, with `RIETX_STATE_DIR` pointed at a temporary
directory. The script is `p3_shots.py` in the runner's scratch directory.

The pictures are a review aid, not a pixel test. The two searches ran separately and under a
two-minute limit, so their candidate lists differ. Compare the layout, the words and the
colours.

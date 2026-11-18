# WP-2218 — hand fitting and the other graphs at `/next`

Review pictures for `../2218-hand-fitting-and-the-other-graphs.md`. Each whole-window picture
shows the rebuilt page at 1440 × 900, one device pixel per CSS pixel. The matching prototype
pictures stay outside the repository; the pull request names where they are.

The first PR's pictures, the Interactive tab and the preview on the Pattern graph:

- `interactive-rest-*.png`: the `fap` example after one staged fit, on the Interactive tab.
  Each slider sits at the last fit, on its mark. The legend keeps a blank slot for Preview.
- `interactive-preview-*.png`: Lattice parameter a dragged a tenth of its track by the mouse,
  as the prototype's picture drags its cell a. The title reads "Preview, not refined" with the
  preview's Rwp beside the last fit's. The legend shows Preview. The value box turns the accent
  colour and its ↺ shows. The action bar counts one pending edit.
- `interactive-preview-zoom-*.png`: the same preview zoomed to 30.6-35.3° 2θ by a drag on the
  plot. The boxed region is cropped beside it.
- `interactive-preview-zoom-crop-*.png`: that region at twice the size. The last fit is the
  grey line under the preview.
- `interactive-rangepop-*.png`: the range pop-up, opened by a click on Caglioti U's name.

Taken 2026-11-17 on macOS (arm64) with the cached chromium, against the dist this branch
commits, with `RIETX_STATE_DIR` pointed at a temporary directory. Every drag and click was made
by a real pointer move or click.

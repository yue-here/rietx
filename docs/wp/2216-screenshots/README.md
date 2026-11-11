# WP-2216 — the refinement window at `/next`

Review pictures for `../2216-the-refinement-window.md`. Each whole-window picture shows the
rebuilt page at 1440 × 900, one device pixel per CSS pixel. The matching prototype pictures
stay outside the repository; the pull request names where they are.

- `next-window-*.png`: the `fap` example after one staged fit, both side panels showing,
  the pointer off the plot. The status bar's right half shows the findings count.
- `next-hover-*.png`: zoomed to 29-35° 2θ by a drag, the pointer on the (3 −1 1) peak at
  31.86°. The status bar's right half shows the reading.
- `next-hover-statusbar-*.png`: that status bar, cropped from the picture above, doubled in
  size and boxed.
- `next-viewmenu-light.png`: the ⋯ menu on the graph's title line.
- `next-contextmenu-light.png`: the plot's right-click menu, off any region.
- `next-armed-light.png`: after choosing "Exclude a region…": the note says what a drag does.
- `next-region-selected-light.png`: a region dragged, then clicked. Its outline is the
  accent colour and its bar floats over the plot with typed bounds and the channel count.
- `next-graphs-hidden-light.png`: the graph column hidden. Rwp and GoF move to the action bar.
- `next-pending-light.png`: one Parameters edit, before Apply.
- `next-applied-light.png`: after Apply. The values are the model's, without esds; the
  graph keeps the last fit until the next run, as today's page does.

The readout follow-up's pictures, as ruled on 2026-11-11 ("try b"):

- `readout-hover-*.png`: the `fap` example after one staged fit, zoomed to 29-35° 2θ by a
  drag, the pointer on the (3 −1 1) peak at 31.86°. The status bar's right half reads
  `2θ 31.860°  d 2.806 Å  Observed 19693  Last fit 20307  Background 175  Difference −4.4σ
  fluorapatite (3 −1 1) +0.012°`. The intensity opens on square root. Parameters shows the
  filter text, the `° 2θ` units and the one-line broadening rows.
- `readout-statusbar-light.png`: that status bar's right half at twice the size. The labels are
  Instrument Sans in the muted colour, the numbers IBM Plex Mono in the ink, and θ and σ come
  from IBM Plex Sans.
- `readout-narrow-880-light.png`: the same hover at 880 px with the model panel hidden. The
  reflection has dropped.
- `readout-narrow-800-light.png`: at 800 px. Background has dropped as well.

Taken 2026-11-11 on macOS (arm64) with the cached chromium, against the dist this branch
commits, with `RIETX_STATE_DIR` pointed at a temporary directory. Every menu, drag, edit and
hover was made by a real click, key press or pointer move.

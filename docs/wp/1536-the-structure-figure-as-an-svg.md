# WP-1536 — the structure figure as an SVG

Milestone: rietview · Status: ⬜
Depends on: —
Priority: P3 2026-10-02 — a workaround covers it: a 3000 px PNG, or a CIF exported to VESTA's own vector output

## Goal

`render_structure(..., path="figure.svg")` writes the picture the PNG draws as
vector shapes. Each atom is an ellipse, each bond half a cylinder outline, each
polyhedron face a polygon, and the letters are text. Inkscape and Illustrator
open it with every atom a separate element, and `rsvg-convert -f pdf` turns it
into the PDF a journal asks for.

## Context

### Why now

WP-1462 D1 and WP-1470's Non-goals declined vector output. 1470's handover
left it "until a picture shows the need". The maintainer asked for it on
2026-10-02, together with ray-tracer input (WP-1537) and ambient occlusion
(WP-1538). No open WP owned it: 1468 is polyhedra rules, 1504 measures the
existing surface, and 1505 moves the code without adding to it.

### Prior art

- VESTA exports EPS, PDF, PS and SVG. 1462's survey named it as the only
  viewer with a vector export. A web search summary says users on its
  mailing list report that export as poorly implemented. Nobody here has
  read the thread (References), so read it before quoting it.
- matplotlib's `savefig` picks the format from the suffix. That is the API
  precedent for D1.
- `docs/wp/1470-spike/mpl_baseline.py` drew the structure with matplotlib,
  back to front. It draws bonds over balls they pass behind. 1470 called this
  the crossing fault, and D2 below is its repair.
- ASE writes EPS and SVG by drawing atoms as circles back to front. ASE is
  LGPL, so concepts only. Read its writer before D2 is built, and record
  what it does about bonds.

### What the writer reads

`scene.build_scene` returns plain lists (`src/rietx/viz/figure3d/scene.py`):

- `atoms`: `pos` (Å), `shape` (3×3 row-major M, so a surface point is
  `pos + M·u` with |u| = 1), `inverse` (M⁻¹), `color`, `rings`.
- `halves`: `from`, `to`, `radius` (Å), `color`. A half is an open cylinder
  from the bond's midpoint to its atom's centre.
- `lines`: `a`, `b`, `color`, `width` in CSS px (cell frame 2, polyhedron
  edges 1.25).
- `faces`: one entry per polyhedron, with `triangles`, `normals`, `color`
  and `centroid`. Faces draw at `POLY_ALPHA` = 0.55.
- `labels`: the a, b, c letters and their positions.

`render.py` fits a `raster.Frame` to the scene and owns the letters, the
background, `outline=` and `dpi=`. `raster.py` draws the PNG. Its module
docstring states the draw order: opaque solids depth-tested, then faces back
to front writing no depth, then letters.

Two projections are exact under the parallel projection the figure uses.
With P the top two rows of the view rotation, an ellipsoid projects to the
ellipse whose shape matrix is (PM)(PM)ᵀ. An open cylinder projects to a
rectangle closed by two half-ellipses.

### Decisions to carry

- **D1. The suffix picks the format.** `path` ending `.svg` writes SVG. The
  raster still runs, so `image`, `report`, `atoms` and `letters` are the
  PNG's. SVG user units are the PNG's pixels at `size`, so every position in
  `atoms` and `letters` holds for the SVG too. `dpi` sets the physical width
  as it sets the PNG's `pHYs`. The refusal at `render.py:670` names every
  suffix it takes. JPEG stays refused.
- **D2. Painter's algorithm, with the crossing fault repaired.** Every
  primitive gets a depth key, and the writer emits them far to near. Three
  repairs come first. A bond half is trimmed where its axis leaves its own
  atom's surface, found by solving |M⁻¹(p − pos)| = 1 along the axis. A
  trimmed half is cut into pieces no longer than the smallest drawn radius,
  so a bond passing behind a third atom sorts piece by piece. Each piece
  needs its own gradient, so count the elements on the largest corpus
  scene. If Inkscape slows, cut only the halves whose screen box overlaps
  an atom they do not belong to. Faces keep
  1470 D6's centroid order, back faces first. Interpenetration is what is
  left: a translucent face cuts a vertex atom, and large ellipsoids overlap.
  Measure that residue on the corpus before choosing whether to repair it.
- **D3. Shading is gradients computed from `LOOK`.** The raster shades
  `base·(ambient + diffuse·d) + specular·s^shininess` with a light fixed to
  the camera. A sphere takes a `radialGradient` whose focus is the
  highlight, with stops sampled from that formula along the radius. An
  ellipsoid takes the same gradient through a `gradientTransform` built
  from its projected 2×2 matrix. That is approximate, because normals
  transform by M⁻ᵀ, and the parity row measures it. A stick takes a
  `linearGradient` across its width, sampled the same way. A principal ring
  is the visible half of a projected ellipse.
- **D4. The letters are `<text>`.** The PNG draws them as Hershey strokes
  (`glyphs.py`). The GUI draws them as DOM text, and an editable label is why
  someone asks for a vector figure. Their positions are the PNG's.
- **D5. Elements carry their site.** Painter's order interleaves atoms,
  sticks and faces, so they cannot be grouped by kind. Each element carries
  a class instead (`atom Ca1`, `stick Ca1`, `face CaO6`, `cell`), so
  Inkscape's select-same selects every Ca1.
- **D6. No PDF writer.** `rsvg-convert` (installed here at
  `/opt/homebrew/bin`) and Inkscape both convert SVG to PDF. Check once that
  the gradients survive, and put the command in the manual.

### Seams

- `src/rietx/viz/figure3d/render.py`: the suffix dispatch. WP-1537 adds
  `.pov` and `.glb` to the same dispatch, so whichever WP lands second
  extends it.
- A new `src/rietx/viz/figure3d/vector.py`: scene and frame to a display
  list, then the display list to SVG text. Standard library only.
- `docs/manual/using/exports.md:219` says "There is no SVG or PDF output."
- `docs/skill/rietx/references/api-figure.md`: the paragraph naming what
  `path=` writes.

### Inherited

- **2026-10-23, from [1504](1504-the-figure-surface-measured-with-real-agents.md) (closed): the
  agent task an SVG answers.** 1504's tasks are in `docs/wp/1504-eval/`. Task 6, fluorapatite
  for print, is the one an agent could answer with an SVG once this lands. A later round that
  re-runs it measures this WP's surface. 1504 runs no further round itself.

## Non-goals

- Ray-tracer and 3D formats: WP-1537.
- Ambient occlusion: WP-1538. Per-pixel darkening has no vector form.
- Order-independent transparency, or splitting faces where they cut atoms,
  until D2's measurement shows a picture that needs it.
- A GUI button for SVG. WP-1537's GUI task adds one menu for every format.

## Tasks

- [ ] Read ASE's EPS/SVG writer and VESTA's vector-export thread. Record
  what each does about bonds and overlap in Context.
- [ ] D1: the suffix dispatch, with the refusal naming each suffix.
- [ ] The display list (`vector.py`): projected ellipses, trimmed and cut
  stick pieces, faces, lines, ring arcs and letters, each with a depth key.
  Unit tests: sample points on a projected ellipse lie on the raster's
  silhouette within half a pixel, and a trimmed end lies on its atom's
  surface.
- [ ] The SVG writer: D3's gradients, background or transparent,
  `outline=`, `dpi=`, D5's classes.
- [ ] The crossing fault: 1470's baseline case drawn correctly. Rasterise the
  SVG and test the pixels where the bond passes behind the ball.
- [ ] Parity: rasterise the SVG in chromium at the PNG's size, beside
  `test_structure3d_browser.py`'s parity row, and compare mean |Δ| in 8-bit
  levels against `render_structure`'s PNG. Run the 21 phases of
  `tests/data/polyhedra_phases.json` in ball, ball with polyhedra, and
  ellipsoid mode. Record each number, set the bar from the measurement as
  `PARITY_LEVELS` was set, and commit the worst three pictures.
- [ ] Convert one figure with `rsvg-convert -f pdf`, open it in Inkscape,
  and record both in the handover.
- [ ] Docs: `exports.md` loses its "no SVG" line and gains the PDF command;
  the `render_structure` docstring.
- [ ] Tests + figure pairs (PNG, rasterised SVG) to `tests/output/figure3d/`.
- [ ] Skill: one clause in `api-figure.md` saying `path="x.svg"` writes a
  vector figure, tagged with the parity measurement.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_structure3d_browser.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
rsvg-convert -f pdf -o /tmp/figure.pdf tests/output/figure3d/<case>.svg
```

The crossing case passes. The corpus parity stays under the bar the
measurement set. Inkscape opens the file with one element per atom.

## References

- VESTA's mailing list on its vector export:
  <https://groups.google.com/g/vesta-discuss/c/XDDrEpNhW10/m/bValumpLA-gJ>
- WP-1462 § D1 and WP-1470 § Non-goals, for the decline this reverses.
- `docs/wp/1470-spike/mpl_baseline.py`, for the crossing fault.

## Handover log

### 2026-10-02 — filed

The maintainer asked whether the structure figure could go to Blender, then
asked for vector output, ray-tracer input and ambient occlusion. This WP is
the vector part. The scene `build_scene` returns is already plain geometry
in Å, so an SVG is a projection of it, and the open question is the
painter's-algorithm fault 1470 found. Nothing is built.

- **Filed** because no open WP owns vector output (1468 is polyhedra rules,
  1504 measures the existing surface, 1505 moves code without adding to it).
- **Read**: `render.py`, `raster.py`'s docstring and `draw`, `scene.py`'s
  `LOOK` and `build_scene` output, 1462 § D1, 1470 § D6, D9 and Non-goals.
- **Reviewed** (`/code-review high --fix`): two stale line citations fixed.
  One point left as written: D5 keys a face's class by formula (`face CaO6`),
  so polyhedra round two Ca sites share a class. That selects every CaO6 at
  once, which may be what a person editing wants. Decide when D5 is built.
- **Tests**: none added, no source changed. The fast selection on this
  branch (`[dev]` venv, macOS 26.6 on Apple silicon) gave 7918 passed, 160
  skipped and 1 failed. The failure is
  `test_numpy_path_bit_identical_to_golden[toy_anomalous]` at 1.6e-11, which
  WP-1531 recorded: #669 re-baselined that golden on macOS 27.0.1. Main's CI
  is green at this branch's base, 94626aac.
- **Next**: the first task. Read ASE's writer before building D2.

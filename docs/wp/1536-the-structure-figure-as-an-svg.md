# WP-1536 — the structure figure as an SVG

Milestone: rietview · Status: 🔄 2026-11-16 — SVG writer in PR #1606; parity, PDF check and ASE read open (#1614)
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
1504's task 6 (`docs/wp/1504-eval/`, fluorapatite for print) is the agent
task an SVG answers; a later round that re-runs it measures this WP's
surface (folded from 1504's inherited note, 2026-11-16).

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
  as it sets the PNG's `pHYs`. The refusal in `render_structure` (at
  `render.py:815` on 2026-11-16, superseding the filed `:670`) names every
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
- **D6. No PDF writer.** `rsvg-convert` and Inkscape both convert SVG to
  PDF. Check once that the gradients survive, and put the command in the
  manual. (Superseded in part 2026-11-16: neither `rsvg-convert` nor
  Inkscape is installed on the runner's Mac any longer, so the check needs
  a machine that has one.)

### The tier of each rule this WP adds

None adds a judgement. The suffix is the caller's word for the format, and
the stick-piece length and gradient stop count are drawing constants that
change no reported number.

### Seams

- `src/rietx/viz/figure3d/render.py`: the suffix dispatch. WP-1537 adds
  `.pov` and `.glb` to the same dispatch, so whichever WP lands second
  extends it.
- A new `src/rietx/viz/figure3d/vector.py`: scene and frame to a display
  list, then the display list to SVG text. Standard library only.
- `docs/docs/reference/figures.md:217` says "There is no SVG or PDF output"
  (the manual moved from `docs/manual/using/exports.md:219`; checked
  2026-11-16).
- `docs/skill/rietx/references/api-figure.md`: the paragraph naming what
  `path=` writes.

### Inherited

- **2026-11-18, from the issue triage (#1667): WP-1537's two external checks are this
  WP's.** PR #1666 (open on 2026-11-18, head `da2f04fd2`) adds the POV-Ray and glTF writers
  and closes WP-1537 with three tasks moved to issue #1667. Two of them land here, since this
  WP's session works the same writers' dispatch (`render.WRITERS`), the same figures and
  `tests/test_render_structure.py`, and already plans an external-tool check of its own
  (`rsvg-convert`, Inkscape). (a) Render fluorapatite and NAC once in POV-Ray 3.7 and once
  in Blender (Cycles, the imported camera), and commit each beside its PNG under
  `docs/wp/1537-renders/`. That is WP-1537's acceptance that the chiral NAC phase (I2₁3)
  keeps its hand in POV-Ray; the merged tests check the hand by projection without
  rendering. (b) Run the Khronos validator on `tests/output/figure3d/nac_ball.glb` and
  `nac_ellipsoid.glb` and fix what it reports. The npm package `gltf-validator`
  (2.0.0-dev.3.10) declares no `bin`, so `npx gltf-validator` does not run; call its
  `validateBytes` from a short Node script. Checked against the tree at 3f5167863: no
  writer is on `main` yet (`render.WRITERS`, `.pov` and `.glb` absent under
  `viz/figure3d/`), POV-Ray and Blender are not installed on the machine that checked, and
  the npm metadata confirms no `bin`. Both tasks wait on #1666 merging. The issue's third
  task, the GUI export menu, is GUI work and stays with the issue until the GUI track takes
  it into the rebuilt Structure graph (WP-2218, open in PR #1673; inventory row 79 of
  WP-2214 homes the PNG export there).
- **2026-11-17, from [1537](1537-the-structure-scene-for-a-ray-tracer.md): the suffix
  dispatch is a tuple.** `render.WRITERS` lists the suffixes `path=` accepts (`.png`, `.svg`,
  `.pov`, `.glb`) and `render_structure` branches on it where it writes. `outline=` and
  `depth_cue=` are refused with a `.pov` or `.glb` scene only; the SVG draws both, as the PNG
  does. The GUI's export menu, which lists SVG, is issue #1667.

## Non-goals

- Ray-tracer and 3D formats: WP-1537.
- Ambient occlusion: WP-1538. Per-pixel darkening has no vector form.
- Order-independent transparency, or splitting faces where they cut atoms,
  until D2's measurement shows a picture that needs it.
- A GUI button for SVG. WP-1537's GUI task adds one menu for every format.

## Tasks

- [x] ~~Read ASE's EPS/SVG writer and VESTA's vector-export thread. Record
  what each does about bonds and overlap in Context.~~ Superseded 2026-11-16:
  D2 is built and tested by its own crossing case (decisions walk, settled).
- [x] D1: the suffix dispatch, with the refusal naming each suffix.
- [x] The display list (`vector.py`): projected ellipses, trimmed and cut
  stick pieces, faces, lines, ring arcs and letters, each with a depth key.
  Unit tests: sample points on a projected ellipse lie on the raster's
  silhouette within half a pixel, and a trimmed end lies on its atom's
  surface.
- [x] The SVG writer: D3's gradients, background or transparent,
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

### 2026-11-16 — first slice (ghostshift runner), PR #1606

`render_structure(..., path="figure.svg")` now writes the picture as vector
shapes: every atom an ellipse with a shaded gradient, every bond a run of short
stick pieces, every polyhedron face a translucent polygon, the letters as text,
each element classed by its site. Looked at side by side with the PNG on
rutile (balls with octahedra, and ellipsoids) and on the largest corpus phase,
the two read as the same figure. What is not yet known is how close they are
in numbers: no rasteriser for SVG is installed where this ran, so the parity
row, the pixel test of the crossing case and the PDF check are all still open.

- **Done.** D1: `render.WRITERS` is `(".png", ".svg")`, the refusal quotes it,
  and the raster runs either way, so `image`, `atoms`, `letters` and `report`
  are the PNG's. The display list and writer are `figure3d/vector.py` (numpy
  and the standard library). D2 as filed, with three choices of this session:
  a stick is trimmed where the **first rim point** leaves its atom (the least
  `t` over 16 rim directions, √(R² − r²) on a sphere), not where the axis
  leaves it, since the axis trim left a background notch; **lines are trimmed
  the same way** at any atom they end in (cell corners, polyhedron vertices),
  or their near pieces sorted in front of the ball they start in; and a half's
  atom is found **by position**, because a bond's far end is often an image
  of atom `j`, not atom `j`. Pieces are no longer than the smallest drawn
  semi-axis, floored at `PIECE_FLOOR` = 0.15 Å, and overlap by half a pixel
  so no seam shows. Atoms tie-break on how far they reach toward the viewer,
  so of two sites sharing a position the one the raster shows is drawn last
  (the corpus's mixed Fe/Mg sites showed it). Each face keys on its own
  centroid (one polygon per plane), which puts a centre atom between its
  polyhedron's back and front faces; D2's per-polyhedron order is not kept,
  issue #1614 item 4. D3 as filed (radial focus at the half vector, stops
  along the ray from it; linear gradient across a stick, exact). D4, D5 as
  filed; D5's open question is answered by the formula with its subscripts,
  so `face TiO₆` selects every TiO₆.
- **Review.** `/code-review` edits the main checkout, so a read-only review
  agent read the diff instead. Fixed from it: the two trims above, quotes in a
  site label breaking the document, one fog value for a whole half, round
  line caps where the raster's are square, and a crossing test whose
  assertion could not fail (the bond now tilts so a whole half would sort
  wrong, and the test asserts per piece). Not fixed, filed as #1614: the
  outline drawn as a centred stroke and never fogged, ring and named-face
  fills that may seam per triangle, the radial gradient's dark rim on the
  highlight side (a limit of D3), face order, `dominant-baseline` in librsvg,
  and the class-token details.
- **Measured.** Element counts at 600 px: rutile with octahedra 49 ellipses,
  72 face polygons, 1380 line pieces, 187 kB; rutile ellipsoids 51 ellipses,
  696 stick paths, 116 linear gradients, 33 ring arcs, 255 kB; the largest
  `polyhedra_phases.json` phase 116 ellipses, 168 faces, 3214 line pieces,
  436 kB. Lines dominate; if an editor slows, cut only pieces whose screen box
  meets an atom (D2's fallback). Writing an SVG adds well under 0.1 s.
  reader_output: exit 0, unchanged.
- **Tests** (`[dev]` venv, macOS 26 arm64 for the targeted runs; a Linux
  workstation for the suites): the canary selection (this file's tests,
  `test_structure3d_browser.py`, audit_table, help, docs_consistency, skill;
  `-n 4`) gave 401 passed, 1 skipped on 07f6ff48d. The fast selection
  (`-m "not slow" -n 8 --dist loadgroup`, 2176fd57b, beside other
  jobs at load 25-32) gave 14859 passed, 280 skipped, 32 xfailed, 0 failed
  in 1005 s. Nine cases were added (seven tests), costing 1.11 s together
  in that run's junit, the slowest the end-to-end SVG test at 0.54 s; the
  browser module skips here as everywhere without playwright. Main's own
  count on the same day was not run, so the +9 is the added cases, not a
  measured delta. ruff clean; Vale 0 errors.
- **Not done.** Task 1: reading ASE's writer is a question for the user (see
  Next). The crossing task is half done: the order-level repair is tested, the
  rasterised pixels are not. Parity, the PDF check and the manual's PDF
  command need chromium (playwright) or `rsvg-convert`/Inkscape, none of
  which is installed on the runner's Mac. The docs and skill tasks are done
  except the PDF command and the measured tag (the skill clause is tagged a
  hypothesis). Figure pairs: the SVG and PNG are written to
  `tests/output/figure3d/`, the rasterised SVG is not.
- **Next.** First, on a machine with playwright's chromium: the parity row
  (21 phases × ball, ball with polyhedra, ellipsoid), which also measures
  #1614's items 1-4 and decides which to repair; then the rasterised crossing
  test from the same harness. Then `rsvg-convert -f pdf` and Inkscape once,
  the PDF command into `figures.md`, and the measured tag on the skill clause.
  Task 1 waits on the user's answer: the house clean-room rule says an
  agent never opens a reference implementation's source, while this task
  asks to read ASE's LGPL writer for concepts.

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

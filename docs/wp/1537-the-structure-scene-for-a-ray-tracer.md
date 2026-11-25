# WP-1537 — the structure scene for a ray tracer: POV-Ray and glTF

Milestone: rietview · Status: 🔄 2026-11-24 — the .pov and .glb writers landed (PR #1666); the GUI menu, the one-off renders and the validator run wait, with #1667 as the pointer; the close is decided at the post-merge handover
Depends on: 1536 soft (the GUI menu lists SVG once it lands)
Priority: P3 2026-10-02 — a workaround covers it: a CIF opened in Blender's atomic add-on or in VESTA, which loses rietx's bond rules, polyhedra and colours

## Goal

`render_structure(..., path="figure.pov")` writes a POV-Ray 3.7 scene, and
`path="figure.glb"` writes a glTF 2.0 binary. Both carry the figure's camera
and light. `povray figure.pov` ray-traces the same framing, and Blender
imports the `.glb` with materials, camera and light ready for Cycles. The
GUI's export button offers SVG, POV-Ray and glTF beside PNG.

## Context

### Why now

The maintainer asked on 2026-10-02 whether the figure could go to Blender
for ray tracing, then asked for ray-tracer input with WP-1536 (SVG) and
WP-1538 (ambient occlusion). WP-1470's Non-goals fenced shadows and ambient
occlusion out of the CPU renderer, and a ray tracer supplies both. No open
WP owns an export format.

### Prior art

- VESTA exports POV-Ray, VRML, X3D and STL among others (References).
- ChimeraX saves `.glb`, `.stl`, `.obj` and `.x3d`. A 2020 post on its
  users' mailing list recommends glTF for getting a scene into Blender,
  Cinema4D or Maya. It exports shapes and vertex colours only and leaves
  materials, camera and lighting to the target program. This WP writes a
  camera, a light and materials, because a figure's framing is most of the
  work.
- The same post notes that STL carries no colour and OBJ no vertex colour.
  That is why neither is written here (Non-goals).
- **Never open ChimeraX's source code, and copy nothing from it** (the
  maintainer, 2026-10-02). Its user documentation and mailing list are the
  only ChimeraX sources here.
- POV-Ray is AGPL-3.0 and ASE's POV-Ray writer is LGPL. This WP writes
  POV-Ray's input language and ports no code. Read ASE's writer for its
  camera and finish conventions, concepts only.

### What the writers read

The same scene WP-1536 reads (`scene.build_scene`): `atoms` with `pos`,
`shape` (3×3 row-major M, surface `pos + M·u` with |u| = 1), `color` and
`rings`; `halves` with `from`, `to`, `radius` and `color`; `lines` with a
width in CSS px; `faces` drawn at `POLY_ALPHA` = 0.55; `labels`. `render.py`
supplies the view rotation, the fitted `raster.Frame` (its `ppa` converts a
pixel width to Å), the letters as Hershey strokes (`glyphs.py`) and the
background. `scene.LOOK` holds the light and finish: light direction
`[-0.40, 0.55, 0.73]` in view space, ambient 0.45, diffuse 0.60, specular
0.16, shininess 40. A principal ring is where the smallest unit-frame
coordinate is under `ring_width` = 0.035.

### POV-Ray

- An atom is `sphere { 0, 1 ... matrix <M> translate pos }`, an exact
  ellipsoid, as the raster solves it. POV-Ray's `matrix` lists the images of
  x, y and z in turn, so its first three numbers are M's first **column**.
  Written in `shape`'s row-major order, the sphere takes Mᵀ, and MᵀM is a
  different ellipsoid whenever M is not symmetric. glTF's `node.matrix` is
  column-major for the same reason.
- A ring is a pigment in the unit frame, before the matrix:
  `function { min(abs(x), min(abs(y), abs(z))) }` under a colour map with
  one step at `ring_width`. That is the shader's own rule, exact on the
  ellipsoid.
- A bond half is `cylinder { from, to, r open }`, open as the raster's are.
  A face is a `mesh2` with `transmit` 1 − `POLY_ALPHA`. A line is a cylinder
  of radius ½·width·`px_scale` / `ppa`, since `width` is in CSS px and `ppa`
  is per image pixel (`raster._pack` scales it the same way). The letters
  are the Hershey strokes as thin cylinders in the camera plane, so no font
  file is needed.
- The camera is `orthographic` with the frame's width and height in Å.
  **POV-Ray is left-handed** and rietx's Cartesian frame is right-handed.
  Without a mirror the picture is the enantiomer, and a centrosymmetric
  test phase cannot show it. Test with a chiral phase and compare against
  the PNG. NAC (I2₁3, `tests/data/cod_1000236.cif`) and quartz (P3₂21,
  entry 12 of `tests/data/polyhedra_phases.json`) are both to hand.
- One `light_source` at the camera's `LOOK` direction, with `finish`
  values mapped from `LOOK`. Radiosity, POV-Ray's global illumination, is
  written behind `#declare RIETX_RADIOSITY = off;`, so a user turns it on
  with one edit.

### glTF 2.0

- A `.glb` is a JSON chunk and a binary chunk. The standard library and
  numpy write it, with no dependency. `.gltf` with a separate `.bin` is two
  files and is declined.
- One unit icosphere and one open unit cylinder hold the geometry. Each
  colour gets a mesh over those shared accessors, since glTF binds a
  material to a mesh primitive. Each atom and each half is a node.
- glTF node matrices must decompose into translation, rotation and scale,
  with no shear. Ball mode's M is r·I. Ellipsoid mode's M should be the
  principal axes (`structure3d._pin_axes`) times the semi-axes, which
  decomposes. Verify it. Where det < 0, negate one axis, because the
  ellipsoid is symmetric under it. Where M does not decompose, bake the
  vertices.
- A ringed atom uses a sphere split into band and non-band triangles: two
  primitives, two materials.
- Faces are one mesh per polyhedron with `alphaMode: BLEND` and base colour
  alpha `POLY_ALPHA`. Lines and letters are thin cylinders, as in POV-Ray.
- An orthographic camera node with `xmag`/`ymag` from the frame. They are
  half the frame's width and height in Å, and Blender's importer doubles
  them into its ortho scale. Then one
  `KHR_lights_punctual` directional light at the `LOOK` direction. Blender
  imports both.
- glTF is right-handed with +Y up, in metres. Write 1 Å as one unit and say
  so in the manual. Blender's importer converts +Y up to +Z up.
- Check every file with the Khronos glTF-Validator (`npx gltf-validator`,
  Apache-2.0, 2.0.0-dev.3.10 on npm on 2026-10-02).

### Tools for the one-off check

`brew install povray` gives 3.7.0.10. `brew install --cask blender` gives
5.2.2. Neither is a test dependency. A task below renders once with each and
commits the pictures beside the PNG.

### The GUI

The PNG export stays client-side (`Structure3D.svelte`, `gl3d.ts`'s
`exportPng`). The other formats come from one server route, for example
`POST /api/structure3d/export`. Its body is the format, the panel's `View`
(`rotation`, `zoom`, `pan`; `structure3d.ts:785`), the canvas's CSS size and
the query options `GET /api/structure3d` already takes. It calls the same
writers through `render.gui_frame`. That frame is the canvas's at zoom 1
with no pan, so the route applies the `View`'s `zoom` and `pan` to it before
the file can have the canvas's framing.
`gui/CLAUDE.md` holds the server contract. `tests/test_gui_manual.py`
partitions the routes, so the route needs a manual chapter in the same
change.

### Seams

- `src/rietx/viz/figure3d/render.py`: the suffix dispatch WP-1536 adds
  `.svg` to. Whichever lands second extends it.
- A new `src/rietx/viz/figure3d/scene3d.py` (or one module per format):
  the scene, view and frame to a POV-Ray text and a GLB byte string.
- `src/rietx/gui/server.py` and `gui/src/panels/Structure3D.svelte` for the
  menu, then a rebuilt dist.

### Inherited

- **2026-11-16, from [1536](1536-the-structure-figure-as-an-svg.md) (open, PR #1606): the
  suffix dispatch exists.** `render.WRITERS` is the tuple `render_structure`'s refusal quotes,
  `(".png", ".svg")`, and the write branch in `render_structure` picks the writer by suffix after
  the raster has run; `.pov` and `.glb` join that tuple and that branch. `vector.py`'s
  `display_list` is a flat, depth-keyed list in image pixels, so it is not the scene a ray tracer
  wants: read `scene.build_scene`'s Å geometry as this WP's Context already says.

## Non-goals

- STL, OBJ, X3D and VRML. STL has no colour and OBJ no vertex colour.
  Blender converts a glTF into each of them.
- A 3D-printable model. It needs thicker sticks than a figure and one
  closed solid, which is its own WP if someone asks.
- Ambient occlusion in rietx's own renderers: WP-1538. In these formats the
  ray tracer supplies it.
- A Blender add-on or a `bpy` script. glTF import ships with Blender.

## Tasks

- [x] The `.pov` writer: atoms, rings, halves, faces, lines, letters,
  camera and light. Test: the handedness check on a chiral phase, an
  unrendered text comparison against a committed small case, and each
  atom's `matrix`, read in POV-Ray's column order, mapping the unit sphere
  onto `pos + M·u` on an ellipsoid whose M is not symmetric.
- [ ] The `.glb` writer. Test: the file parses as GLB (magic, version,
  chunk lengths), node transforms reproduce each atom's `shape` to 1e-12,
  and the validator reports no errors on the corpus. *2026-11-17: built and
  tested; the Khronos validator's own run waits (#1667): `npx gltf-validator`
  has no command-line entry point, so it needs a Node script calling
  `validateBytes`.*
- [ ] Render the fluorapatite and NAC figures once with POV-Ray and once in
  Blender (Cycles, the imported camera). Commit each beside the PNG under
  `docs/wp/1537-renders/` and record the commands in the handover.
  *Waits (#1667, 2026-11-17): neither program was installed on any machine the runner could use.*
- [ ] The GUI: the route, the export menu (PNG, SVG once 1536 lands,
  POV-Ray, glTF), the manual chapter and a browser test that downloads a
  `.glb` and checks its header. Rebuild the dist. *Waits (#1667,
  2026-11-17): the route must carry the panel's client-side drawing state
  besides its `View`.*
- [x] Docs: `docs/manual/using/exports.md` gains a section on ray-tracer
  input, with the POV-Ray command and the Blender import steps. The
  `render_structure` docstring names each suffix. *2026-11-17: that page is
  now `docs/docs/reference/figures.md`, § A scene for a ray tracer.*
- [x] Tests + the render pictures to `tests/output/figure3d/`. *2026-11-17:
  the tests write NAC's `.pov`, `.glb` and PNG there; the ray-traced
  pictures are #1667's.*
- [x] Skill: one clause in `api-figure.md` naming `.pov` and `.glb`, tagged
  with what was rendered (from `docs/skill/make_api_index.py`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_structure3d_browser.py tests/test_gui_manual.py -n auto --dist loadgroup
npx gltf-validator tests/output/figure3d/<case>.glb
povray +W1000 +H600 tests/output/figure3d/<case>.pov
.venv/bin/python -m ruff check src tests examples
npm --prefix gui test && npm --prefix gui run check
```

The chiral phase renders the same hand in POV-Ray as in the PNG. The
validator reports no errors. Blender opens the `.glb` with the figure's
camera and renders it in Cycles.

## References

- VESTA's export formats: <https://jp-minerals.org/vesta/en/>
- ChimeraX `save` (formats) and its note on exporting to Blender:
  <https://www.cgl.ucsf.edu/chimerax/docs/user/commands/save.html>,
  <https://www.rbvi.ucsf.edu/pipermail/chimerax-users/2020-October/001535.html>
- glTF 2.0 specification and `KHR_lights_punctual`: Khronos Group.
- POV-Ray 3.7 reference: `camera` (orthographic), `function` pattern,
  `mesh2`.

## Handover log

### 2026-11-17 — the .pov and .glb writers (PR #1666, rest waits on #1667)

A structure figure can now leave rietx for a ray tracer: `render_structure`
with a `.pov` path writes a POV-Ray scene and with a `.glb` path a glTF
file Blender opens, each framed as the PNG is, with its light. The
mirror-image trap the filing warned about is closed and tested: a chiral
structure's atoms, carried through the written camera as POV-Ray reads it,
land on the PNG's pixels at the PNG's depths, and the test fails without
the mirror. Nothing was ray-traced, because neither POV-Ray nor Blender was
installed on any machine the runner could use, and the GUI menu was not
started; both wait, with the validator run, behind issue #1667. The WP stays
open: the maintainer closes it at the post-merge handover (review of #1666,
2026-11-23).

- **Done**: `viz/figure3d/scene3d.py` (`pov`, `glb`, `ring_sphere`, `trs`);
  `render.py`'s suffix dispatch (`WRITERS`), refusing `outline`/`depth_cue`
  with a scene; `docs/docs/reference/figures.md` § A scene for a ray tracer
  (the WP's `docs/manual/using/exports.md` no longer exists); the skill clause,
  from `docs/skill/make_api_index.py`, tagged Hypothesis; 8 tests (11 items)
  in `tests/test_render_structure.py` and the committed small case
  `tests/data/figure3d_one_ellipsoid.pov` (provenance in its README).
- **Decided here**: glTF colours are linear factors of the sRGB values and
  POV-Ray's are `srgb`, so unlit ink matches the PNG exactly; a lit surface
  shades in linear light and differs. The glTF light is in lux, `diffuse·π·683`,
  which Blender's importer converts back to `diffuse·π` W/m². Roughness 0.5 is a
  look value. The ringed unit sphere lays its triangles on the ring edges
  (octant patches, strips, pole caps), so the band is exact, not sampled.
- **Reviewed** (a read-only review agent, standing in for `/code-review`,
  which a runner may not run): no bug found in either writer. Applied: a
  mirroring sheared shape is folded before baking (it drew inside out);
  accessors are written on first use; normals get their own accessor; glTF
  letter strokes are rounded at their ends; `KHR_materials_unlit` is listed
  only when used; tests now pin both lights, a bond half's ends and the
  letters' plane. Its note that a one-object `union` draws a POV-Ray parse
  warning is left, being harmless.
- **Measured**: the new tests, 11 passed (arm64 Mac, `[dev]` venv); lint and Vale clean; `tests.reader_output` exit 0. The fast suite was running when the shift paused (2026-11-17T16:25Z) and is not quoted: the next session runs it, then marks the PR ready.
- **Gotchas**: `npx gltf-validator` does not run, since the npm package has
  no command-line entry point; it needs a Node script calling
  `validateBytes` (#1667). Homebrew is not on this Mac and pearl has neither
  program.
- **Next** (#1667): run the validator on `tests/output/figure3d/nac_*.glb`;
  render NAC and fluorapatite once in POV-Ray and in Blender to confirm the
  hand by eye; then the GUI route, which must carry the panel's client-side
  drawing state (hidden species, polyhedra switches, exaggeration, stick)
  besides its `View`.

### 2026-10-02 — filed

The maintainer asked whether the structure figure could go to Blender for
ray tracing. The figure's scene is plain geometry in Å, and every atom and
bond is an exact quadric, so a POV-Ray scene can draw it exactly and a glTF
can carry it into Blender with its camera. This WP writes both, and gives
the GUI a menu for them. Nothing is built.

- **Filed** because no open WP owns an export format.
- **Checked**: `povray` 3.7.0.10 and `blender` 5.2.2 install from Homebrew,
  `gltf-validator` is on npm, `rsvg-convert` and Inkscape are installed
  here. None is installed for the tests.
- **Reviewed** (`/code-review high --fix`): POV-Ray's `matrix` and glTF's
  `node.matrix` both take M's columns, so writing `shape` row by row draws
  Mᵀ. A line's radius needs `px_scale`. `gui_frame` is zoom 1 with no pan,
  so the route applies the `View`. All three are now in Context.
- **Next**: the `.pov` writer and its handedness test, which is the trap
  most likely to pass unnoticed.

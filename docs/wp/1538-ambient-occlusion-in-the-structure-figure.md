# WP-1538 — ambient occlusion in the structure figure

Milestone: rietview · Status: ⬜
Depends on: —
Priority: P3 2026-10-02 — a workaround covers it: WP-1537's POV-Ray or Blender output computes ambient occlusion in the ray tracer

## Goal

`render_structure(..., ambient_occlusion=True)` and a GUI toggle darken each
surface by the share of directions from which ambient light cannot reach it.
The darkening comes from 64 directional shadow maps, the method ChimeraX
uses. It is off by default, and both renderers draw the same picture with it
on.

## Context

### Why now

WP-1462's Non-goals listed ambient occlusion as an addition worth its own
WP. WP-1470 D9 declined it as "a cost the figure does not need". The
maintainer asked for it on 2026-10-02, if it is cheap, alongside WP-1536
(SVG) and WP-1537 (ray-tracer input). This file prices it.

### Prior art

- ChimeraX's `lighting soft` lights a scene by ambient light only, shadowed
  from 64 directions. `lighting full` adds a key light with shadows. Its
  parameters are `multiShadow` (64 directions), `msMapSize` (1024, the depth
  map size, which sets how small a crevice can darken) and `msDepthBias`
  (0.01 × scene size, against self-shadowing). These facts come from its
  user documentation (References). **Never open ChimeraX's source code,
  and copy nothing from it** (the maintainer, 2026-10-02). The method is
  built here from its description and from papers.
- Mol\* and NGL use screen-space ambient occlusion (SSAO), computed from the
  depth image after drawing.
- Tarini, Cignoni & Montani (2006), QuteMol, is cited in 1462 and 1470 for
  ambient occlusion and edge cueing. It is not in the local corpus. Ask for
  it before choosing constants.

### Measured on 2026-10-02

`docs/wp/1538-measure/ao_probe.py`, run in this worktree's venv on the
maintainer's Mac, on fluorapatite (106 atoms), NAC (173) and LaB6 (116).

**What it would cost.** 64 id passes, the depth test's twin, took
0.08-0.15 s at 256 px and 0.28-0.71 s at 1024 px. One 1000 px render took
0.02-0.04 s after compile. At ChimeraX's defaults the maps cost 12 to 21
plain renders. Ambient occlusion does not depend on the view, so one set of
maps serves every view of a scene.

**Whether it would show.** This estimate uses the analytic configuration
factor. A sphere of radius r, a distance d away and wholly above a surface
point's tangent plane, occludes cos θ·(r/d)² of its ambient light. Atoms
alone, 64 surface points each:

| Occluders within | Ball mode, mean (p95) | Ellipsoid mode at 50 %, mean (p95) |
|---|---|---|
| 3 Å | 4.7-7.8 % (11-14 %) | 0.4-0.8 % (0.8-1.6 %) |
| 5 Å | 9.1-11.0 % (17-21 %) | 0.7-1.6 % (1.3-2.8 %) |
| no cutoff | 14.9-15.8 % (28-31 %) | 1.2-3.0 % (2.3-5.7 %) |

So ambient occlusion shows in ball mode and is close to invisible in
ellipsoid mode, where the atoms are small against their spacing. With no cutoff,
adding the sticks as chains of spheres (`--sticks`) multiplies the
ball-mode mean by 1.7 to 2.2. Those spheres overlap and overcount, so read that as an upper
bound on what sticks add. The multishadow number is the WP's to measure.

### Decisions to carry

- **D1. Multishadow, over the analytic factor and SSAO.** A shadow map is
  the renderer's own depth test from another direction, so visibility is
  exact for every primitive the raster draws: ellipsoids, sticks and the
  cell frame. The analytic factor needs an approximation for sticks and
  ellipsoids and an invented cutoff. SSAO needs the whole depth image, and
  the CPU raster draws in row bands (`raster.BAND_SAMPLES`), while a shadow
  lookup needs only the sample.
- **D2. One fixed set of directions.** 64 directions on a Fibonacci sphere,
  in the structure's Cartesian frame, identical in Python and TypeScript.
  Nearest-texel lookup with a depth bias. The same map size on both sides.
  Start at ChimeraX's 64, 1024 and 0.01, then measure.
- **D3. Occlusion scales the ambient term only.** The raster shades
  `base·(ambient + diffuse·d) + specular·s^shininess` with `ambient` 0.45 and
  `diffuse` 0.60 (`scene.LOOK`). With A the unoccluded share, the shade
  becomes `base·(ambient·A + diffuse·d) + specular·s^shininess`. The key
  light keeps its direct term, as in ChimeraX's `full` preset.
- **D4. Translucent faces cast and receive nothing at first.** A face at
  `POLY_ALPHA` = 0.55 casting a full shadow would darken its own centre
  atom. Look at the corpus pictures before deciding otherwise.
- **D5. Maps belong to the scene.** They are cached on the scene, so a GUI
  rotation reuses them. `view="auto"`'s id passes shade nothing and need
  none, so only the drawn view builds them. Anything that rebuilds the scene
  rebuilds them: mode, `stick=`, `exaggeration=`, hidden species, cut,
  extent or polyhedra. The cell frame's width is in CSS px, so its width in
  Å follows the frame's `px_scale` and `ppa`. Either it casts at a fixed
  width in Å, or the maps depend on the framing and cannot be cached on the
  scene alone. Decide which before D1's "the cell frame" is built.
- **D6. Python first, then the GUI, and off by default.** `outline=` is the
  precedent (1470 D9): an option the GUI does not draw stays off, so an
  agent's figure looks like the GUI's. Here the GUI gains the toggle in the
  same WP, and `test_structure3d_browser.py`'s parity row gains a case with
  occlusion on, held to the same `PARITY_LEVELS`. Turning it on by default
  is a separate decision, made from before-and-after pairs on the 21
  phases.

### Seams

- `src/rietx/viz/figure3d/raster.py` and `_kernels_numba.py`: a depth-map
  pass beside `id_plane`, and the lookup in the shading of both paths. The
  numpy path stays the bit-identity oracle (root CLAUDE.md, the compiled
  tier).
- `src/rietx/viz/figure3d/render.py`: the keyword, and `recipe` carries it.
- `gui/src/lib/gl3d.ts`: a depth pass per direction into a texture array,
  run when the scene changes, and the lookup in the atom and stick shaders.
  `gui/CLAUDE.md` § the renderer holds its rules: one context for the
  canvas's life, and the PNG export renders again offscreen.
- `gui/src/panels/Structure3D.svelte`: the toggle.
- `scene.LOOK`, if D2's constants become shared look values.

### Inherited

- **2026-10-10, from WP-1940 (4th session, PR #864).** The rasteriser's numba twin is
  deleted in that PR, and its port into `kernels/src/lib.rs` is the next
  kernel release, 1.1.0 (1940 § Decisions item 9). An occlusion kernel joins
  that port or a later minor release, held to `raster.py`'s numpy functions
  on the bit.

- **2026-10-10, from WP-1940 (3rd session).** numba leaves rietx at the
  kernel migration (1940 § Decisions item 8), and the rasteriser's numba
  twin is deleted then. The task "the numba kernel, held bit-identical to
  the numpy path" becomes a kernel in `kernels/src/lib.rs` once 1940 ports
  the rasteriser, or the numpy path alone before that.

## Non-goals

- Ambient occlusion in the SVG (WP-1536). Darkening per pixel has no vector
  form.
- Cast shadows from the key light, depth of field, perspective. A ray
  tracer gives them through WP-1537.
- Changing the default look. D6.

## Tasks

- [ ] Ask for Tarini, Cignoni & Montani (2006), and read it before fixing
  D2's constants.
- [ ] The depth-map pass and the lookup in the numpy path, with unit tests:
  an isolated atom is unoccluded everywhere, and a point between two touching
  atoms is darker than the far side of either.
- [ ] The numba kernel, held bit-identical to the numpy path.
- [ ] `ambient_occlusion=` on `render_structure`, with D5's cache. Measure
  the cost at 1000 px and 3000 px on the 21 phases. Quote ranges.
- [ ] Before-and-after pairs on the 21 phases in ball and ellipsoid mode,
  committed under `docs/wp/1538-measure/`. Decide D4 from them.
- [ ] The GUI: the depth passes and lookup in `gl3d.ts`, the toggle, and a
  parity case with occlusion on. Check that rotation stays smooth on the
  largest corpus scene, since the maps are built once a scene.
- [ ] Docs: the `render_structure` docstring and the GUI guide's structure
  section.
- [ ] Tests + figure pairs to `tests/output/figure3d/`.
- [ ] Skill: one clause in `api-figure.md` saying the option darkens ball
  mode and barely touches ellipsoid mode, tagged with this WP's
  measurement.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_structure3d_browser.py -n auto --dist loadgroup
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_render_structure.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
npm --prefix gui test && npm --prefix gui run check
```

The parity row passes with occlusion on. The numba and numpy paths agree
bit for bit. The before-and-after pairs are committed and looked at.

## References

- ChimeraX `lighting`:
  <https://www.cgl.ucsf.edu/chimerax/docs/user/commands/lighting.html>
- Tarini, M., Cignoni, P. & Montani, C. (2006). Ambient occlusion and edge
  cueing for enhancing real time molecular visualization. *IEEE Trans. Vis.
  Comput. Graph.* 12, 1237-1244. Not yet read.

## Handover log

### 2026-10-02 — filed

The maintainer asked for ambient occlusion in the structure figure if it is
cheap. It is affordable: ChimeraX's method costs 12 to 21 plain renders,
once a scene. It shows in ball mode, where the default figure darkens by
about 15 % on average with no cutoff, the row multishadow comes closest to,
and 5-11 % from occluders within 3-5 Å. It hardly shows in ellipsoid mode. The cost
that matters is the second renderer: the GUI and `render_structure` draw one
picture, so the GUI needs the same depth passes. Nothing is built.

- **Filed** because no open WP owns a lighting change. 1470 D9 declined it,
  and the maintainer's request reverses that.
- **Measured**: the table above, from `docs/wp/1538-measure/ao_probe.py`.
- **Reviewed** (`/code-review high --fix`): D5 rewritten. The view search
  shades nothing and never reads the maps. Everything that rebuilds the
  scene rebuilds them. The cell frame's width in Å follows the framing,
  which is a decision to make before it casts. The headline now quotes the
  no-cutoff row.
- **Next**: ask for Tarini et al. (2006), then the numpy path.

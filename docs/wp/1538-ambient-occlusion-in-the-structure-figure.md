# WP-1538 — ambient occlusion in the structure figure

Milestone: rietview · Status: 🔄 2026-11-17 — built in both renderers (PR #1641); the look choices wait on the maintainer
Depends on: —
Priority: P3 2026-10-02 — a workaround covers it: WP-1537's POV-Ray or Blender output computes ambient occlusion in the ray tracer

## Goal

`render_structure(..., ambient_occlusion=True)` and a GUI toggle darken each
surface by the share of ambient light that cannot reach it, each direction
weighed by its cosine with the surface normal.
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
  *Decided 2026-11-17, provisionally (the maintainer confirms at review): the
  frame neither casts nor receives.* A line 2 CSS px wide is under one texel
  of a 512-texel map at every framing measured, so casting it would change
  nothing visible while tying the maps to the framing, and a line is drawn
  flat, with no ambient term to scale.
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

## Non-goals

- Ambient occlusion in the SVG (WP-1536). Darkening per pixel has no vector
  form.
- Cast shadows from the key light, depth of field, perspective. A ray
  tracer gives them through WP-1537.
- Changing the default look. D6.

## Tasks

- [x] Ask for Tarini, Cignoni & Montani (2006), and read it before fixing
  D2's constants (2026-11-17: requested; it is closed access
  and was not read. D2's constants were measured instead, and reading it
  went to #1647).
- [x] The depth-map pass and the lookup in the numpy path, with unit tests:
  an isolated atom is unoccluded everywhere, and a point between two touching
  atoms is darker than the far side of either (2026-11-17:
  `raster.occlusion_maps` builds each map as an `id_plane` along the light
  and reads the depth back from the ids, so the maps are the same on either
  tier; `raster.occlusion` weighs each direction by its cosine).
- [x] The numba kernel, held bit-identical to the numpy path (2026-11-17:
  superseded. WP-1940 deleted the numba twin and ported the rasteriser to
  `kernels/src/raster.rs`, so this is a kernel in a minor wheel release. Until
  one lands the occluded picture is drawn on the numpy path on either tier,
  from maps the tier's own `id_plane` builds, so the two tiers agree on the
  bit (`test_the_two_paths_draw_the_same_bits_in_any_banding[occluded]`).
  The kernel went to #1647).
- [x] `ambient_occlusion=` on `render_structure`, with D5's cache. Measure
  the cost at 1000 px and 3000 px on the 21 phases. Quote ranges (2026-11-17,
  `1538-measure/results.txt`: the maps 0.06-0.53 s a scene; occluded
  0.36-2.51 s at 1000 px and 2.39-15.68 s at 3000 px against 0.01-0.15 s and
  0.05-0.31 s plain on the wheel, the occluded picture being drawn on the
  numpy path until a kernel draws it).
- [x] Before-and-after pairs on the 21 phases in ball and ellipsoid mode,
  committed under `docs/wp/1538-measure/`. Decide D4 from them (2026-11-17:
  `1538-measure/pairs/`, looked at; D4 stands, the faces casting and
  receiving nothing, since no pair shows a face that would read better
  darkened and a cast face would darken its own centre atom).
- [x] The GUI: the depth passes and lookup in `gl3d.ts`, the toggle, and a
  parity case with occlusion on. Check that rotation stays smooth on the
  largest corpus scene, since the maps are built once a scene (2026-11-17:
  the solids' own shaders write a `DEPTH_COMPONENT32F` texture array under
  `uShadow`; parity 1.13 levels, and 11.97 levels of darkening on both sides
  away from the edges; on garnet, 383 atoms, headless chromium's CPU
  rasteriser drew a rotation frame in 33-42 ms with it off and on alike, and
  the maps with their first frame in 77-81 ms).
- [x] Docs: the `render_structure` docstring and the GUI guide's structure
  section.
- [x] Tests + figure pairs to `tests/output/figure3d/`
  (`ambient_occlusion_{ball,ellipsoid}.png`, `parity_*_occluded.png`).
- [x] Skill: one clause in `api-figure.md` saying the option darkens ball
  mode and barely touches ellipsoid mode, tagged with this WP's
  measurement (2026-11-17: superseded in part by the measurement, which
  found ellipsoid mode's atoms losing about 0.6 of what ball mode's do, the
  sticks shading them, so the clause says that).

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

### 2026-11-17 — built in both renderers; the look choices wait on the maintainer

A structure figure can now be drawn with ambient occlusion: each atom and stick is darkened
by the share of ambient light its neighbours keep from it, read from 64 depth maps of the
scene. `render_structure` and the GUI viewer draw the same picture with it on, and it stays
off by default. It shows on every phase measured, more than the filing expected in
ellipsoid mode: there the sticks a small ellipsoid meets shade it, so its atoms lose about
0.6 of what ball mode's do, where the filing estimated almost nothing from atoms alone. It
is cheap in the GUI, where the maps are built once a scene and a rotation costs no more than
before. In Python it is slow at print sizes, because no compiled kernel draws it yet.

**Waits on the maintainer** (the look choices, as 1548's were confirmed): (1) D2's constants
as shipped, 64 directions, 512-texel maps, a bias of 0.01 of the map's width, chosen from the
measurement below rather than from Tarini et al., which is closed access and was not read;
(2) D4 as filed, the faces casting and receiving nothing, after looking at the 21 pairs;
(3) D5's frame question, decided provisionally above (the frame neither casts nor receives);
(4) the GUI label `ambient occlusion` under `drawing`. Turning it on by default (D6) is #1647's,
with the kernel and the paper.

- **Done:** `raster.occlusion_maps` (one `id_plane` per direction along the light, the depth
  read back from the ids so both tiers build the same maps) and `raster.occlusion` (each
  direction above the tangent plane weighed by its cosine, nearest texel, the bias);
  `_shade(occ=)` scales the ambient term only (D3); `draw(occlusion=)` runs `_band_numpy` on
  either tier. `render_structure(ambient_occlusion=)` with the recipe key. The constants are
  `scene.LOOK`'s, so the scene corpus holds them equal to the GUI's, and the corpus now also
  carries the 64 directions and their map bases, which `structure3d.test.ts` replays.
  `gl3d.ts`: the atom and stick shaders write the maps under `uShadow` into a
  `DEPTH_COMPONENT32F` texture array, built at the first frame that needs them for a scene,
  and read them in `occlusion()`; a failed allocation draws without occlusion; the maps are
  freed when the toggle goes off. The drawer's `ambient occlusion` box. Docs: the
  docstring, the GUI guide, the skill's `api-figure.md` clause (rewritten to the measurement:
  ellipsoid mode about 0.6 of ball mode, not "barely"). Inherited pruned: both 1940 entries had landed
  (the numba twin is gone, `raster.rs` exists), so the numba task became the kernel task and
  went to #1647 with the paper and the default. The paper is Tarini, M., Cignoni, P. & Montani, C. (2006), *IEEE Trans. Vis.
  Comput. Graph.* 12(5), 1237-1244, <https://doi.org/10.1109/TVCG.2006.115>, requested.
- **Measured** (arm64 Mac, `[dev]` venv, wheel loaded; `1538-measure/results.txt`): 1 − A over
  atom pixels of the opening view, mean, ball 3.1-25.1 %, ellipsoid 3.1-24.5 % (0.28-1.07 of
  ball's, median 0.6); sticks 3.3-38.7 %. Map size 256/512/1024 moves the ball mean by
  ≤ 0.1 %, bias 0.005-0.02 by ≤ 1.6 %. Cost: maps 0.06-0.53 s; occluded 0.36-2.51 s at 1000 px
  and 2.39-15.68 s at 3000 px, against 0.01-0.15 s and 0.05-0.31 s plain on the wheel.
  Browser parity (headless chromium, SwiftShader, 507 × 300): 1.13 levels with occlusion on
  (bar 2.0); away from the antialiased edges 1.5 levels from Python's occluded picture against
  11.6 from its plain one, and 11.97 levels of darkening on both sides. Rotation on garnet
  (383 atoms drawn): 33-42 ms a frame off and on alike, maps and first frame 77-81 ms.
- **Tests:** +7 in `test_render_structure.py` (directions, isolated atom, touching pair, D3
  shade, both modes darken; the `occluded` bit-identity row and the recipe row), +1 parity
  case in `test_structure3d_browser.py` (skips where playwright or chromium is missing, so in
  CI), +1 vitest. Fast suite on the workstation at `8ea887b5e` (main `bc77a934e` merged in;
  Linux, its `rietx-py312` venv over the tree's `src`, `-n 4 --dist loadgroup -m "not slow"`):
  14866 passed, 280 skipped, 32 xfailed, 0 failed in 914 s (a `-n 8` run was memory-paused
  three times by co-tenants and stopped). The added tests cost 1.64 s in that run, the
  slowest 1.32 s (`test_ambient_occlusion_darkens_both_modes_and_is_off_by_default`), so none
  joins the slow tail. Vitest 796 passed, svelte-check 0 errors, Vale 0 errors,
  `tests.reader_output` exit 0 (unchanged). The full selection was not run: the option is off
  by default and moves no measured number.
- **Review:** a read-only reviewer found no correctness bug; transforms and texel addressing
  were checked numerically. Its two GL risks (an unchecked 64 MB allocation, maps kept when
  off) and four nits (a wrong memory comment, two docstrings out of step with the
  measurement, `intp` indices) were all fixed in `777134069`.
- **Generality:** not dispatched. The audit table is untouched, `viz` is in `NOT_WALKED`, and
  the session added no heuristic: the option is off by default, and its constants are drawing
  values.
- **Gotchas:** the browser parity row needs playwright and a chromium; with neither cached
  here, `PLAYWRIGHT_BROWSERS_PATH` pointed at a scratch install and `PLAYWRIGHT_CHROMIUM` at
  its binary. In WebGL the map texture must be unbound from its unit while it is the depth
  attachment, or the draw is refused as a feedback loop.
- **Next:** the maintainer's four answers above, then close (✅) with the record entry; any
  change of constant moves `LOOK` on both sides and the corpus. After that, #1647: the kernel
  first, since it is what makes the option usable at print size.

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

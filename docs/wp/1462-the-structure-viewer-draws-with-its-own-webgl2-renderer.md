# WP-1462 — the structure viewer draws with its own WebGL2 renderer

Milestone: unscheduled · Status: ✅ 2026-09-26 — the viewer draws with its own renderer; the GPU gate passed as partial, on software drivers
Track: Render what the fit already knows
Depends on: 1461 (soft)

## Goal

The GUI's 3D structure viewer leaves plotly. No page the GUI serves loads
plotly.js, and the `gui` extra names no plotly. Everything the viewer
shows and does today survives, and its crystallography rules in
`gui/CLAUDE.md` stand unchanged.

*Narrowed 2026-09-25.* The goal first said no page rietx serves loads plotly
and `pyproject.toml` names it nowhere. Two users of plotly are outside this
WP: `rietx compare` and `viz.html.write_html`, which writes a plotly page
from Python. Both keep it through the `viz` extra until WP-1461's last two
tasks move them to uPlot and take plotly out of that extra.
*Superseded 2026-09-26:* WP-1461 closed with both moved, and
`pyproject.toml` names plotly nowhere. The first goal holds whole.

The file was filed recommending three.js as
`1462-the-structure-viewer-draws-with-threejs.md`. The maintainer chose a
renderer of our own (D1), and the file took its title's name on
2026-09-26, once WP-1461 had closed.

## Context

### What the viewer is

WP-1015 built the viewer and its second pass set its look
(`gui/CLAUDE.md`, the structure viewer paragraphs). Its founding rule is
that everything hard stays on the server. `GET /api/structure3d`
(`src/rietx/gui/structure3d.py`) sends Cartesian positions, 3×3 matrices and
index pairs. The browser's whole job is `pos + T·v` over one unit sphere,
which is also why a ball and an ellipsoid are one code path.

The browser half is `gui/src/panels/Structure3D.svelte` (507 lines) and
`gui/src/lib/structure3d.ts` (701 lines), tested by `structure3d.test.ts`
(435 lines) and `tests/test_structure3d.py`. It draws, through plotly:

- atoms as one `mesh3d` per species, each atom the unit sphere under its
  own transform, in Å;
- bonds as two-tone cylinders in Å, one `mesh3d` per species, where a half
  belongs to its atom;
- the cell as `scatter3d` lines in `--accent`, and the a, b and c labels as
  `scatter3d` text at a clearance set by the largest ball;
- a parallel projection, a free trackball (`dragmode: "orbit"`), and a
  light that rides the camera.

And it does:

- ball or ellipsoid mode, and a phase picker;
- a legend whose buttons hide a species, its bond halves included;
- buttons that look down a, b or c, and a reset;
- knobs for the ellipsoid probability, an exaggeration factor and the bond
  tolerance, the last a server round trip;
- hover text per atom (`atomLabel`: label, species, fractional position,
  occupancy, RMS displacements, image outside the cell) and per bond (the
  two site labels and the length in Å);
- a PNG of the scene, plotly's modebar `toImage` and the only button kept;
- the view kept across every redraw, and a `ResizeObserver` size.

### What plotly costs it

The viewer mounts hidden inside the Model panel at boot
(`Model.svelte:455`), so today it is one reason the GUI evaluates plotly
at every open: a 700-811 ms long animation frame (WP-1461,
`1461-uplot-spike/results/gui_td.txt`). WP-1461 defers that load to the
viewer's first show. After WP-1461, this viewer is the only thing that
loads plotly, and the only reason the `gui` extra depends on it.

Several of the viewer's rules exist only because of plotly:

- `react` with fresh trace objects resets the gl3d camera, so the view is
  read back from `gd._fullLayout.scene._scene.getCamera()` before every
  draw, since `layout.scene.camera` reports only what was passed in and
  `plotly_relayout` never fires for a gl3d camera drag;
- `dragmode: "orbit"`, because turntable rewrites any camera whose `up` is
  not +z;
- `responsive: true` hears window resizes only, so a `ResizeObserver`
  calls `Plots.resize`;
- `scatter3d` markers and lines are sized in pixels, so every shape is a
  `mesh3d`.

### How big the scenes are

`structure3d.MAX_ATOMS` = 400 and `MAX_BONDS` = 4000 bound every scene. The
three payloads the spike drew hold 116 to 173 atoms and 174 to 255 bonds
(`1462-spike/payloads.py`: LaB6, NAC with its anisotropic tensors, and
fluorapatite). Any renderer draws that at 60 frames a second. So speed
does not separate the candidates. Load size, the look and the code we own
do.

### The field, measured

Measured 2026-09-25 by `1462-spike/measure.mjs`
(`results/sizes.txt`). Each row bundles the imports a viewer would use,
with esbuild 0.28.2 `--minify`, then `gzip -9`.

| Library | version, licence, upkeep | minified | gzip |
|---|---|---|---|
| plotly.js, as today | Python `plotly` 7.1.0, MIT | 4.82 MB | 1.47 MB |
| NGL | 2.5.0, MIT | 1329 KB | 377 KB |
| three.js, `three/webgpu` | 0.186.1, MIT | 791 KB | 216 KB |
| 3Dmol.js, whole ESM build | 2.5.5, BSD-3-Clause | 587 KB | 169 KB |
| three.js, the 17 imports D1 named | 0.186.1, MIT | 557 KB | 139 KB |
| three.js, renderer and one custom shader | 0.186.1, MIT | 545 KB | 137 KB |
| regl | 2.1.1, MIT, no release since 2024-11 | 123 KB | 41 KB |
| uPlot, for scale | 1.6.32, MIT | 52 KB | 23 KB |
| OGL, scene graph with orbit and raycast | 1.0.11, Unlicense, last release 2025-01 | 63 KB | 19 KB |
| PicoGL.js | 0.17.9, MIT, last commit 2022 | 66 KB | 15 KB |
| twgl.js | 7.0.0, MIT, maintained | 41 KB | 14 KB |
| the spike's prototype renderer | no dependency | 11 KB | 4.8 KB |

The three.js rows show where its size lives. Swapping the stock materials
and lights for one custom shader saves under 3 KB of 139 KB, because
`WebGLRenderer` carries its whole material system.

The rows fall into three tiers. The general engines (three.js, and Babylon.js
and PlayCanvas, which are larger) carry a scene graph, materials and
controls. The thin helpers (twgl.js, OGL) wrap WebGL's program and buffer
calls and are uPlot's size. The molecular viewers own a model of atoms,
bonds and styles. Only Mol\* (5.11.0, MIT) among maintained browser
libraries was found to draw displacement ellipsoids, from its own mmCIF
tensor reader. JSmol draws them too, at 18-20 MB and LGPL. Both would take
the crystallography back from the server, against WP-1015's founding rule.
matterviz (MIT, Svelte 5, three.js through threlte) draws no displacement
ellipsoids, and ChemDoodle Web's free tier is GPLv3. This paragraph comes
from a survey agent's reading of each project's source and docs, and none
of it was measured here.

### What the molecular viewers do

The fast molecular viewers draw an atom as a ray-cast impostor: Mol\*,
NGL, VMD, QuteMol and speck. One screen-aligned quad stands for each atom
or bond. The fragment shader solves the sphere, cylinder or ellipsoid
exactly along the pixel's ray, discards a miss, and writes the hit's depth
through `gl_FragDepth`. The surface is exact at every zoom, and a scene
costs four vertices per primitive (Sigg et al. 2006; Gumhold 2003; Tarini
et al. 2006). A parallel projection makes it simpler still, since every ray
has the same direction.

Mol\* picks by rendering primitive ids to an offscreen buffer and reading
one pixel. That is needed when a surface exists only in a shader. Here the
browser holds each atom's position and T, so the CPU can solve the same
quadric for the pixel under the pointer.

Two platform facts bound the choice. WebGL2 is universal in the three
engines the GUI supports, and `gl_FragDepth` is core in it. WebGPU is not
yet universal: Firefox ships it on Windows since 141 and on Apple silicon
macOS since 145, with Linux still in progress.

### The prototype

`1462-spike/viewer.js` draws the served payload unchanged, as ray-cast
quadrics. It is 392 lines with no dependency.

- **Atoms.** One instanced quad per atom, sized to the exact projected
  extent of the ellipsoid (the norms of the first two rows of R·k·T). The
  fragment shader solves |(k·T)⁻¹(p − c)| = 1 along the view ray. A ball
  is k·T = r·I, so ball and ellipsoid stay one code path.
- **Principal ellipses.** `structure3d._ellipsoid` returns
  T = V·diag(√λ), so T's columns are the principal axes. A principal
  ellipse is then one unit-frame coordinate near zero, three lines of
  shader. ORTEP draws these rings (Johnson 1965). The viewer has never had
  them. `shots/nac-rings.png` shows them on NAC at 2.5× exaggeration.
- **Bonds.** One quad per bond half, solved as a finite cylinder, coloured
  by the atom the half leaves.
- **The rest.** The cell as `gl.LINES`, the a/b/c labels as DOM text, a
  trackball, wheel zoom, CPU picking and a PNG through `toDataURL` in the
  drawing task.
- **Degenerate tensors.** A zero semi-axis has no inverse, so the prototype
  draws it at 1 mÅ. The server's rule stands: the axis still reads as zero.

Measured 2026-09-25, playwright-core 1.63.0, headed, devicePixelRatio 2, on
an Apple M4 shared with other sessions (load average up to 48). Three runs
(`results/proto_run0.txt` to `proto_run2.txt`):

| | Chromium 1223 | Firefox 1543 | WebKit 2359 |
|---|---|---|---|
| data to first frame, first page | 78-265 ms | 33-101 ms | 145-1643 ms |
| data to first frame, later pages | 23-55 ms | 29-97 ms | 22-47 ms |
| draw call, main-thread work per frame | p95 0.1-0.2 ms | p95 ≤ 1 ms (1 ms timer) | p95 ≤ 1 ms (1 ms timer) |
| frame gap during rotation, p95 | 17.5-17.6 ms | 17-33 ms | 17-22 ms |
| hover pick, per event | 12-24 µs | 14-61 µs | 14-26 µs |
| errors | none (a favicon 404) | none | none |

The first page's cost is the browser's first WebGL context and shader
compile. It moved from 1643 ms to 145 ms between runs on WebKit, so it is
the machine's state as much as the page's. It applies to plotly's viewer
too, and only a paired measurement separates them. The three engines drew
the same picture: a mean absolute difference of 0.07 and 0.02 levels of 255
against Chromium (`shots/engines-nac.png`). Headless Chromium runs on
SwiftShader, the CPU rasteriser `tests/test_gui_browser.py` gets, and drew
the same scenes. No CI workflow installs playwright, so no browser test
runs in CI.

The prototype lacks the legend, the a/b/c buttons, the knobs, bond hover,
theme colours and context-loss handling. A full viewer is estimated at
700 lines and under 10 KB gzip.

### Polyhedra

The maintainer asked for a polyhedral view on the same day, because many
users will be solid-state chemists. The spike added one to test whether it
moves D1. `payloads.py` stands in for the server. It reads each centre's
shell off the bond segments, takes the convex hull with scipy, and sends
vertices, outward-wound triangles and edges. `viewer.js` draws them as
ordinary triangles after the opaque impostors: depth-tested against them,
writing no depth, blended at alpha 0.55. Each frame orders the polyhedra
farthest first by centroid and draws each one's back faces before its
front faces.

- **The renderer part is small.** It is 88 lines, taking the prototype to
  480 lines, 13.3 KB minified and 5.5 KB gzip (`results/sizes_poly.txt`).
  NAC's 26 polyhedra (AlF₆ and CaF₈) drew the same in the three engines, a
  mean difference of 0.016 and 0.009 levels of 255
  (`shots/engines-nac-poly.png`). A frame's draw call stayed at p95 0.3 ms
  in Chromium and the frame gap at p95 17-18 ms in all three
  (`results/proto_run3_poly.txt`, load average 43).
- **The ordering is right while polyhedra do not interpenetrate.**
  Coordination polyhedra share corners, edges or faces and never overlap in
  volume, so ordering whole polyhedra works. If artefacts appear,
  weighted blended order-independent transparency needs no ordering at all
  (McGuire & Bavoil 2013). three.js also orders transparent objects whole
  and ships no order-independent mode, so it gains nothing here.
- **The rest is chemistry, and it is WP-1466's.** The spike also met the
  ligand rule, shells matched by position, the hull's coplanar faces and
  the shell measurements behind the polyhedra defaults. All of it is
  server-side, and WP-1466 carries it.

## Decisions this WP takes

The maintainer confirmed D1-D8 on 2026-09-25 and asked for a critical pass
over all of them, against what VESTA, Mol\*, ChimeraX and the others do. That
pass changed D5 and D6 and added D9. Its sources are a survey of those
programs' manuals and docs, and Daams & Villars (1993) for the coordination
shell.

- **D1. The viewer draws its own quadrics in WebGL2, with no library.**
  *Stands.* It follows the practice of Mol\* and NGL, measured above at
  4.8 KB gzip against three.js's 139 KB, and needs no Dependabot entry,
  licence row or bundle pin. The pass found two costs. The code is ours,
  about 1000 lines once export and context loss are in. And no candidate
  gives a vector export: only VESTA offers one (EPS, PDF, SVG), and a
  scene of impostors has no triangles to write. A vector export would
  project the same ellipses and cylinders onto a 2D canvas, depth-sorted,
  and is out of scope here. **Fallback:** three.js, bundled and pinned, if
  the renderer fails on a GPU the spike has not met.
- **D2. The payload does not change.** *Stands.* The prototype drew it as
  served. `structure3d.ts` keeps its pure half (`atomTransform`,
  `atomLabel`, `legend`, `caption`, `stickRadius`) and gains the view
  arithmetic. The plotly trace builders and the tessellation go.
- **D3. The a, b and c labels are a DOM overlay.** *Stands.* Text stays
  crisp and takes the theme. One consequence is D5's: the labels are not
  in the WebGL canvas, so the export draws them itself.
- **D4. Hover solves the quadric on the CPU.** *Stands.* 12-61 µs an event
  at 116 to 173 atoms. Mol\* renders ids to a buffer because its surfaces
  exist only in shaders. Here the browser holds every atom's position and
  T, so the CPU solves the same equation. Bond halves are picked the same
  way, as finite cylinders.
- **D5. PNG export is a render of its own, larger than the screen.**
  *Revised.* Today's export is plotly's `toImage` at scale 1, the size of
  the panel. VESTA multiplies the view by a scale factor, ChimeraX
  supersamples 3× by default, and Mol\* offers presets up to 3840×2160.
  The export renders offscreen with its long side at 3000 px, enough for a
  17 cm figure at 300 dpi with margin. It is multisampled, and capped by
  `MAX_RENDERBUFFER_SIZE` and `MAX_VIEWPORT_DIMS`. Line widths and the
  a/b/c labels scale with it, so the picture matches the screen. The
  background is the screen's. A transparent background, which VESTA, Mol\*
  and ChimeraX all offer, is a second button. Impostors make the larger
  render exact: nothing is tessellated, so nothing needs refining.
- **D6. Anisotropic sites show their principal ellipses in ellipsoid
  mode.** *Stands, with a fix.* On NAC's dark violet Na the dark ring
  vanished into the atom. The ring ink is darkened on a light atom and
  lightened on a dark one. Rings stay off isotropic sites, whose T axes
  are arbitrary and would claim an orientation that is not there. The
  octant cut-out stays out (Non-goals).
- **D7. Silhouettes are antialiased in the shader.** *Stands.* Coverage
  comes from the ray's discriminant, through alpha-to-coverage on a
  multisampled canvas. The export gets the same at its own resolution.
- **D8. The polyhedral view is WP-1466, filed to follow this one.**
  *Stands.* § Polyhedra showed it fits D1 as one more pass, so nothing here
  is built for it. The pass moved its defaults and they live in that file
  now. Its shell rule follows Daams & Villars (1993) and the maximum-gap
  method they apply, and its look and its choice of centres follow VESTA
  and Mercury.
- **D9. Lines are screen-space quads with a width in CSS pixels.**
  *New.* The cell frame is 2 px today, and `gl.LINES` draws one device
  pixel. That is 0.5 CSS px at devicePixelRatio 2, and a hairline in a
  3000 px export. Each edge is an instanced quad extruded across its
  projected direction, depth-tested like the atoms. Its width scales with
  the device and the export. This retires the "one pixel wide" risk below.

## Where it will bite

- **A WebGL context is a scarce resource.** Browsers keep about 16 live
  contexts a page and silently drop the oldest past that. The viewer keeps
  one context for its life and releases it on unmount. Today it disconnects
  its `ResizeObserver` and nothing else, and never calls `Plotly.purge`, so
  toggling the viewer may already leak a context. The spike counts contexts
  across toggles.
- **A lost context must come back.** `webglcontextlost` and
  `webglcontextrestored` rebuild the programs and buffers from the payload
  already held.
- **No vendor GPU off Apple has drawn it.** On 2026-09-26 the gate
  (`1462-spike/gate.py`, `results/gate_ci.txt`) ran on GitHub's Windows and
  Linux runners, which have no GPU. Their drivers are software ones:
  Direct3D 11 over WARP through ANGLE (Chromium, WebKit), Mesa llvmpipe
  (Chromium through ANGLE's GL backend, Firefox, WebKit) and SwiftShader
  (Chromium's default). So ANGLE's translation to HLSL and to GLSL is
  covered, but no NVIDIA, AMD or Intel driver is. `gate.py run` on such a
  machine, compared with `results/gate_payload_mac.json` replayed, is
  the one command that closes it. The maintainer dragged the GUI's 2D
  charts in real Safari on 2026-09-26 and they worked. The viewer's own
  drag was not part of that report.
- **A context with no multisample buffer draws aliased silhouettes.**
  D7's coverage goes through alpha-to-coverage, which needs samples.
  Firefox on WARP granted `antialias: false`. The picture is otherwise the
  reference's, and 96 % of its differing pixels lie on an edge. The export
  renders into its own multisampled buffer and stayed smooth there.
- **A browser that blocks WebGL2 gets the viewer's message.** Firefox's
  default on WARP refuses WebGL2, and the panel said "this browser has no
  WebGL2" with no knobs, as designed.
- **jsdom has no WebGL.** vitest covers the pure half: the projected
  extents, the pick, the trackball and the instance data. A stand-in
  records what was asked to be drawn, as `gui/src/test-uplot.ts` does for
  uPlot. A browser test covers the drawing, and it reads back pixels or
  compares pictures, never a hash of a screenshot (`gui/CLAUDE.md`: a WebGL
  re-render differs by a pixel).
- **An export is a large buffer.** 3000 × 2500 pixels at 4 samples is
  about 240 MB of colour and depth while it renders. The export frees it
  at once, and falls back to fewer samples, then a smaller size, when the
  allocation fails.
- **plotly outlives this WP until the Series panel leaves it.**
  `panels/Series.svelte` still draws with plotly. The `/plotly.js` route,
  `lib/plotly.ts` and the `gui` extra's plotly go with whichever of this WP
  and WP-1461's Series task lands second. *Done 2026-09-25*, in this WP's
  third session.
- **The camera is owned outright.** The renderer keeps the camera between
  draws, so the read-back rule above goes. A redraw must still not reset
  the view, and a test says so.

## Non-goals

- **A new look,** beyond D6. The second pass's choices carry over: parallel
  projection, no axis box, cylinders in Å, a/b/c labels and the light on
  the camera.
- **New structure features:** a packing diagram, labels on atoms, the
  octant cut-out, depth cueing, ambient occlusion, animation of a
  refinement. Each is an addition on D1 and a WP of its own. Polyhedra are
  D8's.
- **WebGPU.** Firefox on Linux does not ship it yet.
- **A vector export** (D1), and DPI metadata in the PNG. The pixel count is
  what a journal checks.
- **Any other chart.** 2D charts are WP-1461's.

## Tasks

- [x] The maintainer confirms D1-D8 (2026-09-25); the critical pass revises D5 and D6 and adds D9; WP-1466 is filed for D8
- [x] Spike, the gate: the renderer on the GPU paths the prototype has not met (any Windows or Linux machine the maintainer can reach), and paired against today's plotly viewer on the same machine: first show, rotation frames and hover work per event, in Chromium, WebKit and Firefox. Record go or no-go in the handover. On no-go, draw the same payloads with three.js before stopping. *Closed as partial 2026-09-26, by the maintainer's choice:* go on the software drivers of GitHub's Windows and Linux runners, with no vendor GPU (§ Where it will bite). The timings were not repeated there, since a software rasteriser's times measure the rasteriser, so the Mac's paired runs stand.
- [x] The renderer: instanced atom and bond-half impostors, D9's line quads for the cell frame, the a/b/c overlay, the orthographic camera, the trackball, the light on the camera, theme colours, boundary images dimmed, D6's ellipses, D7's antialiasing, context loss, and release on unmount
- [x] Interaction: hover on atoms and bond halves, legend toggles, the a/b/c and reset views, pan and zoom, the three knobs, the view kept across redraws, and `ResizeObserver` sizing
- [x] Export (D5): the offscreen render at a 3000 px long side, multisampled, lines and labels scaled, on the screen's background and on a transparent one
- [x] Leave plotly in the viewer: the trace builders, the tessellation, the camera read-back and the modebar. The `/plotly.js` route, `gui/src/lib/plotly.ts`, the `gui` extra's plotly, `viz/plotlyjs.py`, `lib/plot.ts:hoverLabel` and the `Plotly` stand-in in `test-setup.ts` go only if the Series panel has left plotly too. It had, so they went on 2026-09-25 and the `gui` extra is empty; `viz/plotlyjs.py` stays for `rietx compare`.
- [x] D6's rings on a tensor whose principal axes are not all fixed. The gate found four of NAC's six sites with two equal principal values. Three sit on a threefold axis, and Ca1's file gives U11 = U33 on a twofold. `eigh` places their two free axes per LAPACK build. The Mac draws Na1's rings as an X and an x86 runner as a +, while T·Tᵀ agrees to 2e-17 (`1462-spike/shots/gate-uniaxial-rings.png`). *Decided 2026-09-26:* ORTEP-III, PLATON and Jmol draw all three rings on every anisotropic site, wherever their solver puts the axes, and no manual or paper names a tie-break (a survey, with Jmol's `EllipsoidsRenderer` read here). The maintainer chose that practice, made stable: `structure3d._pin_axes` fixes each sign, turns a free pair so one ring's plane holds the lattice vector nearest it, and gives a sphere the orthonormalised lattice. It pins each site once and turns that T by every image's Cartesian rotation, so equivalent atoms wear equivalent rings (the review's finding: pinned image by image they sat up to 60° apart). The x86 runners' own vectors, pinned, land on the Mac's to 5.6e-17 Å.
- [x] Rename this file to its title once WP-1461 has closed, with its ROADMAP row and WP-1461's two links
- [x] Tests: `structure3d.test.ts` on the pure half and the instance data; a WebGL stand-in beside `test-uplot.ts`; a browser test that reads pixels at known atoms, finds a principal ellipse on an anisotropic site, and asserts a redraw keeps the view; a test that no page requests `/plotly.js`
- [x] Docs: the structure viewer paragraphs in `gui/CLAUDE.md` (crystallography rules kept, plotly traps deleted), `using/install.md` for the `gui` extra, ATTRIBUTION.md, and the root CLAUDE.md's GUI lines if they name plotly. On the three.js fallback also: its row in `.github/dependabot.yml`'s allow list (WP-1461 created it) and its licence text in `LICENSE-3RD-PARTY.md`.

## Acceptance

Measured like WP-1461's § Acceptance: the spike driver ported to the real
page, paired with the plotly viewer on the same machine and load, three or
more runs for ranges, recorded in the handover.

1. **No plotly in the viewer.** Showing the structure viewer requests no
   `/plotly.js`. Once the Series panel has left plotly too, the GUI's route
   is gone and the `gui` extra names no plotly (narrowed 2026-09-25, § Goal).
2. **First show:** no long animation frame is attributed to the renderer.
   The time from the viewer's first show to its first frame is recorded
   beside plotly's.
3. **Rotation:** on the largest example structure, a trackball drag holds a
   p95 frame of 17.7 ms or less with zero long animation frames. Hover work
   per event is recorded.
4. **Size:** the renderer adds under 15 KB gzip to the GUI bundle, or
   three.js's measured size on the fallback.
5. **Coverage:** every item in § What the viewer is is present and named by
   a test.
6. **Browsers:** in Chromium, WebKit and Firefox through playwright's
   builds, the viewer draws, rotates and hovers, and nothing throws.

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Sigg, C., Weyrich, T., Botsch, M. & Gross, M. (2006). GPU-based
  ray-casting of quadratic surfaces. *Eurographics Symposium on
  Point-Based Graphics*.
- Gumhold, S. (2003). Splatting illuminated ellipsoids with depth
  correction. *Vision, Modeling and Visualization 2003*, 245-252.
- Tarini, M., Cignoni, P. & Montani, C. (2006). Ambient occlusion and edge
  cueing for enhancing real time molecular visualization. *IEEE Trans.
  Vis. Comput. Graph.* 12, 1237-1244.
- Johnson, C. K. (1965). ORTEP: a Fortran thermal-ellipsoid plot program.
  Report ORNL-3794, Oak Ridge National Laboratory. Burnett, M. N. &
  Johnson, C. K. (1996), ORTEP-III, ORNL-6895, for the principal ellipses
  and the octant convention.
- McGuire, M. & Bavoil, L. (2013). Weighted blended order-independent
  transparency. *Journal of Computer Graphics Techniques* 2(2).
- Rose, A. S. & Hildebrand, P. W. (2015). NGL Viewer: a web application for
  molecular visualization. *Nucleic Acids Res.* 43, W576.
- three.js 0.186.1, MIT. <https://github.com/mrdoob/three.js>
- 3Dmol.js 2.5.5, BSD-3-Clause. Rego, N. & Koes, D. (2015). 3Dmol.js:
  molecular visualization with WebGL. *Bioinformatics* 31, 1322-1324.
  <https://github.com/3dmol/3Dmol.js>
- Mol\* 5.11.0, MIT. <https://github.com/molstar/molstar>
- plotly.js, MIT, as served by the Python `plotly` 7.1.0 package.
- VESTA, Momma, K. & Izumi, F. (2011). *J. Appl. Cryst.* 44, 1272-1276.
  The viewer's second pass read its look against VESTA, Jmol and 3Dmol.js.
- WP-1015 (the viewer) and WP-1461 (every 2D chart on uPlot).
- `1462-spike/README.md`: the files and how to rerun them.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

## Defaults

**Every choice the GUI offers ships a default that suits most phases, and a
setting is for the rest** (the maintainer's rule, recorded in WP-1462). A user
who never opens a drawer sees the conventional picture, such as ellipsoids at
50 % and bonds at 1.15×(rᵢ+rⱼ). A default
is measured across phases and the measurement is kept where the choice is
made. A setting most users would change means the default is wrong.

The **renderer** (WP-1462) draws a `Scene` from a `View`, both built by pure
functions in `structure3d.ts`, and knows nothing else. Eight rules.
**Every atom and bond half is a ray-cast quadric** on one instanced quad, exact
at any zoom and export size (the practice of Mol\* and NGL; WP-1462 § The field).
**Hover solves the shader's own equations on the CPU** (`pickAtom`, `pickHalf`,
12-61 µs an event), and says what it hit in a readout line under the canvas,
WP-1213's rule for the pattern carried over. **An impostor's outline is a
`discard`, which MSAA does not smooth**, so each shader computes its coverage
and hands it to alpha-to-coverage — which writes coverage into the samples, so
**the canvas is opaque**, cleared to the panel's own background, and a
**transparent export renders twice**, on black and on white, taking alpha from
the difference. **A line is a quad with a width in CSS pixels** (`gl.LINES` is
one device pixel: half a CSS pixel at DPR 2, a hairline in an export). **The PNG
is a render of its own**, offscreen at `EXPORT_LONG_SIDE` = 3000 px and
multisampled, and the a/b/c letters, which are DOM on screen, are drawn into it.
**One context for the canvas's life**: the mount effect depends on the canvas
and nothing else, calling `rebuild` under `untrack` — called bare, it read the
geometry, every payload re-ran the effect, and its cleanup's `loseContext` left
the canvas holding a dead context that drew Chrome's sad face (jsdom's stand-in
loses nothing, so `test-gl3d.ts` now counts a renderer made on a dead canvas).
**Firefox presents the first frame only after compiling the shaders**, some
hundreds of ms after the draw call, so a first-show number is read off
screenshots, never off the call. And **faces blend, never through coverage**,
whole polyhedra back to front; only a translucent export pixel proves a face
painted (WP-1466). Under test, `test-setup.ts` mocks
`lib/gl3d`'s `createRenderer` with `test-gl3d.ts`, which records every scene
and view; `--line` is invisible in a 3D scene, so the cell frame takes
`--accent`; and pictures are compared, never a sha256 of one.
**The scene rules have a Python twin** (WP-1470): `rietx.viz.figure3d.scene` ports
`buildScene`, `shownPolyhedra`, the views and `LOOK`, held equal by
`tests/data/gui/scene_cases.json`, which `test_render_structure.py` writes and
`structure3d.test.ts` replays, so a rule changed here changes there in one commit.

## Handover log

### 2026-09-26 (4th session) — renamed, the GPU gate passes as partial, and the WP closes

The structure viewer has now drawn on Windows and Linux as well as on Apple
hardware, and this WP is closed. GitHub's runners have no GPU, so the check ran
on three software drivers. There the pictures matched the Mac's, so the
renderer stands and three.js is not needed. The check also found that a site
displacing equally in two directions drew two of its rings at an angle that
depended on the machine. The viewer now fixes that angle to the lattice. This
follows ORTEP and Jmol, and adds the tie-break they lack. No NVIDIA, AMD or
Intel driver has drawn the viewer yet.

*Done.*
- The file took its title's name, with the ROADMAP row, WP-1461's two links
  and the spike README. The Inherited entry was pruned on arrival. The rename
  it announced is this session's, and its Safari note moved beside the GPU
  risk in § Where it will bite. The goal's 2026-09-25 narrowing is marked
  superseded, since `pyproject.toml` names plotly nowhere now.
- `1462-spike/gate.py` is the gate's probe. `run` drives the real viewer in
  one browser configuration, with its canvas lifted over the page at 720 × 540
  CSS px. It records the GL driver, seven screenshots, both exports, a lost
  and restored context and the contexts left after five toggles. `compare`
  holds a run to a reference machine's run of the same engine, against a bar
  written into its docstring before the first CI run. `--payload=` replays
  another machine's payload. A one-off workflow ran it headed on
  `windows-latest` and `ubuntu-latest`, five configurations each, native and
  replayed. It never reached main, and commit 5f2f495c holds it. The output
  is `results/gate_ci.txt` and the replayed payload
  `results/gate_payload_mac.json`.
- The maintainer chose to close the gate as partial, on software drivers.
- The rings. The maintainer asked for best practice. A survey agent read the
  ORTEP-III and PLATON manuals and Jmol's source, and I read Jmol's
  `EllipsoidsRenderer` and `Tensor` myself. All three draw three rings on
  every anisotropic site wherever their solver puts the axes, and none
  documents a tie-break. The maintainer chose that practice, made stable, in
  `structure3d._pin_axes`. Each lone axis faces (1, e, π). An equal pair's
  first axis is the shadow of the lattice vector nearest their plane. A sphere
  takes the orthonormalised lattice. A site is pinned once, and each image is
  turned by its own M·R·M⁻¹.
- Docs: `gui/CLAUDE.md`'s viewer paragraph, the GUI guide's 3D section and the
  1.5.1 notes.
- Forward notes. WP-1466 inherits the probe and the gate's two findings for a
  translucent pass. Its Priority is re-rated and stays P3: its blocker is gone,
  and its first task waits on the maintainer. WP-1313 inherits that three.js
  joins no allow list.

*Measured.* The reference is this Mac: Apple M4, playwright 1.63.0, Chromium
153 on ANGLE Metal, Firefox 155 and WebKit 26.6, all headed. Its three engines
agree to 0.09 levels of 255 on every picture. With the Mac's payload replayed,
the worst picture per runner configuration was:

| Driver the runner reported | Browsers | Against the bar |
|---|---|---|
| Direct3D 11 over WARP, via ANGLE | Chromium, WebKit (Windows) | go: 0.15 levels, 0.30 % past 32 |
| Mesa llvmpipe | Chromium via ANGLE's GL, Firefox, WebKit (Linux) | go: 0.07 levels, 0.15 % |
| SwiftShader | default Chromium, both runners | 0.50 levels, 1.01 % against a 1 % bar; 99.3 % of those pixels on an edge |
| WARP with no multisample buffer | Firefox forced (Windows) | no-go: 2.44 levels, aliased edges, 96 % on an edge |
| WARP, blocklisted | default Firefox (Windows) | the viewer's "no WebGL2" message |

- On every run a redraw and a restored context came back to 0.000 levels,
  reset moved the view by 22.95 or more, hover picked Ca1, both exports were
  3000 × 2250, five toggles made six contexts and lost six, and no page threw.
- Native payloads, before the pin: T differed from the Mac's by 0.04-0.18 Å on
  the four sites with an equal pair, and by sign alone (≤ 1e-16) on F1 and F2.
  T·Tᵀ agreed to 2e-17. After the pin, each site's own image from the x86
  runners' vectors lands on the Mac's to 5.6e-17 Å.
- Fast selection on the final tree, `[dev]` venv plus python playwright
  1.63.0, macOS arm64, no other suite running, load 3.5 at the start: 6270
  passed, 140 skipped, 179 s. The session added five tests to
  `tests/test_structure3d.py`, all passing, and changed no other test file.
  The full selection did not run, because the change moves the viewer's
  payload and no measured refinement number. GUI vitest did not run, since no
  file under `gui/src` changed.

*Review.* `/code-review high --fix` found nine. It fixed three: the tolerance
comment's numbers (4.5e-16 rounding, 7.8 % nearest real gap), the count of
symmetry-uniaxial sites, and a test through `build()`. Only three of the four
sites with an equal pair sit on a threefold. Ca1 is on a twofold, and its file
gives U11 = U33. I took three it left. Images were pinned one by one, which put
equivalent atoms' free rings up to 60° apart, so a site is now pinned once.
`gate.py` now waits for the payload and reports a reference picture it lacks.
The `_FACING` comment and the guide now say less and cover more. Declined:
`gate.py`'s argument order, whose documented usage puts the flags last.

*Gotchas.*
- `timeout` is not on this Mac. Wrapped round `gh run watch` with stderr
  hidden, it returned at once, three times. Check elapsed time with `date -u`
  against the job's `startedAt`.
- The worktree guard refuses a heredoc whose text names git, and a command
  with a shell variable in its path. A scratchpad script run in one plain
  command passes.
- An element screenshot captures whatever is composited over the element. The
  first reference caught page chrome across the canvas, which is why the probe
  lifts it over the page.
- A real wheel event gives each engine its own zoom, and Firefox zoomed less.
  The probe dispatches a synthetic one.

*Next.*
1. The gate's residual: on a Windows or Linux machine with an NVIDIA, AMD or
   Intel GPU, take a fresh Mac reference and run `gate.py` natively there
   (`1462-spike/README.md` § Running it).
2. WP-1466, the polyhedra, needs the maintainer's P1-P8 and Brunner &
   Schwarzenbach (1971) before its first task.

### 2026-09-25 (3rd session) — the GUI's plotly goes, and the handover resumes

The GUI no longer loads plotly anywhere. The last pieces that could fetch it
went this session, so `rietx gui` runs on a base install. The `gui` extra now
installs nothing and is kept so old install lines still work. Nothing a user
sees changed, because none of the removed code was in the built page. plotly
stays in rietx only for `rietx compare` and the Python HTML export, and
WP-1461's last two tasks move both.

*Done.* Next item 0 of the previous entry, in one commit: the `/plotly.js`
route and `_NO_PLOTLY_JS` in `gui/server.py`, `gui/src/lib/plotly.ts`,
`lib/plot.ts:hoverLabel` and its two tests, and the `Plotly` stand-in in
`test-setup.ts`. `test_gui_server.py` asserts a 404 on the route. The install,
CLI and quickstart pages, `gui/CLAUDE.md` and `docs/releases/1.5.1.md` (a new
section on the viewer) follow. `viz/plotlyjs.py` stays for `compare_app.py`,
its one caller now, and its docstring says so. The Goal and acceptance 1 are
narrowed in place: they had promised that `pyproject.toml` names plotly
nowhere, which is WP-1461's to finish. The rename waits for WP-1461 to
*close*, since four of its PRs have merged and "merged" no longer says when.
The same commit removes an unused variable the merge left in
`test_gui_dist.py`, which had turned the draft PR's ruff job red.

*Measured*, macOS, node 22.15.0 and the `[dev]` venv plus python playwright
1.63.0:
- The rebuilt dist is byte-identical apart from `build-info.json`.
- GUI vitest 560 passed in 23 files. That is 562 less the two `hoverLabel`
  tests. svelte-check clean.
- Fast selection on the merged tree, load average 3: 6221 passed, 140
  skipped, none failed. It is the first fast count on this tree. The previous
  entry's 6125 predates the merge, so the two do not compare. After the
  review's one test and a docs-only merge of `origin/main` (WP-1327's
  handover): 6222 passed, 140 skipped, none failed. This session added that
  one Python test and renamed one.
- The full selection did not run. The change is GUI-only and moves no
  measured number.

*Review.* `/code-review high --fix` on the plotly commit found one defect.
The GUI's `html` export draws with plotly, so on a base install
`write_html`'s `ImportError` reached the route as a 500. It now answers 409
`EXPORT_UNAVAILABLE`, whose message names `rietx[viz]`. A new test hides
plotly to check it, and the install table, the gui-power route row and the
1.5.1 notes say that one export needs `viz`. The rest were stale mentions of
plotly, in ATTRIBUTION.md, `rietx.__getattr__`, a `structure3d.py` comment and
a `plotlyjs.py` docstring. Declined: re-locking `uv.lock`, which was already
about 60 lines behind `pyproject.toml` and would move unrelated pins; and the
plotly lines in DESIGN.md and a `test_docs_consistency.py` cap comment, both
dated records. A fresh `rietx[gui]` install therefore gets no plotly and so
no `html` export until WP-1461 moves `write_html`. Putting plotly back in the
`gui` extra until then is the other choice, and it is the maintainer's.

*Forward note.* WP-1461's `### Inherited` entry from this WP now says the
GUI's plotly is gone and that its compare task should delete
`viz/plotlyjs.py`.

*Next*, in order:
1. The GPU gate: run `1462-spike/gui_viewer.mjs`, or open the GUI, on a
   Windows or Linux machine with a real GPU. A broken picture sends D1 to its
   three.js fallback, and a good one closes the gate and this WP's last
   measured task.
2. Rename this file once WP-1461 closes, with the ROADMAP row and WP-1461's
   two links. No WP-1461 branch is open today, so the maintainer may prefer
   the rename in this PR.
3. WP-1466 (polyhedra) needs Brunner & Schwarzenbach (1971) from the
   maintainer before its threshold is set.

### 2026-09-25 (2nd session) — scoped against the field, decided, and built the renderer

The GUI's structure viewer no longer uses plotly. It draws with a small
renderer written for it, which solves each atom and bond exactly, so spheres
and ellipsoids stay smooth at any zoom, and anisotropic atoms now show the
three principal rings of an ORTEP drawing. Opening the viewer takes a
fraction of what plotly took, and a PNG is now a 3000-pixel render fit for a
paper. Coordination polyhedra, which the maintainer asked for during the
session, fit the same renderer and have a WP of their own (1466). Two things
stay open: a check on a Windows or Linux GPU, and deleting plotly from the
GUI altogether once the Series panel leaves it.

*Decided.* The maintainer confirmed D1-D8 and asked for a critical pass
against VESTA, Mol\*, ChimeraX and Daams & Villars (1993), read in full. It
revised D5 (the export is a render of its own) and D6 (ring ink that stays
visible on a dark atom), and added D9 (lines are quads with a width in CSS
pixels). WP-1466 carries the polyhedra and their proposed defaults.
`gui/CLAUDE.md` § Defaults records the maintainer's rule that every choice
ships a default that suits most phases.

*Done.* `gui/src/lib/gl3d.ts` is the renderer; `lib/structure3d.ts` keeps the
pure half and gains the scene, the view and a CPU pick that solves the
shader's equations; `panels/Structure3D.svelte` owns the view, puts hover in
a readout line under the canvas, and adds pan, zoom, `PNG` and a transparent
option. `gui/src/test-gl3d.ts` stands in for the renderer under jsdom. Docs:
the viewer paragraphs in `gui/CLAUDE.md`, the GUI guide's 3D section, and
root CLAUDE.md's vitest line. The spike (`1462-spike/`) keeps the prototype,
the paired driver and every log quoted here.

*Measured*, Apple M4 on macOS, playwright-core 1.63.0 with Chromium 1223,
Firefox 1543 and WebKit 2359, the NAC example, load average 107-174 on 10
cpus, new against plotly on the same machine (`results/paired_*.txt`):

| | Chromium | Firefox | WebKit |
|---|---|---|---|
| Model tab to a drawn picture | 395-619 ms against 1963-4771 ms | 912-982 against 2754-4329 | 515-729 against 1482-6091 |
| drag frame p95 | 17.1-17.6 ms against 16.9-17.7 | 33-43 against 37-90 | 18-20 against 30-39 |

- Chromium's long frames while opening: one of 55-99 ms against one of
  1497-4086 ms. It is a `Response.text.then` callback in `app.js`, and it is
  absent on a warm reload. The viewer's WebGL calls over the whole opening
  total 14-34 ms, 13-27 of them in the shader-compile checks at mount, which
  run in a different task, plus 7-26 ms for `getContext`
  (`results/first_show.txt`). None during a drag or a hover sweep.
- Acceptance 3's 17.7 ms p95 holds in Chromium. Firefox and WebKit miss it
  under this load, and plotly was slower in every paired run.
- `app.js` 96.4 to 102.6 KB gzip, +6.2 KB net of the deleted trace builders
  (acceptance 4).
- The export is 3000 × 1682 in all three engines, both backgrounds. Five
  toggles of the viewer made six contexts and lost five, so each close gives
  its context back. No `/plotly.js` request while the viewer shows.
- Counts: GUI vitest 558 passed in 23 files, node 22.15.0 on macOS, the same
  as at session start (the viewer's 28 + 16 tests became 26 + 18), then 559
  after the review's one test. Python
  `-m "not slow"`, `[dev]` venv with python playwright 1.63.0 installed in this
  worktree, macOS: 6125 passed, 140 skipped, 1 failed. The failure was
  `test_watch_browser.py`'s console-seam test, which passed alone at load 35.
  The 4 tests in `tests/test_structure3d_browser.py` are new, and skip where
  playwright is absent, CI included. The full selection did not run: the
  change is GUI-only and moves no measured number.

*Gotchas.*
- A mount effect that calls a function reading state tracks that state. The
  viewer's did, so every payload disposed the renderer and made a new one on
  a canvas whose context was dead, and Chrome drew its sad face. Fixed with
  `untrack`; `test-gl3d.ts` now counts a renderer made on a dead canvas.
- Firefox presents the first frame hundreds of ms after the draw call, while
  it compiles the shaders, so first-show numbers come off screenshots.
- In a narrow window the model pane stacks and the viewer sits below the
  fold: a driver scrolls it into view before aiming the mouse, since a
  screenshot finds it either way.
- The first cylinder shader followed Inigo Quilez's published function, whose
  page states no licence. It was rederived as the ellipsoid's equation before
  merge, the spike's copy too.
- `npm --prefix DIR init` writes `package.json` into the working directory,
  not `DIR`.

*Review.* `/code-review high --fix` raised ten findings. It fixed eight,
which landed as one commit: a tensor with two non-positive axes could make
the drawn shape singular, a failed export hid the controls, and the console
quoted the size asked for rather than the size made. `createRenderer` could
throw where it should return null, an empty payload left the last structure
on the canvas, and `background()` misread a translucent or `color()`
ancestor. The geometry is now `$state.raw`, and the browser module has an
`xdist_group`. One finding is declined: a bond half's open end shows when
its own atom is hidden, by the legend or by unticking the images. plotly's
cylinders were open the same way, so nothing is lost. Capping them means
cap discs in the shader and in `pickHalf` together. After the fixes, vitest
passed 559 (the new test is the two-flat-axes case) and svelte-check found
no errors.

*Not done, on purpose.* The tests task's "reads pixels at known atoms" is a
drawn-fraction check and a ring-ink count instead. `using/install.md` and
ATTRIBUTION.md are unchanged: the `gui` extra still needs plotly for the
Series panel, no dependency was added, and no code was ported.

*Paused* at the maintainer's request, during `/wp-handover`, after merging
`origin/main`. The merge brought WP-1461's Series port (#467), so nothing in
`gui/src` imports `lib/plotly.ts` any more and the built dist no longer names
`/plotly.js`. `test_gui_dist.py` and `gui/index.html`'s comment were
corrected for that in the merge. On the merged tree: GUI vitest 562 passed,
svelte-check clean, and `test_gui_dist`, `test_gui_server`,
`test_structure3d_browser`, `test_docs_consistency` and `test_gui_manual`
215 passed (`[dev]` venv plus playwright, macOS). The fast selection has not
run on the merged tree. The handover's steps 10-12 (verify, PR, report)
have not run either. Draft PR #472 holds the reviewer-facing body; step 11
edits it (`gh pr edit 472 --body …`) and marks it ready.

*Next*, in order:
0. The GUI's plotly remnants, now this WP's since it lands after the Series
   port: the `/plotly.js` route and `_NO_PLOTLY_JS` in `gui/server.py` (and
   its module docstring), `gui/src/lib/plotly.ts`, `lib/plot.ts:hoverLabel`
   and its two tests in `plot.test.ts`, and the `Plotly` stand-in in
   `test-setup.ts`. `test_gui_server.py` then asserts `/plotly.js` is a 404.
   The `gui` extra becomes `[]`, kept so `pip install 'rietx[gui]'` still
   works. `using/install.md`, `gui-quickstart.md`, `cli.md` and
   `gui/CLAUDE.md`'s "plotly is not vendored" line follow.
   `viz/plotlyjs.py` stays for `rietx compare` (WP-1461 task 9). Stage the
   new viewer and the extra's change in `docs/releases/1.5.1.md`, whose
   Series section still says the 3D view draws with plotly. Then resume
   `/wp-handover` at step 9 (a review of the new commits), 10 and 11, which
   edits draft PR #472, drops its "paused" note and marks it ready. The GUI
   probes need python playwright in the worktree venv
   (`uv pip install --python .venv/bin/python playwright`) and the NAC
   example built outside the repository (`1462-spike/README.md`).
1. The GPU gate: run `1462-spike/gui_viewer.mjs`, or open the GUI, on a
   Windows or Linux machine with a real GPU. A broken picture there sends D1
   to its three.js fallback; a good one closes the gate.
2. Once WP-1461 merges, rename this file to its title, with the ROADMAP row
   and WP-1461's two links.
3. Whichever of this WP and WP-1461's Series task lands second deletes
   `/plotly.js`, `lib/plotly.ts`, the `gui` extra's plotly, `viz/plotlyjs.py`
   if only the GUI uses it, `lib/plot.ts:hoverLabel` and the `Plotly`
   stand-in. Acceptance 1 is whole then.
4. WP-1466 (polyhedra) needs Brunner & Schwarzenbach (1971) from the
   maintainer before its threshold is set.

- **2026-09-25** — filed from WP-1461's session, on the maintainer's
  request, once they confirmed the move to uPlot. The library sizes above
  were measured that day. Nothing else was: no scene was drawn in three.js
  or 3Dmol.js. *Next:* the maintainer confirms D1-D5, then the spike.

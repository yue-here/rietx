# WP-1548 — depth cueing, and filled rings and faces, in the structure figure

Milestone: rietview · Status: 🔄 2026-11-12 — claimed by @yue-here
Depends on: 2111 soft (its ruling on `DIM_BOUNDARY`, D6)
Priority: P3 2026-11-12 — the maintainer asked for it; nothing waits on it, and a ray tracer through WP-1537 would give fog once that lands

## Goal

The structure figure gains two optional cues, in both renderers.

1. **Depth cueing.** `render_structure(..., depth_cue=...)` and a GUI toggle
   fade each surface toward the background with its distance from the
   viewer, so a reader can tell the near layer from the far one in a still
   picture.
2. **Filled faces.** A ring of bonded atoms, or any set of atoms a caller
   names, is drawn as a translucent filled polygon. The case asked for is an
   aromatic ring, the way a chemist draws a benzene or a pyridine. The
   general case is any face: a coordination plane, a layer, a ring in a
   framework.

Both are off by default. `render_structure` and the GUI draw the same
picture with either on.

## Context

### Why now

The maintainer asked for both on 2026-11-12, as an addition to this track.
No open WP owns either. WP-1538 changes the lighting, not the depth. WP-2111
removes what misleads a reader, and its `DIM_BOUNDARY` item is the one
overlap (below). WP-1468 and WP-2111 own the polyhedra rules, and a filled
face is not a polyhedron. WP-1470 D9 declined fog "because the GUI draws
none". This WP draws it in the GUI too, which removes that reason. 1538 D6
is the precedent: both renderers, off by default, one parity case.

### What the code already has

- **Faces exist as a primitive.** `viz.figure3d.scene.build_scene` turns
  each drawn polyhedron into an entry of `scene["faces"]`: flat triangles,
  one normal each, a colour and a centroid. The CPU raster
  (`viz/figure3d/raster.py`) sorts whole entries back to front by centroid
  and blends them at `POLY_ALPHA` (0.55). The GUI's `gl3d.ts` draws the same
  entries with `FACE_VS`/`FACE_FS`, lit from both sides. So a filled ring is
  a new kind of entry in that list, and neither renderer needs a new
  primitive. Each entry's `index` names a polyhedron today, and
  `viz/figure3d/report.py` and the GUI read it. A ring or a named face needs
  a second kind there.
- **Selections exist.** `viz/figure3d/cut.py` (WP-1501) builds boolean masks
  over the geometry's atoms in crystallographic terms (`select`, `plane`,
  `sphere`, `component`) and combines them with `&`, `|` and `~`. A named
  face takes such a mask, so no second selection language is needed.
- **The bond graph exists, keyed by position rather than by `i`/`j`.**
  *Superseded in part 2026-11-12:* `gui/structure3d.build` returns `bonds`
  whose `j` is the far end's in-cell representative, not always the drawn
  image the bond reaches, so paracetamol's `i`/`j` graph closes "rings" with
  6.1 Å and 10.9 Å edges. Ring perception matches each bond's end positions
  `a`/`b` to drawn atoms instead (`1548-measure/rings_probe.py`). The default
  one-cell drawing also closes no ring a cell edge cuts: paracetamol's
  benzene appears only in a block (`extent`), since the cell adds one bonded
  shell and no more.
- **Planarity, measured** (`1548-measure/rings_*.txt`, 2026-11-12). On the
  drawn bonds of the eight organic and hybrid phases in `tests/data`, the
  flat rings (benzene and pyridine rings in four phases) sit 0.001–0.025 Å
  from their mean plane at most. The cyclohexane chairs of C₁₆H₂₆ sit
  0.226–0.235 Å. A tolerance near 0.1 Å has a factor of four on either side.
  Only one phase gives non-planar six-rings, so the 21-phase pass should add
  more before the number is fixed. *2026-11-12, the 21 CIFs on disk*
  (`1548-measure/rings_planarity.txt`): eight carry carbon, and the gap holds
  at 0.025 Å flat (396 rings, five phases) against 0.226 Å puckered (52
  chairs, C₁₆H₂₆ alone). No five-ring exists on disk; widening the puckered
  side needs new CIFs (a sugar, proline, a cyclophane).
- **Depth is already a number per sample.** Both renderers keep a z-buffer.
  The GUI writes `gl_FragDepth` from view-space z over `uDepth`, the scene's
  depth span. A fog factor is a function of that value, applied after
  shading.
- **The background is known in one renderer only.** `render_structure`
  takes `background="white"` by default, and `None` gives straight alpha
  over nothing (raster.py's docstring, D7). The GUI clears to the theme's
  background. Fog toward the background colour therefore has no target in
  a transparent PNG. D3 decides that case.

### Prior art

Read from the manuals on 2026-11-12, and kept in `docs/practice.md`
§ Depth cueing, and filled rings and faces, in a structure figure, which
replaces the recalled list this section held. Several recalled claims were
wrong: Mol\* documents no fog, PyMOL and VMD give no default, and only
ChimeraX turns depth cueing on unasked. What bears on the decisions:

- **Depth cueing** is linear wherever a form is stated (ChimeraX, VESTA),
  between a start and an end given as fractions of the scene's depth.
  ChimeraX measures them against its clip slab, with defaults 0.5 and 1.0.
  VESTA measures them against the bounding sphere. VESTA and Jmol fade
  toward the background, and ChimeraX toward a fog colour that defaults to
  black. No program says what fog does over a transparent background.
- **Filled rings.** No program tests planarity. ChimeraX fills rings of up
  to six members, Jmol fills what a SMARTS query matches, and Mercury and
  VESTA fit a plane through atoms the user picks. A fill's default colour
  and opacity are almost never documented.
- **Aromaticity from coordinates.** A CIF carries no bond orders as a rule,
  and `crystallography/fragments.py` already records that a coordinate-only
  source "cannot tell an aromatic ring from a chain". So rietx cannot
  decide aromaticity. It can find a ring in the bond graph and test whether
  the ring is planar. D2 follows from that.

### Decisions to carry

- **D1. Fog is a blend toward the background, linear between a start and
  an end depth.** The fog factor f rises from 0 at the start to a maximum
  at the scene's far side, and the shaded colour becomes
  `(1 − f)·colour + f·background`. The constants (start, end, maximum) are
  shared look values in `scene.LOOK`, identical in Python and TypeScript.
  The survey confirms linear (named practice: ChimeraX, VESTA). rietx draws
  no clip planes, so the ramp is measured against the depth the drawn scene
  spans along the line of sight, as VESTA measures against its bounding
  sphere. The start and end take ChimeraX's defaults, 0.5 and 1.0 of that
  span, until the before-and-after pairs say otherwise. *2026-11-12:*
  `raster.draw(fog=...)` takes the start and end as view-space depths, so
  the span is chosen by the caller, `render_structure`.
- **D2. A ring is a planar cycle of the drawn bond graph, never an
  "aromatic" claim.** Perceive the smallest set of smallest rings on the
  drawn bonds, keep rings of a size range (5 and 6 to start) whose atoms lie
  within a tolerance of their mean plane, and fill those. Testing planarity
  goes past what any surveyed program does, which only caps the size
  (ChimeraX at six), so the test is new judgement and needs its own
  measurement, kept in `rings.PLANAR_RING_TOLERANCE`'s docstring and
  `1548-measure/`. *No `_audit` row* (the maintainer's ruling, 2026-11-12):
  the visualisation package stays out of the audit whole, as `_audit.NOT_WALKED`
  already has it. The surface must not call the result aromatic, because
  the package cannot tell (fragments.py). *The surface name is the
  maintainer's call* (see "Waits on the maintainer").
- **D3. A transparent background fades alpha, or declines fog.** With
  `background=None` there is no colour to blend toward. Either fog lowers
  the coverage (the far side turns see-through), or `depth_cue=` with
  `background=None` raises. Decide from a picture of each.
- **D4. A named face is a convex polygon over a mask's atoms.** The caller
  passes masks from `cut.py`, one per face. A planar set is drawn as a fan
  from its centroid, in the order the atoms sit round it. A non-planar set
  is drawn as its convex hull, like a polyhedron with no centre. A set of
  fewer than three atoms raises.
- **D5. A face's colour.** A polyhedron takes its centre's colour, and a ring
  has no centre. Options: a neutral grey, the colour of the ring's most
  common element, or the caller's. The default is a look question and goes
  to the maintainer. A caller's colour is always accepted.
- **D6. The `DIM_BOUNDARY` shade and fog must not read as one cue.** WP-2111
  records that three reviewers read the darker shade on images outside the
  cell as a second species, and took it for a depth cue. Fog darkens (or
  lightens) by depth too. If 2111 keeps the shade, fog and the shade appear
  together on the far side and a reader cannot separate them. Settle 2111's
  ruling first, or show both before choosing.
- **D7. Python first, then the GUI, both off by default.** `recipe` carries
  both options. `test_structure3d_browser.py`'s parity row gains one case
  with fog on and one with a filled ring, held to `PARITY_LEVELS`. Turning
  either on by default is a separate decision, made from before-and-after
  pairs.

### Seams

- `src/rietx/viz/figure3d/scene.py`: ring perception (or a call into a new
  helper beside it), the second kind of face entry, the fog constants in
  `LOOK`.
- `src/rietx/viz/figure3d/raster.py`: fog in the shading of the atom,
  stick, face and outline paths. The numpy path stays the bit-identity
  oracle, and a compiled kernel follows WP-1940's rule (root CLAUDE.md, the
  compiled tier).
- `src/rietx/viz/figure3d/render.py`: the keywords (`depth_cue=`, and the
  ring and face arguments), carried in `recipe`.
- `src/rietx/viz/figure3d/report.py`: a face that is not a polyhedron is
  counted as its own kind, or not at all.
- `gui/src/lib/gl3d.ts`: the fog term in every fragment shader. A ring face
  reuses `FACE_FS`.
- `gui/src/panels/Structure3D.svelte`: the two toggles. The GUI overhaul's
  R3 rebuilds the Structure graph (`docs/milestones/gui-overhaul.md`), so
  put the toggles where R3 puts the view controls if R3 has landed.

### Waits on the maintainer

Three choices are look or naming questions, and the maintainer decides
visual questions. Bring each with a picture:

1. The name of the ring option on `render_structure` and in the GUI, given
   D2 (it must not say "aromatic" unless the maintainer rules otherwise).
2. D3, fog over a transparent background.
3. D5, a ring's default colour.

## Non-goals

- Deciding aromaticity, bond orders or hybridisation. D2.
- Fog in the SVG (WP-1536). A per-pixel blend has a vector form only as a
  colour per primitive, which is that WP's call.
- Ambient occlusion (WP-1538), cast shadows and depth of field (WP-1537).
- Changing the default look. D7.

## Tasks

- [x] Read the depth-cueing and ring-filling sections of the PyMOL,
  ChimeraX, VMD, Mol\*, Jmol, VESTA and Mercury manuals. Replace the
  "recalled" list above with what they say, and add the survey to
  `docs/practice.md`. Never open ChimeraX's source (WP-1537, 1538). *(2026-11-12: VMD unreachable, its host failing TLS through the proxy.)*
- [x] Fog in the numpy raster path, with unit tests: the near and far
  copies of one atom differ by the expected blend, and fog off is
  bit-identical to today. *(2026-11-12: `raster.draw(fog=(z_start, z_end,
  f_max, colour))`, every depth-tested path; a fogged call runs numpy on
  either tier until the wheel has a kernel that fogs, see the next item.)*
- [ ] The compiled kernel: `render_rows_cued` in `kernels/src/raster.rs`,
  bit-identical to the numpy path, shipped as rietx-kernels 1.5.0
  (`docs/RELEASING.md` § The kernel wheel). The floor rises and `draw` stops
  taking the numpy path for fog only once the maintainer publishes it.
- [x] Fog in `gl3d.ts`, and the parity case with fog on. *(2026-11-12:
  `scene.fog_span`/`fogSpan` twins held equal by 8 corpus cases; a FOG
  chunk in all four fragment shaders, clamping before it blends as the
  raster does; `render_structure(depth_cue=)` and the drawer's "depth cue"
  box, R3 not having landed. Parity 0.81 levels cued, 0.87 plain; the cued
  row also asserts the viewer fogged, since fog moves the canvas less than
  the bar. A transparent export draws without fog until D3 is ruled.)*
- [x] Ring perception and the planarity test, with unit tests on
  paracetamol (`tests/data/cod_2104364.cif`, one benzene ring) and on a
  structure with no rings. Measure the planarity spread on the organic
  phases in `tests/data` before fixing the tolerance, and add its `_audit`
  row. *(2026-11-12: `viz/figure3d/rings.py`, the union of minimum cycle
  bases on the position-matched bond graph, rings of 5 and 6 within 0.1 Å
  of their plane; 10 tests in `tests/test_figure_rings.py`. The no-ring case
  is C₄H₂, since fluorapatite closes non-planar Ca–O–P rings. The `_audit`
  row was dropped by the maintainer's ruling, D2.)*
- [ ] Named faces from `cut.py` masks (D4), drawn by both renderers, with
  the parity case.
- [ ] Before-and-after pairs on the 21 phases and paracetamol, committed
  under `docs/wp/1548-measure/`. Show them to the maintainer with the three
  questions above.
- [ ] Docs: the `render_structure` docstring and the GUI guide's structure
  section.
- [ ] Tests + figure pairs to `tests/output/figure3d/`.
- [ ] Skill: one clause in `api-figure.md` for each option, tagged with this
  WP's measurement, then `rietx skill --install . --copy`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_structure3d_browser.py -n auto --dist loadgroup
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_render_structure.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
npm --prefix gui test && npm --prefix gui run check
```

The parity row passes with each option on. With both off, every existing
figure test is bit-identical. The before-and-after pairs are committed and
looked at.

## References

- Tarini, M., Cignoni, P. & Montani, C. (2006). Ambient occlusion and edge
  cueing for enhancing real time molecular visualization. *IEEE Trans. Vis.
  Comput. Graph.* 12, 1237-1244. Covers depth cues in molecular graphics;
  not yet read (WP-1538 asks for it too).
- Ring perception: the smallest set of smallest rings. Figueras, J. (1996).
  Ring perception using breadth-first search. *J. Chem. Inf. Comput. Sci.*
  36, 986-991. Recalled, not read.

## Handover log

### 2026-11-12 — filed

The maintainer asked for depth cueing and for filling aromatic rings and
arbitrary faces, on the structure-figure track. Nothing is built or
measured.

- **Filed** because no open WP owns either. WP-1538 is lighting, WP-2111 is
  what misleads a reader, WP-1468 was the polyhedra rules. 1470 D9 declined
  fog only because the GUI drew none, and this WP draws it in both.
- **Found in the code:** faces are already a primitive both renderers draw,
  and `cut.py`'s masks already name atom sets. So the ring and face half is
  mostly scene-building. Fog touches every shading path in both renderers.
- **Forwarded:** WP-2111's `### Inherited` notes that this WP waits on its
  `DIM_BOUNDARY` ruling (D6).
- **Reviewed:** prose-only branch, so no `/code-review`. Docs-consistency
  tests pass.
- **Next:** the manual survey, then fog in the numpy raster.

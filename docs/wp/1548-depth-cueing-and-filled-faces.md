# WP-1548 — depth cueing, and filled rings and faces, in the structure figure

Milestone: rietview · Status: ⬜
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
- **The bond graph exists.** `gui/structure3d.build` returns `bonds` as atom
  index pairs over the tiled atoms. Ring perception runs on that graph.
- **Depth is already a number per sample.** Both renderers keep a z-buffer.
  The GUI writes `gl_FragDepth` from view-space z over `uDepth`, the scene's
  depth span. A fog factor is a function of that value, applied after
  shading.
- **The background is known in one renderer only.** `render_structure`
  takes `background="white"` by default, and `None` gives straight alpha
  over nothing (raster.py's docstring, D7). The GUI clears to the theme's
  background. Fog toward the background colour therefore has no target in
  a transparent PNG. D3 decides that case.

### Prior art (recalled, not checked)

None of the following has been read from a manual for this WP. The first
task reads them and adds the survey to `docs/practice.md`.

- **Depth cueing.** PyMOL fogs by default (`depth_cue`, `fog_start`). ChimeraX
  fades toward the background by default (`lighting depthCue`, with a start
  and an end as fractions of the scene's depth). VMD offers linear,
  exponential and squared-exponential fog, off by default. Mol\* has fog in
  its renderer settings, on by default. Jmol has `zShade`. VESTA's setting
  is not recalled.
- **Filled rings.** PyMOL's `cartoon_ring_mode` fills rings, mainly for
  nucleic acids. ChimeraX fills rings in its nucleotide and small-molecule
  styles. ChemDraw-style circles inside a ring are a 2D convention. Mercury
  draws mean planes through named atoms. Jmol's `draw polygon` and its
  `polyhedra` over named atoms make an arbitrary face.
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
  Linear first because it is what the recalled defaults do. The task that
  reads the manuals confirms or changes this.
- **D2. A ring is a planar cycle of the drawn bond graph, never an
  "aromatic" claim.** Perceive the smallest set of smallest rings on the
  drawn bonds, keep rings of a size range (5 and 6 to start) whose atoms lie
  within a tolerance of their mean plane, and fill those. The planarity
  tolerance is a heuristic number, so it gets a row in `rietx._audit` with
  its measurement. The surface must not call the result aromatic, because
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

- [ ] Read the depth-cueing and ring-filling sections of the PyMOL,
  ChimeraX, VMD, Mol\*, Jmol, VESTA and Mercury manuals. Replace the
  "recalled" list above with what they say, and add the survey to
  `docs/practice.md`. Never open ChimeraX's source (WP-1537, 1538).
- [ ] Fog in the numpy raster path, with unit tests: the near and far
  copies of one atom differ by the expected blend, and fog off is
  bit-identical to today.
- [ ] Fog in `gl3d.ts`, and the parity case with fog on.
- [ ] Ring perception and the planarity test, with unit tests on
  paracetamol (`tests/data/cod_2104364.cif`, one benzene ring) and on a
  structure with no rings. Measure the planarity spread on the organic
  phases in `tests/data` before fixing the tolerance, and add its `_audit`
  row.
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

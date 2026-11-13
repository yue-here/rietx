# WP-1015 — Structure viewer, zero new dependencies

Milestone: v1.0 · Status: ✅ 2026-07-30 — scene pass landed the same day
Track: The human GUI
Depends on: WP-1010 (WP-1014 soft — the viewer is richer once editing exists)

## Goal

A rotatable 3D structure view — atoms, bonds, cell, thermal ellipsoids —
with **no new JS dependency**: the server computes a small geometry payload
from code that already exists, and plotly (already on the page) renders it.

## Context

- **Everything hard already exists server-side**:
  - `crystallography/symmetry.py:56` `expand_positions(sg, xyz, *, tol=1e-4)`
    — symmetry expansion to the full cell.
  - `crystallography/adp.py` — `cartesian_basis` (`:89`), `u_cartesian`
    (`:101`), `principal_values` (`:113`), `is_positive_definite` (`:132`)
    are exactly the eigen-decomposition a thermal ellipsoid needs (already
    used by the positive-definiteness guard); `u_equivalent` (`:108`) sizes
    the isotropic spheres.
  - gemmi (a core dep) supplies element radii/colours and neighbour search
    for bonds.
- `src/rietx/gui/structure3d.py` computes a JSON payload: expanded atom
  positions in Cartesian coordinates, cell-edge polyline, bond segments by
  radius-sum cutoff, and per-atom ellipsoid transforms. Frontend renders
  with plotly `Scatter3d` (atoms, bonds, cell edges) + `Mesh3d` (a unit
  sphere transformed by each U_cart eigen-decomposition). Rotate/zoom come
  free. Payload for a typical cell is a few kB. Served at
  `GET /api/structure3d` (route reserved in WP-1008).
- **Why this is a diagnostic, not decoration**: the ellipsoids are refined
  quantities. A non-positive-definite ADP — the existing
  `ADP_NOT_POSITIVE_DEFINITE` diagnostic — becomes visibly degenerate
  (flagged in the payload, rendered distinctly, never NaN geometry), and an
  over-flexible background inflating ADPs becomes visible as balloons.
  Ellipsoids draw at a selectable probability (default 50 %); isotropic
  atoms draw as spheres of the U_eq-equivalent radius.
- Remember the representation rules (`crystallography/adp.py` module doc):
  stored CIF **U^ij**, fractional **U\*** for the structure factor,
  **U_cart** where eigenvalues are physical — the viewer wants U_cart, and
  the isotropic limit is U^ij = Uiso·G\*ᵢⱼ/(a\*ᵢa\*ⱼ), not Uiso·δᵢⱼ.

### Inherited

From **WP-1014** (import & in-GUI editing, landed 2026-07-30): `GET /api/structure`
now carries a **`sites` arm** beside the model — per atom, `dof_paths`,
`dof_directions`, `adp_paths`, `adp_patterns`, `site_symmetry_order` and a
`special` flag — derived through the same `stabilizer_rotations` →
`coordinate_basis`/`adp_basis` calls `ParameterTable` uses. A viewer that wants to
draw thermal ellipsoids or mark special positions should read that rather than
re-deriving it, and should note what it deliberately does **not** contain: the
Wyckoff *letter*, because `wyckoff.site_constraints` runs spglib per atom and this
route refetches on every head move (including one a `set_vary` made). If the
viewer wants letters, that is an argument for putting them on `/api/structure3d`,
which is computed on demand — not for adding them here.

Two more facts. The **model editor is a full-window mode**, not a tab
(`panels/Model.svelte`, toggled from the header beside Text), so a 3D view has a
natural home *inside* it — a third column beside the atom table — without needing
a sixth tab. And **an atom's ADP block is toggled by `POST /api/structure/aniso`**,
which seeds `AnisoU.isotropic` server-side; a viewer offering "show ellipsoids"
on an isotropic atom should call that verb rather than inventing a tensor, for the
reason recorded above this section (U^ij = Uiso·G*ᵢⱼ/(a*ᵢa*ⱼ), not Uiso·δᵢⱼ).

From the **v1.0 GUI plan** (2026-07-29): escalation path if a full
ball-and-stick/polyhedra viewer is later wanted — 3Dmol.js (BSD-3,
permissive, clears the licensing invariant, needs an ATTRIBUTION.md entry)
as an opt-in vendored asset. **Not v1**; recorded so the next person doesn't
re-derive the licence answer.

From **WP-1008** (GUI server, landed 2026-07-30): `GET /api/structure3d` is
**reserved** and 404s naming this WP, so the route is settled — decide its
payload here. `GET /api/structure` already serves the whole validated
`Structure` dump, so the 3D route only earns its place by returning something
the model does not already say (expanded symmetry images, bonds, a cell frame);
if it would only reshape `Structure`, do it in the frontend and leave the route
reserved rather than shipping a second view of the same fact.

From **WP-1010** (frontend scaffold, landed 2026-07-30): "zero new dependencies"
now has a precedent to follow — plotly is **not** bundled, it is injected at
runtime from `/plotly.js` (served out of the installed Python package), so the
committed dist stays small and the page stays offline-safe. A 3D viewer built on
the same plotly instance inherits that for free; anything else has to justify
bytes in a dist that is reviewed as a diff.

## Non-goals

- No coordination polyhedra, no supercell packing view, no measurement
  tools (distances/angles readout beyond hover) — v2 with the 3Dmol.js
  escalation if wanted.
- No client-side crystallography: the frontend receives Cartesian geometry
  and draws it; symmetry never crosses the wire.

## Tasks

- [x] `src/rietx/gui/structure3d.py`: payload builder (expanded
      positions, cell edges, bonds by radius-sum cutoff, ellipsoid
      transforms at a probability level; NPD tensors flagged).
- [x] `GET /api/structure3d` on the session (current model state, so edits
      reflect immediately).
- [x] Structure panel: Scatter3d + Mesh3d rendering, probability selector,
      species legend — **not** from gemmi colours, which do not exist; see
      the handover log.
- [x] `tests/test_structure3d.py`: cubic and monoclinic phases give the
      right atom multiplicity and 12 cell edges; a known aniso CIF's
      ellipsoid axes match `principal_values`; a non-positive-definite
      tensor is flagged in the payload rather than producing NaN geometry.

### Second pass — the scene, not the geometry (2026-07-30)

Reopened after a session on the shipped panel: the geometry was right and the
*scene it was drawn in* was plotly's defaults rather than crystallography's.
Measured against how VESTA, Jmol and 3Dmol.js draw the same picture.

- [x] Orthographic projection, no Cartesian x/y/z box, a/b/c letters on the
      cell's own edges, solid frame, `dragmode: "orbit"`, modebar trimmed.
- [x] Bonds as two-tone cylinders in Å (`unitCylinder`/`stickTransform`)
      rather than a `scatter3d` polyline of pixel width — the objection the
      module already made about markers, applied to sticks.
- [x] `BALL_FRACTION` 0.32 → 0.40, `unitSphere` 8×16 → 12×24, one shared
      `LIGHTING`/`LIGHT_POSITION` with no black far side.
- [x] `axisCamera` + view-down-a/b/c and reset buttons.
- [x] The panel's own truthfulness: a loading state, a `seq` guard on
      `load()`, and the shell no longer lists this viewer as still owed.
- [x] The camera read from the scene rather than from an event that never
      fires — see the 2026-07-30 (second pass) handover entry.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_gui_server.py -q
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m ruff check src tests examples
```

## References

- `crystallography/adp.py` (three-representation module doc);
  `crystallography/symmetry.py` `expand_positions`; gemmi element tables.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **structure viewer** (WP-1015, WP-1462; `src/rietx/gui/structure3d.py`,
`gui/src/panels/Structure3D.svelte`, `gui/src/lib/structure3d.ts`,
`gui/src/lib/gl3d.ts`) is the model as drawable geometry, served by
`GET /api/structure3d` and drawn by the viewer's own WebGL2 renderer, **no
library** (plotly cost 4.8 MB for it, three.js would have cost 139 KB gzip, this
costs 6.2 KB). A third column of the model pane rather than a sixth tab. Its
founding rule is that **everything hard stays on the server**: the payload is
Cartesian points, 3×3 matrices and index pairs, and the browser's whole job is
`pos + M·v` over one unit sphere, which is also why a ball and an ellipsoid are
one code path. That forced the one new crystallography verb:
**`symmetry.expand_orbit` returns the operation as well as the position**,
because U\* → R·U\*·Rᵀ means an image drawn with its parent's tensor is right on
a cubic site and wrong on every other one; `expand_positions` now delegates to
it. Four rules. **gemmi has no colour table** — it supplies radii and
`is_metal`, and the colours are the CPK convention with values chosen here
(ATTRIBUTION.md), never transcribed. **A radius-sum bond rule needs a chemical
predicate**: bond a metal to a cation only when the phase has no non-metal in
it, or LaB6's cell edges become La–La sticks and forsterite grows Mg–Si ones
(a cation is `_cation_sites`', WP-1466), and **a floor** (`split_floor`, read by
sticks and shells: 0.7 of the radius sum between non-metals, 0.5 with a metal, uranyl's U=O being 0.67). **A non-positive-definite tensor draws its non-positive axes at
zero** on the server (a √ of a negative is a NaN), and the client keeps such a
column at `FLAT_AXIS` = 1 mÅ because the ray-caster solves through M⁻¹. And
**bond segments complete their partners exactly one level** — a bond to a
translated image is correct and *reads* as broken — which is the line between a
coordination and the packing diagram this WP declined. `probability`,
`bond_tolerance`, `disorder`, `centres` and `ligands` are drawing thresholds on
the query string, never in `ProjectDoc`. **Polyhedra are chemistry, so the server builds them** (WP-1466):
cation centres, anion ligands (`_cation_sites`). A rule change re-runs
`docs/wp/1466-measure/measure.py`, writing the default picture the tests hold.
**A legend switch is as fine as the default it restores** (per formula, since
P5 is per shell size), and a hidden polyhedron's `vertex_only` atoms hide too.

Its **look** (the second pass, 2026-07-30, read against VESTA, Jmol and
3Dmol.js) is crystallography's rather than a plotting library's. **Parallel
projection** (perspective converges a cubic cell's far edges), **no Cartesian
axis box** (the cell's own a/b/c edges are labelled instead, at a clearance in
Å set by the largest ball — a percentage of the edge put every letter inside a
corner atom), and **bonds as two-tone cylinders in Å**, which settles the legend
rule *a half belongs to its atom*. `STICK_RADIUS` = 0.08 Å is a lower bound on
`BALL_FRACTION` = 0.40 (VESTA's fraction, on covalent rather than atomic radii),
pinned by test so hydrogen cannot become a lump on a rod. **The trackball has no
up vector to pin**: `cartesian_basis` is upper-triangular, so c ∥ ẑ for every
orthogonal cell, and a turntable's +z would make "view down c" degenerate — the
free rotation and the a/b/c buttons are one decision. In ellipsoid mode an
anisotropic site draws its **three principal ellipses**, one unit-frame
coordinate near zero since T's columns are the principal axes, and an isotropic
site draws none, its axes pointing nowhere. **Where principal values are equal
the server pins the free axes** (`structure3d._pin_axes`), because `eigh`
chooses them per LAPACK build: a Mac and an x86 runner drew one uniaxial site's
rings as an X and a + (WP-1462's gate). It pins a site once and turns that T by
each image's M·R·M⁻¹, so equivalent atoms wear equivalent rings.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. All cited server-side
  helpers verified present (exact names/lines) the same day.

- **2026-07-30 — landed.** All four tasks done; `GET /api/structure3d` is live
  and out of `RESERVED_ROUTES`. Acceptance above is green: 27 new Python tests
  (1164 → 1192 fast-suite passes, skips unchanged at 107) and vitest 184 → 206;
  ruff and `svelte-check` clean; `app.js` 151.6 → 161.5 kB (55.1 kB gzip).

  **Done.** `src/rietx/gui/structure3d.py` builds the payload — the symmetry
  orbit *with each image's rotation*, bonds over the 27 nearest lattice
  translations, eight cell corners and twelve index pairs, per-atom ellipsoid
  transforms, NPD flagged. `gui/src/lib/structure3d.ts` turns it into plotly
  traces, `gui/src/panels/Structure3D.svelte` is the panel — a **third column of
  the model pane** (the Inherited note's suggestion, taken), toggled by a `3D`
  button in that pane's header. `gui/src/lib/plotly.ts` is the runtime loader,
  now shared with `Plot.svelte`. One new crystallography verb,
  `symmetry.expand_orbit`, with `expand_positions` delegating to it.

  **Four things the WP could not have known, all measured:**

  1. **gemmi has no colour table.** It has `covalent_r`, `vdw_r` and `is_metal`,
     which is what the bond rule and the balls use; there is no `color`. Colours
     are the CPK *convention* (cited) with hex values chosen here for contrast on
     both themes, plus a golden-angle-in-Z fallback for everything the convention
     does not name — so nothing is transcribed from Jmol/VESTA/PyMOL, all of
     which are unsuitable to copy into an MIT core. `ATTRIBUTION.md` now records
     this under Data tables.
  2. **A plain radius-sum bond rule draws LaB6's twelve cell edges as La–La
     sticks** (gemmi's covalent radius for La is 2.07 Å against a = 4.158 Å) and
     the boron framework disappears into a cage. The fix is chemical rather than
     geometric and is a predicate over the *phase*: bond metals to metals only
     when the phase has no non-metal in it, so an alloy still bonds and an
     intermetallic never needs a special case (`bonds_between_metals`).
  3. **A non-positive-definite tensor draws its non-positive axes at zero**, not
     at `√(negative)`: one NaN vertex loses the whole `mesh3d`, not one atom. The
     ellipsoid collapses to a disc or a needle — visibly degenerate — and the
     payload says so in `note` and per atom in `npd`.
  4. **`expand_orbit` had to exist.** A displacement ellipsoid *transforms*
     (U\* → R·U\*·Rᵀ) rather than merely moving, and `expand_positions` discards
     the operation. An image drawn with its parent's tensor looks right on a
     cubic site and is wrong on every other one — asserted by
     `test_every_symmetry_image_rotates_its_tensor_and_keeps_its_size`, whose
     shape is the useful part: a rotation preserves eigenvalues, so every image
     must share its site's semi-axis *lengths* while differing in orientation.

  **The browser found five more, four of which jsdom structurally cannot see**
  (Chrome for Testing via `playwright-core`, installed outside the workspace).
  This is the fifth session running to find one, and the second (after WP-1013)
  where the defect belonged to a *library's* view of the page rather than to the
  DOM the component renders:

  - **plotly's canvas overhung its box and swallowed the legend's clicks.**
    `responsive: true` listens for **window** resizes only, and this plot's box
    shrinks without one — the legend, the knobs and the caption all render
    *below* it as soon as the first payload lands. Playwright reported it exactly
    (`<canvas 1018×1526> … intercepts pointer events`); a human would have read
    it as "the legend is broken". Fixed with a `ResizeObserver` →
    `Plotly.Plots.resize`, which is the general truth rather than a workaround.
  - **The cell frame was invisible**: `--line` is a hairline *border* colour and
    disappears into the page in a 3D scene. The frame is the picture's frame, so
    it takes `--accent`. Nothing in the payload was wrong; the first screenshot
    is what said so.
  - **Every bond ended in mid-air.** A bond drawn to a translated image is
    correct and *reads* as broken. Each out-of-cell endpoint now gets its atom
    drawn (`_partners`), flagged `boundary` so multiplicity counting is
    untouched, and **exactly one level deep** — completing those atoms' bonds in
    turn is a packing diagram, this WP's declared non-goal.
  - **The chosen ellipsoid probability was reset by every reload**, because the
    payload carries the server's default and a reload replaced the whole object.
    The level now lives in the component and meets the geometry in one function
    (`at`), which is the same shape as WP-1013's "two facts must not share one
    field" one rank over.
  - **The rotation was thrown away by every redraw** — and this one is worth the
    most, because the *first* version of this log claimed the opposite. "The
    camera survives a redraw (`uirevision`)" was measured by reading
    `_fullLayout.scene.camera` back, which reports whatever was last passed
    **in**: it says the view was kept while the picture has visibly snapped home.
    A screenshot comparison is what exposed it. Isolated in the browser:
    `Plots.resize` keeps the view, `react` with the *same* trace objects keeps
    it, and `react` with **fresh trace objects** does not — replacing a `mesh3d`
    tears the gl3d scene down and rebuilds it from the layout, which
    `uirevision` does not cover. Every redraw here builds fresh traces (a bond
    refetch, a mode switch, a model edit), so the rotation was lost on all three.
    The camera is now the component's: captured from `plotly_relayout` into a
    plain variable (not `$state` — nothing renders it, and reactivity would
    redraw on every drag) and supplied to `layout()` on every draw. Verified by
    screenshot across a server refetch *and* a ball→ellipsoid→ball round trip:
    eye 1.613, 0.434, 1.326 unchanged, pictures identical.

    > **Withdrawn 2026-07-30 (second pass).** The diagnosis above is right and
    > the fix is not: `plotly_relayout` **never fires for a gl3d camera drag**,
    > so the capture received nothing and the view was lost anyway. Measured
    > against this very build — see the second-pass entry below. The "verified by
    > screenshot, eye 1.613, 0.434, 1.326 unchanged" sentence is wrong; treat the
    > eye figures as unmeasured.

    Two method notes for the next person. **A sha256 of a WebGL screenshot is too
    strict** — a re-render differs by a pixel, so an equality test on the hash
    reports "view lost" for every redraw and hides the real answer. And
    `layout.scene.camera` is not a reading of the view.

  **Measured** (M4, Chrome for Testing, Apple Metal): boot-to-interactive
  **65–99 ms**, unchanged from WP-1013's 81 ms — the viewer costs nothing before
  the model pane is opened, since plotly and the scene are both inside it — and
  click-to-a-drawn-scene **605–1447 ms**, mostly the 4.8 MB plotly fetch and
  parse (1414–1669 ms under software WebGL, so the GPU is not the bottleneck).
  A probability change is a client multiply with **zero** refetches; the bond
  slider is a server round trip because the server owns the bond rule; the
  camera was *claimed* to survive both, and did not — see the fifth browser
  defect above and the second-pass entry below. On NAC read with its aniso loop: 84
  atoms in the cell, ellipsoids at 90 %, each symmetry image visibly rotated, and
  Na1's balloon (Biso 2.16 Å² against Al's 0.59) obvious at a glance where the
  parameter table shows it as six ordinary numbers. That last is the WP's whole
  claim, working.

  **Decisions worth keeping.** A ball and an ellipsoid are the **same code path**
  — `pos + T·v` over one unit sphere, with `T = f·r·I` or `k(p)·T` — because
  plotly's `scatter3d` markers are sized in *pixels* and a ball-and-stick that
  does not scale with the cell cannot be compared with it. Probability levels are
  served as a **table** of k(p) = √χ²₃(p) rather than one number, which is what
  makes the selector a client multiply. `bond_tolerance` and `probability` ride
  on the **query string** and are never persisted: they are drawing thresholds,
  and storing one would make a picture the project's opinion.

  **Not done, deliberately.** No coordination polyhedra, no packing view, no
  measurement tools — the WP's own non-goals, and the 3Dmol.js escalation note
  above still stands if any of them is later wanted. The Wyckoff *letter* is
  still absent: the Inherited note said this route would be the place for it
  since it is computed on demand, and it remains true, but nothing in the panel
  needed it. `MAX_ATOMS` is 400 and `MAX_BONDS` 4000; both report in `note` when
  they bite.

- **2026-07-30 (second pass) — the scene, not the geometry.** Reopened on the
  report that the viewer "is a bit janky". The geometry was right; what was
  wrong was that the *scene* it was drawn in was plotly's defaults rather than
  crystallography's, and that is a different kind of bug — nothing was
  incorrect, everything was slightly unlike the picture a crystallographer
  expects. Read against how VESTA, Jmol and 3Dmol.js draw the same thing, and
  measured against the bundled plotly.js **3.7.0** (which is what `/plotly.js`
  serves — 6.9.0 is the *Python* `plotly` package, corrected 2026-07-30)
  rather than against its documentation.

  **Four defaults were plotly's.** *Perspective*, under which parallel cell
  edges converge and a cubic cell does not look cubic; every crystallographic
  figure is a parallel projection, so `DEFAULT_CAMERA` is orthographic now. *A
  Cartesian x/y/z box*, whose grid, background and tick labels churn on every
  frame of a drag and describe a frame of reference nothing in the picture uses
  — gone, with `axisTrace` putting a, b, c on the cell's own edges instead. *A
  4 px bond polyline*, which is exactly the objection `lib/structure3d.ts`
  already made about why an atom is a `mesh3d` and not a marker: a pixel-width
  primitive does not scale with zoom. And *a faceted sphere* at sixteen
  segments, with a specular that made four hundred identical balls read as
  plastic.

  **What the bond change forced.** Cylinders are `unitCylinder` pushed through
  `stickTransform`, whose columns are the axes — `atomTransform`'s own
  convention — so a tube and a sphere go through the same `transform()`. Two
  consequences worth keeping. Splitting each bond at its midpoint and colouring
  the halves by their own atoms settled a rule the old trace did not have: it
  ignored `hidden` entirely, so a species switched off left its bonds behind; **a
  half belongs to its atom**. And the stick radius (0.08 Å) is now a *lower*
  bound on the ball: `BALL_FRACTION` went 0.32 → 0.40 (VESTA's ball-and-stick
  fraction — comparable only because both ends are stated: VESTA scales *atomic*
  radii, these are covalent), and the pair is pinned by a test, because at 0.32
  hydrogen would have been a lump on a rod.

  **`dragmode: "orbit"` is load-bearing.** Turntable is what gl3d picks when no
  `camera.up` is supplied, i.e. what this scene had been, and it pins `up` to +z
  and *rewrites* any camera that disagrees. `cartesian_basis` is an
  upper-triangular Cholesky factor, so **c ∥ ẑ for every orthogonal cell** — the
  new "view down c" button would have put the eye exactly on the up axis and
  drawn nothing. The two are one decision, not two. (The modebar is trimmed to
  `toImage` for the same reason: `tableRotation` sets turntable from the UI.)
  `axisCamera` also depends on a second job `aspectmode: "data"` turns out to be
  doing — it makes the data→scene map a *uniform* scale, so a direction in Å is
  the same direction in camera coordinates.

  **The correction, and it is the important part of this entry.**
  `plotly_relayout` **does not fire for a gl3d camera drag at all.** The
  component had listened for it since the first pass, and had never received
  one: zero events across a drag that moved the eye from (1.35, 1.35, 0.95) to
  (−0.62, −1.41, −1.47), after which the next redraw put the scene back to the
  opening view. This is *not* a regression from the orbit/orthographic change —
  the same probe against the first pass's own committed `static/` says the same
  thing, which is how it was ruled out. So the fifth browser defect above was
  diagnosed correctly and fixed wrongly, twice in a row on the same question,
  and the pattern in both failures is the same: **the check was cheaper than the
  claim.** The first pass read `_fullLayout.scene.camera` (which reports what was
  passed *in*); the second read a screenshot after a redraw that happened to be a
  `Plots.resize`. What settles it is counting the events.

  The reading that *is* a reading of the view is the scene object's
  `getCamera()` — live `up`/`center`/`eye`/`projection`, read back immediately
  before each `react`. It is private API, and the honest defence of that is only
  that the two public alternatives are a signal that never arrives and a field
  that lies; when it is absent the last known camera stands, which is exactly the
  behaviour it replaces. A camera a *button* chose travels in its own slot
  (`pending`), so `down c` outranks what is on screen while a drag is not
  overwritten by it.

  **The other thing a browser found**: the a/b/c letters were drawn *inside* the
  corner atoms. A percentage of the cell edge is the wrong shape for the problem
  — a corner site is drawn at all eight corners, so a letter has to clear a
  *ball* — and 8 % of LaB6's 4.16 Å edge is 0.33 Å against a lanthanum drawn at
  0.83. The clearance is in Å and set by the largest ball in the phase.

  **Three things the panel said that were not true**, all cheap: "no structure
  yet" during the whole 605–1447 ms first paint (one `geo === null` cannot say
  both "not fetched" and "nothing here"); no request ordering, so two quick
  releases of the bond slider left the picture disagreeing with the slider —
  WP-1013's `seq` rule, and confirmed by removing the guard and watching the
  caption read 1.05× under a slider at 1.25; and the shell still listing this
  viewer under "panels still owed".

  **Measured** (M4, Chrome for Testing, Apple Metal, LaB6 and NAC projects):
  boot-to-interactive 77–122 ms and click-to-drawn-scene 1.9–2.3 s, both
  unchanged in character from the first pass — the added mesh work is nothing
  against the plotly fetch. At `MAX_ATOMS`/`MAX_BONDS` the scene is ~202 k
  vertices; LaB6 at the default tolerance is 36 k. Verified by screenshot: a
  drag survives a bond-threshold refetch *and* a ball→ellipsoid switch; view
  down c on a cubic phase draws a square rather than nothing; sticks keep their
  thickness through a full zoom; nothing goes black after half a turn; and Na1's
  balloon at 90 % is still the obvious thing in the picture.

  **Left alone, deliberately.** The bond rule and its 1.15 default: LaB6 at 1.15
  is still 210 segments and 109 out-of-cell partners, which reads as a hairball,
  but the La–B contact at 3.058 Å is real twelve-coordination and every standard
  rule (including Jmol's additive r+r+0.45) draws it — the honest answer is the
  slider that already exists, and one turn of it to 1.05 gives the picture in the
  screenshots. Balls do not clip against sticks in ellipsoid mode when a tensor is
  very small; ORTEP clips, and that is not worth the code here. And the WP's own
  non-goals stand: no polyhedra, no packing view, no measurement tools.

  Counts: vitest 207 → 221 (fourteen tests, no deletions); Python fast suite
  1192 → 1193 passed with skips unchanged at 107 (one test, both figures moved
  by one). Note for the record that CLAUDE.md's "206" for vitest was one short of
  what the suite actually reported at this WP's landing commit.

  One loose end handed on rather than fixed: the fast suite reports 1193 passed
  + 107 skipped while `pytest -m "not slow" --collect-only` reports **1298**, and
  the full suite 1263 + 116 against 1377 — two short in both selections. The gap
  predates this session (CLAUDE.md's "1378 collected" was passed+skipped added
  up, not a measurement), and both the pass and skip counts move by exactly the
  number of tests added, so the bookkeeping rule still works; but a collected
  figure should be measured before it is quoted again.

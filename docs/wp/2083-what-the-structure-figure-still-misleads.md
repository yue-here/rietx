# WP-2083 — what the structure figure still misleads a reader with, and the controls still asked for

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: —
Priority: P3 2026-11-02 — a view over what the fit already knows; carried from WP-1468, rated P3 there on 2026-10-23 because one reading misleads (`DIM_BOUNDARY`'s shade read as a second species) and waits on a ruling

## Goal

The structure figure stops showing a reader things that are not there: a
second species where there is one, a label printed twice, axis letters under
the atoms. The controls an ORTEP drawing needs (issue #1057) and a cluster
polyhedron on request exist. Each task stands on its own, so a session can
take one.

## Context

Filed 2026-11-02 at WP-1468's close, which held these items in its
`### Inherited` section and one partial task. WP-1468 was about the
polyhedra. Most of what it carried at the close concerns the figure as a
whole, so it moved here rather than being lost with a closed WP. The code is
`src/rietx/viz/figure3d/` (scene, render, report) over the geometry
`src/rietx/gui/structure3d.py` builds. The skill's figure page is
`docs/skill/rietx/references/api-figure.md`, with two committed copies
(`rietx skill --install . --copy`).

### The readings from WP-1957's reviewers (forwarded by WP-1504)

Each entry below came from [1504](1504-the-figure-surface-measured-with-real-agents.md)
(closed) on 2026-10-23, through WP-1468. Each was rechecked against the tree
at b0c79e12d on 2026-11-02 and still holds.

- **`view="auto"` ranks by `hidden`, stacking included, so it prefers an
  oblique view to an axis projection.** `FigureReport.stacked` (WP-1533) is
  the part of `hidden` that sits behind an atom of the same site, within a
  quarter of its drawn radius. One cell down a cell axis reads 0.53 hidden and
  0.53 stacked on HKUST-1, 0.52 and 0.50 on ZSM-5, and 1.00 and 1.00 on
  YBa₂Cu₃O₇; NAC's opening view reads 0.18 and 0.00. The skill's rule already
  reads `hidden - stacked`. The evidence for ranking by occlusion is WP-1957's
  Context 4: three blind reviewers ranked 15 renderings of refined
  fluorapatite, and the view down c (`hidden` 0.45, nearly all of it stacking)
  was first for two and second for the third, while `auto` picked about
  [2 0 1] (`hidden` 0.024) and all three called it "a tangle". The change
  moves every default `auto` pick, so it is an agent question before it is a
  code change.
- **The darker shade on images outside the cell reads as a second species.**
  `scene.DIM_BOUNDARY` (0.62, `viz/figure3d/scene.py:45`) dims every image
  outside the cell. All three of WP-1957's reviewers read one element as two
  species, and took the shade for a depth cue. Waiting on a ruling.
- **`atom_labels=True` prints a stacked pair twice.** WP-1957's reviewers saw
  `F4 F4` at one corner of fluorapatite down c. `FigureReport.stacked` already
  finds such pairs, but nothing in `viz/figure3d/` merges their labels.
- **The a and b letters sit under atoms or bonds in a view down c.** WP-1957's
  reviewers, on fluorapatite.
- **At the default probability, `mode="ellipsoid"` draws the atoms as
  pinpricks.** That is physically right at Biso ≈ 1 Å²
  (`structure3d.DEFAULT_PROBABILITY` is 0.50), but WP-1957's reviewers read it
  as a wire model.

### Issue #1057: two ORTEP controls and one outline defect

From the 2026-10-26 issue triage (maintainer's issue, 2026-10-19), first
recorded in WP-1468. A bond half always takes its atom's site colour
(`viz.figure3d.scene.build_scene`), and the renderer has no per-atom draw
style, so a group cannot be drawn as wireframe beside ellipsoids and bonds
cannot all be grey. `outline=True` also inks the near-side edge of a thin
stick, which on a stick is its whole width. Checked against the tree at
c0e32ab29: on COD paracetamol (`tests/data/cod_2104364.cif`, `aniso=True`)
with four site colours set, the bond halves carry exactly those four colours;
`render_structure` has no bond-colour or style parameter; at `stick=0.3,
outline=True` the white H bond halves are drawn with black edges (looked at).
Rechecked at b0c79e12d: still no `restyle` and no bond-colour parameter. The
issue proposes `rx.viz.restyle(g, mask, "wire")` (no glyph, thin lines in the
bond colour, skipped by the outline) and `render_structure(bond_colour=...)`
or a `bond_color` key in the build dict, both carried in `.recipe`. Its claim
that Mercury and Olex2 set a display style per selection is recalled, not
checked; read their manuals before choosing names, as WP-1468's Context
§ What other viewers do did.

### Cluster polyhedra

Anion-centred and cluster polyhedra (OCa₄, B₆, B₁₂) were WP-1466 non-goals.
WP-1468 made the anion-centred ones reachable through the `centres=` and
`ligands=` lists (fluorite draws FCa₄). A cluster polyhedron has no atom at
its centre, which the payload's `center` index cannot say. This waits for a
user to ask for it; nobody has, as of 2026-11-02.

## Non-goals

- Any change to the default polyhedra on the 21 measured phases without
  re-running `docs/wp/1466-measure/measure.py` and saying which row moved.
- The export formats and ambient occlusion: WP-1536, 1537 and 1538.
- Moving the figure into its own package: WP-1505.

## Tasks

Independent; take any.

- [ ] `view="auto"`: put the ranking by `hidden - stacked` to an agent round, and change the default only if it wins
- [ ] The shade on images outside the cell: take the maintainer's ruling on `DIM_BOUNDARY`, then act on it
- [ ] `atom_labels=True` prints a stacked pair once, using `FigureReport.stacked`
- [ ] The cell-axis letters stay clear of atoms and bonds in an axis view
- [ ] The ellipsoid pinpricks: decide between a skill sentence and a default, since the default probability is physically right
- [ ] Issue #1057: a per-atom draw style, a bond colour, and no outline ink on a thin stick, each carried in `.recipe`
- [ ] A cluster polyhedron round no atom (B₆), when a user asks for one

## Acceptance

Per task. A task that moves the default picture says which committed figure
or screenshot moved, and one that touches polyhedra re-runs
`docs/wp/1466-measure/measure.py`.

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_render_structure.py tests/test_gui_server.py
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1468 (closed 2026-11-02), WP-1504 (closed), WP-1957 (closed), and the
  issue #1057.
- Momma, K. & Izumi, F. (2011). VESTA 3. *J. Appl. Cryst.* 44, 1272-1276.
- The Mercury 2022.3 User Guide (CCDC).

## Handover log

- **2026-11-02** — filed at WP-1468's close by a ghostshift runner, from that
  WP's `### Inherited` section and its one partial task. No open WP owns this
  work: WP-1505 moves the figure into its own package and changes nothing on
  its surface, and WP-1536, 1537 and 1538 add export formats and ambient
  occlusion. WP-1468 itself is closed, so a note left there would be lost.
  Next: the label merge or the axis letters, which need no ruling; the shade
  waits on the maintainer, and the `auto` ranking on an agent round.

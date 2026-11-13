# WP-2111 — what the structure figure still misleads a reader with, and the ORTEP controls asked for

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: 1468 (its close, PR #1355, moves these items here)
Priority: P3 2026-11-05 — a view over what the fit already knows; one reading misleads (three reviewers read one element as two species), and the figure's other surfaces work

## Goal

The structure figure stops showing a reader things that are not there: a second species where
there is one, a label printed twice, and axis letters under the atoms. The two ORTEP controls of
issue #1057 exist, and `outline=True` no longer inks a thin stick's whole width.

## Context

**Source.** Issue #1371 carries WP-1468's leftovers. PR #1355 closes WP-1468 and moves them there
so the maintainer can decide where they belong. WP-1468 was about the polyhedra, and most of these
concern the figure as a whole. No open WP owns them: WP-1505 moves the figure into its own
package, and WP-1536, 1537 and 1538 are its export formats and ambient occlusion.

**The code.** `src/rietx/viz/figure3d/` (scene, render, report) over the geometry
`src/rietx/gui/structure3d.py` builds. The skill's figure page is
`docs/skill/rietx/references/api-figure.md`, with two committed copies
(`rietx skill --install . --copy`).

**The readings from WP-1957's reviewers, forwarded by WP-1504.** Rechecked by the issue at
`b0c79e12d`. `DIM_BOUNDARY`, `stacked` and the absence of `restyle` and a bond-colour parameter
were rechecked at `541f0daf7`.

- `view="auto"` ranks by `hidden`, stacking included, so it prefers an oblique view to an axis
  projection. `FigureReport.stacked` (WP-1533) is the part of `hidden` that sits behind an atom of
  the same site, within a quarter of its drawn radius. One cell down a cell axis reads 0.53 hidden
  and 0.53 stacked on HKUST-1, 0.52 and 0.50 on ZSM-5, and 1.00 and 1.00 on YBa₂Cu₃O₇. NAC's
  opening view reads 0.18 and 0.00. The skill's rule already reads `hidden - stacked`. Three blind
  reviewers ranked 15 renderings of refined fluorapatite. The view down c (`hidden` 0.45, nearly
  all of it stacking) came first for two and second for the third, while `auto` picked about
  [2 0 1] (`hidden` 0.024), and all three called it "a tangle". The change moves every default
  `auto` pick.
- `scene.DIM_BOUNDARY` (0.62, `viz/figure3d/scene.py:45`) dims every image outside the cell. All
  three reviewers read one element as two species and took the shade for a depth cue.
- `atom_labels=True` prints a stacked pair twice (`F4 F4` at one corner of fluorapatite down c).
  `FigureReport.stacked` already finds such pairs, and nothing in `viz/figure3d/` merges the labels.
- The a and b letters sit under atoms or bonds in a view down c.
- At the default probability, `mode="ellipsoid"` draws the atoms as pinpricks. That is physically
  right at Biso ≈ 1 Å² (`structure3d.DEFAULT_PROBABILITY` is 0.50), and reviewers read it as a wire
  model.

**Issue #1057 (the maintainer, 2026-10-19).** A bond half always takes its atom's site colour
(`viz.figure3d.scene.build_scene`), and the renderer has no per-atom draw style. So a group cannot
be drawn as wireframe beside ellipsoids, and bonds cannot all be grey. `outline=True` inks the
near-side edge of a thin stick, which on a stick is its whole width. Measured in WP-1468 at
`c0e32ab29`, on COD paracetamol (`tests/data/cod_2104364.cif`, `aniso=True`): with four site colours
set, the bond halves carry those four colours, and at `stick=0.3, outline=True` the white H bond
halves are drawn with black edges. The issue proposes `rx.viz.restyle(g, mask, "wire")` (no glyph,
thin lines in the bond colour, skipped by the outline) and `render_structure(bond_colour=...)` or a
`bond_color` key in the build dict, both carried in `.recipe`. Its claim that Mercury and Olex2 set
a display style per selection is recalled, not checked. Read their manuals before choosing names.

**Cluster polyhedra.** Anion-centred and cluster polyhedra (OCa₄, B₆, B₁₂) were WP-1466 non-goals.
WP-1468 made the anion-centred ones reachable through `centres=` and `ligands=` (fluorite draws
FCa₄). A cluster polyhedron has no atom at its centre, which the payload's `center` index cannot
say. Nobody has asked for one, as of 2026-11-02.

**Two tasks wait on the maintainer's ruling**: the `DIM_BOUNDARY` shade, and whether `view="auto"`
ranks by `hidden - stacked`. Both are in the triage batch of 2026-11-05.

**Tier.** A change to `DIM_BOUNDARY` or to the `auto` ranking moves a default, so it is an `_audit`
row with its evidence. WP-1957's reviewers and the agent round below are that evidence.

### Inherited

- **2026-11-12, from WP-1548 (filed).** WP-1548 adds optional depth cueing (fog toward the
  background) to both renderers. Fog and the `DIM_BOUNDARY` shade both change the far side's
  colour, so a reader could not tell them apart. WP-1548 waits on this WP's ruling on the shade
  (its D6). Whoever brings that ruling to the maintainer should mention that fog is coming.

## Non-goals

- Any change to the default polyhedra on the 21 measured phases without re-running
  `docs/wp/1466-measure/measure.py` and saying which row moved.
- The export formats and ambient occlusion: WP-1536, 1537 and 1538.
- Moving the figure into its own package: WP-1505.

## Tasks

Independent; take any.

- [ ] `view="auto"`: put the ranking by `hidden - stacked` to an agent round, and change the default only if it wins.
- [ ] The shade on images outside the cell: take the maintainer's ruling on `DIM_BOUNDARY`, then act on it.
- [ ] `atom_labels=True` prints a stacked pair once, using `FigureReport.stacked`.
- [ ] The cell-axis letters stay clear of atoms and bonds in an axis view.
- [ ] The ellipsoid pinpricks: decide between a skill sentence and a default, since the default probability is physically right.
- [ ] Issue #1057: a per-atom draw style, a bond colour, and no outline ink on a thin stick, each carried in `.recipe`.
- [ ] A cluster polyhedron round no atom (B₆), when a user asks for one.
- [ ] Skill: the rows in `references/api-figure.md` for the new controls and the `view` rule, then `rietx skill --install . --copy`.

## Acceptance

Per task. A task that moves the default picture says which committed figure or screenshot moved,
and one that touches polyhedra re-runs `docs/wp/1466-measure/measure.py`.

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_render_structure.py tests/test_gui_server.py
npm --prefix gui test && npm --prefix gui run check
```

## References

- Issues #1371 and #1057; WP-1468, WP-1504, WP-1957 (context 4), WP-1533.

## Handover log

- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1371). Checked against the tree at `541f0daf7`: `DIM_BOUNDARY` is 0.62 at `scene.py:45`, and no `restyle` or bond-colour parameter exists under `viz/figure3d/`; no open WP owns it: WP-1468 holds these items on main only until PR #1355 closes it, and the other figure WPs are the package move and the export formats. Next: the batch's two rulings, then any task.

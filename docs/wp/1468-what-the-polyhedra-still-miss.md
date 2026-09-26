# WP-1468 — what the polyhedra still miss, and the controls a chemist would reach for

Milestone: unscheduled · Status: ⬜
Depends on: 1466
Priority: P3 2026-09-26 — a view over what the fit already knows; each miss is a drawing, never a number, and switching the polyhedron off works around it

## Goal

The structure viewer's automatic polyhedra (WP-1466) are right on the 21
phases measured there. This WP collects the cases they are known to miss,
and the controls other viewers give a chemist for them. Each task stands on
its own, so a session can take one.

## Context

WP-1466 decides a centre and its ligands without asking the user. A centre is
a cation: a metal, or a non-metal bonded to a more electronegative one (P2).
A shell ends at Brunner & Schwarzenbach's largest gap (P3), and a shell of 4
to 6 is drawn by default (P5). A split site draws no polyhedron (P9), and two
non-metals closer than `SPLIT_FLOOR` (0.7) of their radius sum are one atom
over two positions (P10). The code is `src/rietx/gui/structure3d.py`;
`docs/wp/1466-measure/measure.py` re-runs the 21-phase default picture that
`tests/data/polyhedra_phases.json` holds.

### What other viewers do

Read 2026-09-26 from each program's manual.

- **VESTA** builds bonds, and so polyhedra, from a minimum and maximum
  distance per species pair. For a split-atom model its manual says the
  minimum "may be positive". P10 is that minimum set from the radii.
- **Mercury** makes every metal a centre and every non-metal a ligand by
  default, and its Central Elements and Ligand Elements buttons change both
  lists. For disorder it reads the file's labels: in a CSD entry the minor
  positions are suppressed and take no part in connectivity.
- **CrystalMaker** also bonds by a distance range per element pair. Since
  version 10 it reads CIF disorder groups and SHELX PART numbers, and shows
  each alternative as a separate structure.

### Disorder

- **A split pair wider than the floor still bonds.** Two O more than
  0.92 Å apart (0.7 × 1.32 Å) get a stick. Hydroxyfluorapatite with its OH
  oxygen 0.48 Å from F has its two mirror O positions 0.96 Å apart, so they
  do.
- **The floor spares every pair with a metal.** On gemmi's covalent radii
  uranyl's U=O is 0.67 of the radius sum, and vanadyl's V=O and titanyl's
  Ti=O 0.72, from literature bond lengths. A partly occupied cation close to
  a partly occupied anion therefore keeps its stick and can enter a shell. No
  measured case.
- **rietx's structure schema has no disorder group.** The CIF carries one
  (`_atom_site_disorder_assembly`, `_atom_site_disorder_group`), and SHELX
  its PART numbers. That is how Mercury and CrystalMaker separate
  alternatives without guessing from distance.
- **An occupancy test is the cheaper half.** Two partly occupied non-metals
  closer than a second, looser bound would be split too. Its bound has to
  sit below a disordered sulfate's S–O at 0.86, and the 0.77-0.81 band
  holds real triple bonds (N≡N, cyanide's C≡N, CO).

### The chemistry the rules miss

- **A cyanide or carbonyl C** bonds the metal and is itself bonded to a more
  electronegative N or O. So it is a cation, and Prussian blue's C-bonded Fe
  gets a shell of N (WP-1466, P2).
- **An arsenic telluride inverts.** On the Pauling scale Te (2.10) is less
  electronegative than As (2.18), so As₂Te₃'s Te would be the cation. No such
  phase was measured.
- **Four electronegativities are unchecked.** Allred (1961, Table 3) has
  none for Te, At, Kr or Xe. The values in `ELECTRONEGATIVITY` are the ones
  usually tabulated, from sources not read here.

### Controls

- **No centre or ligand override.** Mercury's two lists and VESTA's pair
  ranges are how a user fixes the misses above. Here the rule is fixed. A
  control would be a drawing threshold on the query string, like the bond
  tolerance, never in `ProjectDoc` (`gui/CLAUDE.md`).
- **An intermetallic draws nothing** (P2). Daams & Villars (1993) draw every
  atom's environment. Showing one atom's environment on request was WP-1466's
  stated answer, left out of its scope.
- **Anion-centred and cluster polyhedra** (OCa₄, B₆, B₁₂) are WP-1466
  non-goals. An antiperovskite or an oxynitride is read by its anion-centred
  shapes.

### Ties, the cap and the cost

- **Two nearly equal gaps.** Brunner & Schwarzenbach found six structures
  whose largest gap had a near-equal rival, and Daams & Villars resolve such
  a tie by the fewest environment types. Nothing does here. The closest on
  the measured set is fluorapatite's Ca2, 1.24 against 1.14.
- **A large hidden shell can lose its room at the atom cap** (WP-1466, P7).
  The default shells claim room first, and a hidden one that does not fit
  leaves the legend, counted in the payload's note. None did on the measured
  set, where grossular's payload is 383 of 400 atoms.
- **Two rules are written more than once** (WP-1466's second review).
  "Bonded" is tested in `_bonds` for the sticks and again in
  `_cation_sites`, and P10's floor went into both by hand. The client's
  "which atoms are drawn" rule has three copies: `buildScene`, `caption` and
  the zoom fit. The copies agree today; a change to one that misses another
  is how the caption came to count undrawn atoms.
- **Every bond-slider release recomputes the polyhedra.** They read the
  default bond tolerance, never the slider's, so only the sticks need the
  new value. Grossular's whole payload takes 62 ms best of 7 (Apple M4); the
  polyhedra's share of it is not measured.

## Non-goals

- The octant cut-out, Voronoi solid angles, effective coordination numbers
  and CrystalNN, as in WP-1466.
- Any change to the default picture on the 21 measured phases without
  re-running `measure.py` and saying which row moved.

## Tasks

Independent; take any.

- [ ] Disorder groups: a schema field read from the CIF and SHELX, no stick or shell across two groups of one assembly, and a way to show one alternative
- [ ] Split sites with a metal: measure a real case before choosing a rule, since uranyl's U=O sits under the non-metal floor
- [ ] The occupancy test for split pairs wider than the floor, with its bound measured against disordered sulfates and triple bonds
- [ ] Cyanide and carbonyl ligands: find a rule that keeps SiO₄ and PO₄ and gives Prussian blue FeC₆, and measure it on the 21 phases
- [ ] Centre and ligand overrides on the query string, as Mercury's two lists
- [ ] One atom's environment on request, for an intermetallic
- [ ] Anion-centred and cluster polyhedra, if a user asks for them
- [ ] The two-gap tie: find a real case, then decide whether to apply Daams & Villars' rule
- [ ] A hidden shell dropped at the atom cap stays in the legend as unavailable, or the cap stops counting it
- [ ] The polyhedra stop recomputing on a bond-slider release
- [ ] One authority for "bonded" on the server and one for "drawn" on the client
- [ ] A source for the Te, At, Kr and Xe electronegativities

## Acceptance

Per task. Any task that moves the default picture re-runs
`docs/wp/1466-measure/measure.py` and passes
`test_the_default_picture_on_the_measured_phases`.

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_gui_server.py
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1466 and its measurement, `docs/wp/1466-measure/`.
- Momma, K. & Izumi, F. (2011). VESTA 3. *J. Appl. Cryst.* 44, 1272-1276,
  and the VESTA manual, chapter 8.
- The Mercury 2022.3 User Guide (CCDC): Polyhedral Display Options,
  Disordered Structures, Suppressed Atoms.
- CrystalMaker 10 release notes, and "Disordered Sites in CrystalMaker".
- Brunner, G. O. & Schwarzenbach, D. (1971). *Z. Kristallogr.* 133, 127.
- Daams, J. L. C. & Villars, P. (1993). Atomic environment classification of
  the rhombohedral "intermetallic" structure types.
- Allred, A. L. (1961). *J. Inorg. Nucl. Chem.* 17, 215.

## Handover log

- **2026-09-26** — filed from WP-1466's second session, at the maintainer's
  request, as the further work its automatic polyhedra leave. The survey of
  VESTA, Mercury and CrystalMaker was read from their manuals that day.
  *Next:* any one task; the disorder groups carry the most, and need a
  schema decision first.

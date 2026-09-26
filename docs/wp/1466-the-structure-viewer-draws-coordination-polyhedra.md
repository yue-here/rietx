# WP-1466 — the structure viewer draws coordination polyhedra

Milestone: unscheduled · Status: ✅ 2026-09-26 — polyhedra drawn by Brunner &
Schwarzenbach's gap on 21 measured phases, the legend per formula, a split pair
no bond; the further work is WP-1468
Depends on: 1462

## Goal

The structure viewer draws coordination polyhedra. A user who never opens a
setting sees the polyhedra a solid-state chemist would draw first, and no
others (`gui/CLAUDE.md` § Defaults).

## Context

### The renderer it extends

WP-1462 closed on 2026-09-26, and its renderer passed the GPU gate as
partial. The gate ran Direct3D 11 over WARP, Mesa llvmpipe and SwiftShader on
GitHub's runners, with no vendor GPU. Folded from that WP's inherited note
on 2026-09-26.

- **The gate is the probe for acceptance 3.** `1462-spike/gate.py` pins the
  canvas at 720 × 540 CSS px, drives one browser through a fixed script, and
  compares every picture with a reference machine's. A polyhedra case in
  that script covers this WP.
- **A context can come without a multisample buffer.** Firefox on WARP
  granted none, so anything drawn through alpha-to-coverage loses its
  coverage there. The spike's faces blend with ordinary alpha, which does
  not depend on it.
- **A payload draws the same on every machine.** The server pins an
  ellipsoid's free principal axes (`structure3d._pin_axes`).

### Why

The maintainer asked for it on 2026-09-25, because many rietx users are
solid-state chemists who know VESTA. WP-1462's spike tested whether the
new renderer can take polyhedra (its § Polyhedra: one translucent pass of
88 lines, the same in three engines), and the view was split out here as
WP-1462's D8.

### What the spike found

The spike's server stand-in is `docs/wp/1462-spike/payloads.py`, and its
measurements are `gap.py` and `results/shell_gaps.txt` there.

- **The bond rule is not a coordination rule.** Under the viewer's
  radius-sum rule (1.15 × the covalent radii), fluorapatite's P reaches
  4 Ca at 3.1-3.2 Å beside its 4 O, so its first hull had 8 vertices.
- **A ligand rule fixes it.** The spike took a centre's non-metal
  neighbours of another element. It gives PO₄, AlF₆ and CaF₈. gemmi carries
  no electronegativity table and neither does rietx.
- **A shell's size under the bond rule is not a default key.** With every
  site as a centre, LaB6's La has 24 B, NAC's Al 6, Ca 8 and Na 4 F, and
  fluorapatite's P 4 O and both Ca 9. Na's 4 is the covalent cutoff cutting
  a large ionic cation's shell short.
- **The largest distance gap finds the shell.** Sort a site's ligand
  distances and take the largest ratio of one to the one before, among the
  first 13. Na's shell is 7 F from 2.19 to 2.58 Å, then 3.63 Å: a ratio of
  1.41. The ratio is 2.08 after Al's 6 F, 1.98 after P's 4 O and 1.54 after
  NAC Ca's 8 F. Fluorapatite's Ca sites show none (1.14 and 1.15), and
  LaB6's La has 24 B at one distance.
- **A shell is matched by position.** The server can find a contact from a
  translated copy of the centre, so a shell collected by atom index came out
  short on 6 of 18 Ca in NAC.
- **A hull needs care.** A square face comes out as two triangles, so an
  edge is drawn only where its two faces are not coplanar. A shell of fewer
  than four atoms, or a planar one such as CO₃, has no 3D hull.

### What others do

From the programs' manuals and docs, surveyed on 2026-09-25. Where a
survey could not confirm a default from a primary source, it is left out.

- **VESTA** builds a polyhedron from a directed bond search: a central
  species, a ligand species, and a distance range from a pair table. Its
  default range is the radius sum plus a tolerance. Polyhedra are opt-in
  per species. Their colour is the central atom's, with opacity and edges
  set apart. The default polyhedral style keeps atoms and bonds visible.
  Its default boundary mode fetches ligands from outside the drawing box,
  so no polyhedron is cut off.
- **Mercury** declares two element lists, the possible centres and the
  possible ligands.
- **Materials Project** builds its bonded graph with CrystalNN, which
  assigns no cation-cation bonds.
- **Daams & Villars (1993)**, read in full, define an atom's environment by
  the maximum-gap rule of Brunner & Schwarzenbach (1971). The distances to
  all neighbours go in a histogram, and the environment is every atom
  before its largest gap. When that shell encloses another atom, puts an
  atom on a face, or shows no clear gap, they take the maximum convex
  volume instead. That is the largest convex volume around the centre alone
  with every coordinating atom at a vertex. Where two gaps are about equal,
  they choose the reading that keeps the structure's environment types
  fewest. An environment whose atoms all lie on one side of the centre, such
  as the "loose triangle" of S in MoS₂, is irregular and is not a
  polyhedron. Boron's B₁₂ and B₆ clusters have no central atom and are
  drawn as clusters. Their subject is intermetallics, so every species
  counts as a neighbour.

### The phase-set measurement

Measured 2026-09-26 on the stand-in gap measure, with P2 as amended that
day, and re-run the same day under Brunner & Schwarzenbach's window (P3).
The re-run moved three sites' largest gaps and no default picture.
`1466-measure/measure.py` fetches each phase from the Crystallography
Open Database, and `results.txt` beside it holds the run. Its `--fixture`
writes `tests/data/polyhedra_phases.json`, which
`test_the_default_picture_on_the_measured_phases` holds the default to. The
expected picture was written down before the run. Each shell carries its
gap ratio.

| Phase (COD) | Drawn by default | Qualifies, hidden |
|---|---|---|
| LaB6 (test CIF) | none | LaB₂₄ 1.45 |
| NAC (test CIF) | AlF₆ 2.08 | CaF₈ 1.54, NaF₇ 1.41 |
| fluorapatite (test CIF) | PO₄ 1.98 | CaO₉ 1.38, CaO₆F 1.24 |
| spinel MgAl₂O₄ (5000120) | MgO₄ 1.78, AlO₆ 1.73 | none |
| perovskite SrTiO₃ (1512124) | TiO₆ 2.24 | SrO₁₂ 1.73 |
| grossular (9002677, at 103 K) | SiO₄ 1.96, AlO₆ 1.91 | CaO₈ 1.48 |
| rutile (9015662) | TiO₆ 1.76 | none |
| forsterite (9007377) | SiO₄ 1.90, MgO₆ 1.65 and 1.55 | none |
| zircon (9002554) | SiO₄ 2.04 | ZrO₈ 1.78 |
| corundum (1000032) | AlO₆ 1.63 | none |
| fluorite (1000043) | none | CaF₈ 1.91 |
| wurtzite ZnO (2300450) | ZnO₄ 1.63 | none |
| quartz (5000035) | SiO₄ 2.18 | none |
| calcite (2100992) | CaO₆ 1.47 | none; CO₃ is planar |
| gypsum, with H (2300258) | SO₄ 2.37 | CaO₈ 1.61 |
| pyrite (7700358) | FeS₆ 1.52 | none |
| baryte (8107510) | SO₄ 2.31 | BaO₁₂ 1.21 |
| andalusite (9003990) | SiO₄ 1.64, AlO₆ 1.63, AlO₅ 1.68 | none |
| CsCl (9009743) | none | CsCl₈ 1.91 |
| high cristobalite (9008230, at 221 °C) | none: Si's 24 O positions are split sites (P9) | none |
| olivine, Fe 0.1 beside Mg (built on 9007377) | as forsterite, one octahedron per mixed site | none |

## Decisions this WP takes

The maintainer confirmed P1-P8 on 2026-09-26, with three amendments from
a critical pass that day (in P2, P5 and P7), and chose the recommended P9.
The phase-set measurement then changed P2 a second time, and the maintainer
confirmed that too on the same day. The same day the maintainer chose P10
over recording the split anion site as a limit.

- **P1. The server builds the polyhedra.** `/api/structure3d` gains a
  `polyhedra` arm: the centre's atom index, the vertex positions, outward
  triangles and edges. It is chemistry and geometry, and WP-1015's founding
  rule keeps both on the server.
- **P2. A centre is a cation and a ligand is an anion.** Every metal is a
  cation. A non-metal bonded to a more electronegative non-metal is a
  cation too, as Si is in SiO₄, and bonded means the viewer's radius-sum
  rule at its default tolerance. Every other non-metal except hydrogen is
  an anion, and a ligand is an anion of another element. The
  electronegativities are 18 Pauling values. *Checked 2026-09-26:* 14 are
  Allred's (1961, Table 3) to the last digit (H, B, C, N, O, F, Si, P, S,
  Cl, As, Se, Br, I). His table has none for Te, At, Kr or Xe, so theirs
  stay the values usually tabulated, unchecked. This is Mercury's two lists derived
  rather than declared, and CrystalNN's "no cation-cation bonds" carried
  from the metals to the non-metals. An intermetallic therefore gets no polyhedra by
  default, where Daams & Villars would draw every atom's environment.
  Showing one atom's environment on request is the intermetallic answer,
  and is out of scope. The non-metal test is gemmi's `Element.is_metal`,
  which `structure3d.is_metal` already reads.
  *Amended 2026-09-26: hydrogen is never a ligand.* It is a non-metal, so a
  hydroxide's cation reaches it. On brucite from textbook coordinates, Mg
  has 6 O at 2.10 Å and then 6 H at 2.68 Å, and counting H drops the gap
  ratio from 1.80 to 1.28. That is inside P4's undecided window.
  *Amended again 2026-09-26, after the phase-set measurement.* As first
  confirmed, P2 took any non-metal of another element as a ligand, so Si, S
  and P counted as ligands of the metals beside them, and O and F were
  centres. Forsterite's MgO₆ gap fell to 1.26 (Si at 2.69 Å), grossular's
  Ca took 2 Si into a shell of 10, and andalusite's OA and gypsum's water O
  drew OSi₄ and OS₅ by default. Under the rule above these gaps are 1.55-1.65
  and 1.48, and the anion-centred shells are gone. Its known miss is a
  cyanide or carbonyl C, which bonds the metal and is itself bonded to a
  more electronegative N or O, so Prussian blue's C-bonded Fe would get N.
- **P3. The shell ends at the largest gap in the ligand distances,** as
  Daams & Villars apply Brunner & Schwarzenbach. The gap is measured the way
  Brunner & Schwarzenbach measure it.
  *Read 2026-09-26.* They judge a gap by the quotient of the two distances
  bounding it, which is the spike's ratio. They take the largest gap of the
  whole sequence, computed out to at least three times the shortest
  distance. So the window is theirs too: every ligand out to three times
  the centre's shortest distance (`SHELL_REACH`), with no cap on the
  shell's size. The spike had searched the first 13 ligands, and that hid
  two shells. LaB6's La has 24 B and then a gap of 1.45, and high
  cristobalite's Si has 24 O positions and then 2.25. They also found a
  clear largest gap in about 90 % of their structures. The six without one
  had two gaps of about equal size.
- **P4. A shell is drawn only when it is a polyhedron.** It needs 4 or more
  ligands, the centre strictly inside the hull, every ligand at a hull
  vertex (Daams & Villars' convex-volume condition), and a clear gap. The
  gap threshold is 1.15, the smallest largest gap in Brunner &
  Schwarzenbach's survey (β-Pu averaged over its sites; each single site's
  was larger). On 21 phases (§ The phase-set measurement) every shell's gap
  is 1.21 or more, and the default picture is the same for any threshold up
  to 1.47. *Amended 2026-09-26:* it was first measured as "every site with
  no shell scores 1.00", but the two such sites scored 1.00 only under the
  spike's window (P3).
- **P5. By default, shells of 4 to 6 ligands are drawn.** Tetrahedra and
  octahedra are the framework a chemist reads first. Shells of 7 or more
  qualify and start hidden, because with them NAC's cell fills with
  overlapping polyhedra. On the measured set the default draws the table in
  § The phase-set measurement. The legend switches polyhedra per formula.
  *Amended 2026-09-26 from "7 and 8"*, so a perovskite's 12-coordinate A
  site is covered. *Amended again 2026-09-26, from "per centre species".*
  The default is per shell size and a formula fixes the size, so every
  polyhedron under one switch shares its default. A per-species switch over
  a CaO₆ drawn and a CaO₈ hidden read as on, and off then on drew both,
  with no way back. A three-state species switch (the WAI-ARIA mixed
  checkbox) restores the default but never shows the CaO₈ alone. Per
  formula costs one extra button where a species has two shapes:
  fluorapatite's Ca and andalusite's Al on the measured set.
- **P6. The look follows VESTA, except inside a polyhedron.** Faces take the
  centre's colour at alpha 0.55, and edges a darker ink as WP-1462's D9
  quads. The centre atom stays. The sticks from the centre to its ligands
  are hidden, where VESTA keeps them. The gap shell and the bond rule can
  disagree (Na: 4 sticks, 7 vertices), and drawing both shows the
  contradiction.
- **P7. A polyhedron is never cut off.** Its ligands are drawn as atoms even
  outside the cell, as VESTA's default boundary mode does. The server adds
  them as partners. *Amended 2026-09-26:* the viewer draws at most
  `MAX_ATOMS` (400) atoms and trims partners past it, so a polyhedron that
  loses a vertex to that cap is not drawn, and the payload's note counts it.
- **P8. Polyhedra show in ball mode and hide in ellipsoid mode.** Faces
  would cover the ADPs the ellipsoid mode exists to show. One toggle
  overrides either.
- **P9. A split site draws no polyhedron.** *Added 2026-09-26.* Atoms at one
  position count once, so a mixed site draws one polyhedron in the first
  species' colour. A shell holding two ligands closer to each other than to
  the centre is a split site, and it is not drawn. A site with vacancies
  and no split still draws. Daams & Villars excluded every partly occupied
  point set, which would lose each BO₆ of an oxygen-deficient perovskite.
  Measured on two phases. High cristobalite's O is split six ways at 1/6,
  and the split rule turns Si's shell of 24 O positions away. (The spike's
  window had turned it away by the gap first.) An olivine with Fe beside Mg
  on both M sites drew one octahedron per site.
- **P10. Two non-metals closer than 0.7 of their radius sum are one atom
  over two positions.** *Added 2026-09-26.* No stick joins them, and
  neither makes the other a cation (`SPLIT_FLOOR`). VESTA's manual has the
  user raise a pair's minimum bond length for a split-atom model; this sets
  it from the radii. Mercury and CrystalMaker separate alternatives by the
  file's disorder groups, which rietx's schema does not carry. Every stick on
  the measured set is 0.856 of its radius sum or more (baryte's S–O), and
  the shortest real bonds between non-metals are 0.77 (N≡N, NO⁺). The split
  pairs sit below: hydroxyfluorapatite's O/F at 0.39, and high cristobalite's
  O pairs at 0.34-0.68, which drew O–O sticks until now. A pair with a metal
  keeps the 0.4 Å minimum alone, because uranyl's U=O is 0.67 and vanadyl's
  and titanyl's 0.72. The default picture did not move.

## Where it will bite

The further work these limits suggest is filed as
[WP-1468](1468-what-the-polyhedra-still-miss.md).

- **The threshold has no measured negative.** Under Brunner &
  Schwarzenbach's window every site on the measured set has a gap of 1.21
  or more, so 1.15 rests on their survey. The default picture does not
  depend on it.
- **Two nearly equal gaps.** Brunner & Schwarzenbach found this in six of
  their structures, and Daams & Villars resolve such a tie by the fewest
  environment types. None arose on the measured set: the closest is
  fluorapatite's Ca2, whose largest gap is 1.24 against 1.14 for the next.
- **A cyanide or a carbonyl** draws the wrong shell (P2).
- **An arsenic telluride would invert.** On the Pauling scale Te (2.10) is
  less electronegative than As (2.18), so As₂Te₃'s Te would be the cation
  and As its ligand. No such phase was measured.
- **A split pair wider than the floor still bonds** (P10). Two O more than
  0.92 Å apart get a stick. Hydroxyfluorapatite with its OH oxygen 0.48 Å
  from F has its two mirror O positions 0.96 Å apart, so they do. The F no
  longer makes that O a cation.
- **A large hidden shell can lose its room at the atom cap.** A shell of 24
  needs up to 24 partner atoms. The shells drawn by default claim room first,
  so the default picture keeps its polyhedra. A hidden one dropped at the cap
  leaves the legend, and the payload's note counts it (P7). None dropped on
  the measured set, where grossular's payload is 383 of 400 atoms.
- **Every fetch recomputes the polyhedra**, so each release of the bond
  slider pays the search again: the review measured 75-85 ms on grossular.
  The probability control does not refetch.
- **Translucency ordering** holds while polyhedra do not interpenetrate
  (WP-1462 § Polyhedra).

## Non-goals

- Cluster polyhedra (B₆, B₁₂), anion-centred polyhedra (OCa₄), and the
  all-atom environments of intermetallics.
- The octant cut-out, and any rule heavier than the gap (Voronoi solid
  angles, effective coordination numbers, CrystalNN).
- A bond rule built on the gap. The bond tolerance stays as it is.

## Tasks

- [x] The maintainer confirms P1-P8, and this file records which (2026-09-26: all, with amendments to P2, P5 and P7, and P9 added)
- [x] Read Brunner & Schwarzenbach (1971) (the maintainer supplies it) and set P3's gap measure to theirs, then re-run `1466-measure/measure.py` (2026-09-26: the measure was theirs, the window was not; P3)
- [x] Read Allred (1961) (the maintainer supplies it) and check `structure3d.ELECTRONEGATIVITY`'s 18 values against it (2026-09-26: 14 match, and his table has none for the other four; P2)
- [x] Measure P4, P5 and P9 on the wider phase set, a disordered phase among it, and record the threshold and the table (2026-09-26, on the stand-in gap measure: § The phase-set measurement)
- [x] Server: the `polyhedra` arm, the ligand rule, the gap shell, the polyhedron conditions and the vertex partners, with tests in `tests/test_structure3d.py` (2026-09-26; the gap measure is the stand-in until task 2, and `POLYHEDRON_GAP` is measured at 1.15)
- [x] Renderer: the translucent pass, the edges, and hover on a polyhedron (centre, ligand count, mean distance); a polyhedra case in `1462-spike/gate.py`'s script (2026-09-26; acceptance 3 in `1466-measure/results_*.txt`)
- [x] GUI: the per-species toggles, P5's and P8's defaults, and the caption saying what is drawn (2026-09-26)
- [x] The legend switches per formula, and a hidden polyhedron's own partner atoms hide with it (2026-09-26; P5)
- [x] The split floor between non-metals, for the sticks and the cation test (2026-09-26; P10)
- [x] File the further work as WP-1468 (2026-09-26)
- [x] Docs: the structure viewer paragraphs in `gui/CLAUDE.md` and the GUI guide (2026-09-26)

## Acceptance

1. **Defaults:** on the measured phase set, the default picture draws the
   polyhedra this file's table lists for each phase, and no others.
2. **Every drawn polyhedron is one:** a test holds each to P4.
3. **Browsers:** Chromium, WebKit and Firefox draw it the same, and a
   trackball drag holds a p95 frame of 17.7 ms or less.

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_gui_server.py
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Daams, J. L. C. & Villars, P. (1993). Atomic environment classification of
  the rhombohedral "intermetallic" structure types. The maintainer's copy
  (`rietx-refs-misc`) does not carry the journal details.
- Allred, A. L. (1961). Electronegativity values from thermochemical data.
  *J. Inorg. Nucl. Chem.* 17, 215. Read in full (the maintainer's copy in
  `rietx-refs-misc`).
- Brunner, G. O. & Schwarzenbach, D. (1971). *Z. Kristallogr.* 133, 127.
  Zur Abgrenzung der Koordinationssphäre und Ermittlung der Koordinationszahl
  in Kristallstrukturen. The maximum-gap rule, read in full (the maintainer's
  copy in `rietx-refs-misc`).
- Momma, K. & Izumi, F. (2011). VESTA 3. *J. Appl. Cryst.* 44, 1272-1276,
  and the VESTA manual, chapters 8 and 12.
- Pan, H. et al. (2021). *Inorg. Chem.*, doi:10.1021/acs.inorgchem.0c02996,
  for CrystalNN. Not read here.
- WP-1462 and its spike, `docs/wp/1462-spike/`.

## Handover log

### 2026-09-26 (2nd session) — the gap rule is Brunner & Schwarzenbach's, the legend switches per formula, a split pair is no bond, and the WP closes

Both papers are read, and the viewer follows them. Brunner & Schwarzenbach
measure a gap exactly as the spike did, by the ratio of the two distances
around it. They look further, though: the whole sequence out to three times
the nearest distance. That uncovered two shells the old 13-ligand search had
hidden, and no default picture changed on the 21 phases. Allred's table
confirms 14 of the 18 electronegativities and has none for the other four. The
legend has one button per formula, so a species drawn in part can go back to
its default. A hidden polyhedron no longer leaves its ligands behind as stray
atoms. The maintainer ruled on the split anion site: two non-metals closer
than 0.7 of their radius sum are one atom over two positions, never a bond
(P10). The WP closes, and what the automatic polyhedra still miss is filed as
WP-1468.

*Decided.* The legend's granularity (the maintainer said "use best practice").
One button per formula, because P5's default is per shell size and a formula
fixes the size. A three-state species button (the WAI-ARIA mixed checkbox)
restores a partial default but can never show a CaO₈ alone. Then P10, after a
survey of what VESTA, Mercury and CrystalMaker do (recorded in WP-1468), and
the further work filed at the maintainer's request.

*Done.*

- `structure3d.SHELL_REACH` = 3: every ligand out to three times the
  centre's shortest distance, and no cap on the shell. The orbit grows once
  when a large cation's window passes 6 Å. The twin merge is a KD-tree pair
  query, since the uncapped window made the old loop quadratic.
- `vertex_only` on an atom the payload carries only for a polyhedron. The
  client draws it and counts it in the caption only while a polyhedron that
  uses it is drawn. The zoom fits the atoms the default picture can draw, and
  the depth range holds every atom. Shells drawn by default claim room under
  the 400-atom cap first.
- The legend: `polyhedraLegend` gives one entry per formula, and
  `shownPolyhedra` takes a map keyed by formula.
- `structure3d.SPLIT_FLOOR` = 0.7, in `_bonds` and in `_cation_sites`,
  between two non-metals only (P10).
- `ELECTRONEGATIVITY`'s comment says which values are Allred's.
- `measure.py`'s own shell reader uses the new window, and `results.txt` is
  the re-run.
- The polyhedra are staged in `docs/releases/1.5.1.md`, which the first
  session had missed.
- WP-1468 filed, with its row and ROADMAP's cap 852 -> 854.

*Measured* (Apple M4, macOS; `[dev]` venv plus playwright, node 22.15.0):

- The window moved three sites' largest gaps and no default picture.
  LaB6's La: 24 B, then ×1.45, now a hidden LaB₂₄. CsCl's Cs: ×1.91,
  where the 6 Å pad read ×1.68. High cristobalite's Si: 24 O positions,
  then ×2.25, turned away by P9, its first measured case. Refetching the 17
  COD entries rewrote the fixture byte for byte, and P10 left `results.txt`
  byte for byte too.
- Stray atoms, with no stick and no face, from hidden polyhedra: at the
  default bond tolerance NAC 12 F and baryte 4 O, on main too. At 1.00,
  LaB6 102 B, fluorite 56 F, NAC 36, CsCl 26, grossular 24, baryte 16,
  fluorapatite 14 and gypsum 6.
- The zoom fit at a bond tolerance of 1.00, before its fix: LaB6 and CsCl
  drawn at half size, fluorite ×1.50. No phase moved at the default 1.15.
- Build time, best of 7 against main: the same within noise on 20 phases,
  and LaB6 4.7 to 7.3 ms (it now builds eight polyhedra). With the old
  twin loop LaB6 took 38 ms.
- P10's evidence, as length over covalent radius sum: every stick on the 21
  phases is 0.856 or more (baryte's S–O); N≡N and NO⁺ are 0.77 and cyanide
  0.81. The split pairs are 0.39 (hydroxyfluorapatite's O/F) and 0.34-0.68
  (cristobalite's O). Uranyl's U=O is 0.67 and vanadyl's and titanyl's 0.72,
  from literature bond lengths, which is why metal pairs are exempt.
- Allred (1961), Table 3: H, B, C, N, O, F, Si, P, S, Cl, As, Se, Br and I
  match. Te, At, Kr and Xe are absent from it.
- A NAC probe in Chromium: the legend reads CaF₈, AlF₆, NaF₇. CaF₈ on and
  off again gives back the default picture to 0.0 levels.
- Counts: the fast selection is 6366 passed and 140 skipped. Main is the
  tree the first session counted at 6362 and 140, so +4: the window test
  and three for P10. `tests/test_structure3d.py` 87 passed and 1 skipped.
  GUI vitest 571 passed in 24 files (+3). `tests/test_structure3d_browser.py`
  5 passed. The full selection did not run: the change is GUI and viewer
  code and moves no refinement number.
- After #468 (WP-1326's satellites) merged, main was merged in at
  `a15959be`. The two share no file; #468's schema change is one optional
  field, `Phase.propagation_vector`, that the viewer does not read. The
  merged tree's fast selection is 6426 passed and 145 skipped, the same in
  two runs.

*Review.* Two `/code-review high --fix` passes.

- The first found eight and fixed the caption's image count and a stale
  comment. I took two of its declines as well: the zoom fit, and a stale test
  comment.
- The second found seven and fixed a clipping bug my zoom fix had made (the
  depth range came from the trimmed set), a per-site ligand mask and a
  comment. I took its docstring finding.
- Declined, with reasons: a twin of a twin joins one cluster (needs three
  ligands each within 0.01 Å of the next); a large cation grows the orbit for
  every centre (the build times above); `measure.py` asserts rather than
  widens its 12 Å grid; the per-site shortest distance is computed twice.
- Declined into WP-1468: "bonded" is tested twice on the server and "drawn"
  three times on the client. The two floors agree, since the smallest
  non-metal radius sum (H–H, 0.62 Å) puts the split floor at 0.43 Å, above
  the 0.4 Å minimum.

*Gotchas.*

- `gui/CLAUDE.md` sits at its line cap. The legend rule took one line, and
  the paragraph above it lost two facts that live in `_cation_sites` and
  `measure.py`.
- Any edit under `gui/src`, a test file included, changes the dist's
  fingerprint. Rebuild after the last edit, or `test_gui_dist.py` fails.
- A test that compares against `s3.SPLIT_FLOOR` stays green when the floor
  breaks. The cristobalite assertion reads the pairs without it.

*Next.* None here: the WP closes. WP-1468 carries the further work, each task
independent. Its disorder-group task carries the most and needs a schema
decision first.

### 2026-09-26 — the viewer draws coordination polyhedra, and the ligand rule became cations and anions

The structure viewer now draws coordination polyhedra. A user who never opens
a setting sees the tetrahedra and octahedra a solid-state chemist draws first,
and nothing else, on all 21 phases measured. The measurement also overturned
part of the rule the maintainer had confirmed that morning. Counting every
non-metal as a ligand let Si, S and P join the shells of the metals beside
them, and let oxygen centre shapes of its own. The rule is now "a centre is a
cation, a ligand is an anion", and the same test removed a sibling defect: the
viewer's sticks joined Mg to Si and Ca to P. What is left is one small
decision about the legend, and two papers the maintainer is supplying.

*Decided.* The maintainer confirmed P1-P8 with three amendments (hydrogen is
never a ligand, shells of 7 or more start hidden, a polyhedron that loses a
vertex to the atom cap is not drawn), added P9 (split sites), and then
confirmed the anion rule for P2 after the phase-set measurement. The
electronegativity table and the gap measure are the two open items (Tasks).

*Done.*

- Server: `/api/structure3d` carries `polyhedra`, built by
  `structure3d._polyhedra` over `_orbit`'s images, with `_cation_sites`,
  `is_ligand`, `shell_gap` and `POLYHEDRON_GAP` = 1.15.
- Measurement: `1466-measure/measure.py` fetches 17 COD entries, measures the
  gaps, and writes `tests/data/polyhedra_phases.json` with the expected
  picture written before the run (§ The phase-set measurement).
- Client: a translucent face pass in `gl3d.ts`, edges as D9 quads, hover on a
  face, one switch per mode and one legend button per centre species, and the
  caption. The dist is rebuilt.
- Sticks: no stick joins a metal to a cation, the metal–metal rule widened.
- Acceptance 3: `gate.py` takes a polyhedra picture, and
  `1466-measure/engines.py` compares the engines and times a drag.
- Docs: the GUI guide's 3D view section and three rules in `gui/CLAUDE.md`.

*Measured* (Apple M4, macOS; `[dev]` venv plus playwright 1.63 with
Chromium 153, Firefox 155 and WebKit 26.6):

- Before the anion rule, forsterite's MgO₆ passed at a gap of 1.26 because Si
  sat at 2.69 Å, grossular's Ca took 2 Si into a 10-shell at 1.22, and
  andalusite and gypsum drew OSi₄ and OS₅ by default. After it the gaps are
  1.55-1.65 and 1.48, and no anion centres anything. Every real shell's gap
  is 1.21 or more; the two sites with none score 1.00.
- Hydrogen counted as a ligand drops brucite's Mg gap from 1.80 to 1.28.
- The radius-sum sticks drew 36 Mg–Si in forsterite (2.69-2.79 Å), 38 Ca–P in
  fluorapatite, 90 Ca–Si in grossular and 16 Ca–S in gypsum.
- Build time for NAC, best of 7: 9.8 ms without polyhedra, 21.1 ms with.
- Engines: the polyhedra picture differs from Chromium's by 0.00 levels in
  Firefox and WebKit; the largest difference of any picture is 0.09 levels.
- Drag frame gap p95 with all 34 of NAC's polyhedra on: Chromium 16.9-18.3 ms
  over six runs, Firefox 17.0-18.0, WebKit 16.9-17.6 on 4-9 frames. With them
  off: 16.8-17.4, 17.0-18.0 and 16.0-17.0. No long animation frame in
  Chromium either way. Acceptance 3's 17.7 ms bar is met in Chromium in four
  of six runs and in Firefox in one of six, with or without polyhedra, so it
  measures the engines' pacing at 60 Hz rather than the face pass. WebKit's
  drag ends in too few frames to read.
- The transparent export: the switch adds 61 347 translucent pixels (1.15 %
  of 5.3 Mpx) and 1 400 with the faces' alpha forced to 0.
- Counts: `tests/test_structure3d.py` 37 passed and 1 skipped on main,
  83 and 1 now (+46: seven ligand cases, 21 measured phases, and the rules
  one test each); `tests/test_structure3d_browser.py` 4 to 5 passed (with
  playwright in the venv; without it the module is one skip); GUI vitest 568
  passed in 24 files under node 22.15.0, +7 (six unit, one component), the
  561 before it derived from the first run. The fast selection on **main
  merged into this branch** (main at `ee2a027a`) is 6362 passed and 140
  skipped. The full selection did not run: the change is GUI and viewer
  server code and moves no refinement number.

*Gotchas.*

- The screen cannot prove a face painted: the switch also moves the edges and
  the sticks, and the picture changed by 1.42 levels with alpha 0. The
  browser test reads translucent pixels in the transparent export instead.
- `gate.py`'s pictures now include the default AlF₆ octahedra, so a gate run
  compared with WP-1462's reference Mac pictures will differ on every ball
  picture. Engine-against-engine on one machine is what `engines.py` reads.
- Cyanide and carbonyl ligands are a known miss of the anion rule.
- `/code-review high --fix` made six changes, landed as one commit:
  deuterium takes hydrogen's electronegativity, an unparsed species (`X`) is
  no ligand, a tighter translation grid in `_orbit` (checked: a centre in
  [0, 1 + tol) needs at most 1 + ⌊R·|a*| + tol⌋), ligand rows cached per
  element, `_cation_sites` taking the orbit whole, and a spacing fix. The
  measurement's output is unchanged. It declined three, recorded under
  § Where it will bite. Its claim that the probability control refetches is
  wrong: the probability rescales on the client, and a vitest pins that.

*Next.*

1. Decide the legend's switch for a species whose shells are only partly
   drawn by default (§ Where it will bite). One button per formula instead
   of per species is the fix I would make.
2. When Brunner & Schwarzenbach (1971) arrives, set `shell_gap` to their
   measure and re-run `1466-measure/measure.py`. If the table moves, the
   fixture's expected column stays and the threshold is re-read.
3. When Allred (1961) arrives, check the 18 values in
   `structure3d.ELECTRONEGATIVITY` and drop the "not yet checked" note.
4. Then the WP closes, with the split-site and cyanide cases left as
   recorded limits unless the maintainer wants either fixed.

- **2026-09-25** — filed from WP-1462's session as its D8, after the
  maintainer asked for polyhedra and for good defaults. The spike's
  measurements are WP-1462's. Daams & Villars (1993) was read in full, and
  the survey of VESTA, Mercury and Materials Project came from their docs.
  *Next:* the maintainer confirms P1-P8 and supplies Brunner &
  Schwarzenbach (1971).

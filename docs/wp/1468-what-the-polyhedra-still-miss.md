# WP-1468 — what the polyhedra still miss, and the controls a chemist would reach for

Milestone: unscheduled · Status: ✅ 2026-11-02 — closed: 14 of 15 tasks landed, the 15th in part (PR #1342 the last); cluster polyhedra, the readings from WP-1504 and issue #1057 moved to issue #1371, now WP-2111
Track: Render what the fit already knows
Depends on: 1466

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
  do. *Superseded in part 2026-09-28:* a pair of partly occupied non-metals
  closer to each other than to an atom both are bonded to gets no stick
  (`structure3d.one_atom`, P9's test). A pair with no such neighbour still
  bonds: Prussian blue's C and a vacancy's water O (COD 4343748), 1.025 Å
  apart.
- **The floor spares every pair with a metal.** On gemmi's covalent radii
  uranyl's U=O is 0.67 of the radius sum, and vanadyl's V=O and titanyl's
  Ti=O 0.72, from literature bond lengths. A partly occupied cation close to
  a partly occupied anion therefore keeps its stick and can enter a shell. No
  measured case. *Measured 2026-09-28:* hydrated β-alumina's Li and a water O
  (COD 1529595) at 0.32 of the radius sum, and Ag β-alumina's Ag and O4
  (2105331-2105335) at 0.35 and 0.59-0.70. Real bonds start at 0.65 (U≡N)
  and 0.67 (uranyl), and a disordered uranyl's minor part (1508149) sits at
  0.70. A floor at 0.5 landed for pairs with a metal; the rest need the
  file's disorder groups, which 1508149 declares.
- **rietx's structure schema has no disorder group.** The CIF carries one
  (`_atom_site_disorder_assembly`, `_atom_site_disorder_group`), and SHELX
  its PART numbers. That is how Mercury and CrystalMaker separate
  alternatives without guessing from distance. *Resolved 2026-09-28:*
  `Atom.disorder_assembly` and `Atom.disorder_group`, read and written with
  the CIF (SCHEMA_VERSION 0.34), and read by the viewer.
- **An occupancy test is the cheaper half.** Two partly occupied non-metals
  closer than a second, looser bound would be split too. Its bound has to
  sit below a disordered sulfate's S–O at 0.86, and the 0.77-0.81 band
  holds real triple bonds (N≡N, cyanide's C≡N, CO). *Measured 2026-09-28:
  no such bound exists.* Split O pairs sit 0.787 of their radius sum apart
  in α-K₂SO₄ (COD 1000049) and 0.89-0.99 in orientationally disordered
  NaNO₃ (COD 8103616, 9007558-9007567), so every bound that spares the
  triple bonds misses them. Occupancy cannot separate them either: a
  sulfate at half occupancy sums to 1 as two alternatives do. Each of those
  pairs sits 19.6-32° apart round a metal both are bonded to, against 60°
  in a real three-membered ring, and that test is what landed.

### The chemistry the rules miss

- **A cyanide or carbonyl C** bonds the metal and is itself bonded to a more
  electronegative N or O. So it is a cation, and Prussian blue's C-bonded Fe
  gets a shell of N (WP-1466, P2). *Resolved 2026-09-28* by a donor rule and
  a screen (Tasks). Measured on COD 4002391, the miss was worse than this
  said: Cu₃[Co(CN)₆]₂ drew CoN₆ by default, from the N 3.03 Å out.
- **An arsenic telluride inverts.** On the Pauling scale Te (2.10) is less
  electronegative than As (2.18), so As₂Te₃'s Te would be the cation. No such
  phase was measured.
- **Four electronegativities are checked second-hand.** Allred (1961,
  Table 3) has none for Te, At, Kr or Xe. *Superseded in part 2026-10-03:*
  the four values in `ELECTRONEGATIVITY` (Te 2.10, At 2.20, Kr 3.00,
  Xe 2.60) agree with the Pauling-scale columns of the CRC Handbook (84th
  ed., 2003, § 9, citing Pauling 1960 and Allen 1989), WebElements and
  Lange's Handbook, as Wikipedia's "Electronegativities of the elements
  (data page)" quotes them. No source disagrees, and Lange has no Kr. The
  2026-09-28 note named Allen & Huheey (1980) for Kr and Xe from memory;
  none of the three handbooks cites it, so it is not needed. Neither
  Pauling (1960) nor Allen & Huheey (1980) is in the maintainer's corpus
  (searched 2026-10-03), and no handbook was opened.

### Controls

- **No centre or ligand override.** Mercury's two lists and VESTA's pair
  ranges are how a user fixes the misses above. Here the rule is fixed. A
  control would be a drawing threshold on the query string, like the bond
  tolerance, never in `ProjectDoc` (`gui/CLAUDE.md`). *Resolved
  2026-09-28:* `centres=` and `ligands=`.
- **An intermetallic draws nothing** (P2). Daams & Villars (1993) draw every
  atom's environment. Showing one atom's environment on request was WP-1466's
  stated answer, left out of its scope. *Resolved 2026-09-28:* through the
  lists, and a double-click for one atom.
- **Anion-centred and cluster polyhedra** (OCa₄, B₆, B₁₂) are WP-1466
  non-goals. An antiperovskite or an oxynitride is read by its anion-centred
  shapes. *Resolved in part 2026-09-28:* anion-centred ones come through the
  lists. A cluster polyhedron has no atom at its centre, which the payload's
  `center` index cannot say. *Moved 2026-11-02* to issue #1371, to wait there for
  a user's request.

### Ties, the cap and the cost

- **Two nearly equal gaps.** Brunner & Schwarzenbach found six structures
  whose largest gap had a near-equal rival, and Daams & Villars resolve such
  a tie by the fewest environment types. Nothing does here. The closest on
  the measured set is fluorapatite's Ca2, 1.24 against 1.14. *Measured
  2026-09-28:* over 159 COD files, 38 polyhedra have a second gap that
  Brunner & Schwarzenbach's own Table 1 would call approximately equal
  (logarithm at least 0.70 of the largest's, Ni₂In's least tie). COD
  1509685's Ag2 closes after 6 at 1.166 against 1.152 after 4, both default
  sizes. Daams & Villars' tie rule is declined: it is a hand rule for
  intermetallic structure types, with no number for "practically equal",
  and it chooses by the classification's economy. The rival is reported
  instead (`structure3d.rival_gap`).
- **A large hidden shell can lose its room at the atom cap** (WP-1466, P7).
  The default shells claim room first, and a hidden one that does not fit
  leaves the legend, counted in the payload's note. None did on the measured
  set, where grossular's payload is 383 of 400 atoms. *Resolved 2026-09-28:*
  `polyhedra_dropped`, and a greyed legend button.
- **Two rules are written more than once** (WP-1466's second review).
  "Bonded" is tested in `_bonds` for the sticks and again in
  `_cation_sites`, and P10's floor went into both by hand. The client's
  "which atoms are drawn" rule has three copies: `buildScene`, `caption` and
  the zoom fit. The copies agree today; a change to one that misses another
  is how the caption came to count undrawn atoms. Since WP-1470
  (2026-09-27), `scene.py`'s `build_scene` holds two more copies. *Resolved
  2026-09-28:* `structure3d.bonded`, and `drawnWith` with its twin
  `drawn_with`.
- **Every bond-slider release recomputes the polyhedra.** They read the
  default bond tolerance, never the slider's, so only the sticks need the
  new value. Grossular's whole payload takes 62 ms best of 7 (Apple M4); the
  polyhedra's share of it is not measured. *Measured 2026-09-28:* 25.9 of
  62.7 ms, best of 7, and 17.8 of 51.5 ms once the position keys were rounded
  as arrays. Every other measured phase builds in 28 ms or less.

### The scene rules have a Python twin

WP-1470 (2026-09-27) ported `buildScene`, `shownPolyhedra`,
`lookFrom`/`axisView` and the shaders' `LOOK` to
`rietx.viz.figure3d.scene`, for `rietx.viz.render_structure`.
`tests/data/gui/scene_cases.json` holds the two equal. A task that changes
what `buildScene` draws (a vertex rule, a new toggle, a changed default)
edits `scene.py` in the same commit. It then runs
`tests/test_render_structure.py`, which rewrites the corpus, and
`npm --prefix gui test`. A rule that moves the default picture also moves
`render_structure`'s, and `test_structure3d_browser.py`'s parity row (bar
2.0 levels, measured 1.06) compares the two pictures. The corpus test
replays the rules over the committed payloads and never rebuilds them, since
`build()`'s order moves with the platform. A new payload field rewrites the
file by itself. A change to `build()` that adds no field does not, so delete
the file and run the test to refresh the payloads.

## Non-goals

- The octant cut-out, Voronoi solid angles, effective coordination numbers
  and CrystalNN, as in WP-1466.
- Any change to the default picture on the 21 measured phases without
  re-running `measure.py` and saying which row moved.

## Tasks

Independent; take any.

- [x] Disorder groups: a schema field read from the CIF and SHELX, no stick or shell across two groups of one assembly, and a way to show one alternative (2026-09-28: `Atom.disorder_assembly`/`disorder_group` from the CIF, which is where SHELXL writes PART; no SHELX reader exists to read them from. `disorder=major` draws each assembly's most occupied group)
- [x] Split sites with a metal: measure a real case before choosing a rule, since uranyl's U=O sits under the non-metal floor (2026-09-28: measured on four COD families, Context § Disorder; `METAL_SPLIT_FLOOR` = 0.5, a quarter below the shortest real bond)
- [x] The occupancy test for split pairs wider than the floor, with its bound measured against disordered sulfates and triple bonds (2026-09-28: measured, no bound exists; P9's angle test landed for the sticks instead, Context § Disorder)
- [x] Cyanide and carbonyl ligands: find a rule that keeps SiO₄ and PO₄ and gives Prussian blue FeC₆, and measure it on the 21 phases (2026-09-28: a donor is a ligand, and an atom behind a bonded ligand is screened. The 21-phase default picture is unchanged; two hidden gaps moved, pyrite 1.52 → 1.60 and LaB6 1.45 → 1.90)
- [x] Centre and ligand overrides on the query string, as Mercury's two lists (2026-09-28: `centres=` and `ligands=`, element lists that replace the rule, and the `round` and `corners` rows under `drawing`)
- [x] One atom's environment on request, for an intermetallic (2026-09-28: a double-click on an atom draws its shell among every element alone, and an element's environments come through the lists; Cu₃Au draws AuCu₁₂ and CuAu₄Cu₈)
- [~] Anion-centred and cluster polyhedra, if a user asks for them (2026-09-28: anion-centred ones come through the lists, as fluorite's FCa₄. A cluster polyhedron round no atom, B₆, does not; 2026-11-02: that half moved to issue #1371)
- [x] The two-gap tie: find a real case, then decide whether to apply Daams & Villars' rule (2026-09-28: found, COD 1509685's Ag2 and 37 more; the rule declined and the rival reported in the hover, Context § Ties)
- [x] A hidden shell dropped at the atom cap stays in the legend as unavailable, or the cap stops counting it (2026-09-28: the payload's `polyhedra_dropped` lists each by site and ligands, and the legend greys a formula that has nothing else to draw. The cap still counts every shell: it bounds what the viewer draws)
- [x] The polyhedra stop recomputing on a bond-slider release — declined on the record 2026-09-28. The recompute is kept and made cheaper (Context). A memo would be keyed on the phase and on every rule constant, and one left out of the key serves a stale picture
- [x] One authority for "bonded" on the server and one for "drawn" on the client (2026-09-28: `structure3d.bonded`, `drawnWith` and its twin `drawn_with`)
- [x] A source for the Te, At, Kr and Xe electronegativities (2026-10-03: three handbooks agree, read second-hand, Context; the `ELECTRONEGATIVITY` comment says so)
- [x] An ellipsoid figure from a CIF read with defaults says it drew spheres (#1056; 2026-11-01: `CIF_ANISO_COLLAPSED` info from the reader counts the collapsed sites, `FigureReport.warnings` counts the sites an ellipsoid figure drew as spheres, one skill sentence. #1057, the two figure controls, stays open)
- [x] A theme-dependent C colour (from WP-1533): C's `#383838` reads at 1.56:1 on the dark `#151515`, as H's `#d8d8d8` does at 1.38:1 on the light `#fbfbfa`; a plain 3:1 rule would repaint 11 of 20 CPK colours on light. It changes the dark default picture, so re-run `measure.py` and name the rows that moved. Until then the skill tells an agent to recolour C on a dark background (2026-11-02: **ruled by the maintainer 2026-11-02, in chat**: C draws `#666666` on a dark ground and keeps `#383838` on a light one. `structure3d.DARK_GROUND`, in `render_structure` and the GUI's dark theme. `measure.py` reads no colour, so no row moved)
- [x] Two figure controls the promo scripts did by hand (from WP-1533): `fig.image` cropped to its ink, and a polyhedron colour on the figure, where all six take-2 scripts read `g["sites"]` instead (2026-11-02: `render_structure(pad=0)` and `StructureFigure.polyhedron_palette`)

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

### 2026-11-02 (3rd session) — closed; what is left moved to issue #1371

**WP-1468 is closed, and nothing it still carried is lost.** Its polyhedra
now handle disorder, split sites, cyanide and carbonyl ligands, user-chosen
centres and ligands, one atom's environment, the two-gap tie and the atom
cap, and the last session gave the figure its ink crop, its polyhedron
colours and a lighter carbon on a dark ground. What was left was mostly not
about polyhedra: five readings WP-1957's reviewers made of the structure
figure (forwarded by WP-1504), issue #1057's two ORTEP controls and its
outline defect, and a cluster polyhedron that waits for a user to ask. No
open WP owned them, so they moved to issue #1371 rather than being
folded somewhere they do not belong. The maintainer's triage filed them as WP-2111 on
2026-11-05. PR #1355, from a ghostshift runner,
a close-only job: this session changed no code.

*Done.*
- Status ✅, the `Priority:` line deleted, the `### Inherited` section
  deleted as consumed: all seven entries (five from WP-1504, the #1056 note
  already done on 2026-11-01, the #1057 note) are accounted for. The #1056
  note was done and is dropped; the other six are restated in issue #1371's
  Context, each rechecked against the tree at b0c79e12d (`DIM_BOUNDARY` still
  0.62, no label merge reads `stacked`, `DEFAULT_PROBABILITY` still 0.50, no
  `restyle` and no bond-colour parameter).
- The partial task (anion-centred and cluster polyhedra) stays `[~]`: its
  anion-centred half landed 2026-09-28, and its cluster half is issue #1371's
  last task.
- **Where the leftovers went, and why an issue.** Filed as issue #1371
  (P3 carried from this WP's 2026-10-23 rating). A first draft filed them as
  a new WP; it was withdrawn to the issue on 2026-11-03, since proposals to
  this repository go to issues and the maintainer opens WPs. Checked for an owner first (`grep -rln` over `docs/wp/` for the figure
  code, `DIM_BOUNDARY`, `#1057`, `view="auto"`, `atom_labels`): the open
  candidates were WP-1505, which moves the figure into its own package and
  changes nothing on its surface, and WP-1536, 1537 and 1538, which add the
  SVG, ray-tracer and ambient-occlusion outputs. None owns a reading of the
  picture or a draw style.
- The narrative moved to the v1.12 record, § How v1.12 is getting here (1.11.0 is cut).

*Measured* (`[dev]` venv, darwin/arm64, on origin/main b0c79e12d plus this
close). `tests/test_docs_consistency.py`: 25 passed. ruff clean.
`python -m tests.reader_output`: exit 0, unchanged against the merge-base.
`session_start.py` raises no flag for this WP, and
`closed_wp_writes.py` finds nothing added to a closed WP.

*Not run, and why.* `/code-review` (step 6): a prose-only branch. No
`CLAUDE.md` edit, no lane, no `_audit.py` change and no new heuristic, so no
generality judge. No full suite: nothing could move a measured number.

*Next.* None here. WP-2111 (from issue #1371): the label merge or the axis letters first, since
neither needs a ruling; the `DIM_BOUNDARY` shade waits on the maintainer, and
the `auto` ranking on an agent round.

### 2026-11-02 (2nd session) — carbon is lighter on a dark ground, as the maintainer ruled

**On a dark screen, carbon is now visible.** The maintainer ruled on the
question the first entry below put: carbon draws `#666666` on a dark ground and
keeps `#383838` on a light one (option 2). It was ruled 2026-11-02, in chat, by
the maintainer: "666666 looks better on dark". Shown the light pair, the
maintainer said the two pictures "look 100% identical", which is the point of
the dark-only change. The change reaches the GUI's dark theme, a
`render_structure` call on a dark background, and the notebook's dark copy. The
maintainer also approved the PR's reader output for merge. PR #1342.

*Done.*
- `structure3d.DARK_GROUND = {"C": "#666666"}` and `dark_ground_colours(sites)`,
  the one authority for which sites take it: a site still in its CPK colour,
  never one `recolour` marked, never a colour within `MIN_SEPARATION` of another
  in the phase. `build` writes its answer into the payload as each site's
  `dark_color`. `render_structure` asks again of the dict it is handed, so an
  edited colour is judged as it stands. `recolour` drops a copied `dark_color`.
- GUI: `Site.dark_color`, `onDarkGround` in `lib/structure3d.ts`, and
  `Structure3D.svelte` draws the scene, the species legend and the polyhedron
  swatches from that one geometry on the dark theme. Dist rebuilt. The scene
  corpus rewrote itself for the new field.
- Manual (`reference/figures.md`), the skill's sentence, which had told an agent
  to recolour C on a dark ground, and both skill copies. One pytest rewritten
  (`test_carbon_is_lighter_on_a_dark_ground_only`) and one vitest added.

*Measured* (`[dev]` venv, darwin/arm64, node v24.22.1). The touched files (14,
render, structure3d, gui server, dist, figure cut and boundary, the four skill
suites, docs consistency, manual api, gui manual, gui palette): 789 passed,
1 skipped. vitest 592 passed over 24 files, svelte-check 392 files with 0
errors. ruff clean. `python -m tests.reader_output`: exit 0, unchanged, because
its standard fit prints no figure. No committed figure or screenshot moved:
`make_figures.py` draws no structure, and `make_screenshots.py` photographs the
FAP example, which has no carbon. `measure.py` reads shells, never colours. The
GUI was not driven in a browser. The vitest asserts the scene and the legend
colours from `onDarkGround`.

*Next.* #1057's controls, or the Inherited readings from WP-1504. Cluster
polyhedra wait for a request.

- **2026-11-02** — **A structure figure can now be cropped to its ink, and it says
  what colour each polyhedron was drawn in.** All six scripts of the second promo
  take cut the picture down by hand and then shifted every pixel position they
  read, and each guessed a polyhedron's legend colour from the site list. Now
  `pad=0` fits the frame to the ink, so the positions, the Å-to-pixel map and the
  recipe stay right, and the figure lists each drawn polyhedron formula with its
  colour. The third open task, a lighter carbon on a dark background, changes the
  default dark picture, so it is built and switched off and waits on the
  maintainer's ruling, below. PR #1342, from a ghostshift runner. Issue #1057
  (per-atom draw style, bond colour, outline on thin sticks) is untouched.

  *Done.*
  - `render_structure(pad=...)`: the share of each side left empty, default
    `FIT_PAD` (0.05, ChimeraX `view`'s pad), refused outside 0 ≤ pad < 0.5, in
    `fig.recipe`. The `view="auto"` search reads the frame at the same pad.
  - `StructureFigure.polyhedron_palette`: formula → the centre's colour before
    any dimming, read off the faces the scene drew, a second colour for one
    formula kept as `"<formula> (recoloured)"` by the rule `palette` already had
    (now one helper, `_named`, for both).
  - `structure3d.DARK_GROUND`, **empty**: on a background darker than mid-grey
    `render_structure` gives a site still in its CPK colour that element's
    dark-ground colour, never a site `recolour` marked, and never a colour within
    `MIN_SEPARATION` (0.13 in OKLab) of another colour the phase draws. The GUI
    does not read it.
  - Manual (`reference/figures.md`), the skill's figure row in
    `make_api_index.py`, both committed skill copies. Four test functions, eight cases.

  *Measured* (`[dev]` venv, darwin/arm64). Blank margin round the ink at 1000 px,
  default pad against `pad=0`: fluorapatite down c 49-65 against 15 px (the a,
  b, c's room), YBa₂Cu₃O₇ without its cell 35-53 against 3, paracetamol 49-63
  against 9-13, HKUST-1 down a 65 against 15. The scripts cropped to the ink plus
  1 % of the width, 24-30 px at their 2400-3000 px. NAC's `view="auto"` picks [0 1 2] at
  either pad. `python -m tests.reader_output`: exit 0, unchanged; the new field is
  on the figure object, which no fit returns. `measure.py` was not re-run: no
  colour enters its rows, and with the table empty no picture moved
  (`test_the_default_picture_on_the_measured_phases` passes). Fast suite: whole selection `-m "not slow"` on the branch before its last test-only commit, through ghostshift's suite lock with other runners queued: 13514 passed, 314 skipped, 34 xfailed, 2 failed, 42 min. Both failures are this machine's, not the change's. `test_site_classes.py::test_an_unplaceable_species_does_not_enumerate_the_others` is a 15 s wall-clock guard that read 24 s under load and passes alone. `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone` reached a Jupyter kernel spec pointing at a deleted venv. No baseline count was measured, so the eight added cases are not checked as a delta; CI's fast matrix is the gate. Added-test cost (`tests.added_test_times`, that run, loaded): 7.7 s over the four, 4.2 s of it the polyhedron-palette test, then cut to 0.35 s alone by drawing at 200 px.

  *Review.* `/code-review high` (report mode, since the fast suite was queued on
  the tree) found eight; seven fixed in one commit. A label test patched
  `FIT_PAD`, which the new default argument had made a no-op, so it now passes
  `pad=0`. The view search read the frame at the default pad. A pad near 0.5 blamed
  `size`. The swap ignored the `recoloured` flag, and never checked separation
  after `phase_palette`. The polyhedron palette's undimmed colour and the label
  room at `pad=0` were undocumented. Declined: "the empty table is scaffolding".
  The runner brief asked for the swap built and left off, so the ruling below has
  a one-line change behind it.

  *Generality.* No judge dispatched: `_audit.py` is untouched, and the branch adds
  no heuristic in force. `pad`'s default is the existing `FIT_PAD`, and the table
  is empty.

  *Decision (maintainer): should the default dark picture draw carbon lighter?*
  Ruled the same day: option 2 (the second-session entry above).
  Trigger: it changes the default picture on the main user surface, a value
  judgement about the CPK convention ("carbon black"), and WP-1533 sent it here as
  such. **Why it matters.** C is `#383838`, a near-black grey. On the GUI's dark
  page `#151515` it reads at 1.56:1, and on the notebook's dark copy `#1d1813` at
  1.50:1, so every organic or MOF linker is barely visible on a dark screen. On
  the light page it is 11.3:1. Moderate. **Options.** (1) Nothing: the skill
  already tells an agent to `recolour` C on a dark background, and a person in the
  GUI has no such control. (2) A theme-dependent C, `#666666` on dark only: 3.18:1
  on `#151515`, 3.07:1 on `#1d1813`, 0.143 in OKLab from Ti's `#909090` (the
  separation floor is 0.13); the light picture is untouched (checked bit for bit).
  Cost: one line here for `render_structure` and the notebook, and a twin in the
  GUI client (`Structure3D.svelte` applies it before `buildScene`, a dist rebuild),
  undoable. (3) One C on both grounds, `#666666`: 5.55:1 on light, simpler, but
  the light picture moves too and C stops reading as black. **Practice.** From
  recall, not checked: Jmol draws C `#909090` on both grounds; VESTA a dark grey;
  Mercury a mid grey. **Recommendation:** option 2, a lean. The crux is whether
  "carbon black" is a convention to keep on light pages. Option 2 keeps it there
  and fixes only the case where it fails. It loses to option 3 if you would rather
  have one colour per element across themes. Pictures, before left and after
  right: `~/.cache/ghostshift/rietx/wp-1468/png/C_paracetamol_gui_dark_pair.png`,
  `C_paracetamol_notebook_dark_pair.png`, `C_hkust1_sphere_gui_dark_pair.png`,
  and `C_paracetamol_light_pair.png` (identical halves). Not generalised: Br
  (`#a02020`) and I (`#8020c0`) also sit under 3:1 on `#151515` but read by hue.

  *Gotchas.* The worktree guard refuses heredoc edits chained with other commands;
  write the edit script to the scratch dir and run it by path. Patching
  `render.FIT_PAD` no longer reaches a draw, because `pad=FIT_PAD` binds at
  definition: pass `pad=`.

  *Next.* 1. The maintainer rules on the dark-ground C. If option 2: set
  `DARK_GROUND = {"C": "#666666"}`, mirror it in the GUI client, rebuild the dist,
  and move the skill's "recolour C" sentence. If option 1: delete `DARK_GROUND` and
  `_on_dark_ground`, and close the task as declined. 2. Then #1057.

- **2026-11-01** — **An ellipsoid figure of a CIF read with the defaults now says
  it drew spheres, and the reader says why.** Reading a CIF drops each site's
  anisotropic displacement tensor unless `aniso=True` is passed, and the ellipsoid
  figure then drew spheres with nothing said (issue #1056, maintainer). Now the
  reader's diagnostics list gets one info line counting the sites whose tensors
  were read as U_eq, and the figure's report gets one line counting the sites drawn
  as spheres. A count, because a file's nine hydrogens are isotropic and trigger it
  legitimately. The two lines come from different places and neither knows of the
  other. PR #1298, from a ghostshift runner, for #1056 only; #1057 and the two
  open tasks (dark-theme C colour, figure controls) are untouched.

  *Done.* `CIF_ANISO_COLLAPSED` (info, `crystallography/cif.py`; message
  "N sites carry U_ij in the file and were read as U_eq; pass aniso=True to keep
  them", `where` the `.biso` path of each site, so it names the value that holds
  U_eq). Its `_audit` row (tier 1, ambiguity 1, response info), `help.py` entry,
  `help_keys.json` key, one `diagnostics-reading.md` row. `FigureReport.warnings`
  in ellipsoid mode (`viz/figure3d/render.py`): "Drawn as spheres for want of an
  anisotropic displacement: N of M sites (a CIF's U_ij is kept only by
  Structure.from_cif(..., aniso=True))". The wording has no number agreement, so a
  count of one reads right. The one skill sentence is in `docs/skill/make_api_index.py`
  (the generator), so `api-figure.md` and both committed skill copies were
  regenerated. Two tests in `tests/test_render_structure.py`.

  *Measured* (COD 2104364 paracetamol, venv `[dev]`, darwin/arm64). Default read:
  11 sites collapsed, 20 of 20 drawn as spheres. `aniso=True`: no reader line, 9 of
  20 spheres (the hydrogens). Ball mode: no warning. Both ellipsoid pictures looked
  at (spheres against ellipsoids, same view). `python -m tests.reader_output`: exit 0,
  unchanged, because its standard fit reads no CIF with an aniso loop; the added
  lines show only to a caller who passes `diagnostics=[]` or draws an ellipsoid
  figure. The new tests cost 0.55 s and 0.04 s locally. `tests/silence.py` needs a
  pair only for a `warning` code, and this one is info, so none was added.
  The fast selection (`-m "not slow"`, whole suite) did not run here: its turn in the ghostshift suite lock queue had not come after 80 minutes behind other runners' suites, so I withdrew it. What ran, on the merged tree (main fetched 2026-11-01, `[dev]` venv, darwin/arm64, beside other sessions): the 15 files touching this change (docs consistency, audit table, help, gui help, silence, skill x4, render_structure, cif_blocks, schemas, robustness_external, manual_api, structure3d), 935 passed, 1 skipped, 81 s; ruff clean. The two new tests are in that count; no whole-suite passed+skipped delta was measured. CI's fast matrix is the whole-suite gate.

  *Review.* `/code-review high --fix` found no bug and six minor points. Fixed: the
  singular ("1 sites"), the test's prefix slicing. Declined: the `where` paths point
  at `.biso` (consistent with `CIF_SPECIES_NORMALISED`'s `.species`); the count is
  taken after twin merging and by label, so a file listing one site twice reports
  the merged count, not the loop's row count (rare, and the message says "sites in
  the file" loosely). The generality judge's one finding, that the figure
  sentence's remedy clause fires also on a refined isotropic model, is answered by
  rewording it to a statement of fact ("is kept only by") rather than advice.

  *Generality* (judge's verdicts, edited down to the table's conclusions).
  `CIF_ANISO_COLLAPSED`: **holds**, tier 1 fits; case against is a frequency worry
  nobody measured (most single-crystal CIFs carry an aniso loop, so a powder refiner
  sees it on nearly every read; it is info and only on the `diagnostics=` channel);
  its message says "U_eq" where the reader falls back to trace/3 when the file
  states no `_atom_site_U_iso_or_equiv` (exact only for orthogonal axes). The
  figure warning: **holds**, no row, no threshold. Evidence that would flip it: a
  firing rate over a CIF corpus showing it fires on almost every read while almost
  no caller acts.

  *Gotchas.* `.agents/` and `.claude/` skill copies are committed, so a skill edit
  needs `rietx skill --install . --copy`. `api-figure.md` is generated: edit
  `docs/skill/make_api_index.py`. A new code needs `tests/data/gui/help_keys.json`
  too.

  *Next.* The maintainer reads the two added lines (reader-output rule). Then #1057
  (per-atom draw style, bond colour, outline defect) is the next figure task here;
  it is independent of this one.

- **2026-10-03** — **The four electronegativities nobody had checked now
  have a source.** Te, At, Kr and Xe agree with three handbooks, the CRC
  Handbook among them. The check is second-hand, through the handbooks' values
  as Wikipedia's data page quotes them, and the code comment says so. The
  WP did not close, because WP-1533 had sent it two live asks on 10-02. Both
  are tasks now.

  *Done* (a cleanup session over unowned in-flight WPs). The context note
  rewritten in place, the task ticked, the `ELECTRONEGATIVITY` comment in
  `gui/structure3d.py` naming the three handbooks and the page it read them
  from. No value changed. Inherited pruned: WP-1533's entry is two tasks, the
  dark-theme C colour and the two figure controls. *Searched:* the
  maintainer's zotero-linker, `~/Zotero` and `~/MinerU`, by title, filename
  and full text, hold neither Pauling (1960) nor Allen & Huheey (1980).

  *Next:* either new task. The C colour moves the dark default picture, so it
  re-runs `measure.py` first.

- **2026-09-28** — the structure viewer now reads chemistry it used to get
  wrong. A cyanide's or a carbonyl's C is its metal's ligand, so Prussian blue
  draws FeC₆, and Cu₃[Co(CN)₆]₂ draws CoC₆ where it had drawn a confident,
  wrong CoN₆. A CIF's disorder groups now reach the model and the picture. A
  chemist can choose which elements are centres and which are corners, and
  double-click one atom for its environment. The hover also says when a
  shell's gap has a near-equal rival. Two proposed rules were measured and
  ruled out: no distance bound separates split pairs from real bonds, and a
  memo for the bond slider would have to be keyed on every rule constant. The
  default picture on the 21 measured phases is unchanged.

  *Done*, one commit each: one `bonded` test and one `drawnWith` rule (with
  `drawn_with` in `scene.py`); position keys rounded as arrays; the donor rule
  and a one-step screen (non-metals only, obtuse by more than rounding); P9's
  angle test for sticks (`one_atom`), with a shared neighbour a stick could
  join to both; `polyhedra_dropped` and a greyed legend button;
  `Atom.disorder_assembly`/`disorder_group` (SCHEMA_VERSION 0.34), read from
  and written to CIF; the viewer's group rules, a negative group judged by
  each image's rotation, and `disorder=major`; Mercury's two lists as
  `centres=`/`ligands=`; the double-click; `METAL_SPLIT_FLOOR` = 0.5; the
  rival gap (`RIVAL_GAP` = 0.7); the skill's `api.md` regenerated.

  *Measured.* `measure.py`'s 21-phase output was byte-identical after every
  commit. Against the pre-session module, only two hidden gaps moved on those
  phases and the bundled CIFs: LaB6's La 1.45 → 1.90 and pyrite's Fe
  1.52 → 1.60, both from the screen. Payload build, best of 7 on an Apple M4:
  grossular 62.7 → 51.5 ms, the polyhedra 25.9 → 17.8 of it. Real cases,
  all public COD entries:
  - Cu₃[Co(CN)₆]₂ 4002391, Prussian blue 4343748 (Buser 1977), 1516492.
  - α-K₂SO₄ 1000049: split O at 0.787 of the radius sum, 19.6° round K.
  - NaNO₃ 8103616 and 9007558-9007567: 0.89-0.99, 27-32° round Na.
  - hydrated β-alumina 1529595: Li–O at 0.32.
  - Ag β-alumina 2105331-2105335: 0.35 and 0.59-0.70.
  - partial uranyl 1508149: 0.70 and 0.72, with groups declared.
  - rival gaps: 38 of 159 COD files' polyhedra, none on the 21 phases.
  COD 7223699 (NaClO₄) has Na and Cl swapped and was dropped from the
  measurement. Browser passes (chromium 1223, headless) on four probe
  projects: the perchlorate's toggle, Prussian blue's FeC₆, fluorite's FCa₄
  through the lists, and Cu₃Au's double-click.

  *Counts*, on the worktree's `[dev]` venv, macOS arm64, with `main`
  unmoved under the branch: the fast suite 6578 passed, 151 skipped, one
  other pytest process running beside it (4:14, a loaded figure). Twenty
  tests were added, fifteen in `test_structure3d.py` and five in
  `test_cif_disorder.py`, all passing and none skipped. The run before the
  review pass had 6577 with nineteen added. The twenty cost 1.50 s together
  in that run, the rival-gap test 0.86 s of it, since it builds the 21
  phases.
  vitest 575 → 581, svelte-check clean, and the manual builds under `-W`.

  *Review.* `/code-review high --fix` found seven. Six were fixed in one
  commit. The double-click held its atom by index, which its own refetch
  renumbers, and now holds it by site and position. The early exit returned
  `polyhedra_dropped` as 0. A toggle started from the stale payload's list.
  The major view listed elements it did not draw. Two arrays were rebuilt in
  loops. The seventh it skipped, and I fixed: the disorder-tag gate was
  case-sensitive, so a mixed-case tag dropped every group silently.

  *Gotchas.* The scene corpus (`tests/data/gui/scene_cases.json`) rewrites
  itself whenever the payload gains a field. It did so four times here, and
  the first rewrite moved its scenes in the twelfth digit, since it now
  computes them from the dumped payloads. Commit the rewrite and rerun.
  `gui/CLAUDE.md` sits at its 1060-line cap. `help.test.ts` budgets an
  authored `title=` everywhere but on a `<button>`, so a new control is a
  button with a verb-phrase title. `_orbit` reads a missing `_turn` as 0, so
  an orbit rebuilt from payload atoms, which carry none, cannot judge a
  negative group. `measure.py`'s `shells()` reads Brunner & Schwarzenbach
  without the screen, so its pyrite and LaB6 gaps differ from the server's
  by design.

  *Not done.* The Te, At, Kr and Xe sources: neither paper is on this
  machine (Context). Cluster polyhedra: nobody asked, and a centre with no
  atom does not fit the payload's `center` index. `render_structure` takes no
  new keywords, since the dict `build(…)` returns carries every new control.
  No SHELX reader exists, so disorder groups arrive only through a CIF. The
  skill gets no row: the controls are the GUI's, and an agent's figure
  reaches them through the dict `render_structure` already takes.

  *Next:* 1. The maintainer supplies Pauling (1960) and Allen & Huheey
  (1980). Check the four values against them, and the WP can close with
  clusters left to a request. 2. Otherwise close it as it stands, moving the
  sources to a P4 of their own.

- **2026-09-26** — filed from WP-1466's second session, at the maintainer's
  request, as the further work its automatic polyhedra leave. The survey of
  VESTA, Mercury and CrystalMaker was read from their manuals that day.
  *Next:* any one task; the disorder groups carry the most, and need a
  schema decision first.

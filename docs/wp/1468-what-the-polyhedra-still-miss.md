# WP-1468 — what the polyhedra still miss, and the controls a chemist would reach for

Milestone: unscheduled · Status: 🔄 2026-10-03 — eleven of twelve original tasks landed; WP-1533's dark-theme C colour and two figure controls remain
Track: Render what the fit already knows
Depends on: 1466
Priority: P4 2026-10-03 — the electronegativity sources are checked; left are WP-1533's C colour and two figure controls, and cluster polyhedra nobody has asked for

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
  `center` index cannot say.

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
- [~] Anion-centred and cluster polyhedra, if a user asks for them (2026-09-28: anion-centred ones come through the lists, as fluorite's FCa₄. A cluster polyhedron round no atom, B₆, does not)
- [x] The two-gap tie: find a real case, then decide whether to apply Daams & Villars' rule (2026-09-28: found, COD 1509685's Ag2 and 37 more; the rule declined and the rival reported in the hover, Context § Ties)
- [x] A hidden shell dropped at the atom cap stays in the legend as unavailable, or the cap stops counting it (2026-09-28: the payload's `polyhedra_dropped` lists each by site and ligands, and the legend greys a formula that has nothing else to draw. The cap still counts every shell: it bounds what the viewer draws)
- [x] The polyhedra stop recomputing on a bond-slider release — declined on the record 2026-09-28. The recompute is kept and made cheaper (Context). A memo would be keyed on the phase and on every rule constant, and one left out of the key serves a stale picture
- [x] One authority for "bonded" on the server and one for "drawn" on the client (2026-09-28: `structure3d.bonded`, `drawnWith` and its twin `drawn_with`)
- [x] A source for the Te, At, Kr and Xe electronegativities (2026-10-03: three handbooks agree, read second-hand, Context; the `ELECTRONEGATIVITY` comment says so)
- [ ] A theme-dependent C colour (from WP-1533): C's `#383838` reads at 1.56:1 on the dark `#151515`, as H's `#d8d8d8` does at 1.38:1 on the light `#fbfbfa`; a plain 3:1 rule would repaint 11 of 20 CPK colours on light. It changes the dark default picture, so re-run `measure.py` and name the rows that moved. Until then the skill tells an agent to recolour C on a dark background
- [ ] Two figure controls the promo scripts did by hand (from WP-1533): `fig.image` cropped to its ink, and a polyhedron colour on the figure, where all six take-2 scripts read `g["sites"]` instead

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

# WP-1933 — the CIF module beyond the structure block: the pattern block, the multi-block layout, and the validation hook

Milestone: unscheduled · Status: 🔄 2026-10-09 — C-d landed (#854); C-e waits on 1918's I-c, #752 on a decision
Track: Coming from another code
Depends on: 1319 (#756, #752)
Priority: P2 2026-10-09 — was P3 until 1319 landed the registry, number rule and structure block it builds on; #756's later chunks, a named user waiting

## Goal

The refinement CIF passes checkCIF with A = 0 and B = 0 or each one justified, as
#756 § 2.2 states. `structure_from_cif` reads each block of a multi-phase file and
the su it carries. A label the reader cannot turn into an element is refused at
read with the label named.

## Context

This WP is chunks C-d, C-e and C-g of issue #756, filed 2026-10-09 when the
maintainer gave [1319](1319-structure-interchange.md) C-a to C-c. The design is
#756's body (§ 2.2 the refinement CIF, § 2.5 checkCIF, § 4 the C-W2, C-W3 and C-W5
rows) and the reporter's comment of 2026-10-06, whose table carries each chunk's
acceptance. Each chunk builds on 1319's `rietx/io/cif/` registry, number rule and
structure block, so read 1319's Context for the decisions already taken
(dictionaries vendored whole, the deprecated H-M tag dropped, § 7's defaults).
C-f (magCIF parent record) is [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md)'s.

- **C-d, the pdCIF pattern block** (C-W2). The raw `_pd_meas_*` loop of every
  measured point, su in parentheses, weights with 0 on excluded points, d-spacing,
  2θ ranges, a wavelength loop from `Source.lines`, the reflection loop, QPA, PO,
  extinction and absorption, restraint/constraint/shift counts, text fields with su,
  `_pd_calc_method`, `_pd_instr_geometry`, and σ(V) taken from the covariance at fit
  close (`refine.py`). `io/exporters.py:514` writes `_pd_proc_2theta_corrected` for
  an uncorrected grid and `:516` writes the undefined `_pd_proc_intensity_total_su`
  (both checked at `5d1f5f67`). The second empties 1319's registry allow-list.
  Acceptance: `read_pdcif` reads back 5753 FAP points with weight 0 on the
  excluded ones (three, 130.00-130.04°; "two" here was #756's count, superseded
  2026-10-09 by the acceptance test's own comment and the measurement).
  **Landed 2026-10-09**, record below.
- **C-e, the multi-block layout and the reader** (C-W3). Overall, phase and pattern
  blocks with the `_pd_block_id` trio beside `_audit_block_code`, and the QPA
  phase table (`_pd_phase_block_id`, `_pd_phase_mass_%`), which is that trio's
  table and moved here from C-d; the wavelength on every phase block or
  reachable from it (below, PLAT982/983);
  `structure_from_cif(block=)`; su on read (today the reader drops all 22 su of
  `fap_refinement.cif`, reading through `gemmi.read_small_structure`). The NAC +
  CaF₂ file that `structure_from_cif` refuses on `main` reads block by block. Land
  it after #757's I-c, which edits the same reader lines.
- **C-g, the validation hook** (C-W5). The VRF template, the GSAS-II phase CIF as a
  declared profile over the registry, and the recorded checkCIF alert lists as
  fixtures. Before a magnetic block is written the hook calls #758's
  `validate_magnetic_phase`, and a phase carrying `MAGNETIC_P1_MISMATCH` is refused.

**C-d as landed, 2026-10-09** (`io/cif/powder.py`, `io/exporters.py`,
`model/geometry.cell_volumes`). Four choices the design left open:

- **QPA went to C-e.** The phase table's key, `_pd_phase.id` and
  `_pd_phase_mass.phase_id`, has no flat alias in `cif_pd.dic` 2.5.0, and
  decision 7 keys phases by the deprecated DDL1 trio. So the table is C-e's.
  `_pd_refln_phase_id` is the phase's 1-based position, the id that table will
  name.
- **March-Dollase PO is a sentence** in `_pd_proc_ls_special_details`, with r and
  its su. `_pd_proc_ls_pref_orient_corr` is deprecated in 2.5.0 and its
  replacement `_pd_pref_orient_March_Dollase.*` is dotted only (decision 2).
- **No `_refine_ls_number_constraints`.** The result carries no count of ties,
  and the dictionary counts symmetry ties as constraints too, so a number read
  off the user's ties would understate it. Left for whoever adds the count.
- **The `_refln` loop is `Refinement.write_cif`'s alone**
  (`refinement_cif_doc(reflections=)`), since only a fit's compiled model builds
  the rows. `write_refinement_cif` takes `pattern=` and nothing more:
  `docs/skill/rietx/references/api.md` stands at 39 690 B against its 39 700 B
  cap, and `tests/skill_caps.py` says the next raise is the split, the
  maintainer's call. The next public keyword or `RefinementResult` field needs it.

Beyond the design: `RefinementResult.cell_volumes` (`CellVolume`) holds σ(V) in
every mode, exactly 3a²σ(a) on a cubic cell; `ReflectionRow.phase_index`; the
profile text named TCHZ for a Voigt fit and now names the shape computed;
`numbers.text` moves a value that would carry its tag past 80 columns to a text
field (the class behind PLAT802); f′/f″ are written at the table's four decimals.

**checkCIF after C-d, 2026-10-09** (settings as 1319's; tree `0071e887` plus the
80-column fix, FAP before that fix, which touched nothing it writes over 80;
submissions 14-16 of the day's 30). The FAP file is 326 kB and the NAC + CaF₂ one
2.5 MB, its 59 498 measured points against 22 003 fitted.

| file (block) | A | B | C | G |
|---|---|---|---|---|
| FAP refinement | 3 | 0 | 1 | 4 |
| NAC refinement (NAC block) | 3 | 0 | 3 | 6 |
| NAC refinement (CaF₂ block) | 11 | 0 | 0 | 13 |

No syntax error, and the calculated/reported table is present on every block.
Against 1319's after-C-c run the A counts are unchanged and every A alert is
C-g's: DIFF003, PLAT197, PLAT198 on the pattern block, and the single-crystal
items (EXPT005, ATOM007, PLAT183-185, PLAT699, PLAT880-881) on CaF₂. Gone:
REFI015, PLAT802, PLAT151. The residuals each have a reason for C-g's VRF:

- **PLAT742 (C), an angle without su**: FAP's O5-P3-O6 and NAC's F2-Al1-F1 and
  Al1-F1-Na1. Each depends on nothing the fit refined: coordinates held, and
  the free cell lengths scale the arms' plane evenly (b = a in hexagonal FAP,
  a cubic NAC cell). Our missing su is exact, and checkCIF, which does not know
  the b = a tie, prints (1). `_geom_special_details` says so in words.
- **PLAT982/983 (G) on CaF₂**: Ca's f′ 0.0960 and f″ 0.1052 against "IT values"
  0.2262 and 0.3064, which are Ca's at Mo Kα. The CaF₂ block states no
  wavelength, which sits on the pattern block, so checkCIF compared at its
  default. C-e's layout answers it.
- **PLAT981/986 (G) on FAP**: no f′/f″, because the GSAS protocol declines
  dispersion. Expected.
- FORMU01, PLAT092, PLAT304, PLAT434, PLAT720, PLAT794: as in 1319's Context.

**The reader's setting** (from [1118](1118-foreign-model-files.md), 2026-09-16,
moved here from 1319). A CIF can state its setting in three places, and gemmi's
small-structure reader uses one. It prefers `_space_group_name_H-M_alt` over
`_symmetry_space_group_name_H-M`, ignores `_space_group_IT_coordinate_system_code`
(the core dictionary says that item "cannot be used to define the coordinate
system"), and ignores a `_space_group_symop_operation_xyz` loop. So a bare
`F d -3 m` over origin-2 operations reads here as choice 1, where GSAS-II reads it
correctly by checking the operations. `crystallography.symmetry.setting_from_operators`
already does that comparison for the `.gpx` reader and would close the gap in
`structure_from_cif` with no new authority. Separately, `structure_from_cif`'s two
paths resolve a bare multi-setting symbol two ways: the primary takes
`gemmi.read_small_structure`'s spacegroup (`F d -3 m:2`), the fallback calls
`find_spacegroup_by_name` on the raw string (`F d -3 m:1`). The 8a and 16d
multiplicities swap between them. Only the resolvers were measured; no file was
built that takes the fallback.

**A label read as a species** (issue #752, triage 2026-10-08, reproduced at
`5d1f5f67`). COD 9001547 (spangolite) has `_atom_site_label` and no
`_atom_site_type_symbol`, so `Structure.from_cif` takes the species from the label.
A plain label (`Cu1`, `O2`, `H3`) is rewritten to its element with a
`CIF_SPECIES_NORMALISED` note. A label with a separator or a suffix (`O-h3`,
`O-H7A`) is left as the species, and the refusal comes at the first evaluation
(`ValueError: phase '9001547' atom 7 ('O-h3'): cannot read an element symbol from
species 'O-h3'`), because the compile boundary has no diagnostics channel. The
class is every label `cif._SITE_LABEL` (`^[A-Za-z]{1,2}\d+$`) does not match:
`O1A`, `Cu1A`, `O-h3`, `Ow1`, `Fe(1)`, `C1_2`. A hydrate's `Ho1` (hydroxyl
hydrogen) already reads as holmium, so a wider rule needs `_chemical_formula_sum`
as a check on the elements it may produce. The decision is how far a label may be
read when the file states no type symbol. Whatever is chosen is a repair at read
with a `Diagnostic` (`io/CLAUDE.md`), and the unreadable remainder refuses at read
with the label named. No count of COD files in this class was measured.

**What 1319's structure block left** (C-c, 2026-10-09). Five items, each placed
in a chunk:

- **C-d.** checkCIF's PLAT981/PLAT986 (G) ask for f′ and f″. A refinement CIF
  knows them at its wavelength (`_atom_type_scat_dispersion_real`/`_imag`). A Le
  Bail or Pawley CIF states no formula, Z, Mr, density or `_atom_type` loop
  (`blocks.write_structure_block(composition=)`), and its dummy site is still
  written without #756 § 2.1's `_atom_site_calc_flag dum`.
- **C-e.** `structure_from_cif` reads a stated multiplicity only under the
  deprecated `_atom_site_symmetry_multiplicity` (`cif.py` `_site_statements`), so
  the `_atom_site_site_symmetry_multiplicity` the writer now emits goes unread.
- **C-g.** The GSAS-II phase CIF still writes B and the deprecated
  `_symmetry_space_group_name_H-M` by calling the block's parts. That tag stays on
  `registry.KNOWN_VIOLATIONS` until the profile is declared.
- **Kept as is.** A mass number stays in `_atom_type_symbol` (`57Fe`) so the round
  trip holds, though the dictionary's grammar puts digits only before a charge
  (`blocks._types`).

A long `_atom_type_scat_source` (113 characters) made PLATON skip every test while
the report still said "No syntax errors" (`blocks.SCAT_SOURCE_MAX` holds it at
40). A report whose value table comes back empty is a silent PLATON. Run settings
and alert lists are in 1319's Context.

### Inherited

- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: the two-block refusal names the wrong cause.** `structure_from_cif` refuses a valid two-block CIF with "this file does not read as a CIF (an empty, truncated or non-CIF file reaches here)" (`crystallography/cif.py:206-209`). Task C-e's `block=` is the fix; until it lands, the message could name the blocks it found.

- **2026-10-11, from the issue triage (#756): the superspace-number rule of
  2026-10-06 13:56 (from #682) is in no WP.** `SuperspaceGroup.number` is a
  caller-supplied label nothing sets or checks
  (`crystallography/superspace/operators.py:572-579`). Once a block assembler
  can emit one, it writes the number only when it came from a file that was
  read, or when the group built from the operators is confirmed as that
  number in the standard setting. Otherwise it writes the symbol and
  operators alone. The negative arm: a group carrying a wrong number is
  refused or written without it. This binds the msCIF writer (#678's N-W9)
  and C-g's registry. Checked against the tree at 7d9be3cb: nothing under
  `io/cif` or `crystallography/cif.py` writes a superspace number.
- **2026-10-13, from the issue triage (#913): an operator loop that
  contradicts the H-M symbol is obeyed in silence.** Checked against the tree
  at c3d0367 on gemmi 0.7.5, every case in the issue's table reproduces.
  `structure_from_cif` builds whichever group gemmi resolves
  (`crystallography/cif.py:694-698`) and names no contradiction. A P6₁ loop
  under `P 61 2 2` builds P 6₁, a P2/m loop under `C 1 2/m 1` builds
  P 1 2/m 1, and `-x,-y,-z` under `P 1 21 1` builds P -1. The only signal
  anywhere is `CIF_SITE_MULTIPLICITY_DISAGREES`, which blames a site. A loop
  that is no group, or one gemmi does not tabulate, is dropped for the
  symbol, also silently. So C-e widens from choosing a setting to naming the
  contradiction: one reconciling function in `symmetry.py` beside
  `setting_from_operators`, which magCIF (1918) and the refdb adapter (1921,
  which keeps its own "read `.` as 0") would call too. The Context paragraph
  above saying gemmi "ignores a `_space_group_symop_operation_xyz` loop" is
  stale on 0.7.5: there the loop wins, so a bare `F d -3 m` over origin-2
  operations already reads as `F d -3 m:2`. Two reader defects travel with
  it. A coordinate written `.` or `?` raises an anonymous
  `value nan lies outside bounds` ValidationError, naming neither file, site
  nor tag, because `_number_fault` (`:304`) skips both. An occupancy written
  `.` or `?` reads as 1.0 with no diagnostic (not in the issue; found by the
  triage). Separately, and able to land before C-e: `pyproject.toml` declares
  `gemmi>=0.6.5`, and under 0.6.5 every `structure_from_cif` call raises
  `AttributeError: 'gemmi.SmallStructure' object has no attribute
  'spacegroup'`, so the floor is stale. The proprietary-database counts the
  issue quotes (3 C2/m entries, 97, 5, 135, 7) cannot be checked here.

- 2026-10-26 issue triage: #1063's empty-`data_global` case (an empty or `_audit_*`-only leading block makes `structure_from_cif` refuse a FullProf mCIF as 'not a CIF') is placed in WP-1918's Inherited. C-e's `block=` should skip a block with no structure tags, so build the two together or let C-e generalise WP-1918's rule. Checked against the tree at c0e32ab29.

## Non-goals

- **Not C-a, C-b or C-c**: [1319](1319-structure-interchange.md). **Not C-f**:
  [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md).
- **Not CIF 2.0** (#756 § 3), msCIF (#678), torsions or the ionic bond criterion
  (#759).

## Tasks

- [x] C-d, the pdCIF pattern block, f′/f″ in the `_atom_type` loop and the dummy
      site's `calc_flag`, with its checkCIF re-run.
- [ ] C-e, the multi-block layout, `structure_from_cif(block=)`, su and the current
      multiplicity tag on read; the
      reader's setting from the operator loop through `setting_from_operators`, and
      one resolver for a bare symbol.
- [ ] #752: decide how far a label is read without a type symbol, repair at read
      with a `Diagnostic`, refuse the remainder at read by label.
- [ ] C-g, the validation hook, the VRF template, the GSAS-II profile, the recorded
      reports as fixtures.
- [ ] Tests for each, with the COD 9001547 file as a fixture if its licence allows
      (COD is CC0), else a synthetic one.
- [ ] Skill: a reference row for any new diagnostic code, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_exporters.py tests/test_magcif.py tests/test_projects_gsas2.py tests/test_cif_registry.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the recorded checkCIF report on the FAP and NAC + CaF₂ refinement CIFs
shows A = 0, and B = 0 or each one justified in a `_vrf_` record; every block of
the NAC + CaF₂ file reads back with its su.

## References

- Issue #756 and its comment of 2026-10-06; issues #752, #757, #758.
- Toby, B. H. (2006), ITC Vol. G ch. 3.3 and 4.2 — the pdCIF block layout and items.

## Handover log

### 2026-10-09 (2nd session) — C-d landed: the pattern block, checked by checkCIF

A refinement CIF from this package now deposits every measured point and says
which ones the fit used. It states the experiment and the method: the probe,
every emission line with its weight, the geometry, the absorption and the last
shift over su. Each phase's cell volume now has an esd from the whole
covariance, in every fit mode, and the CIF writes it. checkCIF finds no syntax
error, and the pattern-level alerts are gone. The A alerts left are the
single-crystal and instrument items the VRF template (C-g) answers. The phase
table and the links between blocks are not done. They belong to the multi-block
layout (C-e), which waits for WP-1918.

- **Done.** Claimed (PR #854, stacked on #851, base `main`). Inherited folded
  into Context and Tasks: all five entries were from 1319's close the same day
  and still held. C-d in four commits (`9b99fd14`, `7ac7f64e`, `0071e887`,
  `278ad847`) with the record (`8eb52895`). Context has the four choices C-d
  made (QPA to C-e, PO as a sentence, no constraint count, the `_refln` loop
  through `write_cif` alone) and the checkCIF table. Staged in
  `releases/1.8.0.md`: the renamed pattern tags under § Files that change, and
  § New.
- **`/code-review high --fix`** found ten and fixed eight (`74e83188`). The
  weights now use `RefinementResult.sig()`, the root rule for a weighted
  residual. `_fit_pattern` is recorded beside `result_`, so a cancelled fit
  keeps the previous result with its own pattern. `read_pdcif` pairs σ with the
  intensity column it chose. `text()` wraps what it moves to a text field. The
  Gaussian broadening terms state deg², now read off each `Parameter.unit`.
  `_geom_special_details` states the method only where a row has an su. Two
  helpers became one. Declined, one each way: the reader's 2θ and intensity
  preference, which this branch had flipped for nothing, is restored, so a
  foreign pdCIF stating both reads as before. Folding `cell_volumes` into
  `_sigmas` is left: one rule for a `None` esd now lives in two places.
- **Measured.** FAP (`test_acceptance_fap`'s protocol, Rwp 0.0925): 5753 points
  read back, weight 0 on the three excluded. NAC + CaF₂ (`examples/nac_11bm.py`,
  Rwp 0.0933): 59 498 points written against 22 003 fitted, a 2.5 MB file. σ(V)
  1077.274(13) and 163.1862(62) Å³. checkCIF A/B/C/G: FAP 3/0/1/4, NAC block
  3/0/3/6, CaF₂ block 11/0/0/13 (Context). Fast selection on `main` (`ba9659fd`)
  merged into the branch, `[dev]`, darwin arm64, nothing else running: 8941
  passed, 172 skipped, 1 xfailed in 3:41. Against 1319's 8929 + 172, +12: eleven
  added cases and one more `test_every_base_subclass_survives_the_new_getattr`
  case for `CellVolume`; no new skip. `added_test_times`: the 11 cost 1.03 s
  together, the dearest 0.24 s, so none joins the slow tail. The full selection
  was not run: nothing here moves a fitted number. No lanes.
- **Gotchas.** `docs/skill/rietx/references/api.md` is 39 690 B against its
  39 700 B cap, and `tests/skill_caps.py` says the next raise is the split, the
  maintainer's call. The next public keyword or `RefinementResult` field fails
  there. A pair that gemmi writes on the tag's line passes 80 columns however
  short the text, so `numbers.text` owns that rule. A dataclass field after
  defaulted ones needs a default, so `ReflectionRow.phase_index` defaults to 0,
  and its one writer, `reflection_table`, always sets it. #756 § 6 names WP-1815
  for the torsion loop, and no WP file of that number exists here, so the
  geometry-loop rules (publ_flag, no `?` rows) have no owner to inherit them.
- **Next**, in order:
  1. #752's decision, how far a label is read without a type symbol, from the
     maintainer. It is the one item workable today.
  2. C-e, once 1918's I-c lands (or the maintainer lifts that order): the trio,
     the QPA phase table, a wavelength each phase block can reach (PLAT982/983),
     `structure_from_cif(block=)`, su and the current multiplicity tag on read.
  3. C-g last, with the VRF reasons Context lists.

- **2026-10-09** — created by 1319's session, from #756's C-d, C-e and C-g and
  1319's inherited reader entries (#752, and the two 1118 setting findings). No open
  WP owned them: 1911 owns writers for other programs, and this is the package's own
  format.

# WP-2006 part 2: the rows that wait

Made from the three tiering lanes of the 2026-11-17 session (`/wp-handover` names it). The rows the session tiered are in `src/rietx/_audit.py` itself. This page holds the rest: the tier-3 candidates that need the maintainer's approval, the rows left at `unaudited` with what would close each, and the reader decisions audited by hand. Nothing here is a ruling.

A row marked **magnetic** is a magnetic-path decision, which is Mike's since 2026-11-04 (#1075).

## Tier-3 candidates (35)

Each row is rietx's own choice. The rule's two grounds are given: **Q1**, would every competent refiner act on it; **Q2**, the dataset families it holds on. **Stakes** is the reported quantity it can move, a case on disk, and the dissenter.

### `GSAS2_GPX_SCALE_NOT_COMPARABLE`

- **What it does**: read the site at gsas2.py:1861: always fires with diagnostics; the phase scale is seeded at the inline literal 1e-3 (gsas2.py to_structure, rx.Parameter(value=1e-3)) and the file's own scales stay on model.histograms[...].sample['Scale']. Not carrying a foreign scale is arithmetic (every code normalises it differently: GSAS-II converges to 3.77e-2 and TOPAS to 2.61e-6 for one specimen, forward.py:4906-4915). The seed value is not measured against GSAS-II or anything else
- **Q1**: Shown only a file's foreign scale, would every competent refiner start the rietx phase scale at 1e-3? A caller who would not: anyone with the pattern in hand, who seeds against it (seed_phase_scales does exactly that, and read_recipe and viz.compare call it), since a start four orders off is 'the most common reason a first stage goes nowhere' (forward.py:4906 docstring). The FullProf and TOPAS readers carry the file's scale instead.
- **Q2**: None measured. The literal is shared by the GSAS and GSAS-II readers; no test varies it, and no dataset family is counted. Fails when the true scale is far from 1e-3 on a pattern whose first plan stage cannot recover from the start.
- **Stakes**: The phase scale (hence a QPA fraction) only through convergence from the start; no case on disk where it moved an answer; dissenter: the recipe reader and viz.compare, which seed against the data.
- **Note**: The act of not carrying the scale is tier 1 arithmetic. Only the 1e-3 start is the tier-3 candidate. The maintainer may rule a start-from-data seed instead (needs the pattern at read time, which the readers lack).

### `GSAS_BANK_COMMENTED`

- **What it does**: info; fires when a GSAS file has no live BANK record and a commented one (a BANK line behind # carrying the whole loose header) is read as the bank (gsas.py:321-342 selects, gsas.py:447-456 reports). A commented record beside a live one is never read, because commenting a bank out is how a person disables it (gsas.py:324-330). Origin: issue #230, a tool prepended # and the file fell to the xy reader, 100x too large. No program does this: GSAS-II 5.8.4 G2pwd_fxye.py:42 skips every line starting with # and reports 'No BANK records found'. The act is a repair the format does not state, so it is rietx's own, reported at info
- **Q1**: Shown 'no live BANK record, one commented BANK line with the full header', would every competent refiner read it as the bank? The alternative is a refusal (GSAS-II refuses). The caller who would choose otherwise is one who commented out the only bank to disable the file: they asked for nothing to be read, so a refusal serves them and this reads it. That caller exists but has no reason to open the file. The data records that follow the bank line are unambiguous under it
- **Q2**: One family: issue #230's reporter (one GSAS export tool that prepends #). No fixture on disk carries a commented bank beside no live one beyond the synthetic test; tests/test_readers_robust.py::test_no_real_fixture_trips_a_check_on_what_its_reader_hands_back shows it silent on all 13 real fixtures (9 readers). Fails when the commented line is a stale header from an earlier export whose counts no longer match the data below it; the strict parse then raises on the count mismatch, so it fails loud, not wrong
- **Stakes**: The x axis (a centidegree start and step): read through the bank it is right, through xy it was 100x too large (#230); no dissenter named in the field beyond GSAS-II's refusal; none found in practice for the repair itself
- **Note**: Tier-3 candidate: rietx's own repair, no peer program does it.

### `GSAS_EXP_REFINE_FLAG_MERGED`

- **What it does**: read the sites at gsas.py:1783-1800 (_merged_flag) and :2037: GSAS states one flag for a cell and one X per site; where the Structure holds some members and frees others the writer sets the flag when any member varies, so the file frees a parameter the structure holds, and the warning names the group. The format forces a merge; the direction (free over held) is the writer's choice, argued in the docstring only (a file 'carries more of the protocol free than held')
- **Q1**: Shown a group with some members held and some free, would every competent refiner write the flag free? A caller who would not: one passing a structure whose held member is certified (a calibrant cell with a fixed angle) to GSAS, who needs it held; GSAS-II's own gpx has the same one Cell[0] flag. The other options are refuse, or write held.
- **Q2**: Not measured on any dataset: no family is counted, and tests/test_projects_gsas.py::test_a_flag_that_is_narrower_than_the_model_merges_and_says_so asserts the any() direction without a reference. Fails where a held member matters.
- **Stakes**: A GSAS cell or coordinate a later GSAS run refines when the user meant it held; no case on disk; dissenter: a held-wins writer, none found written.
- **Note**: The merge is forced, the direction is the heuristic; a one-line ruling (refuse, free, hold) closes it.

### `GSAS_EXP_SCALE_NOT_COMPARABLE`

- **What it does**: read the site at gsas.py:1647: always fires with diagnostics; the phase scale is seeded at the inline literal 1e-3 (gsas.py:1614) and the file's GSAS histogram scale is quoted in the message. Same row as GSAS2_GPX_SCALE_NOT_COMPARABLE
- **Q1**: As GSAS2_GPX_SCALE_NOT_COMPARABLE: would every competent refiner start the phase scale at 1e-3? A caller with the pattern in hand seeds against it (seed_phase_scales); FullProf and TOPAS readers carry the file's scale.
- **Q2**: None measured; no dataset family is counted, no test varies the literal. Fails when the true scale is far from 1e-3 and the first stage cannot recover.
- **Stakes**: The phase scale (hence a QPA fraction) only through convergence from the start; no case on disk; dissenter: read_recipe and viz.compare, which seed against the data.
- **Note**: The act of not carrying the scale is tier 1 arithmetic; only the 1e-3 start is the tier-3 candidate.

### `GSAS_PRM_GEOMETRY_ASSUMED`

- **What it does**: read the site at instrument_profile.py:707 and the docstring at :488-495: a PXCR .prm states no geometry, and the reader returns debye_scherrer for every one, 'the one the corpus it was built against is (11-BM capillary)', saying so. GSAS-II's importer chooses by wavelength count instead: a single-wavelength .prm is Debye-Scherrer and a two-wavelength one Bragg-Brentano (GSASIIfiles.py:235-258 in 5.8.4, the same rule GSAS2_INSTPRM_GEOMETRY_ASSUMED cites)
- **Q1**: Shown a PXCR .prm with a Kalpha1/Kalpha2 doublet, would every competent refiner take Debye-Scherrer? GSAS-II would not: it reads that file as Bragg-Brentano. A caller with a laboratory doublet .prm, the commonest PXCR case outside synchrotron capillaries, is the one who would choose otherwise.
- **Q2**: Chosen from one corpus family (11-BM synchrotron capillary, single wavelength); no second family, no test comparing the choice to any program. Fails on a doublet calibration from a flat-plate lab instrument.
- **Stakes**: Position and absorption corrections the geometry decides (sample displacement vs capillary offset, mu_r vs mu_t); the geometry is named in the warning, so the caller can set it; dissenter: GSAS-II's importer, which splits on the wavelength count.
- **Note**: Departs from GSAS-II for doublet files. Not changed, since reading a doublet file as Bragg-Brentano changes reader output.

### `PATTERN_MULTISCAN_DEFAULTED`

- **What it does**: warning; fires when a file holds more than one scan, no scan= was given and a diagnostics list was passed: scan 0 is read (base.py:297-318; called by every multi-scan reader). Reading the first scan is a choice the file does not make. GSAS-II 5.8.4 G2pwd_Panalytical.py:50-76 and G2pwd_rigaku.py:222-250 import every scan as its own pattern, so no program on disk defaults to scan 0 with a message; rietx's other option, a refusal, is what a non-monotone file gets. tests/test_readers.py::test_the_default_scan_is_never_a_silent_one
- **Q1**: Shown 'this file holds N scans and none was named', would every competent refiner read scan 0? No. A caller with a reciprocal-space map (101 scans in panalytical_mesh.xrdml) or a multi-sample .ras wants all of them, and GSAS-II imports all. A caller who wants a refusal and the list is also reasonable. The read-first-and-warn default is the third option, and it is what the package decides on the caller's behalf
- **Q2**: Not measured: scan 0 is a convention chosen with the multi-scan formats (xrdml, ras, brml, raw, rasx). Files on disk: panalytical_mesh.xrdml (101 scans, one lab) and the vendor fixtures with two or more scans, no count of families. Fails when scan 0 is not the pattern the user meant (a mesh file: slice 0 of 101 refines as if it were the sample)
- **Stakes**: Every refined number, since the pattern itself is chosen; on disk the 101-scan mesh read as scan 0; dissenter: GSAS-II (imports every scan)
- **Note**: Tier-3 candidate. Possible demotion to Rule 1 kind 3 (refuse and list scans) is the maintainer's, not proposed here.

### `PATTERN_ROWS_DROPPED`

- **What it does**: warning; three raise sites in two files (one in base.py, two in xy.py), three different acts. (1) base.py:418-446 (finite_rows): a row with a NaN or infinite 2theta, count or sigma is dropped and its 2theta runs named; arithmetic, a NaN carries no value to fit, and dropping and zero-weighting give the same chi-squared (docs/practice.md § A NaN or infinite value in a pattern file; GSAS-II keeps the point at weight 0, silently). Tier 1 for this site. (2) xy.py:416-437: the file's column count is the most common one among its numeric rows, a tie going to the last row's, and a row with another count is dropped. (3) xy.py:438-458: a line between the first and last data row that is not a row of numbers is dropped and named, where GSAS-II's xye importer refuses the file (G2pwd_xye.py:187). Sites 2 and 3 are rietx's own (issue #266, issue #897)
- **Q1**: Shown 'N rows in the data have a column count other than the file's, or are not a row of numbers', would every competent refiner drop them and read on? A caller whose '10.2 n/a' is a lost measured point may prefer the refusal GSAS-II gives, and a caller whose data legitimately mixes 2 and 3 columns would lose rows. The unanimity gate fails for sites 2 and 3, passes for site 1
- **Q2**: Sites 2-3 measured on: issue #266 (one reporter, a PDFgetX2 numeric header row), 22 repository files with a header above the data skipped silently, no repository pattern with a line inside the data, and one real ILL D1B quench file whose first row carries a seventh field and is dropped correctly (tests/test_d1b_co3o4_quench.py::test_every_real_file_reads_with_the_stated_shape); 0 of the 13 real fixtures fire it falsely (tests/test_readers_robust.py::test_no_real_fixture_trips_a_check_on_what_its_reader_hands_back). Two to three laboratories, not counted by instrument. Fails when the header row has the data's own column count (stated in xy.py docstring) or when a short row is a measured point
- **Stakes**: Which points enter the fit, so every refined number can move by one missing point; on disk the D1B file starts one step later; dissenter: GSAS-II refuses a bad line in xye (G2pwd_xye.py:187)
- **Note**: Tier-3 candidate for sites 2 and 3; site 1 alone would be tier 1. If the maintainer wants the row split, it needs a second code.

### `RECIPE_BACKGROUND_PEAK_DEGENERATE`

- **What it does**: read the site at recipe.py:1010: fires when a background peak starts at a FWHM at or above the fitted span; it only reports (the recipe asked for the peak, so it is built); the rule is HumpComponent's own record (a 16-term polynomial plus a peak walked to 24.8 deg and returned 617 HIGH_CORRELATION findings) and the LaB6 recipe, where GSAS-II's peak ran to 8.77e10 deg and TOPAS's stayed at 1.63 deg with an esd 51x its value
- **Q1**: Shown a Gaussian background peak at least as wide as the fitted range, would every competent refiner call it a polynomial in disguise? A caller who would not: someone modelling a deliberate broad amorphous hump on a short range, who wants it as a peak. The code asserts the judgement and changes nothing.
- **Q2**: One family: the LaB6 recipe with two reference engines plus the HumpComponent record; no second instrument or material. Fails where the peak sits off-centre so that it still falls to half height inside the window (the 'never falls to half height' argument in the docstring then does not hold).
- **Stakes**: An ADP or scale that the broad peak absorbs; the case on disk is the LaB6 recipe (617 correlation findings); dissenter: none found.
- **Note**: Thresholded diagnostic over a model parameter, not a residual; batched because the arithmetic claim is loose at the edges. Level is warning, so it would need a response naming a width or an ADP. The `0.0 if pos is None` default at the peak's position waits on the maintainer and is NOT settled here.

### `RECIPE_BACKGROUND_RESEEDED`

- **What it does**: read the site at recipe.py:892: fires when a recipe has a Chebyshev background; only the term count and the refine flag come across and the coefficients start at zero (the committed recipes carry placeholders [10, 5, 1, 0, 0, 0]); linear in the coefficients, so a free background converges from any start
- **Q1**: Shown a recipe's Chebyshev coefficients, would every competent refiner discard them? A caller with refine_flag false, who has asked for the stated background to be held, would not: the reader gives them a held zero background instead of the stated one.
- **Q2**: Two recipe fixtures (LaB6, DRX_33), both with the flag true and placeholder values; no family with a held background. Fails exactly on refine_flag = false with real coefficients.
- **Stakes**: A held background (hence ADPs and scales) when the flag is false; no case on disk; dissenter: none found.
- **Note**: Whether GSAS-II's Chebyshev basis equals rietx's is not stated anywhere I read, which is the reason given for not carrying values; answering that would move this row to tier 1.

### `RECIPE_ENGINE_DEFAULT_DECLINED`

- **What it does**: read the site at recipe.py:1302: fires when a size or strain block exists with a null magnitude; GSAS-II fills it with 1 um and 1000e-6 (measured on the committed LaB6 reference: gamma exceeds the instrument-only width by exactly that, on 49 reflections), and the reader declines to adopt it, leaving the broadening at zero
- **Q1**: Shown a recipe with a present-but-null size block, would every competent refiner leave the broadening at zero? A caller comparing the two engines (PowderLine's whole use) would take GSAS-II's defaults so the Rwp gap means something; the docstring says the strain default alone is 0.057 deg x tan(theta) against peaks 0.027 deg wide.
- **Q2**: One family: the LaB6 recipe (one reference engine output for the default values); no second. Fails whenever the cross-engine comparison, not the physics, is the aim.
- **Stakes**: Rwp and the broadening coefficients (the docstring: the cells are the comparable quantity, not the broadening); case on disk: the LaB6 fixture; dissenter: PowderLine's rule 3 (translate the recipe, do not define one) reads toward adopting.
- **Note**: The measured values are tier 2 evidence for what GSAS-II does; the choice to decline is the tier-3 part.

### `SPACE_GROUP_SETTING_ASSUMED`

- **What it does**: read the raise site at symmetry.py:1340-1440 (setting_diagnostics): fires exactly when a bare H-M symbol names a group the tables hold in more than one setting (origin choices, or hexagonal against rhombohedral axes) and nothing pinned it; the symbol resolves to gemmi's first setting and the message quotes the cell contents each setting implies where they differ, else the multiplicities; a format that states its operators is read by setting_from_operators and never comes here (tests/test_symmetry_orbits.py, tests/test_projects_gsas.py, tests/test_projects_topas.py). Practice: GSAS-II 5.8.4 reads a bare two-origin symbol as origin choice 2 and offers a 1 to 2 shift when a CIF's operators disagree (imports/G2phase_CIF.py:729-783, GSASIIspc.py:4205 spg2origins); rietx's .inp reader maps TOPAS's trailing Z to :2 (WP-1118), so a bare TOPAS symbol is origin choice 1, as gemmi's; FullProf not checked.
- **Q1**: No. A bare symbol must be read as some group, and the programs disagree on which: GSAS-II takes origin choice 2, gemmi and TOPAS origin choice 1. A refiner typing spinel coordinates from a paper (almost always origin 2, issue #217) wants origin 2. The settings are enumerable and the message already quotes each one's contents, so the question is whether the default pick stands beside that ranking or the pick is withheld.
- **Q2**: Not a measured threshold. Cases on disk: 4 of the 46 phases of GSAS-II's tutorial corpus state a bare two-setting symbol whose operators are origin 2 (WP-1118; those are read from the operators and never reach this code); tests/data/gsas2_mn3o4_setting.gpx (hausmannite, the case where the composition does not separate). Fails on a spinel typed from a paper: A2BO4 for AB2O4.
- **Stakes**: element counts, ZMV and weight fractions (spinel A and B multiplicities swap); the case on disk is gsas2_mn3o4_setting.gpx; dissenter GSAS-II 5.8.4 (origin 2).
- **Note**: The act is gemmi's convention, not a threshold. If the maintainer reads 'a pick that must be made, with the ranking beside it' as unanimous, it is tier 2 on TOPAS and gemmi's default with GSAS-II named as dissenter.

### `TOPAS_PHASE_TERM_READ`

- **What it does**: read the site at topas.py:4621 and _reserved_phase_terms (:4636-4650): a prm named p<i>_extinction, p<i>_magnetic_lor_size or p<i>_magnetic_lor_strain is read as phase i's term. These names are rietx's own writer's (topas_ties.RESERVED_PHASE_TERMS: 'TOPAS has no keyword for' them), read back by name from any file
- **Q1**: Shown a prm called p1_extinction, would every competent refiner read it as phase 1's extinction? A caller whose own file uses that name for something else would not, and the suggestion says to set the term back by hand.
- **Q2**: A round-trip convention between rietx's writer and reader (tests/test_topas_p1_ties.py, test_topas_reader_ties.py); not a foreign program's convention and no corpus file uses the names. Fails on a file that reuses a name.
- **Stakes**: A phase's extinction or magnetic width; no case on disk where a foreign file hit the name; dissenter: none found.
- **Note**: Low stakes; included because the convention has no source outside rietx.

### `rietx.crystallography.cif.CIF_ANGLE_CORRECT_MAX_DEG`

- **What it does**: decides correct-and-record against refuse: a symmetry-fixed angle stored between 1e-3 and 0.1 deg from its value is read on it (CIF_CELL_ANGLE_CORRECTED); past 0.1 deg it is left as written and ParameterTable refuses (cif.py:39-55, 85-115). Docstring: 0.1 deg is an 830 ppm d-spacing consequence and separates a reported refined angle (beta = 90.002(3)) from the wild case WP-1036 found, beta = 93.2 under an orthorhombic symbol. tests/test_robustness_external.py::test_the_correction_band_separates_a_report_from_a_mis_declaration asserts only SYMMETRY_ANGLE_TOL_DEG < 0.1 < 3.2.
- **Q1**: Yes for the two cases the docstring names: every refiner puts 90.002(3) on 90 and none silently snaps 93.2. Between them two careful people differ. GSAS-II snaps any deviation once the cell refines, so a GSAS-II user expects 0.5 deg to be snapped too; a refiner who suspects a mislabelled monoclinic phase wants 0.08 deg refused.
- **Q2**: One synthetic orthorhombic file at 90.002 and 93.2 (the tests above) and one wild case (WP-1036). the 16 real CIFs on disk (14 under tests/data, 2 bundled examples; probe S/lane-cif-probe.py, 2026-11-17) fire none of the site or cell codes, so every case that reaches it is a synthetic file written by a test. Fails on a monoclinic phase with beta = 90.08 filed under an orthorhombic symbol: snapped with a warning, the 660 ppm distortion lost.
- **Stakes**: the cell (up to 830 ppm in d at the edge of the band); none on disk; dissenter GSAS-II 5.8.4, which has no band and snaps any size when the cell refines.

### `rietx.crystallography.cif.CIF_STATED_MULTIPLICITY_SNAP_TOL`

- **What it does**: decides move-and-record against report: a site whose file states a smaller multiplicity is moved up to 1e-3 (fractional, per operation displacement) onto the special position that has it (SITE_SNAPPED_TO_SPECIAL_POSITION); further, CIF_SITE_MULTIPLICITY_DISAGREES names it and nothing moves (cif.py:1166-1174, 1395-1478). Docstring: a four-decimal site can sit 2e-4 off (hematite 6e on rhombohedral axes, x + y = 1.5002), and three decimals is as coarse as a CIF is quoted. tests/test_cif_stated_columns.py::test_a_stated_multiplicity_puts_a_rounded_site_on_its_position and ::test_a_stated_multiplicity_the_coordinates_cannot_reach_is_named are the two arms, on synthetic files.
- **Q1**: Mostly yes: the file states the multiplicity itself, so moving a site 1e-3 to agree with the file's own statement is reading the file. A dissenter: GSAS-II 5.8.4 never moves a site and only warns that the stated and computed multiplicities differ (imports/G2phase_CIF.py:572-578). A refiner of a genuinely displaced site whose author copied the parent's Wyckoff column would want it left.
- **Q2**: Synthetic files only (hematite-shaped 6e site). the 16 real CIFs on disk (14 under tests/data, 2 bundled examples; probe S/lane-cif-probe.py, 2026-11-17) fire none of the site or cell codes, so every case that reaches it is a synthetic file written by a test. The fixed 1e-3 is not computed from the file's digits as CIF_PRINTED_ROUNDING is; a two-decimal file (5e-3 rounding) is past it and is reported, not moved.
- **Stakes**: multiplicity, hence ZMV, density and weight fractions (twice the oxygen of hematite left unmoved); none on disk; dissenter GSAS-II 5.8.4 (warns, never moves).
- **Note**: A tier-1 alternative exists: replace the fixed 1e-3 by the per-file printed-digit box, as CIF_PRINTED_ROUNDING does. That changes reader output and goes to the maintainer.

### `rietx.crystallography.cif.DUPLICATE_U_TOLERANCE`

- **What it does**: decides drop-the-copy against refuse: two statements of one orbit whose B (through 8 pi^2 U) or any U^ij differ by more than 2e-4 A^2 are refused, at most that a copy is dropped (cif.py:332-336, 442-456; tests/test_cif_sites_coincide.py::test_a_copy_that_differs_in_displacement_or_disorder_is_refused, ::test_a_copy_that_states_the_same_displacement_is_still_dropped, ::test_a_copy_that_differs_in_anisotropic_displacement_is_refused). Docstring: U is printed to four decimals, so copies differ by at most 1e-4, and twice that covers a conversion through B.
- **Q1**: Yes on its failing side, which is a refusal by name: too tight, a duplicated row is refused and the caller edits the file. Too loose, a copy that says a different U is dropped with its statement; no competent refiner wants that, so the bar should sit at the print. Nobody checked chooses a different bar, because no program checked drops a copy (GSAS-II keeps both rows).
- **Q2**: Synthetic files only. the 16 real CIFs on disk (14 under tests/data, 2 bundled examples; probe S/lane-cif-probe.py, 2026-11-17) fire none of the site or cell codes, so every case that reaches it is a synthetic file written by a test. The four-decimal claim is a convention, not computed per file; a file printing U to three decimals (copies 1e-3 apart) is refused rather than merged.
- **Stakes**: which statement of an ADP survives a duplicate row (B, U^ij); none on disk; none found among the programs, none of which drops a copy.
- **Note**: Could become tier 1 if computed from each value's printed digits (CIF_PRINTED_ROUNDING's rule).

### `rietx.crystallography.cif.OCCUPANCY_TOLERANCE`

- **What it does**: two uses (cif.py:324-330): occupancies of two sites at one place summing to at most 1 + 0.01 are a split site and kept, not an overfill (cif.py:433; tests/test_cif_sites_coincide.py::test_two_quoted_occupancies_summing_to_just_over_one_are_not_an_overfill); and two copies of one orbit whose occupancies differ by more than 0.01 are refused rather than one dropped (cif.py:488; ::test_an_orbit_listed_twice_with_two_occupancies_is_refused). Docstring: 0.01 is two roundings to the second decimal, the coarsest a file prints, and covers 0.523(1) + 0.481(1) = 1.004.
- **Q1**: Yes in the cases named: a quoted split summing 1.004 is not a duplicate. The bar itself is a convention: a refiner whose file quotes occupancy to one decimal (0.5 + 0.6) would want a looser one; one with three-decimal refined values could want su-based agreement.
- **Q2**: Synthetic files only. the 16 real CIFs on disk (14 under tests/data, 2 bundled examples; probe S/lane-cif-probe.py, 2026-11-17) fire none of the site or cell codes, so every case that reaches it is a synthetic file written by a test. Fails on a file printing occupancies to one decimal, where two roundings reach 0.1.
- **Stakes**: which sites survive a duplicate (an occupancy and the site count, hence weight fractions); none on disk; none found (GSAS-II keeps both rows, so it has no such bar).

### `rietx.crystallography.dispersion.LINE_DISPERSION_TOL`

- **What it does**: decides share-or-refuse: one |F|^2 is shared across a source's emission lines, so f' and f'' come from the primary line, and a line whose f' or f'' differs from the primary's by more than 1 % of Z is refused (dispersion.py:236-245, resolve). Docstring: Cu Ka1/Ka2 are 20 eV apart and harmless unless an edge falls between them, while a modelled Kb is about 860 eV away. No test names the constant (grep of tests/, 2026-11-17).
- **Q1**: Yes that some bar is needed, since the shared |F|^2 is an approximation; the 1 % of Z is a choice. A refiner fitting Kb with a light element far from edges loses nothing at 2 %; one near an edge wants the bar tighter.
- **Q2**: No dataset family named; the rationale is the Cu line spacing, not a measurement.
- **Stakes**: a refusal only (no value moves); none on disk; not checked whether any program evaluates f', f'' per line (GSAS-II computes them once per histogram wavelength).
- **Note**: Not in the residual-heuristic family: it compares tabulated f', f'' only.

### `rietx.crystallography.dispersion.NEAR_EDGE_EV`

- **What it does**: within 50 eV of an absorption edge the Cromer-Liberman values are returned but flagged, since f'' there is the compound's near-edge structure (dispersion.py:76-82, near_edge); tests/test_dispersion.py::test_near_edge_flags_the_xanes_region asserts Zn K + 30 eV is flagged and + 500 eV is not, which brackets the value without fixing it
- **Q1**: Yes that the near-edge region is untabulable; the 50 eV width is a convention with no citation in the docstring. An XAS user would put the XANES region at 30-50 eV above the edge and the pre-edge below it (recall, not checked against a source).
- **Q2**: No dataset family; one synthetic bracket on Zn K.
- **Stakes**: a warning only (values are returned either way); none on disk; not checked.
- **Note**: A citation for the XANES width (an XAFS text) would move it to tier 2.

### `rietx.crystallography.symmetry.MAX_HKL_GRID_POINTS`

- **What it does**: ceiling on the (2h+1)(2k+1)(2l+1) grid generate_reflections may allocate, about 1 GB of transient int64; a cell needing more is refused by name before allocation (symmetry.py:32-36); tests/test_robustness_external.py::test_the_grid_limit_clears_every_physical_cell (201^3 for a 100 A cell at d_min 1 A is under it) and ::test_a_collapsed_cell_is_refused_before_the_grid_is_allocated
- **Q1**: A memory cap whose failing side is a named refusal, the shape of dichotomy.MAX_GRID_BYTES and site_classes.MAX_SITE_ASSIGNMENTS (tier 3, approved 2026-10-21 and 2026-10-31). A competent caller who meets it: a 200 A cell (a protein or a large zeolite) at d_min 1 A needs 6.4e7 points and is refused.
- **Q2**: No dataset family reaches it; the cases are a constructed 100 A cell and a collapsed cell.
- **Stakes**: a refusal only; none on disk; none found.
- **Note**: Memory caps went to tier 3 with dated approval in earlier rounds; this row follows them.

### `rietx.crystallography.symmetry.SITE_TOL`

- **What it does**: default tolerance (fractional, on each operation's displacement R x + t - x) for 'this operation fixes this site', so the reach on a mirror is 5e-5; a site within it is expanded at its special position and SITE_SNAPPED_TO_SPECIAL_POSITION reports it (symmetry.py:778-785, 1288-1340). Docstring: a five-decimal ICSD file can miss y = 2x by 1e-4. tests/test_symmetry_orbits.py checks the orbit invariants over all 564 settings at offsets 0 to 5e-4 and that no shift exceeds it. Practice: GSAS-II 5.8.4 counts an image within 2e-4 per coordinate as the site (GenAtom, GSASIIspc.py:2236-2240), so its mirror reach is 1e-4, twice rietx's. Two rigid-body uses (the existing row's evidence: params.vector._refuse_body_off_its_sites, params.bodies.RigidBodyBlock._increment_basis).
- **Q1**: Yes that some tolerance is needed (a five-decimal file misses exact relations). Where: a GSAS-II user expects a site 1e-4 off a mirror counted special, and rietx counts it general; a refiner of a real small displacement off a special position wants the tolerance tighter.
- **Q2**: Cases: ICSD 18318 (B11, B16 at five decimals, issue #215) and synthetic offsets over all 564 settings. the 16 real CIFs on disk (14 under tests/data, 2 bundled examples; probe S/lane-cif-probe.py, 2026-11-17) fire none of the site or cell codes, so every case that reaches it is a synthetic file written by a test. Fails on a four-decimal file: 2e-4 off is read general with twice the multiplicity (the hematite case CIF_STATED_MULTIPLICITY_SNAP_TOL exists for).
- **Stakes**: a site's multiplicity, hence ZMV, density and weight fractions; ICSD 18318 cited, not on disk; GSAS-II 5.8.4 sits at twice the reach (a value outside the range of one program checked, below it).
- **Note**: The existing row already says 'unaudited, for the maintainer's tier'; its rigid-body evidence (the CO2-in-mirror tilt mismatch, measured 2026-10-29) should be kept when the row is rewritten.

### `rietx.crystallography.symmetry.SYMMETRY_ANGLE_TOL_DEG`

- **What it does**: largest deviation of a symmetry-fixed angle from its value that cell_constraints accepts, 1e-3 deg: within it the angle is held at its stored value, past it ParameterTable refuses (symmetry.py:567-580, check_cell_angles). Docstring: at 1e-3 deg the worst d-spacing bias is 8.3 ppm against SRM 660c's 48 ppm cell assertion, and it clears an indexing candidate's 1.4e-14 deg round-off by 7e10x. tests/test_params.py, tests/test_indexing_core.py, tests/test_robustness_external.py.
- **Q1**: Yes for both arms named (round-off accepted, a real disagreement refused). Inside the band the angle is kept at its stored value silently; GSAS-II instead sets it to the symmetry value once the cell refines, with no band. A refiner quoting a cell to 10 ppm would want the angle snapped rather than held.
- **Q2**: Measured on a constructed a=5, b=6, c=7 cell (8.3 ppm) and the indexer's candidates; no dataset family.
- **Stakes**: the cell, at most 8.3 ppm in d; none on disk; GSAS-II 5.8.4 (snaps any deviation on refinement).
- **Note**: Finding: inside 1e-3 deg the CIF reader neither snaps nor reports (cif.py:98), so a silent sub-1e-3 deviation survives into the model; changing that changes reader output and goes to the maintainer.

### `rietx.crystallography.symmetry.TWIN_DISTANCE`

- **What it does**: decides whether one listed site is another's image: same species, occupancies summing past 1 + OCCUPANCY_TOLERANCE, and some operation carrying one within 0.02 A of the other (symmetry.py:1064-1067, cif._sites_listed_twice cif.py:414-440); then CIF_SITE_LISTED_TWICE drops or refuses. The existing row says it no longer decides a site's own twin (TWIN_COORD_TOL does since #1014). tests/test_cif_sites_coincide.py::test_an_orbit_listed_twice_is_counted_once.
- **Q1**: Yes that two rows 0.02 A apart describing an overfilled place are one orbit. The bar is a distance convention: two real atoms of one species are never 0.02 A apart, but a split site refined 0.05 A apart is real and sits outside it, as it should.
- **Q2**: Synthetic files only. the 16 real CIFs on disk (14 under tests/data, 2 bundled examples; probe S/lane-cif-probe.py, 2026-11-17) fire none of the site or cell codes, so every case that reaches it is a synthetic file written by a test. A fixed Cartesian bar, unlike TWIN_COORD_TOL's fractional one; fails on a 100 A cell where a five-decimal duplicate differs by 1e-3 A (inside, fine) and on a duplicate typed to two decimals in a 20 A cell (0.1 A, outside: both copies kept, the orbit counted twice).
- **Stakes**: whether an orbit is counted twice (a site count, hence weight fractions); none on disk; none found (GSAS-II has no duplicate test).
- **Note**: The existing row says 'for the maintainer's tier and approval'.

### `rietx.io.formats.base.HEAD_BYTES`

- **What it does**: a sniff window: every text dispatch reads the first 4096 bytes (base.py:321, head() 788-800), bounded so dispatch is O(1) in file size. On either side: evidence inside the window is claimed by its format; a format whose evidence lies past it is not matched and the file falls to later readers, ending in the xy catch-all, which refuses with the wrong cause or reads the records as columns (a centidegree GSAS file reads 100x too large and is then refused by the 180 degree check). Known real misses: a GSAS TIME_MAP file with its first bank at byte 6068 (vnb5053, handled by one bounded escalation) and a PDFgetX2 header of about 6 kB (handled by matching its banner inside the window). Probe (2026-11-17, probe_head2.py, tests/data, 210 files): identity unchanged for all 210 at 4096 against 65536 bytes; at 2048 one file changes (11BM_LaB6_660a.fxye, bank at byte 2395, gsas to xy), at 1024 the same one, at 512 and 256 twenty. So the margin on the fixtures is 1.7x
- **Q1**: Shown 'the signature of format X sits past 4 kB', would every competent refiner not claim the file? No: a wider window (16 or 64 kB, also a bounded read) would claim both known misses without a special case, at a cost of reading 4 to 16 times more bytes per sniff. The caller who prefers it larger is any user with a long vendor header
- **Q2**: Measured on the 210 files of tests/data (about 20 formats; labs not counted): 0 changes from 4 kB to 64 kB, 1 at 2 kB. Fails on the two real files named above, which are why the escalations exist; the next format with a long preamble fails the same way
- **Stakes**: Which reader claims a file, hence the axis and sigma it gets; on disk vnb5053 (HIPD, LANSCE) and PDFgetX2 headers; dissenter: file(1) reads up to 1 MB for magic numbers, GSAS-II scans the whole file for BANK records (G2pwd_fxye.py:35-52)
- **Note**: Tier-3 candidate (rietx's own bound). The probe is the evidence that a wider window costs no fixture its identity; it is not a recommendation, which is the maintainer's.

### `rietx.io.formats.gsas._GSAS_TIME_MAP_SCAN_BYTES`

- **What it does**: 65536: how far one further bounded read looks for a BANK record once a TIME_MAP token shows in the first 4 kB (gsas.py:251-262). Either side: a bank inside the window is claimed as GSAS; one past it is unsniffed, the file falls to the xy catch-all, which refuses with the wrong cause (a 2theta direction from records read as columns), not a wrong pattern. The one real table is 71 rows with its bank at byte 6068, so 64 kB is about 10x the one measured size (about 800 rows of 80 bytes)
- **Q1**: Shown a TIME_MAP file with its bank past 64 kB, would every competent refiner not read it? No one wants it refused; the bound is a cost trade (one extra read behind a shape gate), not a view of the data. A caller with a very long table would choose a larger bound or the full file, as GSAS-II does by scanning the whole file
- **Q2**: One real file, one family (HIPD at LANSCE, from the GSAS distribution's examples). Fails on a time-map table larger than about 800 rows, refused with the wrong cause
- **Stakes**: Which reader claims the file and the cause printed in the refusal; no reported quantity moves, since the failure is a refusal; dissenter: GSAS-II scans the whole file (G2pwd_fxye.py:35-52)
- **Note**: Tier-3 candidate; the failure is a refusal naming the wrong cause, never a wrong pattern.

### `rietx.io.projects.fullprof._OCCUPANCY_RTOL`

- **What it does**: read fullprof.py:2364 and occupancy_factor (:2367-2455), :2725, :2730 and to_structure (:3635): a phase builds when every site's Occ x M_general/M_site is within 0.5 % of the largest; every site is then written occ = 1.0 with no diagnostic. The comment gives the corpus's Occ rounding as ~2e-5, so the tolerance is 250x the rounding. PROBED 2026-11-17 on the committed synthetic fixture with one site's Occ scaled (S/probe_occ.py): x0.996 builds with occ [1, 1, 1, 1] and only FULLPROF_SPECIES_NORMALISED; x0.9951 builds the same way; x0.995 is refused. The same constant gates the magnetic Scale x f^2 match (:2730), where a mismatch under 0.5 % merges unmentioned
- **Q1**: Shown ratios spread 0.4 %, would every competent refiner build the phase fully occupied? A caller with a real 0.4 % vacancy on one site (a refined partial occupancy in a .pcr written by FullProf itself) would not; the factor is separable only if the other sites are known full, which is the assumption the gate makes.
- **Q2**: One origin-choice failure family (a factor of two, which any tolerance below 1 catches) and the corpus's rounding (2e-5); no dataset family sits between 2e-5 and 5e-3, so the 5e-3 is a guess inside a gap no file measures. Fails at 0.4 %.
- **Stakes**: The site's structure-factor amplitude, up to 0.4 % of that site's contribution (|F|^2 up to 0.8 %), and a QPA fraction through it; a silent repair (no diagnostic) on every file inside the band; case on disk: none (the corpus's Occ is rounded at 2e-5); dissenter: none found.
- **Note**: FINDING (confirmed by probe, not fixed): a site at 0.996 beside full ones is built full with no diagnostic. Tightening the tolerance toward the rounding (say 1e-4), or emitting a diagnostic when the spread exceeds the rounding, changes reader output and goes to the maintainer.

### `CIF_MAGNETIC_NUCLEAR_GROUP` (magnetic)

- **What it does**: read the raise site at magcif.py:1160-1185 (resolve_nuclear_symmetry, nuclear_group='auto', the default): fires when the parent group the file names contains the file's operators and keeps every site's orbit; atom positions then refine under the parent, of index value= over the file's own group, and moments under the magnetic group; the suggestion names nuclear_group='file' (tests/test_magcif.py; WP-1328 records #457's three tiers). Practice: GSAS-II 5.8.4 replaces the parent's operators with the file's magnetic ones (SGFixed, imports/G2phase_CIF.py:312-341) and the nuclear and magnetic phases share that SGData, so positions refine under the file's own group and only the cell takes the parent's Laue class (docs/practice.md section 'A magCIF in a non-standard orientation'). FullProf, TOPAS not checked.
- **Q1**: No. A GSAS-II user refines positions under the file's own operators, and a refiner looking for the atomic displacements a magnetic transition allows (magnetostriction, a lowered nuclear symmetry) wants nuclear_group='file'; a refiner with no such displacement in the data wants the parent's fewer parameters. The choice is enumerable and the record names the switch, so it is a candidate for Rule 1's second kind.
- **Q2**: No dataset family measured: tests/test_magcif.py builds synthetic magCIFs, and no magCIF is under tests/data. Fails where the magnetic order does displace atoms: the parent holds them on its special positions.
- **Stakes**: coordinates and ADPs of a magnetic phase (which DOFs are free); none on disk; dissenter GSAS-II 5.8.4.
- **Note**: Magnetic path: memory says magnetic-path decisions are Mike's since 2026-11-04 (#1075); route this row's ruling accordingly. Ambiguity is my reading (the alternatives are two and a fit could rank them).

### `rietx.crystallography.magcif.MOMENT_FORM_AGREEMENT_MU_B` (magnetic)

- **What it does**: three uses: two statements of one moment (crystal-axis, spherical, Cartesian) differing by more than 0.02 mu_B per component are refused (magcif.py:1320-1333); the printed-digit box of CIF_MAGNETIC_MOMENT_ON_ALLOWED is capped at it (magcif.py:1560-1567); a duplicated magnetic site's moment must match the image moment to it (cif.py:515-519). Docstring: magCIF moments are quoted to five decimals at best and MAGNDATA rounds the spherical form to two, so round-off is ~1e-3 while a real contradiction is order the moment itself (tests/test_magcif.py).
- **Q1**: Yes for the refusal side: no refiner picks one of two contradictory statements of one vector. The 0.02 is a convention sized by MAGNDATA's printing; a file printing the spherical angles to one decimal would need more.
- **Q2**: Rare feature: one producer convention (MAGNDATA) read in synthetic magCIFs; no magCIF under tests/data. Fails on a spherical row whose angles are printed to 0.1 deg on a 5 mu_B moment (up to ~0.01 mu_B per component, inside) or 1 deg (~0.09, refused).
- **Stakes**: a refusal, and the cap on a moment move (at most 0.02 mu_B a component); none on disk; not checked.
- **Note**: Magnetic path: memory says magnetic-path decisions are Mike's since 2026-11-04 (#1075).

### `rietx.crystallography.magnetic.isotropy.CROSS_IRREP_DRAWS` (magnetic)

- **What it does**: draws per direction on a pair of magnetic models no certificate settles, when the caller names none: a pair 12 random draws fail to tell apart is reported sampled-equivalent (isotropy.py:224-238). Docstring: 8 % of the cubic pairs that 3 draws called equivalent were refuted within 12, 0.2 % at 12; on P n -3 m:1 at (0,0,1/2) 12 gives the four classes of the known answer, not two. tests/test_magnetic_isotropy.py::test_every_sampled_edge_prints_the_draws_it_actually_made and ::test_a_proved_separation_inside_a_joined_class_is_reported use it as the count, and no test varies it.
- **Q1**: A sampled verdict carries its label and its draw count, so the reader sees it is not proved; the count is a confidence level. A refiner screening many k-vectors quickly would accept fewer draws; one quoting the class count would want more.
- **Q2**: Rare feature: six cubic sets of one synthetic family (the module's own streams); no real magnetic pattern behind the 8 % and 0.2 %.
- **Stakes**: which magnetic models are joined into one class (four classes against two on the known answer); synthetic only; none found.
- **Note**: Magnetic path: memory says these rulings are Mike's (#1075).

### `rietx.crystallography.magnetic.isotropy.WITHIN_IRREP_DRAWS` (magnetic)

- **What it does**: draws per direction for two different directions of one irrep, which the isometry certificate does not settle (isotropy.py:224-238). Docstring: not measured the way CROSS_IRREP_DRAWS was; 12 there would cost about 4 min more on the known answer (an estimate).
- **Q1**: As CROSS_IRREP_DRAWS; the docstring itself says this one was not measured.
- **Q2**: None: no measurement, an estimate of cost only.
- **Stakes**: which directions of one irrep are joined; none on disk; none found.
- **Note**: Magnetic path (Mike, #1075). A test varying it on the known answer would give it q2.

### `rietx.crystallography.magnetic.moments.MOMENT_DIRECTION_SUPPORT` (magnetic)

- **What it does**: decides the moment-angle hold (refine._flat_moment_scan) and the stationary-angle test: a direction whose pattern response to a MOMENT_PROBE_ANGLE_RAD turn is under 1e-6 of the modulus's response is held (moments.py:110-144). Measured: ~1e-15 on the cubic collinear structure, ~1e0 on Cr2WO6 4 K under BNS 58.395; the joint Newton step reaches 1.3e-12 on the two-site Pnma set. tests/test_magnetic.py (ratio at a 1e-6 step under it, at the probe angle above 1e3 x it) and tests/test_stationary_moment_angle.py.
- **Q1**: Yes that an angle the data cannot see is held; the action's companion MOMENT_PROBE_ANGLE_RAD is tier 3, approved 2026-10-19 (B2). The cut sits in a fifteen-order gap on the cases measured, so no refiner shown those numbers would cut elsewhere.
- **Q2**: Rare feature: one real family (Cr2WO6, HB-2A) plus synthetic cubic and two-site Pnma sets; untested beyond them.
- **Stakes**: which moment angles a stage frees and every esd correlated with them; Cr2WO6 4 K on disk; none found.
- **Note**: A threshold on the pattern's response to a probe, so it is in the maintainer's reversed family (thresholded heuristics over fit metrics or residuals): batch, not tier 1 on the gap. Magnetic path: Mike (#1075).

### `rietx.crystallography.magnetic.moments.SEED_TILT` (magnetic)

- **What it does**: the fraction of the modulus tilted_seed puts on every moment-frame row beyond the first, to break the symmetric stationary point (moments.py:220-236); 0.15 lost two exact recoveries of WP-1418's 20 simulated MAGNDATA structures, 0.02 none; tests/test_magnetic_supercell.py pins the geometry (tan theta = SEED_TILT on a rank-2 site)
- **Q1**: Its alias rietx.strategy.magnetic.SOLVE_SEED_TILT is tier 3, approved 2026-10-19 (B12), and that row's evidence says this row takes the same tier. A starting value inside a pick verb whose ranking travels with it; no competent caller named who would seed differently on that evidence.
- **Q2**: Rare feature: one family, 20 simulated MAGNDATA structures (WP-1418).
- **Stakes**: which local minimum a magnetic solve lands in (two of 20 exact recoveries lost at 0.15); simulated only; none found.
- **Note**: The approval exists on the alias row; the session can write tier 3 here citing B12 (2026-10-19) if the maintainer agrees the approval covers both names.

### `rietx.crystallography.magnetic.scattering.INVARIANCE_MOMENT_TOL` (magnetic)

- **What it does**: the moment half of check_group_is_structure_symmetry's match: an image's moment agrees with the atom's to 1e-3 mu_B relative to max(1, |m|), else the declared magnetic group is refused as no symmetry of the structure (scattering.py:203-204, 288). No test names it.
- **Q1**: Yes that a declared group the moments do not satisfy is refused; the bar is a convention. A file printing moments to two decimals (5e-3) would be refused at it.
- **Q2**: No dataset family named; no test.
- **Stakes**: a refusal only; none on disk; not checked.
- **Note**: Magnetic path: Mike (#1075).

### `rietx.crystallography.magnetic.scattering.INVARIANCE_POS_TOL` (magnetic)

- **What it does**: the position half of the same match: an image within 1e-3 (fractional, per coordinate) of an atom of the compiled structure matches it; looser than SITE_TOL because two atoms the magnetic group relates may be listed separately at four decimals (scattering.py:199-202, 300). No test names it.
- **Q1**: Yes that a match is needed; 1e-3 is a convention about file precision. A file at three decimals (5e-4 rounding) fits; one at two does not.
- **Q2**: No dataset family named; no test.
- **Stakes**: a refusal only, or a silent acceptance of a near-symmetry if too loose; none on disk; not checked.
- **Note**: Magnetic path: Mike (#1075).

### `rietx.crystallography.magnetic.supercell.CHILD_SITE_TOL` (magnetic)

- **What it does**: an alias, CHILD_SITE_TOL = SITE_TOL, with no free factor (supercell.py:132-136): the child positions are the parent's pushed through an exact rational transform, so nothing is looser than site_orbit already accepts
- **Q1**: Inherits SITE_TOL's row (batched).
- **Q2**: Inherits SITE_TOL's row.
- **Stakes**: as SITE_TOL's row.
- **Note**: Tier it with SITE_TOL: a derived constant with no free factor takes its source's tier.

### `rietx.crystallography.representation.irreps.K_MAX_DENOMINATOR` (magnetic)

- **What it does**: largest denominator as_kvector reads out of a float k component; a component needing more is refused by name, never snapped (irreps.py:172-177); tests/test_incommensurate_irreps.py::test_door_refusals pins the value
- **Q1**: Yes that an irrational component is refused rather than snapped. A refiner with a long-period commensurate k (1/96) is refused and must pass it exactly, which is a cost, not a wrong answer.
- **Q2**: No dataset family; the docstring's claim that 64 admits every supercell refined is unmeasured.
- **Stakes**: a refusal only; none on disk; none found.
- **Note**: Could be caller-shaped if a Fraction input bypasses it; not checked.

## Left at `unaudited` (33)

A numerical setting is tier 1 only where a test bounds its error (B10, ruled 2026-10-19). These have no such test yet, or need one the lane could not write read-only. Each line says what would close it.

| Row | Why it waits, and what closes it |
|---|---|
| `rietx.crystallography.magnetic.isotropy.DEFAULT_CELL_SCALE` | Leave: it moves which shells enter a comparison, so it is neither invariant by construction nor bounded by a test. Closing test: run the known-answer classes at scale 4 and 6 A with d_min scaled alike and assert the same classes, or show the classes at fixed d_min do not change across the scales callers use. |
| `rietx.crystallography.magnetic.isotropy.DUAL_AFTER_RESTART` | Leave: whether a pair ends proved-not or sampled-not can depend on when the dual runs. Closing test: the known answer's verdicts and labels at 0, 1 and 3, asserted equal (an invariant row), or the differences named. |
| `rietx.crystallography.magnetic.isotropy.INTENSITY_RTOL` | Leave: B10 needs a test that the cut sits in a gap of the values it separates, as representation.incommensurate.LINE_ATOL's does. Closing test: record the relative values cut and kept at each use over the known-answer and P m -3 m sets and assert an empty band of several decades around 1e-9. |
| `rietx.crystallography.magnetic.isotropy.TRANSFER_FLOAT_STACK` | Leave: it changes a label and no verdict, but nothing pins where the label falls. Closing test: a transfer with mu below and one above 1e-8 asserting each label; then tier 1 as a stated qualifier. |
| `rietx.crystallography.magnetic.isotropy._CLOSURE_LIMIT` | Leave: a guard no test provokes is one no test sees regress. Closing test: monkeypatch it small to provoke the RuntimeError, and assert the largest closure the module builds over its own cases is far below 4096. |
| `rietx.crystallography.magnetic.isotropy._SPAN_GAP` | Leave: closing test records the relative values over the module's cases and asserts none falls in the gap, plus a synthetic stack with a value inside it that returns None. |
| `rietx.crystallography.magnetic.scattering.METRIC_TOL` | Leave: the measured gap is fifteen orders wide, so a test pinning the two arms (a consistent phase passing and a wrong-setting phase refused) would make it tier 1 on the gap, as LINE_ATOL's row is. |
| `rietx.crystallography.representation.distortion._POSITION_TOL` | Leave: closing test runs the distortion candidates at 1e-8 and 1e-4 and asserts the same child atoms, as subgroups._PROBE_SYMPREC's test does. |
| `rietx.crystallography.representation.distortion._PROBE_AMPLITUDE` | Leave: closing test as isotropy._PROBE_RMS's (tests/test_distortion_candidates.py::test_the_probe_tolerance_and_scale_decide_no_child), run on distortion's probe. |
| `rietx.crystallography.representation.distortion._PROBE_SYMPREC` | Leave: closing test as isotropy._PROBE_SYMPREC's, on this module. |
| `rietx.crystallography.representation.distortion._RANK_TOL` | Leave: closing test records the singular values cut and kept over the distortion suites and asserts a gap around 1e-8, as LINE_ATOL's test does. |
| `rietx.crystallography.representation.irreps._SEEDS` | Leave: a different successful seed can give a different basis within an irrep, and the direction labels are gauge-dependent (isotropy.py, magnetic candidates). Closing test: start the sequence at seed 3 and assert the same characters and direction labels over the 230-group sweep (then invariant). |
| `rietx.crystallography.representation.modes.MODE_ATOL` | Leave: closing test asserts a gap in the values it cuts over the mode suites. |
| `rietx.crystallography.representation.modes.POSITION_ATOL` | Leave: closing test holds the mode suites at 1e-8 and 1e-4 to the same matches. |
| `rietx.crystallography.representation.order_parameter.ISOTROPY_ATOL` | Leave: closing test asserts a gap in the values it cuts over the isotropy suites. |
| `rietx.crystallography.spherical_harmonics._TOL` | Leave: closing test asserts the projector residuals over the harmonic suites sit far below 1e-9 and a non-member far above. |
| `rietx.gui.imports.MAX_UPLOAD_BYTES` | leave: no test reaches the cap (grep tests/ for MAX_UPLOAD_BYTES finds none). A test that would close it: a Content-Length of cap+1 gets the 413 naming both numbers and reads no body; a body of exactly the cap is accepted; and the largest committed pattern/CIF is under cap/10. Then tier 1 (a cap whose refusal states the distance). |
| `rietx.gui.imports.PREVIEW_POINTS` | leave: the invariance is plausible but no test asserts it. It would assert that the project committed through the wizard is byte-identical with PREVIEW_POINTS patched to 100 and to 5000, and that the 900-point curve keeps the strongest peak of a 40 000-point pattern (decimation_index's own property). Then 'invariant'. |
| `rietx.gui.imports.WAVELENGTH_RTOL` | leave, with a finding: the tolerance is 5e-4 but a header that quotes Mo as 0.71 A (two decimals, as Cu is quoted 1.54 and matches) is not recognised and is offered as a single-wavelength capillary, though a two-decimal rounding bound would be 7e-3 and still 11x under the 8 % gap. The docstring says 'tight enough that no two anodes overlap' but gives 3 ppm as the loosest case it has to absorb. No test refers to the constant. A test that would close it: every common header spelling (1.54, 1.5406, 1.5418, 0.71, 0.7107, 0.56, 1.79) maps to its anode and no value in the table's range maps to two. Not changed: it moves a pre-filled instrument. |
| `rietx.gui.symmetry.LETTER_CACHE` | leave: invariant by construction but no test names it. A test would call site_letters with the cache cleared and at maxsize 1 and assert the same letters as the default (tests/test_gui_server.py:1497 is the neighbouring cache test, not this one). Then 'invariant'. |
| `rietx.gui.symmetry.ORBIT_COLLISION_TOL` | leave: the tests fix the occupancy logic, not the 1e-3. Tier 1 needs a test showing two atoms 5e-4 apart collide and two 2e-3 apart do not, and that on every committed structure the nearest distinct-orbit pair is more than 10x the tolerance away (CIF coordinates carry 4-6 places, so 1e-3 is the stated rounding scale). It gates a model edit, so it is not an invariant. |
| `rietx.gui.symmetry.POSITION_TOL` | leave: no test sits at the boundary. Tier 1 needs a test that a position 5e-7 off the subspace is accepted and 2e-6 off is refused, and that every coordinate of the committed example CIFs round-trips through position_values unchanged. The docstring gives the argument: CIF coordinates carry 4-6 places, above the lstsq round-off. |
| `rietx.io.formats.base.INTEGRAL_TOL` | Leave. A closing test would assert, on float32-stored and 4-decimal-text rates over counts 1e3..1e6 and t in {0.31, 1, 10, 100} s, that integral(y*t) is True exactly while the representation error is below the bar and never True for a count scaled by a non-whole factor over N >= 1000 points; the failure side must be 'withheld'. Finding: an absolute 1e-3 against float32's relative 6e-8 means a high-count rate file, stored float32 (Bruker RAW), loses sigma derivation above about 2e4 counts at sub-second steps. |
| `rietx.io.formats.dif._MIN_ROWS` | Leave. No test drives the row-count path. It would assert, for header-less hkl tables named .dif of 1..6 rows, the boundary (claimed from 3), and that a two-column scan named .dif of any length is never claimed. Same family of failure on both sides is tiny; I could not measure it beyond the synthetic file. |
| `rietx.io.formats.peaklist._MIN_ROWS` | Leave. Closing test: parametrize plain two-column .pks files of 2..12 numeric rows and assert the boundary at 8, plus the same 40-row file under _MIN_ROWS patched to 3 and 20 giving one answer, which would make it invariant. A real peak list that is header-less and all numeric with 8 or more rows would be read as a profile; none exists to test against. |
| `rietx.io.projects.fullprof._CELL_TIE_MULTIPLIER_TOL` | leave: arithmetic argument, no boundary test. It would assert that two cell codewords whose multipliers differ by 1e-5 (the .pcr's last printed place) are reported dropped and two identical ones carried. Closes as tier 1. |
| `rietx.io.projects.fullprof._DISPERSION_ATOL_E` | leave: no test sits at the boundary and no table of the two tables' disagreement is recorded. It would assert, over every element at the standard anode wavelengths, the largest /f'(FullProf) - f'(rietx)/ a rewritten file can show for a pair that is the same model (print rounding only) against the smallest for pairs that differ, so 0.01 separates them (tests/test_projects_fullprof.py::test_the_reader_reads_a_files_own_dispersion_and_refuses_a_different_one tests refusal, not the margin). |
| `rietx.io.projects.fullprof._MAGNETIC_MATCH_ATOL` | leave: no boundary test. It would assert that a magnetic phase whose cell differs by 5e-5 still finds its partner and one differing by 2e-4 is refused with 'share its cell'. Magnetic-path (Mike's) for the merge itself. |
| `rietx.io.projects.fullprof._RHOMBOHEDRAL_ANGLE_ATOL` | leave: no boundary test (tests/test_projects_fullprof.py:1849 tests an exact rhombohedral cell only). It would assert that a rhombohedral cell with 5e-4 relative and 5e-3 deg noise reads as :R, that 2e-3 and 2e-2 deg does not, and that no a = b != c, gamma = 120 deg hexagonal cell reads as :R at any c/a. Then tier 1. |
| `rietx.io.projects.fullprof._RHOMBOHEDRAL_LENGTH_RTOL` | leave: same closing test as _RHOMBOHEDRAL_ANGLE_ATOL. |
| `rietx.io.projects.fullprof._USER_B_ATOL_FM` | leave, with a finding: the 1e-3 admits a FullProf-rewritten file only if FullProf prints DFP with four decimals, which no test records (the neighbouring FullProf oracle says DEU 0.6671 is used as 6.67 fm, i.e. FullProf shows two decimals of b). A refusal is loud, so the direction is safe. A test that would close it: take the DFP a FullProf run writes into its .new/.pcr for each isotope (measured, FullProf 8.20) and assert the reader accepts all of them. |
| `rietx.io.projects.registry.INP_SNIFF_BYTES` | leave: a cap that decides whether a file is claimed. A test would place the first str block at 60 000 and at 70 000 bytes and assert the first is claimed and the second is refused by name (not read as another format), and that every committed .inp has its opener inside a quarter of the cap. |
| `rietx.io.projects.topas_input.DEFAULT_RADIUS_MM` | leave: no test shows the answer does not depend on the number. It would write the same instrument at goniometer_radius_mm = 100, 217.5 and 500 and assert the written displacement and Finger terms give identical values at every 2-theta (a small calculator over the written equations), or TOPAS's own Y_calc agrees across the three. Then 'invariant'. |

## Reader decisions audited by hand

### `bruker_raw.py _v4_axis atol=1e-6 (src/rietx/io/formats/bruker_raw.py:346)`

- **finding**: np.isclose(d.position, start, atol=1e-6) is called with numpy's default rtol=1e-5 as well, so the effective tolerance is 1e-6 + 1e-5*|start|: 1.01e-4 degrees at a 10 degree start and 8.5e-4 at 85 degrees, 100 to 850 times the written atol. It chooses which drive record is the scanned axis (flagged non-zero and at the start angle), and the rest of the function falls back to the ScanType string when the count of candidates is not exactly one. On the one real v4 file (bruker_raw4_scrambled.raw) the scanned drive's position equals the start exactly (difference 0.0, probe 2026-11-17) and the other drives sit 5 degrees or more away, so any tolerance from 0 to under 5 degrees gives the same pick. Direction of failure: a tolerance too tight drops to the ScanType answer (visible through check_axis); too loose could admit a second flagged drive and also drops to ScanType. Neither picks a wrong axis silently on the evidence available
- **proposed tier**: leave (a numerical tolerance, tier 1 only with a test; none exists)
- **evidence**: tests/writers_xrd.py:74-90 can write drives with chosen positions and flags, but no test varies the position offset. A closing test would write a v4 file with the scanned drive's position offset from the start by 0, 1e-7, 1e-5, 1e-3, 1e-1 degrees and assert the axis pick and the fallback message at each; it would also pass rtol=0 explicitly if 1e-6 is the intended bar. Only one real v4 file exists, and its intensities are scrambled, so the pick is the only thing it proves

### `bruker_raw.py counting-time windows (bruker_raw.py:405 and 638)`

- **finding**: v4: step time is accepted as a counting time only when 0 < step_time_ms < 1e9 (bruker_raw.py:405, milliseconds, about 11.6 days). v3: 0 < step_time < 1e6 (bruker_raw.py:638, seconds, the same 11.6 days). Outside the window the time is None. It decides whether sigma_by_arithmetic (base.py:709-754) can test y*t for integrality: with a time, an all-integer y*t gives a derived sigma; without one, a non-integral y withholds sigma with PATTERN_INTENSITY_SCALED. All-integer y gives the Poisson fallback regardless of the time. The two windows are the same number in different units (1e9 ms = 1e6 s), so they agree. The real fixture's 310.003 ms is far inside. Not a physical constant: the upper bound only screens absurd values, and the lower bound 0 is arithmetic (a time must be positive). A second finding: the later y*t test uses INTEGRAL_TOL = 1e-3 absolute on float32 data, so a rate file with counts above about 2e4 per point at 0.31 s per step cannot verify and loses its derived sigma (measured, probe_tol-style simulation 2026-11-17: counts up to 1e4 pass, 3e4 fail)
- **proposed tier**: 1 for the lower bound (positive time is arithmetic); the upper bound 1e6 s is a sanity screen, leave: tier 3 own number with no measurement, or invariant if a test shows no real file's time exceeds it and any bound from 1e3 s up gives the same sigma
- **evidence**: tests/test_readers.py::test_the_real_v4_fixture_withholds_sigma_because_no_scale_verifies (real file, 0.31 s). No file with an absurd time is on disk. A closing test would write a v4 header with step time 0, -1, 1e3, 1e6, 1e9, 1e10 ms and assert which yield a count_time_s and what sigma results for an integral and a non-integral y

### `pdcif.py weight column on one bad weight (src/rietx/io/formats/pdcif.py:113-139)`

- **finding**: The inherited note is stale for a zero weight. Probed at HEAD with a six-point pdCIF (probe_pdcif.py, 2026-11-17): one zero weight keeps sigma = 1/sqrt(w) for the other five points, excludes the zero-weight point as an excluded region and emits PATTERN_ZERO_WEIGHT_EXCLUDED (info); the docstring says 'Before, one zero dropped the whole column to the Poisson fallback and said nothing' (pdcif.py:70). What still holds: one negative weight or one missing weight ('?' or '.', read by gemmi as NaN) drops the whole column and falls back to Poisson sigma, with PATTERN_WEIGHT_UNUSABLE (info) counting the negative and missing entries, emitted only when the caller passed a diagnostics list (pdcif.py:123, 'elif diagnostics is not None'), so a call without the list is silent. A user sees: a pattern read with Poisson weights and one info line naming 'N negative weight(s) and M missing weight(s)'. xy.py and chi.py instead adopt any positive third column as sigma and pass a sigma <= 0 to read_pattern's hook, which leaves just that channel out (WP-1952, CLAUDE.md Weights). So pdCIF treats one bad weight as 'no column', xy as 'one bad channel', and the two disagree. The maintainer already ruled on the pdCIF side on 2026-10-26 to keep the whole-column fallback and report it, citing that no program surveyed uses a pdCIF weight column (_audit.py PATTERN_WEIGHT_UNUSABLE row; docs/practice.md § A pdCIF weight column with bad entries, issue #1181)
- **proposed tier**: no change: PATTERN_WEIGHT_UNUSABLE and PATTERN_ZERO_WEIGHT_EXCLUDED are already tier 1 rows and stand; drop the stale inherited note
- **evidence**: pdcif.py:113-156 read; probe output: zero -> ['PATTERN_ZERO_WEIGHT_EXCLUDED'], negative -> ['PATTERN_WEIGHT_UNUSABLE'], missing -> ['PATTERN_WEIGHT_UNUSABLE'], clean -> []. Nothing was changed. The remaining difference from xy (whole column versus one point) is a recorded ruling, not a new decision

## Notes on tiered rows

Questions the lanes raised on rows they did tier. None changed a level or a message.

| Row | Note |
|---|---|
| `BRML_ABSORBER_ENGAGED` | Measured on one real file only. If a second .brml with a varying factor disagreed, the row would reopen. |
| `CIF_CELL_ANGLE_CORRECTED` | The 0.1 deg band is the tier-3 part and is batched on CIF_ANGLE_CORRECT_MAX_DEG's row. Finding (not a defect of this code): an angle within SYMMETRY_ANGLE_TOL_DEG of its value is neither snapped nor reported (cif.py:98 continues), so 90.0008 deg under an orthorhombic symbol stays in the model at its stored value, silently; the d-spacing bias is at most 8.3 ppm by that constant's docstring. |
| `CIF_MAGNETIC_SYMMFORM` | No response: the level is set at run time (info or warning). Question for the maintainer under 'Attention is a cost' clauses 1 and 2: the agreeing case is an info that fires on every site of a file that writes symmform (MAGNDATA does), and the disagreeing case is a different consequence carried by the same code; two codes, or no diagnostic on agreement, would follow the clause. |
| `CIF_MAGNETIC_UNIDENTIFIED` | No test fires this code; a test with one of spglib's three missing groups would pin it. |
| `CIF_SITE_LISTED_TWICE` | GSAS-II does not drop the copy by default, so this act is not tier 2; I tier it 1 on the overfill arithmetic. A judge who reads GSAS-II as a dissenter would batch it. |
| `CIF_SITE_TWINS_MERGED` | No program checked does this by default, so the tier rests on the overfill arithmetic alone. |
| `FULLPROF_MAGNETIC_PHASE_OMITTED` | The caller class holds only while nuclear_only stays off the default paths. |
| `FULLPROF_MAGNETIC_PHASE_READ` | Magnetic-path decisions are Mike's; this tiers the act only. The scale-product gate uses _OCCUPANCY_RTOL (0.5 %), so a Scale x f^2 mismatch under 0.5 % merges with no mention: moments then come out up to 0.25 % off. See the _OCCUPANCY_RTOL row. |
| `FULLPROF_OCCUPANCY_UNCHECKED` | DEFECT, not fixed: the condition (len(atoms) == 1, fullprof.py:3515) is broader than the message ('passed without testing the setting'). A one-atom phase in F m -3 m or P 42/m n m has no second setting, yet gets the warning, so the warning fires on every one-atom phase. A fix that restricts it to symbols with an origin alternative changes reader output and goes to the maintainer. Whether warning is the right level for a fact that does not discriminate is the clause-2 question. |
| `FULLPROF_OCCUPANCY_UNCHECKED.suggestion` | Fires on every one-atom phase (see the code row), including those with no second setting. |
| `FULLPROF_ORIGIN_CHOICE` | The occupancy gate that the message says 'accepted this setting' is _OCCUPANCY_RTOL (batch row), and is vacuous for a one-atom phase (FULLPROF_OCCUPANCY_UNCHECKED). Manual not re-read beyond the one note; GSAS-II and TOPAS read a bare symbol as gemmi does (choice 1) but never read a .pcr. |
| `FULLPROF_RHOMBOHEDRAL_RESTATED` | No response: the raise site is a helper whose literal level 'warning' the part-1 scan does not see (levels empty). If the lead wants a response row, it is warning with responds naming the cell and scale: 'quote no FullProf cell or scale from this file as rhombohedral; both are hexagonal'. Shared with GSAS2_CIF_RHOMBOHEDRAL_RESTATED. |
| `FULLPROF_SPECIES_WRITTEN_NEUTRAL` | No response: helper-raised (levels empty). Shared with the GSAS, GSAS-II and TOPAS writers. |
| `GSAS2_CIF_FIELD_NOT_WRITTEN` | Fires on every write, so under clause 1 it is a fixed notice; whether that earns a diagnostic is the maintainer's. |
| `GSAS2_CIF_RHOMBOHEDRAL_RESTATED` | No response: helper-raised (levels empty). |
| `GSAS2_CIF_SPECIES_WRITTEN_NEUTRAL` | No response: helper-raised (levels empty). |
| `GSAS2_GPX_ITEM_NOT_READ` | Which constructs are listed is the reader's table of what it builds, not a threshold. |
| `GSAS2_GPX_PHASE_MAGNETIC` | No response: levels are '' and 'warning' (two levels). Under clause 2 'one code, one level' this is two consequences (the figures the file quotes include magnetic scattering, or they do not) under one code, which is the shape clause 2 says to split; reported, not changed. Issue #606 explains the second site. |
| `GSAS2_GPX_TEXTURE_NOT_CARRIED` | No response: the level is a parameter of the helper (levels ['']), warning or info by reason. |
| `GSAS2_INSTPRM_CONVENTION_ASSUMED` | Source-checked on GSAS-II 5.8.4 at the lines named. The module docstring of recipe.py says the split is 'adopted, not measured', which the GSAS-II source settles; RECIPE_CONVENTION_ASSUMED shares the row's ground. |
| `GSAS2_INSTPRM_FIELD_DROPPED` | where is built at run time from the key list, so the walk sees no where; scope given for that reason. fltPath is a number the file states and the schema drops (l1_m is read from INS FPATH1 in the .iparm reader only); the message names it, so it is reported, not silent. |
| `GSAS2_INSTPRM_FIELD_NOT_WRITTEN` | Fires on every write, so a fixed notice (clause 1). |
| `GSAS2_INSTPRM_VALUE_MERGED` | The FCJ profile depends on s and h separately (fcj.py trapezoid weight), so unequal apertures are a real loss, which the warning states. |
| `GSAS_EXP_SPECIES_WRITTEN_NEUTRAL` | No response: helper-raised (levels empty). |
| `GSAS_IPARM_FIELD_DROPPED` | where is the run-time list of dropped keys, so the walk sees no where; scope given. |
| `GSAS_IPARM_LEGACY_LAYOUT` | Not caller: the verb is opt-in, but the package chose the slot mapping inside it (generality.md, Caller condition 2). The three unnamed slots (1, 5, 8) rest on the manual alone; GSAS-II carrying them under no name is silence, as the module says. All fixtures synthetic. |
| `GSAS_IPARM_PROFILE_DECLINED` | Mixed levels, no response proposed. Dissent on (a): GSAS-II 5.8.4 GSASIIfiles.py:263-271 reads the older unnumbered header form ('INS 1PRCF ' then 'PRCF 1', 'PRCF 2'); rietx declines it, the stricter side, so nothing is guessed. A caller with such a file loses the profile and gets the warning. The warning at (a) and (b) leaves peak-width coefficients at zero, which a TOF refinement would then have to free. |
| `GSAS_IPARM_PROFILE_READ` | The message says 'That order is an assumption'. With GSAS-II agreeing on the slots it reads, the wording could soften to name the check; I propose no message change. Slots GSAS-II does not read (function 3's gam-*, g1ec and the rest) still rest on the manual alone. |
| `GSAS_PRM_FIELD_NOT_WRITTEN` | Fires on every write, so a fixed notice (clause 1). |
| `GSAS_PRM_GEOMETRY_ASSUMED.suggestion` | The code row is batch (the default itself departs from GSAS-II for a doublet); the suggestion only gives the caller's remedy. |
| `PATTERN_INTENSITY_SCALED` | where is ['sigma'], not a parameter path, so the level under a purpose follows scope; 'all' because weights shape every result number. The gsas site reads the values as written and withholds sigma only. |
| `PATTERN_SIGMA_CONSTANT` | Part 1 read this as a judgement. The message and suggestion assert nothing about placeholders: the message gives the value and count, the suggestion starts 'If the column is a placeholder'. Level warning kept as live. |
| `PATTERN_X_AXIS_ASSUMED` | The refusal half (a named non-2theta axis) is the tier-1 physics of the same function and is not a row. Level warning kept as live. |
| `PATTERN_X_AXIS_IMPLAUSIBLE` | Part 1 read this as a judgement. It asserts the axis may not be 2theta only in the suggestion's conditional ('Check that...'); the evidence is an arithmetic comparison against a physical zero. where is an interval string, not a parameter path. |
| `RAS_ATTENUATOR_PRESENT` | Brief: 'if the convention was assumed, batch'. I tiered it 2 instead because the act (do nothing to column 2, tell the reader) matches GSAS-II's default and takes no decision a refiner could reverse, with the open convention carried in the warning. If you read the unmeasured convention as the heuristic, move it to batch. A real .ras with a varying column would settle the convention and make the row tier 1. |
| `RECIPE_BACKGROUND_PEAK_DEGENERATE.suggestion` | The code row is batch; the suggestion repeats the HumpComponent record. |
| `RECIPE_CONVENTION_ASSUMED` | The docstring's 'adopted, not measured' is out of date against the GSAS-II source; the row evidence is from the source. |
| `RECIPE_DISPERSION_DECLINED` | For W (K edge 69.5 keV) at 74.5 keV the f' and f'' are not small, so f = f0 is a real approximation, stated in the docstring. |
| `RECIPE_FIELD_DROPPED` | No response: levels are info and warning (two). The sub-step gamma test (width < one step) is a threshold set by the data's own grid, tiered here as arithmetic. |
| `RECIPE_PLAN_STAGED` | PowderLine's own engines run one pass; staging is rietx's shape. Cumulative staging moves a converged value by up to 0.0004 esd on one fit (root CLAUDE.md, WP-2045), measured, not zero. |
| `RECIPE_ZERO_WEIGHT_EXCLUDED` | Row #1006's pdCIF weight-column question is the pdcif reader's, not this one. |
| `SITE_SNAPPED_TO_SPECIAL_POSITION` | The existing row's response and responds are kept word for word. The cif.py site moves the coordinate, which GSAS-II never does; it acts on the file's own stated multiplicity, and that tolerance is batched on CIF_STATED_MULTIPLICITY_SNAP_TOL. |
| `TOPAS_FIRST_RUN_READ` | The reader offers no run selection (compare scan= for patterns, io/CLAUDE.md), so for a multi-run file the first run is the only one reachable; reported, not changed. |
| `TOPAS_MAGNETIC_GROUP_READ` | Magnetic-path decisions are Mike's; this tiers the act. |
| `TOPAS_MOMENT_CONVENTION` | Magnetic-path decisions are Mike's; measured on one monoclinic and one orthogonal cell. |
| `TOPAS_PHASE_RESTATED_IN_P1` | Holds only while p1_expand stays off the default paths. |
| `TOPAS_PHASE_TERM_READ.suggestion` | Rests on a batch code row (the p<i>_<term> convention is rietx's own). |
| `TOPAS_SPECIES_WRITTEN_NEUTRAL` | No response: helper-raised (levels empty); two call sites. |
| `XRDML_ATTENUATOR_APPLIED` | Measured on one real file. The sibling Rigaku row is unmeasured and differs. |
| `rietx.crystallography.atomic_volume.TABLE_TEMPERATURE` | Hofmann's sample is CSD organic and metal-organic crystals (VOLUME_RATIO_BOUNDS' row). |
| `rietx.crystallography.magnetic.p1._WRAP_TOL` | No test names it; a test wrapping -1e-17 would pin it. |
| `rietx.crystallography.satellites._ORDERS` | Higher-order satellites (a squared-up modulation) are outside this rung by its docstring. |
| `rietx.crystallography.symmetry._SNAP_MESSAGE_SITES` | No test varies it; rietx.refine.RESTRAINT_PAIRS_STALE_LISTED's invariant row has one, and a matching test would close the gap. cif.py's twin of this cap is an inline 4 (cif.py:1457, 1471). |
| `rietx.crystallography.symmetry._SNAP_NOISE` | No test names it; the reach of the floor follows from SITE_TOL's tests. |
| `rietx.crystallography.symmetry._TRANSLATION_DEN` | No test asserts the 1/12 claim; a non-tabulated operator with a 1/8 translation would round to 1/6 and could compare equal to a tabulated one. A test over gemmi.spacegroup_table() would pin it. |
| `rietx.io.formats.gsas.TIME_MAP_FIELD_CHARS` | The real file is not vendored (copyright); the width is checked on a synthetic copy of its layout. |
| `rietx.io.instrument_profile._PRM_CUTOFF` | Dissent: GSAS-II's own test inputs state 0.01 (tests/testinp/INST_XRY.PRM, inst_d1a.prm), so the program uses both; the exporter's value is the default it writes. Tier 2 rests on the exporter. |
| `rietx.io.projects.topas_input.CALC_POINTS_PER_FWHM` | Three cases (neutron, X-ray, neutron P-spline) pass the bar with the constant; the step-1 failure is recorded in the docstring and not asserted by an arm test. The worst case is the sharpest peak on a coarse step, which the cases do not push to the limit. |
| `rietx.io.projects.topas_input._SABINE_XPOL` | No test pins the topas_input copy to model.extinction's; a second copy of a constant. |
| `rietx.io.projects.topas_input._TCH_ETA` | A second copy of the constant; no test pins this copy to pseudovoigt's. The written file carries rietx's, so TOPAS matches it (oracle tests). |
| `rietx.io.projects.topas_input._TCH_GAMMA` | As _TCH_ETA. |
| `rietx.io.readers.TWO_THETA_MAX_DEG` | The refusal is on the end of the axis only (hi > 180, an end of exactly 180.0 reads). A real instrument's zero offset could in principle put a 180.0 end at 180.02; not seen on disk. |

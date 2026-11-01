# WP-1911 — the foreign writers state what the other program reads: the setting, the scale, the free set

Milestone: unscheduled · Status: 🔄 2026-10-12 — PRs #720, #731, #710, #733, #713, #771, #782, #770 (Part B's TOPAS writer), #755 (C1's `Zero`) and #815 (#732's whole TOPAS input) and #839 (its X-ray extinction) and #912 (#721's item 3 on the P1 route) merged from outside; the decision on the rest of #721 is due
Track: Coming from another code
Depends on: — (#713 soft: the P1 restatement Part D builds on)
Priority: P3 2026-10-06 — was P2 for #716, which PR #733 fixed; the remaining issues cost a user hand edits

## Goal

A file written by `write_topas_inp`, `write_fullprof_pcr`, `write_gsas_exp`
or `write_gsas2_phase_cif` is checked against how the program it is for reads
it, not only against rietx's own reader. It states the crystal rietx fitted or
refuses by name, it says what scale it states, and it can free what the fit
freed. The `.pcr` refusals that exist only because a convention was never
measured are measured and lifted, and a magnetic phase has a route to TOPAS
beyond a hand-written P1 list.

## Context

### Why one WP: the round trip cannot see any of this

`src/rietx/io/CLAUDE.md` § Project writers: "A writer is its own reader's
inverse and its acceptance is the **round trip**". Every writer here passes
it. WP-1527 (closed 2026-10-04) found the first fact the round trip cannot
see: GSAS-II read `7Li` as hydrogen while rietx read its own file back
correctly. It answered with an **oracle**: a test that reads the written file
by the other program's *measured* rule, held first to the measurement table
it implements (`tests/test_projects_fullprof.py`,
`test_the_fullprof_oracle_reproduces_the_measured_lookup`). Five issues from
one contributor (mustachefeeling), all filed 2026-10-05 from an exporter
benchmark that ran TOPAS 6, FullProf.2k 8.50 and GSAS-II 5.6.3 as black
boxes, are that gap for four more facts: the setting (#716), the scale and
the free set (#722), the terms the `.pcr` writer refuses (#723), and the
magnetic route (#721, with #715's loop). The rulebook rule this WP adds is
WP-1527's oracle, generalised: for each fact two programs can read
differently, the writer's test reads it the target's way.

### The shared primitive: a phase restated in another setting

No structure-level setting change exists at `32ef5a6`: only
`MagneticGroup.transformed` (`crystallography/magnetic/operators.py:534`,
group level) and the superspace one. Three parts need the same thing: Part A
(write an `R … :R` phase as its hexagonal-axes equivalent), Part C item 4
(origin choice 1 restated as choice 2) and Part D (a magnetic phase at its BNS
standard setting). It is an exact change of basis applied to the cell, the
coordinates, an anisotropic U (a tensor, transformed on both sides, which is
where root CLAUDE.md's Rᵀ-versus-R clause bites), a moment (an axial vector)
and the operators; a Stephens block or restraints are refused, as PR #713's
`restate_phase_in_p1` refuses them. That clause's trap applies here too: every
count passes under the wrong action, so the test is `predict()` on the
restated phase against the original (PR #713 reports 1e-12 that way for P1),
never a multiplicity or a DOF count.
The obverse hexagonal ↔ rhombohedral matrix is *International Tables* A,
Table 5.1.3.1.

### Part A — the setting (#716, a bug)

A `.pcr` has no axis or origin suffix. `write_fullprof_pcr` writes `R -3 c`
beside a rhombohedral cell (a = b = c, α = β = γ) because its own reader
picks `:R` from that metric (`normalize_space_group`, `fullprof.py:1038`,
`_is_rhombohedral_metric` at `:1016`). That rule was written to "close a gap"
(`tests/test_projects_fullprof.py:1833`; every corpus R phase is hexagonal),
never measured against FullProf, and
`test_write_fullprof_pcr_round_trips_both_r_lattice_axis_choices` pins it.

*Measured by the reporter* (FullProf.2k 8.50, `.out`): the phase `R -3 c:R`,
a = 5.4226 Å, α = 55.2757° comes out as `Direct cell parameters: 5.4226
5.4226 5.4226 90 90 120`, V = 138.087 Å³, a different crystal; `R -3 c R`,
`R -3 c :R`, `R -3 c :H` and `R -3 c H` are each "illegal". GSAS-II 5.6.3's
`add_phase` refuses `write_gsas2_phase_cif`'s file: "Numbers of symmetry
elements from input (12) does not match GSAS-II's list (36)". TOPAS 6 accepts
`space_group "R -3 c:R"` with the rhombohedral cell (12 positions).

*Checked at `32ef5a6`* with the reporter's script (Fe³⁺ 12c at x = 0.1448,
O²⁻ 18e at (0.9407, 0.5593, 0.25)): the `.pcr` states `R -3 c` and
`5.4226 5.4226 5.4226 55.2757 55.2757 55.2757`, no diagnostic. The GSAS-II CIF
states `_symmetry_space_group_name_H-M 'R -3 c'` (the tag GSAS-II's importer
reads first, per ATTRIBUTION.md's GSAS-II CIF row), `_space_group_name_H-M_alt
'R -3 c:R'` and 12 operator rows, with an info `GSAS2_CIF_SETTING_IN_OPERATORS`
that explains it as an origin-choice disagreement, which this is not. rietx
reads both back as `R -3 c:R`. The reporter's 138.087 Å³ is exactly
a³ · sin 120° for a = 5.4226 (the rhombohedral cell is 100.369 Å³, the
hexagonal cell of the same lattice 301.106), so FullProf kept the edges and
imposed the hexagonal angles. The `.EXP` writer writes `SG SYM  R -3 c:R` (and
`F d -3 m:2` for an origin choice); its docstring's "the `:2`/`:R` suffix
travels and no refusal is owed" (`gsas.py:1852`) rests on rietx's reader only,
and no GSAS-I run has checked it.

The reader rule meets the same question from the other side: FullProf reads a
bare R symbol on hexagonal axes and forces the angles, so a `.pcr` stating
a = b = c, α = β = γ ≠ 90 beside a bare R symbol is, to FullProf, a symbol and
a cell that contradict. Root CLAUDE.md's rule for that case is refusal (a
symmetry-fixed angle disagreeing with its symmetry is refused, not
normalised).

### Part B — the scale and the free set (#722)

Every writer writes `Phase.scale` verbatim (`topas.py:4550`;
`fullprof.py:3620`) and each `Parameter.vary` as stored. The TOPAS and `.pcr`
*readers* read the scale verbatim too (`topas.py:4222`, `fullprof.py:2858`),
while the GSAS `.EXP` and `.gpx` readers drop it as not comparable
(`GSAS_EXP_SCALE_NOT_COMPARABLE`, `GSAS2_GPX_SCALE_NOT_COMPARABLE`) and
`read_recipe` reseeds it (`RECIPE_SCALE_RESEEDED`: GSAS-II 3.77e-2 against
TOPAS 2.61e-6 on one specimen). Four formats, three stances.

*Measured by the reporter*, zero cycles against `predict()` on the same
points: program scale / rietx scale = 0.01 (TOPAS, neutron), 1/K with K the
polarization constant (TOPAS, X-ray), 0.005 ± 0.2 % over four cases
(FullProf, neutron), ≈ 1.00 (FullProf, X-ray). A cold start 100-200× off
drove one TOPAS refinement to a negative B on Fe and B = 14.6 Å² on Sb, and
one FullProf refinement to NaN. These are not reproduced here; nothing the
issue measured is a tolerance until a committed program output produces it.
The precedent for committing one is
`tests/data/topas_moment_basis_A_mono3_mag_hkl.txt`: TOPAS output for an input
of ours, numbers only, with its `tests/data/README.md` row.

*The flags, checked at `32ef5a6`*: a plan **replaces** the vary flags per
stage (WP-1208), and `Refinement.fitted_structure` returns `self.structure`
(`refine.py:5033`), whose flags are the input's. On the synthetic LaB₆ of
`tests/test_refine_synthetic.py` under `mccusker_default` (converged),
`result.parameters` lists 14 free paths (cell a/b/c, scale, `atoms.1.x`, zero,
u v w x y, c0-c2), `fitted_structure` keeps the input's flags (atoms held,
`cell.a` free, scale held), and the written `.inp` carries one `@` and 16 `!`.
`ref.parameters()` reports the scale free: the free set lives in the table and
the result, not on the models. The skill's `references/api.md` says each
writer gives "a file whose refine flags reproduce the `Structure`'s `vary`
exactly", which is true and is the gap.

The reporter's options: (1) document each constant, measured; (2) opt-in
`write_*(…, scale="program" | "rietx", free=result_or_paths)`, the X-ray or
neutron choice needing `instrument=` as `write_fullprof_pcr` already takes;
(3) change `fitted_structure` to carry the last stage's free set. Recommended
by the reporter: 1 now, 2 as the fix, not 3. **Decision: the maintainer's.**
Freeing a narrower-flag format follows the rulebook: "a flag narrower than the
model merges free, and the group is named".

### Part C — the `.pcr` refusals (#723)

`write_fullprof_pcr` refuses by name, at `32ef5a6`: a non-zero zero shift and
sample displacement, transparency and both capillary offsets
(`_refuse_dropped_instrument`, `fullprof.py:3119`), absorption, roughness,
extra components, a polarization other than 0.5 (`:3172`), a λ/2 line
through the `harmonics` refusal (`:3080`), extinction (`:3449`), March–Dollase
(`:3455`), an occupancy other than 1 (`:3510`), and origin choice 1 through
the setting check (`:3557-3577`). The writer's own reason: "their sign and
unit conventions against rietx's are not measured, and a guessed mapping moves
every peak or rescales every intensity". So each item is a FullProf
measurement first, then a few lines. A partial occupancy is refused by the
*reader* too (`occupancy_factor` refuses a partial `Occ`), so that item
changes both halves. On the synthetic LaB₆ fit above,
`write_fullprof_pcr(fitted_structure, instrument=fitted_instrument)` refused
at the zero shift (0.00798°): the first item shows on the smallest real case.

The reporter's order: (1) `Zero`, `SyCos`, `Occ`; (2) `Cthm`/`Rpolarz` and
`Lambda2` + `Ratio`; (3) extinction and March–Dollase with FullProf's
conventions measured; (4) origin choice 1, the largest and least useful,
last. The reporter does not list transparency, the capillary offsets,
absorption, roughness or extra components; whether they join is open.

### Part D — the magnetic route beyond P1 (#721, #715)

A magnetic phase reaches no foreign program at `32ef5a6` except as a magCIF
(`Structure.to_cif`, which drops the parent k). The FullProf, GSAS and GSAS-II
writers refuse one by design (`crystallography/symmetry.py:103`,
`refuse_magnetic_phase`; #470, measured on GSAS-II 5.6.3), and stay refused.
`write_topas_inp` writes `mag_space_group <BNS>` only when the phase's
operators are that number's standard setting, and `_magnetic_group_line`
(`topas.py:4332`) refuses a propagation vector, a parent k, an unnamed group,
a non-standard setting, a nuclear group larger than the family group, and a
moment ion other than the species. The repo's Cr₂WO₆ magCIF fixture
(`tests/test_magcif.py`, tier 1, index 2) stops at the non-standard-setting
refusal (BNS 58.395) under both `nuclear_group="auto"` and `"file"`.

PR #713 (fork, open; #709) adds `restate_phase_in_p1` and
`write_topas_inp(p1_expand=True)`, which writes `mag_space_group 1.1` and
holds every parameter, the ties that made copies one parameter having no
written form. #721 proposes, after it: (2) the structure-level transform
above; (3) ties in the TOPAS writer, a `prm` per tied group from
`Refinement._ties` and `crystallography.magnetic.supercell.anti_translation_ties`,
flags from the free set (Part B); (4) the reader keeping those equation forms
as ties instead of fixed literals. Items 5 (a `.out` read back loses
`mly = -mFe / b;`) and 6 (flags on forbidden components, #714, PR #720) were
not checked here.

**#715, checked at `32ef5a6`.** The family-group refusal (`topas.py:4428`)
said "a magCIF read with nuclear_group='file' does this"; followed, it loops.
Reproduced: `to_cif` → `from_cif(nuclear_group="file")` gives `P n m a`, two
atoms, no diagnostic, and the same refusal. Cause: `Structure.to_cif` writes
`_symmetry_space_group_name_H-M` (`crystallography/cif.py:634`), gemmi
resolves it, and `structure_from_cif` derives the nuclear group through
`magcif.resolve_nuclear_symmetry`, where `nuclear_group` acts, only inside
`if sg is None:` (`cif.py:335`). So on rietx's own magCIF the option is
ignored for all three values, with no diagnostic, and `"parent"` does not
raise, though `Structure.from_cif` says the choice is "reported either way".
With that tag renamed `_parent_space_group.name_H-M_alt` (MAGNDATA's
spelling), `"file"` gives `P 1 21/c 1` with the same two sites (Fe 4 images
where `P n m a` gave 8), and `write_topas_inp` accepts it: a different
crystal. PR #731 (fork, open) rewrites the message to stop naming the loop
and pins it; it adds no route. A second question the loop raises: the
refusal tests group equality while its message claims orbit loss, and on a
tier-1 phase read from a magCIF the orbits are equal by construction
(`magcif._orbit_mismatch`). Whether the test should be orbits is open.

### Licensing

TOPAS and FullProf are closed: black-box measurement and their manuals only,
no code. GSAS-II may be read as specification only (ATTRIBUTION.md's GSAS-II
rows: royalty-free, grant-back, no code ported), which covers its `SpcGroup`
grammar for a rhombohedral-axes spelling and its CIF importer's tag order. A
measured constant is committed as program output for an input of ours, with
a `tests/data/README.md` row.

### Inherited

- **2026-10-24, from [2044](2044-the-sabine-laue-factor-is-continuous.md):
  two facts for C3 and the TOPAS writer.** FullProf's powder extinction is one
  empirical parameter (`Extinc`, the SHELX-style form), with no Laue and Bragg
  split. `Ext-Model` is single-crystal only. So a `.pcr` cannot carry rietx's
  Sabine factor, and C3 decides between refusing a non-zero extinction and
  writing the nearest empirical term with the difference reported
  (`docs/practice.md` § Extinction, checked in the FullProf manual). The TOPAS
  writer's `scale_pks` now spells rietx's e^(−x)·[I₀ + I₁] as Abramowitz &
  Stegun's polynomials, within 3.6e-8, since TOPAS has no Bessel function. It
  has not been run in TOPAS: the TOPAS 6 oracle at extinction 20 still
  matches, but that case keeps x small.
- **2026-10-23, from [1326](1326-satellites-without-a-moment.md)'s close
  (originally WP-1328, 2026-10-03): `Structure.to_cif` writes no k for a
  nuclear phase.** A phase with `Phase.propagation_vector` set carries
  satellites, but the CIF written from it says nothing of k, although magCIF
  has `_parent_propagation_vector.kxkykz`. #567's review left that as a design
  choice, and the writers' refusals point at the JSON instead. C-f writes the
  same tag from `MagneticSymmetry.propagation_vector_parent`, so the nuclear
  phase's k is a second source for one tag, and C-f is where to decide
  whether it writes. The other half of 1328's note stays a standing choice
  and is not forwarded: `fullprof.to_structure` drops a nuclear phase's `Nvk`,
  because FullProf's nuclear k and rietx's are not the same model.
- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: a tied TOPAS write its own reader refuses.** `write_topas_inp(structure, path, free=ref)` with a structure whose values break one of `ref`'s `tie_equal` groups writes one shared name at two values, and rietx's `.inp` reader then refuses the file (`TopasInpError ... is stated at two values`, `io/projects/topas_ties.py:345`; writer `topas_input.py` through `from_structure_refined`). Reproduced by a WP-1986 lane and not re-run by its parent. `src/rietx/io/CLAUDE.md` asks a writer to refuse what its reader refuses. `docs/docs/reference/foreign-writers.md`'s example sidesteps it by passing `ref.fitted_structure`.

- **2026-10-17, from [1996](1996-the-switching-tab-says-only-what-its-tests-show.md):
  FullProf applies the Laue-class cell constraints itself, and it runs on this
  machine.** `~/Code/rietx-bench/tools/fullprof/files/fp2k` (FullProf.2k 8.20,
  February 2025, x86_64 under Rosetta), run as `fp2k <stem>` in a directory
  holding `<stem>.pcr` and an `Ins=0` `<stem>.dat`, with `FULLPROF` set to the
  binary's directory. On fluorapatite written by `write_fullprof_pcr` with
  codewords `41 0 51 0 0 0` it printed `Cell constraints according to Laue
  symmetry: 6/m` and rewrote them `41 41 51 0 0 41`, so a held b in a
  hexagonal file is safe. The manual (Line 11-4) still says CF must equal CA
  and CB, so the program, not its manual, is the reference for #761's restated
  hexagonal cell.
- **2026-10-09, from [1319](1319-structure-interchange.md): #756's C-f is this
  WP's.** The maintainer split issue #756's CIF writer module across three WPs:
  1319 takes the registry, the number rule and the structure block (C-a to C-c),
  [1933](1933-the-cif-module-beyond-the-structure-block.md) takes the pattern
  block, the multi-block layout and the validation hook, and C-f comes here
  because Part D already writes `_parent_space_group.name_H-M_alt`. C-f, as #756
  § 2.3 and the reporter's comment of 2026-10-06 state it: write
  `_parent_space_group.name_H-M_alt`, `_parent_space_group.child_transform_Pp_abc`
  and `_parent_propagation_vector.kxkykz` whenever
  `MagneticSymmetry.propagation_vector_parent` is set; always write the nuclear
  group's `_space_group_symop` loop; keep the nuclear `_space_group_name_H-M_alt`
  beside the magnetic loops; add `cif_mag.dic` to 1319's registry test (1319
  vendors it into `tests/data/`). Acceptance: `test_magcif.py:997`'s assertion that
  the parent k is lost is inverted, and the `write_magcifs` docstring
  (`strategy/magnetic.py:673-676`), which says the parent is kept, becomes true.
  It depends on 1319's C-a and C-c, and on #757's I-b fixing the parent record's
  field names. The structure block it extends drops the deprecated
  `_symmetry_space_group_name_H-M` (1319's decision 3), which the GSAS-II phase
  CIF's profile keeps until 1933's C-g declares it.

- **2026-10-08, from the issue triage (issue #732): a whole TOPAS input, the
  Chebyshev domain, and the GSAS-I `ZERO` unit.** The issue lists the eleven
  edits an agent made by hand to every exported `.inp` in a 20-case benchmark.
  It proposes four steps in order: `write_topas_inp(instrument=, pattern=)`
  writing a file TOPAS runs as it stands; the Chebyshev fit domain stored on
  the background model; `read_topas_inp(...).to_instrument()`; and the GSAS-I
  `ZERO` unit once a GSAS-I run can measure it. This WP owns the writer half,
  because a whole input is Part B's writer carried from the `str` to the file.
  *Checked against the tree at 5d1f5f67*:
  - `write_topas_inp` takes `instrument=` already (PR #770), and on `main`
    it uses it only to pick the scale convention for `scale="topas"`. No
    `pattern=` exists. No data file, `lam`, `LP_Factor`, `th2_offset`,
    `bkg`, peak type, `exclude` or extinction line is written
    (`topas.py:4689-4707`).
  - `BackgroundChebyshev` stores coefficients only. The domain is the
    compiled grid's own `tt.min()`/`tt.max()`
    (`background/models.py:88`), so a coefficient list read alone cannot be
    evaluated on the range it was fitted on.
  - `write_gsas_prm` still refuses a non-zero `zero_shift`
    (`instrument_profile.py:1043`). WP-1118 closed with that unit open, and
    no open WP measures it.
  - `to_structure` builds no `Instrument` (its docstring says so). WP-1455
    (⬜) owns that reader half, for `TCHZ_Peak_Type`; the same issue is noted
    there.

  **PR #815 (fork, open, head f1ef0462) implements step 1** and claims WP-1911.
  It writes `pattern=` as a `<stem>.xye` from the first to the last fitted
  point, `lam`, `neutron_data`, `LP_Factor`, a `th2_offset` equation for
  zero and displacement, `bkg` for a Chebyshev, the P-spline as `fit_obj`
  basis functions with `penalty` rows, `peak_type pv` with rietx's width laws
  as `pv_fwhm`/`pv_lor`, `Finger_et_al`, Sabine extinction as `scale_pks`,
  and interior `exclude` ranges. That covers the issue's items 1-6, 10 and
  11; #770 already covered item 8. Two items stay out: a March-Dollase
  preferred orientation (named, not written) and the hkl-table output (item
  7, not mentioned in the PR). The PR's design differs from the issue in two
  places, and both agree with what the issue wanted. It writes the P-spline
  exactly where the issue proposed refusing it or refitting a Chebyshev, on a
  measurement (refitted, TOPAS reached Rwp 4.30 % against rietx's 4.73 %).
  And it writes no `TCHZ_Peak_Type`, so no letters need swapping. It refuses
  `shape="voigt"`, a Stephens block, absorption, capillary offsets,
  transparency, a λ/n harmonic and extra components by name. Its fixtures are
  TOPAS 6 zero-cycle `Y_calc` for synthetic NaCl inputs (2.2e-3 to 2.6e-3 of
  the peak). Its Ba₂FeSbSe₅ end-to-end run is cited (Maier et al. 2021,
  *Phys. Rev. B* 103, 054115) and no file of it is committed. It lands
  `api.md` at exactly `API_INDEX_MAX_BYTES` (39 700) by shortening a
  docstring, so #808's split decision is in its path.

  What this leaves here: steps 2 and 4 as tasks, with no PR yet. Step 2 is
  smaller after #815, whose `.xye` puts the series on its own range. It
  still matters for a coefficient list written or read without its pattern.
  Step 4 waits for a GSAS-I run, with the precedent of #755's FullProf `Zero`
  (measured as a black box, and its output still uncommitted).

- **2026-10-05, from the issue triage (issues #706, #707, #714, #709): four
  more TOPAS-writer defects, each in an open PR from the reporter's fork.**
  None has a fix on `main`. All four are in this WP's family: the writer's
  only check is rietx's own round trip.
  - #706 (PR #710): a site within `SITE_TOL` of a special position is
    written with its stored digits (`x ! 0.3333 y ! 0.6667` on ZnO's 2b),
    which TOPAS reads as general. *Checked at `32ef5a6`*: those digits
    generate 6 positions at 1e-9 under the group, against rietx's 2.
    TOPAS's own count (12, the reporter's) was not run here.
  - #707 (PR #710): origin choice 1 is written `F d -3 m:1`, which TOPAS 6
    stops on, and rietx reads it back silently. *Checked at `32ef5a6`* on
    Si. The PR writes TOPAS's `S` suffix, measured by the reporter over all
    33 groups with an origin choice.
  - #714 (PR #720): every moment component takes the moment's refine flag,
    so MnF₂ writes `mlx @ 0.0 mly @ 0.0 mlz @ …` where the allowed basis at
    2a is `[[0,0,1]]`, and TOPAS stops. *Checked at `32ef5a6`*. The PR
    flags only components in `MagneticGroup.allowed_moment_basis`. By its
    own "Not covered", a coupled basis row such as (1, 1, 0) still flags all
    three. Part D's ties task owns that.
  - #709 (PR #713): there is no P1 restatement, so a k ≠ 0 child (Pbcm,
    k = (½, 0, 0)) is refused by name. *Checked at `32ef5a6`*. The PR adds
    `restate_phase_in_p1`/`restate_in_p1` and `write_topas_inp(p1_expand=)`,
    and Part D builds on it.

  Whether `p1_expand=` earns the `API_INDEX_MAX_BYTES` raise the PR makes
  is the PR review's question, not this WP's.

- **2026-10-10, from WP-1543: a real file now reaches the GSAS-I `ZERO`
  refusal, and GSAS-II's importer reads that field as centidegrees.**
  `read_gsas_prm(..., profile_set=3)` reads GSAS-II's tutorial
  `tests/data/gsas2_bt1_cu311.inst` as far as `ICONS`, whose `ZERO` is
  0.04, and refuses there. GSAS-II's `GSASIIfiles.SetPowderInstParms`
  divides that field by 100. That is a second reader's convention rather
  than the format's own reference output, so it corroborates and does not
  settle the unit. Settling it makes this file the first real `.prm` to read
  past `ZERO`. WP-1327's LaMnO₃ acceptance still seeds its widths by hand
  for this reason.

- **2026-10-11, from the issue triage (#732, #761): three asks this file
  names have no task line.** The 2026-10-08 #732 entry leaves "steps 2 and 4
  as tasks", but § Tasks has neither: step 2 is the Chebyshev domain stored
  on the background model, step 4 the GSAS-I `ZERO` unit. #761 (2026-10-06,
  no thread answer yet) is named only in the 2026-10-06 handover. It asks
  that `write_fullprof_pcr` and the GSAS-II phase CIF write the restated
  hexagonal `a` and `c` free where the rhombohedral cell was free, with
  coordinates still held. It carries one decision for the maintainer: a
  caller who freed a_r with α_r held moved a_h and c_h at a fixed ratio,
  which neither program can state, and the reporter would keep both held and
  say so. Checked against the tree at 7d9be3cb: `BackgroundChebyshev`
  (`schemas/instrument.py:1068`) still holds only `kind` and `coefficients`,
  the domain being the grid's (`background/models.py:88`), and the GSAS-II phase CIF writes
  no refine flags at all (`io/projects/gsas2.py:1750`, `:1988`), so #761's
  freeing applies to the `.pcr` writer alone and needs the free set to reach
  it (#722's Part B, unlanded for FullProf).
- **2026-10-13, from the issue triage (#723, #761, #732, after PR #912
  merged 2026-10-12).** Three replies and one gap. **#723** (2026-10-12): the
  reporter's answer to the decision's second half is yes: sample
  transparency, both capillary offsets, absorption, surface roughness and
  extra components join Part C after the eight, under the same rule (each a
  FullProf sign-and-unit measurement before it is code, refused by name
  until then), and partial `Occ` is one task with reader and writer halves,
  as C1 says. The decision is still the maintainer's; taken, it adds a C5
  task. **#761** (2026-10-12): yes to both readings of the 2026-10-11 entry.
  Free the restated hexagonal a and c in the `.pcr` writer only, once Part B
  gives it `free=`; the GSAS-II half is a rewording of
  `GSAS2_CIF_RHOMBOHEDRAL_RESTATED`; with a_r free and α_r held, hold a_h
  and c_h and name the fixed c/a in `FULLPROF_RHOMBOHEDRAL_RESTATED`;
  coordinates stay held. It wants a Part B task line. **#732**: PR #912
  carries the whole input to magnetic P1 phases, but besides steps 2 and 4
  (the 2026-10-11 entry), the issue's item 7 (the hkl table) and item 9
  (March-Dollase named but not written) have no TOPAS task line either.
  **#721**: #912 lands item 3 for the P 1 route. Items 2 (a structure-level
  setting transform), 4 (the reader does not read `mlx = …;` back,
  `tests/test_topas_refined.py:345` is a strict xfail, and no test reads the
  P1 equations back) and 5 stay with Part D, whose "ties in the TOPAS writer"
  task is half landed by #912.

## Non-goals

- Magnetic writers for FullProf, GSAS and GSAS-II: none of those programs
  reads the moments back (#470), so the refusal stays.
- Profile-term conversions already mapped (TCHZ, U V W), except as WP-1543
  finds for the GSAS Gaussian width, which is that WP's.
- The TOPAS reader's own silences: WP-1530.
- A `.pcr` anisotropic displacement (the β_ij convention `to_structure`
  declines to assume) and the Bragg-peak shape terms FullProf has and rietx
  does not.
- Changing what `fitted_structure` means (#722 option 3), unless the
  maintainer chooses it.
- Incommensurate and modulated structures (§ v2+).

## Tasks

Part A first: it is the one silent wrong answer, and its refusal half can
land alone before the transform exists.

- [x] **Decision (maintainer):** for a rhombohedral-axes phase, refuse by
      name in the `.pcr` and GSAS-II writers, or write the hexagonal-axes
      equivalent. Recommended: refuse now, restate once the transform lands.
      *Decided 2026-10-06: restate, through PR #733, which brings the
      transform.*
- [ ] A: `.pcr` writer refuses (or restates) an `R … :R` phase; the `:R` arm
      of `test_write_fullprof_pcr_round_trips_both_r_lattice_axis_choices`
      inverted; an oracle test with FullProf's measured rule (a bare R symbol
      is hexagonal axes with α = β = 90°, γ = 120° imposed; a suffix is
      illegal), held first to the reporter's table
- [ ] A: GSAS-II phase CIF: read GSAS-II's `SpcGroup` grammar (spec only) for
      a rhombohedral-axes spelling, measure it by black box, or refuse; fix
      `GSAS2_CIF_SETTING_IN_OPERATORS`' message, which calls an axis choice an
      origin choice
- [ ] A: `.EXP`: measure what GSAS-I reads for `R -3 c:R` and `F d -3 m:2`;
      refuse what it does not, and correct `gsas.py:1852`'s claim
- [ ] A: `.pcr` reader: a bare R symbol beside a = b = c, α = β = γ ≠ 90 is
      refused as a contradiction (root CLAUDE.md's angle rule), or kept with
      a written reason
- [ ] The shared transform: a `Phase` restated by an exact change of basis
      (cell, coordinates, U, moments, operators), refusing a Stephens block or
      restraints; tested by `predict()` agreement, never by a count
- [ ] **Decision (maintainer):** #722's options 1/2/3, and whether the TOPAS
      and `.pcr` readers take the same constants
- [ ] B: the scale constants measured and committed (TOPAS and FullProf,
      neutron and X-ray, an input of ours each), a test holding rietx's
      intensity against each; stated in each writer's docstring and
      `docs/manual/using/files.md`
- [ ] B: `free=` (a `RefinementResult` or paths) and `scale=` on the writers,
      if decided; a narrower flag merges free and is named
- [ ] B (#761): the `.pcr` writer frees the restated hexagonal a and c where
      the rhombohedral cell was free, coordinates held; with a_r free and
      α_r held, a_h and c_h stay held and `FULLPROF_RHOMBOHEDRAL_RESTATED`
      names the fixed c/a; `GSAS2_CIF_RHOMBOHEDRAL_RESTATED` is reworded.
      *Decided 2026-10-13 (the maintainer, through the issue triage),* both
      readings as the reporter agreed them; it waits on the `free=` task above.
- [ ] **Decision (maintainer):** #723 as one package in the reporter's order,
      and whether the unlisted refusals join
- [ ] C1: `Zero`, `SyCos`, `Occ` (reader and writer), each sign and unit
      measured against FullProf first
- [ ] C2: `Cthm`/`Rpolarz` and `Lambda2` + `Ratio`
- [ ] C3: extinction and March–Dollase, FullProf's conventions measured
- [ ] C4: origin choice 1, through the shared transform (restated as choice
      2), or explicit operators if FullProf's operator input is measured
- [ ] C5 (#723): sample transparency, both capillary offsets, absorption,
      surface roughness and extra components, after the eight and under the
      same rule: each a FullProf sign-and-unit measurement before it is code,
      refused by name until then. *Decided 2026-10-13 (the maintainer,
      through the issue triage):* the unlisted refusals join, as the reporter
      answered; the package's order is still the decision task's.
- [ ] **Decision (maintainer):** #721's items 2-4, and their order, after
      PR #713 lands
- [ ] D: `nuclear_group` on rietx's own magCIF: either `to_cif` writes
      `_parent_space_group.name_H-M_alt` for a magnetic phase, or
      `structure_from_cif` says when the option cannot act (`"parent"` raises
      or reports)
- [ ] D: the family-group refusal tests what its message claims (orbits), or
      the message says groups
- [ ] D: a non-standard BNS setting restated at its standard one through the
      transform, so `mag_space_group N` can be written
- [ ] D: ties in the TOPAS writer (`prm` per tied group), and the reader
      keeping the forms the writer emits, if decided
- [ ] `src/rietx/io/CLAUDE.md` § Project writers: the oracle rule, stated as
      a rule (no findings)
- [ ] Tests: per writer and per fact, an oracle reading the written file the
      target's way, held to its measurement table first
- [ ] Skill: `references/api.md`'s "All four formats write back" passage
      (what a written file's flags and scale are), `references/magnetic.md`'s
      "Exporting" row, and a `references/diagnostics-projects.md` row per new
      code; `rietx skill --install . --copy` to sync
- [ ] The 1.7.0 notes for every default a decision changes

## Acceptance

- #716's phase is refused by name by the `.pcr` and GSAS-II writers, or
  written on hexagonal axes, and an oracle test with FullProf's measured rule
  fails on `32ef5a6`'s writer.
- #715's loop does not loop: following any refusal's advice either writes
  the file or reaches a different refusal.
- Each scale constant the WP states is pinned against a committed program
  output, never a quoted number.
- Each lifted `.pcr` refusal round-trips through rietx and through an oracle
  of FullProf's measured reading.

```sh
.venv/bin/python -m pytest tests/test_projects_fullprof.py tests/test_projects_topas.py tests/test_projects_gsas.py tests/test_projects_gsas2.py tests/test_writers_refuse_magnetic.py tests/test_magcif.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_skill.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #715, #716, #721, #722, #723 (mustachefeeling, 2026-10-05); PRs
  #731 (#715's message), #713 (#709's P1 restatement), #720 (#714's moment
  flags), #710 (#706/#707, TOPAS origin choice 1 and special positions), all
  open from the fork on 2026-10-05.
- [1527](1527-foreign-files-spell-a-species-as-the-program-does.md): the
  oracle pattern. [1543](1543-a-gsas-gaussian-width-is-a-variance.md): the
  same contract for one GSAS width constant. [1118](1118-foreign-model-files.md)
  and [1328](1328-magnetic-interchange.md): the writers and the magnetic
  writer this extends.
- *International Tables for Crystallography* Vol. A (2005), Table 5.1.3.1: the
  hexagonal ↔ rhombohedral (obverse) transformation.
- Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55-69, and the FullProf
  manual: the `.pcr` fields named here. TOPAS Technical Reference: the `str`
  keywords (specification only, per ATTRIBUTION.md).

## Handover log

- **2026-10-12** — a P 1 file now refines as the model does. PR #912 (head
  `2c31b2c5`) merged as `a8960f79` after two rounds. It is #721's proposed
  item 3 for the P 1 route, entry 4 of #732, and the showcase rows M1, M2, M5
  and M10.
  *Done.* `write_topas_inp(p1_expand=True)` beside `free=`, `scale=`,
  `instrument=` or `pattern=` writes every copy of a site as an equation over
  the parameter it copies. That lifts #815's refusal of the combination.
  `p1_expand="auto"` restates only a phase whose magnetic group TOPAS cannot
  name (a k ≠ 0 supercell, an untabulated family group, a non-standard
  setting), and reports `TOPAS_PHASE_RESTATED_IN_P1`. A bare `"auto"` with no
  such phase writes the plain form. `p1_expand` accepts only `False`, `True`
  and `"auto"`. A whole input with `instrument=` writes a magnetic-only width
  as two `str`, the nuclear part and a `mag_only` magnetic part. That lifts
  #815's other refusal.
  *Gotchas.* The two-`str` split is refused when extinction is non-zero or
  free. rietx applies one Sabine factor, from the summed |F|², to both
  components, and TOPAS computes `scale_pks` from one `str`'s own A01..B11.
  `_GroupIdentityRefusal` separates the refusals P 1 answers from the two it
  does not: a magnetic group with no site moment, and a phase's own
  propagation vector. The P 1 expansion now exists twice, in `topas_input.py`
  (`_image_maps`, `_aniso_image_matrix`) and in
  `crystallography/magnetic/p1.py`. Labels were the first drift between them,
  fixed by `_p1_labels` copying `_unique`'s rule. One shared expansion is a
  follow-up on the PR. This entry also corrects the PR's 1.9.0 note, which
  compared against 1.7.0 where 1.8.0 is the base.
  *Gate:* stacked with #903 on `main` `a7e71bf7` as `d41a7932`, macOS arm64,
  `[dev,jax]`, nothing else running: fast 9357 passed, 113 skipped, 2 xfailed;
  `-m slow` 306 passed, 14 skipped. `main` after both merges (`a8960f79`) is
  content-identical to that tree.
  *Next:* the maintainer decision on the rest of #721: item 2's setting
  transform, and item 4 against what #771 landed.

- **2026-10-08 (2nd session)** — the whole TOPAS input now writes an X-ray
  extinction. PR #839 (head `fb34a211`) merged as `3b9aad52`.
  *Done.* The refusal #815 shipped is gone, because a TOPAS 6 run measured the unit
  it was waiting for. On `case_nacl_xray` at extinction 20, TOPAS's
  `A01^2 + B01^2 + A11^2 + B11^2` is rietx's |F|² in electrons² (1.0008 per
  reflection on average), so the X-ray `scale_pks` term carries factor 1. The
  neutron term keeps its 100. `tests/data/topas_export_nacl_xray_ext20_ycalc.txt`
  is the new oracle (README row checked: size, sha256, CRLF). Re-measured here on
  the merged tree, `predict()` misses it by 2.6e-3 of rietx's peak, against 0.243
  at extinction 0 and 3.75 with the neutron factor. The PR also moves every TOPAS
  citation to the printed v6 Technical Reference by section and page (§ 9 for the
  magnetic keywords, which earlier text called § 13). Nothing now cites a macro body,
  and `ATTRIBUTION.md` names the web page only for what v6 lacks.
  *Gotchas.* The term uses the first emission line's λ for every line, while
  rietx's forward model passes each line its own. Kα₂'s x is 0.5 % larger, inside
  the 2.6e-3 match, and the docstring says so. Part B's "state what the other
  program reads" may want it recorded rather than only documented. The
  `_extinction_items` docstring's "misses by 0.79" is the same factor-100 miss over
  TOPAS's peak, where the test's 3.7 is over rietx's. Both were raised as
  follow-ups on the PR.
  *Gate:* stacked with #841 on `main` `63af9e1b` as `5c82b0c2`, macOS arm64,
  `[dev,jax]`: fast 8944 passed, 109 skipped, 1 xfailed, 1 failed (the
  `test_indexing_reduce` reduction-map row, failing on `main` alone); `-m slow`
  290 passed, 14 skipped.

- **2026-10-08** — `write_topas_inp` can now write a whole input TOPAS runs as it
  stands, from #732's `### Inherited` item. PR #815 (head `49225d22`) merged as
  `4f64a0e6` after two rounds.
  *Done.* `instrument=` and `pattern=` write the data beside the file as
  `<stem>.xye`, the wavelength, `neutron_data`, `LP_Factor`, zero and
  displacement, the background (a P-spline as `fit_obj` pieces), the TCHZ widths
  as `pv_fwhm`/`pv_lor`, FCJ as `Finger_et_al` and Sabine extinction as
  `scale_pks`. Three TOPAS 6 Y_calc files back it. Round 1 asked for five things,
  all done: journals on the physics, an X-ray extinction refused by name (its unit
  is unmeasured; the ×100 is the neutron conversion measured on
  `case_nacl_neutron`), the `TOPAS_FIELD_NOT_WRITTEN` row split into its two
  cases, `Dispersion()` declared on `case_nacl_xray` (on 2.4e-3 against off
  4.4e-2), and a refused `xdd` name holding a quote or line break.
  *Gate:* stacked with the run's other merges (#829, #825, #809, #754, #749, #815)
  on `main` `a3f9140a` as `166d362e`, macOS 26.6.2 arm64, `[dev,jax]`. The full
  suite, fast and slow together, gave 9231 passed, 116 skipped, 1 xfailed and 2
  failed. Both failures also fail on `main` alone on that machine: `toy_anomalous`
  (#760, which open PR #828 fixes) and a hypothesis counterexample in
  `test_indexing_reduce.py`. `main` after the merges is content-identical to that
  tree.
  *Gotchas.* `api.md` sat at its cap on `main`, so the PR cut `write_topas_inp`'s
  summary line to "Write.". The next PR adding a verb meets the same cap. #732's
  reader half is WP-1455's.
  *Next:* #721's decision, as before.

- **2026-10-07 (2nd session)** — Two more of this WP's PRs merged from the
  reporter's fork. They were gated together on a four-PR stack replayed onto
  `main` at `57aa2c1` (stack `5af37056`, Linux, 4 cores, `[dev,jax]`):
  - ruff is clean;
  - the fast suite gave 8795 passed, 118 skipped and 1 xfailed;
  - the slow tier, run in two halves, gave 287 passed, 9 skipped and 1 failed.
    `test_pair_diagnostic_class.py::test_every_pair_on_a_solution_names_a_class_whose_rows_carry_it`
    fails identically on bare `main`.

  After the last merge, `main` at `9a3955b` is content-identical to the gated
  tree.
  - PR #770 (#722) as `9a3955b`. `write_topas_inp(free=, scale=, instrument=)`
    writes the fit's free set and ties:
    - a free parameter goes under a name derived from its path;
    - a `tie_equal` group is one shared name;
    - any other affine tie is an equation over its source, with `prm` where no
      written value carries the source;
    - finite bounds are written as `min`/`max`.

    `free=` takes a `Refinement` (ties included), a `RefinementResult` or a
    list of paths. For a result, the symmetry ties are rederived from the
    structure's own table and written from their source, and a user tie's
    copy is written as its own parameter. `scale="topas"` writes × 100 for
    neutrons, held by `topas_export_nacl_neutron_ycalc.txt`. It writes × K
    for X-rays, which is the Technical Reference's definition with no TOPAS
    output in the tree yet. Without the new keywords the file is byte for byte
    what 1.6.0 wrote. Without `free=`, the stored flags are written.
  - This is Part B's writer half for TOPAS only. The B tasks stay unticked:
    the `.pcr`, `.EXP` and GSAS-II writers take neither keyword, and the
    FullProf constants and the X-ray TOPAS constant are not committed.
    `test_a_free_moment_is_read_back` is a strict xfail with
    `raises=TopasInpError`. It still xfails with #771 on `main`, because
    #771's reader does not read `mlx = …;`. The marker flips when that read
    lands.
  - Gotcha, checked in review: a result's coordinate DOFs are steps from the
    fit's start. Written beside a fitted structure, they still read back to
    the fitted coordinates exactly, under both `free=ref` and
    `free=ref.result_`. That was probed on a displaced Pnma, so there is no
    double count.
  - PR #755 (#723 item 1) as `0ce4b9a`. `write_fullprof_pcr(...,
    write_zero_shift=True)` writes `instrument.zero_shift` as `Zero`, with
    its codeword held. The default still refuses a non-zero zero shift, and
    the default file is pinned byte for byte. The convention (degrees 2θ,
    rietx's sign) was measured by the contributor against FullProf 8.20 as a
    black box. That run's output is not committed, so the tree holds the sign
    only in prose. C1 stays unticked: `SyCos` and `Occ` remain.
  - Next: the maintainer decision on #721's items 2-4. #723's package
    decision is still open, beyond its first item.

- **2026-10-07** — Two more of this WP's PRs merged from the reporter's fork.
  Gated together on a nine-PR stack replayed onto `main` at `f99fab05` (stack
  `16a95cef`, macOS arm64, `[dev,jax]`). The whole suite gave 8912 passed, 113
  skipped and 2 failed. Both failures fail identically on bare `main`: the
  `toy_anomalous` golden (#760) and
  `test_the_reduction_map_takes_a_to_f_where_the_reduction_does`. After the
  last merge, `main` at `a65dca1a` is content-identical to the gated tree.
  - PR #771 (#721 item 4, #722's reader half) as `712367bb`.
    `to_structure(constraints=TopasConstraints())` reads a TOPAS file's shared
    names and affine equations back as ties, and `apply_ties` declares them. A
    held path lands in `constraints.skipped` instead of aborting the call. A
    name stated at two values is refused, moment components included, to 1e-6
    of the larger value with no absolute floor, since a TOPAS scale sits near
    1e-6. `to_structure(scale="rietx")` converts TOPAS's scale. A `"<name>
    magnetic part"` `str` merges back into its phase where it equals the
    nuclear `str`, and `read_topas_inp` no longer lists that `mag_only` as
    refused. This is the reader half of Part D's ties task and Part B's scale;
    the writer half is #770.
  - PR #782 (#781) as `a075740e`. `write_topas_inp`'s `str` states the size
    and strain widths and the Stephens block as `lor_fwhm`/`gauss_fwhm`
    equations. TOPAS's `Y_calc` agrees with rietx to 2e-3 of the peak, against
    3e-2 for the isotropic block. `TOPAS_FIELD_NOT_WRITTEN` names the
    magnetic-only widths, extinction and preferred orientation, each by its
    parameter-table path. The size widths are written in degrees, so they hold
    only at the file's one wavelength.
  - Still open from the same fork. #770 (Part B, `free=` and `scale=`) answers
    round 2, including the symmetry-tied rows, and conflicts with #771 and
    #782; a rebase is requested. Its X-ray `× K` constant and the moment
    equations' radians are not yet checked against a TOPAS run. #755 (C1's
    zero shift) is a draft.
  - Next: the maintainer decision on #721's items 2-4.

- **2026-10-06 (2nd session)** — Three more of this WP's inherited
  fixes merged from the reporter's fork. Gated together on a seven-PR stack replayed onto `main` at `7c8a0316` (stack `ee39adb9`, macOS arm64, `[dev,jax]`). The fast suite gave 8523 passed, 103 skipped and 2 failed. Both failures fail identically on bare `main`: the `toy_anomalous` golden (#760) and a hypothesis case in `test_indexing_reduce.py`. The whole slow tier gave 291 passed and 12 skipped. After the last merge, `main` at `0cbb1b70` is content-identical to the gated tree.
  - PR #710 (#706, #707) as `e99cc10b`. `write_topas_inp` writes origin
    choice 1 as TOPAS's `S` suffix (`Fd-3mS`). It writes a site within 1e-4
    of a special position on that position, so TOPAS generates the atoms
    rietx computes with. The stored coordinate is unchanged.
  - PR #733 (#716) as `0063397d`. `write_fullprof_pcr` and
    `write_gsas2_phase_cif` restate an `R … :R` phase in hexagonal axes,
    through `crystallography.symmetry.restate_in_hexagonal_axes`, which cites
    ITA Vol. A Part 5. The scale is divided by 9, and
    `FULLPROF_RHOMBOHEDRAL_RESTATED` and `GSAS2_CIF_RHOMBOHEDRAL_RESTATED`
    report the restatement. This is Part A's writer half for those two
    formats. The transform covers rhombohedral to hexagonal only, so the
    general shared-transform task stays open. The A tasks stay unticked
    until each is checked against its wording; the `.EXP` and `.pcr`-reader
    tasks are untouched. #761 is the follow-up: write the hexagonal cell
    free while the coordinates stay held.
  - PR #713 (#709) as `f75f6b89`. `restate_phase_in_p1` and
    `write_topas_inp(p1_expand=True)` write a phase as its cell's atom list
    in `P 1`, with every flag held. That unblocks the maintainer decision on
    #721's items 2-4, which waited for this PR. One gotcha: the expansion
    uses the unsnapped coordinates. On 83 MAGNDATA entries that lights
    absent rows at ≤ 4.5e-4 of the pattern maximum (the contributor's
    measurement). #710's snap does not reach the P1 path, since nothing is
    special in `P 1`.
  - Still open from the same fork. #770 (Part B, `free=` and `scale=`) is
    reviewed at round 2. Its blocker is that a result's symmetry-tied rows
    are written as free parameters, so a cubic `b` and `c` refine
    independently in TOPAS. It also needs a rebase over #713. #771 (Part D,
    the TOPAS reader's ties and the magnetic-part merge) is reviewed at
    round 2 with four items and needs a rebase over #710. #755 (C1's zero
    shift) is a draft.
  - Next: the maintainer decision on #721's items 2-4.

- **2026-10-06** — Two of this WP's inherited TOPAS-writer fixes merged
  from the reporter's fork, gated together on a six-PR stack (macOS arm64,
  `[dev,jax]`, full suite 8724 passed, 110 skipped, 1 failed on a golden
  that fails on bare `main` on that machine too).
  - PR #720 (#714) as `68792ad1`. A moment component outside
    `allowed_moment_basis` at the site is written `!`, so TOPAS no longer
    stops on a component with no derivative. The basis is asked at the
    stored coordinates with `SITE_TOL`, the tolerance #710's snap uses, so
    the two agree once #710 lands. A coupled basis row such as (1, 1, 0)
    still flags all three components. Part D's ties task owns that.
  - PR #731 (#715) as `7ad82745`. The family-group refusal no longer names
    `nuclear_group='file'` as its remedy, which looped. Part D's
    `nuclear_group` task is untouched by it.
  - Still open from the same fork: #710 (#706, #707), reviewed clean and
    waiting on a rebase over #720; #713 (#709), held on the
    `API_INDEX_MAX_BYTES` raise; #733 (#716), reviewed with one citation to
    add. #733 *restates* a rhombohedral-axes phase, so it takes the
    Part A decision below in the direction this WP did not recommend. The
    maintainer accepted restating the same day, because #733 brings the
    transform the recommendation was waiting for (comment on #733).

- **2026-10-05** — created, from the 2026-10-05 issue triage (issues #715,
  #716, #721, #722, #723). Checked against the tree at 32ef5a6: #715's loop
  reproduced, caused by `nuclear_group` being a no-op on rietx's own magCIF
  (`cif.py:335`); #716's `.pcr` and GSAS-II files written as the reporter
  says, round trip passing; #722's flags reproduced on synthetic LaB₆ (14
  free, one `@`), constants not measurable here; #723's eight refusals
  present, plus five more; #721's refusals as listed and no structure-level
  transform. No open WP owns it: 1118, 1328 and 1527 are closed; 1530 is the
  TOPAS reader's silences; 1543 is one GSAS width constant; 1319 (checkCIF,
  an XYZ reader, and since today #711/#712's CIF-reader repairs) fences out
  "model exporters to other Rietveld codes"; 1455 is a TOPAS profile reader;
  1327's non-goals send interchange to 1328. One WP rather than five because the five share a cause
  (the round trip is the writers' only acceptance) and a primitive (the
  setting transform serves #716, #721 and #723). Next: the maintainer's
  Part A decision, then Part A's refusal as its own PR.

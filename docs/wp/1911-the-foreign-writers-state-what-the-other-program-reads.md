# WP-1911 — the foreign writers state what the other program reads: the setting, the scale, the free set

Milestone: unscheduled · Status: 🔄 2026-10-06 — PRs #720, #731, #710, #733 and #713 merged from outside; #721's decision is due, now that #713 has landed
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
- [ ] **Decision (maintainer):** #723 as one package in the reporter's order,
      and whether the unlisted refusals join
- [ ] C1: `Zero`, `SyCos`, `Occ` (reader and writer), each sign and unit
      measured against FullProf first
- [ ] C2: `Cthm`/`Rpolarz` and `Lambda2` + `Ratio`
- [ ] C3: extinction and March–Dollase, FullProf's conventions measured
- [ ] C4: origin choice 1, through the shared transform (restated as choice
      2), or explicit operators if FullProf's operator input is measured
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
  - Maintainer decision on draft PR #755 (C1's `Zero`):
    `write_fullprof_pcr(..., write_zero_shift=True)` is wanted as an option,
    and the default still refuses a non-zero zero shift. The contributor
    measured the sign and unit against FullProf 8.20 as a black box: `Zero`
    is degrees 2θ with rietx's sign. Whether #723 is taken as one package in
    the reporter's order is not decided, so that task stays open.
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

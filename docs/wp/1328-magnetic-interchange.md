# WP-1328 — magnetic interchange: magCIF in and out, and the readers stop refusing

Milestone: v1.6 · Status: 🔄 2026-09-27 — magCIF in and out and the TOPAS moments landed from outside (PR #478); the `.pcr` Jbt stance and 1314's refusal list remain
Depends on: 1327 (the model the files describe); 1118 soft (the coverage
registry the foreign readers report through)
Priority: P3 2026-09-23 — waits on 1327's model; P2 when it lands

## Goal

A magnetic structure enters the package from a magCIF (the operator list,
the moments, the propagation vector) and leaves as one from a refined
result, and the three foreign-file refusals that exist because "rietx has no
magnetic model" are lifted to *read* where the construct maps onto 1327's
model and stay *refused by name* where it does not.

## Context

Third rung of the magnetic scattering track (ROADMAP § Unscheduled). The
readers are where the package meets a user's existing work, and every one of
them currently refuses a magnetic phase with the same sentence: importing the
nuclear half alone "would look complete" (`io/projects/coverage.py`, the
`magnetic structure` feature at `Stance.REFUSED` over `mag_space_group`,
`mag_only`, `mag_only_for_mag_sites`, `mlx`, `mly`, `mlz`, `mg`,
`mag_atom_out`; the TOPAS reader's raise at ≈ line 1915; WP-1314's refusal
list for Jana `.m50`). Those sentences were right, and 1327 makes them wrong.

**magCIF is the interchange format, and it carries what 1327 stores.** The
COMCIFS `magnetic_dic` (`cif_mag.dic`, tags checked 2026-09-02) defines
`_space_group_symop_magn_operation.xyz` and
`_space_group_symop_magn_centering.xyz` (operators with the time-reversal
sign), `_atom_site_moment.crystalaxis_x/y/z` and their `_su`, the spherical
form `_atom_site_moment.spherical_modulus/polar/azimuthal`,
`_parent_propagation_vector.kxkykz`, and `_space_group_magn.name_BNS` /
`name_OG` / `transform_BNS_Pp_abc` for the symbol and the parent-to-magnetic
cell transform. MAGNDATA and ISODISTORT emit this form, so a reader that
takes it takes every published commensurate structure. `io/cif.py`'s
`structure_from_cif` is the reader to extend; it already carries the
diagnostics channel a repair must report through (species normalised, a cell
angle corrected), and a magnetic block reaches the same channel.

**Writing it is the exporter's job** (`io/exporters.py`,
`write_refinement_cif`): the refined moments with esds, the operator list
that was refined under, and the symbol carried through as metadata. WP-1319
guards the CIF writer with checkCIF, which has no magCIF arm; the guard here
is the dictionary itself, tags checked against `cif_mag.dic` the way the core
tags are checked against the core dictionary. Fetch both the way the standing
memory says (COMCIFS via `gh api`).

**The foreign readers, by construct.** TOPAS states a magnetic structure on
the same `str` as the nuclear one (`mag_space_group`, `mlx mly mlz` on the
site), which is 1327's shape: the site moments map, the symbol is metadata,
and the operators come from TOPAS's own `mag_space_group` number only if the
file also lists them; otherwise the phase is *reported*, not read, and the
message says which tag would have made it readable. `mag_only` is a phase
contributing no nuclear intensity, a shape 1327 does not have, and stays
refused by name. FullProf `.pcr` magnetic phases (Jbt = ±1, Fourier
components per k, a separate phase) map only when k is commensurate and the
phase is described in its magnetic cell; the Fourier-component form is
refused with the sentence naming the incommensurate fence. Jana `.m50`
magnetic phases: the refusal list in 1314 shortens by one entry once this
lands, and 1314's own file is where that edit goes.

**The rule the readers follow** is 1118's: report or refuse, never drop. A
nuclear-only structure that looks complete is the failure every one of these
refusals exists to prevent, so a magnetic construct the reader cannot carry
is still named in the result.

### Inherited

- **2026-09-25, from the issue triage (issue #457, with #286's comments of
  2026-09-24): which group a magCIF's nuclear positions refine under.** A
  magCIF states the magnetic group only. The nuclear symmetry (positions,
  occupancies, ADPs) is a choice between the parent named by
  `_parent_space_group.name_H-M_alt` and the file's own family group (its
  operators with time reversal dropped), which is a subgroup of the parent.
  The fork's `magnetic-v16` took the family group always, handing 463 of
  1171 MAGNDATA entries an operation list: never wrong, and
  under-constrained wherever the parent also fits. The fork's
  `pr/wp1328-magnetic-interchange` (ready, not opened) takes the **highest
  tabulated group the file's atoms satisfy**, in three tiers: (1) the parent,
  when every file operator is one of its operations *and* every listed site
  has the same multiplicity under both (without the orbit test, 241 of 1012
  entries listed one parent orbit as two sites and would have been counted
  twice in |F_N|²); (2) the file's own group when one tabulated setting has
  exactly its operations (reported by `CIF_MAGNETIC_NUCLEAR_SETTING`, info);
  (3) the operation list, a refusal by name until PR #448 lands. Counts on
  the 1012 entries the branch reads: 811 / 201 / 171. Tier 1 is
  bit-identical to reading the parent symbol alone, which is how
  `tests/test_acceptance_magnetic.py` states Cr₂WO₆ (the nuclear phase in
  `P 42/m n m`, line 94). **Checked at `07952d4e`:** no magCIF reader exists on `main`
  (no `_parent_space_group`, no `CIF_MAGNETIC_NUCLEAR_*` code), so none of
  this can be reproduced here; it is a claim about the branch. **The asks:**
  tier 1 must not be silent, so an `info` diagnostic on every magCIF read
  names the tier, the group taken, the file's family group and the index
  between them; an override,
  `structure_from_cif(..., nuclear_group="auto" | "parent" | "file")`; the
  skill row in `references/magnetic.md`. The moments always refine under
  the file's magnetic group, and k ≠ 0 supercells go through
  `magnetic_supercell`, not this rule. **The reporter asked for a decision
  before the PR opens:** the tiered rule, or the file's own group always
  winning over the parent. **Decided 2026-09-25: the tiered rule, parent
  first, with the `info` diagnostic and the `nuclear_group` override.** The
  maintainer asked for established practice, and it agrees. FullProf's
  standard route keeps the nuclear phase in its own space group ("The symbol
  of the space group that we need to provide in the magnetic phase is not
  used for generating atoms", Rodríguez-Carvajal's magnetic-structure
  tutorial, checked verbatim), with a single MSG phase through
  `mCIF_to_PCR` as the alternative. The TOPAS LaMnO₃ tutorial keeps Pnma for
  the nuclear part. Cui, Huang & Toby (2006, *Powder Diffr.* 21, 71) is
  reported to constrain "the nuclear structure to higher symmetry than the
  magnetic structure" (not checked: the publisher blocked the PDF).
  `nuclear_group="file"` is that alternative route. Condition (b) stays a
  hard test.
- **2026-09-16, from [1118](1118-foreign-model-files.md): "out" now has a
  rulebook, and this WP's magCIF writer inherits it.** `io/CLAUDE.md` gained a
  § Project writers when the GSAS-I pair landed, four rules covering every
  later writer in this family. Two bear on a magCIF: refuse on the way out
  whatever the reader refuses on the way in, and where the reader refuses *for
  want of evidence* let magnitude decide drop against refuse — which is the
  shape a magnetic writer meets immediately, since this build refuses a
  magnetic phase for want of a model rather than for want of a spelling. The
  acceptance is the round trip through the matching reader, with no committed
  fixture.
- **2026-09-16, from [1118](1118-foreign-model-files.md): a fourth magnetic
  refusal, a second *shape* of one, and a real magnetic project now in
  `tests/data`.** The GSAS-II `.gpx` reader refuses a phase GSAS-II types
  `magnetic` with the same sentence the other three use, so the table this WP
  changes has one more row than it did yesterday. The new shape is the one to
  design for: GSAS-II also writes the nuclear and magnetic halves as **separate
  phases**, and a nuclear phase carrying `General['magPhases']` imports
  correctly while the file's own Rwp includes scattering this build cannot
  compute. That is reported (`GSAS2_GPX_PHASE_MAGNETIC`, the second of its two
  shapes) rather than refused, because the structure really is right. Also
  practical: `tests/data/gsas2_lacamno3_magnetic.gpx` is a real magnetic
  refinement, vendored under a redistribution grant, whose magnetic phase
  carries moments in its atom records and whose `AtomPtrs` are `[3, 1, 10, 12]`
  rather than `[3, 1, 7, 9]` — the columns move because the moments sit between
  the occupancy and the site symmetry. It is the fixture to test a magnetic
  model against without asking anyone for data.

- **2026-09-15, from [1118](1118-foreign-model-files.md): there is now a third
  magnetic refusal to lift, in the same shape as the other two.** The GSAS
  `.EXP` reader reads a magnetic phase (GSAS phase types 2 and 3, from the
  `EXPR NPHAS` record) onto `GsasPhase.magnetic` and refuses it in
  `to_structure` with the same sentence the `.inp` and `.pcr` readers use — the
  nuclear half would look complete. Its diagnostic row is
  `GSAS_EXP_PHASE_MAGNETIC` in `references/diagnostics-projects.md` §7g. So this
  WP's "one table" now has three entries rather than two, and none of them needs
  new machinery.

- **2026-09-13, from [1118](1118-foreign-model-files.md): the readers are now
  behind a registry, so lifting the magnetic refusals touches one more
  declared place.** `PROJECT_FORMATS` (`io/projects/registry.py`) carries a
  `carries` field per format — what the file holds beyond a structure, in
  words, published through `capabilities().project_formats` and read by a
  client deciding what to ask for. The FullProf row does not mention magnetic
  phases today, correctly, because `to_structure` refuses them. When 1327's
  model lands and that refusal lifts, that row is part of the change and
  `tests/test_projects_registry.py` asserts the arm member for member.
  Nothing else moved: `coverage.py`'s `magnetic structure` stance is still
  `Stance.REFUSED` and there is still no moment on `main` (verified
  2026-09-13), so this WP's premise holds unchanged.

- **2026-09-15, from the issue triage (issue #257, PR #290): two of this
  WP's premises moved.** `MagneticGroup.transformed` (PR #290,
  `crystallography/magnetic/operators.py`) already carries a group between
  settings via magCIF's `transform_BNS_Pp_abc`, lattice completion
  included, so the reader *applies* that transform, and the refusal by name
  is reserved for a string it cannot parse. And the writer can emit
  `_space_group_magn.name_BNS` from `identify()` on the refined operator
  list instead of echoing input metadata, which is #257's ask for this WP.
  MAGNDATA entries carrying the transform are the round-trip fixtures; ten
  of PR #290's twenty published structures are evaluated in a setting the
  BNS standard reaches only through it.

- **2026-09-17, from [1436](1436-k-is-the-wavevector-everywhere-else.md):
  `k` is free for the propagation vector.** The earlier note here warned that
  `scattering.py`, `structure_factor.py` and `dispersion.py` all spent `k` on
  sinθ/λ, in the same subpackage `crystallography/magnetic/` lives in, and
  asked this WP to spell the propagation vector out rather than add a second
  bare `k`. 1436 has landed: that quantity is `stol` in python and `s` in
  equations throughout, following Waasmaier & Kirfel and the IUCr core
  dictionary, and a tree-wide sweep found no line left pairing a bare `k` with
  sinθ/λ in `src/`, `tests/`, `examples/` or the manual. **So name the
  propagation vector `k` and add no qualifier.** Root CLAUDE.md § Conventions
  carries the rule that keeps it free. The same note is in 1326, 1327, 1329 and 1418.

## Non-goals

- The model itself, its physics, its DOFs: 1327.
- The `.pcr` and `.m50` readers as such: 1118 and 1314 own them; this WP
  owns the magnetic rows in their coverage tables.
- checkCIF conformance for the nuclear CIF: 1319.
- Incommensurate structures in any format.

## Tasks

- [x] magCIF reader in `structure_from_cif`: operators with ε, centrings,
      crystal-axis moments (spherical accepted and converted), the parent
      propagation vector, the BNS/OG symbol as metadata; a file describing
      modulation refused by name. (The parent k is read only to refuse a
      k ≠ 0 file; handover 2026-09-27.)
- [x] magCIF writer in `write_refinement_cif`: moments with esds, operators,
      symbol; tags checked against `cif_mag.dic`; a round trip through the
      reader is bit-identical on every stored field. (The tags are a
      hand-copied list; no test reads the dictionary file.)
- [x] `coverage.py`: the `magnetic structure` feature split by keyword into
      *read* (`mag_space_group`, `mlx`, `mly`, `mlz`, `mag_atom_out`) and
      *refused* (`mag_only`, `mag_only_for_mag_sites`), each with its
      sentence; the TOPAS reader's raise becomes the registry's stance.
      (`mag_atom_out` is *ignored*, not read; handover 2026-09-27.)
- [ ] The `.pcr` magnetic rows: Jbt = ±1 in the magnetic cell read,
      Fourier-component form refused by name; a fixture per stance.
- [ ] Manual Part 1 (`using/data.md` and the interchange chapter), skill
      routing row for "you were handed a magnetic structure", and 1314's
      refusal list amended.
- [x] Tests: round trips, the coverage stances, perturbation fuzz in
      `test_readers_robust.py`'s arm.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magcif.py tests/test_projects_topas.py -q
.venv/bin/python -m ruff check src tests examples
```

- A MAGNDATA entry for Cr₂WO₆ or LaMnO₃ (licence checked per file) reads
  into the structure 1327's acceptance refines, and the refined result
  writes back to a file the reader reads to bit-identical stored fields.
- A TOPAS `.inp` with `mag_space_group` and site moments reads with the
  moments in place; one with `mag_only` is refused by name.
- No reader drops a magnetic construct silently: every fixture with one
  either carries it or names it.

## References

- COMCIFS `magnetic_dic` — github.com/COMCIFS/magnetic_dic, `cif_mag.dic`.
- Gallego, S. V. et al. (2016). *J. Appl. Cryst.* **49**, 1750 — MAGNDATA.
  **Not in the corpus; ask.**
- [1327](1327-magnetic-structure.md) the model; [1118](1118-foreign-model-files.md)
  the coverage registry and the report-or-refuse rule;
  [1314](1314-mfile-reader.md) the Jana refusal list;
  [1319](1319-structure-interchange.md) the CIF writer's guard.

## Handover log

### 2026-09-27 — magCIF in and out landed from outside

A magnetic structure can now enter the package from a magCIF and leave as
one. The TOPAS reader reads site moments and a `mag_space_group` number where
it used to refuse them. The FullProf, GSAS and GSAS-II refusals now give their
true reason. It arrived as the contributor's PR #478, second in the v1.6 order
on #286, implementing the nuclear-group rule decided on #457. It was reviewed
over three rounds: a finding list, a rebase onto #477, and a rebase onto #468
with a `SKILL.md` byte cut. Four of the six task lines tick, each with its
deviation noted on the line. The `.pcr` line and the manual-and-skill line
remain.

- *Done*: PR #478, merged as `612453fa`. It closed #457.
  - **The magCIF reader** (`crystallography/magcif.py`, reached through
    `Structure.from_cif`) reads the operator and centring loops with their
    time-reversal signs onto `Phase.magnetic_symmetry`. It reads moments in
    crystal-axis, spherical or Cartesian form and cross-checks the forms
    against each other and against `_atom_site_moment.magnitude`. A modulated
    file and a k ≠ 0 file are refused by name.
  - **The nuclear group** follows #457's three tiers. Tier 1 is the parent
    where the parent holds the file's operators and every site's orbit.
    Tier 2 is the file's own group in a tabulated setting. Tier 3 is the
    file's own operation list, carried on #448's `Phase.symmetry_operations`.
    Each tier says what it did through `CIF_MAGNETIC_NUCLEAR_GROUP` or
    `CIF_MAGNETIC_NUCLEAR_SETTING`. `nuclear_group="auto" | "parent" | "file"`
    overrides it.
  - **The tag vocabulary is data**: `magcif.READ_TAGS`, `IGNORED_TAGS` (each
    with its reason), `WRITTEN_TAGS`, `REFUSED_TAGS` and `PRIVATE_TAGS`. The
    ion and g go under the private `_rietx_atom_site_moment.` category,
    because `cif_mag.dic` has no item for either.
  - **The writer** (`Structure.to_cif`, `write_refinement_cif`) writes the
    loops verbatim and the moments as exact doubles with their `_su` items. It
    computes the magnitude on the cell as the block prints it. A phase with no
    `magnetic_symmetry` is written byte for byte as before.
  - **The TOPAS moment basis is measured.** `mlx mly mlz` are
    fractional-basis components, so the stored crystal-axis moment is
    (mlx·|a|, mly·|b|, mlz·|c|). The contributor ran TOPAS-64 v6 as a black
    box on an oblique cell. Its magnetic intensity ratios match that reading
    on 54 of 54 equal-d pairs, and the other two readings miss by ×1.58 and
    ×1.80. TOPAS's per-reflection table is vendored as
    `tests/data/topas_moment_basis_A_mono3_mag_hkl.txt`, and a test re-runs
    the pair check against it.
  - **A `mag_space_group`-only `str` is a phase.** Its nuclear group is the
    magnetic group's operators with time reversal dropped, taken at tier 2
    or 3.
  - `capabilities().features["magnetic_interchange"]`; manual Part 1 in
    `files.md`, `exports.md` and `data.md`; the skill's interchange rows in
    `references/magnetic.md` and the §7j routing row. The row carries #468's
    satellites clause too. The bytes came from the body's "## The API"
    paragraph, which repeated `references/api.md`'s opening.
- *MAGNDATA round trip* (the contributor's local mirror, aggregate only,
  nothing in the tree): 1086 of 2447 files read (811 tier 1, 201 tier 2, 74
  tier 3). All 1086 round-trip identically on the magnetic fields. 1082
  round-trip on every field, because the core CIF writer prints a cell angle
  and an occupancy at 4 dp. A separate multiplicity recount disagrees on 0 of
  1086. The largest refusal buckets are k ≠ 0 (901) and modulation (163).
- *Not done*:
  - **The `.pcr` line.** Jbt = ±1 is still refused, now naming its real
    reason (`MAGNETIC_PHASE_REFUSAL`). A Jbt = 1 phase is a pure magnetic
    phase with its own scale, and its `MSYM` matrices need not be ε·det(R)·R.
    Whether that stance replaces the task's "read" is the maintainer's call.
    `nuclear_only=True` now reports what it dropped
    (`FULLPROF_MAGNETIC_PHASE_OMITTED`).
  - **1314's refusal list.** `1314-mfile-reader.md` still says an `.m50`
    with modulation is refused "exactly as the TOPAS reader refuses magnetic
    space groups". The TOPAS reader no longer refuses them.
  - **The parent k is not written.** `Structure.to_cif` writes a
    `magnetic_supercell` phase in its child cell and drops
    `MagneticSymmetry.propagation_vector_parent`, so the file reads back as
    k = 0 in that cell. Writing it needs the reader's supercell fence to
    accept a file whose atoms are already the magnetic asymmetric unit.
  - **`setting` prose lands in a Pp_abc field.** The same writer copies
    `MagneticSymmetry.setting` into `_space_group_magn.transform_BNS_Pp_abc`.
    rietx reads it back and another program may not. `exports.md` says so.
  - **91 MAGNDATA files** are refused at tier 3 because their rotations are
    in no tabulated orientation (a two-fold along [110], for one).
    `symmetry._closest_type` has no type to give them. WP-1419's
    orientation-free metric subspace is expected to carry them.
  - **The foreign writers drop moments** in silence: #470.
  - **The TOPAS `MM_CrystalAxis_Display` line** is dropped from the
    tutorial-syntax fixture until a TOPAS run of the synthetic `str` prints
    one.
  - **A `mag_space_group`-only `str` reports `space_group=""`** in
    `TOPAS_CELL_COUPLING_DROPPED`. The group that would tie the edges exists
    only after `to_structure`.
  - **`mag_space_group` beside `space_group` with no moments** reaches neither
    the `Structure` nor a diagnostic, although `coverage.py` declares it READ.
    A group with no moment constrains nothing. Whether the row is READ or
    ignored is a stance call.
- *Deviations from the task text*:
  - Jbt = ±1 stays refused (above).
  - `mag_atom_out` is ignored as an output directive, since it carries no
    model value. The task listed it under *read*.
  - The writer's tags are checked against a list copied from `cif_mag.dic`.
    No test reads the dictionary file.
  - The acceptance's single MAGNDATA entry is covered by the aggregate run
    above. No MAGNDATA file is in the tree.
- *Gotchas found in review* (round one; each fixed with a test):
  - rietx refused a magCIF it had written for a refined oblique cell. The
    writer computed the magnitude on the unrounded cell, and the reader
    recomputed it on the printed one.
  - A bad `mag_space_group` number (`999.1`) reached the caller as a bare
    pydantic error naming no file.
  - Four tags sat in `READ_TAGS` that no code read, so a contradicting value
    passed as read.
  - A spherical or Cartesian row's su was parsed and dropped with no
    diagnostic. A Cartesian row's su now propagates.
    `CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED` names the spherical case.
  - A test fixture carried a TOPAS tutorial's own refined numbers. They are
    synthetic now, in every commit on the branch.
  - A missing centring loop was read as `x,y,z,+1` in silence
    (`CIF_MAGNETIC_CENTERING_ASSUMED` now). A decimal k of `0.0` read as
    incommensurate. A misspelled `moment_ions` key was ignored.
- *Measured on the merged tree* (`main` `b82917f4` + `2101fa80`, macOS arm64,
  python 3.12.10, `[dev,jax]`, 10 cores):
  - ruff clean.
  - Fast suite: 6496 passed, 97 skipped, 4:09, nothing else running.
  - Full `-m slow`: 230 passed, 12 skipped, 1 xfailed, 32:15. Another
    session's serial `test_acceptance_indexing.py` shared the machine for the
    last two minutes.
  - CI's five fast jobs and lint were green on `2101fa80`. `main` did not
    move between the run and the merge.
- *Next*: the `.pcr` stance and 1314's refusal-list line, then the supercell
  reader that lifts the k ≠ 0 refusal and lets the writer keep the parent k.

- **2026-09-02** — created, from the assessment of PR #221, which had the
  readers as one task inside a single WP. Split off because the readers meet
  a user's existing work and their refusals are today's most visible
  statement that the package has no magnetic model. No code touched. First
  task is the magCIF reader.

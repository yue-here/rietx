# WP-1328 — magnetic interchange: magCIF in and out, and the readers stop refusing

Milestone: magnetic · Status: ✅ 2026-10-03 — every task landed (PRs #544, #571), shipped in 1.6.0
Depends on: 1327 (the model the files describe); 1118 soft (the coverage
registry the foreign readers report through)

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
- [x] The `.pcr` magnetic rows: Jbt = ±1 in the magnetic cell read,
      Fourier-component form refused by name; a fixture per stance.
- [x] Manual Part 1 (`using/data.md` and the interchange chapter), skill
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

- **2026-10-03** — **Closed** by a cleanup session over unowned in-flight
  WPs. A magnetic phase now reads from and writes to magCIF, and the foreign
  readers that refused one read it.

  *Inherited, consumed*, each checked against the tree. #567 and #470 are
  closed (PRs #571 and the refusal PR). The nuclear-group tiers are in
  (`CIF_MAGNETIC_NUCLEAR_SETTING`, `nuclear_group`). The project coverage
  table reads moments and magnetic groups (`coverage.py:142-146`), the
  registry's rows say so, the writer emits `name_BNS`, and the TOPAS writer
  writes `mlx mly mlz`. The `k` naming note is a convention now. The 1118
  rulebook notes were guidance for writers that have landed. *Forwarded* to
  WP-1326's Inherited: two design choices #567's entry left open, a
  `.pcr` nuclear phase's `Nvk` k that `fullprof.to_structure` drops, and
  `Structure.to_cif` writing no k. *Not measured, not carried:* whether
  GSAS-II's own CIF import reads the magCIF loops the `gsas2` writer emits.
  Narrative moved to the v1.7 record.

### 2026-10-01 — #567's writer refusal landed from outside

The FullProf, GSAS and GSAS-II writers now refuse a phase that carries a
propagation vector, naming it, instead of writing a file that reads back as
k = 0. Every writer's refusal, TOPAS's included, now points at the
`Structure`'s JSON, the one export that keeps k.

- *Done:* PR #571 (`5bc4c725`), merged as `b9d87369` by `/pr-review`, closing
  #567, which is the `### Inherited` entry "`Phase.propagation_vector` is
  refused by the TOPAS writer only". `symmetry.refuse_propagation_vector` sits
  beside `refuse_magnetic_phase`, and each writer calls it per phase before
  writing.
- *Measured* by the contributor: FullProf 8.20 gives a nuclear phase with
  `Nvk = 1` satellites at a nuclear |F|², which is why the `.pcr`'s k is a
  different model from rietx's.
- *Still open* from that entry, unchanged and design choices:
  `fullprof.to_structure` drops a nuclear phase's `Nvk` k, and
  `Structure.to_cif` writes no k.
- *Next:* prune `### Inherited`, then close.

### 2026-09-30 — the TOPAS moment writer and the `.pcr` stance landed from outside

A magnetic phase now travels both ways through the two foreign formats that
can state one. `write_topas_inp` writes it the way TOPAS's own magnetic
examples do: `mag_space_group <BNS number>`, `mlx mly mlz` on each moment-
bearing site in TOPAS's fractional basis, and `mg` where a Landé g is set.
What a `str` cannot state, it refuses by name. A FullProf `.pcr` with a `Jbt
= ±1` phase in its own nuclear cell at k = 0 now reads onto that nuclear
phase, and every other magnetic stance is refused by name. Both writer
halves ran in TOPAS 6 as a black box, and on those three blocks TOPAS's
intensities match rietx's to one constant factor. This landed as PR #544
(`mustachefeeling`), merged as `fa3d0827` in a `/pr-review` run, with #551
(#550's ion spelling) already on `main`, so the written files run unchanged.
Every task is now ticked. The `### Inherited` items remain, including a new
one from this review.

- *Done*: PR #544, in three commits and three review fixes.
  - **TOPAS writer.** `_magnetic_group_line` refuses a non-standard setting,
    a group with no tabulated number, a nuclear group larger than the
    magnetic family group (#457 tier 1), a group with no site moment, a
    moment ion ≠ the site species, and a propagation vector (either
    `MagneticSymmetry.propagation_vector_parent` or
    `Phase.propagation_vector`, which used to be dropped from a `.inp` in
    silence). The write → read round trip holds to one ulp on 60 moments per
    cell class, orthorhombic, monoclinic and oblique triclinic. `(m/a)·a` is
    not always `m`, and neither neighbouring double of the quotient does
    better.
  - **`.pcr` reader.** `magnetic_reading(model, phase)` returns a
    `MagneticReading` or its refusal as a sentence. It reads a SYMM/MSYM
    pair as a Shubnikov operation exactly when M = ±det(R)·R at phase 0 (the
    FullProf manual's eq. 3.52). It requires the counterpart's cell, Biso,
    multiplicity and `Scale × f²`. `FULLPROF_MAGNETIC_PHASE_READ` (info)
    reports the merge. It refuses by name the Fourier form, `Isy = -2`, `Cen
    = 2`, `MagMat > 1`, a non-axial MSYM, no nuclear phase in the cell, a
    scale mismatch, `Jbt = -1` on a non-orthogonal cell, soft moment
    constraints and moment ties.
  - **Docs.** `using/files.md` and `using/data.md` in the manual, the
    skill's §7j routing row (4 bytes shorter), `references/magnetic.md`'s
    two code rows, and 1314's refusal list, which now drops the commensurate
    phase. Both WP edits were accepted by the maintainer in the batch.
- *Review fixes* (round 2, `2933d17`, `76a2cba`, `ea7dc19`). A `Jbt = ±1`
  phase with no sites, and a counterpart symbol gemmi cannot parse, used to
  escape as bare `ValueError`s naming no file (`max()` of an empty list;
  gemmi's "Unknown space-group name"). Both now refuse by name. The read
  message quoted `found.bns_number` without checking `found.named`, so an
  unnamed group printed `(BNS unnamed)`, the property's placeholder. It now
  quotes `found.reason`, as `_magnetic_group_line` does.
- *Gotchas*:
  - **A partly freed moment reads fully free.** A `Moment` carries one
    refine flag (its three `vary` are one intent that frees the DOFs), so a
    site whose `.pcr` frees only M under `Jbt = -1` comes in with the
    direction free too. The TOPAS reader on `main` merges the same way. The
    read message now names such a site.
  - **Two conformance readings that were not findings.** The writer's single
    `@`/`!` for `mlx mly mlz` is the io rulebook's "merges free, and the
    group is named". "Kit 2" was not a private-corpus name: it is the
    2026-09-25 TOPAS measurement cell, and the test comments now point at
    `TopasSite.moment`'s moment-basis note.
- *Next*: prune `### Inherited`. The 2026-09-30 item (the GSAS, FullProf and
  GSAS-II writers drop `Phase.propagation_vector` silently) is the one this
  review added. A `.pcr` *writer* for `Jbt = 1` was not attempted. Then
  close this WP.
- *Measured on the merged tree* (Linux x86_64, 4 cores, py3.12.3,
  `[dev,jax]`, run as root). Round 1, on `4de2528` + #544: the area files
  with slow tests (`test_projects_topas`, `_fullprof`, `_fullprof_magnetic`,
  `test_writers_refuse_magnetic`, `test_magcif`, `_gsas`, `_gsas2`,
  `test_portability`, `test_skill`, `test_manual`, `test_manual_api`,
  `test_docs_consistency`), 969 passed, and both refusal reproductions as a
  scratch script. The gate, in one stack with #556 and #537 (no shared file)
  on `44eaa09`: 7143 passed, 119 skipped, 1 failed in 1:09:15. The failure
  is `test_held_phase`'s ramp runaway guard (70.3 s against 60 s; 19.6 s
  alone, WP-1420's load sensor). `main` after the three merges, `e8d15d0`,
  is content-identical to the gated tree.


### 2026-09-29 — the foreign writers' refusal landed from outside (#470)

The four foreign-project writers no longer hand another program a magnetic
phase with its moments stripped. `write_topas_inp`, `write_fullprof_pcr`,
`write_gsas_exp` and `write_gsas2_phase_cif` now raise a `ValueError` that
names the phase, its magnetic group and how many sites carry a moment. They
point the caller to `Structure.to_cif`, the one writer that carries the
moments. Before this, each wrote the phase as a nuclear one, with no
exception and no warning, and the file refined as a paramagnet. This is the
refusal issue #470 asked for, decided in this WP's `### Inherited` on
2026-09-27 as a PR separate from this WP. It arrived as the contributor's PR #521 and merged
as `18ae8eff` in the `/pr-review all` run of 2026-09-29. It closed #470.

- *Done*: PR #521.
  - `crystallography.symmetry.refuse_magnetic_phase(phase, fmt, why=None)`
    sits beside `refuse_operation_list`, with one call in each writer where
    that refusal already runs. It tests `magnetic_symmetry` and the site
    moments separately, so neither half-magnetic state rests on the
    schema's own refusal.
  - **gsas2 refuses too, and on a measurement.** The GSAS-II phase CIF does
    carry the magCIF loops (through `write_structure_block`, since #478).
    But GSAS-II 5.6.3's scriptable `add_phase` reads that file back as
    `General.Type` `nuclear`, with no magnetic group, every spin +1 and no
    warning. That is the same silent drop, one program later, so the
    refusal passes `why=` naming the importer. The contributor ran GSAS-II
    as a black box and did not read its source. A hand-canonicalised magCIF
    was read by no GSAS-II importer at all.
  - `tests/test_writers_refuse_magnetic.py`, 15 tests: per writer, the
    refusal message, no file left on disk, and a moment-free twin writing
    with no magnetic token. Also the gsas2 reason and both half-magnetic
    states at the helper.
  - Docs: one sentence in `using/files.md`, and an "Exporting" line in the
    skill's `references/magnetic.md` tagged `(Measured: GSAS-II 5.6.3,
    issue #470)`, with all three copies synced.
- *Measured* (review, Linux x86_64, 4 cores, Python 3.12.3, `[dev,jax]`
  bench venv, run as root, on `f1b89d63` with #523, #450 and #521 merged
  together, which touch disjoint files): full suite, slow included, 7013
  passed, 118 skipped, 1 failed. The failure was a wall-clock runaway guard
  in `test_held_phase.py`, 76.2 s against 60 s under a load average of 9-11
  on 4 cores. It passes alone in 18.85 s.
- *Not done*: writing magnetic records in any foreign format. That means
  TOPAS `mlx mly mlz`, whose basis #478 measured on the reader's side, and
  a GSAS-II-readable magnetic phase if a spelling exists. Both stay with
  this WP, after the refusal, as decided on #470. The `.pcr` line and the
  manual-and-skill line are unchanged.
- *Next*: the `.pcr` Jbt stance, 1314's refusal list, and the TOPAS
  moment writer.

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

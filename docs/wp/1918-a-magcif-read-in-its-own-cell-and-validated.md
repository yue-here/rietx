# WP-1918 — a magCIF the reader refuses today is read in its own cell, and one validator checks it on the way in and out

Milestone: unscheduled · Status: 🔄 2026-11-01 — FullProf's `_parent_space_group.name_H-M` spelling read, from outside as PR #1193 (`cd1c39ff`); an empty second block skipped and the draft magnetic tags refused, as PR #1257 (`1c55eda6`, #1063 items 1 and 3); the six maintainer decisions and I-a onwards open
Track: Coming from another code
Depends on: — (1911 soft: the structure-level setting transform the BNS restatement uses)
Priority: P2 2026-10-08 — a refusal that fires on readable files: 615 of the 900 supercell refusals name a double count the file does not have

## Goal

A commensurate k ≠ 0 magCIF (or one with |det P| ≠ 1) reads in its own cell
under the file's own group, records its parent, and says so in one
diagnostic. Every magnetic phase that enters or leaves rietx passes one
validator, `validate_magnetic_phase`, whose P1 |F|² comparison is the check
that caught the last silent misread class.

## Context

From issues #757 (the import side) and #758 (the validation), both by
mustachefeeling, 2026-10-06, companions to #756 (the CIF writer, folded into
WP-1319). They are one WP because #758's first chunk is #757's acceptance:
every newly read file goes through the P1 check. Every count below is the
reporter's, an aggregate over a local MAGNDATA mirror (Gallego et al. 2016)
reported as counts and entry ids only. MAGNDATA files are never
redistributed or committed.

**Where the reader stands.** `structure_from_cif` reads one block through
`gemmi.read_small_structure`. On a magnetic file it refuses modulation
(`magcif.refuse_modulation`, `magcif.py:458`) and a supercell
(`refuse_a_magnetic_supercell`, `:614`) before anything is built. It resolves
the nuclear group in three tiers (`resolve_nuclear_symmetry`, `:866`): the
parent, the file's own family group in a tabulated setting, and the file's
own operation list under a bracketed label (#448). Of 2447 MAGNDATA files,
1121 read on `65a78ab7`. The refused classes that are design questions:

| count | class | where it fires | chunk |
|---|---|---|---|
| 900 | commensurate k ≠ 0 or \|det\| ≠ 1 | `refuse_a_magnetic_supercell` | I-a, I-b, I-c |
| 91 | family group in no tabulated orientation | `_unnamed_nuclear_group` (`:809`) | I-d |
| 51 | form factor (47 are Ir, Re, Os: 5d, no ⟨j₀⟩ row) | `Phase._moments_are_stateable` | I-e |
| 33 (behind I-c) | an operator gemmi's parser refuses (`-2x+y`, a 1/5 translation) | gemmi `Op` | I-f |
| ≤ 21 | a non-UTF-8 byte in a quoted value; typographic quote delimiters | gemmi tokenizer | I-g |

**What a k ≠ 0 file is.** The supercell refusal says the magnetic
asymmetric unit "generally splits one nuclear orbit". The reporter expanded
every refused file under its own operators: 615 have one listed site per
nuclear orbit and 280 have several. The double count the refusal names
happens under tier 1 only, where `_orbit_mismatch` already detects it. Under
tiers 2 and 3 the listed sites are the asymmetric unit, which is how
`magnetic_supercell(nuclear_group="magnetic")` already states a k ≠ 0
structure (#477). A scratch rewrite of each refused file read 693 more on the
reporter's tree; those 693 have not been through the P1 and overlap checks.

**What is already checked** (#758 § 1, eleven rows). The load-bearing one is
structure invariance: `group_symmetry_violations` and
`check_group_is_structure_symmetry` (`crystallography/magnetic/scattering.py:207`,
`:334`), run at the readers, at `Refinement.__init__`
(`_judge_magnetic_groups`, `refine.py:1753`) and by the supercell builder. It
is the moment half of TOPAS's P1 check. The |F|² half is a separate check:
the symmetric model's reflection list is masked by the parent's centring
(`magnetic_reflections`, `scattering.py:448`) and the P1 phase has no mask.
That is where the M1 misread lived (20 files, magnetic peaks dropped,
`predict()` off by 0.5-32 % of the pattern maximum).

**The proposed checks**, from #758 § 2. `MAGNETIC_P1_MISMATCH` (error):
|F_m|² and |F_N|² on the symmetric phase's reflections to d = 1 Å against
`restate_phase_in_p1` of the same phase, 1e-8 relative, after snapping sites
to their special positions (83 files differ by ≤ 4.5e-4 from printed
rounding before snapping). Called at read, at `Refinement.__init__`, and
before `write_magnetic_block` and `write_topas_inp`. Two report fields on
`FitReport.magnetic`: `net_moment_per_cell` and
`ferromagnetic_component_allowed`. Later and info only:
`MAGNETIC_ORBIT_MODULI_DIFFER`, `CIF_MAGNETIC_K_INCONSISTENT` (exact over
`Fraction`, the `cif_mag.dic` rule for k against anti-translations), and
`MOMENT_IMPLAUSIBLE` (|m| above 1.2 × the free-ion saturation moment from
`form_factor._ASSUMED_ION_SLJ`, `:528`).

**The chunks**, from the two issues' comments of 2026-10-06, each a PR off
`main`:

- I-a. `refuse_a_magnetic_supercell` says which case the file is (one moment
  per orbit, several, a k = 0 nuclear superstructure, an irrational k). No read
  changes.
- I-b. A parent record on `MagneticSymmetry` (`space_group`,
  `child_transform_Pp_abc`, `propagation_vector`) read from `_parent_*`, with
  k taken as stated. An integer k in a centred parent is a zone-boundary
  vector, and `is_commensurate_zero` (`magcif.py:312`) reads it as Γ today.
  `SCHEMA_VERSION` bump.
- I-c. A rational k ≠ 0 or |det| ≠ 1 file read under tiers 2/3, with
  `CIF_MAGNETIC_SUPERCELL_READ` (info). `nuclear_group="parent"` refused by
  name. An unrecognised parent symbol falls through. An irrational k stays
  refused and names #678.
- I-d. A family group in an untabulated orientation restated at its BNS
  standard setting through the file's `transform_BNS_Pp_abc`, with
  `CIF_MAGNETIC_RESTATED_BNS` (warning) and `setting="file"` to opt out.
- I-e. A 5d ⟨j₀⟩ table, Kobayashi, Nagao & Ito (2011).
- I-f. rietx's own triplet parser in `MagneticGroup.from_xyz`, gemmi as
  oracle wherever gemmi parses.
- I-g. Two repairable text faults with `CIF_TEXT_REPAIRED`, and `encoding=`.
- V-a. `crystallography/magnetic/validate.py`, `validate_magnetic_phase`,
  the P1 |F|² check, at read and before both writers.
- V-b. The check at `Refinement.__init__`; the two report fields.
- V-c. Tests only: an explicit-cell |F|² sum using no rietx orbit code and the
  0.3 Å / occupancy > 1 overlap oracle, over every synthetic fixture and, as a
  `slow` opt-in, a local mirror reporting counts.
- V-d. The three info checks.

Order from the issues: I-a → I-b → V-a → I-c, then I-d, I-e, I-f in any
order, I-g after its decision, V-b after V-a, V-d after I-b.

**Seams.** `crystallography/magcif.py`, `crystallography/cif.py`,
`schemas/structure.py` (`MagneticSymmetry`, `propagation_vector_parent` at
`:620`), `crystallography/magnetic/{operators,form_factor,scattering,p1}.py`,
`refine.py`, `report/`, `io/projects/topas.py`, `help.py`, and the skill's
`references/magnetic.md` (every magnetic row goes there, diagnostic codes
included).

**Licensing and data.** MAGNDATA entries are cited by id and never
committed; a fixture is synthetic. The Kobayashi table is a transcription of
a published table into a file that ships in the wheel, so it states its
source and status where it ships (root CLAUDE.md § Licensing). The existing
⟨j⟩ rows came from the public-domain `periodictable` table, and the GPL
transcriptions were deliberately not copied. TOPAS is a black box.

### Inherited

- **2026-10-11, from the issue triage (#757): #756's C-a registry has landed,
  so I-b and I-c take tag names from it.** `rietx.io.cif.registry` (PR #851)
  has no `_parent_*` rows yet, and `tests/test_cif_registry.py` asserts that
  what is written equals the registry. The C-f writer therefore adds
  `_parent_space_group.name_H-M_alt`, `.child_transform_Pp_abc` and
  `_parent_propagation_vector.kxkykz` as rows with their `cif_mag.dic`
  definitions, and I-b agrees the field names with it first. Checked against
  the tree at 7d9be3cb: `io/cif/registry.py`; none of
  `CIF_MAGNETIC_SUPERCELL_READ`, `CIF_TEXT_REPAIRED`,
  `CIF_MAGNETIC_RESTATED_BNS` is under `src/`.

- 2026-10-26 issue triage: #1063 (mustachefeeling, 2026-10-20), three FullProf-mCIF refusals on k = 0 files, independent of I-c. Checked against the tree at c0e32ab29, from `tests/test_magcif.py`'s Cr₂WO₆ fixture: (1) an empty `data_global` block ahead of the structure block, or one holding only `_audit_*` tags, raises "single data block expected, got 2 — this file does not read as a CIF (an empty, truncated or non-CIF file reaches here)" (`crystallography/cif.py:206-209`); (2) `_parent_space_group.name_H-M` without `_alt` raises `MagCifError` naming only the `_alt` tag (`magcif.py:683-690`); `cif_mag.dic` 0.9.9 defines only `name_h-m_alt` (`tests/data/cif_dictionaries/cif_mag.dic:3320`); (3) pre-2016 `_magnetic_atom_site_*`/`_magnetic_cell_*` tags raise "no atom sites found". Two real mCIFs from FullProf's example distribution (held locally, never to be committed) write `_parent_space_group.name_H-M` and both raise (2); with the tag renamed to `_alt`, both read. GSAS-II 5.8.4 falls back to `name_H-M` when `_alt` is absent (`imports/G2phase_CIF.py:242-244`, read 2026-10-26). Proposed: read `name_H-M` where `_alt` is absent, with an info diagnostic naming the non-dictionary tag, and refuse when both are present and disagree; read the one block holding an `_atom_site_` loop when every other block is empty or `_audit_*` only, with an info diagnostic naming the skipped blocks, while two structure blocks stay refused with a message that counts them and names `block=`; refuse the pre-2016 tag set by name. Item (1) edits the same reader lines as WP-1933's C-e (`structure_from_cif(block=)`), whose Inherited already records the wrong-cause message; build them together or land this rule first and let C-e generalise it. Each new code needs its `_audit` row (tier 1: the format's definition) and its `help.py`/skill row.

## Non-goals

- Modulated files and an irrational k (164 files): #678 and the v2+ fence.
- The CIF writer and the tag registry: WP-1319 (#756). Writing the parent
  record back is #756's C-f; which WP owns it is open (Tasks).
- The structure-level setting transform itself: WP-1911 owns "the shared
  transform". I-d consumes it, or builds it if it lands first; it is built
  once.
- The P1 export route and the foreign writers' magnetic legs: WP-1911
  Part D (#713, #721).
- The overlap repair (`CIF_SITE_TWINS_MERGED`, `CIF_SITE_LISTED_TWICE`) and
  the M1 forward-model fix: landed as PRs #765 and #763.
- `MagneticCandidate.verified` (#607): WP-1418.
- Metric ties derived from the operators in the file's own orientation: the
  alternative to I-d (see the decision below).

## Tasks

- [ ] **Decision (maintainer):** lift the supercell refusal for a rational k
      and |det| ≠ 1 (#757 decision 2).
- [ ] **Decision (maintainer):** the parent record as one nested record or
      two flat fields, `propagation_vector_parent` kept as an alias for one
      release (#757 decision 3). Needed before I-b.
- [ ] **Decision (maintainer):** the 91 untabulated orientations. 1328's
      closing handover expected WP-1419's operator-derived metric subspace to
      carry them. #757 proposes a BNS restatement on read instead, with a
      warning and `setting="file"`. Which, and whether I-d builds WP-1911's
      transform or waits for it.
- [ ] **Decision (maintainer):** lenient repair of the two text faults by
      default, or only under `encoding=` (#757 decision 1).
- [ ] **Decision (maintainer):** `verify=True` by default at read and at
      `Refinement.__init__`, with the fit refused on `MAGNETIC_P1_MISMATCH`;
      and whether `write_topas_inp` refuses such a phase or writes it with
      the diagnostic in the header (#758 questions 1 and 3).
- [ ] **Decision (maintainer):** whether this WP joins the `magnetic`
      milestone.
- [ ] I-a: the supercell refusal names its case; reads unchanged
- [ ] I-b: the parent record, read from `_parent_*`; `SCHEMA_VERSION` bump
- [ ] V-a: `validate_magnetic_phase` with `MAGNETIC_P1_MISMATCH`, at read and
      before `write_magnetic_block` and `write_topas_inp`
- [ ] I-c: a rational k ≠ 0 file read under tiers 2/3,
      `CIF_MAGNETIC_SUPERCELL_READ`
- [ ] V-b: the check at `Refinement.__init__`; `net_moment_per_cell` and
      `ferromagnetic_component_allowed` on `FitReport.magnetic`
- [ ] I-d: untabulated orientation, as decided
- [ ] I-e: the 5d ⟨j₀⟩ table with its source row
- [ ] I-f: the triplet parser
- [ ] I-g: the two repairs, as decided
- [ ] V-d: the three info checks
- [ ] Tests: V-c's oracle over every synthetic fixture; the mirror run as a
      `slow` opt-in reporting counts; obs/calc/diff PNGs to `tests/output/`
      for the MnO-shaped fixture
- [ ] Skill: a row in `references/magnetic.md` per new diagnostic code, and
      the "you were handed a magnetic structure" routing row updated for the
      supercell read

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magcif.py tests/test_magnetic_supercell.py tests/test_operator_list_phase.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

- The synthetic Pbcm child at k = (½, 0, 0) of `test_magnetic_supercell.py`,
  written with its parent block, reads back equal on every field,
  `propagation_vector_parent` included (`test_magcif.py:997` inverted).
- A MnO-shaped file (#612) built by hand in the magnetic cell reads, and its
  `predict()` equals an independent P1 sum to 1e-12.
- A synthetic F-centred parent with k = (1, 0, 0) keeps that k and is not read
  as Γ.
- The incommensurate-k file is still refused and names #678. A synthetic
  file whose primed centring contradicts its k is never read silently.
- `MAGNETIC_P1_MISMATCH` fires on a synthetic M1 reproducer with #763's fix
  reverted in the test, and is silent on every existing magnetic fixture and
  on a site 5e-5 off its special position. Its cost per read on the largest
  fixture is measured twice and stated with its conditions.
- MnF₂ (136.499) reports a forbidden ferromagnetic component and a net moment
  of zero. A synthetic ferrimagnet reports the difference of its sublattices.
- Every file that reads today reads bit-identically on every field it reads
  today.
- On the local mirror (counts only): at least 1817 files read, every new read
  passing the P1 check with zero new misreads.

## References

- Issues #757, #758 (with their 2026-10-06 cuts), #612, #678, #709, #713,
  #721; PRs #763, #765, #767, #769 (the sweep's four fixes), #713, #787.
- Gallego, S. V. et al. (2016). *J. Appl. Cryst.* **49**, 1750 and 1941
  (MAGNDATA).
- Kobayashi, K., Nagao, T. & Ito, M. (2011). *Acta Cryst.* A**67**, 473
  (5d radial integrals); *Acta Cryst.* A**68**, 589 (2012).
- COMCIFS `cif_mag.dic` 0.9.9 (the k and anti-translation rule).
- Ashcroft, N. W. & Mermin, N. D. (1976), Table 31.3 (the (S, L, J) rows
  already in `form_factor.py`).
- [1328](1328-magnetic-interchange.md) the reader this extends;
  [1327](1327-magnetic-structure.md) the model; [1911](1911-the-foreign-writers-state-what-the-other-program-reads.md)
  the transform and the export legs; [1319](1319-structure-interchange.md)
  the CIF writer.

## Handover log

- **2026-11-01** (`/pr-review`) — #1063's items 1 and 3 merged from outside as PR #1257 (`1c55eda6`). A CIF whose other data blocks state nothing, or only `_audit_` tags, now reads its one structure block. It records the skip as the info code `CIF_EMPTY_BLOCK_SKIPPED` (tier 1). The pre-2016 draft magnetic tags are refused by name. That refusal is the maintainer's call on file "B" in #1063: refuse. No task of this WP is ticked by it. Follow-ups, not blocking: `refuse_a_magnetic_supercell` does not consult `_magnetic_propagation_vector_kxkykz`. `refuse_draft_tags` matches `^\s*<tag>` over the raw text, so it would fire inside a semicolon text field. What ran: the PR was replayed in a stack of nine with the other round's merges onto `main` `276fe91d` and run at `635d25e3` (Mac arm64, Python 3.12, `[dev,jax]`). Full suite 14 161 passed, 235 skipped, 50 xfailed, 0 failed. The manual `-W` build was green.

- **2026-10-29** (`/pr-review`) — merged from outside as PR #1193 (`cd1c39ff`): where `_parent_space_group.name_H-M_alt` is absent, the reader takes FullProf's `_parent_space_group.name_H-M`, which `cif_mag.dic` does not define, and says so with `CIF_MAGNETIC_PARENT_TAG_UNDEFINED` (info, tier 1). Two tags naming different groups raise `MagCifError` quoting both. Review noted one gap for this WP: `magcif.py` promises the known tags as lists (`READ_TAGS`, `IGNORED_TAGS`, `PRIVATE_TAGS`), and this tag is in none of them, so the completeness oracle cannot see it. None of this WP's tasks is ticked by it; the six decisions stand.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issues #757
  and #758). Checked against the tree at `5d1f5f67`:
  `refuse_a_magnetic_supercell` (`magcif.py:614`), `refuse_modulation`
  (`:458`), `resolve_nuclear_symmetry` (`:866`) and `_unnamed_nuclear_group`
  (`:809`) stand as #757 describes; `form_factor.py` has no Ir, Re or Os
  row; `test_magcif.py:997` pins the parent k lost; no
  `validate_magnetic_phase`, `MAGNETIC_P1_MISMATCH` or `MOMENT_IMPLAUSIBLE`
  exists; `restate_phase_in_p1` exists (`crystallography/magnetic/p1.py:105`,
  PR #713). The four sweep fixes both issues wanted first have merged (#763,
  #765, #767, #769, 2026-10-06), so the 23 misreads are fixed and nothing
  blocks I-a or V-a. PR #787 (merged 2026-10-06, for #612) covers none of
  #757's chunks. It makes `magnetic_supercell`'s refusals on rock salt at
  k = ½½½ name their cause, which is the builder-side analogue of I-a, and
  names the child-cell route as I-c. No MAGNDATA count was re-measured here.
  No open WP owns it: 1328 owned the magCIF reader and closed 2026-10-03, its
  last "Next" naming the supercell reader; 1327's non-goals give magCIF
  reading to 1328; 1911 owns the export legs and the transform, not the
  reader.

# WP-1918 — a magCIF the reader refuses today is read in its own cell, and one validator checks it on the way in and out

Milestone: unscheduled · Status: 🔄 2026-11-03 — FullProf's `_parent_space_group.name_H-M` spelling read, from outside as PR #1193 (`cd1c39ff`); an empty second block skipped and the draft magnetic tags refused, as PR #1257 (`1c55eda6`, #1063 items 1 and 3); its review follow-ups (text fields skipped by every raw-text scan, the draft k tag reaching the supercell refusal) as PR #1284 (`fd5c0bf5`); the six decisions recorded; I-a onwards open, I-d waiting on PR #1108
Track: Coming from another code
Depends on: 1419 soft (I-d reads through its `Phase.parent_cell`, PR #1108)
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
- I-b. A parent record on `MagneticSymmetry`, one nested `parent` record
  (`space_group`, `child_transform_Pp_abc`, `propagation_vector`) as decided
  below, read from `_parent_*`, with k taken as stated. Old files migrate at
  read, and `propagation_vector_parent` keeps no alias. An integer k in a centred parent is a zone-boundary
  vector, and `is_commensurate_zero` (`magcif.py:312`) reads it as Γ today.
  `SCHEMA_VERSION` bump.
- I-c. A rational k ≠ 0 or |det| ≠ 1 file read under tiers 2/3, with
  `CIF_MAGNETIC_SUPERCELL_READ` (info). `nuclear_group="parent"` refused by
  name. An unrecognised parent symbol falls through. An irrational k stays
  refused and names #678.
- I-d. A family group in an untabulated orientation read in the file's own
  axes, through PR #1108's `Phase.parent_cell` (settled below). The child
  cell is the parent cell plus a strain, with ties derived from the
  operators. No restatement and no `setting=` keyword. #757 had proposed a
  BNS restatement with `CIF_MAGNETIC_RESTATED_BNS`.
- I-e. A 5d ⟨j₀⟩ table, Kobayashi, Nagao & Ito (2011).
- I-f. rietx's own triplet parser in `MagneticGroup.from_xyz`, gemmi as
  oracle wherever gemmi parses.
- I-g. Two repairable text faults, repaired by default with
  `CIF_TEXT_REPAIRED` naming the lines (settled below), and `encoding=`.
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

- **2026-11-28, from the issue triage (#1833, a bug in a message): the k ≠ 0
  refusal's wording fails two ways, and both belong to I-a.** Checked at
  `02341ffdb`, `crystallography/magcif.py` `refuse_a_magnetic_supercell`
  (`:763`, the wording at `:815-836`). (1) A decimal k is called
  incommensurate. A component counts as incommensurate when it matches
  neither `_RATIONAL` nor `_INTEGER_DECIMAL`, so `0.5` falls through.
  MAGNDATA 1.31 (MnO, k1 `[0.5 0.5 0.5]`, transform `2a,2b,2c;0,0,0`, |det| = 8)
  is told "The k stated here is not a rational, so this is an incommensurate
  structure". The module's own comment (`:311`, review of #478) says telling
  `0.5` from `0.128` is a judgement this reader does not make, and the
  transform's determinant already settles commensurability. (2) A truly
  incommensurate k gets the supercell sentences: Fe₂SiO₄
  (`fe2sio4_42deg_1_8k2.mcif`, k `[0.7757 0 0]`, doi:10.7488/ds/2439) opens with
  "states its magnetic structure in a cell that is not the parent cell" and ends
  with "the nuclear space group of the supercell", neither of which holds. The
  reporter's asks: the commensurate wording when the transform is a supercell;
  otherwise, for decimals, "k written as decimals; not judged commensurate or
  incommensurate"; and the incommensurate branch its own lead-in and its own
  "what would be needed" (a modulated-moment, superspace model). The asks come
  from the magnetic path's owner (#1075) and match the module's own stance, so
  the session takes them as stated, with both files as message pins.
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

- **2026-11-19, from the issue triage (PR #1697; issue #1688): a phase whose group gemmi cannot name
  raises in `report()` and in the nuclear CIF writer.** I-d sets `parent_cell` where
  `_closest_type` is `None`, so every phase it reads is this kind. On a `magnetic_supercell`
  child (`R-3m [unnamed in 2a,a+b,a+c]`) the fit completes, then `report()` raises at
  `crystallography/satellites.py:746` and `write_structure_block` at `io/cif/blocks.py:217`,
  both through `OperatorGroup.closest_type`. Checked against the tree at 7a4a6cd20. WP-2221
  owns the fix. I-d's acceptance run reaches the same raise until it lands.
  **Update 2026-11-19, from WP-2221 (PR #1721):** both now return.
  `OperatorGroup.crystal_system_str` reads the operators in any cell
  (`symmetry.crystal_system_of`). `hm`, `ext`, `number`, `monoclinic_unique_axis` and
  `cell_constraints` on such a list still raise, so an I-d phase states its cell through
  `parent_cell`. Its satellite candidates omit the hexagonal (⅓, ⅓, ·) points, and its GUI
  symmetry row stays an error row.

- **2026-11-19, from the issue triage (PR #1697; issues #1689, #1691): the 4d ions past M⁺ have no
  form-factor row, and computed rows are offered.** Folded here beside I-e because both add
  rows to one table in `crystallography/magnetic/form_factor.py`, with an `ATTRIBUTION.md` row
  and the table's fingerprint test, and because #1691's first question is I-e's own (which
  analytic form the computed rows share). I-e as written covers 5d only, so this widens it.
  - #1689: `magnetic_form_factor("Ru4+", s)` raises `KeyError`, as do `Ru3+` and `Rh4+`; the
    table carries `Ru`, `Ru1+`. The refusal is #202's rule and stays. The reporter found no
    held reference tabulating Ru²⁺-Ru⁴⁺ (Brown 2004 stops at M⁺ for every 4d element;
    Kobayashi et al. 2011 is 5d). One MAGNDATA file among #757's 51 form-factor refusals is
    Ru⁴⁺, so this row moves I-e's count.
  - #1691: ten computed ⟨j₀⟩/⟨j₂⟩ rows (Ru³⁺-Ru⁶⁺, Rh⁴⁺, Tc⁴⁺, Mo³⁺-Mo⁵⁺, Nb⁴⁺), free-ion
    Hartree-Fock from Cowan's RCN in Kobayashi's HFR footing, fitted to Brown's 7-parameter
    form, with the reporter's controls (Brown's Fe³⁺ and Ru⁺, Kobayashi's Ir⁴⁺, a Dirac-Fock
    check). It also proposes a user-supplied form factor with a required source string, and
    leaves five questions open: which form ships, which ions, evaluation past s = 1.5 Å⁻¹,
    where the input decks live, and where a user-supplied form factor is declared.
  - #1691's comment of 2026-11-19: the shipped bare `"Mo"`, `"Tc"`, `"Ru"`, `"Rh"` rows are
    Brown's fits to singly charged M⁺ 4dⁿ⁻³5s² curves under a neutral label, and the reporter
    asks for a note on the rows or true neutral rows.
  - Checked against the tree at 7a4a6cd20: the three `KeyError`s reproduce; the bare and `1+`
    rows differ (`Ru` 0.4907 against `Ru1+` 0.4268 at s = 0.2 Å⁻¹). The configuration claims
    in the comment were not re-derived.
  - Who decides: every question above is a magnetic-path design call, so Mike's (#1075). Two
    touch the maintainer's side and are named for the maintainer: computed coefficients would ship in the
    wheel, where the data fence asks each file to state its status (root CLAUDE.md
    § Licensing), and question 4 decides whether the input decks enter the repository.
  - **Ruled by the maintainer 2026-11-21: the computed rows ship in the wheel, labelled.**
    They go in their own data file beside Brown's, which states that the rows were computed
    for rietx with RCN and are not peer-reviewed. `approximation_name` names that footing on
    every result that uses a row. The rule that nothing without a peer-reviewed citation goes
    public guards against exposing someone's data (its recorded case was an embargoed sample).
    These numbers are the contributor's own and are already public in #1691, so the rule does
    not bar them. The docs keep the free-ion caveat that applies to every row.
  - Question 4, settled by Claude under that ruling: the input decks and the driver script go
    in `tools/`, outside the wheel, so anyone can regenerate and check the rows. RCN itself
    stays out; only its output numbers ship. The other four questions, and the bare-row note,
    stay Mike's.
  - **Ruled by Mike 2026-11-23** (#1691, comment of 08:43Z), on all four and the bare rows.
    Q1: HFR footing, and the ten ions ship as computed ⟨j₀⟩, ⟨j₂⟩, ⟨j₄⟩ *tables* on
    s = 0-6 at 0.01 Å⁻¹ read by cubic spline, refused past s = 6, replacing the
    7-parameter rows in the issue body. Q2: the ten ions named in #1691 and no more. Q3: the
    #1796 entry below. Q5: a user curve is declared once per phase under a label with a
    colon (`Ru4+:SRO`), with a required `source`, picked by `Moment.ion`; a colon label is
    looked up only in the phase and a bare one only in the tables, and a user label
    shadowing a table name is refused. Bare `Mo`, `Tc`, `Ru`, `Rh`: true neutral rows,
    computed on Brown's footing, which moves bare-`Ru` ⟨j₀⟩ at s = 0.2 Å⁻¹ from 0.491 to
    0.416. Mike's order of work: the #1796 range check, then the data, then one rows-build
    PR. The ruling names as the maintainer's: computed tails on published ITC rows, the
    data-file format, the user-curve field name and the project schema version, the magCIF
    writer's tags and how g travels, whether the label grammar fits CIF, the TOPAS exporter
    refusing a user curve, and the release. None of those is decided here.

- **2026-11-23, from the issue triage (issue #1796, mustachefeeling): every shipped ⟨j₀⟩ and
  ⟨j₂⟩ row is evaluated at any s, past the range Brown fitted it on.** This is #1691's Q3 as
  a defect, so it folds beside that entry: one table, one decision, and Mike's announced fix
  PR is the first of the three above. `j0`, `j2`, `magnetic_form_factor` and the forward
  model's `scattering._form_factor` have no range check, and nothing in the result or the
  diagnostics says a reflection lies past the fit. The fitted ranges are s ≤ 1.5 Å⁻¹ for
  3d, 4d and actinide rows and s ≤ 1.2 Å⁻¹ for rare earths (Brown, ITC Vol. C § 4.4.5,
  p. 461), and s ≤ 1.3 Å⁻¹ for the Lisher & Forsyth Pr³⁺ row (1971, p. 548).
  - Checked against the tree at 711acfc8d, every count in the issue reproduces. Mn²⁺ ⟨j₀⟩
    is −0.00497 / 0.0272 / 0.1715 / 1.0105 / 73.30 / 1.43 × 10⁷ at s = 1.5 / 2 / 2.5 / 3 /
    4 / 6 Å⁻¹, because its third exponent is negative (c = −0.609 Å²). Three of the 96 ⟨j₀⟩
    rows carry a negative exponent (Cr²⁺ −0.0055, Mn²⁺ −0.609, Mn³⁺ −0.0088), and only
    Mn²⁺'s runs away. At s = 6, 11 ⟨j₀⟩ rows exceed 0.05 in size. No ⟨j₂⟩ row has a
    negative exponent, but the s² factor makes D·s² grow: 40 of 96 rows exceed 0.05 at
    s = 3, and 15 exceed 1 at s = 6 (Am⁶⁺ 4.65 the largest).
  - The reach inside a fit is small. TOF is fenced (ROADMAP § v2+), so a pattern reaches
    s ≤ sin θ_max/λ, and only a neutron wavelength under 0.667 Å (0.833 Å for a rare earth)
    gets past a range end. At λ = 0.5 Å to 2θ = 140°, s reaches 1.88 Å⁻¹. Over each row's
    range end to 1.88, the largest |⟨j₀⟩| is 0.032 (Am⁷⁺) and Mn²⁺ reaches 0.015. The
    largest |⟨j₂⟩| is 0.115 (Yb³⁺, past its 1.2 end), which is where a rare-earth moment
    would pick up an error of unknown size. The forward model multiplies by
    exp(−B·s²), which shrinks the runaway further: Mn²⁺ with B = 0.5 Å² gives 0.0026 at
    s = 1.88. A direct call of `j0`, `j2` or `magnetic_form_factor` reaches any s it is
    given, and that is where the 73 and the 1.4 × 10⁷ show.
  - **Ruled by Mike 2026-11-23** (#1691 Q3): Brown's rows stay as printed inside the fitted
    range. Past it, each row gets a computed tail on Brown's own footing (HF term-specific
    for 3d and 4d, Dirac-Fock for rare earths and actinides), blended over 0.2 Å⁻¹,
    labelled computed and announced by one warning. Until a row has its tail, a row whose
    fitted form runs away is refused past its range (the fix PR's criterion lists which;
    Mn²⁺ ⟨j₀⟩ is the clear case), and every other row warns once. The docs carry the
    free-ion caveat beyond about s = 1.2. The criterion for "runs away", the warning's code
    name and its `_audit` row are the fix PR's, and so Mike's.
  - **For the maintainer, open:** whether rietx may put computed tails on rows with a
    peer-reviewed ITC citation. That is a provenance change on published data, and the
    data-file format with it (#1691's ruling names both as the maintainer's). The range
    check itself does not wait on it, since a refusal or a warning changes no shipped
    number inside the fitted range.

- **2026-11-23, from the issue triage (issue #1797, mustachefeeling): the magCIF reader's
  "same number?" tolerances become the file's own print.** A proposal implementing Mike's
  ruling on the magnetic rows of PR #1636 (WP-2006's audit, comment of 2026-11-23 09:04Z):
  row 2 retires `magcif.MOMENT_FORM_AGREEMENT_MU_B` (0.02 µB) for a box of half a unit in
  each printed number's last digit, carried through any operator or axis conversion; row 1's
  tier-1 gate in `resolve_nuclear_symmetry` takes the same box instead of `_orbit_size`'s
  hard-coded 1e-3 merge. Four uses: the snap onto a moment's allowed directions; two forms
  of one moment, with the cell's printed precision carried through the conversion; a listed
  copy of a site against the image of the original's moment; the parent-group gate. It also
  carries the boundary tests for `INVARIANCE_MOMENT_TOL` and `INVARIANCE_POS_TOL`
  (`magnetic/scattering.py`) and the owed case for `WITHIN_IRREP_DRAWS`
  (`magnetic/isotropy.py`), #1636's rows 7, 8 and 4. Folded here because every use edits
  the reader functions this WP owns (§ Context names the three tiers and the invariance
  checks), and one session would build them together. WP-2006 owns the audit rows, and its
  Inherited section is rewritten by the open PR #1636, so the record sits here; the PR that
  lands this dates and retires those rows in `_audit.py` and lands after PR #1636 (which
  tiers the same five rows).
  - Checked against the tree at 711acfc8d, every "main" cell of the issue's tables that was
    run reproduces. The parent gate: P m m 2 under parent P m m m, O at (0.25, 0.3, z),
    c = 6 Å. Stated z = 0, 0.00004, 0.0002 and 0.0004 read under P m m m and store z as 0,
    4e-5, **0** and **0**; the two set to 0 are reported only as `CIF_SITE_TWINS_MERGED`.
    Stated z = 0.0008 reads under P m m 2 and keeps its z. The listed copy, on the MnF₂ fixture of
    `tests/test_cif_sites_coincide.py`: 3.012 against an image of 3.021, a sign slip on
    0.01, 3.00 against 3.01 and 3.000 against 3.015 all read, the copy dropped with
    `CIF_SITE_LISTED_TWICE`. The MAGNDATA counts (0 of 2447 files flip) are the reporter's
    and were not re-run, since the snapshot is not redistributed.
  - What the proposal does not name, found here. (1) The box primitive exists:
    `magcif._last_digit_half` (the D5 helper) and `wyckoff.nearest_allowed_within_print`
    behind `moment_within_print`, and `cif._within_printed_rounding` for positions. (2)
    `_last_digit_half("4")` is 0.5 today, and the D5 magnitude check
    (`magcif.py:1343`, `:1358`) reads it, with its docstring's own case "`magnitude = 4`
    against components giving 4.0497" passing on that 0.5. The ruling reads a number with
    no decimal point as exact, so applied in the shared helper it would refuse that case.
    (3) `_orbit_size` has a second caller, `io/projects/topas.py:4803`, which imports
    magcif's, and `io/projects/fullprof.py:2513` keeps its own twin at
    `_MAGNETIC_MATCH_ATOL`. (4) `_drop_listed_twice` lives in `crystallography/cif.py:534`,
    not in `magcif.py`. (5) The docstring sentence the issue calls not borne out is at
    `magcif.py:1507`.
  - **For Mike, open** (magnetic-path design, #1075): whether "no decimal point is exact"
    also governs the D5 magnitude check, which reverses that docstring's case, or only the
    moment-component box of uses 1-3; and whether the TOPAS and FullProf project readers'
    orbit counts take the print-box gate too, or keep their merge. The reporter's count of
    MAGNDATA files that move from tier 1 to tier 2 under the use-4 gate is still to come,
    on #1797.
  - Who decides the rest: the ruling itself is Mike's, made on PR #1636. Each use changes
    what the reader returns for some file, which is reader output on the magnetic path, so
    Mike's under #1075, with the maintainer's per-release read of reader-output diffs as
    for any other reader change.

- **2026-11-24, from [2006](2006-readers-crystallography-gui-and-the-dead-surface.md) (PR #1636):
  the orbit merge builds atoms the file does not state off a 4-fold axis.** PR #1636 named
  `_orbit_size`'s 1e-3 merge `magcif._ORBIT_MERGE_TOL` and gave it a tier-3 row, with an
  injected mirror case in `tests/test_magcif.py`. Its generality judge found a band by reading
  the code, and a probe on the branch confirmed it. Setup: a magCIF in `P m m m` (BNS 47.249)
  under parent `P 4/m m m`, a = b = 4 Å, O at (7e-4, 0, 0). The reader takes the parent and
  leaves O where it is: the twin merge's `TWIN_COORD_TOL` is 5e-4 and `SITE_TOL` is 1e-4. O
  then expands to 4 images where the file's group gives 2, and only the info code fires. On a
  mirror two images are 2d apart, so the merge and the twin step agree. On a 4-fold axis
  neighbouring images are d apart, which opens the band 5e-4 < d < 1e-3. At d = 3e-4 the site
  is merged onto the axis, and at 1.2e-3 the file's group is taken. The probe script is
  ghostshift scratch, not committed. A fix changes reader output on the magnetic path, so it is
  Mike's (drafted to him with the PR #1636 reply). `topas.py` imports the same count.
  `fullprof.py` keeps its own copy.
- **2026-11-24, from 2006 (PR #1636): three magnetic rows went back to Mike.** The judge called
  `CROSS_IRREP_DRAWS`, `INVARIANCE_MOMENT_TOL` and `INVARIANCE_POS_TOL` weak. Each is at
  `unaudited` with the reason in its evidence. In short: the class merge's draw count is out of
  the caller's reach on `solve_magnetic`. The 2-decimal pair reads as a magCIF but is refused as
  explicit copies. And an honest 3-decimal hexagonal pair can be 1.5e-3 apart. The boundary
  tests owed on #1797 bear on the last two. The PR that lands the print box re-tiers them
  with Mike's answer.

## Non-goals

- Modulated files and an irrational k (164 files): #678 and the v2+ fence.
- The CIF writer and the tag registry: WP-1319 (#756). Writing the parent
  record back is #756's C-f; which WP owns it is open (Tasks).
- The structure-level setting transform itself: WP-1911 owns it, for the
  TOPAS export (#721 item 2). I-d keeps the file's axes and does not need it
  (settled 2026-11-02).
- The P1 export route and the foreign writers' magnetic legs: WP-1911
  Part D (#713, #721).
- The overlap repair (`CIF_SITE_TWINS_MERGED`, `CIF_SITE_LISTED_TWICE`) and
  the M1 forward-model fix: landed as PRs #765 and #763.
- `MagneticCandidate.verified` (#607): WP-1418.
- A restatement at the BNS standard setting on read. No surveyed program
  does it (`docs/practice.md` § A magCIF in a non-standard orientation).

## Tasks

- [x] **Decision (maintainer):** lift the supercell refusal for a rational k
      and |det| ≠ 1 (#757 decision 2). **Settled 2026-11-01 by Claude under
      measurement:** yes, once V-a's P1 check has landed, as the issue's
      order says. The refusal names a double count that 615 of the 900
      refused files do not have (the reporter's count). The read form is the
      one `magnetic_supercell` already builds (#477).
- [x] **Decision (maintainer):** the parent record as one nested record or
      two flat fields, `propagation_vector_parent` kept as an alias for one
      release (#757 decision 3). Needed before I-b. **Decided 2026-11-01
      (maintainer), by consent:** one nested `parent` record on
      `MagneticSymmetry`, mirroring magCIF's own `_parent_*` categories. Old
      saved files migrate at read (`SCHEMA_VERSION` bump), and
      `propagation_vector_parent` keeps no Python alias. Grounds: the CIF
      dictionary groups these tags as one category, and the maintainer's
      standing ruling is that old files must always open and old code need
      not.
- [x] **Decision (maintainer):** the 91 untabulated orientations. 1328's
      closing handover expected WP-1419's operator-derived metric subspace to
      carry them. #757 proposes a BNS restatement on read instead, with a
      warning and `setting="file"`. Which, and whether I-d builds WP-1911's
      transform or waits for it. **Settled 2026-11-02 by Claude under
      established practice**, on the maintainer's ask of 2026-11-01 ("look
      closer into practice and 1108, that will probably resolve it"): keep
      the file's axes, through PR #1108's `Phase.parent_cell`. No automatic
      restatement and no `setting=` keyword. Strain amplitudes are read from
      the file's cell and held by default. Grounds: MAGNDATA writes the
      parent-related setting on purpose (Gallego et al. 2016, §2.2-2.3). The
      IUCr magCIF guidelines accept it (Perez-Mato et al. 2024). GSAS-II
      5.8.4 keeps the file's axes and operators, and no surveyed program
      restates a magCIF on read (`docs/practice.md` § A magCIF in a
      non-standard orientation). I-d waits for #1108. WP-1911's transform
      stays with the TOPAS export (#721 item 2).
- [x] **Decision (maintainer):** lenient repair of the two text faults by
      default, or only under `encoding=` (#757 decision 1). **Settled
      2026-11-01 by Claude under the reader-repair rule** (root CLAUDE.md;
      precedent `CIF_SPECIES_NORMALISED`, which repairs by default and says
      so): repair by default, with a `CIF_TEXT_REPAIRED` warning naming the
      lines. At most 21 files. The new warning's text goes to the maintainer
      before merge under the reader-output rule.
- [x] **Decision (maintainer):** `verify=True` by default at read and at
      `Refinement.__init__`, with the fit refused on `MAGNETIC_P1_MISMATCH`;
      and whether `write_topas_inp` refuses such a phase or writes it with
      the diagnostic in the header (#758 questions 1 and 3). **Settled
      2026-11-01 by Claude under the rule against a confident wrong answer**
      and the measured M1 misread (20 files whose `predict()` was off by
      0.5-32 % of the pattern maximum with no diagnostic): `verify=True` by
      default, the fit refused on `MAGNETIC_P1_MISMATCH`, and
      `write_topas_inp` refusing such a phase. The check's cost is not
      measured. Reopen this if V-a measures it as large against a fit.
- [x] **Decision (maintainer):** whether this WP joins the `magnetic`
      milestone. **Settled 2026-11-01 by Claude under ROADMAP rule 6:** it
      stays unscheduled. The milestone's scope names its seven WPs, and its
      acceptance rows were written at its opening. Adding a WP now would
      change a milestone's acceptance after the fact.
- [ ] I-a: the supercell refusal names its case; reads unchanged
- [ ] I-b: the parent record, read from `_parent_*`; `SCHEMA_VERSION` bump
- [ ] V-a: `validate_magnetic_phase` with `MAGNETIC_P1_MISMATCH`, at read and
      before `write_magnetic_block` and `write_topas_inp`
- [ ] I-c: a rational k ≠ 0 file read under tiers 2/3,
      `CIF_MAGNETIC_SUPERCELL_READ`
- [ ] V-b: the check at `Refinement.__init__`; `net_moment_per_cell` and
      `ferromagnetic_component_allowed` on `FitReport.magnetic`
- [ ] I-d: untabulated orientation, read in the file's axes through
      `Phase.parent_cell`, after PR #1108 merges. To build: read
      `_parent_space_group` (I-b), split the file's cell exactly into the
      parent cell plus a strain within `PARENT_CELL_DRIFT_TOL`, and set
      `parent_cell` where `_closest_type` is `None`. A file with no parent
      block falls back to the BNS standard group through the inverse of
      `transform_BNS_Pp_abc`, at zero strain (untested). Before ticking: a
      `slow` run over the reporter's MAGNDATA mirror counts how many of the
      91 read this way, and each read passes V-a's P1 check.
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

- **2026-11-03** (`/pr-review`) — the two review follow-ups of PR #1257 merged from outside as PR #1284 (`fd5c0bf5`). Every raw-text scan of a magCIF now skips the content of semicolon text fields. The four scans are `refuse_draft_tags`, `refuse_modulation`, the k reader `propagation_vectors` and `cif._magnetic_content`. So prose that quotes a tag no longer refuses a file, supplies a k, or sends a nuclear CIF to the magnetic reader. A k ≠ 0 stated only under the draft tag `_magnetic_propagation_vector_kxkykz` now reaches `refuse_a_magnetic_supercell`. The refusal names only the k tag the file used. No task of this WP is ticked by it. Follow-ups, not blocking: a commented-out k line (`# _parent_propagation_vector.kxkykz [1/2 0 0]`) still reads as a k, as it did on `main` before the PR. Text on a field's opening `;` line is not blanked, so a k there still reads. A loop that lists `kxkykz` before its id column reads no k. The draft reader's four-token fallback has no test. What ran, on the review's merge of head `06909a34` into `main` `62724a30` (Mac arm64, Python 3.12; the slow selection under `[dev,jax]`): fast 13 605 passed, 319 skipped, 34 xfailed, 1 failed; full `-m slow` 921 passed, 16 skipped, 17 xfailed, 1 failed in 46:36. The fast failure is `test_display`'s kernel row, whose Jupyter kernel spec points at a deleted venv on this Mac. The slow failure is `test_watch_app`'s GUI-boot socket timeout, which passed alone. Targeted magCIF rows 505 passed; ruff, the audit delta and the reader output were clean. The PR's later head `81fa6bb3` only merged `main` in.

- **2026-11-02** — the six decisions are recorded, so I-a, I-b and V-a can
  start. One was the maintainer's: the parent record is one nested `parent`
  record, migrated at read with no alias (by consent, 2026-11-01). Claude
  settled the other five. The 91 untabulated orientations keep the file's
  axes through PR #1108's `Phase.parent_cell`, on a practice survey the
  maintainer asked for. No surveyed program restates a magCIF on read, and
  the survey is now `docs/practice.md` § A magCIF in a non-standard
  orientation. The supercell refusal lifts after V-a. The two text faults
  are repaired by default and say so. `verify=True` is the default, and the
  WP stays unscheduled. Measured by a research agent on #1108's head
  `a8bcdd66` (synthetic, no MAGNDATA file): `metric.invariant_metric_basis`
  takes any rotation list. Two untabulated cases (8 operators of P6/mmm
  fixing a, and 8 of Pm-3m with two-folds on face diagonals) build a table
  and predict on #1108, and raise on `main`. A planted strain of 0.004 was
  recovered to 3e-11. A tie list cannot express the hexagonal case, since
  cos γ = −a/(2b) is nonlinear. Not covered: the magnetic layer and a real
  MAGNDATA file. Recorded in PR #1317. *Next:* I-a; I-d waits for #1108.

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

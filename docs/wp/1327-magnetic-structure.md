# WP-1327 — a magnetic structure: state it, refine it, report what the powder cannot see

Milestone: magnetic · Status: 🔄 2026-09-26 — the k = 0 moment (PR #433), the operation-list phase (PR #448) and k ≠ 0's magnetic supercell (PR #477) landed from outside; the analytic moment branch, the LaMnO₃ second dataset and the PNGs remain
Depends on: 1326 (the satellite reflection list)
Priority: P2 2026-09-23 — the open milestone's core; the moment and its hold start without 1326's list

## Goal

A moment can be stated on a site of a nuclear phase, under a magnetic
symmetry given as an explicit operator list, and refined against a
constant-wavelength neutron histogram with the nuclear model, sharing its
scale. The result reports moment magnitudes with esds, marks the direction
components a powder average cannot determine as unmeasured rather than
small, names the form-factor approximation in force, and holds a moment the
data does not support at zero instead of returning a confident number.

## Context

Second rung of the magnetic scattering track (ROADMAP § Unscheduled; the
un-fencing is recorded in DESIGN.md under *Scope discipline*). WP-1134
shipped the CW-neutron instrument this needs: `NeutronSource`
(`kind="neutron_cw"`), `crystallography/neutron.py`'s Sears table, and the
per-radiation species walk in `model/forward.py` (`compile_phase_sites`
resolves b on a neutron source and f₀ on an X-ray one). WP-1134 fenced
magnetic scattering as "a discussion to raise"; this WP is the discussion,
settled.

### The physics, restated because it decides the shape

- **The magnetic structure factor** for a reflection at Q (FullProf manual
  eqs 3.47–3.50, in the maintainer's corpus; Halpern & Johnson 1939 for the
  interaction vector):

  ```
  F_m(Q) = p · Σ_j occ_j · f_j(Q) · T_j · Σ_s ε_s·det(R_s)·R_s·m_j · exp(2πi Q·(R_s x_j + t_s))
  I_mag  ∝ |F_m|² − |Q̂·F_m|²          p = γ r₀ / 2 = 0.2695 × 10⁻¹² cm per μ_B
  ```

  where s runs over the magnetic operators, ε_s = ±1 is the operator's
  time-reversal sign, and det(R_s)·R_s is the action on an *axial* vector.
  Only the component of F_m perpendicular to Q scatters.

- **A moment is an axial vector, and the package's Rᵀ trap applies with a
  twist.** hkl transforms by Rᵀ, a tensor by R·U·Rᵀ, and a moment by
  det(R)·R with the time-reversal sign on top. The transposed set is a group
  too, so a dimension count passes in every crystal system with the wrong
  action; the guard is the one root CLAUDE.md gives for `adp_basis`: assert
  that a known allowed moment lies in the derived span, never how many
  directions the span has.

- **The powder cannot see every direction** (Shirane 1959). |F_⊥|² is not
  constant over the nuclear Laue orbit of Q, because the moment direction
  breaks the Laue symmetry, so "one representative times multiplicity" is
  wrong here and the structure factor returns the *orbit average*, the same
  shape `structure_factors_squared` already takes for the Friedel average
  under dispersion. After that average, a cubic collinear structure gives an
  intensity independent of the moment direction, and a uniaxial one measures
  only the angle to the unique axis. Those are flat directions of θ, and the
  package already has the rule for them: an equilibrated normal matrix, a
  gradient-free column named by `ParameterTable.unmeasured_rows`, an esd that
  is absent rather than zero. The design consequence is the parameterisation:
  refine a moment as modulus and angles in the allowed subspace
  (`atoms.j.moment.dof.k`, absolute like an ADP basis), so that an
  undeterminable direction is a *column* the rule can name; Cartesian
  components would put the flat direction along a rotation no column owns.

- **The form factor is the dipole approximation, and ⟨j₀⟩ alone is not it.**
  f(s) = ⟨j₀⟩(s) + (2/g − 1)·⟨j₂⟩(s), s = sinθ/λ, each ⟨jₙ⟩ an analytic
  three-Gaussian-plus-constant fit (Brown, ITC Vol. C § 4.4.5; ⟨j₂⟩ carries a
  factor s²). For a spin-only 3d ion g = 2 and the ⟨j₂⟩ term vanishes; for a
  rare earth it does not, which is why FullProf's table names Ho³⁺ twice
  (`MHO3` as ⟨j₀⟩, `JHO3` as ⟨j₀⟩ + c₂⟨j₂⟩; manual § form factors). The
  output names which form was used per species. A magnetic ion absent from
  the table is refused by name, never mapped to a neighbour (issue #202's
  rule on a new table). The coefficients are transcribed from ITC Vol. C with
  attribution, as the Rouse table was; not from GSAS-II (spec-only under its
  grant-back clause) and not from a file shipped inside a GPL distribution
  (McPhase's table travels with Dans_Diffraction; the numbers are Brown's,
  the file is not ours to copy).

- **One scale.** The nuclear and magnetic contributions of a phase share
  `Phase.scale`. A separate magnetic scale is the easiest way to a plausible
  fit and a wrong moment, and it is not offered.

- **The off state is zero, and it is flat.** |F_m|² ∝ m², so the moment's
  Jacobian column vanishes at m = 0: a moment seeded at zero cannot move, and
  a moment refined against a paramagnetic pattern collapses to its floor
  with the direction columns going flat as it does. That is WP-1301's shape
  (a phase the data cannot see is a flat direction, held for the stage,
  never bounded), applied to a moment block: hold every direction DOF while
  the modulus sits at its floor, release when it lifts, record the hold in
  `StageResult.held`, and report it. The null test below is the guard.

### The shape we chose, and what we rejected

**Chosen.** A moment is a site attribute (`Atom.moment`, opt-in like
`Atom.aniso`), stored as components along the crystal axes in μ_B (the
magCIF `_atom_site_moment.crystalaxis_*` convention) and refined through
derived DOFs. The phase's magnetic symmetry is an explicit operator list
(`Phase.magnetic_symmetry`: xyz strings with the time-reversal sign, plus
magnetic centrings), the magCIF `_space_group_symop_magn_operation.xyz` and
`_space_group_symop_magn_centering.xyz` form, with the BNS/OG symbol carried
as metadata and never resolved by rietx. A commensurate k ≠ 0 structure is
stated in its magnetic supercell with the parent's k recorded, which is what
the same file format does; the satellites of WP-1326 are then the
supercell's own reflections, so one reflection list serves the nuclear and
the magnetic contribution and one scale multiplies both. The cost is the
supercell's atom and reflection count (2× for a doubled axis), measured and
recorded at landing.

**Rejected.** (1) Resolving a Shubnikov symbol to operators inside rietx:
gemmi carries no magnetic groups (checked on 0.7.5), and every route a user
has to a magnetic structure (MAGNDATA, ISODISTORT, k-SUBGROUPSMAG, the
GSAS-II tutorials) already emits the operator list. (2) FullProf's separate
magnetic phase sharing the nuclear cell: it doubles the specimen's mass in
`phase_zmv` unless excluded by hand, needs two scale factors kept equal, and
PR #221 had to write a test around the consequence. A site attribute makes
the trap unreachable: `phase_zmv` reads species, occupancy and multiplicity
and never sees a moment. (3) A propagation vector plus basis vectors from
representation analysis: what an incommensurate structure needs and this
track fences; a user with basis vectors has an mcif from the same tool.

**Radiation.** The term enters a `neutron_cw` histogram only. On an X-ray
histogram of a joint fit it is identically zero, and a structure carrying a
moment refined against X-ray data alone gets a diagnostic saying the moment
was never observed (name fixed at landing, with its skill row).

**The derivative chain.** A moment DOF is a new derivative path. Under the
`_make_jacobian` gate it takes the whole-model FD column until a branch
claims it, which is correct and slow; the branch lands with the
`test_cross_backend.py` configs that cover it (root CLAUDE.md: the configs
grow whenever a derivative path does), and the traced twin in
`backend/traced.py` either carries the term or declines by name.

**Prior art, concepts only.** FullProf (Fourier components per k, a separate
magnetic phase), GSAS-II (magnetic space group in the BNS setting, moments
on the atoms of the same phase, the magnetic supercell for k ≠ 0), Jana2020
(magnetic superspace groups). `ATTRIBUTION.md`'s fences apply; the data-table
rule above applies to the form factors.

### Inherited

- **2026-10-02, from the issue triage (issue #612): `magnetic_supercell` cannot
  state the textbook MnO case (F m −3 m, k = ½½½).** *Checked at `ca9bda29`*
  with the reporter's script, output identical to the issue. Under
  `nuclear_group="parent"` all four candidates are refused with a message
  naming the parent's own group as the problem. Under
  `nuclear_group="magnetic"`, 167.108, 12.63 and 15.90 are refused with text
  about "the parent's space group" on the branch asked to use the magnetic
  group's nuclear part, and 2.7 ends in a raw pydantic
  `ValidationError: phase … has no atoms`. Mechanism of the last:
  `child_basis` returns the fractional basis `b+c, a/2+b/2+c, a/2+b+c/2` for
  the F-centred parent, and `lattice_cosets` returns `()` for it, so
  `_child_positions` is empty. Positive arm: P 4/m m m, k = (0,0,½) builds 7
  of 8 (candidate × `nuclear_group`) with no invariance violation, and 63.466
  under `"magnetic"` gets the same misleading text. The fix: `lattice_cosets`
  handles or refuses a fractional child basis of a centred parent, each
  branch's refusal names what that branch cannot do, and "no child positions"
  is refused by name before the `Phase` is built.

- **2026-09-29, from [1321](1321-persisted-bounds-repair.md): the supercell
  builder copies values only, so a parent's own stated range does not
  cross.** `crystallography/magnetic/supercell.py` builds the child phase
  from `Parameter(value=...)` for `scale`, each site's `occ`/`biso` and the
  cell. Since 1321 a `Parameter` leaving its bounds unset inherits its
  field's declared range, so the child scale is softplus from zero where it
  was an unbounded identity, which is a fix. But a caller's *own* range on
  the parent, such as `biso` `max=60` for a hot specimen (WP-1311's escape)
  or a scale they bounded, is still replaced by the declared default, and
  `vary` is dropped too. Carry the parent `Parameter` whole
  (`model_copy()`), or say why not, when the verb work next touches the builder.

- **2026-09-21, from the issue triage: #361, a multi-irrep *moment*
  statement has no primitive, and the intersection-group route is the wrong
  shape for it.** Checked against the tree at `4ee4e7f5`: the fork's
  `displacive_statement(components=…)` and `_sign_consistent_operations` are
  not on `main`, so the numbers are the fork's (Ba₂FeSbSe₅, 1.5 K,
  k = (½,0,½), 2026-09-17). Two b-axis irreps S2 and S3 each allow a dim-1
  moment per Fe; their coloured groups' intersection allows dim 3, an
  accidental lower group rather than the sum, and `magnetic_supercell` on it
  refuses on orbit coverage (4 members, 1 in the child). The ask, on this
  WP's `Atom.moment`: a `magnetic_supercell(components=[…])` (or
  `moment_statement`) that builds the common child from whole orbits, gives
  each magnetic atom the **direct sum** of the components' own per-site bases
  (one amplitude per irrep direction, never the intersection group's span),
  exposes the anti-translation so the magnetic child's asymmetric unit
  matches the displacive builder's (28 against 56 atoms today, so a combined
  displacive + moment model reaches 4 of 8 Fe), reports each component's
  amplitude with its own esd and determinability, and refuses incommensurate
  k by name (#258). The comment adds the cheaper route (b): in the distorted
  child, the parent's k = (½,0,½) is k = 0 of the 2a, b, a+c cell and
  S2 ⊕ S3 is one child irrep with two moment magnitudes, so a k = 0 moment
  statement on 1419's child, distortion and moments refined together, needs
  only the shared asymmetric unit, an operator-list parent for
  `candidates(kind="magnetic")`, and per-site moments with their
  determinability. Route (a) is this WP's primitive; (b) is a rung of 1419
  (its § Inherited carries the pointer). The control that precedes either
  on that dataset is 1343's anisotropic magnetic width (refined widths ≈ 1°
  against a 0.5° cluster span).
- **2026-09-02, from [1330](1330-skill-references-by-shape.md): a magnetic
  phase is a task *shape*, and the skill takes one reference file per
  shape.** What an agent must know to refine a moment model — the turn-on
  order for the magnetic parameters, what the powder cannot see, which
  diagnostics decide the deliverable — goes in one
  `docs/skill/rietx/references/` file (say `magnetic.md`), numbered under
  the body section it specialises (`2b` if it is an ordering rule, `3b` if
  a degeneracy, `4c` if a deliverable), never into `SKILL.md`, which takes
  only what holds for every fit. The file opens with the pinned
  three-paragraph header every reference carries (H1 with the section
  number, "Load it when …", the provenance line — copy `series.md`'s), and
  if its rows are written from runs it declares "Every row carries its
  evidence" and tags each row `(Measured: …)` or `(Hypothesis: …)`;
  `tests/test_skill.py` refuses either omission by name. Its routing row in
  the body's table is keyed by the situation ("the phase carries a
  moment", "satellites at G ± k", 1326's case) and costs ~200 B in a body
  with 36 B of headroom, so it is paid for by a cut named in the commit
  (root CLAUDE.md § skill). The engine's new diagnostic codes still go in
  `references/diagnostics.md`'s tables, where `test_docs_consistency.py`
  looks for them. The same holds for 1326, 1328 and 1329, which share the
  file rather than opening one each.

- **2026-09-08, from [1343](1343-the-moment-pays-for-the-width.md): keep the
  magnetic contribution separable inside `phase_peaks`.** 1343 draws the
  magnetic component with its *own* profile width — a phase whose magnetic
  order is coherent over a shorter length than its crystallites has broader
  magnetic peaks, and with one profile the fit reduces the residual under
  them by shrinking the moment instead (issue #277). That WP is an extension
  of this one if the magnetic |F_⊥|² arrives as its own array beside `f2`
  and stays separable through to the per-line `base`, and a rewrite of this
  WP's structure-factor path if it is folded into `f2` irreversibly. Every
  factor after that point — March-Dollase, extinction, Lp, specimen
  absorption, roughness — multiplies both contributions alike, so nothing
  else in the chain has to know. No field, no schema bump and no cost here:
  the ask is only that the sum happens as late as it can.

- **2026-09-15, from the issue triage (issues #256, #257, #278, #287, and
  PR #290): the operator layer landed, and five things it changes here.**

  **M-5 is on `main`** (PR #290, 2026-09-10, from the contributor;
  `crystallography/magnetic/operators.py`, 140 tests). It gives
  `MagneticOperator` (integer rotation, exact-`Fraction` translation, ε),
  `MagneticGroup` (coset representatives plus (anti)centrings, the two
  magCIF loops as the stored form) with `from_xyz`/`xyz()` round trips,
  `magnetic_group(spec, hall_number=…)` and `database_settings` over
  spglib's 1651 groups, `MagneticGroup.transformed` via
  `transform_BNS_Pp_abc` (lattice completion when |det P| ≠ 1),
  `identify()` from a bare operator list (1648 of 1651; three are a spglib
  defect), and `allowed_moment_basis`/`in_span` with the
  `moment_to_cartesian`/`moment_from_cartesian`/`moment_magnitude`
  conversions in magCIF crystal-axis components. Twenty published moments
  assert span, never dimension. So task 1's stored form has its parser and
  printer, and task 2's subspace exists and is wired to nothing. § "The
  shape we chose" rejected alternative (1) on "gemmi carries no magnetic
  groups". Still true of gemmi, and it no longer decides anything: a
  UNI/BNS/OG **number** resolves through spglib and a symbol **string** is
  refused by name. Rewrite that paragraph from the code before quoting it.
  #257 A4 is thereby done. A6(i), the moment basis, has its conversions,
  and the MAGNDATA round trip is the test still to write.

  **#257's other amendments.** A5: the ⟨j₀⟩/⟨j₂⟩ table needs a cross-check
  source; the `periodictable` package carries Brown's coefficients under a
  public-domain notice (licence to verify before use) and can be the
  independent transcription check the Rouse table never had; a table with
  ⟨j₀⟩ for 4f ions and no ⟨j₂⟩ silently enforces g = 2 on a rare earth.
  A6(ii)/(iii): pin the e^{−2πi k·a_g} phase and p = 2.695 fm (with
  `b_Sears.dat` in fm) by round trip, one unit test each. A7: `Magnetic-III`
  (Ba₆Co₆-type cobaltite, D1B) and `Magnetic-IV` (Pr₀.₅Sr₀.₅MnO₃, 3T2) are
  the first public k ≠ 0 commensurate candidates, k to confirm from the
  tutorial pages first. A8: the first non-goal ("determining a magnetic
  structure … ISODISTORT's job") is asked to read as sequencing; the
  decision sits in [1418](1418-the-magnetic-structure-is-determined.md),
  which the triage opened as a candidate.

  **#278 — the magnetic reflections as their own tick row.** Every plot
  draws one tick row per phase, so a phase with a moment would draw
  satellites and parent-forbidden lines on the nuclear row.
  `HistogramResult.ticks` is `dict[str, list[float]]`
  (`schemas/results.py`), so the ask is a second key,
  `"<phase> (magnetic)"`, with its own palette slot, offset and legend
  entry, mixed reflections marked, and the same split in the plotly builder
  and the live view. Owned by this WP's report task. `MomentEvidence`,
  which the issue says knows which reflections are magnetic, does not exist
  on `main`.

  **#287's ruling (2026-09-09) supersedes the 2026-09-02 entry above on one
  point.** The engine's magnetic diagnostic codes do **not** go in
  `references/diagnostics.md`'s tables. That file is at 35 980 B of 36 000
  on this tree, and the ruling puts the whole family (1326–1329 and 1343)
  in one gated `references/magnetic.md`, numbered `2b` under the turn-on
  order, carrying the codes *and* the strategy and the traps, reachable
  from § 7 by a one-line pointer. Whatever in `tests/test_docs_consistency.py`
  or `tests/test_skill.py` looks for a code's row in `diagnostics.md` alone
  has to learn the second file (1338's gates). `DISTORTION_MODE_UNSUPPORTED`
  (1419) stays a § 7 row.

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
  carries the rule that keeps it free. The same note is in 1326, 1328, 1329 and 1418.

## Non-goals

- Determining a magnetic structure: representation analysis, k-SUBGROUPSMAG,
  ISODISTORT's job. This WP refines a structure the user states.
- Incommensurate and modulated structures (superspace; with 1314's fence).
- Time-of-flight (a bank spans a range of λ; 1134's fence stands), polarised
  neutrons, single-crystal data, and magnetic X-ray scattering.
- Terms beyond the dipole approximation (⟨j₄⟩, orbital contributions beyond
  the (2/g − 1) factor).
- Reading or writing magCIF and the foreign readers' refusals: WP-1328.
- The moment along a temperature series: WP-1329.

## Tasks

- [x] The schema: `Atom.moment` (crystal-axis components, μ_B) and
      `Phase.magnetic_symmetry` (operator strings with ε, centrings, the
      symbol as metadata); refused together with `propagation_vector`
      (1326); `SCHEMA_VERSION` bump with its one-sentence comment.
      **PR #433 (`14239188`), `SCHEMA_VERSION` 0.28. The refusal with
      `propagation_vector` is `refuse_moment_model_with_k`, written and
      tested, with no caller until 1326's field exists.**
- [x] Moment DOFs from the operators: the allowed subspace per site from the
      axial action with ε, in `crystallography/wyckoff.py`'s style, wired
      as `atoms.j.moment.dof.k` (modulus and angles in the subspace); the
      span test above, on a published structure's known moment. **Spelled
      `atoms.j.moment.dofK` (`dof0` the signed modulus); twenty published
      moments lie in the derived span.**
- [x] The form-factor table: ⟨j₀⟩ and ⟨j₂⟩ coefficients transcribed from
      ITC Vol. C with the `ATTRIBUTION.md` row, keyed by magnetic ion, refusal
      by name for an absent ion, the g-factor input, and the approximation
      named in the output. **From the public-domain `periodictable` table
      (Brown's coefficients), with `ATTRIBUTION.md` rows; the GPL
      transcriptions were deliberately not copied.**
- [x] The magnetic structure factor: the orbit average of |F_⊥|², p, the
      shared scale, the neutron-only dispatch, the per-stage freeze of
      operators and form factors beside `PhaseSites.f_anom`.
- [x] The flat-direction hold: `moving_paths` and `StageResult.held` for a
      moment block at its floor, re-measured at the answer as 1301 does.
- [ ] The Jacobian: FD first, then the analytic branch with its
      `_column_extras` reach declared, cross-backend rows, the traced twin.
      **FD and the cross-backend `magnetic` row landed. A magnetic phase's
      structural columns take the peak-chain FD column by declared
      exclusion (`structural_grad_supported`), and the traced backends
      decline it by name. No analytic moment branch yet.**
- [x] The report: moment magnitudes and esds in the parameter table, the
      unmeasured direction named, the approximation named, the hold named;
      QPA untouched, asserted.
- [x] Manual Part 2 (the structure factor, the perpendicular projection, the
      dipole form factor, each with its *Source* line), Part 1 chapter, skill
      rows, `help.py` entries, `capabilities()` feature flag.
- [ ] Tests, including the acceptance below, with obs/calc/diff PNGs to
      `tests/output/`. **Cr₂WO₆ 4 K and the 150 K null ship
      (`test_acceptance_magnetic.py`). LaMnO₃ is not vendored (its licence
      is checked, 2026-10-03: `Magnetic-I/data/LaMnO3_50k.gsas` and
      `BT1_Cu311.inst` sit under the GSAS-II-tutorials `LICENSE`, the GSAS-II
      Open Source License the `gsas2_*.gpx` fixtures already ship under), and no
      magnetic refinement writes a PNG.**

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magnetic.py tests/test_cross_backend.py -q
.venv/bin/python -m ruff check src tests examples
```

- Cr₂WO₆ at 4 K (HB-2A, λ = 2.4067 Å, vendored by 1326) under P4₂/mnm with
  k = 0: the Cr moment lands within the esd of the GSAS-II tutorial's
  2.35(2) μ_B, nuclear and magnetic sharing one scale.
- LaMnO₃ at 50 K (BT-1, NIST, GSAS-II `Magnetic-I`; licence checked per file
  before vendoring) under Pnma with k = 0, the second dataset.
- **The null test.** The same model refined against Cr₂WO₆ at 150 K, above
  its ordering temperature, reports the moment held at its floor and
  unsupported, not a small number with a small esd.
- A cubic collinear test structure: the orbit-averaged intensity is
  independent of the moment direction to fp64, and the direction DOFs come
  back in `unmeasured_rows` with no esd.
- `qpa.weight_fractions` on a two-phase fixture is bit-identical with and
  without a moment block on one phase.
- Every number a shipped fixture pins is bit-identical with no moment
  declared.

## References

- Halpern, O. & Johnson, M. H. (1939). *Phys. Rev.* **55**, 898 — the
  magnetic interaction vector.
- Shirane, G. (1959). *Acta Cryst.* **12**, 282 — what a powder average
  determines of a moment direction.
- Brown, P. J. *International Tables for Crystallography* Vol. C, § 4.4.5 —
  magnetic form factors, the ⟨jₙ⟩ coefficients. *In the maintainer's
  library since 2026-10-03* (Prince ed., 3rd ed., 2004): Tables
  4.4.5.1-4.4.5.14, ⟨j₀⟩ to ⟨j₆⟩, read by `pdftotext` cleanly enough to
  cross-check A5's table against.
- Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual (in the corpus) has eqs 3.47–3.54 and the form-factor conventions.
- Perez-Mato, J. M. et al. (2015). *Annu. Rev. Mater. Res.* **45**, 217 —
  magnetic symmetry and the BNS/OG settings. Gallego, S. V. et al. (2016).
  *J. Appl. Cryst.* **49**, 1750 — MAGNDATA. *Both in the maintainer's
  library since 2026-10-03.*
- COMCIFS `magnetic_dic` (`cif_mag.dic`, tags checked 2026-09-02) — the
  operator, centring, moment and propagation-vector tags this WP's stored
  form mirrors.
- [1326](1326-satellites-without-a-moment.md), [1328](1328-magnetic-interchange.md),
  [1329](1329-moment-in-a-series.md); [1301](1301-hold-unsupported-phase.md)
  the hold rule; [1134](1134-constant-wavelength-neutron.md) the instrument;
  [1312](1312-neutron-followthrough.md) the joint-fit audit this term joins.

## Handover log

### 2026-10-03 — three references found and LaMnO₃'s licence checked, by a cleanup session

Nothing this WP needs is still with the maintainer. The three references it
marked "ask" are in the maintainer's library, and the second dataset's
licence allows vendoring it.

*Done* (WP-file edits only): *International Tables* Vol. C § 4.4.5 (Tables
4.4.5.1-14, the ⟨jₙ⟩ coefficients A5's cross-check needs), Perez-Mato et al.
(2015) and Gallego et al. (2016) recorded as held. `Magnetic-I/data/
LaMnO3_50k.gsas` and `BT1_Cu311.inst` sit under the GSAS-II-tutorials
`LICENSE`, the one the `gsas2_*.gpx` fixtures ship under. *Next:* vendor
LaMnO₃ and add it to the acceptance, then the analytic moment branch.

### 2026-09-26 — k ≠ 0's magnetic supercell landed from outside

A commensurate k ≠ 0 magnetic structure can now be stated. As magCIF does, it
is stated in its magnetic supercell, with the parent's k recorded beside it.
The satellites are then the child cell's own reflections, and one scale covers
the nuclear and magnetic parts, as § "The shape we chose" asks. It arrived as
the contributor's PR #477, split out of #433 at the first review, parked
until #433 and #448 landed, and reviewed over two rounds. No task line ticks: the
tasks track the k = 0 moment, and this is the k ≠ 0 route the design section
describes.

- *Done*: PR #477, merged as `63e2a8c4`.
  `crystallography.magnetic.supercell.magnetic_supercell` returns a
  `SupercellStatement`: the child `Phase`, the transform,
  `child_group_named` and the statement's own diagnostics. There are two ways
  in.
  - A candidate from `isotropy.candidates`, which inherits that function's
    2k ∈ L* fence.
  - An explicit group with its `transform_BNS_Pp_abc` transform, which works
    for any commensurate k. The docstring's case is Mn₃O₄: I4₁/amd at
    k = (0, ½, 0), which `candidates` refuses.

  `nuclear_group` chooses what the child's `space_group` states: `"parent"`
  (the parent's group carried through the transform) or `"magnetic"` (the
  magnetic group with ε dropped).
  - **An unnamed child is an operation list.** Where no Hermann-Mauguin symbol
    generates the child's nuclear group in the child cell, the child is #448's
    operation-list phase under a bracketed label, with an info
    `CHILD_GROUP_UNNAMED`. The usual cause is a parent half translation along
    the doubled axis, which becomes a quarter in the child. The diagnostic's
    `where` is `space_group`, relative to the returned phase, because the
    statement cannot know its phase's index.
  - **The anti-centring ties are part of the statement.**
    `anti_translation_ties` gives the affine ties for `Refinement.tie`, and
    `anti_translation_residual` measures how far a refinement has left the
    declared group. Without the ties, the two cosets of a parent site are
    independent columns, and their ferromagnetic combination is free. Both
    cite Gallego et al. (2012) eq. (3).
  - **The parent's k is provenance.** `MagneticSymmetry.propagation_vector_parent`
    records it. Only `magnetic_supercell` writes it, and it never generates
    a reflection: a k beside a moment model is still refused by
    `refuse_moment_model_with_k`. `SCHEMA_VERSION` is 0.31.
- *Not done*:
  - A MAGNDATA k ≠ 0 round trip and real-data k ≠ 0 acceptance. `Magnetic-III`
    and `Magnetic-IV` (#257 A7) are the public candidates, with k unconfirmed.
    Every fixture in the PR is synthetic.
  - `magnetic_supercell(components=[…])` for a multi-irrep moment.
  - The GUI's `symmetryLine` closest-type wording, carried from #448.
  - The task list's own open lines: the analytic moment branch, LaMnO₃ and
    the PNGs.
- *Gotchas found in review*: round one found two bugs, and both are fixed with
  tests. I mutation-checked both: restoring the old line fails its tests.
  - **The origin shift was applied in the wrong frame.** With an origin shift
    on the explicit route, the child's group sat at a different origin from
    its atoms. `MagneticGroup.transformed((Q, q))` realises x′ = Q·x + q,
    and the atoms sit at P⁻¹·(x − p), so q is −P⁻¹·p, not p. The error is
    (I − W′)·(p + P⁻¹·p), which is a lattice vector for some shifts and
    not for others. So `1/2,0,0` on P4/mmm built, while `0,0,1/4` was
    refused as "not a whole orbit". A shift that puts translations off gemmi's
    1/24 grid is now refused by name.
  - **The seed was normalised in the wrong metric.** `tilted_seed` received a
    unit cubic cell, so an oblique child's seed had the wrong modulus: 2.324
    μ_B for `magnitude=3` on a hexagonal child. The child's own cell now goes
    through.
  - **Docstrings cited code that exists only on the contributor's fork.**
    They named fork-only functions, files and tracking labels, and all of them
    are restated in terms of `main`. `child_basis`'s alternate-basis chooser
    went with them, because its oracle was fork-only.
    - Against `main`'s `cell_constraints` it never switched a basis: 639
      (group, k) pairs in the contributor's sweep.
    - Where it would have switched, the child is now refused by
      `_unnamed_child` rather than restated in another primitive cell of the
      same lattice.
- *Measured on the merged tree* (`main` `b16772f0` + #477, a fast-forward;
  Linux x86_64, python 3.12.3, `[dev,jax]`, 4 cores, run as root, nothing
  else running):
  - ruff clean.
  - Fast suite: 6235 passed, 106 skipped, 1 failed, 21:00. The failure is
    `test_telemetry`'s unwritable-directory case, which cannot hold as root.
    passed + skipped + failed matches the contributor's 6342.
  - Full `-m slow`: 226 passed, 14 skipped, 2 failed, 1:27:20. Neither
    failure is the PR's.
    - The ramp runaway guard in `test_held_phase` (154 s against 60 s under
      `-n auto`) passes when run alone.
    - Brucite's strict xfail passed. It is red on `main`'s nightly of
      2026-09-25 too, and xfails when run alone.
  - CI's fast jobs and lint were green.
- *Next*: #468 (WP-1326's satellites) conflicts with this merge in six files
  and renumbers to `SCHEMA_VERSION` 0.32. After it come the analytic moment
  branch, LaMnO₃ once its licence is checked, and the acceptance PNGs.

### 2026-09-25 — the operation-list phase landed from outside

A phase can now carry its own list of symmetry operations. It is for a group
that no Hermann-Mauguin symbol names in its cell, as when a doubled cell turns
a glide's half translation into a quarter. A k ≠ 0 magnetic supercell needs
it. It arrived as the contributor's PR #448, which the first review round
of PR #433 split out, and was reviewed over two rounds. No task line ticks,
because the tasks track the k = 0 moment and this is k ≠ 0's prerequisite.

- *Done*: PR #448, merged as `48118bb6`. `Phase.symmetry_operations` holds
  the list, and `SCHEMA_VERSION` is 0.30. With a list present, `space_group`
  is a label. A bracketed label (`"Pm [unnamed in 2a,b,a+c]"`) requires the
  list, and a plain symbol must generate it exactly. Every symmetry consumer
  reads `resolve_group(phase.space_group, phase.symmetry_operations)`. A phase
  with no list takes the old path bit for bit, on the numpy and compiled paths
  both. Three facts change how anyone builds on it. A structure CIF writes the
  list as a symop loop, and `structure_from_cif` reads it back only beside a
  bracketed label. The GSAS, GSAS-II, TOPAS and FullProf writers refuse such a
  phase by name (`symmetry.refuse_operation_list`), because each format states
  a group only as a symbol. And the GUI's facts for such a phase quote the
  closest type's `number`. They give `None` for `hall`, `symmorphic`,
  `enantiomorphic` and `reference_setting`, which depend on translations the
  closest type does not have.
- *Not done*: `magnetic_supercell` builds this kind of phase for a k ≠ 0
  structure. It is on the contributor's `pr/wp1327c-magnetic-supercell`
  branch, with `MagneticSymmetry.propagation_vector_parent`, the supercell
  tick-row case and the `CHILD_GROUP_UNNAMED` row. That PR opens next, rebased
  onto `main`.
- *Gotchas found in review*: round one found three readers that still
  resolved the label instead of the list. `merge_magnetic` dropped the list,
  so `report()` raised on any moment on such a phase. The GUI's facts showed
  an error row beside working sites, and its preview compared against no
  orbits, so an orbit collision went uncaught. A structure CIF wrote the label
  with no operations, and no reader could expand it. Fixing the GUI exposed a
  fourth: `with_symbol` kept the list, so the validator refused every typed
  symbol but the list's own. All four are fixed in the PR with tests. The
  `Phase` closure check is now cached per list, because `validate_assignment`
  reran it on every field write. The contributor measured 35-37 ms a write on
  `F d -3 m:2`'s 192 operations before and 2-3 µs after.
- *Measured on the merged tree* (`main` `bbc2ef9d` + #448; darwin/arm64,
  python 3.12, `[dev,jax]`, nothing else running): ruff clean, and the fast
  suite 6196 passed, 91 skipped. The Sphinx `-W` build was clean. Full
  `-m slow`: 226 passed, 9 skipped, 1 xfailed. On the tree before #467 and
  #469 merged, the fast count was `main`'s plus 58, which is this PR's fast
  ids. CI's py3.11 job was first cancelled by the old 20-minute guard, and it
  passed on a rerun in 16 minutes.
- *Next*: the supercell PR. It also makes `symmetry.OperatorGroup`'s
  docstring true, since that names `magnetic.supercell.resolve_child_group`.
  The GUI panel's `symmetryLine` still prints `No. 123` for an operation-list
  phase, where the `.rxt` line says "closest type No. 123". That fix is a
  client change and a dist rebuild. After those come the analytic moment
  branch, LaMnO₃ once its licence is checked, and the acceptance PNGs.

### 2026-09-24 — the k = 0 moment landed from outside

rietx can now refine a magnetic structure. A moment is stated on a site of
a nuclear phase, under a magnetic space group given as its operator list,
and refined against a constant-wavelength neutron pattern with the phase's
one scale. The report says what the powder cannot see: a direction it is
blind to comes back held and unmeasured, and a moment within three of its
own esds comes back unsupported rather than small. It arrived as the
contributor's PR #433, reviewed over two rounds. The first round split the
k ≠ 0 supercell and the operation-list phase out to their own PRs, and asked
for the real-data acceptance to ship. Seven of nine tasks are ticked.

- *Done*: PR #433, merged as `14239188`. The Tasks above say which landed
  and how. Three facts change how anyone builds on it. `SCHEMA_VERSION` is
  0.28 on `main`, and the maintainer's open #446 also claims 0.28, so it
  renumbers. `RadiationCapability.magnetic_scattering` is derived from
  `scattering.MAGNETIC_SOURCE_KINDS`, the table `magnetic_wanted` dispatches
  on. `MomentEvidence.supported` is `bool | None`, with `None` where the
  modulus has no esd.
- *Acceptance, against this file's text*: the Cr₂WO₆ pair ships verbatim
  from GSAS-II-tutorials `924e9eb8`, SHA-256 checked against upstream. The
  suite starts from ideal trirutile positions, because the tutorial's CIF is
  an ICSD entry. **The 2.35(2) μ_B bar is not met by either code**: current
  GSAS-II on the tutorial's own steps gives 2.121 ± 0.019, and the shipped
  protocol gives 2.12 ± 0.06. So `test_acceptance_magnetic.py` asserts a
  1.9-2.3 envelope, a ratio above 10 and alignment along a. **The null is
  met by the ratio rule, not by the floor**: 0.067 ± 1.02 μ_B, `supported`
  False, Rwp unmoved to 1e-3. The WP text says "held at its floor". The
  shipped value stays off the floor, and the `MomentEvidence` docstring
  explains why the ratio is the honest test. LaMnO₃ (3.54 ± 0.33 μ_B
  against about 3.7 published) was run read-and-test and is not vendored.
  The cubic-collinear, QPA and no-moment bit-identity items ship as tests.
- *Gotchas found in review*: `magnetic_reflections` had skipped the
  parent's centring along with the glides. It now applies each centring
  unless the magnetic group carries it as an anti-centring (BNS type IV). A
  moment DOF the phase hold took was released by the direction probe, which
  skips `dof0`, so a still-invisible phase's modulus walked (2.12 → −1.73 μ_B
  on the fixture). The paired esd was built from |dof0| and flipped its
  cross term for antiparallel sites.
- *Measured on the merged tree* (`main` + #425 + #438 + #433, the tree this
  merge produced; Linux x86_64, `[dev,jax]`, 4 cores): fast suite 1 failed,
  6067 passed, 101 skipped, which is +117 passed and +5 skipped from this PR.
  The failure is `test_telemetry`'s root-only case. GUI vitest gave 594
  passed, svelte-check was clean, and the dist was byte-identical. Full
  `-m slow`: 2 failed, 193 passed, 9 skipped, with every magnetic slow file
  passing. Both failures were load (WP-1415's entry of this date).
- *Next*: the contributor's two follow-on branches, the operation-list phase
  with the CIF exporter's `resolve_group` fix, then `magnetic_supercell` on
  top of both. Either can make `symmetry.OperatorGroup`'s docstring true
  again, since it names two functions `main` does not have (already so
  before this PR). After those: the analytic moment branch, LaMnO₃ once its
  licence is checked, and the acceptance PNGs. WP-1458 (a null group's
  zero-intensity ticks quieting `LOW_ANGLE_UNMODELLED`) was filed in review.

- **2026-09-02** — created, from the assessment of PR #221. That proposal
  left two decisions open, the stated form and the QPA exclusion; both are
  taken here with the rejected alternatives recorded, and the dataset the
  proposal did not name is the GSAS-II tutorial data whose provenance the
  package already vendors. No code touched. First task is the schema.

# WP-1327 — a magnetic structure: state it, refine it, report what the powder cannot see

Milestone: unscheduled · Status: ⬜
Depends on: 1326 (the satellite reflection list)

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

- [ ] The schema: `Atom.moment` (crystal-axis components, μ_B) and
      `Phase.magnetic_symmetry` (operator strings with ε, centrings, the
      symbol as metadata); refused together with `propagation_vector`
      (1326); `SCHEMA_VERSION` bump with its one-sentence comment.
- [ ] Moment DOFs from the operators: the allowed subspace per site from the
      axial action with ε, in `crystallography/wyckoff.py`'s style, wired
      as `atoms.j.moment.dof.k` (modulus and angles in the subspace); the
      span test above, on a published structure's known moment.
- [ ] The form-factor table: ⟨j₀⟩ and ⟨j₂⟩ coefficients transcribed from
      ITC Vol. C with the `ATTRIBUTION.md` row, keyed by magnetic ion, refusal
      by name for an absent ion, the g-factor input, and the approximation
      named in the output.
- [ ] The magnetic structure factor: the orbit average of |F_⊥|², p, the
      shared scale, the neutron-only dispatch, the per-stage freeze of
      operators and form factors beside `PhaseSites.f_anom`.
- [ ] The flat-direction hold: `moving_paths` and `StageResult.held` for a
      moment block at its floor, re-measured at the answer as 1301 does.
- [ ] The Jacobian: FD first, then the analytic branch with its
      `_column_extras` reach declared, cross-backend rows, the traced twin.
- [ ] The report: moment magnitudes and esds in the parameter table, the
      unmeasured direction named, the approximation named, the hold named;
      QPA untouched, asserted.
- [ ] Manual Part 2 (the structure factor, the perpendicular projection, the
      dipole form factor, each with its *Source* line), Part 1 chapter, skill
      rows, `help.py` entries, `capabilities()` feature flag.
- [ ] Tests, including the acceptance below, with obs/calc/diff PNGs to
      `tests/output/`.

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
  magnetic form factors, the ⟨jₙ⟩ coefficients. **Not in the corpus; ask.**
- Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual (in the corpus) has eqs 3.47–3.54 and the form-factor conventions.
- Perez-Mato, J. M. et al. (2015). *Annu. Rev. Mater. Res.* **45**, 217 —
  magnetic symmetry and the BNS/OG settings. Gallego, S. V. et al. (2016).
  *J. Appl. Cryst.* **49**, 1750 — MAGNDATA. **Neither in the corpus.**
- COMCIFS `magnetic_dic` (`cif_mag.dic`, tags checked 2026-09-02) — the
  operator, centring, moment and propagation-vector tags this WP's stored
  form mirrors.
- [1326](1326-satellites-without-a-moment.md), [1328](1328-magnetic-interchange.md),
  [1329](1329-moment-in-a-series.md); [1301](1301-hold-unsupported-phase.md)
  the hold rule; [1134](1134-constant-wavelength-neutron.md) the instrument;
  [1312](1312-neutron-followthrough.md) the joint-fit audit this term joins.

## Handover log

- **2026-09-02** — created, from the assessment of PR #221. That proposal
  left two decisions open, the stated form and the QPA exclusion; both are
  taken here with the rejected alternatives recorded, and the dataset the
  proposal did not name is the GSAS-II tutorial data whose provenance the
  package already vendors. No code touched. First task is the schema.

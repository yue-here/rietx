# WP-2061 — a crystallite has a shape: hkl-dependent size broadening on the analytical profile

Milestone: unscheduled · Status: ⬜
Track: The specimen is not an angle, and the neutron follow-through
Depends on: — (WP-1343 soft, for the magnetic task only)
Priority: P3 2026-10-26 — a feature no open milestone was opened for, with one named user asking; no wrong number today, only a misfit the isotropic model cannot absorb

## Goal

A phase can carry a size broadening that depends on hkl, in two declared forms, both off by default: a Laue-class-adapted size harmonic series (crystallite shape, uniaxial as its two-coefficient case) and a size term confined to a declared family of reflections. Each has an exact isotropic limit, and the microstructure report gives a size per direction with esds.

## Context

**Where it came from.** Issue #1065 (2026-10-20, an outside contributor), which proposes four chunks AS-1 to AS-4. This WP carries AS-1 to AS-3. AS-4 (the same terms on a TOF bank) waits behind the TOF fence (ROADMAP § v2+, #193).

**What exists.** Size broadening is isotropic per phase: `Phase.lor_size` and `gauss_size`, with WP-1131's per-histogram λ factor (`params.multi.SIZE_LAMBDA_POWER`), and WP-1343's `magnetic_lor_size`/`magnetic_lor_strain` for the magnetic part. Anisotropic broadening exists for strain only: Stephens (1999), WP-0503, `Phase.microstrain`, `crystallography/stephens.py`. Three WPs fenced anisotropic size out:

- WP-0503 non-goals (line 209): anisotropic size, "the 1/cosθ counterpart, e.g. ellipsoidal or spherical-harmonics domain shape … different WP".
- WP-1131 non-goals (lines 260-261): "an anisotropic size model is a new physics seam and belongs with FPA at v2+". The ROADMAP's § v2+ list does not name it, so the fence was a sentence in a closed WP only.
- WP-1343 non-goals (line 323): anisotropic magnetic broadening, "only when the isotropic pair has shown what it recovers".

WP-1946's non-goals note that brucite's platelets "may carry" anisotropic size instead of the Stephens strain that WP fits. That is a live case where the two mechanisms compete.

**Practice (read 2026-10-26).** All three programs carry anisotropic size on the analytical profile, without fundamental parameters.

- GSAS-II 5.8.4: `SizeType` is `isotropic`, `uniaxial` or ellipsoidal (`GSASIIstrMath.py:3237-3249`). The uniaxial width is (1.8λ/π)/(Size;i·Size;a·cosθ)·√((sinφ·Size;a)² + (cosφ·Size;i)²), with φ the angle between H and the axis. The ellipsoidal one is 1.8λ/(π cosθ · `ellipseSize(H, Sij)`) over six coefficients. Read from the installed source.
- FullProf (manual on disk, `FullProf_Manual.pdf`): size as spherical harmonics, Lorentzian, with Järvinen's normalisation; platelets and needles as `IsizeModel = ±1`; selective size broadening for anti-phase domains and stacking faults, by a rule on the indices. Read from the manual.
- TOPAS: any width may be an expression in H, K, L, and `spherical_harmonics_hkl` supplies the symmetrised harmonics (Technical Reference, as the issue cites it; not read this session).
- Literature: Popa (1998) gives the hkl dependence of size and strain for every Laue group; Järvinen (1993) the harmonic normalisation.

So the seam does not need FPA. FPA would change how a size convolves, not which reflections it broadens.

**The shape to copy.** WP-0503's Stephens block is the template one rank over: a subspace derived from the operators rather than tabulated (`crystallography/stephens.py`, `wyckoff._nullspace_int`), absolute DOFs, an out-of-subspace set refused, an isotropic seed, and a lock on the isotropic parameter whose direction the block contains (`lor_strain` there, `lor_size` here). The Stephens rules in root CLAUDE.md apply in kind: the width must stay non-negative in every direction, and that couples all coefficients, so it is a guard or an LM linear inequality, never a box bound.

**Seams to extend.** `schemas/structure.py` (`Phase`), `params/vector.py` (`_collect_microstrain`'s neighbour, and the lock), `model/forward.py` and `profiles/` (the Lorentzian FWHM sum), `model/microstructure.py` (a size per direction with esds), `params/multi.py` (`SIZE_LAMBDA_POWER` gains the new rows, since a size coefficient goes as λ), `help.py`, `capabilities()` features, `tests/test_cross_backend.py` configs (a new derivative path), the manual's Theory tab (each equation with its *Source* line), and `viz/compare.py` with `tests/test_compare_ui.py` (a new correction adds its row).

**Tier.** Every term is declared by the caller and off by default, so nothing decides for the user. No `suggestion=` points at it from a residual statistic: strain, preferred orientation and stacking faults are competing explanations of an hkl-dependent width, and a powder pattern often cannot rank them. The one new diagnostic is a size sum that goes negative in some direction, the analogue of `STEPHENS_STRAIN_NOT_POSITIVE`. A negative width is unphysical, so it is tier 1 with its `_audit` row. The harmonic subspace is physics (Popa 1998); the selective rule is named practice (FullProf's selective broadening, TOPAS's hkl conditions).

**Reference before code.** The isotropic control is the ceria size-strain round robin (Balzar et al. 2004, CC BY). No published anisotropic-size refinement with data rietx may hold is known yet. Until one is found the harmonic and family terms ship "not yet validated", with GSAS-II as a black-box oracle on a synthetic uniaxial pattern (the two parameterisations meet on the uniaxial case). The FullProf manual's selective example (Önnerud et al. 1997, Pd₃MnD₀.₈) is the candidate for the family term if its data can be held.

**Licensing.** GSAS-II source may be read for the concept and as an oracle; FullProf and TOPAS by manual and paper only.

### Inherited

- 2026-10-31, from the issue triage (issue #1065): the reporter (2026-10-28)
  answered the issue's questions 1 and 2 for this WP's first task. Question 1
  (leaving WP-1131's "with FPA at v2+") is settled by this WP's placement, and
  they agree. Question 2 (the schema shape), their view: a separate
  `Phase.size_harmonics` beside `Phase.microstrain`, and AS-2 as a third field
  `Phase.size_families`, rather than one microstructure block. Their reasons:
  `microstrain` appears in 34 files under `src/` and 70 with `tests/` (the
  GSAS-II, TOPAS and FullProf project readers and writers, `io/recipe.py`,
  `params/vector.py`, the GUI, `help.py`), so a block would migrate a landed
  field and every saved project and recipe path naming it;
  `model/microstructure.py` already joins size and strain in the report;
  GSAS-II (`Size`/`Mustrain`), FullProf (separate model codes) and TOPAS
  (`CS_L`/`Strain_L`) keep size and strain apart, so an exporter maps field to
  field. The cost they name: the `lor_size` lock and the non-negativity guard
  are written across two fields, as WP-0503 already does for Stephens.
  Question 3: no public anisotropic-size dataset found by them either. Checked
  against the tree at d87c8cc91: no landing on this subject since 2026-10-26.
  The schema shape stays the maintainer's decision (this WP's task "Decide the
  schema shape with the maintainer"); a block would be a stored-format change.

## Non-goals

- AS-4, the terms on a TOF bank: behind the TOF fence (ROADMAP § v2+, #193; T-2/T-3).
- A free expression language for widths (TOPAS-style). A rule is a declared integer condition on hkl, checked against the reflection list and refused by name when it selects nothing or everything.
- Anisotropic Gaussian size, unless the harmonic task finds a reference that needs it. GSAS-II's and FullProf's anisotropic size is Lorentzian.
- Any automatic choice between anisotropic size and Stephens strain.

## Tasks

- [ ] Decide the schema shape with the maintainer: `Phase.size_harmonics` beside `Phase.microstrain`, or one microstructure block holding both (issue #1065, question 2).
- [ ] Laue-class size harmonics (AS-1): the subspace derived per Laue class (Popa 1998), Lorentzian, Scherrer 1/cosθ law; isotropic seed and the `lor_size` lock; uniaxial as the documented two-coefficient case; the non-negativity guard (or LM inequality) and its `_audit` row; `SIZE_LAMBDA_POWER` rows.
- [ ] The harmonics' derivatives: FD first, the analytic branch with its declared reach, a `test_cross_backend.py` config, the traced twin.
- [ ] Selective family size (AS-2): a declared integer rule on hkl, or "the magnetic reflections of k", each with its own Lorentzian size; refused by name when it selects no reflection or every one.
- [ ] Anisotropic magnetic width (AS-3): the harmonics and families on the magnetic part, after WP-1343 closes.
- [ ] Reporting: `model/microstructure.py` gives a size per direction with esds; `help.py` entries; `capabilities()` flag; the Theory tab's equations with *Source* lines; a `rietx compare` row.
- [ ] Tests (unit/property; acceptance if this WP carries it) + obs/calc/diff PNGs to `tests/output/`: isotropic limit equals `lor_size` to 1e-12; equal widths across every symmetry-equivalent hkl per Laue class; a planted platelet recovered; GSAS-II's uniaxial model as oracle; the isotropic synthetic comes back isotropic within its esds; a family term equal to `lor_size` bit-identical to the isotropic fit; a planted anti-phase broadening on one family recovered; ceria as the isotropic control.
- [ ] Skill: a reference row keyed by the new field names in `references/` for microstructure (when to declare a shape, and that a powder often cannot separate it from Stephens strain or texture); no body rule.

## Acceptance

The isotropic limits are bit-identical to `lor_size` fits, a planted platelet and a planted family broadening are recovered within their esds on synthetic patterns, the GSAS-II uniaxial oracle agrees on a synthetic pattern, and every shipped fixture is bit-identical with no anisotropic size declared.

```sh
.venv/bin/python -m pytest tests/test_size_harmonics.py tests/test_cross_backend.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Popa, N. C. (1998). *J. Appl. Cryst.* **31**, 176–180. doi:10.1107/S0021889897009795.
- Järvinen, M. (1993). *J. Appl. Cryst.* **26**, 525–531. doi:10.1107/S0021889893001219.
- Stephens, P. W. (1999). *J. Appl. Cryst.* **32**, 281–289.
- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* **46**, 544–549 (GSAS-II).
- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210–218 (TOPAS).
- Balzar, D. et al. (2004). *J. Appl. Cryst.* **37**, 911–924 (ceria round robin).
- Önnerud, P. et al. (1997), cited by the FullProf manual for selective broadening (Pd₃MnD₀.₈).
- Issue #1065.

## Handover log

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1065). Checked against the tree at c0e32ab29: size broadening is isotropic per phase (`lor_size`, `gauss_size`, WP-1343's magnetic pair) and anisotropic only for strain (`Phase.microstrain`); the three quoted non-goals stand at WP-0503:209, WP-1131:260-261 and WP-1343:323; GSAS-II 5.8.4 carries isotropic, uniaxial and ellipsoidal size on the analytical profile (`GSASIIstrMath.py:3237-3249`) and the FullProf manual on disk carries spherical-harmonic, platelet/needle and selective size broadening; ROADMAP § v2+ does not list anisotropic size, so WP-1131's "with FPA at v2+" was never a fence entry. No open WP owns it: WP-0503 and WP-1131 are closed, WP-1343 fences anisotropic magnetic width out until its isotropic pair is measured, and WP-1946 names anisotropic size only as a non-goal. *Next:* the schema-shape decision, then AS-1.

# WP-0508 — Flat-plate absorption + a real-data capillary acceptance

Milestone: v0.5 · Status: ✅ shipped 2026-07-28
Depends on: 0501

## Goal

Two pieces WP-0501 fenced out, both landed:

1. **Flat-plate absorption** in the two geometries where it is not degenerate
   with the phase scale — *International Tables* Vol. C Table 6.3.3.1 case (2)
   (finite-thickness reflection) and case (3a) (symmetric transmission) — behind
   the same `CompiledModel._absorption` seam the cylinder uses.
2. **The real-data capillary acceptance** WP-0501 could not run, on an 11-BM
   pattern of NIST SRM 660a LaB₆ in a stated 0.81 mm bore, µR ≈ 0.5.

## Context

### The dataset question, answered

WP-0501's evidence for the cylinder correction is algorithm-level only, because
`tests/data/` had no capillary pattern with a **stated bore diameter and
specimen** — the two things µR needs. `11bmb_3844.fxye` from the GSAS-II
tutorials repo (`FitPeaks/data/`) is one, and it was hiding behind a file name:

- its header carries `#userHolder1.VAL, sample_name, "SRM 660a"` and
  `#userHolder2.VAL, chemical_formula, "Lanthanum Hexaboride (LaB6)"` — a
  **certified** specimen with a known composition, so µ is computable;
- 11-BM is transmission (Debye-Scherrer) geometry, and its mail-in program
  supplies **one** capillary: "Standard Size = 0.8 mm diameter Kapton tube",
  Cole-Parmer #95820-06, quoted on the beamline's own supplies page as
  **ID 0.0320″ = 0.81 mm**, OD 0.86 mm. The scan comment is `robotic
  collection`, i.e. the mail-in robot, which only accepts those bases;
- λ = 0.4131280 Å from the accompanying `.prm`, 132 992 points, 0.4995–66.995°
  2θ at 0.0005°, with a measured esd column;
- the repo already ships two files from this exact source (`11BM_NAC.fxye`,
  `FAP.XRA`), so the provenance and licence question is settled precedent.

At R = 0.405 mm and λ = 0.413 Å the composition gives **µR = 0.47 (packing 0.35)
to 0.67 (packing 0.50)** — mid-range for the Rouse fit, which stops at 1.

**The cell is not the acceptance criterion here, and saying why matters.** That
λ came from the beamline's own LaB₆ calibration (`# Calibration from:
oct09/11bmb_3843.calib`), so refining a cell against it is circular: a is fixed
by construction to reproduce the standard. Measured, it does — a = 4.1568496 Å
against the SRM 660a certificate's 4.1569162(97) Å at 22.5 °C, 16 ppm low, and
the scan is at 295.0 K (≈ −4 ppm of thermal expansion of that gap). Quote it as
a consistency check, never as an anchor. The anchor role stays with SRM 660c
(lab, flat plate) and SRM 676a (`qarr/corundum.prn`).

### What the capillary acceptance actually asserts

WP-0501's central claim is that the Rouse factor is *exactly* a constant times
exp(c·sin²θ), so applying it is an exact reparameterisation of {phase scale,
Biso}: **Rwp cannot move, and the ADPs carry the entire content.** That is a
falsifiable statement about real data, and it is what the acceptance tests.
Measured on this pattern, 2–60° 2θ, 116 001 points, the same staged plan run
with `mu_r=None` and `mu_r=0.674`:

| quantity | no correction | µR = 0.674 | Δ |
|---|---|---|---|
| Rwp | 0.0884883 | 0.0884884 | +3.2e-8 |
| a (Å) | 4.1568496 | 4.1568496 | −7.9e-12 |
| B(La) (Å²) | 0.453890 | 0.470545 | **+0.0166542** |
| B(B) (Å²) | 0.205395 | 0.222049 | **+0.0166542** |

against `equivalent_delta_biso(0.674, 0.413128) = 0.0166542`. Both atoms move by
the predicted shift to seven decimals; Rwp and the cell do not move at all. The
same run with `Source.dispersion` enabled reproduces the shift to 0.0166540 —
i.e. the identity is independent of what else is in the model, which is the
point of calling it exact.

**One honest caveat the acceptance must carry.** The *absolute* B here is not a
certified quantity and a reader should not treat it as one: switching anomalous
dispersion on (WP-0504; La at 30 keV has f′ = −1.22, f″ = +0.94, the K edge
being at 38.9 keV) moves B(La) 0.4539 → 0.4098 and B(B) 0.2054 → 0.2690 — 2.6×
the absorption effect, in the opposite direction for La. Absorption and
dispersion are separate biases on the same parameters, and only the *difference*
this WP measures is attributable to absorption.

### Flat plate: which cases exist, and the two that are worth having

*International Tables* Vol. C Table 6.3.3.1, with A the **transmission** factor
the forward model multiplies in (`model/absorption.py` states that convention;
most tabulations print A\* = 1/A instead):

    (1a) reflection, specimen thicker than the penetration depth
         A = 1/2µ                                    — no θ at all

    (2)  reflection, finite thickness t, planes parallel to the surface
         A = {1 − exp(−2µt·cosec θ)} / 2µ

    (3a) transmission, plate of thickness t, symmetric (φ = 0)
         A = t·sec θ·exp(−µt·sec θ)

Case (1a) is *identical* to the phase scale, not merely correlated: a parameter
with an identically zero column. GSAS-II returns 1.0 for its `'Bragg'` case for
the same reason. It stays a non-goal.

**Normalisation is a design decision, and the two cases take opposite answers.**

- Case (2) is normalised by its own thick limit, **A = 1 − exp(−2µt·cosec θ)**,
  so the correction is *relative to what this package already models* and
  µt → ∞ recovers the identity exactly. Note the consequence: the off state is
  µt = **∞** (i.e. the field absent), not µt = 0 — the opposite of every other
  correction here, where 0 is the identity. A zero-thickness plate diffracts
  nothing.
- Case (3a) has no thick limit (A → 0), so it is normalised at θ = 0:
  **A = sec θ·exp(−µt·(sec θ − 1))**. µt = 0 leaves `sec θ`, which is *real
  physics and not a bug*: the beam's footprint on a tilted plate, hence the
  diffracting volume, grows as sec θ. Choosing the geometry is what turns it on.

Two properties worth asserting in tests: (2) → 1 as µt → ∞ (the continuity
check), and (3a) has a maximum in µt at µt = cos θ — a transmission plate has an
**optimal thickness**, t ≈ 1/µ, which is a genuinely useful thing to report to
someone about to prepare one.

### µt is a plain float, and this was measured rather than assumed

WP-0501 made µR non-refinable because the Rouse factor is an *exactly* singular
direction alongside {scale, Biso}. The `### Inherited` note below (correctly)
refused to extend that to flat plate without measuring, since neither (2) nor
(3a) is of that form. Measured — ∂lnA/∂µt projected onto span{1, sin²θ}, the
subspace a free phase scale and a free Biso span, reporting the norm fraction
left over (the `mu_r_identifiable_fraction` construction, shipped as
`mu_t_identifiable_fraction`):

| 2θ range | case (2) at µt = 0.05 / 0.3 / 1.0 / 2.0 | case (3a), any µt |
|---|---|---|
| 5–60° | 0.119 / 0.148 / 0.211 / 0.469 | 0.035 |
| 10–90° | 0.064 / 0.164 / 0.082 / 0.322 | 0.084 |
| 20–140° | 0.028 / 0.119 / 0.048 / 0.174 | 0.265 |

**The measurement moved once it was made against the code rather than the
paper, and that is worth recording.** Case (3a)'s ∂lnA/∂µt is −(sec θ − 1) for
the *normalised* expression this WP implements and −sec θ for ITC's — a
difference of a constant, i.e. of a multiple of the phase-scale direction. The
numerator of the ratio is identical either way; the denominator is not, and the
unnormalised form reports 0.2–1.3 % where the normalised one reports 3–26 %.
**The fraction is basis-dependent and is not an esd**; read it as "how much of
this correction's angular signature survives a free scale and a free Biso" and
quote the normalised numbers, which are what the shipped function returns.

Either way the conclusion holds, but its *grounds* change: flat-plate µt is not
degenerate the way µR is exactly degenerate — it is merely ill-conditioned. So
**µt is a plain float, computed from thickness × composition × packing, and
never refined**, on three stated grounds rather than on an identity: µt is
knowable from the specimen, a free one lands in the {scale, Biso, background}
corner WP-0502 needed guards for, and what it would silently re-apportion is the
ADPs the correction exists to protect. The fraction is *reported* on the result
record, so a caller who disagrees can see the number and decide for themselves.
Case (2)'s residue is also largest exactly where the correction is weakest
(µt ≥ 2 depresses nothing: A is within 1 % of 1 across the whole range), which
is the opposite of a case for refining it.

### Files and seams to extend (do not duplicate)

- **`model/absorption.py`** — the module to extend. Exports
  `cylinder_absorption`, `cylinder_absorption_and_dmur`, `equivalent_delta_biso`,
  `mu_r_identifiable_fraction`, `CYLINDER_MU_R_MAX = 1.0`, and the A-vs-A\*
  convention statement a flat-plate function must honour too.
- **`CompiledModel._absorption` is the single seam** — and its docstring records
  the hazard: A multiplies the same product that `_structural_intensity_grad`
  and `po_intensity_grad` rebuild by hand, so a *new* geometry's factor applied
  in only one of the three leaves those analytic columns silently wrong while FD
  stays right. The two guard tests in `tests/test_absorption.py` (with their
  `(1 − A).max() > 0.5` pre-asserts) are the pattern to copy. Because
  `_absorption` already dispatches on `geometry_kind`, a new kind is one branch.
- **`packed_mu_r` / `estimate_capillary_mu_r`** are shape-agnostic except the
  final `× R`; factor the shared part rather than re-deriving bulk µ.
  `Geometry.packing_fraction` applies unchanged.
- **µt needs no `params/vector.py` work at all** — a plain float never enters
  the parameter table, so the `sample_`-prefix heuristic and the
  `scalar_chain_supported` trap that bit WP-0502 are both inapplicable here.

### Inherited

From **WP-0501** (cylindrical absorption, landed 2026-07-27):

- `model/absorption.py` exists and is the module to extend, not to duplicate.
- `CompiledModel._absorption` is the single seam; the three-assembly hazard
  above is its documented rule.
- `packed_mu_r` and `estimate_capillary_mu_r` already exist and are
  shape-agnostic in everything but the final `× R`.
- **A refinable absorption parameter needs a real justification here.** Check
  whether (2) and (3) are separable before assuming µt can be refined — measure
  it (project ∂lnA/∂µt onto span{1, sin²θ}) rather than assuming. *Done: see
  the table above. They are not, and µt stays a plain float.*
- **A digit-transposition trap, and the lesson from it.** WP-0501's b₂ was
  printed "−0·0375" in the available scan when it is −0·3750; the error was
  invisible against a constant-θ slice and 0.0821 wrong at µR = 1. Validate an
  absorption expression against something spanning **both** its arguments. Here
  that is cheap: cases (2) and (3a) are closed-form integrals, not fits, so they
  are checked against a direct quadrature of the defining volume integral rather
  than against another code's transcription.

From **WP-0507** (anode wavelengths, landed 2026-07-28):

- `schemas.instrument._KA_DOUBLETS` holds six anodes (Cr/Fe/Co/Cu/Mo/Ag, each
  also as a `…Ka1` variant). Import wavelengths from it; do not re-enter a
  number, and specifically do not reach for the Bearden values — mixing
  wavelength scales is a ~100 ppm cell error.
- **A flat-plate acceptance is no longer implicitly a Cu experiment**, and the
  anode changes µt by more than the geometry does: Fe µ/ρ = 297.7 at Cu Kα1,
  56.2 at Co Kα1, 36.2 at Mo Kα1. A µt quoted without naming the anode is
  meaningless.
- **µ and f′/f″ come from different tables that jump at the same edges**
  (`data/mu_McMaster.dat`, `data/f1f2_CromerLiberman.dat`); a wavelength near an
  edge makes both untrustworthy at once.

From **WP-0502** (surface roughness, landed 2026-07-27) — it shipped a
correction in this WP's geometry and family:

- **Copy the block shape, don't re-derive it.** `Geometry.surface_roughness` is
  the worked example of an opt-in, geometry-gated correction, with one applier
  (`_roughness_factor`) called from all three intensity assemblies.
- **`optimize/statistics.block_projection_r2(jac, block, targets, nuisance)` is
  exported**, and `nuisance` is the load-bearing argument: any multiplicative
  correction is trivially ~0.96 "scale-like", so project the scale and
  background out first and read the partial R².
- **Judge a correction at reflection positions, not on the fitted grid** — the
  round-robin patterns start at 5° 2θ but first reflect at 25–32°, and a
  grid-based fence reported a 27 % depression no modelled peak ever saw.
- **No dataset in the repo can constrain a low-angle intensity correction**;
  0502's real-data outcome was a negative result. *Still true here: every
  flat-plate pattern in the repo is a thick back-packed specimen, so case (2) is
  the identity on all of them — which is itself the thing to assert, since it is
  why no shipped number changes.*
- ~~**Watch for `|ρ| > 1`**~~ — fixed 2026-07-28 (`covariance_estimates` now
  symmetrises JᵀJ and passes `hermitian=True`). The lesson survives: absorption
  parameters land in the ill-conditioned {scale, displacement, background}
  corner, so suspect the linear algebra before the physics, and
  `np.allclose(corr, corr.T)` is the cheapest tell.

From **WP-0504** (anomalous f′/f″, landed 2026-07-27):

- **µ stays on McMaster; do not re-source it from f″.** f″ is photoabsorption
  only, while beam removal needs the total cross section, and the
  Rayleigh + Compton gap is largest for light elements.
- `attenuation.photoelectric_cross_section` exposes the photoelectric column
  separately; the edge-refusal behaviour lives there and is unchanged.
- **A dispersion block does not change µ, and µ does not change f′/f″.** They
  are independent inputs that share a physical origin. *Measured here on LaB₆ at
  30 keV: the two corrections move B(La) by −0.044 and +0.017 Å² respectively,
  independently and additively.*

## Non-goals

- Thick-specimen Bragg-Brentano reflection, ITC case (1a) — exactly degenerate.
- **Position aberrations of a transmission goniometer.** The new geometry kind
  models absorption and nothing else; like `debye_scherrer`, only `zero_shift`
  moves its peaks. Inventing a displacement law for it is out of scope and
  would violate the cite-your-source rule.
- Asymmetric / tilted transmission, ITC case (3b) with φ ≠ 0. `Geometry` carries
  no tilt angle, and the symmetric case is what a flat-plate transmission
  instrument (Stoe Stadi P, D8 in transmission) actually runs.
- Re-opening the cylinder parameterisation. Lobanov & Alte da Veiga's fit
  (GSAS-II/TOPAS) reaches µR ≤ 3 where Rouse stops at 1, but its coefficients
  trace only to an unobtainable conference abstract. If µR > 1 specimens become
  important, the defensible route is a quadrature or a fit *this project*
  derives against ITC eq. (6.3.3.4).

## Tasks

- [x] Expand this stub into a full WP before writing code
- [x] Source a capillary dataset with a stated bore diameter and specimen
- [x] Land `tests/data/11BM_LaB6_660a.fxye` + `.prm` with provenance rows in
      `tests/data/README.md` (source, licence, capillary spec, the circular-λ
      warning)
- [x] `tests/test_acceptance_capillary.py` (slow): the exact-reparameterisation
      identity on real data — Rwp and cell invariant, both Biso shifted by
      `equivalent_delta_biso`; obs/calc/diff PNGs to `tests/output/`
- [x] `model/absorption.py`: `flat_plate_absorption` for ITC (2)/(3a), the
      generalised (projected) ΔBiso, `mu_t_identifiable_fraction`, optimal
      thickness; validated against a quadrature of the defining integral
- [x] Schema seam: `Geometry.kind += "flat_plate_transmission"`, `mu_t`,
      `thickness_mm`, validators; `estimate_flat_plate_mu_t` beside the
      capillary estimator
- [x] `CompiledModel.mu_t` + `_absorption` dispatch, applied in all three
      intensity assemblies, guarded analytic-vs-FD as `test_absorption.py` does
- [x] `AbsorptionCorrection` record + diagnostics; `pxrdref compare` row +
      the `lab6_capillary` standard; AGENT_PROTOCOL §8.12 and two diagnostic rows
- [x] Handover log + ROADMAP sync

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_absorption.py tests/test_flat_plate.py -q
.venv/bin/python -m pytest tests/test_acceptance_capillary.py -q       # slow
.venv/bin/python -m pytest -m "not slow" -q
.venv/bin/python -m ruff check src tests examples
```

**Capillary (real data, SRM 660a at 11-BM, µR = 0.674):** |ΔRwp| < 1e-6,
|Δa| < 1e-9 Å, and |ΔB − `equivalent_delta_biso`| < 1e-5 Å² for *every* atom.

**Flat plate (algorithm level):** both ITC expressions agree with a direct
quadrature of the defining path-length integral to < 1e-10 over
0 ≤ µt ≤ 5 × the measured 2θ range; case (2) → 1 as µt → ∞; every analytic
Jacobian column agrees with FD with the correction switched on (the guard that
catches a factor applied in one assembly and not the other three).

## References

- *International Tables for Crystallography* Vol. C, Table 6.3.3.1 and
  eq. (6.3.3.1) — flat-plate absorption factors; the A vs A\* convention.
- Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* **A26**, 682–691, eq. (2)
  — the cylinder fit WP-0501 shipped and this WP validates on real data.
- NIST SRM 660a certificate (a = 4.1569162(97) Å at 22.5 °C),
  tsapps.nist.gov/srmext/certificates/archives/660a.pdf.
- 11-BM capillary specification: wiki-ext.aps.anl.gov/ug11bm →
  *Supplies and Tools* ("Standard Size = 0.8 mm diameter Kapton tube";
  Cole-Parmer #95820-06, ID 0.0320″ = 0.81 mm) and *Sample Preparation for
  Mail-In Users* ("11-BM uses transmission (Debye-Scherrer) geometry").
- Dataset: GSAS-II tutorials repo, `FitPeaks/data/11bmb_3844.{fxye,prm}`
  (github.com/AdvancedPhotonSource/GSAS-II-tutorials).

## Handover log

- **2026-07-28 (later)** — **shipped.** *Done:* everything on the checklist.
  Seven commits: WP expansion, dataset + provenance, capillary acceptance,
  flat-plate physics + quadrature tests, the model/record/diagnostic wiring, the
  compare-UI row and `lab6_capillary` standard, and the doc sweep
  (AGENT_PROTOCOL §8.12 + two diagnostic rows, DESIGN's absorption section,
  README, CLAUDE.md). 907 tests green (`-m "not slow"` 868, ~2.8 min).

  *Findings worth carrying, beyond what is written above:*

  - **The capillary acceptance came out cleaner than the design expected.** The
    prediction was "Rwp roughly unchanged"; the measurement is Rwp to 3e-8, the
    cell to 8e-12 Å, and *both* Biso to seven decimals of the predicted shift,
    including on top of an anomalous-dispersion model. That is tight enough to
    use as a regression on the whole intensity chain, not just on absorption.
  - **The flat-plate correction is much bigger than the capillary one** — ΔBiso
    −1.5 Å² at µt = 0.2 versus 0.49 at µR = 1 — and it moves Rwp, so it is a
    genuinely different animal despite sharing a module. The compare-UI row is
    the honest way to show it: on a thick specimen (fluorite) declaring µt = 0.5
    makes Rwp *worse* and drives a Biso onto its bound, which is the correction
    refusing a specimen that is not there.
  - **The identifiable-fraction number is basis-dependent**, and this was found
    only by re-measuring against the shipped code rather than the ITC form (the
    table above records both). Any future ratio-of-norms diagnostic wants the
    same check: the numerator is invariant to adding a scale direction, the
    denominator is not.
  - **The flat-plate ΔBiso the record reports is a *lower bound*, and this was
    only found by testing it end to end.** Every other test here checks the
    projection arithmetic; the one that generates a pattern through the
    correction and refits without declaring the thickness shows the fit absorbs
    **1.06–1.5×** the predicted bias, tracking `unabsorbed_fraction` (0.080 →
    0.263). The projection is unweighted, the refinement is weighted, and they
    agree only insofar as the correction really is a {scale, Biso} direction —
    which for the cylinder it exactly is, hence seven decimals there and a
    factor of 1.5 here. Anything that reports a "bias" by projecting onto a
    parameter subspace inherits this, and the honest fix was to say so and pin
    the relationship rather than to widen a tolerance.
  - **The two flat geometries disagree about what silence means**, which is why
    neither can use a sentinel. Under *reflection* an undeclared thickness means
    infinitely thick (the correction is the identity); under *transmission* it
    means a transparent plate, because the sec θ footprint belongs to the tilt
    and not to the absorption — so that geometry applies its factor
    unconditionally and always emits a record. This was caught by re-reading a
    docstring against the code: the preset promised the behaviour and named a
    diagnostic that did not exist, and the docstring turned out to have the
    physics right.
  - **A fence gated on the wrong quantity fires always.** The
    `ABSORPTION_THICKNESS_MATTERS` threshold was first put on the identifiable
    fraction, which is 3–47 % for *every* flat-plate µt including the inert
    µt ≥ 2 — WP-0502's "guard that always fires" all over again. It is gated on
    |ΔBiso| > 0.05 Å² instead, and a test pins that gating on the residue would
    have inverted the message.
  - **A missing thickness must not be spelled `0.0`.** The reflection case's
    identity is µt = ∞, so the usual "0 means off" convention would multiply
    every intensity by zero. This is enforced in three places (schema refusal,
    `CompiledModel.mu_t: float | None`, a test that a thick specimen leaves the
    forward model bit-untouched) rather than commented once.

  *Next:* nothing on this WP. The v0.5 milestone closes with it — record in
  `docs/milestones/v0.5.md`.

  *Deferred, with the numbers that would justify revisiting:* making µt
  refinable. It is not the exactly-singular direction µR is (3–47 % of its
  signature survives the {scale, Biso} projection), so a bounded-LM solver plus
  the `block_projection_r2` nuisance machinery could in principle fit it on data
  with a strong low-angle range. What stops it today is that µt is measurable
  and the failure mode is silent ADP re-apportionment. Anyone reopening this
  should start from `test_mu_t_identifiability_is_small_but_not_zero`.

- **2026-07-28** — stub expanded to a full WP, with the two questions it was
  blocked on both answered by measurement rather than assumption. *Done:* the
  dataset hunt (11-BM SRM 660a LaB₆, 0.81 mm Kapton, µR ≈ 0.47–0.67) and a
  viability run confirming the exact-reparameterisation identity on real data to
  seven decimals; the µt separability measurement that settles µt as a plain
  float. *Next:* land the data + acceptance, then the flat-plate cases.
  *Gotchas:* λ is beamline-calibrated on this very standard, so the cell is
  circular — do not quote it as an anchor; and the *absolute* Biso is
  contaminated by neglected dispersion at 2.6× the absorption effect, so the
  acceptance must assert the shift, never the value.
- **2026-07-27** — created by WP-0501, which fenced both pieces out with the
  rationale above rather than deferring them silently.

# WP-0504 — Anomalous scattering f′, f″

Milestone: v0.5 · Status: ✅ shipped 2026-07-27
Depends on: —

## Goal

The scattering factor becomes f = f₀(k) + f′(λ) + i·f″(λ), and the powder
|F|² the forward model uses becomes the **Friedel-averaged** one that a powder
pattern actually measures. Opt-in per source; absent ⇒ bit-identical to today.
A diagnostic fires when the correction is off but large enough to matter, so
"off" is never a silent wrong answer.

## Context

### Why this is a correctness WP, not a refinement

f′/f″ are not a modelling flourish; at a lab Cu tube they are a
**double-digit-percent** error on the Bragg power of a 3d-bearing phase, and
QPA divides one phase's scale by another's. Measured with the bundled table
(Cu Kα1, total Σ m·|F|² over 2θ ≤ 110°, round-robin phases exactly as
`test_acceptance_qpa_roundrobin` declares them):

| phase | Bragg power with f′,f″ ÷ without |
|---|---|
| fluorite CaF₂ `F m -3 m` | **+7.3 %** |
| corundum Al₂O₃ `R -3 c` | **+5.4 %** |
| brucite Mg(OH)₂ `P -3 m 1` | +4.6 % |
| zircon ZrSiO₄ `I 41/a m d:2` | +0.2 % |
| LaB₆ `P m -3 m` | −1.0 % |
| magnetite Fe₃O₄ `F d -3 m:2` | −9.2 % |
| zincite ZnO `P 63 m c` | **−15.6 %** |

Signs differ across phases and nothing cancels into a common scale: the *ratio*
corundum:zincite moves by 25 %, and that is the whole QPA answer. See
"Acceptance" for the pre-registered prediction this makes about the
already-measured v0.3 numbers.

Two entries in that table are traps worth naming, because getting them wrong
by recall rather than by lookup is exactly what happened while writing this WP:

* **Zn (−15.6 %) and Zr (+0.2 %) are not the same story.** Zn sits just below
  its K edge at 8.048 keV (f′ = −1.55, f″ = 0.68); Zr's K edge is at 18 keV, far
  above, so its f′ is only −0.18 while f″ = 2.24 from the L shell. "Below the
  K edge ⇒ large negative f′" is true only *just* below.
* **f′ and f″ partly cancel for heavy elements.** |f|² picks up f″ as
  +f″², so La (f′ = −1.38, f″ = 9.03) nets to only −1.0 % on LaB₆. A
  correction can be individually large and collectively small.

### The powder average is Friedel-averaged, and there is an exact closed form

`symmetry.generate_reflections` merges **±h into one orbit** and keeps one
representative with the Laue multiplicity (its own comment says why: "the v0.1
model is kinematic without anomalous scattering, so Friedel's law holds").
With complex f that premise dies: in a non-centrosymmetric group |F(h)|² ≠
|F(−h)|², while d(h) = d(−h) — the two land in the *same* powder peak. So the
model must produce the orbit **average**, not the representative's value.

Do not average by enumerating the orbit. With

    G_j(h) = Σ_m T_jm · exp(2πi h·(R_m x_j + t_m))        (the orbit sum today)
    A(h)   = Σ_j occ_j · (f₀_j(k) + f′_j) · G_j(h)
    B(h)   = Σ_j occ_j ·  f″_j          · G_j(h)

the Friedel average is exactly

    ⟨|F|²⟩ = ½(|F(h)|² + |F(−h)|²) = |A(h)|² + |B(h)|²                      (1)

because F(−h) = conj(Σ_j conj(f_j)·G_j(h)) = conj(A − iB) — the same G_j, no
second orbit pass. **Measured**: on ZnO `P 63 m c` at Cu Kα, (1) reproduces the
explicit Laue-orbit average of |F|² to **5.1e-15** relative on every reflection
to 90° 2θ. The naive "complex f at the representative only" is wrong by up to
**1.2 %** there, so this is not a theoretical nicety.

Three properties that make (1) the right shape to build on:

* **f″ = 0 ⇒ B = 0 ⇒ (1) = |F|²**, the expression today. f′ = f″ = 0 is
  bit-identical to today. The off state costs one multiply by zero, not a
  branch.
* It is exact for **centrosymmetric** groups too (there A and B share one
  common phase, so Im(ĀB) = 0 identically) — no case analysis anywhere.
* Both A and B are structure factors with *real* per-atom coefficients, so
  every existing derivative keeps its shape: ∂⟨|F|²⟩/∂p = 2Re(Ā·∂A/∂p) +
  2Re(B̄·∂B/∂p), i.e. `d_f2_d_xyz`/`d_f2_d_uaniso` run their existing kernel
  twice with different prefactors rather than growing a new one.

### f′, f″ are frozen per stage — and that is structural, not a convention

`EmissionLine.wavelength` is a plain `float`, not a `Parameter` (the schema
docstring: "emission wavelengths are known far more accurately than a powder
pattern can refine them"), and species assignment is discrete. So (f′, f″) is
a **compile-time constant per (species, wavelength)** — it belongs on
`PhaseSites` alongside the frozen op subsets, computed in `compile_phase_sites`
and never touched during a solve. It never enters θ, is never traced, and adds
nothing to the frozen-per-stage risk surface.

### |F|² is shared across emission lines — guard it, do not smear it

`phase_peaks` computes `f2` **once** outside the emission-line loop
(`forward.py`, "|F|² samples the form factors at sinθ/λ = 1/2d —
line-independent"). f′/f″ break that in principle: Cu Kα1 and Kα2 are 20 eV
apart. In practice, 20 eV is nothing unless an edge sits between them — but a
modelled Kβ line (≈ 860 eV away) or a W Lα contamination line is a real
difference.

Follow `attenuation.py`'s idiom — **refuse rather than smear**. Evaluate f′/f″
at *every* line at compile (it is a scalar table lookup per species, free), use
line 0's values for the shared |F|², and raise when any other line's values
differ by more than `LINE_DISPERSION_TOL` × Z. Note for the successor: the
orbit sums G_j in (1) are line-independent, so a genuinely per-line |F|² costs
one extra *combine* per line, not a re-evaluation — the fix is cheap if a real
dataset ever needs it.

### The edge is where the tables are wrong, so say so

`crystallography/attenuation.py` already refuses a wavelength whose grid
interval spans an absorption edge. f′/f″ need the same guard **and one more**:
within roughly a few tens of eV of an edge, tabulated dispersion corrections
are wrong *in principle* — f″ there is the XANES of the actual compound, not
of an isolated atom, and no table knows the coordination. So near-edge must be
a loud warning plus a way to supply **measured** values (the `overrides` map),
not an interpolation.

### Ions, and what f′ attaches to

`normalize_species` resolves `"Zn2+"` to an ionic f₀ when tabulated. f′/f″ are
core-level effects and are tabulated **per element only**; strip the charge for
the dispersion lookup and keep the ionic f₀. State it in the docstring — the
asymmetry looks like a bug otherwise.

### Files to touch

| file | change |
|---|---|
| `data/f1f2_*.dat` *(new)* + `ATTRIBUTION.md` | bundled tabulation (see "Data source") |
| `crystallography/dispersion.py` *(new)* | loader, `dispersion(element, wavelength) -> (f′, f″)`, edge guard, near-edge warning, f1→f′ convention |
| `crystallography/structure_factor.py` | A/B form (1); `PhaseSites.f_anom`; `compile_phase_sites(phase, wavelengths, …)`; both derivative kernels |
| `schemas/instrument.py` | opt-in `Dispersion` block on `Source` + `overrides`, validators |
| `model/forward.py` | pass λ into `compile_phase_sites`; line-spread guard |
| `io/exporters.py` | reflection table reports the Friedel-averaged \|F\|² |
| `refine.py` (+ `strategy/staged.py`) | `DISPERSION_NEGLECTED` diagnostic |
| `tests/test_dispersion.py` *(new)*, `tests/test_acceptance_dispersion.py` *(new)* | unit/property + real-data acceptance |

### Data source: `f1f2_CromerLiberman.dat`, bundled — decided, not open

The title of this WP says "via xraydb". That is now wrong and stays only as
the historical filename. **Bundle**, matching the `f0_WaasKirf.dat` /
`mu_McMaster.dat` precedent, and take the *Cromer-Liberman* tabulation:

* **xraydb** is MIT with a CC0 data dedication, and its Chantler tables are the
  best data in the survey — but it hard-requires **sqlalchemy** (tightened, not
  dropped, in recent releases), which is a heavy ABI-churning dependency for a
  numeric core. It also returns f′ with the 3/5-CL relativistic and
  nuclear-Thomson corrections folded in and no way to remove them.
* **`f1f2_Chantler.dat` must not be bundled.** Its DABAX header reads "The
  present license has been purchased by the ESRF Programming Group. No use of
  these data is allowed from outside ESRF", over a NIST SRD 66 copyright —
  and NIST Standard Reference Data is the statutory *exception* to
  17 U.S.C. §105, not public domain. The MIT grant on the DABAX repo cannot
  convey rights its author never held. (It is also technically the worst
  option: ~545 eV grid spacing at 8 keV.)
* **Cromer-Liberman is the crystallographic reference**: it is what
  *International Tables* Vol. C §4.2.6 tabulates and what GSAS-II computes, so
  a disagreement with another Rietveld code is attributable — the repo's
  "adopt the protocol" principle applied to a data table. Z = 3–98, 1–70 keV,
  1024 log-spaced points (0.42 % spacing, ~33 eV at 8 keV), column 2 is **f′
  itself**, and the per-element `#UF1ADD` header equals Z exactly — asserted on
  extraction, so the f1-vs-f′ convention cannot silently rot.
* **Not** periodictable's Henke tables: they cap at 30 keV, *below* the 11-BM
  acceptance energy (29.95 keV is inside but 0.4 Å synchrotron work is not),
  and the Windt/Henke f″ differs from Cromer-Liberman by up to 8 % (La) in the
  hard-X-ray band where it is extrapolated. (This WP's original scope line
  called them "the wrong tool"; that judgement is confirmed, but it lives here
  and not in `../DESIGN.md`, which has no dispersion entry.)

Source: `github.com/oasys-kit/DabaxFiles` (MIT), the current home of DABAX;
the `esrf.fr/computing/scientific/dabax` URL in every header is dead.

**gemmi already exposes `gemmi.cromer_liberman`** and is already a hard
dependency — but it is used here only as a **test oracle for f″** (agrees with
the table to 1e-4 e), never for f′: its f′ disagrees with every published
tabulation for a handful of lanthanides and actinides (Ce by 11 e at 19 keV,
Bi by 6.9 e near 8 keV), and it returns (0, 0) silently outside Z = 3–92.
Say so in ATTRIBUTION.md, so "why not just call gemmi" has a recorded answer.

### The cross-check that makes the bundled table falsifiable

The optical theorem ties f″ to the photoabsorption cross section:

    σ_photo [barn] = 2 · r_e[Å] · λ[Å] · f″ · 1e8,   r_e = 2.8179403262e-5 Å

and `mu_McMaster.dat` already carries a **photoelectric column** from an
entirely independent compilation (1969 vs 1983, no shared inputs). Measured at
Cu Kα1, the two agree to **0.04 % (O) / 3.4 (Al) / 1.2 (Ca) / 1.1 (Fe) / 5.4
(Zn) / 3.8 (Zr) / 2.5 % (La)** — a real unit test across Z = 8→57, at a 6 %
tolerance. The residual is genuine tabulation disagreement, and that is
precisely why µ stays on McMaster (below) rather than being re-derived.

### Inherited

From **WP-0305** (Brindley, landed 2026-07-23), which explicitly deferred this
decision here — "revisit the coordination when WP-0504 actually needs f′/f″":
**xraydb was deliberately not pulled in** (it drags sqlalchemy); 0305 bundled
`data/mu_McMaster.dat`, an energy-trimmed (2–120 keV) three-column extract of
DABAX `CrossSec_McMaster.dat` (McMaster 1969), with ATTRIBUTION.md updated.

**This WP's call: keep µ on McMaster, add f′/f″ as a separate bundled table.**
Not a compromise — a physics fence. µ is *beam removal* and needs the total
cross section; f″ gives **photoabsorption only**. The gap is Rayleigh +
Compton, and it is largest for **light** elements — photoabsorption grows about
as Z⁴ while Rayleigh grows as Z², so at Cu Kα the scattering share is ~4.6 %
for O and ~1.1 % for La. That is exactly where 0305 flagged McMaster as
weakest, so re-sourcing µ from f″ would trade one small error for another; the
two tables instead check each other (previous section). 0305's other measured
warning stands and is not fixed here: McMaster's low-Z accuracy vs NIST
Hubbell-Seltzer is B −7 %, O −3.6 %.

Also from 0305, and now this WP's problem: `crystallography/attenuation.py`
**refuses** a wavelength whose grid interval contains an absorption edge rather
than smearing it — and edges are exactly the regime f′/f″ exists to describe.
This WP does not replace that guard; it repeats its shape for the f1f2 grid and
adds the near-edge warning + `overrides` escape hatch that the µ path lacks.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24): the sample-1 QPA bias
has a stable signed **shape** — zincite low (mean −2.7 wt %), corundum high
(+1.7), fluorite high (+1.0) — asserted as a live test
(`test_sample1_bias_has_the_microabsorption_shape`) *specifically* so that "a
change that breaks — or fixes — the physics fails loudly and prompts
re-derivation". This WP is that change. 0310 attributed the shape to untreated
microabsorption but flagged that fluorite's positive sign does not fit that
story. See "Acceptance": neglected dispersion predicts all three signs,
fluorite included.

## Non-goals

* **Refining f′/f″** (resonant/MAD powder contrast, valence-state
  determination). They stay fixed constants; the `overrides` map is how a
  measured near-edge value gets in. v2 fence.
* **Per-emission-line |F|²**. Guarded against instead (above), with the cheap
  extension path recorded.
* **Kramers-Kronig derivation of f′** from the bundled µ table. The 2–120 keV
  truncation wrecks the principal-value integral; bundle f′, do not compute it.
* **Re-sourcing µ from f″** — decided against on physics grounds above.
* **Neutron scattering lengths / resonant neutron absorption.** v2 (TOF).
* **Flipping the default to on.** Every acceptance number in `milestones/` was
  measured with dispersion off; changing the default is a re-measurement of the
  whole validation matrix, which is WP-1001's job (written into its
  `### Inherited`).
* **Friedel-pair *splitting*** (reporting the two members separately, as a
  single-crystal code would). A powder cannot resolve them — they share d.
  Only the average is observable, and (1) is it.

## Tasks

Each item ≈ one commit, prefixed `WP-0504:`.

- [x] Expand this stub into a full WP before writing code
- [x] `crystallography/dispersion.py` + bundled `f1f2_CromerLiberman.dat` +
      ATTRIBUTION.md: loader in the existing `#S`-block idiom,
      `dispersion(element, wavelength) -> (f′, f″)`, `#UF1ADD == Z` asserted at
      extraction so the f1-vs-f′ convention cannot rot, edge-interval refusal,
      `near_edge` for the XANES region, H/He zeroed rather than refused.
      `attenuation.photoelectric_cross_section` split out for the
      optical-theorem cross-check. Tests: International Tables at Cu Kα,
      `gemmi.cromer_liberman` as an independent f″ oracle (1e-3 e), and the
      optical theorem vs McMaster at 6 %.
- [ ] `schemas/instrument.py`: opt-in `Dispersion` block on `Source`
      (`overrides: {element: (f′, f″)}` for measured near-edge values),
      validators, JSON round-trip test.
- [x] `crystallography/structure_factor.py`: the A/B Friedel-averaged form (1);
      `PhaseSites.f_anom` (per-atom complex, frozen);
      `compile_phase_sites(phase, f_anom)`. Bit-identity when off — which
      constrained the fp *association order*, not just the algebra; identity vs
      the explicit orbit average on ZnO to 1e-12.
- [x] Derivatives: `d_f2_d_xyz` and `d_f2_d_uaniso` in the A/B form (B reuses
      A's bracketed sum, so it costs one multiply-accumulate); FD and jax
      `jacfwd` agreement; `toy_anomalous` backend golden — the only
      non-centrosymmetric state in the set, so it is the only one that
      exercises B ≠ 0.
- [x] `model/forward.py`: λ wired into the compile; line-spread guard
      (`LINE_DISPERSION_TOL`, 1 % of Z). `io/exporters.py` already reported the
      Friedel-averaged |F|² by construction (it reads `cp.sites`); its docstring
      now says so.
- [x] `DISPERSION_NEGLECTED` diagnostic: fires when the block is absent and a
      species' |f|² at k = 0 moves ≥ 2 %, escalating to a warning at 5 %.
- [x] Tests: `tests/test_dispersion.py` (36 unit/property) + PNGs to
      `tests/output/` from the acceptance module.
- [x] Acceptance (below), and the re-derivation WP-0310 asked for:
      `test_sample1_bias_has_the_microabsorption_shape` is renamed
      `…_has_the_dispersion_shape` with the corrected reasoning (its assertions
      are unchanged — that suite deliberately stays dispersion-off and
      comparable to v0.3). `docs/milestones/v0.3.md` carries a dated
      superseded-explanation note.

## Acceptance

**Primary — IUCr round-robin sample 1a–1h, `tests/data/qarr/cpd-1*.prn`.**
This WP makes a *pre-registered, parameter-free* prediction about numbers that
were measured before it started. Neglecting dispersion inflates each phase's
fitted scale by r_p = (power with f′f″)/(power without) = 1.0542 (corundum),
0.8441 (zincite), 1.0728 (fluorite), so the recovered fractions are biased to
W_p ∝ w_p·r_p renormalised. Against the v0.3 measured errors:

| sample | corundum pred/meas | zincite pred/meas | fluorite pred/meas |
|---|---|---|---|
| 1a | −0.01 / +0.61 | −0.83 / −0.57 | +0.84 / −0.04 |
| 1b | +0.18 / −0.12 | −0.27 / −0.02 | +0.09 / +0.14 |
| 1c | +1.15 / +1.26 | −1.49 / −1.72 | +0.34 / +0.47 |
| 1d | +0.80 / +1.85 | −4.99 / −3.87 | +4.19 / +2.02 |
| 1e | +1.43 / +2.21 | −2.72 / −2.32 | +1.30 / +0.12 |
| 1f | **+3.24 / +3.17** | **−5.71 / −5.13** | **+2.47 / +1.96** |
| 1g | +2.08 / +2.39 | −5.00 / −3.91 | +2.93 / +1.52 |
| 1h | +2.01 / +2.17 | −4.64 / −3.72 | +2.63 / +1.54 |

All three signs reproduced in 7 of 8 mixtures, including **fluorite positive**,
which the microabsorption story could not explain. Subtracting the prediction
takes the RMS error from **2.26 → 0.83 wt %**.

Criterion: with dispersion on, the worst |ΔW| falls well below the v0.3 5.13
wt % (1f zincite) and the signed shape collapses — mean zincite error toward
zero rather than −2.7.

**Measured** (2026-07-27, `tests/test_acceptance_dispersion.py`, all eight
refitted under the identical v0.3 protocol with only the block added):

| phase | mean error off → on | RMS off → on | worst off → on |
|---|---|---|---|
| corundum | +1.69 → **+0.75** | 1.96 → 0.88 | 3.17 → 1.20 |
| zincite | −2.66 → **−0.54** | 3.14 → 0.70 | 5.13 → 1.39 |
| fluorite | +0.97 → **−0.20** | 1.27 → 0.43 | 2.02 → 0.65 |
| **overall** | | **2.26 → 0.69** | **5.13 → 1.39** |

The refinement *beat* the parameter-free prediction (0.69 vs 0.83 predicted),
despite `qpa_plan` freeing Biso so it could have re-absorbed the correction
instead. Every phase's RMS improves and the signed shape is gone.

**Structural — ZnO `P 63 m c` (`qarr/zincite.prn`), the non-centrosymmetric
case.** Unit-level: (1) matches the explicit Laue-orbit average to < 1e-12.
Real-data measured: cell unmoved (a, c to 1e-5 Å), Rwp 10.907 → 10.758 %, and
the finding Rwp barely shows — **B(O) goes from 0.022 to 0.429 Å²**. Without
Zn's f′ = −1.55 the model over-scatters Zn by ~10 %, and the only lever the
refinement has to restore the Zn:O contrast is to drive B(O) to its floor. The
correction hands back a physical displacement parameter.

**Negative control — SRM 660c LaB₆ (`nist_srm660c_100a.cif`).** Measured:
`a` = 4.156895 Å both ways (esd 25e-6), Rwp 8.661 → 8.640 %. LaB₆ is the quiet
case by *net* power (f′ = −1.38 and f″ = 9.03 nearly cancel in |f|², −1.0 %) yet
still redistributes between the sites, since only La carries the correction:
B(La) +12 %, B(B) −22 %. Recorded as a characterisation.

End-to-end, the `DISPERSION_NEGLECTED` diagnostic fires on the off run and is
absent from the on run.

```sh
.venv/bin/python -m pytest tests/test_dispersion.py -q
.venv/bin/python -m pytest tests/test_acceptance_dispersion.py -q     # slow
.venv/bin/python -m pytest -q                                         # full suite
.venv/bin/python -m ruff check src tests examples
```

## References

- Cromer, D. T. & Liberman, D. (1970). *J. Chem. Phys.* **53**, 1891–1898 —
  relativistic calculation of anomalous scattering factors.
- Cromer, D. T. & Liberman, D. (1981). *Acta Cryst.* **A37**, 267–268 —
  the correction near absorption edges.
- Chantler, C. T. (1995). *J. Phys. Chem. Ref. Data* **24**, 71–643;
  (2000) **29**, 597–1056 — theoretical form factors / NIST FFAST.
- Kissel, L. & Pratt, R. H. (1990). *Acta Cryst.* **A46**, 170–175 —
  corrections to the Cromer-Liberman f′.
- Waasmaier & Kirfel (1995). *Acta Cryst.* **A51**, 416–431 — the f₀ this adds
  to (`crystallography/scattering.py`).
- *International Tables for Crystallography* Vol. C, §4.2.6 — f′, f″ at the
  common characteristic wavelengths; the independent check for the loader.
- McMaster, Del Grande, Mallett & Hubbell (1969), UCRL-50174 Sec. II Rev. 1 —
  the bundled cross sections the optical-theorem test runs against.
- Data: IUCr CPD QPA round robin, `tests/data/qarr/cpd-1*.prn`, `zincite.prn`;
  provenance in `tests/data/README.md`.

## Handover log

Append-only, newest first. An entry is REQUIRED before ending any session that
touched this WP — done / in flight / next / gotchas.

- **2026-07-27 (end of session)** — **all eight checklist items landed; the
  suite is green (523 fast + the `slow` acceptance, 36 new unit tests and 14 new
  acceptance tests).** The design in the entry below survived contact; what it
  did not anticipate is below.

  **The headline is the acceptance, not the feature.** Refitting the eight IUCr
  round-robin sample-1 mixtures under the identical v0.3 protocol with only the
  dispersion block added takes the QPA error from RMS **2.26 → 0.69 wt %** and
  worst |ΔW| **5.13 → 1.39**. That *re-derives a v0.3 conclusion*: the signed
  bias v0.3 attributed to untreated microabsorption is mostly this. WP-0310
  asked for exactly that re-derivation if the physics changed; the shape test is
  renamed `test_sample1_bias_has_the_dispersion_shape` with corrected reasoning
  (assertions untouched — that suite stays dispersion-off and comparable), and
  `milestones/v0.3.md` carries a dated superseded-explanation note. The
  prediction was written into this file *before* the refits and the refinement
  beat it (0.69 measured vs 0.83 predicted) even though `qpa_plan` frees Biso
  and could have re-absorbed the correction instead.

  **The single best illustration is not in the QPA numbers.** Pure ZnO: Rwp
  moves only 10.91 → 10.76 %, but **B(O) goes from 0.022 to 0.429 Å²**. With
  Zn's f′ = −1.55 neglected the model over-scatters Zn by ~10 %, and the only
  lever the refinement has to restore the Zn:O contrast is to drive B(O) to its
  floor — a displacement parameter spent absorbing a systematic. Rwp is not
  where this shows up; the ADPs are.

  **Four gotchas that cost real time, none of them the physics.**
  1. *Bit-identity constrains the fp association order, not just the algebra.*
     Factoring a shared `occ·dw` prefactor out of A and B is algebraically
     identical and moved two backend goldens by an ulp. `_orbit_terms` builds
     `occ·f·dw` in that order deliberately; there is a comment saying so.
  2. *`amp_b` must be (N,) on the anisotropic path too.* f″ carries no
     per-reflection Debye-Waller factor to spread it, so it came out a scalar,
     and the derivative kernels index `amp[:, None]`. Found only by building the
     `toy_anomalous` golden with an aniso site — a reason to put one there.
  3. *Do not trust recalled f′/f″ values.* Three of the seven I used to size the
     WP were wrong (Al's f′ and f″ swapped; Zr and La at Cu Kα badly off), which
     put wrong magnitudes in the first draft. Four independent tabulations agree
     with each other; recall does not. `gemmi.cromer_liberman` is already
     available and is the cheapest oracle.
  4. *The DABAX Chantler file is a licence trap.* It is the best data and it is
     in an MIT repo, and its own header restricts use to the ESRF over a live
     NIST SRD copyright. Read the `#UD` block of any DABAX file before bundling
     it.

  **Not done, deliberately** (all fenced in Non-goals): refining f′/f″,
  per-emission-line |F|² (guarded against instead — Ni's K edge between Cu Kα
  and Kβ is the test case), Kramers-Kronig f′ from the µ table, re-sourcing µ
  from f″, flipping the default to on. Also untouched: `multi.py` — a
  multi-histogram run compiles per histogram so each gets its own λ and its own
  f′/f″, which should just work, but is untested.

  **Next**, if reopened: nothing outstanding for v0.5. The one change that would
  multiply what shipped is flipping the default to on, which is a re-measurement
  of the whole validation matrix and is written into WP-1001's `### Inherited`.
- **2026-07-27** — expanded the stub into this WP (task 1). Design settled and
  the load-bearing claims *prototyped and measured* before writing, not
  asserted:
  1. **The powder average, not the representative.** `generate_reflections`
     merges ±h and evaluates |F|² at one representative — sound only while f is
     real. The exact fix is ⟨|F|²⟩ = |A|² + |B|² with A carrying f₀+f′ and B
     carrying f″ over the *same* orbit sums; verified against the explicit
     Laue-orbit average on ZnO `P 63 m c` to 5.1e-15, where the naive
     complex-f-at-the-representative is off by 1.2 %. It reduces bit-identically
     when f″ = 0 and needs no centro/non-centro case split.
  2. **Magnitude**: at Cu Kα the Bragg power moves −15.6 % (zincite), −13.2 %
     (zircon), −9.2 % (magnetite), −4.8 % (LaB₆), +6.9 % (fluorite), +6.2 %
     (corundum). Opposite signs across phases ⇒ QPA does not cancel.
  3. **The v0.3 QPA bias is largely this.** The parameter-free prediction
     reproduces the measured sample-1 signed errors (table above) and cuts their
     RMS from 2.26 to 0.77 wt %. Expect
     `test_sample1_bias_has_the_microabsorption_shape` to break — WP-0310 asked
     for exactly that, so re-derive it, do not silence it.
  4. **Bundle, do not depend.** µ stays on McMaster (it needs the *total* cross
     section; f″ is photoabsorption only — measured Rayleigh+Compton share
     0.6–4.4 % at Cu Kα), and the two tables cross-check via the optical theorem
     to 1–5.6 % across Z = 8→57. Default stays **off** so every milestone number
     stays valid; flipping it is WP-1001's re-measurement.

  **Next**: `crystallography/dispersion.py` and the bundled table — confirm the
  file's f1-vs-f′ convention (Z\*, not Z) before trusting any value.
- **2026-07-22** — created as a stub from the ROADMAP split.
</content>
</invoke>

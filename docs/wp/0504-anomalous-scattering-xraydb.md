# WP-0504 — Anomalous scattering f′, f″

Milestone: v0.5 · Status: 🔶 in progress
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
**double-digit-percent** error on the Bragg power of any 3d/4d-bearing phase,
and QPA divides one phase's scale by another's. Measured with a prototype
(`f′,f″` at Cu Kα1, total Σ m·|F|² over 2θ ≤ 110°, round-robin phases as the
acceptance test declares them):

| phase | Bragg power with f′,f″ ÷ without |
|---|---|
| corundum Al₂O₃ `R -3 c` | **+6.2 %** |
| fluorite CaF₂ `F m -3 m` | **+6.9 %** |
| LaB₆ `P m -3 m` | −4.8 % |
| magnetite Fe₃O₄ `F d -3 m:2` | −9.2 % |
| zircon ZrSiO₄ `I 41/a m d:2` | −13.2 % |
| zincite ZnO `P 63 m c` | **−15.6 %** |

Signs differ across phases (Zn/Fe/Zr sit *below* their K edges at 8.048 keV so
f′ is a large negative; Al/Ca sit above theirs so f′ is positive), so nothing
cancels into the scale — the *ratio* corundum:zincite moves by 26 %. That is
the whole QPA answer. See "Acceptance" for the pre-registered prediction this
makes about the already-measured v0.3 numbers.

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

### Data source: bundle a table, do not depend on xraydb

WP-0305 already made this call once for µ and this WP inherits the reasoning
(see `### Inherited`): the package bundles DABAX extracts (`f0_WaasKirf.dat`,
`mu_McMaster.dat`) rather than taking runtime dependencies, and xraydb drags
sqlalchemy. Bundle an f1f2 tabulation in the same `#S`-block DABAX format the
two existing loaders already parse.

Two conventions to pin when the file is chosen, both of which silently corrupt
values if got wrong:

1. Several DABAX f1f2 files tabulate **f1 = Z\* + f′** (Z\* = Z minus a small
   relativistic correction), not f′. Converting needs Z\*, not Z. Test it:
   far above every edge f′ must approach a *small negative constant*, not 0.
2. Sign of f″ (always ≥ 0 in the f = f₀ + f′ + i f″ convention used here).

**Do not** pull in periodictable's Henke tables — they cap at 30 keV and are
the wrong tool (locked decision, `../DESIGN.md`).

### The cross-check that makes the bundled table falsifiable

The optical theorem ties f″ to the photoabsorption cross section:

    σ_photo [barn] = 2 · r_e[Å] · λ[Å] · f″ · 1e8,   r_e = 2.8179403262e-5 Å

and `mu_McMaster.dat` already carries a **photoelectric column** from an
entirely independent compilation. Prototyped at Cu Kα1: the McMaster-implied
f″ agrees with published values to **1.0 (O) / 3.5 (Al) / 1.3 (Ca) / 1.1 (Fe) /
5.6 (Zn) / 4.4 (Zr) / 2.6 % (La)**. That is a real unit test across Z = 8→57,
and it is the reason µ stays on McMaster (below).

### Inherited

From **WP-0305** (Brindley, landed 2026-07-23), which explicitly deferred this
decision here — "revisit the coordination when WP-0504 actually needs f′/f″":
**xraydb was deliberately not pulled in** (it drags sqlalchemy); 0305 bundled
`data/mu_McMaster.dat`, an energy-trimmed (2–120 keV) three-column extract of
DABAX `CrossSec_McMaster.dat` (McMaster 1969), with ATTRIBUTION.md updated.

**This WP's call: keep µ on McMaster, add f′/f″ as a separate bundled table.**
Not a compromise — a physics fence. µ is *beam removal* and needs the total
cross section; f″ gives **photoabsorption only**. Measured at Cu Kα1 from the
bundled table, the scattering (Rayleigh + Compton) share of the total is 4.4 %
(O), 1.2 % (Al), 0.7 % (Ca), 0.6 % (Fe), 3.5 % (Zn), 2.0 % (Zr), 1.1 % (La) —
small but systematic and largest exactly where 0305 flagged McMaster as
weakest. Re-sourcing µ from f″ would therefore make µ *worse*, not better; the
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
- [ ] `crystallography/dispersion.py` + bundled data file + ATTRIBUTION.md:
      loader in the existing `#S`-block idiom, `dispersion(element, wavelength)
      -> (f′, f″)`, f1→f′ conversion with the Z\* convention pinned, edge-
      interval refusal, near-edge warning. Unit tests against published values
      at Cu/Mo Kα and the optical-theorem cross-check vs the McMaster
      photoelectric column.
- [ ] `schemas/instrument.py`: opt-in `Dispersion` block on `Source`
      (`overrides: {element: (f′, f″)}` for measured near-edge values),
      validators, JSON round-trip test.
- [ ] `crystallography/structure_factor.py`: the A/B Friedel-averaged form (1);
      `PhaseSites.f_anom` (per-atom complex, frozen);
      `compile_phase_sites(phase, wavelengths=…)`. Bit-identity golden when off;
      identity vs the explicit orbit average on a non-centrosymmetric group.
- [ ] Derivatives: `d_f2_d_xyz` and `d_f2_d_uaniso` in the A/B form; FD and jax
      `jacfwd` agreement; `toy_anomalous` backend golden (non-centrosymmetric,
      so it actually exercises B ≠ 0).
- [ ] `model/forward.py`: wire λ into the compile; line-spread guard
      (`LINE_DISPERSION_TOL`); `io/exporters.py` reports the Friedel-averaged
      |F|².
- [ ] `DISPERSION_NEGLECTED` diagnostic: fires when the block is absent and any
      species' |f′| or f″ exceeds a threshold fraction of Z at any line.
- [ ] Tests: unit/property + obs/calc/diff PNGs to `tests/output/`.
- [ ] Acceptance (below); re-derive
      `test_sample1_bias_has_the_microabsorption_shape` and record the measured
      numbers in the handover log.

## Acceptance

**Primary — IUCr round-robin sample 1a–1h, `tests/data/qarr/cpd-1*.prn`.**
This WP makes a *pre-registered, parameter-free* prediction about numbers that
were measured before it started. Neglecting dispersion inflates each phase's
fitted scale by r_p = (power with f′f″)/(power without) = 1.0616 (corundum),
0.8438 (zincite), 1.0690 (fluorite), so the recovered fractions are biased to
W_p ∝ w_p·r_p renormalised. Against the v0.3 measured errors:

| sample | corundum pred/meas | zincite pred/meas | fluorite pred/meas |
|---|---|---|---|
| 1a | +0.00 / +0.61 | −0.82 / −0.57 | +0.82 / −0.04 |
| 1b | +0.24 / −0.12 | −0.28 / −0.02 | +0.04 / +0.14 |
| 1c | +1.20 / +1.26 | −1.52 / −1.72 | +0.33 / +0.47 |
| 1d | +0.92 / +1.85 | −4.97 / −3.87 | +4.05 / +2.02 |
| 1e | +1.67 / +2.21 | −2.76 / −2.32 | +1.11 / +0.12 |
| 1f | **+3.41 / +3.17** | **−5.79 / −5.13** | **+2.38 / +1.96** |
| 1g | +2.28 / +2.39 | −5.04 / −3.91 | +2.76 / +1.52 |
| 1h | +2.22 / +2.17 | −4.68 / −3.72 | +2.45 / +1.54 |

All three signs reproduced in 7 of 8 mixtures, including **fluorite positive**,
which the microabsorption story could not explain. Subtracting the prediction
takes the RMS error from **2.26 → 0.77 wt %**.

Criterion: with dispersion on, the worst |ΔW| falls well below the v0.3 5.13
wt % (1f zincite) and the signed shape collapses — mean zincite error toward
zero rather than −2.7. *If it does not*, that is the finding and it gets
written up: the prediction above uses fixed Biso and scales, and a real
refinement will partly re-absorb the change into Biso — quantify how much
rather than tuning to the table.

**Structural — ZnO `P 63 m c` (`qarr/zincite.prn`), the non-centrosymmetric
case.** Unit-level: (1) matches the explicit Laue-orbit average to < 1e-12
relative. Real-data: refining zincite alone with dispersion on must not degrade
Rwp, and the cell must stay put (dispersion moves intensities, never positions).

**Negative control — SRM 660c LaB₆ (`nist_srm660c_100a.cif`).** `a` must be
unmoved within its esd (the **absolute** anchor; positions do not see f′), and
Rwp/Biso(La) recorded as a characterisation — La at Cu Kα carries f″ ≈ 9, so
Biso(La) is expected to move measurably, and that number is the deliverable.

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

# pxrd-refine

**API-first Rietveld refinement of powder X-ray diffraction data, designed for
automated and agentic workflows.**

`pxrd-refine` is an MIT-licensed Python package for Rietveld and Le Bail
refinement built as a library first — no GUI trees, no pickles, no hidden
state:

- **Typed, JSON-round-trippable schemas** (pydantic v2) for structures,
  instruments, patterns, plans, and results. Every schema exports JSON Schema
  for LLM tool-calling; unknown fields fail loudly with actionable errors.
- **numpy + scipy float64 core** (~50 MB install). Optional autodiff/GPU
  backends (JAX first) are on the roadmap; the forward model is written to
  stay differentiable (frozen reflection lists and evaluation windows per
  refinement stage, smooth reparameterisations, no clamps in the graph).
- **Documented mathematics**: every implemented equation cites its literature
  reference in the docstring (Rietveld 1969; Caglioti 1958; Thompson-Cox-
  Hastings 1987; Waasmaier-Kirfel 1995; Toby 2006; Le Bail 1988; …).
  See `ATTRIBUTION.md` for the full source/license map.
- **Automation-first background handling**: structured pattern diagnostics,
  BIC + Durbin-Watson order selection, and a penalized P-spline co-refined in
  the least squares — plus a guardrail that measures whether the background
  could imitate your ADPs and scales before it silently biases them.
- **Staged refinement strategies** following the IUCr guidelines
  (McCusker et al., 1999), with correlation, bound-hit and
  background-absorption guards.
- **Agent-native fit assessment**: the `FitReport` returns *numbers, not
  pixels* in three gated layers — model-free diagnostics, misfit attributed to
  physical causes ("peaks 0.008° low, 5 % weak"), and typed suggested actions
  the strategy engine can veto — so an agent can close the refinement loop
  without reading a plot image. Every layer is built to **abstain rather than
  guess**: collinear causes are reported as unresolved, not resolved wrongly.

## Status: v0.3 (pre-alpha)

Working today — constant-wavelength X-ray, both **capillary/synchrotron** and
**laboratory Bragg-Brentano** geometry:

| Capability | State |
|---|---|
| Rietveld & Le Bail modes, multi-phase | ✅ |
| CIF import/export (gemmi), space-group symmetry, absences, multiplicities | ✅ |
| TCHZ pseudo-Voigt, Caglioti widths, instrument ⊕ sample profile split, Lp | ✅ |
| Kα1/Kα2 doublet (per-line dispersion), FCJ axial asymmetry, Bragg-Brentano displacement/transparency | ✅ |
| Chebyshev / arPLS / SNIP / **penalized P-spline** backgrounds + auto-selection | ✅ |
| Bounded TRF least squares, **analytic Jacobian**, esds with Bérar-Lelann inflation | ✅ |
| Staged plans (`mccusker_default`, `lab_bragg_brentano`, `lab_calibrate`, `lab_sample_refine`, …) | ✅ |
| **FitReport Layers 0-2**: diagnostics → gated misfit attribution → typed actions | ✅ |
| `.xy` / `.xye` / GSAS raw / pdCIF readers; instrument-profile files | ✅ |
| Branchable history DAG: checkout, branch, **merge, cherry-pick**, replay | ✅ |
| matplotlib plots, **VLM montage**, plotly HTML viewer, `pxrdref watch` live view | ✅ |
| Atomic-coordinate refinement (Wyckoff/site-symmetry constraints), anisotropic ADPs | ✅ |
| QPA weight fractions (Hill-Howard ZMV), Brindley microabsorption + µR fence | ✅ |
| Pawley whole-pattern mode, March-Dollase preferred orientation | ✅ |
| Stephens anisotropic strain (hkl-dependent widths; Laue-allowed S_HKL derived, not tabulated) | ✅ |
| Anomalous scattering f′, f″ (Cromer-Liberman; Friedel-averaged \|F\|², opt-in per source) | ✅ |
| Multi-histogram joint refinement (shared structure, per-histogram Rwp) | ✅ |
| Exporters: reflection table, refinement CIF (values + esds), QPA table | ✅ |
| Differentiable backends: JAX autodiff Jacobians, torch/MPS; true Voigt; restraints | v0.4 |
| Fundamental Parameters Approach, neutron/TOF, texture | v2 |

Milestones are tracked in [docs/ROADMAP.md](docs/ROADMAP.md), which indexes
per-task work packages ([docs/wp/](docs/wp/)), the design rationale
([docs/DESIGN.md](docs/DESIGN.md)), and the measured acceptance records of
shipped milestones ([docs/milestones/](docs/milestones/)).

### Validation

Seven real-data acceptance suites, each with its tolerance chosen to match what
the reference actually is:

| Dataset | Result | Reference |
|---|---|---|
| APS 11-BM **NAC** (synchrotron) | a = 10.251285(12) Å, Rwp 9.2 % | CaF₂ impurity auto-flagged by the FitReport from unmatched fluorite 111/220/311/422 peaks |
| NIST **SRM 660c** LaB₆ (lab CuKα) | a = 4.156895(25) Å, Rwp 8.7 % | +28 ppm vs NIST's recomputed cell for this dataset — an **absolute** anchor |
| GSAS-II **fluorapatite** tutorial | Rwp 9.73 %, Rp 7.76 % | GSAS's own 10.05 % / 7.66 % on identical channels; cell +116 ppm — a **cross-code consistency** check |
| SRM 676a **corundum** (lab CuKα) | c/a = 2.729928 (+30 ppm) | the axial ratio where uniform d-scale systematics cancel — a **certificate-grade** anchor; absolute axes carry a ~−300 ppm lab d-scale offset |
| IUCr **CPD QPA round robin** (samples 1a–h, 2, 4) | worst 5.1 wt % (sample 1); traces ≤ 1.3 wt % | tolerance referenced to the published **participant spread**; sample 4 is the designed Brindley-defeating case (µR fence fires, no accuracy band claimed) |
| IUCr round robin **with f′, f″ applied** | worst 1.4 wt %, RMS 0.69 (was 5.1 / 2.26) | a **pre-registered prediction**: the parameter-free bias from neglecting anomalous scattering was written down before the refits, and re-derives the v0.3 shape v0.3 had attributed to microabsorption. Pure ZnO: Rwp barely moves, B(O) 0.02 → 0.43 Å² |
| CPD **brucite** / **corundum** (anisotropic strain) | brucite Rwp 18.55 → 17.90 %, ΔBIC +488 — *and rejected* | a **characterisation**: the improvement passes both statistical tests yet drives the strain variance negative on 12 of 43 reflections, so the cone guard fires and no S_HKL are quotable. Corundum is the isotropic control (ΔBIC −17, diagnostic 1.60×, not detected) |

The SRM 660c fit does **not** reach the certificate's ±8×10⁻⁶ Å band, and does
not claim to: the residual is a characterised cotθ/sin2θ aberration
(flat-specimen divergence, tube tails, monochromator passband) that belongs to
the fundamental-parameters work fenced for v2. That gap is documented rather
than tuned away — see [docs/milestones/v0.2.md](docs/milestones/v0.2.md).

The FitReport's confidence numbers are calibrated by **synthetic misfit
injection**: perturb exactly one known cause, assert the report recovers it,
ranks it first, and reports *low* confidence when causes are deliberately
made collinear. Run `pytest` (~2 min, includes all of the above; `pytest -m
"not slow"` is ~20 s), `python examples/nac_11bm.py` (synchrotron walkthrough) or
`python examples/srm660c_lab.py` (lab walkthrough: diagnostics → refinement →
all three FitReport layers → plots + interactive HTML).

## Example

```python
import pxrdref as pr

data = pr.read_pattern("11BM_NAC.fxye")                  # esds read from file
structure = pr.Structure.from_cif("NAC.cif")
instrument = pr.Instrument.debye_scherrer(wavelength=0.4139090)

# Structure-free Le Bail first: cell + profile + background
ref = pr.Refinement(structure, instrument)
lebail = ref.fit(data, mode="lebail", two_theta_limits=(2, 24))

# Rietveld with the standard staged turn-on order (McCusker et al. 1999)
result = ref.fit(data, plan="mccusker_default", two_theta_limits=(2, 24))
print(result.statistics.rwp, result.statistics.gof)
print(result.parameter("phases.0.cell.a"))               # value ± stderr

report = ref.report()                                     # agent-native JSON
print(report.summary)                                     # regions, unmatched peaks
result.plot(path="fit.png")                               # obs/calc/diff/ticks
```

### Laboratory data

```python
data = pr.read_pattern("sample.xrdml.xy")
instrument = pr.Instrument.bragg_brentano(radiation="CuKa",      # Kα1/Kα2 doublet
                                          monochromator_two_theta=26.6)
instrument.background = pr.background.auto_background(data)       # diagnose → select → build

ref = pr.Refinement(structure, instrument)
result = ref.fit(data, plan="lab_bragg_brentano")   # + displacement, Kα2 ratio, FCJ axial
```

Calibrate on a standard once, then reuse the instrument for every sample:

```python
cal = pr.Refinement(lab6_certified, instrument)      # certified cell held fixed
cal.fit(standard_data, plan="lab_calibrate")
pr.save_instrument_profile(cal.fitted_instrument, "diffractometer.json")

frozen = pr.load_instrument_profile("diffractometer.json")   # everything vary=False
ref = pr.Refinement(unknown, frozen)
ref.fit(sample_data, plan="lab_sample_refine")   # only sample size/strain, cell, scale…
```

### Fit assessment an agent can act on

```python
report = ref.report(plan="lab_bragg_brentano")

for region in report.attribution:            # Layer 1: physical causes, gated
    if region.gates_passed:
        print(region.two_theta_lo, [(c.kind, c.value) for c in region.coefficients])
    else:
        print("not readable here:", region.gate_failures)

for action in report.suggested_actions:      # Layer 2: typed, advisory
    if action.active:                        # (the strategy engine holds the veto)
        print(action.kind, action.confidence, action.alternatives, action.rationale)

outcome = pr.report.predict_then_verify(ref, data, report.suggested_actions[0])
print(outcome.accepted, outcome.reason)      # tried on a branch; rolled back if it didn't help
```

`report.abstained_reason` is set when the fit is too immature to attribute
misfit to specific parameters — the report says so instead of guessing.

### Exporting results

Three exports, in the forms other people and other codes actually consume:

```python
ref.write_reflection_table("refl.csv")   # hkl, d, 2θ, |F|², I, multiplicity —
                                         # one row per (emission line, reflection)
ref.write_cif("refinement.cif")          # structure with esds + R-factors,
                                         # wavelength, profile/background, pattern
ref.write_qpa_table("qpa.csv")           # Hill-Howard weight fractions, with the
                                         # "crystalline content only" caveat inline

# or as plain functions / typed objects
rows = ref.reflection_table()            # list[ReflectionRow], both Kα lines present
pr.write_refinement_cif(result, ref.fitted_structure, ref.fitted_instrument, "r.cif")
```

The refinement CIF round-trips through the package's own readers —
`pr.read_pdcif("refinement.cif")` recovers the pattern and
`pr.Structure.from_cif("refinement.cif")` the structure — and refined values
carry their standard uncertainty in `4.59370(25)` notation (`pr.format_su`).

### Live monitoring

```python
from pxrdref.viz.live import LiveSession
ref.fit(data, events=LiveSession("live/"))   # rewrites live/fit.html per stage
```

```sh
pxrdref watch live/     # stdlib http.server: auto-refreshing plot + event console
```

Everything is JSON-serialisable end to end:
`structure.model_dump_json()` / `Structure.model_validate_json(...)`, and the
same for instruments, results, reports, and history nodes. (Staged plans are
dataclasses for their positional constructor; `schemas.history.PlanSpec` is
their round-trippable mirror.)

## Branchable refinement history

Every stage auto-commits a restorable checkpoint, so you can back up and try a
different strategy instead of re-running from scratch — and an agent can
search over strategies the same way.

```python
ref = pr.Refinement(structure, instrument, history="session.jsonl")
ref.fit(data, plan="lab_bragg_brentano")
ref.history.tag(ref.history.head, "baseline")
print(ref.history.summary())          # indented tree, Rwp per node

ref.checkout("baseline")              # restore that exact state
ref.run_stage(data, pr.Stage("axial", ["instrument.geometry.axial_*"]))
ref.history.compare([n.id for n in ref.history.leaves()])
ref.checkout(ref.history.best("rwp").id)

rival = ref.branch("baseline")        # a second working tree, same history
rival.run_stage(data, pr.Stage("strain", ["phases.*.lor_strain"]))
ref.merge(rival.result_.node_id)      # three-way merge against the common ancestor
ref.cherry_pick(some_node_id, data)   # replay another node's stage action here
```

Nodes store *state*, not curves (~10 kB each, versus ~1.2 MB if the fitted
pattern were embedded), so wide branching is cheap; `pr.replay(tree, node_id,
data)` recomputes the curves on demand. The log is append-only JSONL, and each
node carries the API call that produced it, so a session doubles as a
reproducible script. Pass `history=False` for a zero-overhead plain fit.

## Install (development)

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"
pytest              # 354 tests incl. five real-data acceptance suites (~2 min)
pytest -m "not slow"    # 336 unit/property tests only (~20 s)
ruff check src tests examples
```

Extras: `[viz]` (matplotlib, plotly), `[baselines]` (pybaselines algorithm zoo).

## Architecture (one paragraph)

Pydantic schemas are the source of truth. `params/vector.py` compiles the
model tree once per stage into a flat float64 vector (crystal-system cell
ties applied as identity constraints; softplus/logit transforms keep widths,
scales, and occupancies physical). `model/forward.py` freezes the reflection
list, symmetry-operation orbits, and per-reflection evaluation windows for
the stage, then evaluates y_calc = background + Σ intensity·profile.
`optimize/least_squares.py` drives scipy's bounded TRF with an analytic
Jacobian — exact per-point profile derivatives chained through cheap
per-reflection scalars, with finite differences only as a fallback — and
derives esds from the covariance matrix with Bérar-Lelann inflation.
`strategy/staged.py` walks the turn-on plan, regenerating frozen state
between stages and running the guards. `report/` turns the result into
machine-readable diagnostics in three gated layers, reusing the same
derivative bases the Jacobian is built from.

## License

MIT. Algorithms are independent implementations from the published
literature; inspiration sources and data provenance are documented in
`ATTRIBUTION.md` and `tests/data/README.md`. GPL codebases (BGMN, Profex,
xrayutilities) were studied conceptually only — no code was ported.

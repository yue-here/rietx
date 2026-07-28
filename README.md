# pxrd-refine

**API-first Rietveld refinement of powder X-ray diffraction data, designed for
automated and agentic workflows.**

`pxrd-refine` is an MIT-licensed Python package for Rietveld and Le Bail
refinement built as a library first — no GUI trees, no pickles, no hidden
state:

- **Typed, JSON-round-trippable schemas** (pydantic v2) for structures,
  instruments, patterns, plans, and results. Every schema exports JSON Schema
  for LLM tool-calling; unknown fields fail loudly with actionable errors.
- **numpy + scipy float64 core** (~50 MB install), with optional autodiff
  backends behind the `[jax]` and `[torch]` extras: `backend="jax"` /
  `"torch"` / `"torch-mps"` swap in an exact forward-mode Jacobian, and every
  one is held to per-column agreement with the analytic assembly in CI. The
  numpy path is the default and the fast one; `[torch]` is **experimental**,
  never installed by default, and earns its place as an independent check on
  the analytic Jacobian rather than as a speedup. The forward model is written
  to stay differentiable (frozen reflection lists and evaluation windows per
  refinement stage, smooth reparameterisations, no clamps in the graph). GPU columns run fp32 — the residual and the solve are always
  fp64 on host, because JᵀJ squares the condition number. Reported honestly:
  Apple-GPU execution is currently *slower* than numpy (the peak loop is
  dispatch-bound, not arithmetic-bound), so `torch-mps` today buys precision
  validation rather than speed.
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

## Status: v0.4 shipped, v0.5 in progress (pre-alpha)

v0.4 is recorded with measured acceptance in
[docs/milestones/v0.4.md](docs/milestones/v0.4.md); the v0.5 rows marked below
have landed but the milestone has not closed (see
[docs/ROADMAP.md](docs/ROADMAP.md) for what remains). Working today —
constant-wavelength X-ray in three geometries — **capillary/synchrotron**,
**laboratory Bragg-Brentano** and **flat-plate transmission**:

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
| **Sequential series** (in-situ/parametric): warm-started chain, parameter trajectories, forward-vs-backward path-dependence check | ✅ |
| Exporters: reflection table, refinement CIF (values + esds), QPA table | ✅ |
| Differentiable backends (`backend="jax"` / `"torch"` / `"torch-mps"`), held to per-column Jacobian agreement | ✅ |
| True Voigt peak shape (shared Faddeeva `w(z)`; TCHZ still the default) | ✅ |
| Soft bond / angle / value restraints (Rietveld, single-histogram) | ✅ |
| Capillary (cylindrical) absorption, µR computed from composition — unbiases Biso, cannot change Rwp | ✅ |
| Flat-plate absorption (ITC 6.3.3.1 finite-thickness reflection + symmetric transmission), µt computed from composition | ✅ |
| Surface roughness (Suortti 1972 / Pitschke 1993), Bragg-Brentano, with identifiability fences | ✅ |
| Secondary extinction (Sabine polycrystalline blend) | ✅ |
| Fundamental Parameters Approach, neutron/TOF, texture | v2 |

Milestones are tracked in [docs/ROADMAP.md](docs/ROADMAP.md), which indexes
per-task work packages ([docs/wp/](docs/wp/)), the design rationale
([docs/DESIGN.md](docs/DESIGN.md)), and the measured acceptance records of
shipped milestones ([docs/milestones/](docs/milestones/)).

**Driving this from an agent?** Read
[docs/AGENT_PROTOCOL.md](docs/AGENT_PROTOCOL.md) first — the turn-on order, the
degeneracies to memorise, how to read the abstentions, what every diagnostic
code forbids you from reporting, and ten measured findings that change how an
automated operator should behave (starting with: a correction that provably
cannot improve Rwp can still be the one you need).

### Validation

Eight real-data acceptance suites, each with its tolerance chosen to match what
the reference actually is:

| Dataset | Result | Reference |
|---|---|---|
| APS 11-BM **NAC** (synchrotron) | a = 10.251285(12) Å, Rwp 9.2 % | CaF₂ impurity auto-flagged by the FitReport from unmatched fluorite 111/220/311/422 peaks |
| NIST **SRM 660c** LaB₆ (lab CuKα) | a = 4.156895(25) Å, Rwp 8.7 % | +28 ppm vs NIST's recomputed cell for this dataset — an **absolute** anchor |
| GSAS-II **fluorapatite** tutorial | Rwp 9.73 %, Rp 7.76 % | GSAS's own 10.05 % / 7.66 % on identical channels; cell +116 ppm — a **cross-code consistency** check |
| SRM 676a **corundum** (lab CuKα) | c/a = 2.729928 (+30 ppm) | the axial ratio where uniform d-scale systematics cancel — a **certificate-grade** anchor; absolute axes carry a ~−300 ppm lab d-scale offset |
| IUCr **CPD QPA round robin** (samples 1a–h, 2, 4) | worst 5.1 wt % (sample 1); traces ≤ 1.3 wt % | tolerance referenced to the published **participant spread**; sample 4 is the designed Brindley-defeating case (µR fence fires, no accuracy band claimed) |
| IUCr round robin **with f′, f″ applied** | worst 1.4 wt %, RMS 0.69 (was 5.1 / 2.26) | a **pre-registered prediction**: the parameter-free bias from neglecting anomalous scattering was written down before the refits, and re-derives the v0.3 shape v0.3 had attributed to microabsorption. Pure ZnO: Rwp barely moves, B(O) 0.02 → 0.43 Å² |
| APS 11-BM **SRM 660a** LaB₆ (capillary, 0.81 mm bore) | Rwp and cell invariant to 3e-8 / 8e-12 Å; every Biso +0.0166542 Å² | the capillary absorption correction's claim, on real data: it is an *exact reparameterisation* of {scale, Biso}, so the predicted ΔB is the only observable. λ is beamline-calibrated on this standard, so the cell here is a consistency check and **not** an anchor |
| CPD **brucite** / **corundum** (anisotropic strain) | brucite Rwp 18.55 → 17.90 %, ΔBIC +488 — *and rejected* | a **characterisation**: the improvement passes both statistical tests yet drives the strain variance negative on 12 of 43 reflections, so the cone guard fires and no S_HKL are quotable. Corundum is the isotropic control (ΔBIC −17, diagnostic 1.60×, not detected) |

Plus one validation suite that has no reference dataset because its subject is
the code itself: **cross-backend Jacobian agreement**. Every way the package can
produce a Jacobian — the analytic peak-chain assembly, central differences, JAX
`jacfwd`, torch, and each of those under the fp32-column policy — is compared
column by column on the same compiled state, across eight configurations
(Rietveld, Le Bail, Pawley, anisotropic ADPs / preferred orientation /
extinction, true Voigt, restraints, and two real patterns), the stacked
multi-histogram layout, and across stage-boundary recompiles. An
**all-fp32 Apple-GPU refinement of SRM 676a lands 3.5×10⁻⁸ Å from the numpy
fp64 cell**, because the residual and the solve are fp64 on host whatever the
columns are computed in — see
[docs/milestones/v0.4.md](docs/milestones/v0.4.md).

The SRM 660c fit does **not** reach the certificate's ±8×10⁻⁶ Å band, and does
not claim to: the residual is a characterised cotθ/sin2θ aberration
(flat-specimen divergence, tube tails, monochromator passband) that belongs to
the fundamental-parameters work fenced for v2. That gap is documented rather
than tuned away — see [docs/milestones/v0.2.md](docs/milestones/v0.2.md).

The FitReport's confidence numbers are calibrated by **synthetic misfit
injection**: perturb exactly one known cause, assert the report recovers it,
ranks it first, and reports *low* confidence when causes are deliberately
made collinear. Run `pytest` (~14 min, includes all of the above; `pytest -m
"not slow"` is ~2.5 min), `python examples/nac_11bm.py` (synchrotron walkthrough) or
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
# also "CrKa" / "FeKa" / "CoKa" / "MoKa" / "AgKa", or any of them suffixed "1"
# for a Kα1-only monochromated beam (2θ_m above is a Cu number — recompute it)
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

### Comparing settings — "does this correction actually help?"

```sh
pxrdref compare --open    # pick a standard, tick variants, read the Δχ² panel
```

A browser UI (same stdlib-http, offline-plotly architecture as `watch`) that
refines a bundled standard under several settings and draws the comparison the
eye cannot do from two Rietveld panels: **cumulative Δχ² against a reference
variant**, where a falling curve is a variant winning and the *slope* says at
which angles it won. That distinction matters, because some corrections here
provably cannot move Rwp at all and others improve it by absorbing physics that
belongs elsewhere — so the statistics table and the structured diagnostics sit
beside the plots rather than under them.

The registry is a plain API too:

```python
from pxrdref.viz import compare
base = compare.run("zincite", "baseline")
disp = compare.run("zincite", "dispersion")   # Rwp barely moves; B(O) 0.02 → 0.43 Å²
```

Its standards *are* the acceptance suites' protocols — asserted field by field
in `tests/test_compare_ui.py`, so a comparison run here is comparable with the
recorded acceptance numbers.

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
pytest              # 953 tests incl. eight real-data acceptance suites (~24 min)
pytest -m "not slow"    # 873 unit/property tests only (~3.3 min)
ruff check src tests examples
```

Extras: `[viz]` (matplotlib, plotly), `[baselines]` (pybaselines algorithm zoo),
`[jax]` (autodiff Jacobians) and `[torch]` (**experimental** — an independent
check on the analytic Jacobian and a route to differentiable-layer use, not a
faster path; never installed by default). Every backend row in the agreement
and conformance suites self-skips when its package is absent, so a numpy-only
checkout is fully green.

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

# CLAUDE.md — pxrd-refine

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64
core, pydantic v2 schemas, gemmi for CIF/symmetry. Import name: `pxrdref`.

## Commands

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup (once)
uv pip install -e ".[dev,jax,torch]"                   # + optional jax/torch backends
.venv/bin/python -m pytest                             # full suite ~24 min (953 tests), incl. real-data acceptance
.venv/bin/python -m pytest -m "not slow"               # skip acceptance (873 tests, ~3.3 min)
.venv/bin/python -m pytest tests/test_cross_backend.py # Jacobian agreement matrix; rows self-skip without their backend
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
.venv/bin/pxrdref watch <live-dir>                     # live viewer for a LiveSession run
.venv/bin/pxrdref compare --open                       # settings-comparison UI on the standards
```

`pxrdref compare` is the fastest way to answer "does this new correction
actually help?": pick a standard, tick variants, and read the **cumulative
Δχ² vs reference** panel, which localises *where* a change acted rather than
only whether Rwp moved. Registry + runner in `viz/compare.py` (also usable
headlessly as `compare.run(standard, variant)`); server/page in
`compare_app.py`. Its standards are the acceptance suites' protocols, and
`tests/test_compare_ui.py` asserts that field-by-field so the two cannot
drift — **add a row there whenever a new correction lands.**

## Data flow

```
Structure/Instrument/PatternData (schemas/, pydantic, JSON round-trip)
  → ParameterTable (params/vector.py): tree → flat fp64 θ, dot-paths
    ("phases.0.cell.a", "instrument.profile.w", "instrument.background.c2"),
    crystal-system cell ties (b←a etc.), softplus/logit transforms
  → CompiledModel (model/forward.py): per-stage frozen state — reflection list
    (crystallography/symmetry.py, gemmi), per-atom symmetry-op subsets
    (structure_factor.py), per-(emission line, reflection) point windows,
    FCJ quadrature node counts (profiles/fcj.py), background design matrix
    (+ P-spline penalty rows); derivative_bases() serves both the analytic
    Jacobian and FitReport Layer 1 from one expansion
  → run_least_squares (optimize/least_squares.py): scipy TRF, bounds,
    analytic peak-chain Jacobian (FD fallback), esds from χ²·(JᵀJ)⁻¹ ×
    Bérar-Lelann inflation
  → staged runner (strategy/staged.py) loops stages, guards, recompiles
  → RefinementResult (schemas/results.py) → FitReport (report/, 3 layers)
    → plot / plot_for_vlm / write_html (viz/)
  → history DAG (history/, schemas/history.py): every stage auto-commits an
    immutable restorable node; checkout/run_stage/branch to fork a strategy,
    merge/cherry_pick to recombine, replay to recompute a node evaluate-only,
    append-only JSONL to persist; history/events.py streams per-iteration
    events, viz/live.py + watch.py render them live
```

A **series** (in-situ ramp, parametric sweep, tray of related specimens) is N
separate refinements chained by a warm start — `sequential.py`
(`SequentialRefinement` / `refine_sequential`), returning a `SeriesResult` of
per-pattern summaries plus parameter *trajectories*, one history tree per
pattern (a tree is pinned to its pattern by `TreeHeader.data_fingerprint`),
linked by annotation notes. Not to be confused with `multi.py`, which stacks
patterns into **one joint residual**. A chained fit is worth ≈3× in iterations
and nothing in accuracy, and its trajectory is path-dependent by construction,
so `direction="both"` runs the chain each way and flags parameters the two
disagree on (`SEQUENTIAL_PATH_DEPENDENT`) — the only check that separates a
measured trajectory from an ordering artefact.

Entry points: `Refinement.fit()` / `refine()` in `refine.py`; modes
`"rietveld"`, `"lebail"` (intensity partitioning in
`CompiledModel.lebail_update`) and `"pawley"` (per-hkl intensities refined as
an off-table θ block — `model.forward.PawleyBlock`, appended in
`run_least_squares`; overlapped groups get equal-split restraints and come back
flagged `PAWLEY_OVERLAP_UNRESOLVED` rather than confidently split).

## Invariants (do not break)

- **Frozen-per-stage discreteness**: the hkl list, symmetry-op subsets, FCJ
  quadrature node counts, and window index ranges are computed at stage
  compile and NEVER change during a least-squares run; regenerate only
  between stages. This keeps the residual smooth for FD/autodiff Jacobians.
  (FCJ node *positions* follow the parameters smoothly, with the quadrature
  split at the overlap-trapezoid kink — see profiles/fcj.py.)
- **fp64 everywhere** in the core; a GPU backend may compute Jacobian
  *columns* in fp32 but the residual used for cost/statistics and the solve
  stay fp64 on host — `backend/linalg64.py` is that boundary, and it holds on
  real hardware: an Apple-MPS refinement whose every column was computed in
  fp32 lands 3.5e-8 Å from the numpy fp64 cell, because the trust region
  re-measures each step against an fp64 cost.
- **No pydantic in the hot loop**: `ParameterTable.decode()` returns a plain
  dict; the forward model consumes floats/arrays only.
- **Weights**: use the file's esd column when present (readers), Poisson
  √max(y,1) only as fallback. Never subtract an estimated background —
  hold it additively (`BackgroundFixedPlusChebyshev`) or co-refine it under
  a smoothness penalty (`BackgroundPSpline`).
- **Background flexibility is a correctness question, not a cosmetic one.**
  A background able to imitate the peaks biases ADPs up and scales (hence QPA
  fractions) down while Rwp *improves*. Measure it as the block projection
  R² of a structural Jacobian column onto the background column span
  (`optimize.statistics.background_absorption`) — pairwise ρ misses it
  entirely (~0.2 per coefficient while the block absorbs ~46 %).
- **Reciprocal-space symmetry action is Rᵀ** (transposed rotation) — matters
  for non-cubic orbit/multiplicity counting (see symmetry.py comment).
- **Every physics function cites its reference** (author, year, journal) in
  the docstring, and documents conventions by physics not letters (e.g.
  size↔1/cosθ, strain↔tanθ; GSAS and FullProf swap X/Y labels).
- **The FitReport must never return a confident wrong singleton.** Every
  Layer-1 statement passes four gates (resolvability on the *scale-normalised*
  Gram, 0.4·FWHM validity radius, local-χ²_red significance, share-based
  global maturity); collinear angular templates are compared as *nested single
  fits* and reported non-separable rather than resolved. Confidence weights
  importance (share of χ²), not just statistical significance.
- **Licensing**: port code only from permissive sources with ATTRIBUTION.md
  updates. BGMN/Profex/xrayutilities are GPL — concepts only, never code.
  TOPAS/FullProf are closed — papers only.

## Conventions

- Parameter paths are dot-separated, glob-matched with fnmatch in stage plans
  (`"phases.*.cell.*"`). No brackets in paths (fnmatch treats `[..]` as class).
- Schemas: `extra="forbid"`, `ser_json_inf_nan="strings"` (±inf bounds must
  survive JSON round-trip — tested).
- Angles in degrees throughout; Caglioti U,V,W in deg²(2θ); Biso in Å²
  (= 8π²·Uiso); wavelengths in Å; k = sinθ/λ.
- **Hot-path code must not put a frozen numpy constant on the left of a python
  operator against a θ-derived value** — `ndarray * tensor` raises on the torch
  backend (and `tensor * ndarray` routes through numpy's deprecated
  `__array_wrap__`, then fails under a functorch transform). Route it through
  `xp.matmul` or lift it with `xp.asarray(c, dtype=np.float64)`; both are no-ops
  on numpy. Same rule for a *new op*: add it to `_OP_NAMES` and implement it on
  every backend — `tests/test_backend_conformance.py` fails, for every
  registered backend at once, if you don't.
- **Two things are written once and consumed everywhere; never restate either.**
  The residual **row layout** `[data | background-penalty | Pawley-restraint |
  soft-restraint]` lives in `model/rows.py` (`BLOCK_ORDER`, `layout()`,
  `assemble()`) — the numpy residual, the numpy Jacobian's row offsets and every
  traced residual build from it, so a new block is one edit. The **traced twin**
  of `decode`/residual lives in `backend/traced.py`, parameterised by `xp` — jax
  and torch share it, and a new backend inherits it. Adding a backend means
  adding a name to `backend.api.BACKEND_NAMES` and a row to
  `test_cross_backend.METHODS`; the conformance suite's meta-test fails if you
  do the first without the second.
- **Traced code runs inside `backend.traced.active(xp)`** — it makes `xp` the
  globally-bound backend *and* opens the backend's `full_precision()` scope.
  jax's fp64 is scoped, so a constant (or a θ vector) materialised outside it
  is silently float32: this cost the Pawley aux columns four orders of accuracy
  once, and is why constants are lifted inside the traced call, not at closure
  build.
- **Specimen absorption is one seam, three geometries, and their "off" states
  disagree** (`model/absorption.py`, `CompiledModel._absorption`). Capillary:
  `Geometry.mu_r`, Rouse (1970), off at µR = 0, and *exactly* a
  reparameterisation of {scale, Biso} — Rwp provably cannot move, the whole
  content is ΔB = c(µR)·λ²/2 (measured on real 11-BM SRM 660a data:
  ΔRwp 3e-8, every Biso +0.0166542 Å² against a predicted 0.0166542). Flat plate:
  `Geometry.mu_t`, ITC Table 6.3.3.1 case (2) under `bragg_brentano` and case
  (3a) under `flat_plate_transmission`, **off at µt = ∞** (thick specimen, ITC
  (1a), the assumption every flat-plate fit here made before v0.5) — so `mu_t`
  absent ≠ `mu_t = 0`, which is a specimen of no thickness and raises. It is
  *not* an exact reparameterisation (1-40 % of ln A survives the projection), so
  it moves Rwp, its ΔBiso is an order of magnitude larger and negative, and on a
  genuinely thick specimen declaring a thickness correctly makes the fit worse.
  Neither µR nor µt is refinable: µR is exactly singular, µt is merely
  ill-conditioned and knowable from the specimen, and the difference is recorded
  rather than smoothed over.
- **Instrument ⊕ sample profile split**: Gaussian *variances* add
  (instrument U,V,W + phase `gauss_size`/`gauss_strain`), Lorentzian *FWHMs*
  add (instrument X,Y + phase `lor_size`/`lor_strain`). Workflow:
  `lab_calibrate` on a standard with its **certified cell held fixed** (that
  is what decorrelates zero/displacement/cell) → `save_instrument_profile` →
  `load_instrument_profile` (everything `vary=False`) → `lab_sample_refine`.
- Atomic coordinates refine as site-symmetry DOFs: `ParameterTable` wires
  `phases.i.atoms.j.dof.k` (one per allowed direction from
  `crystallography/wyckoff.py`) and affine-ties x/y/z to them; free them with
  the `phases.*.atoms.*.dof.*` glob (the `mccusker_structural` plan does).
  Fully fixed special positions get locked coords — `vary=True` there raises.
- **Anisotropic ADPs are opt-in per atom** (`Atom.aniso`, CIF U^ij in Å²) and
  refine the same way: `phases.i.atoms.j.adp.k` patterns from
  `wyckoff.adp_basis`, freed by the `phases.*.atoms.*.adp.*` glob that every
  displacement stage carries alongside `…biso`. Unlike coordinate DOFs they
  are **absolute** (U = Σₖ θₖ·Bₖ), which enforces the site symmetry exactly;
  a tensor outside the allowed subspace raises rather than being symmetrised.
  Three representations, all named in `crystallography/adp.py` — the stored
  CIF **U^ij**, the fractional-space **U\*** = U^ij·a\*ᵢa\*ⱼ that the structure
  factor uses (U\* is what transforms as R·U·Rᵀ, making `Rᵀh` on the parent
  *identically* the image's tensor), and **U_cart** where eigenvalues and
  U_eq are physical. The isotropic limit is U^ij = Uiso·G\*ᵢⱼ/(a\*ᵢa\*ⱼ), **not**
  Uiso·δᵢⱼ except for orthogonal reciprocal axes. Non-positive-definite
  tensors raise an `ADP_NOT_POSITIVE_DEFINITE` diagnostic (the Debye-Waller
  factor diverges at high Q, so this is not cosmetic); positive-definiteness
  is not enforced by bounds, since the constraint couples all six components.
  `structure_from_cif(..., aniso=True)` is opt-in — several test CIFs carry
  aniso loops, and reading a file must not silently change what a plan frees.
- **Anisotropic strain is opt-in per phase** (`Phase.microstrain`, Stephens
  1999) and is the first width that depends on hkl rather than only on θ:
  σ²(M) = 10⁻¹²·Σ S_HKL h^H k^K l^L adds Λ(hkl)·tanθ to the *Lorentzian* FWHM.
  Same shape as the ADP story one rank up — the Laue-allowed S_HKL patterns are
  **derived** from the operators (`crystallography/stephens.py`, exact rational
  nullspace of the induced rank-4 action, sharing `wyckoff._nullspace_int`),
  refine as absolute DOFs `phases.i.microstrain.dof.k`, and an out-of-subspace
  set raises. Three conventions are load-bearing and stated in that module:
  √Σ·d²·10⁻⁶ is the **FWHM** (not σ) of the ΔM/M distribution; the coefficients
  are in **10⁻¹² Å⁻⁴** (physical Å⁻⁴ values ~10⁻⁸ would be finite-differenced
  with a step 100× their own size); and they multiply the **literal** monomials,
  where other codes fold symmetry multiplicities in. A block **locks
  `lor_strain`** — its isotropic direction is identically that column, the
  `biso`/`aniso` bargain again — so the block subsumes it, and it must be freed
  *in* the sample-broadening stage, not after. The isotropic limit S = ε²·[M²]
  (exactly in the subspace, whatever the symmetry) is both the seed and the only
  legal start: at S ≡ 0 the √ has unbounded slope, so `Stage.strain_seed`, not
  `Stage.seed`, which reaches softplus entries only. σ²(M) ≥ 0 is a *cone*
  coupling all fifteen, hence a guard (`STEPHENS_STRAIN_NOT_POSITIVE`) rather
  than bounds — and measured on real data it fires on isotropic and anisotropic
  specimens alike, so read it as "these coefficients are not quotable", never as
  evidence *of* anisotropy.
- **Anomalous scattering is opt-in per source** (`Source.dispersion`, f = f₀ +
  f′ + i·f″ from bundled Cromer-Liberman `data/f1f2_CromerLiberman.dat`), and
  the load-bearing part is *not* that f goes complex — F always was. It is that
  `generate_reflections` merges ±h into one Laue orbit and evaluates a single
  representative, which is exact only while f is real: with f″ ≠ 0 in a
  non-centrosymmetric group |F(h)|² ≠ |F(−h)|², and both land in the *same*
  powder peak. So `structure_factors_squared` returns the **Friedel average**,
  in the exact closed form ⟨|F|²⟩ = |A|² + |B|² with A carrying f₀+f′ and B
  carrying f″ over the *same* orbit sums — no second orbit pass, no
  centro/non-centro case split, and B ≡ 0 recovers |F|² bit-identically (which
  constrains the fp *association order* in `_orbit_terms`, not just the
  algebra). f′/f″ are frozen at stage compile onto `PhaseSites.f_anom`: they
  depend only on species and λ, and `EmissionLine.wavelength` is a plain float,
  so they can never be a function of θ. One |F|² is shared across emission
  lines, *guarded* rather than smeared — `dispersion.resolve` raises when a line
  differs from the primary by more than 1 % of Z (an edge between them). Near an
  edge the table is wrong in principle, not merely coarse, so that is refused
  too and `Dispersion.overrides` takes measured pairs. Default **off** so every
  shipped acceptance number stays valid; `DISPERSION_NEGLECTED` makes "off"
  loud. Ions resolve to the element (core-level effect), unlike ionic f₀.
- History nodes store **state, not curves** (a node is ~10 kB; embedding
  y_calc would make it ~1.24 MB). Their cached metrics are *as-optimised* —
  measured on a model frozen at the values each stage *started* from — so
  `refine.replay`, which recompiles at the values the stage *ended* on, can
  differ marginally. That gap is a staleness signal, not a bug. Le Bail
  extracted intensities live outside θ and are path-dependent, so they are
  serialized per node (`ReflectionState`); Pawley will reuse that container
  rather than adding one dot-path per reflection to `free_paths`.
- Emission-line weights are relative to line 0, which is structurally locked
  at 1 (degenerate with phase scales); `set_vary` globs can never free locked
  entries (also protects symmetry-fixed cell angles).
- `RefinementResult.ticks` carries **every emission line's** positions, not
  just the primary — otherwise Layer 0 flags each Kα2 peak as an unindexed
  impurity (this was a real bug, caught by the misfit-injection suite).
- Tests: fast unit/property tests always; real-data acceptance marked
  `@pytest.mark.slow` (`test_acceptance_nac.py`, `_srm660c.py`, `_fap.py`,
  `_capillary.py`).
  Reference values and data provenance in `tests/data/README.md`. Every test
  refinement also writes obs/calc/diff PNGs to `tests/output/` (gitignored)
  for visual inspection — Rwp hides locally-bad fits.
- Comparing against another code means **adopting its protocol**, not just
  its numbers: mirror its refine flags, held parameters and excluded regions,
  then check the channel count matches before believing any Rwp comparison.

## Roadmap & how to work on it

Planning docs are split so a session loads only what it needs — do not read
them all:

- `docs/ROADMAP.md` — thin index: milestone table, work-package (WP) index,
  "Current focus", and the session protocol.
- `docs/wp/NNNN-*.md` — one **self-contained** WP per task (context, commit-
  sized checklist, acceptance command, handover log).
- `docs/DESIGN.md` — design record; read only the section a WP links.
- `docs/milestones/vX.Y.md` — shipped records with measured acceptance blocks.

**Protocol**: to work on the roadmap, read the active WP file (named under
"Current focus" in ROADMAP.md) and nothing else. Commit per checklist item,
prefixed `WP-NNNN:`. Before ending any session that touched a WP — or when
interruption threatens — append a dated handover-log entry (done / in flight /
next / gotchas) and sync its Status glyph into ROADMAP.md's index. When a
milestone ships, record measured acceptance in `docs/milestones/` and flip
the ROADMAP.md row.

Because sessions never read other WP files, **a handover log only reaches your
own successor on the same WP**. Anything you learned that changes work in a
not-yet-started WP — a constant now exported for reuse, a design bullet there
that has gone stale, a deferral into it, a gotcha that would mislead it — goes
in *that* WP's `### Inherited` section, naming yours as the source
(ROADMAP.md step 3b; slot defined in `docs/wp/TEMPLATE.md`).

Shipped: **v0.1** (synchrotron vertical slice), **v0.2** (2026-07-22: lab
Bragg-Brentano, analytic Jacobian, background automation, FitReport L1-2,
history DAG, live viz), **v0.3** (2026-07-24: coordinate refinement, anisotropic
ADPs, QPA weight fractions, Brindley microabsorption, Pawley whole-pattern mode,
March-Dollase preferred orientation, multi-histogram, exporters — WP-0301…0310,
measured acceptance in `docs/milestones/v0.3.md`: SRM 676a cell anchor via c/a
(+30 ppm) plus the IUCr QPA round robin with participant-spread-referenced
tolerances), **v0.4** (2026-07-27: differentiable backends — WP-0401…0408,
measured acceptance in `docs/milestones/v0.4.md`).

**v0.5 — corrections & microstructure** (2026-07-28: capillary absorption 0501,
surface roughness 0502, Stephens anisotropic strain 0503, anomalous f′/f″ 0504,
sequential series 0505, secondary extinction 0506, anode wavelengths 0507,
flat-plate absorption + the real-data capillary acceptance 0508; measured
acceptance in `docs/milestones/v0.5.md`). Its method result is worth carrying
into any future correction: **not one of the eight is well judged by Δ Rwp** —
two provably cannot move it, one moves it the *wrong way* when it is right, and
the two largest accuracy wins are invisible in it. So a new correction ships
with a record field or a diagnostic that states what it changed, never with an
Rwp comparison as its evidence.

**In flight: v0.6 — solver, performance & agents.** `pyproject.version` tracks
the milestone *in flight* (0.6.0.dev0), not the last one shipped, because that
string is stamped into every `RefinementResult.provenance` and history node.

**v0.4 — differentiable backends.** `backend=` takes `"numpy"` (the default and
the only one anyone needs), `"jax"`, or the **experimental** `"torch"` (CPU
fp64) / `"torch-mps"` (Apple GPU, necessarily fp32) — never installed by
default, kept as an independent opinion in the agreement matrix and as the
route to using the forward model as a differentiable layer (DESIGN.md, "What
the differentiable core unlocks"). Every backend is held to per-column
agreement with the analytic Jacobian in `tests/test_cross_backend.py` — whose
configs must grow whenever a *new derivative path* does, or no backend row
covers it. Also landed: true Voigt
(`Instrument.profile.shape="voigt"`, one shared Weideman Faddeeva `w(z)`, TCHZ
still the default), soft bond/angle/value restraints (extra residual rows below
the data, Rietveld and single-histogram only), and the Bérar-Lelann esd fix
(reported esds now carry the inflation; the correlation matrix is a true Pearson
matrix and the 0.98 guard is live). Apple-GPU execution is *slower* than numpy
(46-182×, launch-latency-bound) — `torch-mps` buys precision validation, not
speed; the measured break-even (≈65 k elements per kernel) and ceiling (≈2.5×)
are in the v0.4 record. v2 fence:
FPA, neutron/TOF, spherical-harmonics texture, MCP server.

Key test data (provenance + every reference value in `tests/data/README.md`):
- `11BM_NAC.fxye` — APS 11-BM synchrotron, λ=0.4139090 from the .prm; NAC +
  CaF₂ impurity; acceptance expects a≈10.2513, Rwp<0.12.
- `nist_srm660c_100a.cif` — NIST LaB6 certification data, CuKα doublet +
  graphite analyzer; fits the `…_meas` block with zero fixed / displacement
  refined; expects a≈4.15678±2e-4, Rwp<0.10. **Absolute** anchor.
- `FAP.XRA` + `FAP.EXP` — GSAS-II LabData tutorial fluorapatite; the `.EXP` is
  GSAS's converged fit and supplies both the reference values and the protocol
  the test mirrors. **Cross-code consistency** check (±300 ppm), not truth.
- `qarr/*.prn` — IUCr CPD QPA round-robin patterns (samples 1a-1h, 2, 4 + six
  pure phases; plain 2-column ASCII, Cu Kα doublet, graphite diffracted-beam
  mono). QPA truth is the **weighed composition**; tolerances referenced to
  the published participant spread, never to σ(W). `corundum.prn` doubles as
  the SRM 676a cell-anchor specimen (c/a is the certificate-grade assertion;
  absolute axes carry lab d-scale systematics).

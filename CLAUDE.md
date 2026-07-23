# CLAUDE.md — pxrd-refine

API-first Rietveld refinement package (powder XRD). MIT. numpy/scipy fp64
core, pydantic v2 schemas, gemmi for CIF/symmetry. Import name: `pxrdref`.

## Commands

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"   # setup (once)
.venv/bin/python -m pytest                             # full suite ~2 min, incl. real-data acceptance
.venv/bin/python -m pytest -m "not slow"               # skip acceptance (~20 s)
.venv/bin/python -m ruff check src tests examples      # lint (must be clean)
.venv/bin/python examples/nac_11bm.py                  # end-to-end demo + plot
.venv/bin/pxrdref watch <live-dir>                     # live viewer for a LiveSession run
```

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
- **fp64 everywhere** in the core; future GPU backends may compute Jacobian
  *columns* in fp32 but the residual used for cost/statistics and the solve
  stay fp64 on host.
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
  `@pytest.mark.slow` (`test_acceptance_nac.py`, `_srm660c.py`, `_fap.py`).
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

Shipped: **v0.1** (synchrotron vertical slice), **v0.2** (2026-07-22: lab
Bragg-Brentano, analytic Jacobian, background automation, FitReport L1-2,
history DAG, live viz). In progress: **v0.3** — coordinate refinement,
anisotropic ADPs, QPA weight fractions, Brindley microabsorption, Pawley
whole-pattern mode and March-Dollase preferred orientation have landed
(WP-0301…0307; `RefinementResult.qpa` = Hill-Howard ZMV with correlated σ, plus
corrected fractions + µR fence when every phase carries `particle_radius_um`;
`Phase.preferred_orientation` is an optional single-axis March-Dollase block —
integer hkl axis + softplus `r`, identity at r=1, analytic ∂P/∂r column, and a
Layer-1 axis diagnostic on `FitReport.texture` that fits the full nonlinear
P(r) — the linear template is degenerate in high-symmetry crystals);
the v0.3 acceptance (WP-0310) is measured and recorded in
`docs/milestones/v0.3.md` — SRM 676a cell anchor via c/a (+30 ppm) plus the
IUCr QPA round robin with participant-spread-referenced tolerances; only
multi-histogram (0308) and exporters (0309) remain before the milestone row
flips. v2 fence: FPA, neutron/TOF, spherical-harmonics texture, MCP server.

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

# WP-0406 — Restraint penalty rows

Milestone: v0.4 · Status: ✅ 2026-07-24
Depends on: —

## Goal

Soft restraints (bond lengths, bond angles, value targets) as extra
`√w·(computed − target)/σ` rows in the residual vector, following the
penalty-row seam the P-spline background and Pawley equal-split already
established: kept in the covariance, excluded from Rwp/Durbin-Watson/
Bérar-Lelann, with an analytic row-Jacobian and a restraint-summary report.

## Context

- **The penalty-row seam is already proven twice — reuse it, don't invent.**
  `BackgroundPSpline` appends `√λ·D₂·c` rows and Pawley appends
  `√λ/s·(δ − 1/n)·I` rows, both concatenated *after* the data rows in
  `_make_residual` ([`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py)),
  with `covariance_estimates(..., n_data=N_data)` keeping them in JᵀJ but
  slicing `fun[:n_data]` for χ²/Rwp/DW/Bérar-Lelann (statistics on data rows
  only). The three touchpoints: (1) compile a `√w`-scaled row block; (2)
  `concatenate` it below the data (and background-penalty) rows in
  `_make_residual`; (3) write its rows into the Jacobian below `n_data` and
  register the count so `covariance_estimates`/`compute_statistics` keep
  slicing `[:n_data]`. WP-0308 verified this contract survives the
  multi-histogram stacked layout.
- **The one new wrinkle:** the P-spline and Pawley rows are *constant*
  matrices; bond/angle restraints are **nonlinear** in the coordinates, so
  they need their own row-Jacobian (the precedents don't).
- **Natural consumer:** WP-0302 atomic coordinates — bond-length restraints
  become useful the moment coordinates refine.

### Inherited

From **WP-0301 / WP-0302** (Wyckoff constraints, coordinates — landed):
restraints were fenced out of both ("Restraints (WP-0406, penalty rows)";
"Restraints / soft bond-length penalties (WP-0406 supplies the penalty rows)"),
so this WP owns them outright. Critically, **restrain the DOF paths, not
`x`/`y`/`z`.** Coordinates refine as site-symmetry DOFs
(`phases.i.atoms.j.dof.k`), with x/y/z *affine-tied* to them through the
constant block `p = C·θ + d`. The x/y/z paths are tied, match no `set_vary`
glob, and are not columns of θ — a restraint written against them has nothing
to differentiate. The bond-length row-Jacobian must chain through the same
constraint directions the analytic structural columns use
(`table.constraint_block()`, as in `_structural_column`).

From **WP-0306** (Pawley, landed): the `n_free` convention you are inheriting
credits nothing for restraints — "`n_free` for Rexp/GoF counts the whole
intensity block (`_pawley_n`); the restraint makes that slightly conservative
(standard Pawley convention)". This WP's promise that restraints are excluded
from Rwp/DW/Bérar-Lelann is about *residual rows*, which is a separate axis
from parameter counting. Decide explicitly whether restrained coordinates
follow Pawley's precedent (count fully) or claim fractional DOF, and say which
— silently differing from the shipped convention is the trap.

From **WP-0401** (op shim, landed):

- **`pawley_restraint_residual(vec)` changed signature** — it now takes the
  intensity vector rather than reading a mutated buffer, part of the residual
  purity refactor. New penalty rows must follow the same functional threading:
  values in, no hidden reads of mutable state, so the residual stays traceable.
- **Bit-identity goldens now lock the existing penalty rows.** Five states in
  `tests/data/backend_goldens/` include a toy Le Bail *with P-spline penalty
  rows* and a toy Pawley *with overlap-restraint rows*. Adding rows must either
  leave those byte-identical or follow the re-baseline rule in
  `tests/data/README.md` (regenerate via `python -m tests.test_backend_shim`,
  only from a green tree).
- **No general index-array scatter is available** to assemble rows —
  `window_add` on frozen contiguous windows plus `concatenate` is the whole
  vocabulary, deliberately.

### Design (decided)

- **Schema** (pydantic v2, `extra="forbid"`; opt-in, empty default so a
  phase that declares none is untouched — the extinction/PO pattern):
  `Phase.restraints: list[Restraint] = []`, with
  `BondRestraint{atom_i, atom_j, target, sigma, weight=1.0}`,
  `AngleRestraint{atom_i, atom_j, atom_k, target_deg, sigma, weight=1.0}`,
  `ValueRestraint{path, target, sigma, weight=1.0}`. Each contributes a row
  `√weight·(computed − target)/sigma`.
- **Distances/angles under PBC: explicit symmetry-op + translation, not bare
  minimum-image.** The restraint carries an optional (rotation-op index,
  lattice translation) for the *second* atom, defaulting to minimum-image
  when unspecified. Powder restraints almost always target a
  symmetry-generated neighbour (an M–O in an adjacent cell), which
  minimum-image alone renders ambiguous; the frozen `sites.ops`
  (`crystallography/structure_factor.py`) already stores the R, t arrays, so
  the restraint names an op index rather than re-deriving symmetry.
  d = |L·(R·x_j + t + n − x_i)| with L the direct cell matrix
  (`crystallography/lattice.py`); angles from two such vectors via `arccos`.
  Differentiable w.r.t. fractional coords **and** cell.
- **Jacobian: analytic row now, jacfwd later.** An analytic `∂d/∂θ` row —
  chain `∂d/∂x_frac · ∂x_frac/∂θ` through the same affine constraint block
  `_structural_column` uses, plus `∂d/∂cell` — keeps the numpy path exact.
  FD (`fd_cols`) is the fallback for any restraint kind whose analytic row
  isn't written yet. Under jax (WP-0402) the restraint rows fall out of
  jacfwd automatically (the residual is one function).
- **Statistics exclusion:** restraint rows go below the data (and
  background-penalty) rows, so χ²/Rwp/DW/Bérar-Lelann see data only, while
  JᵀJ keeps them — the covariance is the *restrained* one (correct:
  restraints inform parameter uncertainties). Identical to the multi-histogram
  penalty-row contract WP-0308 verified.
- **Reporting:** a `RestraintReport` on the result/FitReport — per-restraint
  (computed, target, deviation/σ) and a pooled restraint-χ². An over-tight
  restraint fighting the data (deviation ≫ σ) is thereby visible, matching
  the package's "never hide a bad sub-fit" ethos. Deviations in units of σ
  are the headline.

## Non-goals

Rigid bodies (v2 fence); anti-bump/van-der-Waals repulsion restraints
(future); torsion restraints; automatic restraint generation from a
connectivity search.

## Tasks

- [x] `schemas/structure.py`: `BondRestraint`/`AngleRestraint`/
      `ValueRestraint` + `Phase.restraints` (opt-in, empty default); the PBC
      sym-op/translation spec
- [x] `model/restraints.py`: differentiable distance/angle from (xyz, cell)
      using frozen `sites.ops`; `√w·(d − target)/σ` rows
- [x] Compile-time restraint row block + analytic `∂/∂θ` row-Jacobian below
      the background-penalty rows in `_make_residual`/`_make_jacobian` (both
      residual builders — numpy + jax); the shipped kinds are all analytic so
      no per-kind FD fallback was needed
- [x] `covariance_estimates` reuse verified (rows in JᵀJ, excluded from
      `fun[:n_data]`); `RestraintReport` on the result + FitReport +
      `RESTRAINT_TENSION` diagnostic; multi-histogram deferred (guard raises)
- [x] Tests: `tests/test_restraints.py` — a bond restraint pulls a
      deliberately-displaced atom back to target within σ without changing
      the data-row statistics; the restraint-row analytic Jacobian vs FD
      <5e-3 per kind; Rwp/DW/Bérar-Lelann bit-identical to the no-restraint-row
      statistics at the same parameters + obs/calc/diff PNGs to
      `tests/output/`; 6th backend golden (`toy_restraints`) locks the rows

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_restraints.py -q
```

Measured: a bond-length restraint recovers a perturbed coordinate to within
σ; the restraint-row analytic Jacobian matches FD <5e-3; Rwp/DW/Bérar-Lelann
are computed on data rows only (bit-identical to the no-restraint-row
statistics at the same parameters).

## References

- Waser (1963) Acta Cryst. 16, 1091 — least squares with observational
  restraints.
- Watkin (1994) Acta Cryst. A50, 411 — restraint weighting in practice.
- GSAS-II restraint conventions (BSD — concepts only, cite; never ported).

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): schema (opt-in
  bond/angle/value), explicit sym-op+translation PBC spec over minimum-image,
  analytic nonlinear row-Jacobian, statistics-exclusion seam reuse and the
  `RestraintReport` decided.
- **2026-07-24** — **LANDED.** Full acceptance measured, suite green
  (376 fast + 11 new restraint tests + the 6th backend golden; ruff clean).

  **Done.** Schema (`schemas/structure.py`): `BondRestraint`/`AngleRestraint`/
  `ValueRestraint` + `Phase.restraints=[]` (plain smart union — the field sets
  are distinct so no discriminator needed; `sigma>0`/`weight≥0` field
  constraints, atom-index `@model_validator` on `Phase`).  Geometry
  (`model/restraints.py`): traceable `restraint_residual` (xp) + host-numpy
  analytic `restraint_partials`/`summarise_restraints`; min-image freeze over
  `sites.ops[j] × {−1,0,1}³` at compile.  Wiring: `CompiledModel.restraints`
  + `restraint_residual` method, resolved rietveld-only in `compile_model`,
  4th `parts.append` in **both** `_make_residual` and `make_traced_residual`.
  Jacobian: `J[restr, :n_table] = (R_phys @ C.toarray()) * dpdu` below the
  data/penalty/Pawley rows; Fix A (bounded the Pawley write to its stripe) and
  Fix B (`C.toarray()`) both applied.  Report: `RestraintReport` on
  result + `HistogramResult` + `for_histogram`, attached in `_build_result`,
  `RESTRAINT_TENSION` diagnostic at |dev/σ|>3, surfaced in `build_report`.

  **Measured.** Bond restraint recovers a displaced rutile O within σ
  (GoF 1.03); analytic-vs-FD restraint rows <5e-3 per kind (bond ~1e-6, angle
  0 machine, value machine; triclinic P1 exercised all six ∂G/∂cell + the
  angle quotient rule); data-row Rwp/DW/χ²/n_points bit-identical with vs
  without restraint rows; jax jacfwd matches numpy restraint rows to 2.8e-16
  (data rows untouched — same 2.6e-6 WP-0402 level with or without restraints).

  **Gotchas / notes for a successor.**
  - The six exact `∂G/∂cell` (angles in degrees ⇒ the π/180 factor), in
    `_metric_g_derivs`: `∂G/∂a` (0,0)=2a,(0,1)=(1,0)=b·cosγ,(0,2)=(2,0)=c·cosβ;
    `∂G/∂b` (0,1)=a·cosγ,(1,1)=2b,(1,2)=c·cosα; `∂G/∂c` (0,2)=a·cosβ,
    (1,2)=b·cosα,(2,2)=2c; `∂G/∂α` (1,2)=(2,1)=−bc·sinα·π/180; `∂G/∂β`
    (0,2)=−ac·sinβ·π/180; `∂G/∂γ` (0,1)=−ab·sinγ·π/180.
  - **Angle degeneracy:** cos θ is clamped to `±(1−1e-9)` before `arccos`
    (`_COS_CLAMP`); the derivative ∝ 1/sinθ, so 0°/180° are unsupported. The
    auto min-image picks the *same* nearest image for both neighbours when
    `atom_i == atom_k` → u ∥ v → a degenerate 0° angle; name distinct
    `op_index_i`/`op_index_k` to get a real angle (the golden/tests do).
  - **Chain-rule seam:** partials are written against the *entry* dot-paths
    (atom x/y/z + six cell), never the DOF paths — `C.toarray()` chains them,
    so a coordinate DOF (e.g. rutile O's [110]) sums its x and y automatically,
    exactly the WP-0301/0302 `### Inherited` requirement.
  - Restraints are **Rietveld-only** (Le Bail/Pawley `model.restraints is None`)
    and **single-histogram-only** (`run_multi_least_squares` raises
    `NotImplementedError`; the stacked layout needs a third offset row-block —
    forward-reference left in WP-0308's `### Inherited`).
  - `n_free` unchanged (restrained coords count fully — Pawley precedent);
    restraint rows are *soft observations*, out of Rwp/DW/Bérar-Lelann.

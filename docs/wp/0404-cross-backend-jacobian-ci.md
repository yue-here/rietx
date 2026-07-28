# WP-0404 — Cross-backend Jacobian-agreement CI

Milestone: v0.4 · Status: ✅ landed 2026-07-24
Depends on: WP-0402

## Goal

A test matrix proving that analytic, FD, jax-jacfwd, torch-fp64-CPU and
fp32-column-policy Jacobians agree — including across stage boundaries, in
Rietveld (single- and multi-histogram) and in Le Bail/Pawley (single-histogram;
multi-histogram is Rietveld-only by WP-0308's design) — so backend drift is
caught the day it happens, not the day it ships a wrong esd. Green with and
without the optional backends installed.

## Context

- [../DESIGN.md](../DESIGN.md#risks--mitigations) — "backend drift → small op
  vocabulary + mandatory cross-backend tests"; this WP is that mitigation.
- The v0.2 harness to extend, not replace:
  `tests/test_v02_core.py::test_analytic_jacobian_matches_fd` — 18
  `ANALYTIC_FAMILIES` paths on a lab Bragg-Brentano state (Kα doublet + FCJ +
  displacement/transparency), per-column rel-L2 <5e-3, cosine >0.99999, FD
  step `1e-6·max(1,|θ|)`. `tests/test_jacobian.py::_check_columns` is the
  coordinate/ADP-DOF variant with the same tolerances.

### Inherited from upstream WPs (added 2026-07-24, after 0402 and 0403 landed)

This section exists because the session protocol forbids reading other WP
files — anything 0402/0403 learned that changes work *here* has to be
restated here or it is lost.

- **Import the fp32 bars, do not restate them.** WP-0403 exports
  `COLUMN_REL_L2_MAX = 2e-2` and `COLUMN_COSINE_MIN = 0.999` from
  `pxrdref.backend.linalg64`, together with
  `column_agreement(J_ref, J_test) -> (worst rel-L2, worst cosine)`, which
  already skips transform-floor-dead columns. Re-declaring those numbers in
  `tests/test_cross_backend.py` would be the exact drift this WP exists to
  catch. (The fp64 bars 5e-3 / 0.99999 have no home yet — declare those here.)
- **Driving the fp32-column row.** It is not a backend; it is a policy over
  whichever backend built the columns:
  `with precision_policy(FP32_JACOBIAN): J32 = _jacobian_for(model, table, be)(theta)`.
  So it composes with the numpy *and* jax rows rather than being a row of its
  own, and it needs no `importorskip` — it runs on a numpy-only checkout.
- **Do not tighten the fp32 bars to the measured CPU numbers.** The CPU
  simulation round-trips fp64→fp32→fp64, which reproduces fp32
  *representation* loss only, not error accumulated inside a device fp32
  forward pass. Measured agreement is ~2.6e-8 rel-L2 against the 2e-2 bar;
  that six-order margin is an artifact of the simulation, and the bars are
  sized for the real hardware WP-0408 brings. Tightening them would make the
  torch-MPS row fail for the wrong reason.
- **The FCJ S/L == H/L kink needs a loose bar (from 0402).** At axial
  S/L = H/L the quadrature split point ξ_kink = |S/L − H/L| sits at its own
  non-differentiable zero, so analytic node-FD (right-sided), jax
  (sign(0) = 0 subgradient) and central FD legitimately differ by ~3e-3.
  Not a bug. The `srm660c` shim state *starts* at exactly that point, so its
  two axial columns carry a documented 2e-2 loose bar in
  `test_backend_jax.py::_column_agreement`; reuse that convention here.
  States built for FD comparison (`_lab_state`, `toy_rich`) use unequal
  ratios on purpose.
- **The multi-histogram jax row was deferred *to this WP* (from 0402).** 0402
  deliberately shipped no jax test for `MultiHistogramRefinement` — the wiring
  is shared via `_jacobian_for`, so a dedicated test there would have doubled
  jit-compile cost for no new code path. This WP's stacked-layout task is its
  intended home.
- **Reusable state builders.** `tests/test_acceptance_srm660c.py` exposes
  `build_srm_inputs()` (extracted by 0402 for exactly this reason), and
  `tests/test_backend_shim.py` exposes `STATES` — `srm660c`, `nac`,
  `toy_lebail`, `toy_pawley`, `toy_rich`, each returning
  `(model, table, extras)` at a compiled expansion point.
- **Budget jit compile, not flops.** jax's per-stage jit compile is ~1-4 s and
  dominates toy-sized runs; parametrizing the matrix finely over jax configs
  costs compile time, not compute.
- **The Goal above overpromises: multi-histogram Le Bail and Pawley cells do
  not exist.** WP-0308 shipped multi-histogram as Rietveld-only, with an
  explicit `NotImplementedError` in `multi.py` — "Le Bail / Pawley intensities
  are per-pattern extractions, not shared, so a joint fit of them is just
  independent single-pattern fits". So the matrix is (Rietveld × {single,
  multi}) + ({Le Bail, Pawley} × single). Shrink the Goal sentence rather than
  growing scope this WP does not own.
- **Pawley is not the same comparison as Rietveld** (from 0306). Its Jacobian
  differentiates the *augmented* residual — extra overlap-restraint rows below
  the data and background-penalty rows — over θ = [table θ | per-hkl
  intensities], and `LSQOutcome` hides that tail behind `n_aux` while returning
  table-only columns. Compare the full augmented array from `_jacobian_for`,
  not the outcome's `jac`. The intensity columns are exact analytic
  (`−√w·Σ_lines w_line·Ω`), never FD, so they should agree to round-off — a
  loose bar there is hiding something.
- **Reuse the five-state golden corpus, don't build new states** (from 0401).
  `tests/data/backend_goldens/` already pins SRM 660c, NAC, toy Le Bail (with
  P-spline penalty rows), toy Pawley (pseudo-cubic cell so overlap-restraint
  rows exist) and a toy with aniso + PO + extinction + displacement/
  transparency all *nonzero*. They are environment-pinned; re-baseline only
  via the documented rule in `tests/data/README.md`.
- **Extinction is off by default, and that hides a real Jacobian trap** (from
  WP-0506). The analytic `dof`/`adp` columns carry a factor `G = E + x·dE/dx`
  (`model/forward.py`), and if it is wrong the columns disagree with FD **only
  when `ext ≠ 0`**. Every default-state comparison would pass. The `toy_rich`
  golden state has extinction nonzero — use it, or the matrix is blind here.
- **FCJ columns routed to FD are out of scope by decision** (from 0401): when
  `axial_ok=False` the axial columns fall back to FD, and autodiff correctness
  *at* that discontinuity was explicitly declared out of scope. Exclude or
  specially tolerate those cells rather than treating a mismatch as drift.

### Design (decided)

- **The matrix.** Methods × configs, parametrized in one
  `tests/test_cross_backend.py`:
  - Methods: analytic, FD, jax-jacfwd fp64 (WP-0402), torch-jacfwd fp64-CPU
    (row added when WP-0408 lands), fp32-column policy (WP-0403 — a policy
    layered over the numpy/jax rows, not a backend of its own; see Context).
  - Configs: the 18 `ANALYTIC_FAMILIES`; Pawley exact linear intensity
    columns; Le Bail (fixed extracted intensities); single- and
    multi-histogram (stacked layout from `run_multi_least_squares`);
    stage-boundary regeneration cases.
- **Tolerances, centralized as module constants:** fp64 methods <5e-3
  rel-L2 / cosine >0.99999 (v0.2 style) — declare these here; fp32 columns
  <2e-2 / cosine >0.999 — **import** these from `backend.linalg64` as
  `COLUMN_REL_L2_MAX` / `COLUMN_COSINE_MIN` (WP-0403 owns them; see Context).
  The fp32 rationale: fp32 carries ~7 significant digits and a column near a
  cancellation loses 2–3 more — a wrong *direction* is still caught by the
  cosine, and the stricter parameter-level gate lives in WP-0403's acceptance.
- **Stage-boundary is the headline case** (frozen-state regeneration between
  stages is where discreteness bugs surface): run a 3-stage SRM 660c plan;
  at each recompile assert Jacobian continuity `‖J_after − J_before‖/‖J‖ <
  1e-6` at the shared parameter values. Cover Rietveld, Le Bail and Pawley.
  *(Corrected on landing: 1e-6 was written before measurement and sits below
  the real srm660c gap of 5.9e-6 — a converged stage moves parameters, so the
  frozen state it regenerates is genuinely staler than that. Shipped bars are
  1e-4 Frobenius / 1e-3 per column, against measured 5.9e-6 / 6.9e-5; see
  Acceptance. Two sharper claims carry the weight instead: the boundary whose
  stage freed only scale/background must be **exactly** zero, and the frozen
  state must be **bit-identical** across each least-squares run.)*
- **Runs without extras.** Backend-specific rows use
  `pytest.importorskip("jax")` / `importorskip("torch")` (the established
  pattern — see `tests/test_pawley.py`); the analytic-vs-FD core always
  runs, so a numpy-only checkout stays green. The full matrix runs after
  `uv pip install -e ".[dev,jax]"` (the `torch` extra does not exist yet —
  it lands with WP-0408, and the torch row skips itself until then).
  GitHub Actions wiring is deliberately deferred to WP-1002 (no `.github/`
  exists yet) — acceptance here is pytest-command-based.
- **Central differences, not forward** *(decided on landing)*. Forward FD
  carries O(h) truncation error, which on real data with sharp peaks is not
  small: measured against the analytic column, forward FD sits 6.2e-3 away on
  `srm660c` `phases.0.cell.a` and 4.7e-3 on `nac` — at or past the 5e-3 bar,
  for reasons that have nothing to do with any backend. Central FD (O(h²))
  puts the same two columns at 4.3e-5 and 2.2e-5. A bar loose enough for forward FD
  would be too loose to catch drift. The forward-difference variant stays under
  test where it belongs: `test_v02_core.test_analytic_jacobian_matches_fd`.

## Non-goals

CI-service configuration (WP-1002); performance benchmarking (reported in
WP-0402/0408); esd-value assertions (WP-0407 owns the esd path).

## Tasks

- [x] `tests/test_cross_backend.py`: parametrized (method × config) matrix;
      analytic-vs-FD and fp32-column always-on (the fp32 policy needs no
      extra); jax/torch rows `importorskip`-gated; fp64 tolerance constants
      declared here, fp32 bars imported from `backend.linalg64`
- [x] Stage-boundary continuity cases (3-stage SRM 660c; Rietveld + Le Bail
      + Pawley)
- [x] Multi-histogram stacked-Jacobian agreement (via
      `run_multi_least_squares` layout)
- [x] Document the extras invocation (`uv pip install -e ".[dev,jax]"`) in
      this file and CLAUDE.md once the extras exist — done for jax; the
      `torch` extra does not exist yet and lands with WP-0408

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py -q   # numpy-only rows only
# after: uv pip install -e ".[dev,jax]"   (torch extra: WP-0408)
.venv/bin/python -m pytest tests/test_cross_backend.py -q   # + the jax rows
```

Measured 2026-07-24 (jax 0.11.0, no torch installed — 46 tests / 42 s with the
two `slow` real-data configs, 34 tests / 22 s without; 10 skips are the torch
rows and the configs with no axial columns):

| method | worst rel-L2 off the kink | on the kink | bar |
|---|---|---|---|
| central FD | 8.8e-4 (`srm660c` `profile.u`) | 3.0e-3 | 5e-3 / kink 2e-2 |
| jax jacfwd | 8.8e-4 (`srm660c` `profile.u`) | 6.1e-3 | 5e-3 / kink 2e-2 |
| numpy + fp32 policy | 3.7e-8 (`toy_pawley` intensity column) | 2.6e-8 | 2e-2 |
| jax + fp32 policy | 8.8e-4 | 6.1e-3 | 2e-2 |
| multi-histogram, stacked | FD 1.4e-4, jax 1.8e-6, fp32 2.7e-8 | — | as above |

Only the two real-data configs reach 1e-4 at all; the four synthetic ones stay
below 2.8e-5 for every method. Worst cosine off the kink columns: 1 − 1.3e-7
(`srm660c` `profile.u`, both FD and jax — i.e. the disagreement is in
magnitude, not direction). The Pawley intensity block — exact linear columns on
both sides — agrees to 6.7e-14 (jax) and 1.1e-10 (central FD, i.e. round-off/h).

Stage boundaries (3-stage plans; per-boundary Frobenius / worst column, bars
1e-4 / 1e-3): `srm660c` Rietveld **0.0** then 5.9e-6 / 6.9e-5; toy Le Bail
**0.0** then 1.9e-7; toy Pawley **0.0** then 7.6e-7. The exact zeros are the
boundaries whose stage freed only scale/background, which cannot move the
frozen state; the frozen state (hkl list, window ranges, FCJ node counts, PO
orbit members) is bit-identical across every least-squares run. For contrast,
letting Le Bail *re-extract* intensities at the same boundary moves the same
columns 8.2e-2 (Le Bail) and 3.2e-1 (Pawley) — which is why the measurement is
taken with intensities carried.

The file is green with and without jax installed; the torch rows skip with
`unknown backend 'torch'` until WP-0408.

## References

No new physics — this WP is the DESIGN.md risk mitigation made concrete. The
tolerance style is the measured v0.2 harness.

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): matrix,
  centralized tolerances (fp64 5e-3/0.99999, fp32 2e-2/0.999),
  stage-boundary continuity test and the extras-gated execution model
  decided; torch row lands with WP-0408.
- **2026-07-24 (from the 0403 session, not yet started here)** — added the
  "Inherited from upstream WPs" Context block. 0402 and 0403 both landed
  facts that change the work here (the fp32 bars now exist as importable
  constants; the fp32 row is a policy, not a backend; the FCJ kink needs a
  loose bar; the multi-histogram jax test was deferred *to* this WP), and the
  session protocol forbids reading their files — so they are restated above.
  The Design tolerance bullet previously said to declare the fp32 bars
  locally; that would have duplicated `linalg64`'s exports, which is the very
  drift this WP exists to catch. Corrected.
- **2026-07-24 — landed.** All four tasks done in `tests/test_cross_backend.py`
  (46 tests: 5 methods × 6 configs = 30, the 5 multi-histogram method rows +
  its layout guard, 3 stage-boundary plans, the per-config `axial_ok` guard
  (6), and the Pawley exact-column check). Measured numbers in Acceptance
  above.
  - *Done*: the (method × config) matrix; stage-boundary continuity for
    Rietveld/Le Bail/Pawley; multi-histogram stacked agreement;
    `uv pip install -e ".[dev,jax]"` documented here and in CLAUDE.md.
  - *Two design bullets were corrected against measurement, not opinion*: the
    1e-6 boundary bar (real srm660c gap is 5.9e-6) and forward-vs-central FD
    (forward sits 6.2e-3 from analytic on srm660c cell `a` — past the fp64
    bar, from truncation alone). Both are annotated in Design above.
  - *One production change*: `optimize/least_squares._multi_closures()`, the
    stacked residual/Jacobian pair split out of `run_multi_least_squares` so
    the multi-histogram layout is reachable without running a solve. Behaviour
    unchanged; `run_multi_least_squares` now calls it.
  - *Gotchas for anyone extending this file*:
    - **The matrix only covers what the state builders contain.** Configs are
      `tests/test_backend_shim.py::STATES` plus the `ANALYTIC_FAMILIES` lab
      state. New physics (a new profile shape, restraint rows, an absorption
      correction) is invisible here until it appears in one of those states.
    - **jit compile, not flops, is the cost.** `_JACOBIAN_CACHE` keys one
      built callable per (config, backend) so the `+fp32` rows reuse the
      compiled jax one — that halved the file's runtime (29 s → 15 s for the
      non-`slow` subset). Do not build a second callable per row.
    - **The kink loose bar is conditional**, applied only when the state's
      decoded S/L equals H/L. Do not make it unconditional to silence a
      failure on some other state — that would hide real drift.
    - Suite runtimes were badly stale and are now measured: `-m "not slow"`
      ~85 s (CLAUDE.md said ~20 s) and the full suite ~13 min (it said ~2 min).
      This file is ~22 s / ~42 s of those. CLAUDE.md corrected; WP-1002's
      `### Inherited` warned, since it sizes CI jobs from those numbers.
  - *Next*: nothing here. WP-0408 activates the torch rows by adding the
    `torch` branch to `_jacobian_for` plus a `torch` extra — the row and its
    skip are already written (noted in 0408's `### Inherited`).

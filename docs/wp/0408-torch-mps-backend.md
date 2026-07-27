# WP-0408 — torch backend (MPS fp32 forward)

Milestone: v0.4 · Status: ⬜ not started
Depends on: WP-0401, WP-0402, WP-0404 (also consumes WP-0403's policy and
WP-0405's `w(z)`)

<!-- Was WP-0603 (v0.6); pulled into v0.4 on 2026-07-24 — see Context. -->

## Goal

A `TorchBackend` on the WP-0401 op shim: fp64 on CPU (an independent row in
the cross-backend agreement matrix) and fp32 forward + Jacobian columns on
Apple MPS under the WP-0403 mixed-precision policy — local GPU acceleration
on the maintainer's Mac, and the first *real-hardware* validation of the
fp32-column policy.

## Context

- **Why this is in v0.4 and not v0.6** (decided 2026-07-24): MPS acceleration
  cannot come through jax — jax-metal is abandoned, a locked decision
  ([../DESIGN.md](../DESIGN.md#locked-decisions)) — so it requires torch. The
  v0.4 shim (0401) and agreement CI (0404) make a second backend far cheaper
  to add, and torch-MPS is what makes WP-0403's fp32-Jacobian-column policy
  testable on real GPU hardware rather than only in CPU simulation. See the
  dated amendment in DESIGN.md's locked decisions.
- **The scope-discipline condition is preserved by sequencing, not by
  milestone:** torch work starts only after the jax path (WP-0402) *and* the
  cross-backend CI (WP-0404) are green. One autodiff backend is brought up at
  a time; the second lands against an existing agreement harness.
- **The hard constraint:** no Apple GPU supports fp64 in any framework
  ([../DESIGN.md](../DESIGN.md#locked-decisions)), and JᵀJ squares the
  condition number ⇒ fp64 torch runs on **CPU**; MPS runs fp32 for the
  forward and Jacobian columns only, crossing WP-0403's `linalg64.py` host
  boundary before the solve (invariant 2). complex128 on CPU, complex64 on
  MPS.
- torch has no `wofz` — the WP-0405 shared Faddeeva is what makes the true
  Voigt option work here, and is the reason it is implemented on the op set
  rather than per-backend.

### Inherited

From **WP-0401** (op shim, landed 2026-07-24) — the contract `TorchBackend`
must satisfy, so these are not open design choices:

- **The three sites to flip.** `backend: str = "numpy"` is already threaded
  through `refine.py` (~line 58), `multi.py` (~line 73) and
  `schemas/common.py` (~line 109), each raising for unknown backends. That is
  the whole integration surface.
- **`window_add` is functional**, returning a new array — callers thread
  `y = xp.window_add(...)`. torch may implement it with `index_add`, but must
  not expose in-place semantics, and must **not** widen the API to a general
  index-array scatter even though torch supports one: data-dependent indices
  are what frozen-per-stage discreteness forbids. `segment_sum` is likewise
  `index_add` (numpy uses `bincount`, jax `jax.ops.segment_sum`).
- **Bind once, not per op.** Hot-loop code does `xp = get_backend()` once per
  compiled-model call, so the backend cannot depend on per-call device/dtype
  inspection — device and dtype come from WP-0403's policy object.
- **Gotcha (1), which binds every non-numpy backend, not just jax:**
  compile-time code (`fcj_extent_deg`, node sizing) shares `_xi_max`, which is
  xp-routed. Set the non-numpy backend only *around the solve*, or
  `np.asarray` at the compile boundary, so frozen state stays host numpy. For
  MPS this is sharper than it was for jax: leaking device tensors into
  `compile_model` would put non-fp64 arrays into frozen state.
- **Gotcha (2):** the FCJ fallback `ok` predicate and one-hot fallback weights
  assume `n_nodes` (hence shapes) frozen — true by construction, but a
  shape-dynamic torch implementation would break it silently.
- **The analytic-column path is not traceable and never will be.**
  `derivative_bases` keeps a python `isfinite` skip on purpose: it is host-side
  Jacobian support, and mask-converting it would let NaN structural/PO gradient
  columns reach `window_add`. Residual-path masking lives in
  `_reflection_profile` and `phase_peaks` instead.

From **WP-0402** (jax backend, landed 2026-07-24): `_jacobian_for` in
`optimize/least_squares.py` is the single dispatch point — add the torch branch
there and the mixed-precision policy, multi-histogram wiring and Pawley/Le Bail
row layout all come for free. 0402 deliberately shipped no multi-histogram jax
test for that reason (the wiring is shared); the same argument applies here.

From **WP-0403** (mixed-precision policy, landed 2026-07-24):

- The policy object is `MixedPrecisionPolicy` in `backend/linalg64.py`; scope
  it with `with precision_policy(FP32_JACOBIAN)`. `jacobian_dtype` is its only
  field — `residual_dtype`/`solve_dtype` are read-only properties pinned to
  fp64, so there is deliberately no way to configure an fp32 residual or solve.
- `cast_columns` is already applied at `_jacobian_for`'s exit, so **torch
  inherits the policy with no new wiring** — do not add a second hook.
- **This WP supplies the first real evidence about the policy.** The CPU gate
  round-trips fp64→fp32→fp64, which captures fp32 *representation* loss only,
  not error accumulated inside a device fp32 forward pass. Measured CPU
  agreement is ~2.6e-8 rel-L2 against a 2e-2 bar; MPS computing the whole
  peak-chain in fp32 is expected to be far worse, and that is the number worth
  reporting. If the bars fail on MPS, that is a finding, not a bar to loosen
  without saying why.
- `column_agreement(J_ref, J_test)` in `linalg64.py` gives (worst rel-L2, worst
  cosine) with dead columns already skipped — reuse it.

From **WP-0405** (true Voigt, landed 2026-07-24) — only relevant when a torch
run uses `Instrument.profile.shape="voigt"` (TCHZ is the default and is
complex-free):

- **The Voigt path needs working complex tensors, not just `exp`/`conj`.**
  `model/profiles/faddeeva.py` builds `z` with `1j * z`, divides complex arrays
  with the bare `/` operator, and takes `.real`/`.imag` — deliberately *not*
  through named ops in `backend/api.py`, so it dispatches on the tensor type
  alone. torch supports all of these, but verify `1j * tensor`, complex `/` and
  `torch.real`/`imag` on your device before claiming the shape works. There is
  **no new op to implement** for it — if TCHZ passes the op-set contract, add a
  single agreement point for `faddeeva_w` on a complex sample and one Voigt
  forward eval, no more.
- **Complex is fp-policy-coupled on MPS.** w(z) is fp64/complex128 on CPU;
  under WP-0403's fp32 column policy it is complex64. If MPS lacks a needed
  complex op, the honest move is to route `shape="voigt"` to the CPU-fp64 torch
  path (like the analytic column path already is) rather than silently degrade —
  the Voigt argument always has Im z ≥ 0, so no branch is needed, only dtype.
- **Sizing is shape-free.** `compile_model` sizes windows/FCJ nodes with the
  TCHZ Γ proxy under both shapes, so no Voigt-specific compile-time path (and
  hence no device-tensor-in-frozen-state risk beyond Gotcha (1) above).

### Design (decided)

- **Autodiff strategy: torch accelerates the *forward*; `torch.func.jacfwd`
  is the fp64-CPU cross-check.** The analytic peak-chain columns are already
  exact and cheap, so on MPS the win is forward throughput (batched
  einsum/exp/`window_add`), not autodiff. Use `torch.func.jacfwd`/`vmap` over
  one-hot seeds on **CPU fp64** as an independent Jacobian for the WP-0404
  matrix — that is what proves the torch impl of the op set is correct.
- **`window_add` / `segment_sum` on torch:** both via `index_add` on the
  frozen window range; keep the functional signature from 0401.
- **Packaging/wiring:** optional `[torch]` extra; lazy import inside
  `set_backend("torch")` so numpy-only users are unaffected; flip the
  `backend="torch"` `NotImplementedError` in `refine.py`/`multi.py`. Device
  and dtype come from the WP-0403 policy, not from ad-hoc flags.
- **Benchmark, reported not gated:** `examples/bench_torch_mps.py` times the
  forward evaluation and a full refine, MPS vs numpy, on the 11-BM NAC
  pattern (synchrotron, single wavelength — the simplest hot loop) and SRM
  676a corundum. Wall-clock is hardware-dependent, so it is **reported** in
  the milestone record, never asserted as a threshold.

## Non-goals

torch autodiff replacing the analytic Jacobian on the numpy path; fp64 on
MPS (does not exist); CUDA-specific work (WP-0403 owns the policy and its
deferred CUDA script); the TOPAS-style bounded LM solver (WP-0601).

## Tasks

- [ ] `[torch]` extra; `TorchBackend` on the 0401 op set (`window_add`/
      `segment_sum` via `index_add`; complex128 CPU / complex64 MPS); device
      and dtype selected by the WP-0403 policy
- [ ] `torch.func.jacfwd`/`vmap` fp64-CPU Jacobian; add the torch row to the
      WP-0404 matrix
- [ ] MPS fp32 forward + fp32 Jacobian columns crossing the `linalg64.py`
      fp64 host boundary
- [ ] Wire `backend="torch"` through `refine.py`/`multi.py`; add the
      `uv pip install -e ".[dev,jax,torch]"` line to CLAUDE.md commands
- [ ] `examples/bench_torch_mps.py`: MPS vs numpy wall-clock on 11-BM NAC and
      SRM 676a (reported)
- [ ] Tests (`pytest.importorskip("torch")`): torch-fp64-CPU Jacobian
      agreement <5e-3 / cosine >0.99999; torch-MPS-fp32 SRM 676a refine
      matches the numpy `a` within 3e-5 Å; the numpy path is unaffected +
      obs/calc/diff PNGs to `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_backend_torch.py -q   # skips without torch
.venv/bin/python examples/bench_torch_mps.py                # reports MPS vs numpy, not gated
```

Measured: the torch fp64-CPU Jacobian agrees with the analytic and jax
Jacobians to <5e-3 rel-L2 / cosine >0.99999; a torch-MPS fp32 refine of SRM
676a matches the numpy `a` within 3e-5 Å (the WP-0403 fp32-column band); the
MPS-vs-numpy speedup on 11-BM NAC is recorded in the milestone record.

## References

- [../DESIGN.md](../DESIGN.md#locked-decisions) — the no-Apple-fp64 hard
  constraint and the 2026-07-24 amendment moving `[torch]` into v0.4.
- Higham (2002) *Accuracy and Stability of Numerical Algorithms*, 2nd ed.,
  SIAM — why the solve stays fp64 (shared with WP-0403).
- `torch.func` (`jacfwd`, `vmap`) documentation.

## Handover log

- **2026-07-22** — created as a stub (WP-0603, v0.6) from the ROADMAP split.
- **2026-07-24** — **moved to WP-0408 / v0.4** and expanded (v0.4 planning
  session). Rationale: the maintainer wants local GPU acceleration, which
  jax cannot provide on Apple hardware; sequencing after 0402+0404 preserves
  the one-autodiff-backend-at-a-time discipline. Strategy decided: torch
  accelerates the forward on MPS fp32 under the 0403 policy, with
  `torch.func.jacfwd` on CPU fp64 as the agreement cross-check; benchmark
  reported, not gated.

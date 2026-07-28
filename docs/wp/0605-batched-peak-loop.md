# WP-0605 — Batched peak loop (spike, then decide)

Milestone: v0.6 · Status: ⬜ not started
Depends on: — (informed by WP-0401, WP-0404, WP-0408)

## Goal

Decide, **with measurements rather than reasoning**, whether the per-(emission
line, reflection) python loop in `model/forward.py` should become a padded
batched evaluation — and only then write it. The deliverable of this WP is a
recorded go/no-go plus answers to the three design questions below. The rewrite
itself is explicitly Phase 2 and out of scope here.

## Context

The forward model evaluates each reflection on its own frozen window, one at a
time in python: ~130 windows per pattern, each a profile evaluation (~20
elementwise ops) plus a `window_add`. A forward is therefore a few thousand tiny
array operations, and **every backend is ~100 % dispatch-bound at that
granularity** — the per-op overhead (numpy ~0.6 µs, torch-CPU ~2 µs, MPS
~110-165 µs) times the op count *is* the runtime, with arithmetic nowhere in it.

WP-0408 measured what restructuring would buy, at fixed total work, by comparing
128 windows × 900 points against one kernel of 115 200 points
(`examples/bench_torch_mps.py`, which prints this):

| shape | elements | numpy | torch-CPU | MPS |
|---|---|---|---|---|
| 128 × 900 | 115 200 | 1.36 ms | 4.34 | 10.57 |
| 1 × 115 200 | 115 200 | **0.56 ms** | 0.43 | 0.41 |

**≈2.4× on the numpy path** — the default every user runs, no optional
dependency. That is this WP's entire justification. It is *not* GPU enablement,
and the same script pins why: sweeping one kernel across sizes puts **break-even
at ≈50-65 k elements and the ceiling at ≈2.5-3×** (the peak chain is ~17 flops
per element, i.e. memory-bound, so a device's arithmetic throughput never
participates). One batched kernel per pattern is 121 k elements for 11-BM NAC,
38 k for lab corundum, 17 k for SRM 660c — so a single lab pattern is *below
break-even even after batching*, and reaching the plateau needs ≈10 (synchrotron)
to ≈60 (lab) patterns processed together, i.e. the v2-fenced in-situ series. See
[../DESIGN.md](../DESIGN.md#locked-decisions), dated 2026-07-27. **Do not adopt
this WP hoping for a GPU win, and do not let it grow into that.**

Why it is a spike and not a rewrite: `model/forward.py`'s loop is the most
invariant-dense code in the package (frozen-per-stage discreteness, the
accumulation order that six bit-identity goldens pin, the analytic Jacobian's
shared expansion). A 2.4× wall-clock win does not license rewriting that on
faith.

### Inherited

From **WP-0505** (sequential series, landed 2026-07-28): **the "batch many
patterns" case now has an API to live behind.** WP-0408 measured that a device
only pays at ≈10 synchrotron / ≈60 lab patterns batched together and fenced the
`vmap`-batched series to v2; `pxrdref.sequential.SequentialRefinement` is now
where such a series is expressed, and it walks patterns strictly one at a time
(`_chain`). So if the batched-loop spike here ever grows a multi-pattern form,
`_chain` is the single call site to change, and its warm-start chain is the
reason a naive batch is *not* equivalent: pattern k's starting values are
pattern k−1's answers, so patterns in a chain cannot be evaluated
simultaneously. A batched series has to batch across independent chains (or
give up the warm start), which is a design constraint that did not exist before
this WP and is not visible from the timing numbers alone.

From **WP-0408** (torch backend, landed 2026-07-27) — the measurements above,
plus three constraints that are already known and need not be rediscovered:

- **`torch.compile` is not an alternative to batching.** Measured: 2.5× slower
  than eager on CPU (13.5 vs 5.4 ms) after a 38 s compile; on MPS it fails,
  dynamo hitting its recompile limit because `i0, i1 = cp.win[il, k]` and the
  `arange(i0, i1)` in `window_add` specialise on each window's literal bounds, so
  it attempts one graph per reflection. Any batched design that keeps
  per-window python-int bounds inherits that.
- **Padding cost is already sized on real states** (compiled models, measured
  2026-07-27):

  | state | reflections × lines | window widths | padding waste, profile plane | with FCJ nodes |
  |---|---|---|---|---|
  | 11-BM NAC | 129 × 1 | 35-939 (mean 865) | 1.09× | 1.09× (no FCJ) |
  | SRM 660c | 30 × 2 | 171-276 | 1.23× | 3.06× (4 MB fp64) |
  | corundum + FCJ | 64 × 2 | 91-296 | 1.49× | **3.98×** (9 MB fp64) |

  The profile plane pads cheaply; **the FCJ node axis is where padding hurts**,
  because node counts vary per reflection (0-64). Extrapolated to a large problem
  — 2000 reflections × 2 lines × 64 nodes × 300 points — the padded tensor is
  ~615 MB fp64, which is the memory question Phase 1 must answer.
- **The hot-path rules from the three-backend era still bind** (CLAUDE.md
  Conventions): no frozen numpy constant on the left of an operator against a
  θ-derived value, and any new op lands on numpy, jax *and* torch together.

## Non-goals

The rewrite itself (Phase 2, a separate WP or a follow-on once this one says go);
GPU acceleration of single-pattern refinement (measured not to exist — the fence
above); `vmap`-batched multi-pattern/in-situ refinement (v2); touching the
analytic Jacobian's *consumers* in `optimize/least_squares.py`.

## Tasks

- [ ] **Prototype** the batched layout for one phase, symmetric peaks only
      (`fcj_n == 0`), against the 11-BM NAC state, in a scratch module or a test
      — **the shipped path is not modified in this WP**. Measure forward time on
      numpy/torch/MPS, peak memory, and elementwise agreement with the current
      loop.
- [ ] **Extend the prototype to the FCJ case** on the corundum state (padded
      `(N, max_nodes, W)` with zero weights on the pad) and measure whether the
      3-4× padding waste eats the win; if it does, measure the two mitigations —
      chunking over reflections (precedent: `DEFAULT_CHUNK` in
      `backend/jax_backend.py` / `backend/torch_backend.py`) and bucketing
      reflections by node count.
- [ ] **Answer the three design questions** (below), in writing, in this file.
- [ ] **Record the go/no-go** in the handover log with the measured numbers, and
      either open the Phase-2 WP or close this one with the reason.

### The three design questions

1. **Does `window_add` survive, or does the op set have to grow?** The batched
   form needs a padded-window scatter rather than the contiguous-window one.
   The indices remain frozen at stage compile, so this does not violate the
   *intent* of frozen-per-stage discreteness — which forbids **data-dependent**
   indices, not compile-time ones — but it does widen the vocabulary that
   `backend/api.py`'s docstring keeps deliberately minimal, and every op added is
   a three-backend liability. Decide whether a padded `window_add` replaces the
   current one or joins it.
2. **Does `derivative_bases` have to move too?** `CompiledModel.derivative_bases`
   carries the *same* per-reflection loop and hands ragged per-reflection entries
   to `_peak_chain_column` / `_axial_column` in `optimize/least_squares.py`. It is
   also the dominant cost — the numpy Jacobian is 13-23 ms against a 2-5 ms
   forward — so **batching only the forward captures a minority of the win**, and
   batching both means changing the entries contract that three call sites read.
3. **What guards the numerics?** `tests/test_backend_shim.py` asserts
   **bit-identity** against six goldens in `tests/data/backend_goldens/`.
   Reordering an accumulation changes the last bits. State up front whether the
   batched path is expected to be bit-identical (achievable if per-window
   accumulation order is preserved — a scatter-add over disjoint windows is, a
   fused reduction is not) or whether it needs a re-baseline per
   `tests/data/README.md`. The second is a far larger claim and should not be
   discovered halfway through Phase 2.

## Acceptance

```sh
.venv/bin/python examples/bench_torch_mps.py   # the looped-vs-batched table this WP acts on
```

A go/no-go recorded in the handover log naming: the measured numpy speedup on
NAC *and* corundum (the FCJ case is the one at risk), the memory ceiling and the
chosen mitigation, and a written answer to each of the three questions. **No
production code changes in this WP** — if the prototype lands anywhere it is in
a test or a scratch example.

## References

- `examples/bench_torch_mps.py` — the dispatch-cost and looped-vs-batched
  microbenchmarks this WP is built on.
- [../DESIGN.md](../DESIGN.md#locked-decisions) — the dated 2026-07-27
  measurements, including why this is not a GPU story.
- `tests/data/README.md` — the golden re-baseline rule, if question 3 needs it.

## Handover log

- **2026-07-27** — created from WP-0408's follow-up measurements. Scoped
  deliberately as a spike: the ≈2.4× numpy win is real and worth having, but the
  code it touches is the most invariant-dense in the package, and the original
  framing of this work (as Apple-GPU enablement) was measured to be wrong before
  any of it was written. Not started.

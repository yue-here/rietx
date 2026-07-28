"""Time the torch backends against numpy on real patterns (WP-0408).

**Reported, never gated.**  Wall-clock is hardware-, thread- and thermal-
dependent, so no test asserts a speedup and none should; the numbers this
prints go into the milestone record as a measurement of one machine.  What *is*
asserted, in ``tests/test_backend_torch.py`` and WP-0404's matrix, is that every
backend computes the same Jacobian.

What is timed
-------------
Two patterns, chosen for opposite hot-loop shapes:

* **11-BM NAC** — synchrotron, one wavelength, no axial asymmetry: the simplest
  possible peak chain, so the loop overhead per reflection dominates.
* **SRM 676a corundum** — lab Cu Kα doublet through a graphite monochromator,
  *with the axial aperture opened* so FCJ quadrature is live: ~2 lines × tens of
  nodes more arithmetic per reflection, which is where a GPU has something to
  bite on.  (The acceptance test runs the same specimen with S/L = H/L = 0, i.e.
  no asymmetry; that would make this pattern the cheaper of the two, not the
  richer, so the benchmark sets them.)

and two quantities per (pattern, backend):

* one **forward** evaluation of the weighted residual — the thing a device
  accelerates;
* one full **Jacobian** — n_free columns, which is where the backends actually
  differ in *kind* (numpy assembles analytic peak-chain columns and does not
  evaluate the forward once per parameter; torch runs a vmapped ``jvp``, i.e.
  the whole forward per seed).

That last asymmetry is the honest headline: the numpy path is not "the same
algorithm on the CPU".  A per-column comparison against an analytic assembly
flatters no autodiff backend, and reading these numbers as "torch is slower
than numpy" would miss that the analytic chain is what is fast, not numpy.

The microbenchmarks
-------------------
The pattern timings above say the GPU is slow; they do not say *why*, and the
prose that used to stand here guessed.  So this script also measures the three
things the explanation rests on, and every number quoted in DESIGN.md and
WP-0408 is readable off its output:

* **per-op cost vs array width** — one ``exp()`` per backend across five decades
  of size.  If a backend's cost is flat in the width, that backend is paying
  launch latency, not arithmetic, and the fix cannot be "fewer flops".
* **looped vs batched at fixed total work** — K windows of W points against one
  window of K·W points, same arithmetic either way.  The ratio is exactly what
  restructuring the peak loop would buy, per backend, with no model changes and
  no guessing.
* **the crossover** — one kernel of N elements, GPU against numpy, swept across
  the size where the device stops losing and starts winning.  This is the number
  to quote when someone asks "is a GPU worth it here": **break-even ≈ 50-65 k
  elements per kernel, and the ceiling is only ≈2.5-3×**, because ~17 flops per
  element is memory-bound work in which a GPU's arithmetic throughput never
  participates (measured ~10 G-element/s device vs ~3 G-element/s host, and
  roughly half of even that gap is fp32 moving half the bytes of numpy's fp64).

Measured (2026-07-27, Apple-silicon Mac, torch 2.13, best of 3)
---------------------------------------------------------------
**MPS is 60-125× slower than numpy here, and the reason is the loop shape, not
the device.**  On 11-BM NAC the forward runs 1.9 ms (numpy) / 5.7 ms (torch CPU)
/ 359 ms (MPS); on corundum-with-FCJ 5.5 / 13.7 / 689 ms.  The printed hot-loop
line is the diagnosis: ~130 windows of 200-900 points each, evaluated one at a
time in python, so a forward is a few thousand kernel launches.  MPS per-op cost
is **flat at 110-165 µs from 64 to 65 536 elements** (numpy: 0.3 µs at 64), i.e.
pure launch latency; it overtakes numpy only at ~10⁶ elements per kernel
(255 µs vs 1588 µs, a 6× win — the one row where the device behaves like a GPU).

**But batching does not turn this into a GPU win, and that is the part the first
draft of this file got wrong.**  At fixed total work, 128×900 → 1×115 200 takes
MPS from 10.6 ms to ~0.4 ms (26×) — and numpy from 1.36 ms to ~0.55 ms.  A single
batched pattern sits right at the crossover (65 k elements → 0.99×; 131 k →
1.47×), so the device would buy a small factor at best, against an fp32
constraint and an optional dependency.  So:

* **the batched peak loop is worth doing for the *numpy* path** (1.36 → 0.56 ms,
  2.4×, no optional dependency, every user), not as GPU enablement — scoped in
  WP-0605;
* **the GPU case needs a bigger problem** — and is worth ≈2.5-3× when it
  arrives, not an order of magnitude.  One batched kernel per pattern is 121 k
  elements for 11-BM NAC, 38 k for lab corundum, 17 k for SRM 660c, so reaching
  the plateau means processing **≈10 (synchrotron) to ≈60 (lab) patterns
  together**: a ``vmap``-batched in-situ/parametric series, which is v2-fenced.
  A single lab pattern is below break-even even after batching.

``torch.compile`` does not rescue it either: on CPU the compiled residual is
**2.5× slower** than eager (13.5 vs 5.4 ms) after a 38 s one-off compile, and on
MPS it fails — dynamo hits its recompile limit because ``i0, i1 = cp.win[il, k]``
and ``arange(i0, i1)`` specialise on each window's literal bounds, so it tries to
build one graph per reflection.  The loop shape defeats compilation for the same
reason it defeats the GPU.

So the WP-0408 deliverable that survives is the *correctness* one: torch fp64 on
CPU is an independent third opinion in WP-0404's agreement matrix, and MPS gives
the first real-hardware confirmation that WP-0403's fp32-column policy converges
to the same answer (SRM 676a cell within 3e-5 Å — ``tests/test_backend_torch.py``).

Usage::

    python examples/bench_torch_mps.py
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.optimize.least_squares import _jacobian_for, _make_residual
from pxrdref.params.vector import ParameterTable

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"

#: the free set: one of every column family that costs real work
FREE_GLOBS = ("phases.*.scale", "phases.*.cell.*", "instrument.background.*",
              "instrument.profile.*", "instrument.zero_shift",
              "phases.*.atoms.*.biso")

#: repeats per timing; the reported number is the *best* of these, which is the
#: standard way to time on a machine that also has other work to do
REPEATS = 3


def available_backends() -> list[str]:
    """numpy plus whichever optional backends this machine actually has."""
    names = ["numpy"]
    try:
        import jax  # noqa: F401

        names.append("jax")
    except ImportError:
        pass
    try:
        import torch

        names.append("torch")
        if torch.backends.mps.is_available():
            names.append("torch-mps")
    except ImportError:
        pass
    return names


def nac_state():
    """11-BM NAC: synchrotron, single wavelength, no axial asymmetry."""
    path = DATA / "11BM_NAC.fxye"
    cif = DATA / "cod_1000236.cif"
    if not (path.exists() and cif.exists()):
        return None
    data = pr.read_pattern(path)
    structure = pr.Structure.from_cif(str(cif))
    instrument = pr.Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    from pxrdref.schemas.instrument import BackgroundChebyshev

    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument, (2.0, 24.0)


def corundum_state():
    """SRM 676a corundum: lab Cu Kα doublet + FCJ quadrature per reflection.

    The state of ``tests/test_acceptance_srm676a`` — inlined rather than imported,
    because an example must run from anywhere without the test package on the
    path.  α-Al₂O₃, R-3c on hexagonal axes (Lewis, Schwarzenbach & Flack, 1982,
    Acta Cryst. A38, 733) on the IUCr CPD round-robin's Philips Bragg-Brentano.
    """
    path = DATA / "qarr" / "corundum.prn"
    if not path.exists():
        return None
    data = pr.read_pattern(path)

    def p(v, **kw):
        return pr.Parameter(value=v, **kw)

    structure = pr.Structure(phases=[pr.Phase(
        name="corundum", space_group="R -3 c",
        cell=pr.Cell(a=p(4.7593, min=1.0), b=p(4.7593, min=1.0),
                     c=p(12.9917, min=1.0), alpha=p(90.0), beta=p(90.0),
                     gamma=p(120.0)),
        atoms=[pr.Atom(label="Al", species="Al", x=p(0.0), y=p(0.0),
                       z=p(0.35216), biso=p(0.30, min=0.0, max=25.0)),
               pr.Atom(label="O", species="O", x=p(0.30624), y=p(0.0),
                       z=p(0.25), biso=p(0.30, min=0.0, max=25.0))],
        scale=p(1e-3, min=0.0, transform="softplus"),
        lor_size=p(0.02, min=0.0, transform="softplus"))])
    instrument = pr.Instrument.bragg_brentano(radiation="CuKa",
                                             goniometer_radius_mm=173.0,
                                             monochromator_two_theta=26.6)
    from pxrdref.schemas.instrument import BackgroundChebyshev

    instrument.background = BackgroundChebyshev.with_terms(6)
    # a real axial aperture, so the FCJ quadrature is live — see the module
    # docstring on why the benchmark sets what the acceptance test leaves at zero
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.030
    # seed the scale so the calculated intensity is in the data's decade (the
    # acceptance test's seed_scales, for one phase)
    model = compile_model(structure, instrument, data, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    obs = np.asarray(data.intensity)
    structure.phases[0].scale.value *= float(
        (obs.sum() - obs.min() * len(obs)) / max(float(y.sum()), 1e-9))
    return data, structure, instrument, None


def compile_state(data, structure, instrument, limits):
    table = ParameterTable(structure, instrument)
    table.set_vary(["*"], False)
    for glob in FREE_GLOBS:
        table.set_vary([glob], True)
    model = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=limits,
                          free_paths=set(table.free_paths))
    return model, table


def best_of(fn, *, repeats: int = REPEATS) -> float:
    """Seconds for the fastest of ``repeats`` calls, one warm-up discarded.

    The warm-up matters: the first torch call pays lazy kernel compilation (and
    on MPS, pipeline-state creation), which is a one-off per process, not a cost
    the solver pays per iteration.
    """
    fn()
    return min(_time_once(fn) for _ in range(repeats))


def _time_once(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def bench(label: str, state, backends: list[str]) -> None:
    if state is None:
        print(f"\n{label}: dataset not present — skipped")
        return
    data, structure, instrument, limits = state
    model, table = compile_state(data, structure, instrument, limits)
    theta = table.x0()
    n_points, n_free = len(model.tt), len(theta)
    n_refl = sum(len(cp.reflections) for cp in model.phases)
    n_nodes = sum(int(cp.fcj_n.sum()) for cp in model.phases)
    # the number that explains the result: one `window_add` (and a whole profile
    # evaluation) per non-empty (line, reflection) window, each over a slice this
    # wide.  A few thousand kernel launches of a few hundred elements is a shape
    # in which per-launch overhead, not arithmetic, is the cost — quantified by
    # the two microbenchmarks below.
    widths = np.concatenate([(cp.win[..., 1] - cp.win[..., 0]).ravel()
                             for cp in model.phases])
    widths = widths[widths > 0]
    print(f"\n{label}: {n_points} points, {n_refl} reflections × "
          f"{len(model.line_wavelengths)} line(s), {n_nodes} FCJ nodes, "
          f"{n_free} free parameters")
    print(f"  hot loop: {widths.size} windows of {widths.mean():.0f} points mean "
          f"({widths.min()}-{widths.max()})")

    # the forward is backend-dispatched through the *global* backend, so time it
    # by flipping that; the Jacobian callables carry their own backend
    residual = _make_residual(model, table)
    base_forward = best_of(lambda: residual(theta))
    print(f"  {'backend':10s}  {'forward':>10s}  {'vs numpy':>9s}  "
          f"{'jacobian':>10s}  {'vs numpy':>9s}  {'per column':>10s}")
    base_jac = None
    for name in backends:
        jac = _jacobian_for(model, table, name)
        t_jac = best_of(lambda: jac(theta))
        t_fwd = base_forward if name == "numpy" else _forward_on(name, model, table, theta)
        base_jac = base_jac if base_jac is not None else t_jac
        print(f"  {name:10s}  {t_fwd * 1e3:9.2f}ms  {base_forward / t_fwd:8.2f}×  "
              f"{t_jac * 1e3:9.2f}ms  {base_jac / t_jac:8.2f}×  "
              f"{t_jac / n_free * 1e3:9.2f}ms")


# ----------------------------------------------------------------------
# the two microbenchmarks the explanation rests on
# ----------------------------------------------------------------------
#: array widths for the per-op sweep — five decades, spanning "smaller than any
#: peak window" to "larger than a whole pattern"
_OP_WIDTHS = (64, 1024, 8192, 65536, 1048576)

#: (windows, width) shapes at ~fixed total work.  The first is the peak loop's
#: actual shape on 11-BM NAC; the last is that same work as one kernel.
_LOOP_SHAPES = ((128, 900), (128, 90), (16, 900), (1, 115200))

#: widths for the crossover sweep — one kernel each, spanning the size where the
#: GPU stops losing and starts winning.  This is the number a reader actually
#: wants: "how big does an array have to be before the device is worth it".
_CROSSOVER_WIDTHS = (16384, 65536, 131072, 524288, 1048576, 4194304)

#: elementwise ops per window in the synthetic loop — roughly a pseudo-Voigt
#: (the real one is ~20 including the profile normalisation and the mask)
_OPS_PER_WINDOW = 17


def _timed_op(kind: str, width: int) -> float:
    """One ``exp()`` on ``width`` elements, on backend ``kind``."""
    if kind == "numpy":
        a = np.ones(width)
        return best_of(lambda: np.exp(a), repeats=20)
    import torch

    dev = "cpu" if kind == "torch" else "mps"
    t = torch.ones(width, dtype=torch.float64 if dev == "cpu" else torch.float32,
                   device=dev)
    if dev == "cpu":
        return best_of(lambda: torch.exp(t), repeats=20)

    def run():
        torch.exp(t)
        torch.mps.synchronize()   # else we would time the enqueue, not the work

    return best_of(run, repeats=20)


def _timed_loop(kind: str, n_windows: int, width: int) -> float:
    """``n_windows`` × (a pseudo-Voigt-ish chain + a scatter-add), the peak loop's
    shape, with the total element count held by the caller."""
    if kind == "numpy":
        y, x = np.zeros(n_windows * width), np.ones(width)

        def run():
            out = y.copy()
            for k in range(n_windows):
                u = x * 1.7 + 0.3
                for _ in range(6):
                    u = u * 1.0001 + 0.5
                out[k * width:(k + 1) * width] += np.exp(-u * u) / (1.0 + u * u)
            return out
    else:
        import torch

        dev = "cpu" if kind == "torch" else "mps"
        dt = torch.float64 if dev == "cpu" else torch.float32
        y = torch.zeros(n_windows * width, dtype=dt, device=dev)
        x = torch.ones(width, dtype=dt, device=dev)

        def run():
            out = y.clone()
            for k in range(n_windows):
                u = x * 1.7 + 0.3
                for _ in range(6):
                    u = u * 1.0001 + 0.5
                v = torch.exp(-u * u) / (1.0 + u * u)
                idx = torch.arange(k * width, (k + 1) * width, device=dev)
                out = out.index_add(0, idx, v)
            if dev == "mps":
                torch.mps.synchronize()
            return out

    return best_of(run)


def microbenchmarks(backends: list[str]) -> None:
    """Why the pattern timings look the way they do — dispatch, not arithmetic —
    and how big an array has to be before a device is worth using at all."""
    kinds = [b for b in backends if b in ("numpy", "torch", "torch-mps")]

    print("\nper-op cost — one exp(), microseconds per call")
    print("  a backend whose cost is FLAT in the width is paying launch latency,")
    print("  not arithmetic, and no amount of fp32 will fix that")
    print("  " + f"{'elements':>10}" + "".join(f"{k:>12}" for k in kinds))
    for width in _OP_WIDTHS:
        row = "".join(f"{_timed_op(k, width) * 1e6:12.1f}" for k in kinds)
        print(f"  {width:>10}{row}")

    print("\nlooped vs batched — same arithmetic, different number of kernels (ms)")
    print(f"  ~{_OPS_PER_WINDOW} ops per window; the last row is the first row's")
    print("  work as ONE kernel, i.e. what batching the peak loop would buy")
    print("  " + f"{'windows':>8}{'width':>8}{'elements':>10}"
          + "".join(f"{k:>12}" for k in kinds))
    for n_windows, width in _LOOP_SHAPES:
        row = "".join(f"{_timed_loop(k, n_windows, width) * 1e3:12.2f}" for k in kinds)
        print(f"  {n_windows:>8}{width:>8}{n_windows * width:>10}{row}")

    if "torch-mps" not in kinds:
        return
    print("\ncrossover — one kernel of N elements, GPU vs numpy (ms, and speedup)")
    print("  break-even is where the speedup passes 1.0; the plateau above it is")
    print("  the ceiling, because ~17 flops/element is memory-bound work and a")
    print("  GPU's arithmetic throughput never comes into it")
    print("  " + f"{'elements':>10}{'numpy':>10}{'torch-mps':>11}{'speedup':>10}")
    for width in _CROSSOVER_WIDTHS:
        t_np = _timed_loop("numpy", 1, width)
        t_mps = _timed_loop("torch-mps", 1, width)
        print(f"  {width:>10}{t_np * 1e3:10.3f}{t_mps * 1e3:11.3f}"
              f"{t_np / t_mps:9.2f}×")


def _forward_on(name: str, model, table, theta) -> float:
    """One residual evaluation with ``name`` installed as the global backend.

    Uses each backend's own traced residual (its ``decode`` twin included), which
    is what the Jacobian differentiates — not the numpy closure with a backend
    bolted on.
    """
    from pxrdref.backend import resolve_backend, set_backend

    xp = resolve_backend(name)
    if name == "jax":
        from pxrdref.backend.jax_backend import _enable_x64, make_traced_residual

        residual = None
        set_backend(xp)
        try:
            with _enable_x64():
                residual = make_traced_residual(model, table)
                return best_of(lambda: np.asarray(residual(theta)))
        finally:
            set_backend("numpy")
    from pxrdref.backend.torch_backend import make_traced_residual

    set_backend(xp)
    try:
        residual = make_traced_residual(model, table, xp)
        t = xp.asarray(theta, dtype=np.float64)
        return best_of(lambda: np.asarray(residual(t).detach().cpu()))
    finally:
        set_backend("numpy")


def main() -> None:
    backends = available_backends()
    print(f"backends: {', '.join(backends)}")
    if "torch" in backends:
        import torch

        print(f"torch {torch.__version__}, mps available: "
              f"{torch.backends.mps.is_available()}")
    bench("11-BM NAC (synchrotron, 1 line)", nac_state(), backends)
    bench("SRM 676a corundum (Cu Kα doublet + FCJ)", corundum_state(), backends)
    microbenchmarks(backends)
    print("\nReported, not gated — see the module docstring on why the numpy "
          "Jacobian column is not the same algorithm, and why the batched row "
          "above is a numpy win rather than a GPU one.")


if __name__ == "__main__":
    main()

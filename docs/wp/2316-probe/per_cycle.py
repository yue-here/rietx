"""WP-2316: the Le Bail evidence cases, one row per case.

    .venv/bin/python -u docs/wp/2316-probe/per_cycle.py [case ...]

Cases:

- ``740``: issue #740's pattern (``tests/test_lebail_cycles.py``'s fixture),
  ``profile_only`` in Le Bail.  Cell error against the true cell in ppm, and
  Rwp against the true structure's Rwp on the same pattern.
- ``bigcell-seeded`` / ``bigcell-unseeded``: ``examples/bench_refinement.py``'s
  ``bigcell-lebail``, from its seeded background and from probe 1's
  all-zero Chebyshev of 6 terms.  Wall, Rwp, evaluations, cell against truth.

Each row prints one line of numbers.  ``--plot DIR`` writes an obs/calc/diff
PNG per case.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402

BIG_TRUE = {"a": 12.0, "b": 36.0, "c": 4.0}


def _ppm(result, truth):
    values = {p.path: p.value for p in result.parameters}
    return {k: (values[f"phases.0.cell.{k}"] - v) / v * 1e6 for k, v in truth.items()}


def _plot(result, name, out):
    if out is None:
        return
    from rietx.viz.plots import plot_result
    out.mkdir(parents=True, exist_ok=True)
    plot_result(result, path=str(out / f"{name}.png"))


GRID = np.arange(10.0, 150.0, 0.1)
LIMITS = (10.0, 150.0)
TRUE_CELL = {"a": 5.74, "b": 7.69, "c": 5.54}


def _refinement(data):
    from tests.test_auto_background_seed import _neutron, _phase
    ins = _neutron()
    ins.background = rx.auto_background(data, two_theta_limits=LIMITS, seed=True).background
    return rx.Refinement(rx.Structure(phases=[_phase(1.0)]), ins)


def _plan():
    from rietx.strategy.staged import resolve_plan
    return resolve_plan("profile_only", "lebail")


def case_740(out):
    from tests.test_auto_background_seed import _neutron, _phase
    truth = rx.Refinement(rx.Structure(phases=[_phase(1.0)]), _neutron())
    y = np.asarray(truth.predict(GRID)) + 300.0 + 2.0 * GRID
    y = np.maximum(y + np.random.default_rng(1).normal(
        scale=np.sqrt(np.maximum(y, 1.0))), 0)
    data = rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())
    from rietx.strategy.staged import Stage
    true = _refinement(data).fit(
        data, plan=rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"])]),
        telemetry=False)
    ref = _refinement(data)
    t0 = time.perf_counter()
    res = ref.fit(data, mode="lebail", plan=_plan(), telemetry=False)
    wall = time.perf_counter() - t0
    ppm = _ppm(res, TRUE_CELL)
    print(f"740: wall {wall:.1f} s  rwp {res.statistics.rwp:.5f}  true-structure rwp "
          f"{true.statistics.rwp:.5f}  ratio {res.statistics.rwp / true.statistics.rwp:.4f}  "
          f"max|cell ppm| {max(abs(v) for v in ppm.values()):.2f}  ppm {ppm}  "
          f"codes {[d.code for d in res.diagnostics if d.level != 'info']}")
    for s in res.stages:
        print("   ", s.name, s.status, s.n_iterations, f"{s.rwp:.5f}",
              getattr(s, "lebail_cycles_run", None))
    _plot(res, "wp2316_740", out)


def _bigcell(seeded: bool, out):
    import bench_refinement as b
    from rietx.schemas.instrument import BackgroundChebyshev
    setup = b._bigcell_lebail() if seeded else b._bigcell(
        "lebail", 90.0, 10, rx.RefinementPlan.mccusker_default(), "mccusker_default")
    if not seeded:
        setup.instrument.background = BackgroundChebyshev.with_terms(6)
    ref = rx.Refinement(setup.structure, setup.instrument, history=False)
    t0 = time.perf_counter()
    res = ref.fit(setup.data, mode="lebail", plan=setup.plan, telemetry=False)
    wall = time.perf_counter() - t0
    ppm = _ppm(res, BIG_TRUE)
    name = "seeded" if seeded else "unseeded"
    print(f"bigcell-{name}: wall {wall:.1f} s  rwp {res.statistics.rwp:.5f}  "
          f"nfev {sum(s.n_iterations for s in res.stages)}  ppm "
          f"{ {k: round(v, 1) for k, v in ppm.items()} }  codes "
          f"{[d.code for d in res.diagnostics if d.level != 'info']}")
    for s in res.stages:
        print("   ", s.name, s.status, s.n_iterations, f"{s.rwp:.5f}",
              getattr(s, "lebail_cycles_run", None))
    _plot(res, f"wp2316_bigcell_{name}", out)


CASES = {"740": case_740,
         "bigcell-seeded": lambda out: _bigcell(True, out),
         "bigcell-unseeded": lambda out: _bigcell(False, out)}

if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--plot" in args:
        i = args.index("--plot")
        out = Path(args[i + 1])
        del args[i:i + 2]
    for name in args or list(CASES):
        if name not in CASES:
            sys.exit(f"unknown case {name!r}; known: {', '.join(CASES)}")
        CASES[name](out)

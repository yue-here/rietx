"""C19: the Le Bail partition at an intermediate stage's 1e-6 end point (WP-2018, task 3).

``CompiledModel.lebail_update`` runs after each stage's solve, so in every
intermediate stage it partitions at the point ``intermediate_ftol`` (1e-6)
stopped the solve, and the next stage starts from those intensities.  The
fixture is ``tests/test_lebail_cycles.py``'s (#740's synthetic Pnma LaMnO₃,
CW neutron 2.4 Å, FWHM 0.5°, true cell known), fitted with the
``profile_only`` Le Bail plan as that module does, in four arms:

  close_1e-6   shipped: intermediate stages at 1e-6, closing stage appended
  close_none   ``intermediate_ftol = None``: every stage at 1e-9
  open_1e-6    ``closing_window_tol = None`` (no closing stage), 1e-6
  open_none    no closing stage, every stage at 1e-9
  close_<tol>  any other tolerance, the positive arms (1e-2, 1e-1, 5e-1): a
               looser stop that should move the partition if the tolerance binds

Per arm: the cell (value, esd, ppm from the truth), Rwp and the true
structure's Rwp on the same pattern, per stage its tolerance, iterations and
the partition's cycles and whether it settled, and the extracted intensities
(written once per arm, so arms can be differenced).

usage (repo root): python docs/wp/2018-measure/lebail_ftol.py [arm ...]
"""
from __future__ import annotations

import dataclasses
import importlib
import os
import sys

from common import OUT, diagnostics, emit, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from rietx.strategy.staged import Stage  # noqa: E402
from tests.test_lebail_cycles import TRUE_CELL, _plan, _refinement  # noqa: E402

refine_module = importlib.import_module("rietx.refine")

ARMS = ("close_1e-6", "close_none", "open_1e-6", "open_none")


def _pattern():
    # the module's ``pattern`` fixture body, called directly
    import numpy as np

    from tests.test_auto_background_seed import _neutron, _phase
    from tests.test_lebail_cycles import GRID
    truth = rx.Refinement(rx.Structure(phases=[_phase(1.0)]), _neutron())
    y = np.asarray(truth.predict(GRID)) + 300.0 + 2.0 * GRID
    y = np.maximum(y + np.random.default_rng(1).normal(
        scale=np.sqrt(np.maximum(y, 1.0))), 0)
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


def fit(arm: str, data):
    closing, tol = arm.split("_")
    plan = _plan()
    plan = dataclasses.replace(
        plan, intermediate_ftol=None if tol == "none" else float(tol),
        closing_window_tol=None if closing == "open" else plan.closing_window_tol)
    ref = _refinement(data)
    return ref, ref.fit(data, mode="lebail", plan=plan, telemetry=False)


def main(arms):
    data = _pattern()
    true = _refinement(data).fit(
        data, plan=rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"])]),
        telemetry=False)
    emit({"provenance": provenance(), "true_structure_rwp": true.statistics.rwp})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            ref, result = fit(arm, data)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rows = {p.path: p for p in result.parameters}
        cell = {ax: [rows[f"phases.0.cell.{ax}"].value, rows[f"phases.0.cell.{ax}"].stderr,
                     (rows[f"phases.0.cell.{ax}"].value - t) / t * 1e6]
                for ax, t in TRUE_CELL.items()}
        states = refine_module._extract_reflections(ref._model)
        emit({"arm": arm, "rwp": result.statistics.rwp, "status": result.status,
              "cell": cell,
              "stages": [{"stage": s.name, "ftol": s.ftol, "status": s.status,
                          "n_iterations": s.n_iterations, "rwp": s.rwp,
                          "lebail_cycles_run": list(s.lebail_cycles_run),
                          "lebail_settled": s.lebail_settled}
                         for s in result.stages],
              "params": {p.path: [p.value, p.stderr] for p in result.parameters},
              "intensities": [st.intensity for st in states],
              "hkl": [st.hkl for st in states],
              "diagnostics": diagnostics(result)})
        result.plot(path=str(OUT / f"c19_{arm}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

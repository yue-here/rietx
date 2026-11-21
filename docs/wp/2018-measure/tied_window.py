"""C3a: the support window on an unseen phase's cell that drives a visible one (WP-2018, task 3).

``ParameterTable.bounds`` windows a free cell column by its *path*
(``_cell_parameter_name``), so when an unseen phase's ``cell.a`` is the source
of a user tie that sets a visible phase's ``cell.a``, the window anchored on
the unseen phase also bounds the visible phase's cell.  The support hold reads
what a column *moves* (``column_reach``), so it never holds that source.  The
fixture is ``tests/test_absent_phase.py``'s (LaB₆ at 4.1606 Å, truth 4.15660,
plus a LaB₆ copy at 5.2 Å and scale 1e-9 that is not in the pattern), with
``ref.tie("phases.0.cell.a", "phases.1.cell.a", scale=4.1606/5.2)``, fitted
with ``mccusker_default``, in these arms:

  notie           the fixture as shipped, no tie (the visible phase's own answer)
  tie             the tie, everything as shipped
  tie_no_window   the tie, ``least_squares._freeze_cell_windows`` patched to
                  window no phase (hold, collapse and reset as shipped)
  tie_no_support  the tie, ``phase_support_sigma = None`` (no window, no hold,
                  no collapse)
  tie_narrow      the positive arm: the tie, the window patched to ±0.01 % with
                  no pad, so the source can move the visible cell by about
                  4.2e-4 Å per stage against the 4.0e-3 Å the fit must travel
  notie_narrow    the narrow window without the tie: the control that the
                  narrowed window alone does not reach the visible phase

Per arm: Rwp, both cells (committed values, and rows where the cell is a
column), every code, what each stage held and released.

usage (repo root): python docs/wp/2018-measure/tied_window.py [arm ...]
"""
from __future__ import annotations

import functools
import importlib
import os
import sys

from common import OUT, emit, patched, provenance, record

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from tests.test_absent_phase import _absent_phase_inputs  # noqa: E402
from tests.test_refine_synthetic import TRUE_A, synthesize  # noqa: E402

vector = importlib.import_module("rietx.params.vector")
lsq = importlib.import_module("rietx.optimize.least_squares")

ARMS = ("notie", "tie", "tie_no_window", "tie_no_support", "tie_narrow", "notie_narrow")
PATHS = ("phases.0.cell.a", "phases.0.scale", "phases.1.cell.a", "phases.1.scale")
RATIO = 4.1606 / 5.2


def fit(arm: str):
    plan = rx.RefinementPlan.mccusker_default()
    if arm == "tie_no_support":
        plan.phase_support_sigma = None
    structure, ins = _absent_phase_inputs()
    ref = rx.Refinement(structure, ins, history=False)
    if arm.startswith("tie"):
        ref.tie("phases.0.cell.a", "phases.1.cell.a", scale=RATIO)
    data = synthesize()
    if arm == "tie_no_window":
        real = lsq._freeze_cell_windows

        def no_window(model, table, sigma=None):
            real(model, table, None)          # None windows no phase
        with patched(lsq, "_freeze_cell_windows", no_window):
            return ref, ref.fit(data, plan=plan, telemetry=False)
    if arm.endswith("narrow"):
        narrow = functools.partial(vector.cell_window, fraction=1e-4)
        with patched(vector, "cell_window", narrow), \
                patched(vector, "CELL_WINDOW_PAD_A", 0.0):
            return ref, ref.fit(data, plan=plan, telemetry=False)
    return ref, ref.fit(data, plan=plan, telemetry=False)


def main(arms):
    emit({"provenance": provenance(), "fixture": "test_absent_phase + tie",
          "true_a": TRUE_A, "ratio": RATIO})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            ref, result = fit(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rec = record(result, PATHS)
        rec["arm"] = arm
        rec["cell_a"] = [p.cell.a.value for p in ref.structure.phases]
        rec["visible_a_minus_truth"] = ref.structure.phases[0].cell.a.value - TRUE_A
        rec["n_iterations"] = [s.n_iterations for s in result.stages]
        emit(rec)
        result.plot(path=str(OUT / f"c3a_{arm}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

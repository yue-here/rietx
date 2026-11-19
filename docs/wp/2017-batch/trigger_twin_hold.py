"""The width twin hold on the simulated ``trigger`` bench case (WP-2017 § Inherited, 2026-11-19).

Fits ``examples/bench_refinement.py``'s trigger pattern (seed 1111, drift 0) under the
shipped ``qpa_plan`` with the closing stage off, in four arms, and prints Rwp and the
instrument widths beside the simulation truth:

- ``shipped``: the tree as it is.
- ``no hold``: ``refine._hold_width_twins`` returns nothing, so U, X and Y stay free
  beside their specimen twins (the parent of ``1a4f5c52e``).
- ``no hold, 1.9.0 floors``: the same with U >= -0.05, V >= -0.5 and Y >= 0, which is
  the v1.9.0 fit.
- ``axial first``: the hold on, with ``lines_axial`` moved ahead of ``profile``.

Run from the repository root: ``.venv/bin/python docs/wp/2017-batch/trigger_twin_hold.py``
(about 15 s on an M-series Mac).
"""
import dataclasses
import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("bench_refinement",
                                              ROOT / "examples" / "bench_refinement.py")
bench = importlib.util.module_from_spec(spec)
sys.modules["bench_refinement"] = bench
spec.loader.exec_module(bench)

import rietx as rx  # noqa: E402
from test_acceptance_qpa_roundrobin import qpa_plan  # noqa: E402

refine_module = sys.modules["rietx.refine"]
shipped_hold = refine_module._hold_width_twins
data = bench._trigger_pattern(seed=1111, drift=0.0)


def plan(axial_first: bool) -> rx.RefinementPlan:
    p = dataclasses.replace(qpa_plan(), closing_window_tol=None)
    if axial_first:
        stages = list(p.stages)
        names = [s.name for s in stages]
        axial = stages.pop(names.index("lines_axial"))
        stages.insert(names.index("profile"), axial)
        p = dataclasses.replace(p, stages=stages)
    return p


def fit(label: str, *, hold: bool, old_floors: bool, axial_first: bool) -> None:
    refine_module._hold_width_twins = (shipped_hold if hold
                                       else (lambda table, unseen: ([], {}, {})))
    structure, instrument = bench._trigger_cold(data)
    if old_floors:
        instrument.profile.u.min = -0.05
        instrument.profile.v.min = -0.5
        instrument.profile.y.min = 0.0
    ref = rx.Refinement(structure, instrument, history=False)
    res = ref.fit(data, plan=plan(axial_first), mode="rietveld", telemetry=False)
    p = ref.instrument.profile
    strain = [round(ph.lor_strain.value, 4) for ph in ref.structure.phases]
    print(f"{label:24s} Rwp {res.statistics.rwp:.5f}  U {p.u.value:+.4f} V {p.v.value:+.4f} "
          f"W {p.w.value:+.4f} X {p.x.value:+.4f} Y {p.y.value:+.4f}  lor_strain {strain}")


truth = bench._trigger_instrument(truth=True).profile
print(f"{'truth':24s} Rwp ~0.0195  U {truth.u.value:+.4f} V {truth.v.value:+.4f} "
      f"W {truth.w.value:+.4f} X {truth.x.value:+.4f} Y {truth.y.value:+.4f}  lor_strain 0")
fit("shipped", hold=True, old_floors=False, axial_first=False)
fit("no hold", hold=False, old_floors=False, axial_first=False)
fit("no hold, 1.9.0 floors", hold=False, old_floors=True, axial_first=False)
fit("axial first", hold=True, old_floors=False, axial_first=True)
refine_module._hold_width_twins = shipped_hold

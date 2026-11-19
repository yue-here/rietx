"""WP-2104 item 1: N single Pawley fits against one joint Pawley fit.

The ramp is ``tests/test_parametric_series.pawley_ramp`` (LaB6, a(T) on a
line, 3-24° at 0.005°, so 4 200 points and 19 reflections a pattern).
Run from the repository root, alone if wall clock is to be quoted:

    PYTHONPATH=. .venv/bin/python docs/wp/2104-measure/pawley_scaling.py 10

At N > 10 only the blocked layout runs: the dense joint Jacobian of 100
patterns would be 7.4 GB.  Peak memory was read with ``/usr/bin/time -l``.
"""
import sys
import time

import rietx as rx
from rietx.multi import refine_multi
from rietx.optimize import blocked
from rietx.params.multi import SharingMap
from rietx.schemas.parametric import CoordinateTable, ParametricEquation
from tests.test_parametric_series import pawley_ramp
from tests.test_sequential import _start_models

n = int(sys.argv[1])
patterns, coords, equation, truth = pawley_ramp(n)
t0 = time.perf_counter()
nfev = 0
for p in patterns:
    s, ins = _start_models()
    r = rx.Refinement(s, ins, history=False).fit(p, mode="pawley", telemetry=False)
    nfev += sum(st.n_iterations for st in r.stages)
t_single = time.perf_counter() - t0
print("singles", n, "wall", round(t_single, 1), "iterations", nfev)
for layout in ("dense", "blocked") if n <= 10 else ("blocked",):
    was = blocked.set_layout(layout)
    s, ins = _start_models()
    t0 = time.perf_counter()
    r = refine_multi(patterns, s, [ins] * n, mode="pawley",
                     sharing=SharingMap(shared=["instrument.zero_shift",
                                                "instrument.profile.*"]),
                     coordinates=coords, parametric=[equation], telemetry=False)
    blocked.set_layout(was)
    print("joint", layout, n, "wall", round(time.perf_counter() - t0, 1),
          "iterations", sum(st.n_iterations for st in r.stages),
          "n_free", r.statistics.n_free_parameters)

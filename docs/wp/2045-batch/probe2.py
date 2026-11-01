"""WP-2045 probe 2: does cpd-1b's warm fit still run away when its windows follow the parameters?

Captures the warm attempt's start models as probe.py does, then refits cpd-1b
from them with the warm stage cut into short stages that each recompile (an
emulation of windows that follow the parameters, at a recompile every K
iterations), closing stage off. K = 400 is one frozen stage that is the last
stage, so it runs at the solver's ftol 1e-9. It is not the shipped warm
stage, which runs at intermediate_ftol 1e-6 before a closing stage
(probe3.py measures that one).
"""
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.strategy.staged import RefinementPlan, Stage  # noqa: E402
from rietx.viz.compare import qpa_plan  # noqa: E402
from tests.test_acceptance_qpa_roundrobin import DATA, SAMPLE1, qarr_instrument, seed_scales  # noqa: E402
from tests.test_acceptance_sequential import _phases  # noqa: E402

refine_mod = sys.modules["rietx.refine"]


class Abort(BaseException):
    pass


calls = []
real_compile = refine_mod.compile_model
capture = {"on": True}


def wrapped(structure, instrument, pattern, **kw):
    if capture["on"]:
        calls.append((structure.model_copy(deep=True), instrument.model_copy(deep=True),
                      pattern, dict(kw)))
        if kw.get("window_area_tol") == 1e-3 and instrument.geometry.axial_sl.value > 1.0:
            raise Abort()
    return real_compile(structure, instrument, pattern, **kw)


refine_mod.compile_model = wrapped

structure = rx.Structure(phases=_phases())
ins = qarr_instrument()
patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
seed_scales(structure, ins, patterns[0])
try:
    rx.SequentialRefinement(structure, ins).fit(patterns, labels=list(SAMPLE1[:2]),
                                                plan=qpa_plan())
    sys.exit("no runaway reached")
except Abort:
    pass
capture["on"] = False
st_s, st_i, data, _ = calls[-2]   # the warm_refit compile's inputs: the stage start
print(f"start axial_sl={st_i.geometry.axial_sl.value:.5g}", flush=True)

globs = list(dict.fromkeys(g for s in qpa_plan().stages for g in s.turn_on))
TOTAL = 400
for k in (400, 50, 10, 3):
    stages = [Stage(f"warm_{i}", globs, max_iter=k, seed=0.0) for i in range(TOTAL // k)]
    plan = RefinementPlan(stages=stages, closing_window_tol=None)
    t = time.perf_counter()
    ref = rx.Refinement(st_s.model_copy(deep=True), st_i.model_copy(deep=True))
    res = ref.fit(data, plan=plan)
    g = ref.instrument.geometry
    sc = [p.scale.value for p in ref.structure.phases]
    # the answer measured on fresh windows at the closing precision
    capture["on"] = False
    from rietx.params.vector import ParameterTable
    fresh = real_compile(ref.structure, ref.instrument, data)
    table = ParameterTable(ref.structure, ref.instrument)
    yc = np.asarray(fresh.evaluate(table.decode(table.x0())), dtype=np.float64)
    r = (fresh.y_obs - yc) / fresh.sigma
    w = fresh.y_obs / fresh.sigma
    rwp_fresh = float(np.sqrt((r @ r) / (w @ w)))
    iters = sum(s.n_iterations for s in res.stages)   # iterations, not evaluations
    print(f"K={k:>3}: {len(stages)} stage(s) {time.perf_counter() - t:6.1f} s  "
          f"Rwp(as fitted)={res.statistics.rwp:.5f}  Rwp(fresh 1e-3)={rwp_fresh:.5f}  "
          f"axial_sl={g.axial_sl.value:.5g}  v={ref.instrument.profile.v.value:.4g}  "
          f"scales={[f'{s:.4g}' for s in sc]}  iters={iters}", flush=True)

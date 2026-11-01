"""WP-2045 probe 5: from the runaway answer, does a re-solve on fresh (declared-precision) windows walk back?"""
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402
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
ans_s, ans_i, data, _ = calls[-1]
print(f"answer axial_sl={ans_i.geometry.axial_sl.value:.5g}", flush=True)
globs = list(dict.fromkeys(g for s in qpa_plan().stages for g in s.turn_on))
for ftol in (1e-6, 1e-9):
    plan = RefinementPlan(stages=[Stage("resolve_fresh", globs, max_iter=100, ftol=ftol,
                                        seed=0.0)], closing_window_tol=None)
    t = time.perf_counter()
    ref = rx.Refinement(ans_s.model_copy(deep=True), ans_i.model_copy(deep=True))
    res = ref.fit(data, plan=plan)
    st = res.stages[-1]
    fresh = real_compile(ref.structure, ref.instrument, data)
    table = ParameterTable(ref.structure, ref.instrument)
    yc = np.asarray(fresh.evaluate(table.decode(table.x0())), dtype=np.float64)
    r = (fresh.y_obs - yc) / fresh.sigma
    w = fresh.y_obs / fresh.sigma
    print(f"re-solve from the answer on fresh windows, ftol={ftol:g}: {time.perf_counter() - t:6.1f} s "
          f"status={st.status} iters={st.n_iterations} Rwp={res.statistics.rwp:.5f} "
          f"Rwp(fresh 1e-3)={float(np.sqrt((r @ r) / (w @ w))):.5f} "
          f"axial_sl={ref.instrument.geometry.axial_sl.value:.5g} "
          f"w={ref.instrument.profile.w.value:.4g}", flush=True)

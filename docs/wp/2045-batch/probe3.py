"""WP-2045 probe 3: which stopping rule leaves cpd-1b's warm stage at the runaway (ftol, max_iter)."""
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
st_s, st_i, data, _ = calls[-2]
print(f"start axial_sl={st_i.geometry.axial_sl.value:.5g}", flush=True)
globs = list(dict.fromkeys(g for s in qpa_plan().stages for g in s.turn_on))

for max_iter, ftol in ((100, 1e-6), (100, 1e-9), (400, 1e-6), (400, 1e-9)):
    plan = RefinementPlan(stages=[Stage("warm_refit", globs, max_iter=max_iter, ftol=ftol,
                                        seed=0.0)], closing_window_tol=None)
    t = time.perf_counter()
    ref = rx.Refinement(st_s.model_copy(deep=True), st_i.model_copy(deep=True))
    res = ref.fit(data, plan=plan)
    st = res.stages[-1]
    fresh = real_compile(ref.structure, ref.instrument, data)
    table = ParameterTable(ref.structure, ref.instrument)
    yc = np.asarray(fresh.evaluate(table.decode(table.x0())), dtype=np.float64)
    r = (fresh.y_obs - yc) / fresh.sigma
    w = fresh.y_obs / fresh.sigma
    print(f"max_iter={max_iter} ftol={ftol:g}: {time.perf_counter() - t:5.1f} s "
          f"status={st.status} iters={st.n_iterations} Rwp(frozen)={res.statistics.rwp:.5f} "
          f"Rwp(fresh 1e-3)={float(np.sqrt((r @ r) / (w @ w))):.5f} "
          f"axial_sl={ref.instrument.geometry.axial_sl.value:.5g}", flush=True)

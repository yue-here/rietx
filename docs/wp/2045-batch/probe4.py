"""WP-2045 probe 4: how much Bragg intensity a stage's frozen windows drop at the stage's answer.

For every declared stage of the cpd-1a fit and cpd-1b's runaway warm stage:
the frozen model (compiled at the stage start) and a fresh compile at the same
precision (at the answer), both evaluated at the answer; the fraction of the
fresh Bragg intensity the frozen one is missing, and the χ² ratio fresh/frozen.
"""
import sys

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402
from rietx.viz.compare import qpa_plan  # noqa: E402
from tests.test_acceptance_qpa_roundrobin import DATA, SAMPLE1, qarr_instrument, seed_scales  # noqa: E402
from tests.test_acceptance_sequential import _phases  # noqa: E402

refine_mod = sys.modules["rietx.refine"]


class Abort(BaseException):
    pass


calls = []
real_compile = refine_mod.compile_model


def wrapped(structure, instrument, pattern, **kw):
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


def values(s, i):
    t = ParameterTable(s, i)
    return t.decode(t.x0())


def chi2(model, v):
    r = (model.y_obs - np.asarray(model.evaluate(v), dtype=np.float64)) / model.sigma
    return float(r @ r)


# consecutive compiles: compile k's inputs are stage k's start, compile k+1's are its answer
for k in range(len(calls) - 1):
    s0, i0, data0, kw0 = calls[k]
    s1, i1, data1, _ = calls[k + 1]
    if data1.intensity[:50] != data0.intensity[:50]:
        continue   # the next compile is the next pattern's: no answer recorded here
    frozen = real_compile(s0, i0, data0, **kw0)
    fresh = real_compile(s1, i1, data0, **kw0)
    v = values(s1, i1)
    yb_frozen = np.asarray(frozen.bragg_component(v, None), dtype=np.float64).sum()
    yb_fresh = np.asarray(fresh.bragg_component(v, None), dtype=np.float64).sum()
    lost = 1.0 - yb_frozen / yb_fresh
    print(f"compile {k + 1:>2} (tol {kw0.get('window_area_tol')}): lost {100 * lost:6.2f} % "
          f"of Bragg intensity at its answer; chi2 fresh/frozen {chi2(fresh, v) / chi2(frozen, v):7.3f}; "
          f"axial_sl {i0.geometry.axial_sl.value:.4g} -> {i1.geometry.axial_sl.value:.4g}", flush=True)

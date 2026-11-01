"""WP-2045 probe: is the runaway answer a minimum of the true model, or only of the frozen one?

Runs the hostile series' first two patterns (cpd-1a -> cpd-1b) as `chained_all`
does, aborts at cpd-1b's first runaway closing compile, then evaluates Rwp at
the runaway answer on (A) the frozen declared-stage model it was solved on,
(B) a fresh compile at the closing precision, (C) a fresh compile at the
declared precision, and (D) the stage-start values on a fresh closing compile.
"""
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])  # the worktree root, for `tests.`

import rietx as rx  # noqa: E402

refine_mod = sys.modules["rietx.refine"]  # `rietx.refine` the attribute is the function
from rietx.params.vector import ParameterTable  # noqa: E402
from rietx.viz.compare import qpa_plan  # noqa: E402
from tests.test_acceptance_qpa_roundrobin import DATA, SAMPLE1, qarr_instrument, seed_scales  # noqa: E402
from tests.test_acceptance_sequential import _phases  # noqa: E402


class Abort(BaseException):
    pass


calls = []
real_compile = refine_mod.compile_model


def work(model):
    total, nmax, wmax = 0, 0, 0
    for ph in model.phases:
        span = np.maximum(ph.win[..., 1] - ph.win[..., 0], 0)
        nodes = np.maximum(ph.fcj_n, 1)
        total += int((span * nodes).sum())
        nmax = max(nmax, int(ph.fcj_n.max(initial=0)))
        wmax = max(wmax, int(span.max(initial=0)))
    return total, nmax, wmax


def wrapped(structure, instrument, pattern, **kw):
    t = time.perf_counter()
    model = real_compile(structure, instrument, pattern, **kw)
    w = work(model)
    rec = dict(structure=structure.model_copy(deep=True),
               instrument=instrument.model_copy(deep=True),
               pattern=pattern, kw=dict(kw), work=w, secs=time.perf_counter() - t)
    calls.append(rec)
    print(f"compile #{len(calls)}: tol={kw.get('window_area_tol')} work={w[0]:,} "
          f"max_nodes={w[1]} max_window_pts={w[2]} "
          f"sl={instrument.geometry.axial_sl.value:.4g}", flush=True)
    # the same abort test as probes 2-5; the recorded run aborted at compile
    # #12 under this test and under the earlier "max FCJ nodes >= 512" alike
    if kw.get("window_area_tol") == 1e-3 and instrument.geometry.axial_sl.value > 1.0:
        raise Abort()
    return model


refine_mod.compile_model = wrapped


def rwp(model, structure, instrument):
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    t = time.perf_counter()
    yc = np.asarray(model.evaluate(values), dtype=np.float64)
    dt = time.perf_counter() - t
    r = (model.y_obs - yc) / model.sigma
    w = model.y_obs / model.sigma
    return float(np.sqrt((r @ r) / (w @ w))), dt


structure = rx.Structure(phases=_phases())
ins = qarr_instrument()
patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
seed_scales(structure, ins, patterns[0])
t0 = time.perf_counter()
try:
    rx.SequentialRefinement(structure, ins).fit(patterns, labels=list(SAMPLE1[:2]),
                                                plan=qpa_plan())
    print("no runaway closing compile reached; nothing to measure")
    sys.exit(0)
except Abort:
    pass
print(f"aborted at the runaway closing compile after {time.perf_counter() - t0:.1f} s")

closing = calls[-1]
declared = calls[-2]   # the warm_refit compile, at the stage-start values
ans_s, ans_i = closing["structure"], closing["instrument"]
st_s, st_i = declared["structure"], declared["instrument"]
data = closing["pattern"]
g = ans_i.geometry
p = ans_i.profile
print(f"answer: axial_sl={g.axial_sl.value:.4g} axial_hl={g.axial_hl.value:.4g} "
      f"u={p.u.value:.4g} v={p.v.value:.4g} w={p.w.value:.4g} x={p.x.value:.4g} y={p.y.value:.4g}")
print(f"start : axial_sl={st_i.geometry.axial_sl.value:.4g}")

frozen = real_compile(st_s, st_i, data, **declared["kw"])
print("A frozen declared model at the answer: Rwp=%.5f (%.2f s)" % rwp(frozen, ans_s, ans_i))
decl_kw = dict(declared["kw"])
fresh_decl = real_compile(ans_s, ans_i, data, **decl_kw)
print("C fresh declared-precision compile at the answer: work=%s Rwp=%.5f (%.2f s)"
      % ((f"{work(fresh_decl)[0]:,}",) + rwp(fresh_decl, ans_s, ans_i)))
fresh_start = real_compile(st_s, st_i, data, **closing["kw"])
print("D fresh closing compile at the start values: work=%s Rwp=%.5f (%.2f s)"
      % ((f"{work(fresh_start)[0]:,}",) + rwp(fresh_start, st_s, st_i)))
print("A' frozen declared model at the start values: Rwp=%.5f (%.2f s)" % rwp(frozen, st_s, st_i))
t = time.perf_counter()
fresh_close = real_compile(ans_s, ans_i, data, **closing["kw"])
print(f"   (closing compile took {time.perf_counter() - t:.1f} s)")
print("B fresh closing compile at the answer: work=%s Rwp=%.5f (%.2f s)"
      % ((f"{work(fresh_close)[0]:,}",) + rwp(fresh_close, ans_s, ans_i)))

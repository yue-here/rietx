"""WP-2047 probe 1: the staleness candidates at every stage's answer, and what each costs.

Wraps ``refine.compile_model`` and pairs consecutive compiles of one pattern as
one stage's start and answer (probe 4 of WP-2045 did the same; a stage that
compiles twice, a released phase, splits its row).  At each answer, against a
fresh compile with the stage's own keywords:

- ``lost``: the fraction of the fresh Bragg intensity the frozen windows drop
- ``chi2``: χ²(fresh)/χ²(frozen)
- ``grew``: reflections whose fresh window is not inside the frozen one, and
  the most points by which one overran (needs equal reflection lists)
- ``t_compile``: the fresh compile's wall seconds, which is the check's cost,
  against ``t_stage``, the stage's own compile-to-next-compile seconds

Families are ``tests.test_window_domain._protocol``'s four, plus ``hostile``:
cpd-1a → cpd-1b as ``chained_all`` runs it, under the pre-WP-2045 tolerance
schedule (every stage but the closing one at ``intermediate_ftol``), aborting
at the runaway closing compile as WP-2045's probes did.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe1.py . [family ...]
"""
import json
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402

refine_mod = sys.modules["rietx.refine"]
real_compile = refine_mod.compile_model
FAMILIES = tuple(sys.argv[2:]) or ("lab6", "fap", "cpd1a", "nac", "hostile")


class Abort(BaseException):
    pass


calls = []


def wrapped(structure, instrument, pattern, **kw):
    if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
            and instrument.geometry.axial_sl.value > 1.0):
        calls.append({"abort": True, "t0": time.perf_counter(),
                      "s": structure.model_copy(deep=True),
                      "i": instrument.model_copy(deep=True), "data": pattern, "kw": dict(kw)})
        raise Abort()
    t0 = time.perf_counter()
    model = real_compile(structure, instrument, pattern, **kw)
    calls.append({"t0": t0, "t1": time.perf_counter(),
                  "s": structure.model_copy(deep=True), "i": instrument.model_copy(deep=True),
                  "data": pattern, "kw": dict(kw)})
    return model


def old_stage_ftols(self):
    """The schedule before WP-2045's option 5: only the endpoints converge."""
    stages = self.run_stages()
    endpoints = {len(stages) - 1}
    if len(stages) == len(self.stages):
        endpoints.add(len(self.stages) - 1)
    return [s.ftol if s.ftol is not None
            else (None if i in endpoints else self.intermediate_ftol)
            for i, s in enumerate(stages)]


def values(s, i):
    t = ParameterTable(s, i)
    return t.decode(t.x0())


def chi2(model, v):
    r = (model.y_obs - np.asarray(model.evaluate(v), dtype=np.float64)) / model.sigma
    return float(r @ r)


def grew(frozen, fresh):
    n_grew, overrun = 0, 0
    for pf, pn in zip(frozen.phases, fresh.phases, strict=True):
        if pf.win.shape != pn.win.shape:
            return None
        lo = pf.win[..., 0] - pn.win[..., 0]
        hi = pn.win[..., 1] - pf.win[..., 1]
        over = np.maximum(lo, hi)
        n_grew += int((over > 0).sum())
        overrun = max(overrun, int(over.max(initial=0)))
    return n_grew, overrun


def fit(family):
    if family == "hostile":
        from rietx.viz.compare import qpa_plan
        from tests.test_acceptance_qpa_roundrobin import DATA, SAMPLE1, qarr_instrument, seed_scales
        from tests.test_acceptance_sequential import _phases
        RefinementPlan.stage_ftols = old_stage_ftols
        structure = rx.Structure(phases=_phases())
        ins = qarr_instrument()
        patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
        seed_scales(structure, ins, patterns[0])
        refine_mod.compile_model = wrapped
        try:
            rx.SequentialRefinement(structure, ins).fit(
                patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan())
        except Abort:
            pass
        return
    from tests import test_window_domain as w
    data, st, ins, plan, kw = w._protocol(family)
    refine_mod.compile_model = wrapped
    rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)


def rows():
    out = []
    for k in range(len(calls) - 1):
        a, b = calls[k], calls[k + 1]
        if a.get("abort") or b["data"] is not a["data"]:
            continue
        t0 = time.perf_counter()
        fresh = real_compile(b["s"], b["i"], a["data"], **a["kw"])
        t_compile = time.perf_counter() - t0
        frozen = real_compile(a["s"], a["i"], a["data"], **a["kw"])
        v = values(b["s"], b["i"])
        yf = np.asarray(frozen.bragg_component(v, None), dtype=np.float64).sum()
        yn = np.asarray(fresh.bragg_component(v, None), dtype=np.float64).sum()
        out.append({
            "k": k + 1,
            "tol": a["kw"].get("window_area_tol"),
            "lost": round(1.0 - yf / yn, 5) if yn > 0 else None,
            "chi2": round(chi2(fresh, v) / chi2(frozen, v), 4),
            "grew": grew(frozen, fresh),
            "t_compile": round(t_compile, 3),
            "t_stage": round(b["t0"] - a["t1"], 3),
            "axial_sl": [round(a["i"].geometry.axial_sl.value, 4),
                         round(b["i"].geometry.axial_sl.value, 4)],
        })
    return out


if __name__ == "__main__":
    family = FAMILIES[0]
    if len(FAMILIES) > 1:
        sys.exit("one family a process: the hostile family patches RefinementPlan")
    t0 = time.perf_counter()
    fit(family)
    refine_mod.compile_model = real_compile
    fit_s = time.perf_counter() - t0
    for r in rows():
        print(family, json.dumps(r), flush=True)
    print(family, "fit seconds", round(fit_s, 1), "compiles", len(calls), flush=True)

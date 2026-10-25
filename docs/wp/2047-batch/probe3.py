"""WP-2047 probe 3: the staleness candidate at every accepted iteration of every stage.

Probe 2 asked this of the hostile warm stage alone.  Here every stage of a
family is asked: at each accepted LM trial, the fraction of the fresh Bragg
intensity the stage's frozen windows drop (``lost``), against a fresh compile
with the stage's own keywords at that iterate.  Each compile owns the ``eval``
events between it and the next compile, read against the most recent
``stage_start``'s ``free_paths`` (a collapse's second solve emits its own).
Per stage: accepted iterations, the largest ``lost`` reached and where, ``lost``
at the solve's last accepted iterate, and the first iteration past each
threshold.  Beside it ``est``: the same fraction estimated off the frozen
model alone (``est_lost``), and its median milliseconds.  Families as probe 1's; ``hostile`` runs the pre-WP-2045 schedule.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe3.py . FAMILY
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
THRESHOLDS = (0.005, 0.01, 0.02, 0.05)


class Abort(BaseException):
    pass


calls = []
events = []


def wrapped(structure, instrument, pattern, **kw):
    if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
            and instrument.geometry.axial_sl.value > 1.0):
        raise Abort()
    calls.append({"s": structure.model_copy(deep=True), "i": instrument.model_copy(deep=True),
                  "data": pattern, "kw": dict(kw), "at": len(events)})
    return real_compile(structure, instrument, pattern, **kw)


def old_stage_ftols(self):
    stages = self.run_stages()
    endpoints = {len(stages) - 1}
    if len(stages) == len(self.stages):
        endpoints.add(len(self.stages) - 1)
    return [s.ftol if s.ftol is not None
            else (None if i in endpoints else self.intermediate_ftol)
            for i, s in enumerate(stages)]


def at(s, i, paths, vals):
    s, i = s.model_copy(deep=True), i.model_copy(deep=True)
    t = ParameterTable(s, i)
    for p, x in zip(paths, vals, strict=True):
        t.entries[t._paths[p]].value = x
    t.refresh_ties()
    t.apply_to_models(s, i)
    return s, i, t.decode(t.x0())


def est_lost(model, v):
    """The same fraction off the frozen model alone: each reflection's
    pseudo-Voigt (Γ, η) integrated between its frozen window's edges,
    intensity-weighted.  No compile; the axial asymmetry is left out."""
    from scipy.special import erf
    tt = np.asarray(model.tt)
    half_step = 0.5 * np.diff(tt).mean()
    num = den = 0.0
    for ip, cp in enumerate(model.phases):
        for il, (pos, g, eta, inten) in enumerate(model.phase_peaks(ip, v, None)):
            pos, g, eta, inten = (np.asarray(x, dtype=np.float64) for x in (pos, g, eta, inten))
            i0, i1 = cp.win[il, :, 0], cp.win[il, :, 1]
            ok = (i1 > i0) & np.isfinite(pos) & (g > 0)
            lo = tt[i0[ok]] - half_step - pos[ok]
            hi = tt[i1[ok] - 1] + half_step - pos[ok]
            gg, ee = g[ok], np.clip(eta[ok], 0.0, 1.0)

            def cdf(x, gg=gg, ee=ee):
                return (ee * np.arctan(2.0 * x / gg) / np.pi
                        + (1.0 - ee) * 0.5 * erf(2.0 * np.sqrt(np.log(2.0)) * x / gg))
            captured = cdf(hi) - cdf(lo)
            num += float((inten[ok] * (1.0 - captured)).sum())
            den += float(inten[ok].sum())
    return num / den if den > 0 else 0.0


def fit(family):
    refine_mod.compile_model = wrapped
    try:
        if family == "hostile":
            from rietx.viz.compare import qpa_plan
            from tests.test_acceptance_qpa_roundrobin import (
                DATA,
                SAMPLE1,
                qarr_instrument,
                seed_scales,
            )
            from tests.test_acceptance_sequential import _phases
            RefinementPlan.stage_ftols = old_stage_ftols
            structure = rx.Structure(phases=_phases())
            ins = qarr_instrument()
            patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
            seed_scales(structure, ins, patterns[0])
            try:
                rx.SequentialRefinement(structure, ins).fit(
                    patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan(),
                    events=events.append)
            except Abort:
                pass
            return
        from tests import test_window_domain as w
        data, st, ins, plan, kw = w._protocol(family)
        refine_mod.compile_model = wrapped
        rx.Refinement(st, ins, history=False).fit(data, plan=plan, events=events.append, **kw)
    finally:
        refine_mod.compile_model = real_compile


def main(family):
    fit(family)
    for c, nxt in zip(calls, [*calls[1:], None], strict=True):
        span = events[c["at"]:(nxt["at"] if nxt else len(events))]
        frozen = real_compile(c["s"], c["i"], c["data"], **c["kw"])
        paths, stage, rows, ests, t_est = None, None, [], [], []
        for e in span:
            d = e["data"]
            if e["kind"] == "stage_start":
                paths, stage = d["free_paths"], d["stage"]
            elif e["kind"] == "eval" and d.get("accepted") and paths is not None:
                s1, i1, v = at(c["s"], c["i"], paths, d["values"])
                fresh = real_compile(s1, i1, c["data"], **c["kw"])
                yf = np.asarray(frozen.bragg_component(v, None), dtype=np.float64).sum()
                yn = np.asarray(fresh.bragg_component(v, None), dtype=np.float64).sum()
                rows.append(1.0 - yf / yn if yn > 0 else 0.0)
                t0 = time.perf_counter()
                ests.append(est_lost(frozen, v))
                t_est.append(time.perf_counter() - t0)
        if not rows:
            continue
        worst = int(np.argmax(rows))
        print(family, json.dumps({
            "stage": stage, "tol": c["kw"].get("window_area_tol"), "iters": len(rows),
            "max_lost": round(rows[worst], 5), "at_iter": worst + 1,
            "end_lost": round(rows[-1], 5),
            "est_at_worst": round(ests[worst], 5), "est_end": round(ests[-1], 5),
            "est_max": round(max(ests), 5),
            "est_ms": round(1e3 * float(np.median(t_est)), 2),
            "first_past": {str(t): next((k + 1 for k, x in enumerate(rows) if x > t), None)
                           for t in THRESHOLDS}}), flush=True)


if __name__ == "__main__":
    main(sys.argv[2])

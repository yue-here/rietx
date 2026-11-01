"""WP-2047 probe 4: two between-solve recompile rules, emulated, on the five families.

Wraps ``refine.run_least_squares`` so a stage's solve becomes several solves,
each on frozen windows, with a fresh compile between them when the windows
have gone stale.  Stale is probe 1's ``lost`` above the compile's own
``window_area_tol`` (``WINDOW_AREA_TOL`` for a declared stage).  Arms:

- ``shipped``: no change.
- ``end``: solve; at the answer, if stale, recompile there and solve again;
  at most ``CAP`` recompiles a solve.
- ``chunkN``: solve ``N`` iterations at a time; after each chunk, recompile if
  stale; stop at a chunk that converged without needing one, or at the
  stage's own ``max_iter`` in total.

The emulation stops at the solver: ``_run_stage`` keeps the model it compiled
for what it measures after the solve (support, guards), so those read the
stale windows, and the next stage's compile is unchanged.  The answer, the
iterations and the time are what this probe is for.

Read-outs per arm: fit seconds, residual evaluations (``n_iterations`` summed
over the solves), recompiles, Rwp, and against ``shipped`` the largest shift
in plain esd (``test_window_domain._shift``).  ``hostile`` reports cpd-1b's
Rwp and ``axial_sl`` instead, under the pre-WP-2045 schedule; ``hostile5``
the same under the shipped schedule.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe4.py . FAMILY ARM
"""
import dataclasses
import json
import signal
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.model.forward import WINDOW_AREA_TOL  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402

refine_mod = sys.modules["rietx.refine"]
real_compile = refine_mod.compile_model
real_lsq = refine_mod.run_least_squares
CAP = 5
LIMIT = 300  # wall seconds a run; a recompile at runaway values can page the machine
compiles = {}
counts = {"recompiles": 0, "solves": 0}


class Abort(BaseException):
    pass


def wrapped_compile(structure, instrument, pattern, **kw):
    if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
            and instrument.geometry.axial_sl.value > 1.0):
        raise Abort(f"closing compile at axial_sl {instrument.geometry.axial_sl.value:.4g}")
    model = real_compile(structure, instrument, pattern, **kw)
    compiles[id(model)] = (structure.model_copy(deep=True), instrument.model_copy(deep=True),
                           pattern, dict(kw))
    return model


def lost_at(model, table, theta):
    """(lost, fresh model) at ``theta``, which the table holds afterwards."""
    s, i, data, kw = compiles[id(model)]
    table.commit(theta)
    s, i = s.model_copy(deep=True), i.model_copy(deep=True)
    table.apply_to_models(s, i)
    fresh = real_compile(s, i, data, **kw)
    if model.mode in ("lebail", "pawley"):
        # the extracted intensities, as _run_stage carries them; without
        # them a Le Bail stage reads its partition as lost intensity
        refine_mod._carry_lebail(model, fresh)
    compiles[id(fresh)] = (s, i, data, kw)
    v = table.decode(table.x0())
    yf = np.asarray(model.bragg_component(v, None), dtype=np.float64).sum()
    yn = np.asarray(fresh.bragg_component(v, None), dtype=np.float64).sum()
    tol = kw.get("window_area_tol") or WINDOW_AREA_TOL
    fresh.origin = model.origin
    return (1.0 - yf / yn if yn > 0 else 0.0), tol, fresh


def merge(first, last, n):
    return dataclasses.replace(last, cost_initial=first.cost_initial, n_iterations=n)


def make_lsq(arm):
    def end(model, table, **kw):
        out = first = real_lsq(model, table, **kw)
        n = out.n_iterations
        counts["solves"] += 1
        for _ in range(CAP):
            lost, tol, fresh = lost_at(model, table, out.theta)
            if lost <= tol:
                break
            counts["recompiles"] += 1
            model = fresh
            out = real_lsq(model, table, **kw)
            counts["solves"] += 1
            n += out.n_iterations
        return merge(first, out, n)

    def chunk(model, table, *, max_iter=100, **kw):
        size = int(arm[len("chunk"):])
        first = out = None
        n = 0
        while n < max_iter:
            out = real_lsq(model, table, max_iter=min(size, max_iter - n), **kw)
            first = first or out
            counts["solves"] += 1
            n += out.n_iterations
            lost, tol, fresh = lost_at(model, table, out.theta)
            if lost > tol:
                counts["recompiles"] += 1
                model = fresh
            elif out.status == "converged":
                break
        return merge(first, out, n)

    return end if arm == "end" else chunk


def old_stage_ftols(self):
    stages = self.run_stages()
    endpoints = {len(stages) - 1}
    if len(stages) == len(self.stages):
        endpoints.add(len(self.stages) - 1)
    return [s.ftol if s.ftol is not None
            else (None if i in endpoints else self.intermediate_ftol)
            for i, s in enumerate(stages)]


def on_alarm(signum, frame):
    raise Abort(f"over {LIMIT} s")


def run(family, arm):
    signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(LIMIT)
    refine_mod.compile_model = wrapped_compile
    if arm != "shipped":
        refine_mod.run_least_squares = make_lsq(arm)
    t0 = time.perf_counter()
    try:
        if family.startswith("hostile"):
            from rietx.viz.compare import qpa_plan
            from tests.test_acceptance_qpa_roundrobin import (
                DATA,
                SAMPLE1,
                qarr_instrument,
                seed_scales,
            )
            from tests.test_acceptance_sequential import _phases
            if family == "hostile":
                RefinementPlan.stage_ftols = old_stage_ftols
            structure = rx.Structure(phases=_phases())
            ins = qarr_instrument()
            patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
            seed_scales(structure, ins, patterns[0])
            series = rx.SequentialRefinement(structure, ins)
            try:
                result = series.fit(patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan())
            except Abort as exc:
                return {"arm": arm, "runaway": str(exc), "seconds": round(time.perf_counter() - t0, 1),
                        **counts}
            res = series.results_[1]
            axial = next(p.value for p in res.parameters
                         if p.path == "instrument.geometry.axial_sl")
            return {"arm": arm, "seconds": round(time.perf_counter() - t0, 1), **counts,
                    "rung": result.entries[1].rung, "rwp_1b": round(res.statistics.rwp, 5),
                    "axial_sl_1b": round(axial, 5),
                    "evals_1b": sum(s.n_iterations for s in res.stages)}
        from tests import test_window_domain as w
        data, st, ins, plan, kw = w._protocol(family)
        try:
            res = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
        except Abort as exc:
            return {"arm": arm, "aborted": str(exc), "seconds": round(time.perf_counter() - t0, 1),
                    **counts}
        return {"arm": arm, "seconds": round(time.perf_counter() - t0, 2), **counts,
                "evals": sum(s.n_iterations for s in res.stages),
                "rwp": round(res.statistics.rwp, 6), "rows": w._rows(res)}
    finally:
        refine_mod.compile_model = real_compile
        refine_mod.run_least_squares = real_lsq


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[2], sys.argv[3])), flush=True)

"""WP-2047 probe 5: ``forward.window_loss`` against a fresh compile, and its cost.

At each stage's answer (consecutive compiles of one pattern, as probe 1
pairs them), two readings of what the stage's frozen model drops:

- ``loss``: ``forward.window_loss``, windows rebuilt on the frozen
  reflection list by ``forward.rewindow``, no compile
- ``lost``: probe 1's, against a fresh compile with the stage's keywords
  (Le Bail intensities carried, as ``_run_stage`` carries them)

with the milliseconds of each.  The frozen model is the one the stage
solved on.  Families as probe 1's; ``hostile`` runs the pre-WP-2045
schedule and stops at the runaway closing compile.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe5.py . FAMILY
"""
import json
import sys
import time

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.model import forward  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402

refine_mod = sys.modules["rietx.refine"]
real_compile = refine_mod.compile_model


class Abort(BaseException):
    pass


calls = []


def wrapped(structure, instrument, pattern, **kw):
    s, i = structure.model_copy(deep=True), instrument.model_copy(deep=True)
    if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
            and instrument.geometry.axial_sl.value > 1.0):
        calls.append({"abort": True, "s": s, "i": i, "data": pattern})
        raise Abort()
    model = real_compile(structure, instrument, pattern, **kw)
    calls.append({"s": s, "i": i, "data": pattern, "kw": dict(kw), "model": model})
    return model


def old_stage_ftols(self):
    stages = self.run_stages()
    endpoints = {len(stages) - 1}
    if len(stages) == len(self.stages):
        endpoints.add(len(self.stages) - 1)
    return [s.ftol if s.ftol is not None
            else (None if i in endpoints else self.intermediate_ftol)
            for i, s in enumerate(stages)]


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
                    patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan())
            except Abort:
                pass
            return
        from tests import test_window_domain as w
        data, st, ins, plan, kw = w._protocol(family)
        rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
    finally:
        refine_mod.compile_model = real_compile


def ms(f):
    t0 = time.perf_counter()
    out = f()
    return out, round(1e3 * (time.perf_counter() - t0), 2)


def main(family):
    fit(family)
    for k in range(len(calls) - 1):
        a, b = calls[k], calls[k + 1]
        if a.get("abort") or b["data"] is not a["data"]:
            continue
        model = a["model"]
        if len(model.phases) != len(b["s"].phases):
            # an internal trial on a cut-down structure (a Le Bail validation)
            # sits between two of the fit's own compiles
            print(family, json.dumps({"k": k + 1, "skipped": "phase count"}), flush=True)
            continue
        t = ParameterTable(b["s"], b["i"])
        v = t.decode(t.x0())
        loss, t_loss = ms(lambda: forward.window_loss(model, v))

        def fresh_lost():
            fresh = real_compile(b["s"], b["i"], a["data"], **a["kw"])
            if model.mode in ("lebail", "pawley"):
                refine_mod._carry_lebail(model, fresh)
            yf = np.asarray(model.bragg_component(v), dtype=np.float64).sum()
            yn = np.asarray(fresh.bragg_component(v), dtype=np.float64).sum()
            return 1.0 - yf / yn
        lost, t_lost = ms(fresh_lost)
        print(family, json.dumps({
            "k": k + 1, "tol": model.window_area_tol, "mode": model.mode,
            "loss": round(loss, 6) if loss is not None else None,
            "lost": round(lost, 6), "ms_loss": t_loss, "ms_compile": t_lost,
            "axial_sl": round(b["i"].geometry.axial_sl.value, 4)}), flush=True)


if __name__ == "__main__":
    main(sys.argv[2])

"""WP-2047 probe 6: the shipped report, ``StageResult.window_loss`` and
``STAGE_WINDOWS_STALE``, in real fits: what each stage records, which fits
raise the code, and what the measurement costs.

For the four protocols, the fit is timed ``N`` times each with the
measurement and with ``refine.window_loss`` stubbed to ``None``, interleaved,
and the medians are compared.  ``hostile`` runs the pre-WP-2045 schedule and
``hostile5`` the shipped one, through the closing stage this time, since
nothing aborts.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe6.py . FAMILY [N]
"""
import json
import statistics
import sys
import time

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402

refine_mod = sys.modules["rietx.refine"]
real_loss = refine_mod.window_loss


def old_stage_ftols(self):
    stages = self.run_stages()
    endpoints = {len(stages) - 1}
    if len(stages) == len(self.stages):
        endpoints.add(len(self.stages) - 1)
    return [s.ftol if s.ftol is not None
            else (None if i in endpoints else self.intermediate_ftol)
            for i, s in enumerate(stages)]


def row(res):
    return {"loss": [None if s.window_loss is None else round(s.window_loss, 5)
                     for s in res.stages],
            "stale": [d.message[:60] for d in res.diagnostics
                      if d.code == "STAGE_WINDOWS_STALE"],
            "rwp": round(res.statistics.rwp, 5)}


def hostile(family):
    from rietx.viz.compare import qpa_plan
    from tests.test_acceptance_qpa_roundrobin import DATA, SAMPLE1, qarr_instrument, seed_scales
    from tests.test_acceptance_sequential import _phases
    if family == "hostile":
        RefinementPlan.stage_ftols = old_stage_ftols
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
    seed_scales(structure, ins, patterns[0])
    series = rx.SequentialRefinement(structure, ins)
    series.fit(patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan())
    for k, res in enumerate(series.results_):
        print(family, json.dumps({"pattern": SAMPLE1[k], **row(res)}), flush=True)


def timed(family, n):
    from tests import test_window_domain as w
    times = {"on": [], "off": []}
    res = None
    for _ in range(n):
        for arm in ("on", "off"):
            refine_mod.window_loss = real_loss if arm == "on" else (lambda m, v: None)
            data, st, ins, plan, kw = w._protocol(family)
            t0 = time.perf_counter()
            out = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
            times[arm].append(time.perf_counter() - t0)
            if arm == "on":
                res = out
    refine_mod.window_loss = real_loss
    on, off = statistics.median(times["on"]), statistics.median(times["off"])
    print(family, json.dumps({**row(res), "s_on": round(on, 3), "s_off": round(off, 3),
                              "ms_added": round(1e3 * (on - off), 1),
                              "ratio": round(on / off, 3)}), flush=True)


if __name__ == "__main__":
    fam = sys.argv[2]
    if fam.startswith("hostile"):
        hostile(fam)
    else:
        timed(fam, int(sys.argv[3]) if len(sys.argv) > 3 else 7)

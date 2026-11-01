"""WP-2047 probe 2: how the staleness candidates grow inside the hostile warm stage.

cpd-1a → cpd-1b under the pre-WP-2045 schedule (probe 1's ``hostile``),
recording every ``eval`` event.  The warm stage is cpd-1b's one declared
stage, and the runaway is its first solve.  At each of that solve's
*accepted* iterations, against the stage's frozen model and a fresh
compile at that iterate: ``lost`` (Bragg intensity the frozen windows drop)
and the χ² ratio fresh/frozen, beside ``axial_sl`` and the frozen χ².  The
first iteration past each threshold says where a test checked between short
solves would have fired.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe2.py .
"""
import json
import sys

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402
from rietx.viz.compare import qpa_plan  # noqa: E402
from tests.test_acceptance_qpa_roundrobin import DATA, SAMPLE1, qarr_instrument, seed_scales  # noqa: E402
from tests.test_acceptance_sequential import _phases  # noqa: E402

refine_mod = sys.modules["rietx.refine"]
real_compile = refine_mod.compile_model
THRESHOLDS = (0.005, 0.01, 0.02, 0.05, 0.1)


class Abort(BaseException):
    pass


calls = []
events = []


def wrapped(structure, instrument, pattern, **kw):
    if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
            and instrument.geometry.axial_sl.value > 1.0):
        raise Abort()
    calls.append((structure.model_copy(deep=True), instrument.model_copy(deep=True),
                  pattern, dict(kw)))
    return real_compile(structure, instrument, pattern, **kw)


def old_stage_ftols(self):
    stages = self.run_stages()
    endpoints = {len(stages) - 1}
    if len(stages) == len(self.stages):
        endpoints.add(len(self.stages) - 1)
    return [s.ftol if s.ftol is not None
            else (None if i in endpoints else self.intermediate_ftol)
            for i, s in enumerate(stages)]


def chi2(model, v):
    r = (model.y_obs - np.asarray(model.evaluate(v), dtype=np.float64)) / model.sigma
    return float(r @ r)


def at(s, i, paths, vals):
    """(structure, instrument, decoded values) with the free paths set to ``vals``."""
    s, i = s.model_copy(deep=True), i.model_copy(deep=True)
    t = ParameterTable(s, i)
    for p, x in zip(paths, vals, strict=True):
        t.entries[t._paths[p]].value = x
    t.refresh_ties()
    t.apply_to_models(s, i)
    return s, i, t.decode(t.x0())


def main():
    RefinementPlan.stage_ftols = old_stage_ftols
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
    seed_scales(structure, ins, patterns[0])
    refine_mod.compile_model = wrapped
    try:
        rx.SequentialRefinement(structure, ins).fit(
            patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan(), events=events.append)
        sys.exit("no runaway reached")
    except Abort:
        pass
    refine_mod.compile_model = real_compile

    s0, i0, data, kw = calls[-1]
    frozen = real_compile(s0, i0, data, **kw)
    # the warm stage's first solve: from cpd-1b's first stage_start to the
    # next one (a collapse re-solves once on the same frozen model, and the
    # runaway is already complete by then)
    starts = [k for k, e in enumerate(events) if e["kind"] == "stage_start"
              and e["data"].get("series_index") == 1]
    first_start = starts[0]
    stop = starts[1] if len(starts) > 1 else len(events)
    paths = events[first_start]["data"]["free_paths"]
    evals = [e["data"] for e in events[first_start:stop] if e["kind"] == "eval"
             and e["data"].get("accepted")]
    print("warm stage", events[first_start]["data"]["stage"], "free", len(paths),
          "accepted iterations", len(evals), "solves", len(starts), flush=True)
    first = {}
    for n, ev in enumerate(evals):
        s1, i1, v = at(s0, i0, paths, ev["values"])
        fresh = real_compile(s1, i1, data, **kw)
        yf = np.asarray(frozen.bragg_component(v, None), dtype=np.float64).sum()
        yn = np.asarray(fresh.bragg_component(v, None), dtype=np.float64).sum()
        lost = 1.0 - yf / yn
        c_frozen = chi2(frozen, v)
        row = {"iter": n + 1, "n_eval": ev["n_eval"],
               "axial_sl": round(v["instrument.geometry.axial_sl"], 4),
               "lost": round(lost, 5), "chi2_ratio": round(chi2(fresh, v) / c_frozen, 4),
               "chi2_frozen": round(c_frozen, 1)}
        print(json.dumps(row), flush=True)
        for t in THRESHOLDS:
            if lost > t and t not in first:
                first[t] = row
    print("first past", json.dumps({str(t): r["iter"] for t, r in first.items()}))


if __name__ == "__main__":
    main()

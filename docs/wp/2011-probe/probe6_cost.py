"""Task 4's cost half: seconds per validation fit, both modes, inside ``index_pattern``.

``MEASURED_VALIDATION_SECONDS`` was measured by running the indexer on the
known-cell corpus and timing its validation fits (WP-1037 task 0).  This runs
the same searches once per dataset with the acceptance suite's specs and wraps
``workflow.validate_by_lebail`` so every candidate the indexer validates is
validated twice, once per mode, order alternating per call.  The pipeline
carries on with the Le Bail verdict, so the candidates checked are the shipped
ones.  The search is mode-independent and runs once.

Run from the worktree root:  .venv/bin/python docs/wp/2011-probe/probe6_cost.py [name ...]
Rows go to $WP2011_OUT/rows6.json; one JSON line per validation on stdout.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe5_after_941 import fit_mode  # noqa: E402
from probe_lebail_vs_pawley import OUT  # noqa: E402

import rietx.indexing.workflow as wf  # noqa: E402

_VALIDATE = wf.validate_by_lebail
ROWS: list[dict] = []
_CALLS = [0]


def timed(cand, data, ins, **kw):
    case = timed.case
    order = ("lebail", "pawley") if _CALLS[0] % 2 == 0 else ("pawley", "lebail")
    _CALLS[0] += 1
    got = {}
    for mode in order:
        with fit_mode(mode):
            t0 = time.perf_counter()
            v = _VALIDATE(cand, data, ins, **kw)
            got[mode] = (time.perf_counter() - t0, v)
    rec = dict(case=case, system=cand.system, centring=cand.centring,
               volume=round(cand.volume, 2), n_refl=got["lebail"][1].n_reflections,
               **{f"secs_{m}": round(s, 3) for m, (s, _) in got.items()},
               **{f"rwp_{m}": round(v.rwp, 4) for m, (_, v) in got.items()},
               **{f"unmatched_{m}": v.unmatched_observed for m, (_, v) in got.items()},
               **{f"status_{m}": v.status for m, (_, v) in got.items()})
    ROWS.append(rec)
    print(json.dumps(rec), flush=True)
    return got["lebail"][1]


def main(names):
    from tests.test_acceptance_fap import build_fap_inputs
    from tests.test_acceptance_indexing import (
        REAL_DATA_BUDGET_SECONDS,
        REAL_DATA_N_UNINDEXED,
        REAL_DATA_SYSTEMS,
        _qarr,
    )
    from tests.test_acceptance_nac import build_nac_inputs
    from tests.test_acceptance_srm660c import build_srm_inputs
    from rietx.indexing.engines import SearchSpec
    from rietx.indexing.pick import pick_peaks

    def spec(systems, vmax):
        return SearchSpec(systems=systems, max_volume=vmax,
                          budget_seconds=REAL_DATA_BUDGET_SECONDS,
                          n_unindexed=REAL_DATA_N_UNINDEXED)

    sets = {
        "corundum": (lambda: _qarr("corundum.prn"), spec(REAL_DATA_SYSTEMS, 600.0), True),
        "cpd1a": (lambda: _qarr("cpd-1a.prn"), spec(REAL_DATA_SYSTEMS, 600.0), False),
        "zincite": (lambda: _qarr("zincite.prn"), spec(("hexagonal",), 700.0), True),
        "zircon": (lambda: _qarr("zircon.prn"), spec(("tetragonal",), 700.0), True),
        "fap": (lambda: build_fap_inputs()[::2], spec(("hexagonal", "trigonal"), 600.0), True),
        "lab6": (lambda: build_srm_inputs()[::2], spec(REAL_DATA_SYSTEMS, 300.0), True),
        "magnetite": (lambda: _qarr("magnetit.prn"), spec(("cubic",), 700.0), True),
        "nac": (lambda: build_nac_inputs()[::2], spec(("cubic",), 1200.0), True),
    }
    wf.validate_by_lebail = timed
    try:
        for name in names or list(sets):
            load, sp, pick = sets[name]
            data, ins = load()
            timed.case = name
            t0 = time.perf_counter()
            if pick:
                res = wf.index_pattern(pick_peaks(data, ins), data=data, instrument=ins,
                                       spec=sp, preset="full")
            else:
                res = wf.index_pattern(data=data, instrument=ins, spec=sp, preset="full")
            top = res.candidates[0] if res.candidates else None
            print(json.dumps(dict(case=name, run_seconds=round(time.perf_counter() - t0, 1),
                                  n_candidates=len(res.candidates),
                                  top=None if top is None else
                                  [top.system, top.centring, round(top.volume, 2), top.confidence])),
                  flush=True)
    finally:
        wf.validate_by_lebail = _VALIDATE
    (OUT / "rows6.json").write_text(json.dumps(ROWS, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])

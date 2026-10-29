"""What clock does ``quick`` leave validation, and what does each checked fit cost?

Option (f) reorders or reshares the validation reserve.  Whether any schedule
can validate a candidate depends on two numbers this records per case: the
clock left when the first validation fit starts, and each checked
candidate's *unbudgeted* fit cost, in the order the loop visits them.  With
both, every schedule can be simulated offline (probe 17) before one is built.

One quick run per case records the entry clock (``validate_by_lebail`` is
wrapped, its budgeted outcome kept); then every checked candidate is refitted
with no cancel token and timed.  Run alone: the run is wall-clock bound.

    .venv/bin/python docs/wp/2011-probe/probe16_schedule.py nac_default ...
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe8_quick import sets  # noqa: E402

import rietx.indexing.engines as eng  # noqa: E402
import rietx.indexing.workflow as wf  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.optimize.cancel import RefinementCancelled  # noqa: E402


def run(name, load, spec, mode):
    data, ins = load()
    peaks = pick_peaks(data, ins)
    wf.VALIDATION_MODE = mode
    real = wf.validate_by_lebail
    calls = []

    def wrapped(cand, *a, **kw):
        t = time.perf_counter()
        rec = dict(entry=round(t - t0, 2), cand=cand, kw=kw, a=a)
        calls.append(rec)
        try:
            out = real(cand, *a, **kw)
            rec["budgeted"] = round(time.perf_counter() - t, 2)
            rec["status"] = out.status
            return out
        except RefinementCancelled:
            rec["budgeted"] = round(time.perf_counter() - t, 2)
            rec["status"] = "cancelled"
            raise

    wf.validate_by_lebail = wrapped
    t0 = time.perf_counter()
    try:
        res = wf.index_pattern(peaks, data=data, instrument=ins, spec=spec)
    finally:
        wf.validate_by_lebail = real
    total = time.perf_counter() - t0
    rows = []
    for k, rec in enumerate(calls):
        cand = rec["cand"]
        kw = dict(rec["kw"], cancel=None)
        t = time.perf_counter()
        out = real(cand, *rec["a"], **kw)
        cost = time.perf_counter() - t
        rank = next(i for i, c in enumerate(res.candidates) if c is cand)
        rows.append(dict(
            visit=k, rank=rank, system=cand.system, centring=cand.centring,
            volume=round(cand.volume, 2), entry=rec["entry"],
            budgeted=rec["budgeted"], quick_status=rec["status"],
            cost=round(cost, 2), status=out.status, rwp=round(out.rwp, 4),
            unmatched=out.unmatched_observed,
            n_refl=getattr(out, "n_reflections", None)))
    return dict(case=name, mode=mode,
                reserve=eng.VALIDATION_RESERVE_FRACTION, total=round(total, 1),
                first_entry=calls[0]["entry"] if calls else None,
                n_candidates=len(res.candidates),
                searched=list(res.systems_searched),
                incomplete=sorted(k for k, v in res.search_complete.items() if not v),
                top=[[c.system, c.centring, round(c.volume, 2)]
                     for c in res.candidates[:6]],
                fits=rows)


def main(argv):
    if os.environ.get("RESERVE"):
        # the reserve is read at call time from engines, so this reaches it
        eng.VALIDATION_RESERVE_FRACTION = float(os.environ["RESERVE"])
    mode = "pawley"
    if argv and argv[0].startswith("--mode="):
        mode = argv.pop(0).split("=", 1)[1]
    table = sets()
    for name in argv:
        load, spec = table[name]
        print(json.dumps(run(name, load, spec, mode)), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])

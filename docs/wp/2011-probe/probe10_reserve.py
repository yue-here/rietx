"""What would it take for ``quick`` to validate NAC's shortlist under Pawley?

Probe 8 found Pawley validating none of 11-BM NAC's checked candidates under
``quick`` with every system searched, where Le Bail validated one to three.
The search stops ``VALIDATION_RESERVE_FRACTION`` (8 %, 9.6 s) before the
ceiling, a reserve sized for three 1.9 s Le Bail fits.

``cost``: the candidates ``index_pattern`` checks on NAC (default spec, quick,
captured from a Le Bail run), each validated with no deadline in both modes,
order alternating.  ``reserve``: ``index_pattern`` under ``quick`` with the
reserve at 0.08, 0.2, 0.3 and 0.4, Pawley, on the cases that hit the ceiling
in probe 8 -- what the validation gains and what the search loses.

Run from the worktree root:
    .venv/bin/python docs/wp/2011-probe/probe10_reserve.py cost|reserve [case ...]
Rows go to $WP2011_OUT/rows10_<which>.json; one JSON line per run on stdout.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe8_quick import OUT, sets  # noqa: E402

import rietx.indexing.engines as eng  # noqa: E402
import rietx.indexing.workflow as wf  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402

_VALIDATE = wf.validate_by_lebail


def checked_candidates(data, ins, peaks, spec):
    """The candidates a ``preset="full"`` search validates, under Le Bail."""
    seen = []

    def capture(cand, *a, **kw):
        seen.append(cand.model_copy(deep=True))
        return _VALIDATE(cand, *a, **kw)

    mode = wf.VALIDATION_MODE
    wf.VALIDATION_MODE = "lebail"
    wf.validate_by_lebail = capture
    try:
        # full: no slice, so every checked candidate reaches the capture
        wf.index_pattern(peaks, data=data, instrument=ins, spec=spec, preset="full")
    finally:
        wf.validate_by_lebail = _VALIDATE
        wf.VALIDATION_MODE = mode
    return seen


def cost(rows, names):
    for name in names or ["nac_default", "nac_all"]:
        load, spec = sets()[name]
        data, ins = load()
        peaks = pick_peaks(data, ins)
        seen = checked_candidates(data, ins, peaks, spec)
        for k, cand in enumerate(seen):
            order = ("lebail", "pawley") if k % 2 == 0 else ("pawley", "lebail")
            for mode in order:
                wf.VALIDATION_MODE = mode
                t0 = time.perf_counter()
                v = _VALIDATE(cand, data, ins, peaks=peaks)
                rec = dict(case=name, mode=mode, system=cand.system,
                           centring=cand.centring, volume=round(cand.volume, 2),
                           n_refl=v.n_reflections, secs=round(time.perf_counter() - t0, 2),
                           load=round(os.getloadavg()[0], 1), status=v.status,
                           rwp=round(v.rwp, 4), unmatched=v.unmatched_observed)
                rows.append(rec)
                print(json.dumps(rec), flush=True)


def reserve(rows, names):
    table = sets()
    wf.VALIDATION_MODE = "pawley"
    shipped = eng.VALIDATION_RESERVE_FRACTION
    try:
        for name in names or ["nac_default", "nac_all", "corundum", "fap_default",
                              "zircon_default"]:
            _reserve_case(rows, name, *table[name])
    finally:
        eng.VALIDATION_RESERVE_FRACTION = shipped


def _reserve_case(rows, name, load, spec):
    data, ins = load()
    peaks = pick_peaks(data, ins)
    for frac in (0.08, 0.2, 0.3, 0.4):
        eng.VALIDATION_RESERVE_FRACTION = frac
        t0 = time.perf_counter()
        res = wf.index_pattern(peaks, data=data, instrument=ins, spec=spec)
        cands = res.candidates
        rec = dict(case=name, reserve=frac, seconds=round(time.perf_counter() - t0, 1),
                   load=round(os.getloadavg()[0], 1),
                   n_candidates=len(cands),
                   n_validated=sum(c.lebail is not None for c in cands),
                   systems_searched=list(res.systems_searched),
                   incomplete=[s for s, ok in res.search_complete.items() if not ok],
                   top=[[c.system, c.centring, round(c.volume, 2), c.confidence,
                         None if c.lebail is None else c.lebail.status,
                         None if c.lebail is None else round(c.lebail.rwp, 4)]
                        for c in cands[:6]])
        rows.append(rec)
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    which = sys.argv[1]
    rows: list[dict] = []
    {"cost": cost, "reserve": reserve}[which](rows, sys.argv[2:])
    (OUT / f"rows10_{which}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

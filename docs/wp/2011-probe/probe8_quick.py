"""The ``quick`` risk: does a Pawley validation leave candidates unvalidated?

Under ``preset="quick"`` (``index_pattern``'s default) each validation fit
draws a slice of a whole-run ceiling, and a slice that runs out leaves its
candidate ``lebail = None`` (``not_validated``, capping the grade at
``medium``).  Pawley costs 3-5x Le Bail on 11-BM NAC, so this runs the
indexer as a user's first click would, once per mode, and counts what each
left unvalidated or failed.  Only ``workflow.VALIDATION_MODE`` differs: the
extinction screen's own Le Bail fits are untouched (probe 5's ``fit_mode``
would have swapped them too).

Specs: ``default`` is ``SearchSpec()`` with nothing declared (every system);
``acceptance`` is the indexing acceptance suite's spec for that dataset, with
the per-unit budget left at its default, since ``quick`` sets the clock.

Run from the worktree root:
    .venv/bin/python docs/wp/2011-probe/probe8_quick.py [name ...]
Rows go to $WP2011_OUT/rows8.json; one JSON line per run on stdout.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe_lebail_vs_pawley import OUT  # noqa: E402  (creates the directory)

import rietx.indexing.workflow as wf  # noqa: E402
from rietx.indexing.engines import SearchSpec  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402


def sets():
    from tests.test_acceptance_fap import build_fap_inputs
    from tests.test_acceptance_indexing import REAL_DATA_N_UNINDEXED, REAL_DATA_SYSTEMS, _qarr
    from tests.test_acceptance_nac import build_nac_inputs
    from tests.test_acceptance_srm660c import build_srm_inputs

    def acc(systems, vmax):
        return SearchSpec(systems=systems, max_volume=vmax,
                          n_unindexed=REAL_DATA_N_UNINDEXED)

    all7 = ("cubic", "hexagonal", "trigonal", "tetragonal", "orthorhombic",
            "monoclinic", "triclinic")
    return {
        "nac": (lambda: build_nac_inputs()[::2], acc(("cubic",), 1200.0)),
        "nac_all": (lambda: build_nac_inputs()[::2], acc(all7, 1200.0)),
        "nac_default": (lambda: build_nac_inputs()[::2], SearchSpec()),
        "fap": (lambda: build_fap_inputs()[::2], acc(("hexagonal", "trigonal"), 600.0)),
        "fap_default": (lambda: build_fap_inputs()[::2], SearchSpec()),
        "lab6": (lambda: build_srm_inputs()[::2], acc(REAL_DATA_SYSTEMS, 300.0)),
        "corundum": (lambda: _qarr("corundum.prn"), acc(REAL_DATA_SYSTEMS, 600.0)),
        "zincite": (lambda: _qarr("zincite.prn"), acc(("hexagonal",), 700.0)),
        "zircon": (lambda: _qarr("zircon.prn"), acc(("tetragonal",), 700.0)),
        "zircon_default": (lambda: _qarr("zircon.prn"), SearchSpec()),
        "magnetite": (lambda: _qarr("magnetit.prn"), acc(("cubic",), 700.0)),
    }


def run(name, load, spec, mode):
    data, ins = load()
    peaks = pick_peaks(data, ins)
    wf.VALIDATION_MODE = mode
    t0 = time.perf_counter()
    res = wf.index_pattern(peaks, data=data, instrument=ins, spec=spec)
    secs = time.perf_counter() - t0
    cands = res.candidates
    validated = [c for c in cands if c.lebail is not None]
    codes = sorted({d.code for d in res.diagnostics})
    budget = [d.message for d in res.diagnostics if d.code == "INDEX_BUDGET_EXHAUSTED"]
    return dict(
        case=name, mode=mode, preset=res.preset, seconds=round(secs, 1),
        load=round(os.getloadavg()[0], 1),
        n_candidates=len(cands), n_validated=len(validated),
        statuses=[c.lebail.status for c in validated],
        modes=sorted({c.lebail.mode for c in validated}),
        not_validated_in_budget_msg=budget,
        top=[[c.system, c.centring, round(c.volume, 2), c.confidence,
              None if c.lebail is None else c.lebail.status,
              None if c.lebail is None else round(c.lebail.rwp, 4),
              None if c.lebail is None else c.lebail.unmatched_observed]
             for c in cands[:6]],
        codes=codes)


def main(names):
    table = sets()
    rows = []
    for k, name in enumerate(names or list(table)):
        load, spec = table[name]
        order = ("lebail", "pawley") if k % 2 == 0 else ("pawley", "lebail")
        for mode in order:
            rec = run(name, load, spec, mode)
            rows.append(rec)
            print(json.dumps(rec), flush=True)
    (OUT / "rows8.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])

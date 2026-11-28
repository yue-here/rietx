"""WP-2311: is the dependence on the units, or on the start state?

``lab6_data``'s instrument declares the f = 1 background in counts, Chebyshev
(30, -4, 1).  Probe 1 scaled the data and left that declaration alone, so the
fit at f started from a background 1/f times too high for the data.  Two
variants separate the causes:

- ``units``: intensity, σ *and* the declared background coefficients scaled
  by f, so the start state is the f = 1 start in the new units.  Invariance
  should be exact up to the solver's tolerances.
- ``start``: f = 1 data, declared background multiplied by 1/f, so only the
  start state moves.

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe2_start_vs_units.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from probe1_rerun import lab6_data, scaled, stage_row, widths  # noqa: E402

from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from tests.test_indexing_consensus import TRUE_A, _candidate, _instrument  # noqa: E402


def with_bkg(ins, g):
    out = ins.model_copy(deep=True)
    for c in out.background.coefficients:
        c.value *= g
    return out


def main():
    data = lab6_data(11)
    ins = _instrument()
    peaks = pick_peaks(data, ins)
    cand = _candidate(TRUE_A)
    cases = [("units", f, scaled(data, f), with_bkg(ins, f))
             for f in (1.0, 0.1, 0.01, 1e-3, 1e-4)]
    cases += [("start", f, data, with_bkg(ins, 1.0 / f)) for f in (0.1, 0.01)]
    for name, f, d, i in cases:
        v, res = validate_by_lebail(cand, d, i, peaks=peaks, with_result=True)
        rec = dict(case=name, f=f, rwp=round(v.rwp, 6), status=v.status,
                   params={k: float(f"{x:.6g}") for k, x in widths(res).items()},
                   stages=[stage_row(s) for s in res.stages])
        print(json.dumps(rec, default=str), flush=True)


if __name__ == "__main__":
    main()

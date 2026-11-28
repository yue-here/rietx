"""WP-2311 task 1: rerun WP-2011 probe 9's ``scaled`` reading on the current tree.

Synthetic LaB6 (``probe2_lebail_vs_pawley.lab6_data(11)``), its true cell, the
shipped ``validate_by_lebail`` (Pawley).  For each factor f the intensity and
σ are both multiplied by f, so χ² is the same function of every parameter but
the Pawley intensities, which should come back in ratio f.

Two peak-list variants, so the picker's response to the units is separable from
the fit's: ``base`` hands every f the f = 1 list; ``repick`` re-picks the scaled
pattern, as probe 9 did and as a user's run would.

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe1_rerun.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parents[1] / "2011-probe"))

from probe2_lebail_vs_pawley import lab6_data  # noqa: E402

from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from tests.test_indexing_consensus import TRUE_A, _candidate, _instrument  # noqa: E402

FACTORS = tuple(float(x) for x in sys.argv[1:]) or (1.0, 0.1, 0.01, 1e-3, 1e-4)


def scaled(data, f):
    y = np.asarray(data.intensity, dtype=np.float64)
    return data.model_copy(update={"intensity": (y * f).tolist(),
                                   "sigma": (np.asarray(data.sig()) * f).tolist()})


def widths(result):
    return {p.path.split(".")[-1]: p.value for p in result.parameters
            if p.path.startswith("instrument.")}


def stage_row(s):
    return {k: getattr(s, k) for k in ("name", "status", "n_iterations", "cost_initial", "cost_final")
            if hasattr(s, k)}


def main():
    data = lab6_data(11)
    ins = _instrument()
    base_peaks = pick_peaks(data, ins)
    cand = _candidate(TRUE_A)
    for f in FACTORS:
        d = scaled(data, f)
        for variant in ("base", "repick"):
            pk = base_peaks if variant == "base" else pick_peaks(d, ins)
            t0 = time.perf_counter()
            v, res = validate_by_lebail(cand, d, ins, peaks=pk, with_result=True)
            rec = dict(f=f, peaks=variant, n_peaks=len(pk.peaks),
                       secs=round(time.perf_counter() - t0, 2),
                       rwp=round(v.rwp, 5), status=v.status, unmatched=v.unmatched_observed)
            if res is not None:
                rec["params"] = {k: float(f"{x:.5g}") for k, x in widths(res).items()}
                rec["stages"] = [stage_row(s) for s in res.stages]
            print(json.dumps(rec, default=str), flush=True)


if __name__ == "__main__":
    main()

"""Do the cheaper Pawley solves change a validation's verdict?  Probe 5's cells.

Each case runs the shipped ``validate_by_lebail`` (Pawley, peak-list path,
widths free) once per solver variant, set through module switches the probe
snapshot carries (``lm.SPARSE_NORMAL``, ``least_squares.MERGE_PAWLEY``,
``least_squares.NO_COV``).  A row records the readings a candidate is judged
on (unmatched, absent, status, Rwp), the seconds, and the widest system the
LM driver solved (``n_cols``), so a merge's reduction is visible.

    python probe13_variants.py truths|lab6|magnetite
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import probe5_after_941 as p5  # noqa: E402
from probe_lebail_vs_pawley import OUT  # noqa: E402

import rietx.optimize.least_squares as L  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from rietx.optimize import bccg, lm  # noqa: E402

N_COLS: list[int] = []
_MIN = lm.minimize


def _minimize(residual, jacobian, x0, *a, **k):
    N_COLS.append(len(x0))
    return _MIN(residual, jacobian, x0, *a, **k)


lm.minimize = _minimize

VARIANTS = [("pcg_cached", {(lm, "SPARSE_NORMAL"): True, (lm, "SPARSE_CACHE"): True, (bccg, "PRECONDITION"): True}),
            ("lu_cached", {(lm, "SPARSE_NORMAL"): True, (lm, "SPARSE_CACHE"): True, (bccg, "PRECONDITION"): True, (bccg, "EXACT_LU"): True})]
_UNUSED = [("merge", {(L, "MERGE_PAWLEY"): True}),
            ("sparse", {(lm, "SPARSE_NORMAL"): True}),
            ("nocov", {(L, "NO_COV"): True})]


def run(rows, case, cand, data, ins, peaks, **_):
    for name, flags in VARIANTS:
        for (mod, key), value in flags.items():
            setattr(mod, key, value)
        N_COLS.clear()
        try:
            t0 = time.perf_counter()
            v, result = validate_by_lebail(cand, data, ins, peaks=peaks, with_result=True)
            secs = time.perf_counter() - t0
        finally:
            for (mod, key) in flags:
                setattr(mod, key, False)
        rec = dict(case=case, variant=name, secs=round(secs, 2), n_refl=v.n_reflections,
                   n_cols=max(N_COLS) if N_COLS else None, rwp=round(v.rwp, 4),
                   status=v.status, unmatched=v.unmatched_observed,
                   absent=v.predicted_but_absent,
                   iters=[s.n_iterations for s in result.stages] if result else None)
        rows.append(rec)
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    which = sys.argv[1]
    p5.run = run
    rows: list[dict] = []
    {"truths": p5.truths, "lab6": p5.lab6, "magnetite": p5.magnetite}[which](rows)
    (OUT / f"rows13_{which}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

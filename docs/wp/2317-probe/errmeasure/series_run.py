"""cpd-1 series (tests/test_acceptance_sequential.py's chained fixture) under a
last-stage stop, one JSON per (stop, seed).  Calls ../convnoise/series.py's run().

usage: python series_run.py NWORKERS STOP[,STOP...] SEEDS(e.g. none,0,1,...)
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("RIETX_COMPILED_THREADS", "2")
HERE = Path(__file__).resolve().parent
CONV = HERE.parent / "convnoise"
ROOT = HERE.parents[3]
OUT = HERE / "results"


def job(stop, seed):
    for p in (str(CONV), str(ROOT), str(ROOT / "tests")):
        if p not in sys.path:
            sys.path.insert(0, p)
    out = OUT / f"series_cpd1__{stop}__{seed}.json"
    if out.exists():
        return f"skip {out.name}"
    real_stop = stop
    if stop == "numpy":
        # the shipped settings on the numpy tier instead of the compiled kernels:
        # the same model, arithmetic differing at a rounding bound (a change whose
        # true effect on every answer is zero to ~1e-13 relative)
        os.environ["RIETX_COMPILED"] = "0"
        real_stop = "ftol1e-9"
    import series
    rec = series.run("cpd1", real_stop, None if seed == "none" else int(seed))
    rec["stop"] = stop
    out.write_text(json.dumps(rec))
    return f"done {out.name} wall={rec['wall_s']} nfev={rec['nfev_total']}"


def main():
    n = int(sys.argv[1])
    stops_ = sys.argv[2].split(",")
    seeds = sys.argv[3].split(",")
    with cf.ProcessPoolExecutor(max_workers=n, max_tasks_per_child=1) as ex:
        futs = {ex.submit(job, s, k): (s, k) for s in stops_ for k in seeds}
        for f in cf.as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception:
                print("FAIL", futs[f], traceback.format_exc(), flush=True)


if __name__ == "__main__":
    main()

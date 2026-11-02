"""What does the scoring after the search's stop cost, counted rather than clocked?

WP-2011 measured it on a quiet machine as a wall-clock overrun (probes 19-21):
consensus's ``rank_candidates`` over NAC's whole merge, 4.9 s for 80 panels,
and a trial_error unit's own ranking, 3.6 s for 24.  A loaded machine cannot
repeat that clock, so this splits it into a count and a unit cost.

``capture`` runs one ``quick`` index of 11-BM NAC (default ``SearchSpec()``)
and pickles every ``rank_candidates`` call's arguments, tagged by caller.
``replay`` re-runs each call five times and prints the minimum of the
calling thread's CPU time (``time.thread_time``, which waiting for a core
does not inflate) and a digest of the ranked answer.  Replay the same pickle
under two trees (``PYTHONPATH=<tree>/src``) to compare them.

    python probe1_panel_replay.py capture OUT.pkl
    python probe1_panel_replay.py replay OUT.pkl
"""
from __future__ import annotations

import hashlib
import importlib
import pickle
import sys
import time
from pathlib import Path

import numpy as np

CALLERS = ("consensus", "dichotomy", "svd", "trial_error")


def capture(out: Path) -> None:
    sys.path.insert(0, str(Path.cwd()))
    import rietx.indexing.workflow as wf
    from rietx.indexing.engines import SearchSpec
    from rietx.indexing.pick import pick_peaks
    from tests.test_acceptance_nac import build_nac_inputs

    calls = []
    for name in CALLERS:
        mod = importlib.import_module(f"rietx.indexing.{name}")
        real = mod.rank_candidates

        def wrapped(*a, _real=real, _name=name, **kw):
            kw.pop("cancel", None)
            # pickled at the call: the ranking fills each candidate's panel
            calls.append(pickle.dumps(dict(caller=_name, args=a, kwargs=kw)))
            return _real(*a, **kw)
        mod.rank_candidates = wrapped
    data, _structure, ins = build_nac_inputs()
    peaks = pick_peaks(data, ins)
    t0 = time.perf_counter()
    res = wf.index_pattern(peaks, data=data, instrument=ins, spec=SearchSpec())
    print(f"quick run: {time.perf_counter() - t0:.1f} s wall, "
          f"searched {list(res.systems_searched)}", flush=True)
    out.write_bytes(pickle.dumps(calls))
    print(f"{len(calls)} calls captured to {out}")


def _digest(ranked) -> str:
    h = hashlib.sha256()
    for c in ranked:
        h.update(np.asarray(c.fit.af, dtype=np.float64).tobytes())
        for m in (c.fom or []):
            h.update(f"{m.name}:{m.value!r}".encode())
    return h.hexdigest()[:12]


def replay(path: Path) -> None:
    import rietx.indexing.engines as eng

    totals: dict[str, float] = {}
    for k, raw in enumerate(pickle.loads(path.read_bytes())):
        best, out = np.inf, None
        for _ in range(5):
            call = pickle.loads(raw)            # fresh, unscored candidates
            t = time.thread_time()
            out = eng.rank_candidates(*call["args"], **call["kwargs"])
            best = min(best, time.thread_time() - t)
        n = len(call["args"][0])
        totals[call["caller"]] = totals.get(call["caller"], 0.0) + best
        print(f"{k:3d} {call['caller']:12s} panels_in={n:4d} "
              f"cpu_min={best:7.3f} s digest={_digest(out)}", flush=True)
    for name, t in totals.items():
        print(f"total {name}: {t:.2f} s")


if __name__ == "__main__":
    verb, target = sys.argv[1], Path(sys.argv[2])
    {"capture": capture, "replay": replay}[verb](target)

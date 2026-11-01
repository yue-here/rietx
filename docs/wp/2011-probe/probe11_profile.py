"""Where a Pawley validation of NAC's 2224-reflection candidate spends 379 s.

Probe 10 timed the candidates ``index_pattern`` checks on 11-BM NAC
(default spec): Pawley 11 s at 1223-1241 reflections and 379 s at 2224,
against Le Bail's 1.4-2.4 s.  This captures those candidates again (a
``preset="full"`` search, Le Bail validation, cached to
``$WP2011_OUT/nac_checked.json``), then validates the largest under
``cProfile`` in Pawley mode and prints the top of the cumulative table, with
the per-stage iteration counts.

Run from the worktree root:  .venv/bin/python docs/wp/2011-probe/probe11_profile.py
"""
from __future__ import annotations

import cProfile
import io
import json
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe8_quick import OUT, sets  # noqa: E402
from probe10_reserve import checked_candidates  # noqa: E402

import rietx.indexing.workflow as wf  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.schemas.indexing import CellCandidate  # noqa: E402

_VALIDATE = wf.validate_by_lebail


def main():
    load, spec = sets()["nac_default"]
    data, ins = load()
    peaks = pick_peaks(data, ins)
    cached = OUT / "nac_checked.json"
    if not cached.exists():
        seen = checked_candidates(data, ins, peaks, spec)
        cached.write_text(json.dumps([c.model_dump(mode="json") for c in seen]),
                          encoding="utf-8")
    cands = [CellCandidate.model_validate(c)
             for c in json.loads(cached.read_text(encoding="utf-8"))]
    # the monoclinic subcell: the 2224-reflection one (orthorhombic ties its volume)
    big = next(c for c in cands if c.system == "monoclinic")
    print("candidate", big.system, big.centring, big.cell, flush=True)
    wf.VALIDATION_MODE = "pawley"
    prof = cProfile.Profile()
    t0 = time.perf_counter()
    prof.enable()
    v, res = _VALIDATE(big, data, ins, peaks=peaks, with_result=True)
    prof.disable()
    print(json.dumps(dict(secs=round(time.perf_counter() - t0, 1), n_refl=v.n_reflections,
                          status=v.status, rwp=round(v.rwp, 4),
                          stages=[(s.status, s.n_iterations) for s in res.stages])),
          flush=True)
    buf = io.StringIO()
    pstats.Stats(prof, stream=buf).sort_stats("cumulative").print_stats(45)
    print(buf.getvalue())
    buf = io.StringIO()
    pstats.Stats(prof, stream=buf).sort_stats("tottime").print_stats(25)
    print(buf.getvalue())


if __name__ == "__main__":
    main()

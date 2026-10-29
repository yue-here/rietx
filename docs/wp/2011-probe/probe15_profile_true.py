"""Where a Pawley validation of NAC's *true* cell spends its 6 s.

Probe 14 found ``quick`` validating none of NAC's candidates even with the
2224-reflection outlier fixed: a slice is 2-3 s and the well-conditioned true
cell (837 reflections) costs about 6.  This profiles that one fit, under the
solver variant ``--variant`` names, and prints the top of the tottime and
cumulative tables.

    python probe15_profile_true.py truths nac --variant SPARSE_NORMAL=1,...
"""
from __future__ import annotations

import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import probe5_after_941 as p5  # noqa: E402

from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from rietx.optimize import bccg, lm  # noqa: E402


def run(rows, case, cand, data, ins, peaks, **_):
    prof = cProfile.Profile()
    t0 = time.perf_counter()
    prof.enable()
    v = validate_by_lebail(cand, data, ins, peaks=peaks)
    prof.disable()
    print(case, round(time.perf_counter() - t0, 2), "s", v.n_reflections, v.rwp,
          v.unmatched_observed, flush=True)
    for key in ("tottime", "cumulative"):
        buf = io.StringIO()
        pstats.Stats(prof, stream=buf).sort_stats(key).print_stats(28)
        print(buf.getvalue()[-6000:])


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--variant" in args:
        i = args.index("--variant")
        for kv in args[i + 1].split(","):
            key, value = kv.split("=")
            mod = bccg if key.startswith("bccg.") else lm
            key = key.split(".", 1)[-1]
            old = getattr(mod, key)
            setattr(mod, key, value == "1" if isinstance(old, bool) else type(old)(value))
        del args[i:i + 2]
    sys.argv = [sys.argv[0]] + args
    p5.run = run
    p5.truths([])

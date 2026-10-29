"""Profile ``consensus`` on 11-BM NAC under ``quick``: 6.5 s of a 9.6 s reserve.

Probe 19 timed consensus at 114.5 → 120.95 s, after the search, against the
whole-run clock; with the search's own 4.1 s overrun it left validation
nothing.  This profiles that one call inside a real ``quick`` run.

    python probe20_consensus_profile.py nac_default
"""
from __future__ import annotations

import cProfile
import importlib
import io
import pstats
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe8_quick import sets  # noqa: E402

import rietx.indexing.workflow as wf  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402


def main(argv):
    cons = importlib.import_module("rietx.indexing.consensus")
    real = cons.consensus
    prof = cProfile.Profile()

    def wrapped(*a, **kw):
        prof.enable()
        try:
            return real(*a, **kw)
        finally:
            prof.disable()
    cons.consensus = wrapped
    load, spec = sets()[argv[0]]
    data, ins = load()
    peaks = pick_peaks(data, ins)
    wf.index_pattern(peaks, data=data, instrument=ins, spec=spec)
    out = io.StringIO()
    stats = pstats.Stats(prof, stream=out)
    stats.sort_stats("cumulative").print_stats(35)
    stats.sort_stats("tottime").print_stats(15)
    print(out.getvalue())


if __name__ == "__main__":
    main(sys.argv[1:])

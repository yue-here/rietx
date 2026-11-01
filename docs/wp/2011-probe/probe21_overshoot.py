"""How late does a search unit stop after its clock fires?  11-BM NAC.

Probe 19 had trial_error's tetragonal unit end 4.1 s after the search's
deadline.  This runs each engine's unit for one system on NAC under a
``Deadline`` of a few seconds and prints how long past it the unit returned,
profiling the trial_error unit to say where the time between checks goes.

    python probe21_overshoot.py tetragonal 5
"""
from __future__ import annotations

import cProfile
import io
import pstats
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from tests.test_acceptance_nac import build_nac_inputs  # noqa: E402

from rietx.indexing.engines import Deadline, SearchSpec, get_engine  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.indexing.quality import assess_peak_list  # noqa: E402


def main(argv):
    system, seconds = argv[0], float(argv[1])
    data, _structure, ins = build_nac_inputs()
    peaks = pick_peaks(data, ins)
    quality = assess_peak_list(peaks)
    spec = replace(SearchSpec(), systems=(system,))
    for name in ("trial_error", "svd", "dichotomy"):
        prof = cProfile.Profile()
        deadline = Deadline(seconds)
        t0 = time.perf_counter()
        prof.enable()
        get_engine(name)(peaks, spec=spec, quality=quality, cancel=deadline)
        prof.disable()
        took = time.perf_counter() - t0
        print(f"{name} {system}: returned at {took:.2f} s, "
              f"{took - seconds:+.2f} s past a {seconds:g} s clock", flush=True)
        if name == "trial_error":
            out = io.StringIO()
            pstats.Stats(prof, stream=out).sort_stats("cumulative").print_stats(18)
            print(out.getvalue())


if __name__ == "__main__":
    main(sys.argv[1:])

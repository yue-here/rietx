"""How late does a Pawley validation fit honour its cancel, and where is it?

Issue #1231: a 3931-reflection rival ran 125 s past ``Deadline(30)``.  The
triage reproduced it on 11-BM NAC with a tP description of the true cI
metric (4552 reflections), 10.9 s late under ``Deadline(15)``.  This builds
that candidate, fits it under a ``Deadline``, and prints how late the
cancel landed, with a cProfile of the fit to say what runs between reads.

    python probe2_late_cancel.py SECONDS [--profile]
"""
from __future__ import annotations

import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from rietx.indexing.engines import Deadline  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from rietx.optimize.cancel import RefinementCancelled  # noqa: E402
from rietx.schemas.indexing import CellCandidate  # noqa: E402
from tests.test_acceptance_nac import build_nac_inputs  # noqa: E402

A = 10.2510


def main(argv):
    seconds = float(argv[0])
    profile = "--profile" in argv
    data, _structure, ins = build_nac_inputs()
    peaks = pick_peaks(data, ins)
    cand = CellCandidate(
        cell=(A, A, A, 90.0, 90.0, 90.0), cell_esd=(1e-5,) * 6,
        system="tetragonal", centring="P", lattice_group="P 4/m m m",
        volume=A ** 3, n_indexed=20, n_lines=20)
    prof = cProfile.Profile()
    deadline = Deadline(seconds)
    t0 = time.perf_counter()
    if profile:
        prof.enable()
    try:
        out = validate_by_lebail(cand, data, ins, peaks=peaks, cancel=deadline)
        status = f"{out.status}, {out.n_reflections} reflections"
    except RefinementCancelled as exc:
        status = f"cancelled ({exc})"
    finally:
        prof.disable()
    took = time.perf_counter() - t0
    print(f"{status}: returned at {took:.2f} s, {took - seconds:+.2f} s past "
          f"a {seconds:g} s clock", flush=True)
    if profile:
        buf = io.StringIO()
        st = pstats.Stats(prof, stream=buf)
        st.sort_stats("cumulative").print_stats(30)
        st.sort_stats("tottime").print_stats(12)
        print(buf.getvalue())


if __name__ == "__main__":
    main(sys.argv[1:])

"""FAP.XRA's Pawley fit with and without the dense Cholesky preconditioner.

The one measured Pawley stage past ``PAWLEY_SPARSE_DENSITY`` is FAP's closing
stage (38 % dense, 343 columns), well conditioned.  This times the shipped
fit with ``bccg._PRECONDITION_DENSE`` off and on, alternating, and prints
Rwp to seven decimals and each stage's iterations.

    python probe22_fap_dense_pc.py 3
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import rietx as rx  # noqa: E402
from rietx.optimize import bccg  # noqa: E402
from tests.test_acceptance_fap import build_fap_inputs  # noqa: E402


def main(argv):
    for _ in range(int(argv[0]) if argv else 1):
        for on in (False, True):
            bccg._PRECONDITION_DENSE = on
            data, structure, instrument = build_fap_inputs()
            ref = rx.Refinement(structure, instrument, history=False)
            t = time.perf_counter()
            result = ref.fit(data, mode="pawley", telemetry=False)
            secs = time.perf_counter() - t
            print(f"dense_pc={on} {secs:.2f}s rwp={result.statistics.rwp:.7f}",
                  [s.n_iterations for s in result.stages], flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])

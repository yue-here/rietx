"""Task 4, idle half: seconds per validation fit on the largest patterns, both modes.

Probe 6 timed the indexer's own validations while another session's suite
held the machine; this one is for an idle machine.  It times the shipped
``validate_by_lebail`` (peak list supplied, as ``index_pattern`` calls it) on
11-BM NAC's true I cell and its primitive description, FAP's true cell and
corundum's, three repeats each, the two modes alternating.

Run alone, from the worktree root:  .venv/bin/python docs/wp/2011-probe/probe7_idle_cost.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe5_after_941 import fit_mode  # noqa: E402

from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from rietx.schemas.indexing import CellCandidate  # noqa: E402

REPEATS = 3


def main():
    from tests.test_acceptance_fap import build_fap_inputs
    from tests.test_acceptance_indexing import _qarr
    from tests.test_acceptance_nac import build_nac_inputs
    from rietx.indexing.pick import pick_peaks

    hexa = (90.0, 90.0, 120.0)
    right = (90.0, 90.0, 90.0)
    cases = [
        ("nac_I", lambda: build_nac_inputs()[::2], "cubic", "I", (10.2510,) * 3 + right),
        ("nac_P", lambda: build_nac_inputs()[::2], "cubic", "P", (10.2510,) * 3 + right),
        ("fap", lambda: build_fap_inputs()[::2], "hexagonal", "P", (9.3717, 9.3717, 6.8859) + hexa),
        ("corundum", lambda: _qarr("corundum.prn"), "trigonal", "R", (4.7589, 4.7589, 12.991) + hexa),
    ]
    for name, load, system, centring, cell in cases:
        data, ins = load()
        peaks = pick_peaks(data, ins)
        cand = CellCandidate(cell=cell, cell_esd=(0.0,) * 6, system=system,
                             centring=centring)
        secs = {"lebail": [], "pawley": []}
        for k in range(REPEATS):
            for mode in (("lebail", "pawley") if k % 2 == 0 else ("pawley", "lebail")):
                with fit_mode(mode):
                    t0 = time.perf_counter()
                    v = validate_by_lebail(cand, data, ins, peaks=peaks)
                    secs[mode].append(round(time.perf_counter() - t0, 2))
        print(json.dumps(dict(case=name, n_refl=v.n_reflections, **secs)), flush=True)


if __name__ == "__main__":
    main()

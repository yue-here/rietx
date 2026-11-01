"""test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error's fits under 1e-14 nudges to cell a.

usage: python lebail_nudge.py <worktree> <tmpdir> k [k ...]
"""
import math
import sys
import traceback

root, tmp = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.schemas.structure import lebail_scaffold  # noqa: E402
from tests._synthetic_silicon import silicon_pattern  # noqa: E402
from tests.test_cell_runaway_safety import TRICLINIC  # noqa: E402

path = f"{tmp}/si_flat.xy"
pattern = silicon_pattern("flat")
np.savetxt(path, np.c_[pattern.two_theta, pattern.intensity], fmt="%.4f %.0f")
data = rx.read_pattern(path)

for k in (int(a) for a in sys.argv[3:]):
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.background = rx.background.auto_background(data).background
    cell = list(TRICLINIC)
    cell[0] *= 1 + k * 1e-14
    structure = lebail_scaffold("P 1", cell)
    out = []
    try:
        for plan in ("profile_only", "lab_bragg_brentano"):
            ref = rx.Refinement(structure, ins, history=False, solver="trf")
            result = ref.fit(data, mode="lebail", plan=plan, telemetry=False,
                             two_theta_limits=(8.0, 70.0))
            rwp = float(result.statistics.rwp)
            runaway = sum(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
            out.append(f"{plan}: rwp {rwp:.4g} finite {math.isfinite(rwp)} runaway {runaway}")
            structure, ins = ref.fitted_structure, ref.fitted_instrument
        print(k, " | ".join(out), flush=True)
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)
        where = " <- ".join(f"{f.filename.split('/src/')[-1]}:{f.lineno} {f.name}" for f in tb[::-1] if "/src/rietx/" in f.filename)
        print(k, " | ".join(out), "| RAISED", type(e).__name__, str(e)[:80], "at", where, flush=True)

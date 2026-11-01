"""The case the density gate's review asked for: ill-conditioned *and* past the cut.

``PAWLEY_SPARSE_DENSITY`` sends a Pawley stage whose windows fill more than
5 % of the intensity block to the dense path, whose CG is unpreconditioned.
NAC's 376 s outlier was ill-conditioning (a pseudo-symmetric candidate whose
reflections pair up just outside the 0.5-FWHM overlap restraint), on narrow
synchrotron windows.  Lab windows are wide, so the same pathology on a lab
pattern would land on the dense, unpreconditioned path.

This builds it: a lab truth cell described as monoclinic P with β nudged off
90° (or, for a hexagonal cell, its orthohexagonal C setting with b nudged off
a·√3), so each reflection gets a partner a fraction of a FWHM away.  Each row
records the validation's seconds, the widest LM system (``n_cols``), the
stage densities seen, the CG products spent per solve and the readings.

    python probe17_dense_illcond.py zircon:0.06 fap:0.002 ...
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import rietx.optimize.least_squares as L  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from rietx.optimize import bccg, lm  # noqa: E402

N_COLS: list[int] = []
CG: list[int] = []
DENS: list[float] = []
_MIN = lm.minimize
_PCG = bccg.projected_cg
_NE = L._pawley_normal_equations


def _minimize(residual, jacobian, x0, *a, **k):
    N_COLS.append(len(x0))
    return _MIN(residual, jacobian, x0, *a, **k)


def _projected_cg(H, g, lo, hi, *, budget=None):
    count = [0]

    class Counting(np.ndarray):
        def __matmul__(self, v):
            count[0] += 1
            return np.asarray(self) @ v

    from scipy import sparse
    if sparse.issparse(H):
        M = H

        class Wrapped(type(H)):
            def __matmul__(self, v):
                count[0] += 1
                return M @ v
        Hc = Wrapped(H)
    else:
        Hc = np.asarray(H).view(Counting)
    out = _PCG(Hc, g, lo, hi, budget=budget)
    CG.append(count[0])
    return out


def _normal_equations(model, n_table):
    from rietx.model import rows as row_layout

    row, _indptr = L._pawley_tail_pattern(model)
    DENS.append(len(row) / float(row_layout.n_rows(model) * max(model.pawley.n, 1)))
    return _NE(model, n_table)


lm.minimize = _minimize
bccg._PRECONDITION_DENSE = os.environ.get("DENSE_PC", "1") == "1"
bccg.projected_cg = _projected_cg
L._pawley_normal_equations = _normal_equations


def cases():
    from tests.test_acceptance_fap import build_fap_inputs
    from tests.test_acceptance_indexing import _qarr

    return {
        "zircon": (lambda: _qarr("zircon.prn"), (6.6042, 6.6042, 5.9796)),
        "fap": (lambda: build_fap_inputs()[::2], (9.3717, 9.3717, 6.8859)),
        "corundum": (lambda: _qarr("corundum.prn"), (4.7589, 4.7589, 12.991)),
        "zincite": (lambda: _qarr("zincite.prn"), (3.2498, 3.2498, 5.2066)),
    }


def candidate(name, abc, nudge):
    from rietx.schemas.indexing import CellCandidate

    a, b, c = abc
    if name in ("fap", "corundum", "zincite"):
        # orthohexagonal C: (a, a√3, c, 90, 90, 90), then monoclinic with
        # β nudged — reflections pair as (h k l)/(h k -l)
        b = a * math.sqrt(3.0)
        return CellCandidate(cell=(a, b, c, 90.0, 90.0 + nudge, 90.0),
                             cell_esd=(0.0,) * 6, system="monoclinic",
                             centring="C")
    return CellCandidate(cell=(a, b, c, 90.0, 90.0 + nudge, 90.0),
                         cell_esd=(0.0,) * 6, system="monoclinic", centring="P")


def main(argv):
    from rietx.indexing.pick import pick_peaks

    table = cases()
    for arg in argv:
        name, nudge = arg.split(":")
        load, abc = table[name]
        data, ins = load()
        peaks = pick_peaks(data, ins)
        cand = candidate(name, abc, float(nudge))
        N_COLS.clear()
        CG.clear()
        DENS.clear()
        t0 = time.perf_counter()
        v = validate_by_lebail(cand, data, ins, peaks=peaks)
        secs = time.perf_counter() - t0
        dense = [n for n in CG]
        print(json.dumps(dict(
            case=name, dense_pc=bccg._PRECONDITION_DENSE, nudge=float(nudge), secs=round(secs, 2),
            n_refl=v.n_reflections, n_cols=max(N_COLS) if N_COLS else None,
            density=[round(d, 3) for d in DENS], n_solves=len(CG),
            cg_products_max=max(dense) if dense else None,
            cg_products_total=sum(dense), status=v.status,
            rwp=round(v.rwp, 5), unmatched=v.unmatched_observed,
            absent=v.predicted_but_absent)), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])

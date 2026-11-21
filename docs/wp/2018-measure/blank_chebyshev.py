"""C37: a free measured-background scale beside the Chebyshev rows (WP-2018, task 3).

``BackgroundFixedPlusChebyshev`` puts the measured curve in the design as a
row when its scale is free (forward.py) and the Chebyshev terms describe what
is left; both are linear in the background, so as the polynomial grows it can
take over part of the curve, and nothing in the fit separates the two
(``background.select`` counts the scale in its BIC only).  The dataset is
``tests/test_acceptance_si640c.py``'s Si SRM 640c in Kapton with the blank
(``11BM_Kapton.xy``), the ``_fit_chebyshev`` protocol, in arms:

  free_<n>   the blank's scale free from 1.0 under an n-term Chebyshev,
             n = 2, 3 (the ``blank_free`` fixture), 6 (``blank_free_cheb6``)
             and 10, the positive arm, where the polynomial has room to
             imitate the blank
  held_<n>   the scale held at 1.0 (n = 3, the ``blank_held`` fixture, and 10)

Per arm: the blank's scale (value, esd), its largest |ρ| with any Chebyshev
coefficient in the closing solve's correlation matrix, the specimen's scale,
Biso, ``lor_size`` and λ, Rwp (each arm against its own σ, which C26 shows
depends on the scale), and every code.

usage (repo root): python docs/wp/2018-measure/blank_chebyshev.py [arm ...]
"""
from __future__ import annotations

import importlib
import os
import sys

import numpy as np
from common import diagnostics, emit, patched, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

from tests.test_acceptance_si640c import _fit_chebyshev  # noqa: E402

refine_module = importlib.import_module("rietx.refine")

ARMS = ("free_2", "free_3", "free_6", "free_10", "held_3", "held_10")
SCALE = "instrument.background.scale"
PATHS = (SCALE, "phases.0.scale", "phases.0.atoms.0.biso", "phases.0.lor_size",
         "instrument.source.lines.0.wavelength", "instrument.background.c0")


def _keeping(real, last):
    def solve(model, table, **kwargs):
        outcome = real(model, table, **kwargs)
        last[:] = [list(table.free_paths), outcome.correlation]
        return outcome
    return solve


def main(arms):
    emit({"provenance": provenance(), "fixture": "test_acceptance_si640c, Kapton blank"})
    for arm in arms:
        kind, n = arm.split("_")
        last = []
        try:
            with patched(refine_module, "run_least_squares",
                         _keeping(refine_module.run_least_squares, last)):
                fit = _fit_chebyshev(int(n), blank_scale=1.0, free_scale=kind == "free")
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        res = fit.result
        rho = None
        free, corr = last if last else ([], None)
        if corr is not None and SCALE in free:
            c = np.asarray(corr)
            i = free.index(SCALE)
            cheb = [j for j, p in enumerate(free) if p.startswith("instrument.background.c")]
            rho = {free[j]: float(c[i, j]) for j in cheb}
        emit({"arm": arm, "rwp": res.statistics.rwp, "status": res.status,
              "params": {p.path: [p.value, p.stderr] for p in res.parameters
                         if p.path in PATHS},
              "scale_rho_with_chebyshev": rho,
              "diagnostics": diagnostics(res)})


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

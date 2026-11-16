"""C36: the background's start against the Le Bail partition at stage compile (WP-2018, task 3).

``CompiledModel.lebail_update`` partitions the observed counts at each stage's
compile, against the background the stage starts from, and holds those
intensities through its solve; ``auto_background(seed=True)`` starts the
background at a percentile of the counts instead of at 0, and is opt-in
(background/auto.py).  So by default the first partition (the ``bkg`` stage
of ``profile_only``) runs against an unfitted background.  Three patterns of
the same synthetic Pnma LaMnO₃-like phase (CW neutron 2.4 Å, FWHM 0.5°, true
cell known): #740's (``tests/test_lebail_cycles.py``, pedestal 300 + 2·2θ),
and ``tests/test_lebail_background_hump.py``'s two (the same pedestal with a
different scale and noise draw, and with a 600-count hump at 50°), each
fitted as that module fits (``profile_only`` Le Bail from the true cell and
widths), in arms ``<pattern>_<start>``:

  zero    ``auto_background(...)``: every coefficient at 0 (the default)
  seed    ``auto_background(..., seed=True)``
  truth   the positive arm: the true background curve held
          (``BackgroundFixedPlusChebyshev``, its 4 Chebyshev terms free from
          0), so the first partition is against the right curve

Per arm: Rwp, the cell in ppm from the truth with esds, the widths, the
background over the truth at 50°, and every code.

usage (repo root): python docs/wp/2018-measure/lebail_bkg_seed.py [arm ...]
"""
from __future__ import annotations

import os
import sys

import numpy as np
from common import diagnostics, emit, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

from lebail_ftol import _pattern as cycles_pattern  # noqa: E402

import rietx as rx  # noqa: E402
from tests.test_auto_background_seed import _neutron, _phase  # noqa: E402
from tests.test_lebail_background_hump import (  # noqa: E402
    GRID,
    HUMP_CENTRE,
    LIMITS,
    _pattern,
    _true_background,
)
from tests.test_lebail_cycles import TRUE_CELL  # noqa: E402

PATTERNS = ("740", "flat", "hump")
ARMS = tuple(f"{p}_{s}" for p in PATTERNS for s in ("zero", "seed", "truth"))


def _data(name):
    if name == "740":
        return cycles_pattern(), _true_background(False)
    hump = name == "hump"
    return _pattern(hump), _true_background(hump)


def fit(arm):
    name, start = arm.split("_")
    data, truth = _data(name)
    if start == "truth":
        background = rx.BackgroundFixedPlusChebyshev.from_pattern(
            rx.PatternData(two_theta=GRID.tolist(), intensity=truth.tolist()),
            source="the true curve")
    else:
        background = rx.auto_background(data, two_theta_limits=LIMITS,
                                        seed=start == "seed").background
    ins = _neutron()
    ins.background = background
    ref = rx.Refinement(rx.Structure(phases=[_phase(0.02)]), ins, history=False)
    result = ref.fit(data, mode="lebail", plan="profile_only", telemetry=False)
    ratio = (np.interp(HUMP_CENTRE, result.two_theta, result.y_background)
             / np.interp(HUMP_CENTRE, GRID, truth))
    return result, float(ratio)


def main(arms):
    emit({"provenance": provenance(), "true_cell": TRUE_CELL})
    for arm in arms:
        try:
            result, ratio = fit(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rows = {p.path: p for p in result.parameters}
        cell = {ax: [(rows[f"phases.0.cell.{ax}"].value - t) / t * 1e6,
                     rows[f"phases.0.cell.{ax}"].stderr / t * 1e6]
                for ax, t in TRUE_CELL.items()}
        emit({"arm": arm, "rwp": result.statistics.rwp, "status": result.status,
              "cell_ppm": cell, "background_over_truth_at_50": ratio,
              "widths": {p.path.rsplit(".", 1)[-1]: [p.value, p.stderr]
                         for p in result.parameters
                         if p.path.startswith("instrument.profile.")},
              "stages": [{"stage": s.name, "rwp": s.rwp,
                          "lebail_cycles_run": list(s.lebail_cycles_run)}
                         for s in result.stages],
              "diagnostics": diagnostics(result)})


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

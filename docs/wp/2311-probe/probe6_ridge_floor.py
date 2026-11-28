"""WP-2311: is zircon's residual unit dependence the off-data ridge's floor?

Probe 5, with the group floor fixed: zircon's true cell reads Rwp 0.147446
on counts and 0.147441 with intensity, σ and the declared background divided
by the maximum count.  ``PAWLEY_OFF_DATA_SCALE_FLOOR`` (1.0, in counts) is
the other absolute number in ``build_pawley_restraint``; WP-2011 probe 9
recorded it binding on zircon at a maximum of 1.  This reruns zircon's
``base`` and ``units`` variants at the shipped floor and at 1e-10, and logs
the ridge's scale per build.

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe6_ridge_floor.py [names...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "2011-probe"))

import probe5_after_941 as p5  # noqa: E402
from probe5_real_truths import variant  # noqa: E402

import rietx.model.forward as fwd  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402

SHIPPED = fwd.PAWLEY_OFF_DATA_SCALE_FLOOR
_BUILD = fwd.CompiledModel.build_pawley_restraint
RIDGE: list[float] = []


def build(self, lam=fwd.PAWLEY_OVERLAP_LAMBDA):
    pb = self.pawley
    if pb is not None and pb.off_data:
        intens = self.pawley_x0()
        off = np.zeros(pb.n, dtype=bool)
        off[pb.off_data] = True
        for a, b in pb.phase_slices:
            on = intens[a:b][~off[a:b]]
            RIDGE.append(float(on.max()) if len(on) else 0.0)
    _BUILD(self, lam)


def run(rows, case, cand, data, ins, peaks):
    fwd.CompiledModel.build_pawley_restraint = build
    try:
        for floor in (SHIPPED, 1e-10):
            fwd.PAWLEY_OFF_DATA_SCALE_FLOOR = floor
            for which in ("base", "units"):
                d, i = variant(data, ins, which)
                RIDGE.clear()
                v, _ = validate_by_lebail(cand, d, i, peaks=peaks, with_result=True)
                rec = dict(case=case, data=which, ridge_floor=floor, rwp=round(v.rwp, 7),
                           unmatched=v.unmatched_observed,
                           ridge_s=[float(f"{x:.3g}") for x in RIDGE])
                print(json.dumps(rec), flush=True)
    finally:
        fwd.PAWLEY_OFF_DATA_SCALE_FLOOR = SHIPPED
        fwd.CompiledModel.build_pawley_restraint = _BUILD


if __name__ == "__main__":
    p5.run = run
    sys.argv = [sys.argv[0], "truths", *(sys.argv[1:] or ["zircon"])]
    p5.truths([])

"""WP-2311 task 5: the fix on the nine real true cells of WP-2011 probe 5.

Each true cell runs the shipped ``validate_by_lebail`` (Pawley, peak-list
path, widths free) with ``PAWLEY_GROUP_SCALE_FLOOR_REL`` at 0 (the old
behaviour exactly: the group scale was max(mean, 1e-10)) and at the shipped
value, under three data variants:

- ``base``: the pattern as read;
- ``scaled``: intensity and σ divided by the maximum count, the declared
  instrument untouched (WP-2011 probe 9's variant, which moves the start too);
- ``units``: as ``scaled``, with the declared background coefficients divided
  by the same number, so only the units move.

Each row records the validation's readings and, per restraint build, how many
groups the new floor raised (``bound``: mean under ρ × the phase's largest
on-data intensity).  Peaks are picked once from the pattern as read and handed
to every variant, so the picker is not a variable (probe 1: it is not one).

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe5_real_truths.py [names...]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parents[1] / "2011-probe"))

import probe5_after_941 as p5  # noqa: E402

import rietx.model.forward as fwd  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402

SHIPPED = fwd.PAWLEY_GROUP_SCALE_FLOOR_REL
_BUILD = fwd.CompiledModel.build_pawley_restraint
BOUND: list[int] = []


def build(self, lam=fwd.PAWLEY_OVERLAP_LAMBDA):
    pb = self.pawley
    if pb is not None and pb.groups:
        intens = self.pawley_x0()
        off = np.zeros(pb.n, dtype=bool)
        off[pb.off_data] = True
        n_bound = 0
        for a, b in pb.phase_slices:
            on = intens[a:b][~off[a:b]]
            top = float(on.max()) if len(on) else 0.0
            n_bound += sum(1 for g in pb.groups if a <= g[0] < b
                           and float(np.mean(intens[g])) < SHIPPED * top)
        BOUND.append(n_bound)
    _BUILD(self, lam)


def variant(data, ins, which):
    if which == "base":
        return data, ins
    top = float(np.max(data.intensity))
    d = data.model_copy(update={"intensity": (np.asarray(data.intensity) / top).tolist(),
                                "sigma": (np.asarray(data.sig()) / top).tolist()})
    if which == "scaled":
        return d, ins
    i = ins.model_copy(deep=True)
    for c in getattr(i.background, "coefficients", None) or []:
        c.value /= top
    return d, i


def run(rows, case, cand, data, ins, peaks):
    fwd.CompiledModel.build_pawley_restraint = build
    try:
        for which in ("base", "scaled", "units"):
            d, i = variant(data, ins, which)
            for rel in (0.0, SHIPPED):
                fwd.PAWLEY_GROUP_SCALE_FLOOR_REL = rel
                BOUND.clear()
                t0 = time.perf_counter()
                v, result = validate_by_lebail(cand, d, i, peaks=peaks, with_result=True)
                rec = dict(case=case, data=which, rel=rel,
                           secs=round(time.perf_counter() - t0, 2),
                           rwp=round(v.rwp, 6), status=v.status,
                           unmatched=v.unmatched_observed,
                           absent=v.predicted_but_absent,
                           bound=list(BOUND))
                rows.append(rec)
                print(json.dumps(rec), flush=True)
    finally:
        fwd.PAWLEY_GROUP_SCALE_FLOOR_REL = SHIPPED
        fwd.CompiledModel.build_pawley_restraint = _BUILD


if __name__ == "__main__":
    p5.run = run
    sys.argv = [sys.argv[0], "truths", *sys.argv[1:]]
    rows: list[dict] = []
    p5.truths(rows)

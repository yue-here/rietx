"""WP-2311: is the equal-split restraint's scale the lock?

``build_pawley_restraint`` weighs each overlap group's rows by √λ/s with
s = max(mean(I_group), 1e-10).  Probe 3: under a declared background 10x or
100x the data the seed leaves groups on ``LEBAIL_INTENSITY_FLOOR`` (1e-10), so
s is 1e-10 and the rows weigh 5e9, in every stage, since each rebuild reads
the group's stuck value.  Each variant replaces the group scale and nothing
else (the off-data ridge is untouched):

- ``shipped``: the tree's own ``build_pawley_restraint`` (the absolute floor
  when this ran on 2026-11-26 before the fix; the relative one after it).
- ``no_groups``: the overlap rows dropped (λ_group = 0); the ridge stays.
- ``phase_max``: s = max(mean, phase's largest on-data intensity).
- ``rel=r``: s = max(mean, r × phase's largest on-data intensity).

Every variant but ``shipped`` builds its own group rows and takes only the
ridge from the tree's builder, so its reading does not depend on which floor
the tree ships.  f = 1 data throughout; ``g`` multiplies the declared
background.  ``rel=1e-9`` is the window's lower edge (the lock returns).

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe4_restraint_scale.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from probe1_rerun import lab6_data  # noqa: E402
from probe2_start_vs_units import with_bkg  # noqa: E402

import rietx.model.forward as fwd  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from tests.test_indexing_consensus import TRUE_A, _candidate, _instrument  # noqa: E402

_BUILD = fwd.CompiledModel.build_pawley_restraint


def make_build(rel):
    """``rel`` None: no group rows; a float: floor s at rel × phase on-data max."""
    def build(self, lam=fwd.PAWLEY_OVERLAP_LAMBDA):
        pb = self.pawley
        groups = pb.groups
        if rel is None:
            pb.groups = []
            try:
                _BUILD(self, lam)
            finally:
                pb.groups = groups
            return
        pb.groups = []
        try:
            _BUILD(self, lam)            # the ridge alone
        finally:
            pb.groups = groups
        if not groups:
            return
        intens = self.pawley_x0()
        off = np.zeros(pb.n, dtype=bool)
        off[pb.off_data] = True
        phase_of = np.zeros(pb.n, dtype=int)
        top = []
        for ip, (a, b) in enumerate(pb.phase_slices):
            phase_of[a:b] = ip
            on = intens[a:b][~off[a:b]]
            top.append(float(on.max()) if len(on) else 0.0)
        rows = []
        for g in groups:
            s = max(float(np.mean(intens[g])), rel * top[phase_of[g[0]]], 1e-10)
            n = len(g)
            for k in g:
                row = np.zeros(pb.n)
                for j in g:
                    row[j] = (np.sqrt(lam) / s) * ((1.0 if j == k else 0.0) - 1.0 / n)
                rows.append(row)
        rest = pb.restraint if pb.restraint is not None else np.zeros((0, pb.n))
        pb.restraint = np.vstack([np.array(rows), rest])
    return build


VARIANTS = [("shipped", "shipped"), ("no_groups", None), ("phase_max", 1.0),
            ("rel=1e-2", 1e-2), ("rel=1e-4", 1e-4), ("rel=1e-6", 1e-6),
            ("rel=1e-8", 1e-8), ("rel=1e-9", 1e-9)]


def main():
    data = lab6_data(11)
    ins = _instrument()
    peaks = pick_peaks(data, ins)
    cand = _candidate(TRUE_A)
    for name, rel in VARIANTS:
        fwd.CompiledModel.build_pawley_restraint = (
            _BUILD if rel == "shipped" else make_build(rel))
        try:
            for g in (1.0, 10.0, 100.0):
                v, res = validate_by_lebail(cand, data, with_bkg(ins, g), peaks=peaks,
                                            with_result=True)
                p = {q.path.split(".")[-1]: q.value for q in res.parameters
                     if q.path.split(".")[-1] in ("u", "w", "y")}
                print(json.dumps(dict(variant=name, g=g, rwp=round(v.rwp, 6),
                                      cost=round(res.stages[-1].cost_final, 3),
                                      iters=[s.n_iterations for s in res.stages],
                                      **{k: float(f"{x:.5g}") for k, x in p.items()})),
                      flush=True)
        finally:
            fwd.CompiledModel.build_pawley_restraint = _BUILD


if __name__ == "__main__":
    main()

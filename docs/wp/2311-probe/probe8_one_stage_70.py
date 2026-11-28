"""WP-2311 (generality review): why the one-stage fit fails at a background x70.

``probe7_one_stage.py`` recovers at x1 to x50 and reads Rwp 0.449 at x70.  This
logs what ``build_pawley_restraint`` sees (the seeded block's largest value,
how many reflections sit on the partition floor, the largest row weight) and
reruns with the group rows dropped, so the restraint's part is separable from
the solve's.

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe8_one_stage_70.py [g ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe7_one_stage import PLAN  # noqa: E402

import rietx.model.forward as fwd  # noqa: E402
from rietx import Dispersion, Refinement  # noqa: E402
from tests.test_pawley import _overlapped_lab6, _synth_overlapped  # noqa: E402

_BUILD = fwd.CompiledModel.build_pawley_restraint


def run(g, drop_groups, pattern):
    log = []

    def build(self, lam=fwd.PAWLEY_OVERLAP_LAMBDA):
        pb = self.pawley
        x = self.pawley_x0()
        groups = pb.groups
        if drop_groups:
            pb.groups = []
        try:
            _BUILD(self, lam)
        finally:
            pb.groups = groups
        w = float(np.abs(pb.restraint).max()) if pb.restraint is not None else 0.0
        log.append((float(x.max()), int((x <= 1e-9).sum()), x.size, w))

    fwd.CompiledModel.build_pawley_restraint = build
    try:
        s, ins = _overlapped_lab6(a=4.160, w=1e-2)
        ins.source.dispersion = Dispersion()
        for c in ins.background.coefficients:
            c.value *= g
        ref = Refinement(s, ins, history=False)
        r = ref.fit(pattern, mode="pawley", plan=PLAN)
    finally:
        fwd.CompiledModel.build_pawley_restraint = _BUILD
    print(g, "no_groups" if drop_groups else "shipped", r.status,
          round(r.statistics.rwp, 6), [st.n_iterations for st in r.stages],
          "builds (top, n_floor, n, w_max):", log, flush=True)


def main():
    pattern, _, _ = _synth_overlapped()
    for g in tuple(float(x) for x in sys.argv[1:]) or (50.0, 70.0):
        for drop in (False, True):
            run(g, drop, pattern)


if __name__ == "__main__":
    main()

"""WP-2311: what the Pawley seed and restraint look like under a too-high start.

Probe 2 showed the answer depends on the declared background's level, not on
the units.  The seed is one Le Bail partition of max(y_obs - bkg, 0), so a
background above the data partitions nothing and every intensity sits on
``LEBAIL_INTENSITY_FLOOR``.  This logs, per ``build_pawley_restraint`` call
(one per stage), the intensity block it saw and the restraint weight it built,
and per stage the fraction of intensities within 1e-6 of zero at the end.

Variants (f = 1 data throughout): ``g`` multiplies the declared background.
``bkg_only`` also runs a background-only stage *before* the plan, so the seed
partitions against a fitted background — the candidate fix's effect.

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe3_seed_state.py
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
LOG: list[dict] = []


def build(self, lam=fwd.PAWLEY_OVERLAP_LAMBDA):
    intens = self.pawley_x0()
    _BUILD(self, lam)
    pb = self.pawley
    s = [max(float(np.mean(intens[g])), 1e-10) for g in pb.groups] if pb else []
    LOG.append(dict(n=int(intens.size), n_floor=int((intens <= 1e-9).sum()),
                    i_max=float(intens.max()) if intens.size else None,
                    n_groups=len(pb.groups) if pb else 0,
                    s_min=min(s) if s else None,
                    w_max=(float(np.abs(pb.restraint).max())
                           if pb is not None and pb.restraint is not None else None)))


def main():
    data = lab6_data(11)
    ins = _instrument()
    peaks = pick_peaks(data, ins)
    cand = _candidate(TRUE_A)
    fwd.CompiledModel.build_pawley_restraint = build
    try:
        for g in (1.0, 10.0, 100.0):
            LOG.clear()
            v, res = validate_by_lebail(cand, data, with_bkg(ins, g), peaks=peaks,
                                        with_result=True)
            print(json.dumps(dict(g=g, rwp=round(v.rwp, 6),
                                  builds=[{k: (float(f"{x:.4g}") if isinstance(x, float) else x)
                                           for k, x in b.items()} for b in LOG])), flush=True)
    finally:
        fwd.CompiledModel.build_pawley_restraint = _BUILD


if __name__ == "__main__":
    main()

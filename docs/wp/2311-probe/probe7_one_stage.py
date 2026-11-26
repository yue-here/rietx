"""WP-2311 (review finding 1): does a fit's first stage still lock?

When the seed empties *every* on-data reflection of a phase, the phase's
largest on-data intensity is ``LEBAIL_INTENSITY_FLOOR`` itself, so the
relative floor has nothing to stand on and the group rows weigh 5e9 for that
stage.  A staged plan recovers at its next rebuild; a one-stage plan has none.
This fits the overlapped Cu-LaB6 fixture of ``tests/test_pawley.py`` with one
stage freeing background, cell, w and the zero shift, from the declared
background x1 and x100.

Run from the worktree root:
    .venv/bin/python docs/wp/2311-probe/probe7_one_stage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from rietx import Dispersion, Refinement  # noqa: E402
from rietx.strategy.staged import RefinementPlan, Stage  # noqa: E402
from tests.test_pawley import _overlapped_lab6, _synth_overlapped  # noqa: E402

PLAN = RefinementPlan(stages=[Stage("all", [
    "instrument.background.*", "phases.*.cell.*", "instrument.profile.w",
    "instrument.geometry.zero_shift"])], closing_window_tol=None)


def main():
    pattern, _, _ = _synth_overlapped()
    for g in (1.0, 100.0):
        s, ins = _overlapped_lab6(a=4.160, w=1e-2)
        ins.source.dispersion = Dispersion()
        for c in ins.background.coefficients:
            c.value *= g
        ref = Refinement(s, ins, history=False)
        r = ref.fit(pattern, mode="pawley", plan=PLAN)
        print(g, r.status, round(r.statistics.rwp, 6),
              int((ref._model.pawley_x0() < 1e-6).sum()),
              [st.n_iterations for st in r.stages], flush=True)


if __name__ == "__main__":
    main()

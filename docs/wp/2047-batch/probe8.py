"""WP-2047 probe 8: which answer is right, shipped or windows resized at every
evaluation (probe 7's ``perEval``)?

Each arm's protocol answer is polished at ``TOL_CONVERGED`` (5e-5) windows,
one stage freeing every glob the plan freed and no closing stage, until no row
moves by 0.01 esd (``test_window_domain._fixed_point``'s rule, started from
each arm's own answer rather than from the shipped one).  Reported: each
answer's distance from its own polished point, the distance between the two
polished points, and χ² at each.  Two polished points that agree mean the
arms differ by window error alone, and the nearer arm is the more accurate;
two that differ mean the arms reached different minima, and χ² ranks them.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe8.py . FAMILY
"""
import json
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import probe7  # noqa: E402

import rietx as rx  # noqa: E402
import rietx.model.forward as fwd  # noqa: E402
from tests import test_window_domain as w  # noqa: E402


def answer(family, arm):
    data, st, ins, plan, kw = w._protocol(family)
    probe7.arm_on(arm)
    try:
        ref = rx.Refinement(st, ins, history=False)
        res = ref.fit(data, plan=plan, **kw)
    finally:
        probe7.arm_off()
    return (data, plan, kw, ref.fitted_structure.model_copy(deep=True),
            ref.fitted_instrument.model_copy(deep=True), res)


def polish(data, plan, kw, st, ins):
    globs = sorted({g for s in plan.stages for g in s.turn_on})
    kw = {k: v for k, v in kw.items() if k != "plan"}
    was = fwd.WINDOW_AREA_TOL
    fwd.WINDOW_AREA_TOL = w.TOL_CONVERGED
    try:
        prev = res = None
        for rounds in range(1, 6):
            ref = rx.Refinement(st.model_copy(deep=True), ins.model_copy(deep=True),
                                history=False)
            res = ref.fit(data, plan=rx.RefinementPlan(
                stages=[rx.Stage("polish", globs)], closing_window_tol=None), **kw)
            cur = w._rows(res)
            st, ins = ref.fitted_structure, ref.fitted_instrument
            if prev is not None and max(w._shift(cur, prev, background=False)[0],
                                        w._shift(cur, prev, background=True)[0]) < 0.01:
                break
            prev = cur
        return res, rounds
    finally:
        fwd.WINDOW_AREA_TOL = was


def main(family):
    out = {"family": family}
    pols = {}
    for arm in ("shipped", "perEval"):
        data, plan, kw, st, ins, res = answer(family, arm)
        pol, rounds = polish(data, plan, kw, st, ins)
        pols[arm] = pol
        own = w._shift(w._rows(res), w._rows(pol), background=False)
        out[arm] = {"rwp": round(res.statistics.rwp, 6),
                    "chi2_polished": round(pol.statistics.chi2, 3),
                    "rounds": rounds,
                    "to_own_polish_esd": [round(own[0], 3), own[1]]}
    between = w._shift(w._rows(pols["perEval"]), w._rows(pols["shipped"]), background=False)
    out["polished_apart_esd"] = [round(between[0], 3), between[1]]
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main(sys.argv[2])

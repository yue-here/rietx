"""WP-2045 probe 6: what option 5 costs the four acceptance protocols and one joint fit.

Option 5 runs the last declared stage at the solver's tolerance when a closing
stage follows it.  Emulated here, as the task asks, by setting that stage's own
``ftol`` to ``optimize.lm.FTOL``, which wins in ``stage_ftols``.  Each family
runs shipped and emulated, interleaved, ``ROUNDS`` times.  Read-outs per arm:
wall seconds, residual evaluations (``StageResult.n_iterations`` counts them)
for the whole fit, the last declared stage and the closing stage, Rwp, and the
largest shift from the shipped answer in plain esd (non-background and
background rows apart, ``test_window_domain._shift``).

    RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2045-batch/probe6.py . [family ...]
"""
import json
import sys
import time

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.optimize.lm import FTOL  # noqa: E402
from tests import test_window_domain as w  # noqa: E402

ROUNDS = 2
FAMILIES = tuple(sys.argv[2:]) or ("lab6", "fap", "cpd1a", "nac", "joint")


def _joint_inputs():
    from tests.test_acceptance_wavelength import (
        NEUTRON_LIMITS,
        XRAY_LIMITS,
        _neutron_instrument,
        _patterns,
        _plan,
        _structure,
        _xray_instrument,
    )
    return (list(_patterns()), _structure(), [_xray_instrument(), _neutron_instrument()],
            _plan(None), {"two_theta_limits": [XRAY_LIMITS, NEUTRON_LIMITS]})


def run(family, arm):
    if family == "joint":
        data, st, ins, plan, kw = _joint_inputs()
    else:
        data, st, ins, plan, kw = w._protocol(family)
    assert plan.closing_window_tol == 1e-3
    own = plan.stages[-1].ftol
    if arm == "opt5" and own is None:
        plan.stages[-1].ftol = FTOL
    t0 = time.perf_counter()
    if family == "joint":
        res = rx.refine_multi(data, st, ins, plan=plan, **kw)
    else:
        res = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
    seconds = time.perf_counter() - t0
    stages = res.stages
    assert stages[-1].name == "closing", [s.name for s in stages]
    return {
        "seconds": seconds,
        "evals": sum(s.n_iterations for s in stages),
        "last_declared": (stages[-2].name, stages[-2].n_iterations, stages[-2].ftol,
                          stages[-2].status),
        "closing": (stages[-1].n_iterations, stages[-1].status),
        "rwp": res.statistics.rwp,
        "own_ftol": own,
        "rows": w._rows(res),
    }


def main():
    was = compiled.set_enabled(True)
    out = {}
    try:
        for family in FAMILIES:
            arms = {"shipped": [], "opt5": []}
            for _ in range(ROUNDS):
                for arm in ("shipped", "opt5"):
                    arms[arm].append(run(family, arm))
            ref = arms["shipped"][0]["rows"]
            summary = {}
            for arm, runs in arms.items():
                nonbg = w._shift(runs[0]["rows"], ref, background=False)
                bg = w._shift(runs[0]["rows"], ref, background=True)
                summary[arm] = {
                    "seconds": [round(r["seconds"], 2) for r in runs],
                    "evals": [r["evals"] for r in runs],
                    "last_declared": runs[0]["last_declared"],
                    "closing": runs[0]["closing"],
                    "rwp": runs[0]["rwp"],
                    "own_ftol": runs[0]["own_ftol"],
                    "away": (round(nonbg[0], 4), nonbg[1]),
                    "away_bg": (round(bg[0], 4), bg[1]),
                }
            out[family] = summary
            for arm, s in summary.items():
                print(family, arm, json.dumps(s), flush=True)
    finally:
        compiled.set_enabled(was)
    return out


if __name__ == "__main__":
    main()

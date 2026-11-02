"""WP-2045 probe 7: what the intermediate tolerance saves behind today's closing stage.

The four ``intermediate_ftol`` rows in ``src/rietx/_audit.py`` rest on cost
alone (ruled 2026-11-01).  Their saving, 1.00-2.15x fewer evaluations, was
measured by WP-1123 and WP-2002 before the closing stage existed and before
the last declared stage converged (option 5).  This probe measures the net
saving on today's schedule.

Two arms per protocol, interleaved, ``ROUNDS`` times:

- ``shipped``: the acceptance protocol as it ships (``intermediate_ftol``
  1e-6, the last declared stage and the closing stage at the solver's 1e-9).
- ``tight``: ``intermediate_ftol = None``, the bit-identical way back, so
  every stage runs at the solver's 1e-9.  The closing stage stays.

The protocols are ``tests/test_window_domain._protocol``'s, which
``tests/test_staged_start_invariance.py`` fits.  ``cpd1a_zircon`` is that
file's absent-phase fit.  Read-outs per arm: residual evaluations over the
whole fit (``StageResult.n_iterations`` is scipy's ``nfev``), wall seconds,
Rwp, and the largest shift between the arms in plain esd on non-background
rows and on background rows apart (``test_window_domain._shift``).

    RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2045-batch/probe7.py . [family ...]
"""
import json
import sys
import time

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from tests import test_window_domain as w  # noqa: E402

ROUNDS = 3
FAMILIES = tuple(sys.argv[2:]) or ("lab6", "fap", "cpd1a", "cpd1a_zircon", "nac")


def _zircon_inputs():
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
        zircon_phase,
    )
    if not DATA.exists():
        raise SystemExit(f"cpd1a_zircon needs the IUCr QPA round-robin data under {DATA}")
    data = rx.read_pattern(DATA / "cpd-1a.prn")
    st = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase(),
                              zircon_phase()])
    ins = qarr_instrument()
    seed_scales(st, ins, data)
    return data, st, ins, qpa_plan(), {}


def run(family, arm):
    if family == "cpd1a_zircon":
        data, st, ins, plan, kw = _zircon_inputs()
    else:
        data, st, ins, plan, kw = w._protocol(family)
    assert plan.closing_window_tol == 1e-3
    assert plan.intermediate_ftol == 1e-6, plan.intermediate_ftol
    if arm == "tight":
        plan.intermediate_ftol = None
    t0 = time.perf_counter()
    res = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
    seconds = time.perf_counter() - t0
    stages = res.stages
    assert stages[-1].name == "closing", [s.name for s in stages]
    return {
        "seconds": seconds,
        "evals": sum(s.n_iterations for s in stages),
        "per_stage": [(s.name, s.n_iterations, s.ftol, s.status) for s in stages],
        "rwp": res.statistics.rwp,
        "rows": w._rows(res),
    }


def main():
    was = compiled.set_enabled(True)
    out = {}
    try:
        for family in FAMILIES:
            arms = {"shipped": [], "tight": []}
            for _ in range(ROUNDS):
                for arm in ("shipped", "tight"):
                    arms[arm].append(run(family, arm))
            ref = arms["tight"][0]["rows"]
            cur = arms["shipped"][0]["rows"]
            nonbg = w._shift(cur, ref, background=False)
            bg = w._shift(cur, ref, background=True)
            summary = {"family": family}
            for arm, runs in arms.items():
                summary[arm] = {
                    "seconds": [round(r["seconds"], 2) for r in runs],
                    "evals": [r["evals"] for r in runs],
                    "per_stage": runs[0]["per_stage"],
                    "rwp": runs[0]["rwp"],
                }
            summary["ratio_tight_over_shipped"] = round(
                arms["tight"][0]["evals"] / arms["shipped"][0]["evals"], 3)
            summary["shift_esd"] = (round(nonbg[0], 4), nonbg[1])
            summary["shift_esd_bg"] = (round(bg[0], 4), bg[1])
            out[family] = summary
            print(json.dumps(summary), flush=True)
    finally:
        compiled.set_enabled(was)
    return out


if __name__ == "__main__":
    main()

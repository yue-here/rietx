"""C18: ``intermediate_ftol`` against the holds that read each stage's end (WP-2018, task 3).

The support hold, its release and collapse, the moment hold and the ridge hold
each read the point a stage ends at, and an intermediate stage ends at
``intermediate_ftol`` (1e-6) rather than the solver's 1e-9.  WP-2002 B7 saw the
support hold flip with the tolerance on cpd-1a with zircon declared (a phase
the sample lacks), under LM and before the closing stage existed;
``tests/test_staged_start_invariance.py`` now asserts the closing stage holds
zircon's nine structural paths under either tolerance.  Four arms, the round
robin's ``qpa_plan()`` with zircon declared, LM:

  close_1e-6   shipped: intermediate stages at 1e-6, the closing stage appended
  close_none   ``intermediate_ftol = None``: every stage at 1e-9
  open_1e-6    ``closing_window_tol = None`` (no closing stage), 1e-6: B7's arm
  open_none    no closing stage, every stage at 1e-9: B7's other arm, the
               positive arm (the flip B7 saw lives here if anywhere)

Per arm: what every stage held, released and collapsed (zircon's paths and
the rest apart), its tolerance, iterations and status, the final rows with
both esds, the QPA fractions and every code.

usage (repo root): python docs/wp/2018-measure/ftol_holds.py [arm ...]
"""
from __future__ import annotations

import os
import sys

from common import OUT, diagnostics, emit, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from tests.test_acceptance_qpa_roundrobin import (  # noqa: E402
    DATA,
    corundum_phase,
    fluorite_phase,
    qarr_instrument,
    qpa_plan,
    seed_scales,
    zincite_phase,
    zircon_phase,
)

ARMS = ("close_1e-6", "close_none", "open_1e-6", "open_none")


def fit(arm: str):
    closing, tol = arm.split("_")
    data = rx.read_pattern(DATA / "cpd-1a.prn")
    st = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase(),
                              zircon_phase()])
    ins = qarr_instrument()
    seed_scales(st, ins, data)
    plan = qpa_plan()
    plan.intermediate_ftol = None if tol == "none" else float(tol)
    if closing == "open":
        plan.closing_window_tol = None
    ref = rx.Refinement(st, ins, history=False)
    return ref, ref.fit(data, plan=plan, telemetry=False)


def rec_of(ref, result):
    def split(paths):
        z = [p for p in paths if p.startswith("phases.3.")]
        return {"zircon": z, "other": [p for p in paths if p not in z]}

    return {
        "rwp": result.statistics.rwp, "status": result.status,
        "stages": [{"stage": s.name, "ftol": s.ftol, "status": s.status,
                    "n_iterations": s.n_iterations, "rwp": s.rwp,
                    "held": split(list(s.held)), "released": split(list(s.released)),
                    "collapsed": split(list(s.collapsed or [])),
                    "cell_reset": list(s.cell_reset or [])}
                   for s in result.stages],
        "params": {p.path: [p.value, p.stderr, p.stderr_uncorrected, p.at_bound]
                   for p in result.parameters},
        "zircon_committed": {"a": ref.structure.phases[3].cell.a.value,
                             "c": ref.structure.phases[3].cell.c.value,
                             "scale": ref.structure.phases[3].scale.value},
        "fractions": {q.name: (q.weight_fraction, q.weight_fraction_stderr)
                      for q in result.qpa.phases} if result.qpa else None,
        "diagnostics": diagnostics(result),
    }


def main(arms):
    emit({"provenance": provenance()})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            ref, result = fit(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rec = rec_of(ref, result)
        rec["arm"] = arm
        emit(rec)
        result.plot(path=str(OUT / f"c18_{arm}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

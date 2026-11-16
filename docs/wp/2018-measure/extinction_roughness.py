"""C21: extinction and surface roughness free together (WP-2018, task 3).

Primary extinction (``model/extinction.py``) and Suortti roughness
(``model/corrections.py``) both attenuate intensity with angle, so each is
degenerate with the scale and Biso, and the structural plans free them in two
late stages, extinction then roughness, each kept free by cumulative staging.
Nothing but that order separates them.  The five lab patterns of C20, each
under its acceptance protocol (no closing stage), with five arms:

  neither      the protocol alone
  ext          ``Phase.extinction = 0.0`` declared on every phase, the plan's
               extinction stage appended
  rough        ``RoughnessSuortti()`` declared, the shipped roughness stage
               appended
  both         both declared, extinction then roughness: the shipped order
  swapped      both declared, roughness then extinction

Per arm: every extinction coefficient, Suortti a and b, every Biso and scale
(value, esd, plain esd, at_bound), χ², Rwp and every code.

usage (repo root): python docs/wp/2018-measure/extinction_roughness.py [family:arm ...]
"""
from __future__ import annotations

import os
import sys

from common import OUT, diagnostics, emit, provenance
from roughness_seed import FAMILIES, _inputs

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from rietx.schemas import RoughnessSuortti  # noqa: E402
from rietx.strategy.staged import _ROUGHNESS_STAGE  # noqa: E402

ARMS = tuple(f"{f}:{a}" for f in FAMILIES
             for a in ("neither", "ext", "rough", "both", "swapped"))
EXT_STAGE = rx.Stage("extinction", ["phases.*.extinction"])


def fit(arm: str):
    family, how = arm.split(":")
    data, structure, ins, plan = _inputs(family)
    ext = how in ("ext", "both", "swapped")
    rough = how in ("rough", "both", "swapped")
    if ext:
        for phase in structure.phases:
            phase.extinction = 0.0
    if rough:
        ins.geometry.surface_roughness = RoughnessSuortti()
    order = {"neither": [], "ext": [EXT_STAGE], "rough": [_ROUGHNESS_STAGE[0]],
             "both": [EXT_STAGE, _ROUGHNESS_STAGE[0]],
             "swapped": [_ROUGHNESS_STAGE[0], EXT_STAGE]}[how]
    plan.stages.extend(order)
    plan.closing_window_tol = None
    ref = rx.Refinement(structure, ins, history=False)
    return ref.fit(data, plan=plan, telemetry=False)


def main(arms):
    emit({"provenance": provenance()})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            result = fit(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        st = result.statistics
        emit({"arm": arm, "rwp": st.rwp, "chi2": st.chi2, "status": result.status,
              "stages": [(s.name, s.status, s.n_iterations) for s in result.stages],
              "params": {p.path: [p.value, p.stderr, p.stderr_uncorrected, p.at_bound]
                         for p in result.parameters
                         if p.path.endswith((".biso", ".scale", ".extinction"))
                         or ".surface_roughness." in p.path},
              "diagnostics": diagnostics(result)})
        result.plot(path=str(OUT / f"c21_{arm.replace(':', '_')}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

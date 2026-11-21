"""C20: the roughness seed against Biso under cumulative staging, Pitschke's c (WP-2018, task 3).

``staged.ROUGHNESS_SEED`` (0.3) lifts a roughness strength sitting on its
floor of 0 when the roughness stage frees it, while every Biso the earlier
stages freed keeps refining beside it.  WP-2002 measured Suortti's b
start-invariant on five lab Bragg-Brentano patterns from three laboratories
(``tests/test_seed_invariance.py``) and noted that Pitschke's c, which shares
the literal, is not.  This is that remaining measurement: the same five
patterns, each under its acceptance protocol with a ``RoughnessPitschke``
block declared and the shipped roughness stage appended last (no closing
stage, as that test runs), in two arms:

  seeded   the shipped stage: c lifted from 0 to 0.3 (τ starts at its 0.05)
  zero     the same stage with ``seed=0.0``: c starts on its floor

Families: ``fap`` (the GSAS-II tutorial's fluorapatite, GSAS protocol),
``lab6`` (NIST SRM 660c, the NIST protocol), and the CPD round robin's pure
``corundum``, ``fluorite`` and ``zincite`` under ``qpa_plan()``.  Dispersion is
declined on FAP, as the test does; the others keep their protocol's setting.

Per arm: c and τ (value, esd), every Biso and scale with esds, χ², what the
stage seeded, and every code (``ROUGHNESS_OUTSIDE_REGIME`` among them).

usage (repo root): python docs/wp/2018-measure/roughness_seed.py [family:arm ...]
"""
from __future__ import annotations

import dataclasses
import os
import sys

from common import OUT, diagnostics, emit, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from rietx.schemas.instrument import RoughnessPitschke  # noqa: E402
from rietx.strategy.staged import _ROUGHNESS_STAGE  # noqa: E402

FAMILIES = ("fap", "lab6", "corundum", "fluorite", "zincite")
ARMS = tuple(f"{f}:{a}" for f in FAMILIES for a in ("seeded", "zero"))
C = "instrument.geometry.surface_roughness.c"
TAU = "instrument.geometry.surface_roughness.tau"


def _inputs(family: str):
    if family == "fap":
        from tests.test_acceptance_fap import _gsas_protocol_plan, build_fap_inputs
        data, structure, ins = build_fap_inputs()
        ins.source.dispersion = None
        return data, structure, ins, _gsas_protocol_plan()
    if family == "lab6":
        from tests.test_acceptance_srm660c import _nist_calibrated_plan, build_srm_inputs
        data, structure, ins = build_srm_inputs()
        return data, structure, ins, _nist_calibrated_plan()
    from tests import test_acceptance_qpa_roundrobin as rr
    phase = {"corundum": rr.corundum_phase, "fluorite": rr.fluorite_phase,
             "zincite": rr.zincite_phase}[family]()
    data = rx.read_pattern(rr.DATA / f"{family}.prn")
    structure = rx.Structure(phases=[phase])
    ins = rr.qarr_instrument()
    rr.seed_scales(structure, ins, data)
    return data, structure, ins, rr.qpa_plan()


def fit(arm: str):
    family, how = arm.split(":")
    data, structure, ins, plan = _inputs(family)
    ins.geometry.surface_roughness = RoughnessPitschke()
    stage = _ROUGHNESS_STAGE[0]
    if how == "zero":
        stage = dataclasses.replace(stage, seed=0.0)
    plan.stages.append(stage)
    plan.closing_window_tol = None
    ref = rx.Refinement(structure, ins, history=False)
    return ref.fit(data, plan=plan, telemetry=False)


def main(arms):
    emit({"provenance": provenance(), "roughness_seed": _ROUGHNESS_STAGE[0].seed})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            result = fit(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        st = result.statistics
        last = result.stages[-1]
        emit({"arm": arm, "rwp": st.rwp, "chi2": st.chi2, "status": result.status,
              "last_stage": {"name": last.name, "status": last.status,
                             "n_iterations": last.n_iterations,
                             "seeded": dict(last.seeded or {})},
              "params": {p.path: [p.value, p.stderr, p.stderr_uncorrected, p.at_bound]
                         for p in result.parameters
                         if p.path.endswith((".biso", ".scale")) or p.path in (C, TAU)},
              "diagnostics": diagnostics(result)})
        result.plot(path=str(OUT / f"c20_{arm.replace(':', '_')}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

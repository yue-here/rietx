"""C14 on the 11-BM NAC protocol (WP-2018, task 3).

``least_squares.gaussian_width_inequalities`` holds Γ_G² ≥ ε (ε =
``caglioti._MIN_GAMMA_G2``) at every reflection under LM, while
``staged._exact_active_bounds``, which ``bound_findings`` reads, sees box sides
only.  The question: on NAC, does the answer sit on a row, and is a width held
there reported?  The fit is ``tests/test_acceptance_nac.py``'s (Le Bail pass,
then two-phase Rietveld under ``mccusker_default`` + biso, intermediate ftol
1e-6, closing window 1e-3), in three arms:

  shipped   LM with the rows, as main runs it
  no_rows   LM with ``gaussian_width_inequalities`` patched to build no row
  trf       ``solver="trf"``, which never builds the rows

The positive arm, ``syn_*`` (the same three): NAC has no reflection near the
floor, so a synthetic LaB₆ pattern is drawn whose true Γ_G² = u·(tanθ − t₀)²
touches 0 at t₀ = 0.1 (2θ ≈ 11.4°) with W interior (``tests/
test_gaussian_width_floor.py``'s construction and plan, with this truth).  A
fit there wants Γ_G² ≤ ε near t₀ with no box side reached.

Per arm: Rwp, U, V, W, X, Y and each phase's gauss_* with esd and at_bound,
the smallest Γ_G²/ε over each phase's reflections in the fitted range at the
answer, and every BOUND_HIT / FLOOR_HIT / RESOLUTION_NOT_POSITIVE.

usage (repo root): python docs/wp/2018-measure/gaussian_rows.py [arm ...]
"""
from __future__ import annotations

import importlib
import math
import sys

from common import OUT, emit, patched, provenance, record

import rietx as rx
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2
from tests.test_acceptance_nac import LIMITS, _caf2_phase, build_nac_inputs

lsq = importlib.import_module("rietx.optimize.least_squares")

ARMS = ("shipped", "no_rows", "trf", "syn_shipped", "syn_no_rows", "syn_trf")
#: true Γ_G² = U0·(tanθ − T0)²: zero at T0, positive elsewhere
U0, T0 = 9e-4, 0.1
SYN_TRUE = {"u": U0, "v": -2.0 * U0 * T0, "w": U0 * T0 * T0, "x": 2e-3}
INSTRUMENT = [f"instrument.profile.{k}" for k in "uvwxy"]


def synthetic():
    """(pattern, fresh structure, fresh instrument) for the touching truth."""
    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.common import Parameter
    from rietx.schemas.instrument import BackgroundChebyshev
    from tests.test_gaussian_width_floor import _models

    structure, ins = _models(true=True)
    for name, value in SYN_TRUE.items():
        getattr(ins.profile, name).value = value
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=40.0)])
    tt = np.arange(3.0, 24.0, 0.005)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist()), *_models(true=False)


def fit(arm: str):
    if arm.startswith("syn_"):
        from tests.test_gaussian_width_floor import PLAN as SYN_PLAN
        data, structure, ins = synthetic()
        solver = "trf" if arm == "syn_trf" else "lm"
        ref = rx.Refinement(structure, ins, solver=solver, history=False)
        return ref, ref.fit(data, plan=SYN_PLAN, telemetry=False)
    data, structure, instrument = build_nac_inputs()
    solver = {"solver": "trf"} if arm == "trf" else {}
    ref_lb = rx.Refinement(structure, instrument, **solver)
    ref_lb.fit(data, mode="lebail", two_theta_limits=LIMITS, telemetry=False)
    structure2 = ref_lb.fitted_structure.model_copy(deep=True)
    instrument2 = ref_lb.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(_caf2_phase())
    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3
    ref = rx.Refinement(structure2, instrument2, **solver)
    return ref, ref.fit(data, plan=plan, two_theta_limits=LIMITS, telemetry=False)


def min_gamma_g2(ref, result):
    """min over each phase's ticks in range of Γ_G²/ε, at the committed values."""
    ins, out = ref.instrument.profile, {}
    u, v, w = ins.u.value, ins.v.value, ins.w.value
    for ip, phase in enumerate(ref.structure.phases):
        gs = phase.gauss_strain.value if phase.gauss_strain is not None else 0.0
        gz = phase.gauss_size.value if phase.gauss_size is not None else 0.0
        lo, hi = min(result.two_theta), max(result.two_theta)
        ticks = [t for t in result.ticks.get(phase.name, []) if lo <= t <= hi]
        vals = []
        for tt in ticks:
            th = math.radians(0.5 * tt)
            t = math.tan(th)
            vals.append(((u + gs) * t * t + v * t + w + gz / math.cos(th) ** 2, tt))
        if vals:
            g2, tt = min(vals)
            out[phase.name] = {"min_ratio": g2 / _MIN_GAMMA_G2, "at_2theta": tt,
                               "n_ticks": len(vals),
                               "n_within_1pct": sum(1 for g, _ in vals
                                                    if g <= 1.01 * _MIN_GAMMA_G2),
                               "n_under_eps": sum(1 for g, _ in vals
                                                  if g < _MIN_GAMMA_G2 * (1 - 1e-9))}
    return out


def main(arms):
    emit({"provenance": provenance(), "fixture": "11-BM NAC", "eps": _MIN_GAMMA_G2})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        paths = INSTRUMENT + [f"phases.{i}.{t}" for i in (0, 1)
                              for t in ("gauss_strain", "gauss_size")]
        if arm in ("no_rows", "syn_no_rows"):
            with patched(lsq, "gaussian_width_inequalities", lambda *a, **k: []):
                ref, result = fit(arm)
        else:
            ref, result = fit(arm)
        rec = record(result, paths)
        rec["arm"] = arm
        rec["committed"] = {"u": ref.instrument.profile.u.value,
                            "v": ref.instrument.profile.v.value,
                            "w": ref.instrument.profile.w.value}
        rec["min_gamma_g2"] = min_gamma_g2(ref, result)
        rec["cell_a"] = [p.cell.a.value for p in ref.structure.phases]
        rec["cell_a_esd"] = [result.parameter(f"phases.{i}.cell.a").stderr
                             if f"phases.{i}.cell.a" in {p.path for p in result.parameters}
                             else None for i in range(len(ref.structure.phases))]
        rec["truncations"] = {s.name: [s.n_constraint_truncations,
                                       dict(getattr(s, "truncated_by", None) or {})]
                              for s in result.stages}
        emit(rec)
        stem = "c14_synthetic" if arm.startswith("syn_") else "c14_nac"
        result.plot(path=str(OUT / f"{stem}_{arm}.png"))


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

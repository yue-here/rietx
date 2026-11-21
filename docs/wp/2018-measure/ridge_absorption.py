"""C4, the scale-B ridge hold against capillary absorption (WP-2018, task 3).

``refine._hold_scale_b_ridges`` holds a phase's displacement columns where its
scale and B cannot be told apart (WP-1534); capillary absorption,
``A = K(µR)·exp(c(µR)·sin²θ)``, multiplies every phase component and is an
exact reparameterisation of {scale, B}, its whole content ΔB = c(µR)·λ²/2
(``model/absorption.py``).  The probe reads a component that already carries A,
and the hold freezes the column A's shift lands on.  Two datasets.

**ridge** — ``tests/test_scale_b_ridge.py``'s four phases (corundum, zincite,
fluorite, bcc Fe with one reflection in 25-50°), its noise seed and its
``cell_then_B`` staging, moved to a capillary: the ``debye_scherrer`` preset at
Cu Kα1 (one line) with the Bragg-Brentano preset's profile, and the pattern
drawn **with** µR = 1.0.  Arms (``<declared>_<hold>``):

  mu_hold      µR = 1.0 declared, the hold as shipped
  mu_nohold    µR = 1.0 declared, ``_hold_scale_b_ridges`` holding nothing
               (the positive arm: Fe's B is free to walk)
  nomu_hold    µR left undeclared (0), the hold as shipped
  nomu_nohold  µR undeclared, no hold

**lab6** — 11-BM SRM 660a with ``tests/test_acceptance_capillary.py``'s
protocol (dispersion off, estimated µR), the dataset whose ΔB the hold must not
undo.  Arms: ``plain`` (no capillary) and ``corrected`` (capillary), each with
the hold as shipped, and ``corrected_forced``, the positive arm:
``SCALE_B_SEPARATION_FLOOR`` raised to 2 so the hold takes LaB₆'s B in every
stage that frees it, which is what ΔB would read if the hold ever fired here.

Every arm also records what the probe measured, every time the runner asked it
(``_scale_b_probe``'s separation per phase), so the distance from the floor is
read with and without A in the component.

usage (repo root): python docs/wp/2018-measure/ridge_absorption.py [arm ...]
"""
from __future__ import annotations

import importlib
import sys

import numpy as np
from common import OUT, emit, patched, provenance, record

import rietx as rx
from rietx import PatternData
from rietx.model.absorption import equivalent_delta_biso
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.strategy.staged import RefinementPlan

refine_module = importlib.import_module("rietx.refine")

RIDGE_ARMS = ("mu_hold", "mu_nohold", "nomu_hold", "nomu_nohold")
LAB6_ARMS = ("plain", "corrected", "corrected_forced")
MU_R = 1.0
FE = 3


def _capillary(structure_instrument, mu_r):
    """The ridge fixture's models with the instrument moved to a capillary."""
    structure, bb = structure_instrument
    ins = rx.Instrument.debye_scherrer(
        wavelength=bb.source.lines[0].wavelength.value, mu_r=mu_r)
    ins.profile = bb.profile.model_copy(deep=True)
    ins.source.dispersion = bb.source.dispersion
    ins.background = bb.background.model_copy(deep=True)
    return structure, ins


def _ridge_pattern():
    from tests.test_scale_b_ridge import TRUE_SCALES, TT, _models
    structure, ins = _capillary(_models(TRUE_SCALES, unbounded=False), MU_R)
    blank = PatternData(two_theta=TT.tolist(), intensity=np.zeros_like(TT).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


def _spy(hold: bool):
    """``_hold_scale_b_ridges`` that records the probe, then holds or not."""
    real = refine_module._hold_scale_b_ridges
    calls = []

    def hold_ridges(model, table, phases=None):
        sep = refine_module._scale_b_probe(model, table, phases)[0]
        calls.append({str(k): v for k, v in sep.items()})
        return real(model, table, phases) if hold else ([], {}, {})

    hold_ridges.calls = calls
    return hold_ridges


def _bisos(structure):
    return [[a.biso.value for a in p.atoms] for p in structure.phases]


def ridge(arm):
    from tests.test_scale_b_ridge import ORDERS, START_SCALES, _models
    declared, hold = arm.split("_")
    mu = MU_R if declared == "mu" else None
    structure, ins = _capillary(_models(START_SCALES, unbounded=True), mu)
    ref = rx.Refinement(structure, ins, history=False)
    spy = _spy(hold == "hold")
    with patched(refine_module, "_hold_scale_b_ridges", spy):
        result = ref.fit(_ridge_pattern(),
                         plan=RefinementPlan(stages=ORDERS["cell_then_B"]),
                         telemetry=False)
    paths = [f"phases.{i}.scale" for i in range(4)] + [
        "phases.0.atoms.0.biso", "phases.1.atoms.0.biso",
        "phases.2.atoms.0.biso", "phases.2.atoms.1.biso", f"phases.{FE}.atoms.0.biso"]
    rec = record(result, paths)
    rec["probe"] = spy.calls
    rec["scale_b_held"] = [{str(k): v for k, v in (s.scale_b_held or {}).items()}
                           for s in result.stages]
    rec["biso"] = _bisos(ref.fitted_structure)
    rec["wt_frac"] = {q.name: q.weight_fraction for q in result.qpa.phases}
    rec["predicted_dB"] = equivalent_delta_biso(MU_R, ins.source.lines[0].wavelength.value)
    rec["absorption_dB"] = (result.absorption.equivalent_delta_biso
                            if result.absorption is not None else None)
    return result, rec


def lab6(arm):
    from tests import test_acceptance_capillary as cap
    ref = rx.Refinement(cap._structure(),
                        cap._instrument(capillary=arm != "plain", dispersion=False),
                        history=False)
    data = rx.read_pattern(cap.DATA / "11BM_LaB6_660a.fxye")
    spy = _spy(True)
    floor = 2.0 if arm == "corrected_forced" else refine_module.SCALE_B_SEPARATION_FLOOR
    with patched(refine_module, "_hold_scale_b_ridges", spy), \
            patched(refine_module, "SCALE_B_SEPARATION_FLOOR", floor):
        result = ref.fit(data, plan=cap._plan(), two_theta_limits=cap.LIMITS,
                         telemetry=False)
    paths = ["phases.0.scale", "phases.0.cell.a", "phases.0.atoms.0.biso",
             "phases.0.atoms.1.biso"]
    rec = record(result, paths)
    rec["probe"] = spy.calls
    rec["scale_b_held"] = [{str(k): v for k, v in (s.scale_b_held or {}).items()}
                           for s in result.stages]
    rec["biso"] = _bisos(ref.fitted_structure)
    rec["absorption_dB"] = (result.absorption.equivalent_delta_biso
                            if result.absorption is not None else None)
    rec["mu_r"] = result.absorption.mu_r if result.absorption is not None else None
    return result, rec


def main(arms):
    emit({"provenance": provenance(), "mu_r_ridge": MU_R,
          "floor": refine_module.SCALE_B_SEPARATION_FLOOR})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            result, rec = (ridge if arm in RIDGE_ARMS else lab6)(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rec["arm"] = arm
        emit(rec)
        result.plot(path=str(OUT / f"c4_{arm}.png"))


if __name__ == "__main__":
    main(sys.argv[1:] or RIDGE_ARMS)

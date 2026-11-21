"""C7, the moment hold and turn against the stationary-angle test (WP-2018, task 3).

``refine._hold_flat_moments`` holds a moment direction the pattern does not
respond to, and on a site whose flat direction is a combination of the polar
angle and the azimuth (#599) turns the moment onto the flat meridian and holds
the azimuth alone, leaving the turned polar angle free.  The solver's
``least_squares.stationary_angle_test`` (WP-1929) then asks of every free
angle whether it sits where the symmetry makes its column vanish, and leaves
the ones that do out of the covariance.  Four arms:

  shipped   main as it stands
  no_hold   ``refine._flat_moment_scan`` answering nothing: no hold at stage
            start, no release, no collapse of a moment direction, no turn
  no_turn   ``refine._turn_onto_meridians`` turning nothing: the azimuth is
            held where the stage found it (#599's trap)
  no_test   ``least_squares.stationary_angle_test`` answering nothing: every
            angle stays a column of the covariance

Datasets (``<dataset>:<arm>``):

  cr2wo6    HB-2A Cr₂WO₆ at 4 K, ``tests/test_acceptance_magnetic.py``'s
            protocol (nuclear 150 K then 4 K, then the moment seeded along a)
  lamno3    BT-1 LaMnO₃ at 50 K under Pn′ma′, ``…_lamno3.py``'s protocol (its
            plan frees the modulus and the polar angle only)
  rh        ``tests/test_magnetic.py``'s #599 fixture: one Mn on rhombohedral
            axes (uniaxial about [111]), truth (1.5, 2, 3), start (3, 0.2, 0.2)
  rh111     the same with the truth on the unique axis, (2, 2, 2): the turned
            polar angle then ends on a direction the pattern is even about,
            which is the stationary-angle test's case (the positive arm)
  rhn, rh111n
            the two above with Poisson noise (seed 3) on the fixture's
            pattern plus its background of 20, so the test's statistic, which
            divides by χ²_red, is not read at roundoff

Every arm records the moment rows (value, esd, interval), what each stage held,
released, collapsed and turned, each stage's ``moment_angle_tests``, the
report's magnetic row and the codes.

usage (repo root): python docs/wp/2018-measure/moment_hold.py [dataset:arm ...]
"""
from __future__ import annotations

import importlib
import os
import sys
from functools import cache

import numpy as np
from common import OUT, diagnostics, emit, patched, provenance

# the fixtures' own fits (``tests/test_magnetic._fit``, the acceptance
# ``_fit``s) record a run unless told not to, as the suite's conftest tells them
os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402

refine_module = importlib.import_module("rietx.refine")
lsq_module = importlib.import_module("rietx.optimize.least_squares")

ARMS = ("shipped", "no_hold", "no_turn", "no_test")
DATASETS = ("rh", "rh111", "rhn", "rh111n", "lamno3", "cr2wo6")


def _arm(arm):
    if arm == "no_hold":
        return patched(refine_module, "_flat_moment_scan", lambda *a, **k: ([], {}))
    if arm == "no_turn":
        return patched(refine_module, "_turn_onto_meridians", lambda *a, **k: {})
    if arm == "no_test":
        return patched(lsq_module, "stationary_angle_test", lambda *a, **k: (None, []))
    assert arm == "shipped", arm
    return patched(refine_module, "_flat_moment_scan", refine_module._flat_moment_scan)


@cache
def _cr2wo6_nuclear():
    from tests.test_acceptance_magnetic import (
        DATA,
        NUCLEAR_STAGES,
        _fit,
        _instrument,
        _trirutile,
    )
    d4 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_4K.dat")
    d150 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_150K.dat")
    ref150, _ = _fit(_trirutile(), _instrument(), d150, NUCLEAR_STAGES,
                     closing_window_tol=None)
    ref4, _ = _fit(ref150.structure.model_copy(deep=True),
                   ref150.instrument.model_copy(deep=True), d4, NUCLEAR_STAGES,
                   closing_window_tol=None)
    return d4, ref4


@cache
def _lamno3_nuclear():
    from rietx.crystallography.cif import structure_from_cif
    from tests.test_acceptance_magnetic_lamno3 import (
        CONTAMINANT,
        DATA,
        NUCLEAR_STAGES,
        _fit,
        _instrument,
    )
    data = rx.read_pattern(DATA / "gsas2_bt1_lamno3_50K.gsas")
    data = data.model_copy(update={"excluded_regions": [CONTAMINANT]})
    ref, _ = _fit(structure_from_cif(DATA / "gsas2_bt1_lamno3.cif"),
                  _instrument(), data, NUCLEAR_STAGES)
    return data, ref


def _fit(dataset):
    if dataset == "cr2wo6":
        from tests.test_acceptance_magnetic import MAGNETIC_STAGES, _fit, _with_moment
        d4, ref4 = _cr2wo6_nuclear()
        return _fit(_with_moment(ref4.structure, (2.0, 0.0, 0.0)),
                    ref4.instrument.model_copy(deep=True), d4, MAGNETIC_STAGES)
    if dataset == "lamno3":
        from tests.test_acceptance_magnetic_lamno3 import (
            MAGNETIC_STAGES,
            PN_MA,
            _fit,
            _with_moment,
        )
        data, ref = _lamno3_nuclear()
        return _fit(_with_moment(ref.structure, PN_MA),
                    ref.instrument.model_copy(deep=True), data, MAGNETIC_STAGES)
    from tests.test_magnetic import _fit, _rhombohedral
    truth = (1.5, 2.0, 3.0) if dataset in ("rh", "rhn") else (2.0, 2.0, 2.0)
    if not dataset.endswith("n"):
        return _fit(_rhombohedral(truth), _rhombohedral((3.0, 0.2, 0.2)))
    return _noisy_fit(_rhombohedral(truth), _rhombohedral((3.0, 0.2, 0.2)))


def _noisy_fit(truth_phase, start_phase, background=20.0):
    """``tests/test_magnetic._fit`` with Poisson noise on its pattern."""
    from rietx.optimize.least_squares import DEFAULT_SOLVER
    from tests.test_magnetic import LAMBDA_CW, _compiled, _grid
    model, _t, values, *_ = _compiled(truth_phase)
    y = np.asarray(model.evaluate(values), dtype=np.float64) + background
    y = np.random.default_rng(3).poisson(y).astype(float)
    ref = rx.Refinement(rx.Structure(phases=[start_phase]),
                        rx.Instrument.constant_wavelength_neutron(LAMBDA_CW),
                        solver=DEFAULT_SOLVER, history=False)
    data = rx.PatternData(two_theta=_grid().tolist(), intensity=y.tolist())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"]),
    ]))
    return ref, result


def _angle_to_111(moment):
    from rietx.crystallography.magnetic.operators import moment_to_cartesian
    six = (4.0, 4.0, 4.0, 70.0, 70.0, 70.0)
    m = moment_to_cartesian(np.asarray(moment, dtype=np.float64), six)
    u = moment_to_cartesian(np.ones(3), six)
    return float(np.degrees(np.arccos(min(1.0, abs(m @ u) / np.linalg.norm(m)
                                          / np.linalg.norm(u)))))


def measure(spec):
    dataset, arm = spec.split(":")
    with _arm(arm):
        ref, result = _fit(dataset)
    moment_rows = {p.path: (p.value, p.stderr, p.at_bound,
                            None if p.interval is None else p.interval.model_dump())
                   for p in result.parameters if ".moment." in p.path}
    held_values = {r.path: r.value for r in ref.parameters()
                   if ".moment." in r.path}
    stages = [{
        "stage": s.name, "rwp": s.rwp, "status": s.status,
        "held": [p for p in s.held if ".moment." in p],
        "released": [p for p in s.released if ".moment." in p],
        "collapsed": [p for p in (s.collapsed or []) if ".moment." in p],
        "flat_axes": s.moment_flat_axes, "turned": s.moment_turned,
        "angle_tests": [t.model_dump() for t in (s.moment_angle_tests or [])],
    } for s in result.stages]
    report = ref.report().magnetic
    rows = [{k: getattr(r, k, None) for k in (
        "label", "magnitude", "magnitude_esd", "crystalaxis", "supported",
        "unmeasured_directions", "note")} for r in report]
    rec = {"spec": spec, "rwp": result.statistics.rwp, "status": result.status,
           "chi2": result.statistics.chi2, "moment_rows": moment_rows,
           "moment_values": held_values, "stages": stages, "report": rows,
           "diagnostics": diagnostics(result)}
    if dataset.startswith("rh"):
        rec["angle_to_111"] = _angle_to_111(
            ref.fitted_structure.phases[0].atoms[0].moment.values())
    return result, rec


def main(specs):
    emit({"provenance": provenance()})
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        try:
            result, rec = measure(spec)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"spec": spec, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        emit(rec)
        result.plot(path=str(OUT / f"c7_{spec.replace(':', '_')}.png"))


if __name__ == "__main__":
    main(sys.argv[1:] or [f"{d}:{a}" for d in DATASETS for a in ARMS])

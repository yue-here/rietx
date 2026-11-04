"""WP-2081: what each route frees on the frames after the first, and what it does.

Run from the repository root:

    .venv/bin/python docs/wp/2081-batch/measure_routes.py

Two measurements, written to ``routes.json`` beside this file.

**Free sets.** For each preset, what the collapsed warm plan frees on a later
frame, read off a real ``ParameterTable`` for a LaB6 model on three instruments
(Bragg-Brentano, capillary with a goniometer radius, capillary without one).

**Routes.** The seven-pattern thermal LaB6 ramp of ``tests/test_sequential.py``
(capillary geometry, single wavelength, true zero shift 0.008 deg, true W and
background constant across frames, cell expands by 0.05 % a step). This ramp is
synthetic and its instrument is constant by construction, so it can show what
each route does and cannot show which route is right on real data.

- ``default``: ``refine_sequential(plan="mccusker_default")``.
- ``calibrate_then_cautious``: fit frame 0 alone under ``mccusker_default``,
  pass the refined models in as the series' start, and run a custom plan
  freeing the scale, the background and the cell.
- ``calibrate_then_sample``: the same calibration, then ``lab_sample_refine``.
- ``two_pass``: ``calibrate_then_cautious``, then a second ``fit`` freeing Biso
  as well, each frame starting from its own first-pass answer through
  ``prepare``. Nothing else in the surface says "pass 2 of a series".
- ``two_pass_forced``: the same second pass with frame 2's warm rungs forced to
  raise, to see what the cold rung starts from.
- ``joint_calibration``: one ``refine_multi`` over frames 0 and 6 with the zero
  shift and profile shared and a cell per frame, the nearest spelling of
  calibrating across chosen frames.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402
from rietx.sequential import (  # noqa: E402
    SequentialRefinement,
    _collapse,
    _PatternRaised,
)
from rietx.strategy.staged import PLAN_PRESETS, resolve_plan  # noqa: E402
from tests.test_schemas import make_lab6  # noqa: E402
from tests.test_sequential import (  # noqa: E402
    A0,
    RAMP,
    TEMPERATURES,
    _simulate,
    _start_models,
)

FORCED = 2
ZERO = "instrument.zero_shift"
SETUP = ("instrument.zero_shift", "instrument.geometry.", "instrument.profile.",
         "instrument.source.")
CAUTIOUS = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("cell", ["phases.*.cell.*"]),
])
RELEASE = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("cell", ["phases.*.cell.*"]),
    rx.Stage("biso", ["phases.*.atoms.*.biso"]),
])

_original_fit_one = SequentialRefinement._fit_one


def _forcing(self, data, label, previous, *args, **kwargs):
    """Raise on frame FORCED's warm rungs, so the ladder reaches the cold one."""
    index = args[8]  # _fit_one's positional ``index``
    if index == FORCED and previous is not None:
        raise _PatternRaised(RuntimeError("forced to the cold rung (WP-2081)"))
    return _original_fit_one(self, data, label, previous, *args, **kwargs)


def kind(path: str) -> str:
    if path.startswith("instrument.background."):
        return "background"
    if path.startswith(SETUP):
        return "setup"
    return "sample"


def free_sets() -> list[dict]:
    instruments = {
        "bragg_brentano": rx.Instrument.bragg_brentano(radiation="CuKa"),
        "capillary_with_radius": rx.Instrument.debye_scherrer(
            wavelength=0.45, goniometer_radius_mm=1000.0),
        "capillary_no_radius": rx.Instrument.debye_scherrer(wavelength=0.45),
    }
    rows = []
    for preset in sorted(PLAN_PRESETS):
        mode = "pawley" if preset == "pawley_default" else "rietveld"
        turn_on = _collapse(resolve_plan(preset, mode)).stages[0].turn_on
        for name, ins in instruments.items():
            table = ParameterTable(make_lab6(), ins.model_copy(deep=True))
            table.set_vary(["*"], False)
            table.set_vary(list(turn_on), True)
            split: dict[str, list[str]] = {
                "setup": [], "background": [], "sample": []}
            for path in table.free_paths:
                split[kind(path)].append(path)
            rows.append({"preset": preset, "instrument": name, **split})
    return rows


def frame_rows(arm: str, series: SequentialRefinement, result) -> list[dict]:
    rows = []
    for k, entry in enumerate(result.entries):
        ins = series.fitted_instruments[k]
        st = series.fitted_structures[k]
        a_true = A0 * (1.0 + RAMP * k)
        fit = series.results_[k]
        free = [p.path for p in fit.parameters]
        a_esd = next((p.stderr for p in fit.parameters
                      if p.path == "phases.0.cell.a"), None)
        rows.append({
            "arm": arm, "frame": k, "rung": entry.rung,
            "evaluations": entry.n_iterations,
            "n_setup_free": sum(kind(p) == "setup" for p in free),
            "n_free": len(free),
            "zero_shift": ins.zero_shift.value,
            "w": ins.profile.w.value,
            "biso": st.phases[0].atoms[0].biso.value,
            "cell_a_ppm": 1e6 * (st.phases[0].cell.a.value - a_true) / a_true,
            "cell_a_esd_ppm": None if a_esd is None else 1e6 * a_esd / a_true,
            "gof": entry.statistics.gof if entry.statistics else None,
        })
    return rows


def calibrated(pattern) -> tuple:
    structure, instrument = _start_models()
    ref = rx.Refinement(structure, instrument)
    ref.fit(pattern, plan="mccusker_default")
    return ref.fitted_structure, ref.fitted_instrument


def routes(patterns) -> list[dict]:
    rows: list[dict] = []
    x = TEMPERATURES

    structure, instrument = _start_models()
    series = SequentialRefinement(structure, instrument)
    rows += frame_rows("default", series, series.fit(
        patterns, x=x, plan="mccusker_default"))

    structure, instrument = calibrated(patterns[0])
    first = SequentialRefinement(structure, instrument)
    rows += frame_rows("calibrate_then_cautious", first, first.fit(
        patterns, x=x, plan=CAUTIOUS))

    sample = SequentialRefinement(structure, instrument)
    rows += frame_rows("calibrate_then_sample", sample, sample.fit(
        patterns, x=x, plan="lab_sample_refine"))

    pass1_structures = list(first.fitted_structures)
    pass1_instruments = list(first.fitted_instruments)

    def from_pass_one(index, data, structure, instrument):
        """Start this frame from its own first-pass answer."""
        for path, target in (("cell.a", structure.phases[0].cell.a),
                             ("cell.b", structure.phases[0].cell.b),
                             ("cell.c", structure.phases[0].cell.c)):
            source = pass1_structures[index].phases[0].cell
            target.value = getattr(source, path.split(".")[1]).value
        structure.phases[0].scale.value = (
            pass1_structures[index].phases[0].scale.value)
        instrument.background = pass1_instruments[index].background.model_copy(
            deep=True)

    second = SequentialRefinement(structure, instrument)
    rows += frame_rows("two_pass", second, second.fit(
        patterns, x=x, plan=RELEASE, prepare=from_pass_one))

    SequentialRefinement._fit_one = _forcing
    try:
        forced = SequentialRefinement(structure, instrument)
        rows += frame_rows("two_pass_forced", forced, forced.fit(
            patterns, x=x, plan=RELEASE, prepare=from_pass_one))
    finally:
        SequentialRefinement._fit_one = _original_fit_one
    return rows


def joint_calibration(patterns) -> dict:
    """One fit over frames 0 and 6: zero and profile shared, each its own cell."""
    structure, instrument = _start_models()
    last = structure.model_copy(deep=True)
    for name in "abc":
        getattr(last.phases[0].cell, name).value = A0 * (1 + RAMP * 6) * 1.0002
    sharing = rx.SharingMap(per_histogram=["phases.*.cell.*"],
                            shared=["instrument.profile.*", ZERO])
    fit = rx.refine_multi([patterns[0], patterns[6]], [structure, last],
                          [instrument.model_copy(deep=True) for _ in range(2)],
                          plan="mccusker_default", sharing=sharing)
    row = next(p for p in fit.parameters if p.path == ZERO)
    return {"status": fit.status, "zero_shift": row.value, "zero_esd": row.stderr}


def spread(rows: list[dict], arm: str, field: str) -> float:
    values = [r[field] for r in rows if r["arm"] == arm]
    return float(np.ptp(values))


def main() -> None:
    t0 = time.time()
    patterns = [_simulate(A0 * (1.0 + RAMP * k), seed=11 + k)
                for k in range(len(TEMPERATURES))]
    sets = free_sets()
    rows = routes(patterns)
    joint = joint_calibration(patterns)
    out = {
        "platform": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "rietx": rx.__version__,
        "venv": "worktree .venv, [dev]",
        "free_sets": sets,
        "rows": rows,
        "joint_calibration": joint,
    }
    print("free set on a later frame (setup/background/sample paths)")
    for r in sets:
        print(f"  {r['preset']:20s} {r['instrument']:22s} "
              f"{len(r['setup']):2d} {len(r['background']):2d} "
              f"{len(r['sample']):2d}  {' '.join(r['setup'])}")
    print(f"{'arm':24s} {'fr':>2s} {'rung':>11s} {'eval':>4s} {'setup':>5s} "
          f"{'free':>4s} {'zero':>9s} {'W':>9s} {'Biso':>6s} {'a ppm':>7s} "
          f"{'esd ppm':>7s} {'GoF':>6s}")
    for r in rows:
        esd = -1.0 if r["cell_a_esd_ppm"] is None else r["cell_a_esd_ppm"]
        print(f"{r['arm']:24s} {r['frame']:2d} {r['rung']:>11s} "
              f"{r['evaluations']:4d} {r['n_setup_free']:5d} {r['n_free']:4d} "
              f"{r['zero_shift']:9.5f} {r['w']:9.3e} {r['biso']:6.3f} "
              f"{r['cell_a_ppm']:7.2f} {esd:7.2f} {r['gof']:6.3f}")
    for arm in dict.fromkeys(r["arm"] for r in rows):
        err = [r["cell_a_ppm"] for r in rows if r["arm"] == arm]
        esd = [r["cell_a_esd_ppm"] for r in rows if r["arm"] == arm]
        evals = sum(r["evaluations"] for r in rows if r["arm"] == arm)
        print(f"{arm}: zero spread {spread(rows, arm, 'zero_shift'):.2e} deg, "
              f"W spread {spread(rows, arm, 'w'):.2e}; cell error mean "
              f"{np.mean(err):.2f} ppm, sd {np.std(err, ddof=1):.2f} ppm, "
              f"mean esd {np.mean(esd):.2f} ppm; {evals} evaluations")
    print(f"joint fit over frames 0 and 6: zero {joint['zero_shift']:.6f}"
          f" +/- {joint['zero_esd']:.2e} deg, {joint['status']}")
    out["seconds"] = round(time.time() - t0, 1)
    print(f"{out['platform']}, Python {out['python']}, rietx {out['rietx']}, "
          f"{out['seconds']} s")
    Path(__file__).with_name("routes.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

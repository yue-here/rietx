"""C33: positions that move inside a stage whose reflection list and windows are frozen (WP-2018, task 3).

At each stage's compile the reflection list is enumerated ``REFLECTION_MARGIN_DEG``
(0.5°) past the fitted range at the zero and geometric shift the stage starts
from, and every peak's window is sized at the positions of that moment
(``WINDOW_MIN_DEG``, ``window_slack_deg``); Pawley's ``off_data`` flag reads
the same list.  The zero and the shifts have had no box since 2026-10-20, so a
stage can move them any distance against a list and windows that do not
follow (forward.py; ``rewindow`` resizes windows only).  The dataset is 11-BM
NAC (``tests/test_acceptance_nac.py``'s ``build_nac_inputs``) cold-fitted from
a cell 0.1 % short, Rietveld (``mccusker_default``, CaF₂ declared as that
suite does not; NAC alone) and Pawley (``pawley_default``), in arms
``<mode>_<zero start>``:

  <mode>_0      shipped: the zero starts at 0
  <mode>_0.1    the zero starts at +0.1°: one stage must move it a third of
                the narrowest window's width
  <mode>_<z>_repeat
                every declared stage run three times in a row, so the list and
                the windows are recompiled at two more points along each
                stage's path: the arm with less of the freeze
  <mode>_0.6    the positive arm: the zero starts at +0.6°, past the
                reflection margin, so a stage moves every peak further than
                the list and the windows were drawn for

Every solve is logged: the stage, and the zero and every free shift path
(``instrument.geometry.*`` whose name carries ``displacement``, ``offset`` or
``shift``) at its start and its answer.  Per arm: Rwp, the cell, the zero,
status, and every code (``FROZEN_COMPILE_STALE`` is the package's own reading
of a frozen compile that mattered).

usage (repo root): python docs/wp/2018-measure/frozen_positions.py [arm ...]
"""
from __future__ import annotations

import dataclasses
import importlib
import os
import sys

from common import diagnostics, emit, patched, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from tests.test_acceptance_nac import LIMITS, build_nac_inputs  # noqa: E402

refine_module = importlib.import_module("rietx.refine")

ARMS = tuple(f"{m}_{z}" for m in ("rietveld", "pawley")
             for z in ("0", "0.1", "0.6", "0_repeat", "0.1_repeat"))
SHORT = 0.999


def _positions(paths):
    return [p for p in paths if p == "instrument.zero_shift" or (
        p.startswith("instrument.geometry.")
        and any(w in p for w in ("displacement", "offset", "shift")))]


def _logging(real, log):
    def solve(model, table, **kwargs):
        free = list(table.free_paths)
        watch = _positions(free)
        before = table.decode(table.x0())
        outcome = real(model, table, **kwargs)
        after = table.decode(outcome.theta)
        log.append({"stage": kwargs.get("stage", ""),
                    "moved": {p: [before[p], after[p]] for p in watch}})
        return outcome
    return solve


def fit(arm, log):
    mode, zero, *repeat = arm.split("_")
    data, structure, instrument = build_nac_inputs()
    for ax in "abc":
        cell = structure.phases[0].cell
        getattr(cell, ax).value = SHORT * getattr(cell, ax).value
    instrument.zero_shift.value = float(zero)
    ref = rx.Refinement(structure, instrument, history=False)
    plan = (rx.RefinementPlan.pawley_default() if mode == "pawley"
            else rx.RefinementPlan.mccusker_default())
    if repeat:
        plan.stages = [dataclasses.replace(st, name=f"{st.name}{'' if i == 0 else i}")
                       for st in plan.stages for i in range(3)]
    with patched(refine_module, "run_least_squares",
                 _logging(refine_module.run_least_squares, log)):
        result = ref.fit(data, mode=mode, plan=plan, two_theta_limits=LIMITS,
                         telemetry=False)
    return ref, result


def main(arms):
    emit({"provenance": provenance(), "fixture": "11-BM NAC, cell 0.1 % short"})
    for arm in arms:
        log = []
        try:
            ref, result = fit(arm, log)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400], "solves": log})
            continue
        rows = {p.path: [p.value, p.stderr, p.at_bound] for p in result.parameters
                if p.path in ("phases.0.cell.a", "phases.0.cell.c", "instrument.zero_shift")
                or p.path in _positions([p.path])}
        emit({"arm": arm, "rwp": result.statistics.rwp, "status": result.status,
              "params": rows, "solves": log,
              "stages": [{"stage": s.name, "status": s.status, "rwp": s.rwp,
                          "held": list(s.held), "collapsed": list(s.collapsed or []),
                          "n_iterations": s.n_iterations} for s in result.stages],
              "diagnostics": diagnostics(result)})


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

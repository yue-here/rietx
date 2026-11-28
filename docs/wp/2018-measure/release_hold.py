"""C22: ``solve_magnetic``'s one-site release against the flat-moment hold (WP-2018, task 3).

A class with two or more magnetic sites is refined from the flat seed and from
one start per site: that site alone, then the others put back at
``SOLVE_RELEASE_FRACTION`` (0.05) of their seed (``strategy.magnetic._release``)
and refitted.  Every stage of that refit runs ``refine._hold_flat_moments``,
which can hold a moment angle the pattern does not move.  A one-site class has
one start and no release (``_starts`` returns before it), so the chosen
dataset, Cr₂WO₆ 4 K with its one Cr site, cannot exercise the pair; this runs
``tests/test_magnetic_solve.py``'s two-site Pnma fixture instead (Mn1 3.5 µB
and Mn2 0.7 µB along x, A-type, CW neutrons), in four arms:

  shipped        as on main
  no_hold        ``refine._flat_moment_scan`` holding nothing (the C7 arm)
  tiny           the positive arm: the release at 1e-4 of the seed instead of
                 0.05, where a released site starts nearly dead
  tiny_no_hold   both

Every trial fit ``_fit`` runs is recorded: which moments it started with, its
Rwp and status, what each stage held and released among the moment paths, and
the fitted moment values.  The solution's ranking per arm is recorded too.

usage (repo root): python docs/wp/2018-measure/release_hold.py [arm ...]
"""
from __future__ import annotations

import importlib
import os
import sys

from common import emit, patched, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from rietx.schemas.structure import MagneticSymmetry, Moment  # noqa: E402
from tests.test_magnetic_solve import (  # noqa: E402
    A_TYPE_BNS,
    MN_SITE,
    candidate_named,
    neutron,
    nuclear_fit,
    simulate,
    two_site,
)

refine_module = importlib.import_module("rietx.refine")
magnetic = importlib.import_module("rietx.strategy.magnetic")

ARMS = ("shipped", "no_hold", "tiny", "tiny_no_hold")


def _moments(structure):
    return {a.label: [round(v, 6) for v in a.moment.values()]
            for a in structure.phases[0].atoms if a.moment is not None}


def _recording(real, log):
    def fit(structure, instrument, data, plan, ties=None, limits=None, hold=()):
        ref, result = real(structure, instrument, data, plan, ties, limits, hold)
        log.append({
            "start_moments": _moments(structure),
            "rwp": result.statistics.rwp, "status": result.status,
            "stages": [{"stage": s.name,
                        "held": [p for p in s.held if ".moment." in p],
                        "released": [p for p in s.released if ".moment." in p],
                        "flat_axes": s.moment_flat_axes}
                       for s in result.stages],
            "fitted_moments": {p.path: [p.value, p.stderr] for p in result.parameters
                               if ".moment." in p.path},
        })
        return ref, result
    return fit


def run(arm, ref, data):
    log = []
    fraction = 1e-4 if arm.startswith("tiny") else magnetic.SOLVE_RELEASE_FRACTION
    scan = ((lambda *a, **k: ([], {})) if arm.endswith("no_hold")
            else refine_module._flat_moment_scan)
    with patched(magnetic, "_fit", _recording(magnetic._fit, log)), \
            patched(magnetic, "SOLVE_RELEASE_FRACTION", fraction), \
            patched(refine_module, "_flat_moment_scan", scan):
        solution = rx.solve_magnetic(ref, data, sites=["Mn1", "Mn2"], ion="Mn3+")
    return solution, log


def main(arms):
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    data = simulate(two_site(
        m1=Moment.from_values((3.5, 0.0, 0.0), "Mn3+"),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=list(ops), centerings=list(cent))),
        instrument)
    emit({"provenance": provenance(), "fixture": "test_magnetic_solve two_site",
          "truth": {"Mn1": [3.5, 0, 0], "Mn2": [0.7, 0, 0]}, "bns": A_TYPE_BNS})
    for arm in arms:
        ref = nuclear_fit(two_site(), data, instrument)
        try:
            solution, log = run(arm, ref, data)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        emit({"arm": arm, "verdict": solution.verdict,
              "trials": [{"bns": t.bns_number, "start": t.start,
                          "n_starts": t.n_starts, "n_minima": t.n_minima,
                          "rwp": t.rwp, "delta_bic": t.delta_bic}
                         for t in solution.trials],
              "fits": log})


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

"""C25: the size cap against ``SIZE_LAMBDA_POWER`` on a joint X-ray and neutron fit (WP-2018, task 3).

A phase's ``lor_size`` and ``gauss_size`` are one shared column in a joint fit,
which histogram h reads scaled by (λ_h/λ_0)^p (``params.multi.SIZE_LAMBDA_POWER``,
p = 1 and 2).  The size cap (``params.vector.size_cap_hi``) is declared to every
table as the widest histogram's cap (``least_squares._freeze_size_cap_multi``),
each table divides it by its own value scale, armed only where that table's
copy has reached it, and ``MultiParameterTable`` intersects the bounds.  The
dataset is ``tests/test_acceptance_wavelength.py``'s published Nd₂Ru₂O₇ pair
(11-BM X-ray, histogram 0, and a CW neutron pattern, histogram 1), refined by
``refine_multi`` under its own ``mccusker_structural`` protocol (both λ held)
with one stage appended that frees ``lor_size`` and ``gauss_size``, in arms:

  shipped        as on main
  no_cap         ``_freeze_size_cap_multi`` declaring no cap
  no_lambda      ``SIZE_LAMBDA_POWER`` emptied: both histograms read the column
                 in degrees as it stands (the case WP-1131 fixed)
  tight          the positive arm: ``SIZE_CAP_RANGE_FRACTION`` set to ``TIGHT``
                 (1e-8), so the cap must arm on the fitted size
  tight_no_lambda  both
  tight6         the fraction at 1e-6, a cap just under the fitted size
  seeded, tight6_seeded, tight6_seeded_no_lambda
                 both sizes started at ``SEED`` (2e-5, the shared column's units)
                 instead of 0, so a table's copy can have reached its cap at a
                 stage's compile, which is the only place the cap arms

Every stage's size-cap freeze is logged: per histogram table, the cap declared,
the ``lor_size``/``gauss_size`` entry's value in that table's own units and the
upper bound ``bounds()`` gives its column (in the shared column's units).

Per arm: each histogram's Rwp, every size row, the cell, the scales, each
histogram's cap in degrees, and every code.

usage (repo root): python docs/wp/2018-measure/joint_size_cap.py [arm ...]
"""
from __future__ import annotations

import importlib
import os
import sys

from common import diagnostics, emit, patched, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from rietx.strategy.staged import Stage  # noqa: E402
from tests.test_acceptance_wavelength import (  # noqa: E402
    NEUTRON_LIMITS,
    XRAY_LIMITS,
    _neutron_instrument,
    _patterns,
    _plan,
    _structure,
    _xray_instrument,
)

vector = importlib.import_module("rietx.params.vector")
multi = importlib.import_module("rietx.params.multi")
lsq = importlib.import_module("rietx.optimize.least_squares")

ARMS = ("shipped", "no_cap", "no_lambda", "tight", "tight_no_lambda", "tight6",
        "seeded", "tight6_seeded", "tight6_seeded_no_lambda")
TIGHT = 1e-8
SEED = 2e-5
SIZES = ("phases.0.lor_size", "phases.0.gauss_size")


def _logging(real, log):
    def freeze(models, mtable):
        real(models, mtable)
        row = []
        for table in mtable.tables:
            lo, hi = table.bounds()
            free = table.free_paths
            row.append({"cap": table._size_cap, **{
                p: [table.entries[table._paths[p]].value,
                    float(hi[free.index(p)]) if p in free else None]
                for p in SIZES}})
        log.append(row)
    return freeze


def fit(arm, log):
    plan = _plan(None)
    plan.stages.append(Stage("size", ["phases.*.lor_size", "phases.*.gauss_size",
                                      "phases.*.scale", "instrument.background.*"]))
    real = lsq._freeze_size_cap_multi
    if arm == "no_cap":
        def real(models, mtable):
            for t in mtable.tables:
                t.freeze_size_cap(None)
    patches = [(lsq, "_freeze_size_cap_multi", _logging(real, log))]
    if arm.endswith("no_lambda"):
        patches.append((multi, "SIZE_LAMBDA_POWER", {}))
    if arm.startswith("tight"):
        patches.append((vector, "SIZE_CAP_RANGE_FRACTION",
                        1e-6 if arm.startswith("tight6") else TIGHT))
    data = _patterns()
    ctx = [patched(m, n, v) for m, n, v in patches]
    for c in ctx:
        c.__enter__()
    try:
        caps = [vector.size_cap(*lim) for lim in (XRAY_LIMITS, NEUTRON_LIMITS)]
        structure = _structure()
        if "seeded" in arm:
            structure.phases[0].lor_size.value = SEED
            structure.phases[0].gauss_size.value = SEED
        result = rx.refine_multi(
            list(data), structure, [_xray_instrument(), _neutron_instrument()],
            plan=plan, two_theta_limits=[XRAY_LIMITS, NEUTRON_LIMITS])
    finally:
        for c in reversed(ctx):
            c.__exit__(None, None, None)
    return result, caps


def main(arms):
    emit({"provenance": provenance(), "fixture": "test_acceptance_wavelength Nd2Ru2O7",
          "tight_fraction": TIGHT})
    for arm in arms:
        try:
            log = []
            result, caps = fit(arm, log)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        emit({"arm": arm, "status": result.status,
              "rwp": [h.statistics.rwp for h in result.histograms],
              "caps_deg_limits_only": caps,
              "params": {p.path: [p.value, p.stderr, p.at_bound]
                         for p in result.parameters
                         if p.path.endswith(("_size", ".scale", "cell.a"))},
              "stages": [{"stage": s.name, "status": s.status,
                          "n_iterations": s.n_iterations}
                         for s in result.stages],
              "cap_freezes": log,
              "diagnostics": diagnostics(result)})


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

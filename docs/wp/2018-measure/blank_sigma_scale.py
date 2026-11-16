"""C26: σ widened at the compile-time blank scale while the scale is free (WP-2018, task 3).

``BackgroundFixedPlusChebyshev`` with a measured blank widens σ at compile,
σ² = σ_y² + s²·σ_f², at the scale ``s`` the stage compiled at
(forward.py, the ``fixed_sigma`` branch), while a free ``s`` is a design row
the same stage moves.  So each stage weights by the previous stage's ``s``, and
``result.sigma`` is the closing stage's compile-time σ, not the σ at the
answer's ``s``.  The dataset is ``tests/test_acceptance_si640c.py``'s Si SRM
640c in Kapton with its blank (``11BM_Kapton.xy``, ``_fit_chebyshev(3,
blank_scale=…, free_scale=True)``, the ``blank_free`` fixture's protocol), in arms:

  start_1       shipped: the scale starts at 1.0 (the fixture's start)
  start_conv    the scale starts at ``CONVERGED`` (the shipped answer), so
                every stage compiles at the answer's ``s``
  start_3       the positive arm: the scale starts at 3.0, so the first stages
                weight by a scale far from the answer
  again         start at 1.0, with one declared stage appended that frees every
                glob the plan freed, so the closing stage compiles at a scale
                one more solve has moved towards the answer: the arm that
                shrinks the lag the closing stage carries
  pinned        start at 1.0, every compile widening σ at ``PINNED`` (the
                start_1 answer's scale) rather than the scale it holds, by
                setting the instrument's scale for the compile alone (a free
                scale is a design row, so the compile reads it only for σ): the
                fixed point the lag is measured against
  no_sigma      the blank's esd column dropped (``blank_sigma=False``), the
                start at 1.0: no widening at all, how much σ_f weighs here; its
                σ is σ_y, so σ_f² = (σ² − σ_y²)/s_c² on the same grid, with s_c
                the closing stage's compile-time scale: the second-last compile
                logged, as the last is the report's fresh compile at the
                answer, which keeps the solve's σ (refine.py, ``fresh.sigma =
                model.sigma``)

Per arm: the scale every compile saw, Rwp, the answer's s, phase scale, Biso,
λ, zero, the widths, and the largest relative gap between ``result.sigma`` and
σ recomputed at the answer's s.

usage (repo root): python docs/wp/2018-measure/blank_sigma_scale.py [arm ...]
"""
from __future__ import annotations

import dataclasses
import importlib
import os
import sys

import numpy as np
from common import diagnostics, emit, patched, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from tests.test_acceptance_si640c import _fit_chebyshev  # noqa: E402

refine_module = importlib.import_module("rietx.refine")

ARMS = ("start_1", "start_conv", "start_3", "again", "pinned", "no_sigma")
PINNED = 0.8413162190297673
CONVERGED = float(os.environ.get("WP2018_CONVERGED", "0.85"))
PATHS = ("instrument.background.scale", "phases.0.scale", "phases.0.atoms.0.biso",
         "instrument.source.lines.0.wavelength", "instrument.zero_shift",
         "instrument.profile.u", "instrument.profile.w", "phases.0.lor_size",
         "instrument.background.c0")


def _logging(real, log, pin=None):
    def compile_model(structure, instrument, data, *a, **k):
        scale = instrument.background.scale
        log.append(float(scale.value))
        if pin is None:
            return real(structure, instrument, data, *a, **k)
        held, scale.value = scale.value, pin
        try:
            return real(structure, instrument, data, *a, **k)
        finally:
            scale.value = held
    return compile_model


def fit(arm, log):
    start = {"start_conv": CONVERGED, "start_3": 3.0}.get(arm, 1.0)
    fit_method = rx.Refinement.fit
    if arm == "again":
        def fit_method(self, data, *, plan, **kwargs):
            freed = list(dict.fromkeys(g for st in plan.stages for g in st.turn_on))
            plan = dataclasses.replace(plan, stages=[*plan.stages, rx.Stage("again", freed)])
            return real_fit(self, data, plan=plan, **kwargs)
    real_fit = rx.Refinement.fit
    with patched(refine_module, "compile_model",
                 _logging(refine_module.compile_model, log,
                          PINNED if arm == "pinned" else None)), \
            patched(rx.Refinement, "fit", fit_method):
        return _fit_chebyshev(3, blank_scale=start, free_scale=True,
                              blank_sigma=arm != "no_sigma")


def main(arms):
    arms = ["no_sigma"] + [a for a in arms if a != "no_sigma"]
    emit({"provenance": provenance(), "fixture": "test_acceptance_si640c blank_free",
          "converged_start": CONVERGED})
    for arm in arms:
        log = []
        try:
            chebfit = fit(arm, log)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        res = chebfit.result
        rows = {p.path: [p.value, p.stderr, p.at_bound] for p in res.parameters
                if p.path in PATHS}
        s = rows.get("instrument.background.scale", [None])[0]
        sigma = np.asarray(res.sigma, dtype=np.float64)
        gap = widen = None
        if arm == "no_sigma":
            sigma_y = sigma
        elif s is not None and sigma.shape == sigma_y.shape:
            s_c = PINNED if arm == "pinned" else log[-2]
            var_f = (sigma ** 2 - sigma_y ** 2) / s_c ** 2
            at_answer = np.sqrt(sigma_y ** 2 + s ** 2 * var_f)
            gap = float(np.max(np.abs(sigma / at_answer - 1.0)))
            widen = float(np.max(sigma / sigma_y - 1.0))
        emit({"arm": arm, "rwp": res.statistics.rwp, "status": res.status,
              "compile_scales": log, "params": rows,
              "closing_compile_scale": log[-2] if len(log) > 1 else None,
              "sigma_gap_vs_answer_s": gap, "sigma_widening_max": widen,
              "stages": [{"stage": st.name, "rwp": st.rwp, "n_iterations": st.n_iterations}
                         for st in res.stages],
              "diagnostics": diagnostics(res)})


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)

"""Why group A's arms went unreached, and proof that each patch can reach its seat.

``group_a.py`` calls an arm ``unreached`` when it matches shipped bit for bit.  That has
two possible causes: the fit never meets the constant, or the patch misses its seat.
This script separates them and writes ``group_a_reach.json``.

``global_reads``: the function whose bytecode loads each constant as a module global, so
a ``setattr`` on ``lm`` reaches it at call time.  ``FTOL`` is absent from these by design:
its seats are the keyword defaults that ``group_a.patched`` rewrites.

``seats``: every arm of ``group_a.ARMS`` under ``group_a.patched``, on synthetic
least-squares problems taken from ``tests/test_lm_solver.py`` and run through
``lm.minimize``.  An arm that changes a problem's evaluations or answer has reached its
constant through that patch.  The problems are Rosenbrock from (-1.2, 1), the column that
vanishes at its minimum, and the crawl along a constraint face that WP-1334 stops.

``reach``: one shipped fit per family with ``lm._next_lambda`` wrapped, so every λ update
is recorded with what it read.  Condition (iii) multiplies λ, so ``_M_LO`` changes nothing
at λ = 0.  Condition (iv) adds to it, so ``_M_HI`` matters at any λ.  The counts name the
condition each constant needs:

- ``_M_HI``: an accepted step with r_u above the smaller value, 5.
- ``_M_LO``: an accepted step with λ > 0 and r_u below the larger value, 0.8.
- ``_Q_TRIGGER``, ``_Q_WINDOW``: Q reaching 4, the smallest arm's trigger plus one.
- ``_LAMBDA_FAIL_*``: a rejected trial.
- ``_CURVATURE_GATE``: a trial that lowered nothing at λ of 30 or more.  A trial whose
  step the model itself refuses (``promise >= 0``, ``lm.py:619``) raises λ without reading
  the gate, so ``max_lambda`` alone does not show a read.  ``gate_lambdas`` lists the λ of
  each read, ``n_curvature_measured`` how many returned a curvature.  The gate's trial is
  not counted in ``nfev`` and changes nothing unless it adopts one, so ``gate_lambdas``
  empty is the only clean reading of ``unreached`` here.
- ``SLOW_DESCENT_ESD``: a stage spending 100 evaluations, ``_SLOW_DESCENT_WINDOW``.

    .venv/bin/python docs/wp/2017-batch/group_a_reach.py
"""

from __future__ import annotations

import inspect
import json
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import group_a as a  # noqa: E402
import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.optimize import lm  # noqa: E402
from tests import test_lm_solver as t  # noqa: E402


def _crawl(start):
    """The constraint-face crawl: the shape that reaches ``slow_descent``."""
    residual, jacobian, X, y = t._collinear_pair()
    d = np.array([np.cos(0.7), np.sin(0.7)])
    row = lm.LinearInequality(T=d[None, :], c=np.array([-(float(d @ np.ones(2)) + 0.5)]),
                              label="face")
    return residual, jacobian, np.array(start), {"inequalities": [row]}


def _problems():
    rosen = t._rosenbrock()
    vanish = t._vanishing_column()
    return {"rosenbrock": (rosen[0], rosen[1], np.array([-1.2, 1.0]), {}),
            "vanishing": (vanish[0], vanish[1], np.array([1.0, 0.2, 0.8]), {}),
            "crawl": _crawl([3.0, 3.0 * (1.0 + 1e-15)]),
            "crawl2": _crawl([3.0, 3.0 * (1.0 - 1e-14)])}


def _solve(problem) -> tuple:
    residual, jacobian, x0, kw = problem
    inf = np.full(len(x0), np.inf)
    out = lm.minimize(residual, jacobian, x0, lo=-inf, hi=inf, **kw)
    return int(out.nfev), out.x.tolist(), out.termination


def global_reads() -> dict:
    """Which ``lm`` function reads each constant as a global, at call time."""
    functions = [v for v in vars(lm).values() if inspect.isfunction(v)
                 and v.__module__ == lm.__name__]
    return {name: [f.__name__ for f in functions if name in f.__code__.co_names]
            for name in a.ARMS}


def seats() -> dict:
    """Each arm's change on each synthetic problem against shipped."""
    problems = _problems()
    real = lm._solve_constrained_step
    lm._solve_constrained_step = t._truncated_step
    try:
        base = {name: _solve(p) for name, p in problems.items()}
        out: dict = {"shipped": {k: [v[0], v[2]] for k, v in base.items()}}
        for constant, values in a.ARMS.items():
            for value in values:
                with a.patched(constant, value):
                    got = {name: _solve(p) for name, p in problems.items()}
                changed = {name: [got[name][0], got[name][2]] for name in problems
                           if got[name][:2] != base[name][:2]}
                out[f"{constant}={value}"] = {"seat_reached": bool(changed), "changed": changed}
    finally:
        lm._solve_constrained_step = real
    return out


def reach(family: str) -> dict:
    """The shipped fit's λ updates and what each constant needed."""
    data, st, ins, plan, kw = a._start(family)
    solves: list = []
    with a.lambda_spied() as seen, a.spied(solves):
        result = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
    return {"rwp": result.statistics.rwp, **a.reach_numbers(*seen, solves)}


def main() -> None:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    out = {"global_reads": global_reads(), "seats": seats(), "reach": {f: reach(f) for f in a.FAMILIES}}
    (HERE / "group_a_reach.json").write_text(json.dumps(out, indent=1) + "\n",
                                             encoding="utf-8")


if __name__ == "__main__":
    main()

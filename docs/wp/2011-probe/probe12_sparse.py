"""Where a Pawley validation's time goes, and what a sparse solve buys.

Validates chosen candidates in Pawley mode with the LM driver instrumented:
seconds in the normal-equation build, in the step solves, the number of
solves and of Hessian products.  ``--variant`` picks the solver path through
module switches on :mod:`rietx.optimize.lm`, so one script measures each.

Candidates: NAC's cached shortlist (probe 11's ``nac_checked.json``, passed
as ``--cache``), chosen by crystal system (``monoclinic`` is the
2224-reflection subcell).

**The switches are not in the tree.**  They are a scratch patch,
``probe12_switches.patch`` beside this file, applied to an archive of the
WP-2011 branch at 6f0f65fa6 and run with that copy's ``src`` first on
``PYTHONPATH``.  Probes 13-15 read the same patch: ``lm.SPARSE_NORMAL`` (A =
JᵀJ formed sparse), ``lm.SPARSE_CACHE`` (the sparsity pattern read once a
stage), ``bccg.PRECONDITION`` / ``EXACT_LU`` / ``REFACTOR_ON_HIT`` (the CG's
preconditioner), and ``least_squares.MERGE_PAWLEY`` / ``MERGE_FRAC`` /
``NO_COV``.

    python probe12_sparse.py --cache nac_checked.json --which monoclinic \
        --variant SPARSE_NORMAL=1,SPARSE_CACHE=1,bccg.PRECONDITION=1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import rietx.indexing.workflow as wf  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.optimize import bccg, lm  # noqa: E402
from rietx.schemas.indexing import CellCandidate  # noqa: E402

TALLY = {}


def _reset():
    TALLY.clear()
    if hasattr(bccg, "PC_STATS"):
        bccg.PC_STATS["factorisations"] = 0
    TALLY.update(t_normal=0.0, t_solve=0.0, n_solves=0, n_products=0, n_outer=0,
                 t_jac=0.0, t_constrained=0.0, n_constrained=0, t_cov=0.0)


class _Counting:
    def __init__(self, H):
        self.H = H

    def __matmul__(self, v):
        TALLY["n_products"] += 1
        return self.H @ v


def _instrument():
    ne, ss, pcg, mz = lm._normal_equations, lm._solve_step, bccg.projected_cg, lm.minimize
    sc = lm._solve_constrained_step

    def constrained(*a, **k):
        t0 = time.perf_counter()
        try:
            return sc(*a, **k)
        finally:
            TALLY["t_constrained"] += time.perf_counter() - t0
            TALLY["n_constrained"] += 1

    def normal(J, r):
        t0 = time.perf_counter()
        out = ne(J, r)
        TALLY["t_normal"] += time.perf_counter() - t0
        TALLY["n_outer"] += 1
        return out

    def solve(*a, **k):
        t0 = time.perf_counter()
        out = ss(*a, **k)
        TALLY["t_solve"] += time.perf_counter() - t0
        TALLY["n_solves"] += 1
        return out

    def cg(H, *a, **k):
        return pcg(_Counting(H), *a, **k)

    def minimize(residual, jacobian, *a, **k):
        def jac(x):
            t0 = time.perf_counter()
            out = jacobian(x)
            TALLY["t_jac"] += time.perf_counter() - t0
            return out
        return mz(residual, jac, *a, **k)

    lm._normal_equations, lm._solve_step, bccg.projected_cg = normal, solve, cg
    lm.minimize = minimize
    lm._solve_constrained_step = constrained
    import rietx.optimize.least_squares as L
    gc = L._guarded_covariance

    def cov(*a, **k):
        t0 = time.perf_counter()
        try:
            return gc(*a, **k)
        finally:
            TALLY["t_cov"] += time.perf_counter() - t0
    L._guarded_covariance = cov


def nac():
    from tests.test_acceptance_nac import build_nac_inputs
    return build_nac_inputs()[::2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--which", default="mono",
                    help="comma list: mono (the 2224-reflection subcell), cubic, all")
    ap.add_argument("--variant", default="dense")
    ap.add_argument("--mode", default="pawley")
    args = ap.parse_args()
    import rietx.model.forward as F
    import rietx.optimize.least_squares as L
    mods = {"L": L, "F": F, "wf": wf, "bccg": bccg}
    for key, value in (kv.split("=") for kv in args.variant.split(",") if "=" in kv):
        mod = lm
        if "." in key:
            prefix, key = key.split(".", 1)
            mod = mods[prefix]
        old = getattr(mod, key)
        setattr(mod, key, value == "1" if isinstance(old, bool) else type(old)(value))
    _instrument()
    data, ins = nac()
    peaks = pick_peaks(data, ins)
    cands = [CellCandidate.model_validate(c)
             for c in json.loads(Path(args.cache).read_text(encoding="utf-8"))]
    want = args.which.split(",")
    chosen = []
    for k, c in enumerate(cands):
        tag = c.system
        if "all" in want or tag in want:
            chosen.append((k, c))
    wf.VALIDATION_MODE = args.mode
    for k, c in chosen:
        _reset()
        t0 = time.perf_counter()
        v, res = wf.validate_by_lebail(c, data, ins, peaks=peaks, with_result=True)
        row = dict(k=k, system=c.system, centring=c.centring, variant=args.variant,
                   mode=args.mode, secs=round(time.perf_counter() - t0, 2),
                   n_refl=v.n_reflections, status=v.status, rwp=round(v.rwp, 5),
                   unmatched=v.unmatched_observed, absent=v.predicted_but_absent,
                   stages=[(s.status, s.n_iterations) for s in res.stages],
                   factorisations=bccg.PC_STATS["factorisations"] if hasattr(bccg, "PC_STATS") else None,
                   **{key: (round(val, 2) if isinstance(val, float) else val)
                      for key, val in TALLY.items()})
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()

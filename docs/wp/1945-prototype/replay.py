"""WP-1945 task 1: count the scalar memo's block builds over whole bench fits.

usage: replay.py REPO OUT.json CASE...

Per case (``examples/bench_refinement.py``'s setups): residual and Jacobian
evaluation counts, every stage's ``n_iterations``, Rwp and every refined value
as ``float.hex``, and the memo's block builds per slot, by wrapping
``CompiledModel._memo``'s ``build``.  Run it on two trees and diff the JSON:
the hex fields must be identical, and the builds are the comparison.
``MEMO_DEPTH=`` in the environment overrides ``_MEMO_DEPTH``.  This is the
script behind the ``_memo`` docstring's build counts and the WP's handover
tables.
"""
import json
import os
import sys

repo, out, cases = sys.argv[1], sys.argv[2], sys.argv[3:]
sys.path.insert(0, os.path.join(repo, "examples"))
os.environ.setdefault("RIETX_TELEMETRY", "0")

import bench_refinement as br  # noqa: E402

import rietx as rx  # noqa: E402
import rietx.optimize.least_squares as lsq  # noqa: E402
from rietx.model.forward import CompiledModel  # noqa: E402

if os.environ.get("MEMO_DEPTH"):
    import rietx.model.forward as fwd
    fwd._MEMO_DEPTH = int(os.environ["MEMO_DEPTH"])
    print(f"_MEMO_DEPTH = {fwd._MEMO_DEPTH}", flush=True)

cnt = {"nfev": 0, "njev": 0, "builds": {}}
o_res, o_jac, o_memo = lsq._make_residual, lsq._make_jacobian, CompiledModel._memo


def w_res(*a, **k):
    f = o_res(*a, **k)

    def g(*x, **y):
        cnt["nfev"] += 1
        return f(*x, **y)
    return g


def w_jac(*a, **k):
    f = o_jac(*a, **k)

    def g(*x, **y):
        cnt["njev"] += 1
        return f(*x, **y)
    return g


def w_memo(self, cp, slot, key_fn, build):
    def counted():
        cnt["builds"][slot] = cnt["builds"].get(slot, 0) + 1
        return build()
    return o_memo(self, cp, slot, key_fn, counted)


lsq._make_residual, lsq._make_jacobian, CompiledModel._memo = w_res, w_jac, w_memo
res = {}
for case in cases:
    setup = {c.key: c for c in br.CASES}[case].build()
    cnt.update(nfev=0, njev=0, builds={})
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True), history=False)
    r = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                two_theta_limits=setup.limits)
    res[case] = {
        "rwp": float(r.statistics.rwp).hex(), "status": str(r.status),
        "nfev": cnt["nfev"], "njev": cnt["njev"],
        "stages": [[s.name, s.n_iterations] for s in r.stages],
        "params": {p.path: float(p.value).hex() for p in r.parameters},
        "builds": dict(cnt["builds"]),
    }
    print(case, "rwp", r.statistics.rwp, "nfev", cnt["nfev"], "njev",
          cnt["njev"], "builds", sum(cnt["builds"].values()), flush=True)
with open(out, "w") as fh:
    json.dump(res, fh, indent=1, sort_keys=True)

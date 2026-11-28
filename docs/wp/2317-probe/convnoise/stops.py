"""Stop rules for the last stage, installed by wrapping rietx.optimize.lm.minimize.

The package is not changed. ``least_squares`` calls ``lm_mod.minimize`` through
the module attribute, so replacing the attribute reaches every LM solve.

Rules are keyed by a *sentinel* ftol, which the caller puts on the last
declared stage (``Stage.ftol``).  The sentinel sits 1e-6 relative above 1e-9,
so the driver's own ftol test is the shipped one to six digits.

- ``gsas``:  stop at the first accepted iteration whose relative decrease in S
  is under ``dm`` (GSAS-II ``min dM/M``, one cycle suffices,
  ``GSASIImath.HessianLSQ``); ``maxcyc`` caps the accepted iterations
  (GSAS-II's ``max cyc`` 3 a Refine call), None = uncapped.
- ``fullprof``: stop at the first accepted iteration where every free
  column's last shift is under ``eps`` x its esd, the esd computed at that
  point as sqrt(chi2_red * diag((J^T J)^-1)) with Jacobi equilibration
  (no Berar-Lelann factor, as FullProf's own test).

A stop is made by raising inside the jacobian hook at the new accepted point,
then rebuilding the outcome at that point with one ``max_nfev=1`` call (one
residual and one jacobian evaluation, subtracted from the counts reported).
"""
from __future__ import annotations

import dataclasses

import numpy as np

import rietx.optimize.lm as lm
from rietx.backend.linalg64 import to_host_fp64
from rietx.optimize.blocked import BlockJacobian

_ORIG = lm.minimize
RULES: dict[float, dict] = {}
LOG: list[dict] = []


def sentinel(k: int) -> float:
    return 1e-9 * (1.0 + k * 1e-6)


class _Stop(Exception):
    def __init__(self, x):
        self.x = x


def _dense(J):
    if isinstance(J, BlockJacobian):
        return J.toarray()
    return np.asarray(to_host_fp64(J), dtype=np.float64)


def esd_at(J, r, n_par):
    J = _dense(J)
    d = np.sqrt(np.einsum("ij,ij->j", J, J))
    ok = d > 0
    Js = J[:, ok] / d[ok]
    C = np.linalg.pinv(Js.T @ Js, rcond=1e-12, hermitian=True)
    dof = max(len(r) - n_par, 1)
    chi2r = float(r @ r) / dof
    esd = np.full(J.shape[1], np.inf)
    esd[ok] = np.sqrt(np.maximum(np.diag(C), 0.0) * chi2r) / d[ok]
    return esd


def minimize(residual, jacobian, x0, *, ftol=lm.FTOL, **kw):
    rule = RULES.get(ftol)
    cnt = {"r": 0, "j": 0, "acc": 0}
    cache: dict[bytes, tuple] = {}

    def res(x):
        cnt["r"] += 1
        out = residual(x)
        if len(cache) > 64:
            cache.clear()
        cache[np.asarray(x).tobytes()] = (out, float(out @ out))
        return out

    st = {"prev": None, "prev_s": None, "rels": [], "shift_esd": []}

    def jac(x):
        cnt["j"] += 1
        J = jacobian(x)
        x = np.asarray(x)
        hit = cache.get(x.tobytes())
        if rule is not None and st["prev"] is not None and hit is not None \
                and not np.array_equal(x, st["prev"]):
            r, s = hit
            cnt["acc"] += 1
            stop = False
            if rule["kind"] == "gsas":
                rel = (st["prev_s"] - s) / st["prev_s"]
                st["rels"].append(rel)
                stop = rel < rule["dm"] or (rule["maxcyc"] is not None
                                            and cnt["acc"] >= rule["maxcyc"])
            else:
                esd = esd_at(J, r, len(x))
                ratio = float(np.max(np.abs(x - st["prev"]) / esd))
                st["shift_esd"].append(ratio)
                stop = ratio < rule["eps"]
            if stop:
                raise _Stop(x.copy())
        if hit is not None:
            st["prev"], st["prev_s"] = x.copy(), hit[1]
        return J

    if rule is None:
        out = _ORIG(res, jac, x0, ftol=ftol, **kw)
        LOG.append({"ftol": ftol, "rule": None, "nfev": out.nfev, "njev": out.njev,
                    "n_res_calls": cnt["r"], "termination": out.termination,
                    "n_free": len(x0), "n_outer": out.n_outer, "cost": out.cost})
        return out
    try:
        out = _ORIG(res, jac, x0, ftol=1e-9, **kw)
        stopped = False
    except _Stop as e:
        n_r, n_j = cnt["r"], cnt["j"]
        kw2 = dict(kw)
        kw2["max_nfev"] = 1
        out = _ORIG(residual, jacobian, e.x, ftol=1e-9, **kw2)
        out = dataclasses.replace(out, status=1, termination="ftol_runs",
                                  nfev=n_r, njev=n_j)
        stopped = True
    LOG.append({"ftol": ftol, "rule": rule["name"], "nfev": out.nfev, "njev": out.njev,
                "n_res_calls": cnt["r"], "termination": out.termination,
                "rule_stopped": stopped, "n_free": len(x0), "n_accepted": cnt["acc"], "cost": out.cost,
                "rels": st["rels"], "shift_esd": st["shift_esd"]})
    return out


def install():
    lm.minimize = minimize


STOPS = {
    "ftol1e-9": None, "ftol1e-8": 1e-8, "ftol1e-7": 1e-7, "ftol1e-6": 1e-6,
    "ftol1e-5": 1e-5, "ftol1e-4": 1e-4,
    "gsas": {"name": "gsas", "kind": "gsas", "dm": 1e-3, "maxcyc": None, "k": 1},
    "gsas3": {"name": "gsas3", "kind": "gsas", "dm": 1e-3, "maxcyc": 3, "k": 2},
    "fp0.2": {"name": "fp0.2", "kind": "fullprof", "eps": 0.2, "k": 3},
    "fp0.1": {"name": "fp0.1", "kind": "fullprof", "eps": 0.1, "k": 4},
}


def last_stage_ftol(stop: str):
    """The ftol to declare on the last stage for ``stop`` (None = shipped)."""
    v = STOPS[stop]
    if v is None or isinstance(v, float):
        return v
    s = sentinel(v["k"])
    RULES[s] = v
    return s


def set_last_ftol(plan, stop: str):
    f = last_stage_ftol(stop)
    if f is not None:
        plan.stages[-1] = dataclasses.replace(plan.stages[-1], ftol=f)
    return plan

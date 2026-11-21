"""Wrap lm.minimize: report per stage the inequality blocks, rows active at the end, box bounds active."""
import numpy as np
from rietx.optimize import lm

_orig = lm.minimize
LOG = []

def spy(residual, jacobian, x0, *, lo, hi, inequalities=None, **kw):
    out = _orig(residual, jacobian, x0, lo=lo, hi=hi, inequalities=inequalities, **kw)
    x = out.x
    rec = {"n": len(x0), "term": out.termination, "n_trunc": out.n_truncated,
           "trunc_by": dict(out.truncated_by), "active_box": int(np.count_nonzero(out.active_mask)) if out.active_mask is not None else None,
           "blocks": []}
    for blk in inequalities or []:
        g = blk.T @ x + blk.c
        rec["blocks"].append((blk.label, blk.T.shape[0], int(np.sum(g <= 1e-12 * (1 + np.abs(blk.c)))), float(g.min())))
    LOG.append(rec)
    return out

lm.minimize = spy

import os
CHECK = os.environ.get("SPY_JAC")

def _jcheck(residual, jacobian, x0, lo, hi):
    r = residual(x0)
    J = jacobian(x0)
    J = J.toarray() if hasattr(J, "toarray") else np.asarray(J)
    print(f"    [jac] n={len(x0)} cost={0.5*r@r:.4f}")
    for i in range(len(x0)):
        h = 1e-5 * max(abs(x0[i]), 1e-3)
        xp, xm = x0.copy(), x0.copy()
        xp[i] += h; xm[i] -= h
        if xm[i] < lo[i]:
            xm[i] = x0[i]; fd = (residual(xp) - r) / h
        else:
            fd = (residual(xp) - residual(xm)) / (2 * h)
        a = J[:, i]
        err = np.linalg.norm(a - fd) / max(np.linalg.norm(fd), 1e-300)
        print(f"    [jac] {i:2d} x={x0[i]: .6g} |J|={np.linalg.norm(a):.4g} relerr={err:.2e} g_an={a@r: .5g} g_fd={fd@r: .5g}")

_orig2 = spy
def spy2(residual, jacobian, x0, *, lo, hi, inequalities=None, **kw):
    if CHECK and len(x0) == int(CHECK):
        _jcheck(residual, jacobian, x0, lo, hi)
    return _orig2(residual, jacobian, x0, lo=lo, hi=hi, inequalities=inequalities, **kw)
lm.minimize = spy2

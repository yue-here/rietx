"""WP-2017 group A: Coelho (2018)'s two hard problems on rietx's own solver.

Group A's four families barely reach the rarer branches of the lambda schedule.  The paper
that prints the schedule names the problems that do, so this runs them through
``optimize.lm.minimize`` with no diffraction model:

* AntiBump, equation (16): 100 atoms in a cubic cell with cyclic boundaries, a penalty
  (B - r)^2 on each pair closer than r = 1.  Cell 4 and 4.5, random starts.  The paper says
  the Q > 5 branch was seen on this example alone.  It ran the penalty under BFGS and this
  runs the full J^T J, so a difference from the paper may be that.  At cell 4 the spheres
  would fill 82 % of the box, past close packing, so S cannot reach 0 and "reached" is
  meaningless there: read the median S.
* The cusp, equation (12): Y_o = |x|^n, Y_c = |x - a|^n on x = -10..10, one parameter a,
  starts in (0, 0.5].  Far from quadratic for small n.  The paper stops at |a| < 1e-3.

Each constant takes one value either side of the shipped one.  A row records whether the
start reached the minimum, what the fit cost, and how often each branch fired.

    .venv/bin/python docs/wp/2017-batch/group_a_paper_cases.py run
    .venv/bin/python docs/wp/2017-batch/group_a_paper_cases.py summary
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import numpy as np  # noqa: E402

from rietx.optimize import lm  # noqa: E402

OUT = pathlib.Path.home() / ".cache/rietx/wp-2017/group_a_paper_cases.jsonl"

ARMS = [("shipped", None, None),
        ("_Q_TRIGGER", "_Q_TRIGGER", 3), ("_Q_TRIGGER", "_Q_TRIGGER", 7),
        ("_Q_TRIGGER", "_Q_TRIGGER", 10 ** 9),
        ("_Q_WINDOW", "_Q_WINDOW", 5), ("_Q_WINDOW", "_Q_WINDOW", 11),
        ("_Q_WINDOW", "_Q_WINDOW", 20),
        ("_M_HI", "_M_HI", 5.0), ("_M_HI", "_M_HI", 20.0),
        ("_M_LO", "_M_LO", 0.2), ("_M_LO", "_M_LO", 0.8),
        ("_LAMBDA_FAIL_FACTOR", "_LAMBDA_FAIL_FACTOR", 5.0),
        ("_LAMBDA_FAIL_FACTOR", "_LAMBDA_FAIL_FACTOR", 20.0),
        ("_LAMBDA_FAIL_FLOOR", "_LAMBDA_FAIL_FLOOR", 0.01),
        ("_LAMBDA_FAIL_FLOOR", "_LAMBDA_FAIL_FLOOR", 1.0),
        ("_CURVATURE_GATE", "_CURVATURE_GATE", 30.0),
        ("_CURVATURE_GATE", "_CURVATURE_GATE", 1000.0),
        ("_CURVATURE_GATE", "_CURVATURE_GATE", float("inf"))]


def antibump(cell: float, seed: int, n_atoms: int = 100, r_min: float = 1.0):
    """Equation (16): one residual per pair, zero beyond r_min."""
    rng = np.random.default_rng(seed)
    i, j = np.triu_indices(n_atoms, 1)

    def geometry(p):
        f = p.reshape(n_atoms, 3)
        d = f[i] - f[j]
        d -= np.round(d)
        return d, cell * np.sqrt((d * d).sum(axis=1))

    def residual(p):
        _, b = geometry(p)
        return np.where(b < r_min, b - r_min, 0.0)

    def jacobian(p):
        d, b = geometry(p)
        hit = np.flatnonzero((b < r_min) & (b > 0.0))
        out = np.zeros((len(b), 3 * n_atoms))
        g = cell * d[hit] / (b[hit, None] / cell)
        for k in range(3):
            out[hit, 3 * i[hit] + k] = g[:, k]
            out[hit, 3 * j[hit] + k] = -g[:, k]
        return out

    return residual, jacobian, rng.uniform(0.0, 1.0, 3 * n_atoms)


def cusp(power: float, start: float):
    """Equation (12): the minimum is a = 0."""
    x = np.arange(-10.0, 11.0)
    y_obs = np.abs(x) ** power

    def residual(p):
        return y_obs - np.abs(x - p[0]) ** power

    def jacobian(p):
        u = x - p[0]
        m = np.abs(u)
        safe = np.where(m > 0.0, m, np.inf)
        return (power * safe ** (power - 1.0) * np.sign(u))[:, None]

    return residual, jacobian, np.array([start])


def one(job: tuple) -> dict:
    kind, a, b, name, value = job
    shipped = getattr(lm, name) if name is not None else None
    if name is not None:
        setattr(lm, name, value)
    seen = {"q_fired": 0, "ru_ge_5": 0, "accepted": 0, "rejected": 0, "max_q": 0.0, "max_ru": 0.0}
    real = lm._next_lambda

    def spy(lam, r_u, q):
        if r_u is None:
            seen["rejected"] += 1
        else:
            seen["accepted"] += 1
            seen["q_fired"] += int(q > lm._Q_TRIGGER)
            seen["ru_ge_5"] += int(r_u >= 5.0)
            seen["max_q"] = max(seen["max_q"], float(q))
            seen["max_ru"] = max(seen["max_ru"], float(r_u))
        return real(lam, r_u, q)

    lm._next_lambda = spy
    try:
        residual, jacobian, x0 = antibump(a, b) if kind == "antibump" else cusp(a, b)
        out = lm.minimize(residual, jacobian, x0, lo=np.full(len(x0), -np.inf),
                          hi=np.full(len(x0), np.inf), max_nfev=2000)
    finally:
        lm._next_lambda = real
        if name is not None:            # a pool's worker outlives the job
            setattr(lm, name, shipped)
    s = float(np.dot(residual(out.x), residual(out.x)))
    reached = s < 1e-12 if kind == "antibump" else abs(float(out.x[0])) < 1e-3
    return {"kind": kind, "a": a, "b": b, "name": name, "value": value, "s": s,
            "reached": bool(reached), "nfev": int(out.nfev), "termination": out.termination, **seen}


def jobs() -> list[tuple]:
    out = []
    for _label, name, value in ARMS:
        for cell in (4.0, 4.5):
            out += [("antibump", cell, seed, name, value) for seed in range(30)]
        for power in (0.05, 0.1, 0.2, 0.3, 0.5):
            out += [("cusp", power, float(start), name, value)
                    for start in np.arange(0.0125, 0.5001, 0.0125)]
    return out


def run() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(4) as pool, OUT.open("w", encoding="utf-8") as fh:
        for row in pool.map(one, jobs(), chunksize=4):
            fh.write(json.dumps(row) + "\n")


def summary() -> None:
    rows = [json.loads(x) for x in OUT.read_text(encoding="utf-8").splitlines()]
    print("| problem | arm | reached | S, median | evals, median | Q fired, fits | r_u >= 5, fits | rejected, median |")
    print("|---|---|---|---|---|---|---|---|")
    keys = sorted({(r["kind"], r["a"]) for r in rows})
    for kind, a in keys:
        for _label, name, value in ARMS:
            sub = [r for r in rows if (r["kind"], r["a"], r["name"], r["value"]) == (kind, a, name, value)]
            print(f"| {kind} {a} | {name or 'shipped'} {'' if value is None else value} "
                  f"| {sum(r['reached'] for r in sub)}/{len(sub)} "
                  f"| {np.median([r['s'] for r in sub]):.4g} "
                  f"| {int(np.median([r['nfev'] for r in sub]))} "
                  f"| {sum(r['q_fired'] > 0 for r in sub)} "
                  f"| {sum(r['ru_ge_5'] > 0 for r in sub)} "
                  f"| {int(np.median([r['rejected'] for r in sub]))} |")


if __name__ == "__main__":
    {"run": run, "summary": summary}[sys.argv[1]]()

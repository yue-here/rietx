"""WP-2017 group C: the seven ``bccg`` constants, on Pawley fits of three families.

The starts, arms and reads were fixed before anything ran (WP-2017 § The list, "C, its
starts and arms", 2026-11-16):

============================  ========  ===============
constant                      shipped   arms
============================  ========  ===============
``_PCG_TOL``                  1e-10     1e-8, 1e-12
``_PCG_BUDGET_PER_VARIABLE``  2         1, 4
``_CAUCHY_ARMIJO``            1e-4      1e-5, 1e-3
``_CONVERGED_FRACTION``       1e-4      1e-5, 1e-3
``_CONVERGED_RUNS``           3         2, 5
``_SMALL_FACTOR``             200       100, 400
``_SMALL_RUNS``               6         3, 12
============================  ========  ===============

Each row is one whole ``fit(data, mode="pawley")`` under the default Pawley plan, from
``tests.test_window_domain._protocol``'s data, structure and instrument for ``fap``,
``nac`` (after its Le Bail pass, CaF₂ appended) and ``cpd1a``.  The start is built once
per family under the shipped constants, pickled, and loaded fresh for every arm.  Two
extra rows per family: ``shipped`` and ``noise`` (shipped constants, every refinable
start value that is not zero times 1 + 1e-12).

The first three constants are read in :func:`rietx.optimize.bccg.projected_cg`, the LM
step above ``lm.BVLS_MAX_COLUMNS``; the last four only in :func:`bccg.solve`, which no
package code calls since WP-1953.  ``_CONVERGED_FRACTION`` is also ``solve``'s ``tol``
keyword default, bound at ``def`` time, so its arms patch that default too.  Every fit
records how often each of the two was called (``n_solve``, ``n_projected_cg``) and the
largest column count ``projected_cg`` saw.  The spy's own positive arm: after each fit,
one call to ``bccg.solve`` on a 2 × 2 system inside the spy must be counted
(``spy_counts_a_call``), so a zero is a zero and not a spy that cannot see.

Reading a row: ``measures`` is ``group_a.measure`` against the same family's shipped
arm: ``model`` and ``background`` are ``tests.test_window_domain._shift`` in plain esd,
``unreached`` is bit-identical rows, Rwp and evaluations.  An arm counts only past the
family's noise arm.  The reference is the family's cell where one exists (FAP: GSAS's
converged ``FAP.EXP``; NAC: the acceptance suite's NAC and CaF₂ cells); cpd-1a's weighed
fractions are not a Pawley fit's to read, so cpd-1a is read against its shipped arm only.

    python docs/wp/2017-batch/group_c.py           # starts, then the sweep; resumes
    python docs/wp/2017-batch/group_c.py canary    # fap and nac, shipped arm only
    python docs/wp/2017-batch/group_c.py summary   # rewrite group_c_summary.md

``WP2017C_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-c``, not
committed); ``WP2017C_WORKERS`` the pool (default 4).  The figures go to
``tests/output/wp2017_groupC_*.png``.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import pickle
import platform
import subprocess
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")

from rietx._about import COMPILED_THREADS_ENV  # noqa: E402

os.environ.setdefault(COMPILED_THREADS_ENV, "1")

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.optimize import bccg  # noqa: E402
from tests import test_window_domain as w  # noqa: E402

group_a = importlib.import_module("group_a")

RAW = Path(os.environ.get("WP2017C_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-c"))
JSONL = RAW / "group_c.jsonl"
SUMMARY = HERE / "group_c_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017C_WORKERS", "4"))

FAMILIES = ("fap", "nac", "cpd1a")
SHIPPED = {"_PCG_TOL": 1e-10, "_PCG_BUDGET_PER_VARIABLE": 2, "_CAUCHY_ARMIJO": 1e-4,
           "_CONVERGED_FRACTION": 1e-4, "_CONVERGED_RUNS": 3, "_SMALL_FACTOR": 200.0,
           "_SMALL_RUNS": 6}
ARMS = {"_PCG_TOL": (1e-8, 1e-12), "_PCG_BUDGET_PER_VARIABLE": (1, 4),
        "_CAUCHY_ARMIJO": (1e-5, 1e-3), "_CONVERGED_FRACTION": (1e-5, 1e-3),
        "_CONVERGED_RUNS": (2, 5), "_SMALL_FACTOR": (100.0, 400.0), "_SMALL_RUNS": (3, 12)}
#: read in projected_cg (the LM step above the BVLS cut); the rest only in bccg.solve
PCG = ("_PCG_TOL", "_PCG_BUDGET_PER_VARIABLE", "_CAUCHY_ARMIJO")
NUDGE = 1e-12
ESD_BAR = 0.1


def references(family: str) -> dict:
    if family == "cpd1a":
        return {}
    return group_a.references(family)


@contextmanager
def patched(constant: str | None, value):
    """``constant`` at ``value`` in ``bccg``, and in ``solve``'s ``tol`` default."""
    if constant is None:
        yield
        return
    assert getattr(bccg, constant) == SHIPPED[constant], constant
    was = getattr(bccg, constant)
    tol = bccg.solve.__kwdefaults__["tol"]
    try:
        setattr(bccg, constant, value)
        if constant == "_CONVERGED_FRACTION":
            bccg.solve.__kwdefaults__["tol"] = value
        yield
    finally:
        setattr(bccg, constant, was)
        bccg.solve.__kwdefaults__["tol"] = tol


@contextmanager
def spied(counts: dict):
    """Count ``bccg.solve`` and ``bccg.projected_cg`` calls, the latter's largest n."""
    solve, pcg = bccg.solve, bccg.projected_cg

    def spy_solve(*args, **kwargs):
        counts["n_solve"] += 1
        return solve(*args, **kwargs)

    def spy_pcg(H, g, *args, **kwargs):
        counts["n_projected_cg"] += 1
        counts["max_pcg_columns"] = max(counts["max_pcg_columns"], len(g))
        return pcg(H, g, *args, **kwargs)

    bccg.solve, bccg.projected_cg = spy_solve, spy_pcg
    try:
        yield
    finally:
        bccg.solve, bccg.projected_cg = solve, pcg


def _start_path(family: str) -> Path:
    return RAW / f"start_{family}.pkl"


def build_start(family: str) -> dict:
    path = _start_path(family)
    if not path.exists():
        warnings.simplefilter("ignore")
        compiled.set_enabled(True)
        data, st, ins, _plan, kw = w._protocol(family)
        path.write_bytes(pickle.dumps((data, st, ins, kw)))
    return {"family": family, "start": str(path)}


def _nudged(ref: rx.Refinement) -> int:
    values = {}
    for row in ref.parameters():
        if not row.refinable or row.value == 0.0:
            continue
        value = row.value * (1.0 + NUDGE)
        if not row.lo <= value <= row.hi:
            value = row.value * (1.0 - NUDGE)
        values[row.path] = value
    ref.set_values(values)
    return len(values)


def _png(family: str, constant: str, arm: str) -> Path:
    return OUT / f"wp2017_groupC_{family}_{constant.lstrip('_')}_{arm}.png"


def fit_one(task: dict) -> dict:
    family, constant, arm, value = task["family"], task["constant"], task["arm"], task["value"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"family": family, "constant": constant, "arm": arm}
    try:
        data, st, ins, kw = pickle.loads(_start_path(family).read_bytes())
        ref = rx.Refinement(st, ins, history=False)
        if constant == "noise":
            row["n_nudged"] = _nudged(ref)
        counts = {"n_solve": 0, "n_projected_cg": 0, "max_pcg_columns": 0}
        name = constant if constant in SHIPPED else None
        with patched(name, value), spied(counts):
            result = ref.fit(data, mode="pawley", **kw)
            seen = counts["n_solve"]
            bccg.solve(np.eye(2), np.ones(2))
            row["spy_counts_a_call"] = counts["n_solve"] == seen + 1
            counts["n_solve"] = seen
        png = _png(family, constant, arm)
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        row.update(counts)
        row.update({
            "rows": {p: list(v) for p, v in w._rows(result).items()},
            "n_pawley": int(ref._model.pawley.n),
            "rwp": result.statistics.rwp, "gof": result.statistics.gof,
            "status": result.status, "converged": result.status == "converged",
            "cost_final": result.stages[-1].cost_final,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "stages": [{"name": s.name, "status": s.status, "termination": s.termination,
                        "n_iterations": s.n_iterations} for s in result.stages],
            "png": str(png.relative_to(ROOT)),
        })
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = group_a._error_line(exc)
    return row


def read_rows(path: Path = JSONL) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _meta() -> dict:
    import importlib.metadata as md

    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip() or "unknown"
    return {"head": head, "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "rietx": rx.__version__,
            "numpy": md.version("numpy"), "kernels": md.version("rietx-kernels"),
            "workers": WORKERS}


def _tasks(families=FAMILIES, arms: bool = True) -> list[dict]:
    tasks = []
    for family in families:
        tasks.append({"family": family, "constant": "shipped", "arm": "shipped", "value": None})
        if not arms:
            continue
        tasks.append({"family": family, "constant": "noise", "arm": str(NUDGE), "value": None})
        for constant, values in ARMS.items():
            tasks += [{"family": family, "constant": constant, "arm": str(v), "value": v}
                      for v in values]
    return tasks


def _pool(n: int) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max_workers=max(1, min(WORKERS, n)),
                               mp_context=get_context("spawn"))


def sweep(families=FAMILIES, arms: bool = True) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with _pool(len(families)) as pool:
        for f in as_completed([pool.submit(build_start, fam) for fam in families]):
            print("start", f.result()["family"], flush=True)
    done = {(r["family"], r["constant"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in _tasks(families, arms)
            if (t["family"], t["constant"], t["arm"]) not in done]
    if not todo:
        return
    with _pool(len(todo)) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["family"], row["constant"], row["arm"],
                  row.get("error") or f"{row['rwp']:.6f} {row['n_eval']}", flush=True)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def summary() -> None:
    rows = read_rows()
    latest = {(r["family"], r["constant"], r["arm"]): r for r in rows}
    meta = dict(next((r["meta"] for r in reversed(rows) if "meta" in r), {}))
    meta["workers"] = "/".join(sorted({str(r["meta"]["workers"]) for r in rows if "meta" in r}))
    lines = ["# WP-2017 group C: the seven `bccg` constants on Pawley fits", "",
             f"Run at `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, "
             f"Python {meta.get('python', '?')}, numpy {meta.get('numpy', '?')}, "
             f"rietx-kernels {meta.get('kernels', '?')}, {meta.get('workers', '?')} workers, "
             "compiled tier on, one kernel thread.  Written by `group_c.py summary`; "
             "arms and reads in its docstring.", "",
             "## Each family's shipped fit", "",
             "| Family | Pawley columns | Rwp | evaluations | stages converged | "
             "`projected_cg` calls (largest n) | `bccg.solve` calls | noise arm, plain esd "
             "(background) |", "|---|---|---|---|---|---|---|---|"]
    errors = [r for r in latest.values() if "error" in r]
    for fam in FAMILIES:
        s = latest.get((fam, "shipped", "shipped"))
        if s is None or "error" in s:
            lines.append(f"| {fam} | not run | | | | | | |")
            continue
        n = latest.get((fam, "noise", str(NUDGE)))
        nm = group_a.measure(n, s, {}) if n and "error" not in n else None
        conv = sum(st["status"] == "converged" for st in s["stages"])
        lines.append(
            f"| {fam} | {s['n_pawley']} | {s['rwp']:.7f} | {s['n_eval']} | "
            f"{conv}/{len(s['stages'])} | {s['n_projected_cg']} ({s['max_pcg_columns']}) | "
            f"{s['n_solve']} | "
            + (f"{_fmt(nm['model'])} ({_fmt(nm['background'])})" if nm else "—") + " |")
    lines += ["", "## Each arm against its family's shipped fit", "",
              "Plain esd over the larger of the two arms' esds (`_shift`); `unreached` is "
              "bit-identical rows, Rwp and evaluations.  Reference: the arm's distance from "
              "the family's reference, shipped's in brackets, in the reference's unit.", "",
              "| Constant | Arm | Family | Rwp | evaluations (× shipped) | model | background | "
              "unreached | `solve` calls | reference |", "|---|---|---|---|---|---|---|---|---|---|"]
    for constant, values in ARMS.items():
        for v in values:
            for fam in FAMILIES:
                r = latest.get((fam, constant, str(v)))
                s = latest.get((fam, "shipped", "shipped"))
                if r is None or s is None or "error" in s:
                    continue
                if "error" in r:
                    lines.append(f"| `{constant}` | {v:g} | {fam} | {r['error']} | | | | | | |")
                    continue
                m = group_a.measure(r, s, references(fam))
                ref = "; ".join(
                    f"{k} {_fmt(t['distance'], '.2e')} ({_fmt(t['shipped_distance'], '.2e')})"
                    for k, t in m["reference"]["table"].items() if t) or "—"
                lines.append(
                    f"| `{constant}` | {v:g} | {fam} | {r['rwp']:.7f} | {r['n_eval']} "
                    f"({m['eval_ratio']:.2f}) | {_fmt(m['model'])} | {_fmt(m['background'])} | "
                    f"{'yes' if m['unreached'] else 'no'} | {r['n_solve']} | {ref} |")
    spy = [r.get("spy_counts_a_call") for r in latest.values() if "error" not in r]
    lines += ["", f"Spy positive arm: {sum(bool(x) for x in spy)} of {len(spy)} fits counted "
              "the extra `bccg.solve` call.", ""]
    if errors:
        lines += ["## Errors", ""] + [f"- {r['family']} {r['constant']} {r['arm']}: "
                                       f"{r['error']}" for r in errors] + [""]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "summary":
        summary()
    elif arg == "canary":
        sweep(("fap", "nac"), arms=False)
    else:
        sweep()

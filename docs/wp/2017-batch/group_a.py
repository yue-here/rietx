"""WP-2017 group A: the ten LM stop constants on the four protocol families.

Each row is a whole fit through the closing stage, from one start per family.
The arms were fixed before anything ran (WP-2017 § The list, 2026-11-05):

=====================  =======  ====================
constant               shipped  arms
=====================  =======  ====================
``_M_HI``              10       5, 20
``_M_LO``              0.4      0.2, 0.8
``_Q_TRIGGER``         5        3, 7
``_Q_WINDOW``          10       5, 20
``_LAMBDA_FAIL_FACTOR`` 10      5, 20
``_LAMBDA_FAIL_FLOOR`` 0.1      0.01, 1
``_CONVERGED_RUNS``    3        2, 5
``_CURVATURE_GATE``    100      30, 1000
``FTOL``               1e-9     1e-8, 1e-10
``SLOW_DESCENT_ESD``   1.0      0.5, 2.0, None
=====================  =======  ====================

``lm.py:650`` caps Q at 10, so ``_Q_WINDOW`` = 20 reads a window of 20 and
``_Q_WINDOW`` = 5 can never pass ``_Q_TRIGGER`` = 5.  ``_LAMBDA_FAIL_FACTOR`` is
also the λ/10 factor at ``lm.py:421``.

``FTOL`` has four seats, because a keyword default is bound at ``def`` time:
``lm.FTOL``, ``least_squares.FTOL`` and the ``ftol`` keyword defaults of
``lm.minimize`` and ``least_squares.run_least_squares``.  The last declared stage and
the closing stage reach the solver with ``ftol`` absent, since
``RefinementPlan.stage_ftols`` gives them ``None`` and ``Refinement._run_stage``
then passes nothing.  ``run_multi_least_squares`` carries a fifth default that no
family reaches.  Every fit records the ``ftol`` each ``lm.minimize`` call received, and
the ``FTOL`` arms assert the shipped 1e-9 is absent from that set.

Three extra rows per family stand beside the arms: ``shipped``, ``noise`` (shipped
constants with every free start value nudged by 1e-12 relative; a start of zero has
no relative nudge and stays, bar a coordinate DOF, which is a step from the stored
coordinate and takes 1e-12 of a typical 0.25) and ``polish`` (below).

The start is built once per family under the shipped constants, NAC's Le Bail pass
included, pickled, and deep-copied for every arm.  The constant is patched only around
the Rietveld fit.

An arm over the 0.1 plain esd bar is polished: one stage freeing the closing stage's
globs plus the shipped closing stage, repeated until no row moves by 0.01 esd (at most
five rounds), under the shipped constants, from that arm's answer.  The shipped answer
is polished the same way, so the comparison tells a path scatter from a second minimum.

    .venv/bin/python docs/wp/2017-batch/group_a.py          # sweep, resumes from the JSONL
    .venv/bin/python docs/wp/2017-batch/group_a.py summary  # rewrite group_a_summary.md

Reading a row: ``measures.model`` and ``measures.background`` are
``tests.test_window_domain._shift`` against the shipped arm, in plain esd
(``stderr_uncorrected``), the axial pair ordered.  ``measures.reference`` is each
reference number's distance, shipped's beside it, and ``worst_further_esd`` is how much
further the arm sits than shipped.  ``measures.unreached`` is true when the arm matches
shipped bit for bit in evaluations and answer.
"""

from __future__ import annotations

import copy
import dataclasses
import fnmatch
import hashlib
import json
import math
import os
import pickle
import subprocess
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")

from rietx._about import COMPILED_THREADS_ENV  # noqa: E402

os.environ.setdefault(COMPILED_THREADS_ENV, "1")

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.optimize import least_squares as ls  # noqa: E402
from rietx.optimize import lm  # noqa: E402
from tests import test_window_domain as w  # noqa: E402
from tests.test_staged_start_invariance import _axial_pair_ordered  # noqa: E402

HERE = Path(__file__).resolve().parent
JSONL = HERE / "group_a.jsonl"
SUMMARY = HERE / "group_a_summary.md"
OUT = ROOT / "tests" / "output"
FITS = OUT / "wp2017_groupA_fits"

WORKERS = 4
FAMILIES = ("fap", "nac", "cpd1a", "lab6")
SHIPPED = {"_M_HI": 10.0, "_M_LO": 0.4, "_Q_TRIGGER": 5, "_Q_WINDOW": 10,
           "_LAMBDA_FAIL_FACTOR": 10.0, "_LAMBDA_FAIL_FLOOR": 0.1, "_CONVERGED_RUNS": 3,
           "_CURVATURE_GATE": 100.0, "FTOL": 1e-9, "SLOW_DESCENT_ESD": 1.0}
ARMS = {"_M_HI": (5.0, 20.0), "_M_LO": (0.2, 0.8), "_Q_TRIGGER": (3, 7),
        "_Q_WINDOW": (5, 20), "_LAMBDA_FAIL_FACTOR": (5.0, 20.0),
        "_LAMBDA_FAIL_FLOOR": (0.01, 1.0), "_CONVERGED_RUNS": (2, 5),
        "_CURVATURE_GATE": (30.0, 1000.0), "FTOL": (1e-8, 1e-10),
        "SLOW_DESCENT_ESD": (0.5, 2.0, None)}

ESD_BAR = 0.1
FIXED_POINT_ESD = 0.01
POLISH_ROUNDS = 5
NUDGE = 1e-12
#: what a coordinate DOF's nudge is relative to, a DOF being a step from zero
COORDINATE_SCALE = 0.25


def references(family: str) -> dict[str, tuple[str, float]]:
    """Each family's reference: {name: (where to read it, the reference value)}.

    ``rows:<path>`` reads a parameter row, ``qpa:<name>`` a weight fraction in wt %.
    The numbers are the acceptance suites' own, imported where the suite names them.
    The Le Bail cell, NAC's third reference, is added from the start in :func:`_start`.
    """
    if family == "fap":
        from tests.test_acceptance_fap import A_GSAS, C_GSAS
        return {"a_gsas": ("rows:phases.0.cell.a", A_GSAS),
                "c_gsas": ("rows:phases.0.cell.c", C_GSAS),
                "lx_gsas": ("rows:phases.0.lor_size", 0.0335)}
    if family == "nac":
        return {"a_nac": ("rows:phases.0.cell.a", 10.2510),
                "a_caf2": ("rows:phases.1.cell.a", 5.4631)}
    if family == "cpd1a":
        from tests.test_acceptance_qpa_roundrobin import WEIGHED
        return {f"wt_{k}": (f"qpa:{k}", v) for k, v in WEIGHED["cpd-1a"].items()}
    from tests.test_acceptance_srm660c import A_REFERENCE, DISP_REFERENCE
    return {"a_cert": ("rows:phases.0.cell.a", A_REFERENCE),
            "disp_spec": ("rows:instrument.geometry.sample_displacement", DISP_REFERENCE)}


@contextmanager
def patched(constant: str | None, value):
    """``constant`` at ``value`` in every seat it has, for the length of the block."""
    if constant is None:
        yield
        return
    seats = [(lm, constant, getattr(lm, constant))]
    defaults = []
    if constant == "FTOL":
        seats.append((ls, "FTOL", ls.FTOL))
        defaults = [(lm.minimize, lm.minimize.__kwdefaults__["ftol"]),
                    (ls.run_least_squares, ls.run_least_squares.__kwdefaults__["ftol"])]
    try:
        for module, name, _ in seats:
            setattr(module, name, value)
        for func, _ in defaults:
            func.__kwdefaults__["ftol"] = value
        yield
    finally:
        for module, name, was in seats:
            setattr(module, name, was)
        for func, was in defaults:
            func.__kwdefaults__["ftol"] = was


@contextmanager
def spied(solves: list):
    """Record what each ``lm.minimize`` call received and how it stopped."""
    inner = lm.minimize

    def spy(*args, **kwargs):
        res = inner(*args, **kwargs)
        solves.append({"ftol": kwargs.get("ftol"), "nfev": int(res.nfev),
                       "n_outer": int(res.n_outer), "termination": res.termination,
                       "lambda_final": float(res.lambda_final)})
        return res

    lm.minimize = spy
    try:
        yield
    finally:
        lm.minimize = inner


def _start_path(family: str) -> Path:
    return FITS / f"start_{family}.pkl"


def _fit_path(constant: str, arm: str, family: str) -> Path:
    return FITS / f"{family}_{constant.lstrip('_')}_{arm}.pkl"


def _png(family: str, constant: str, arm: str) -> Path:
    return OUT / f"wp2017_groupA_{family}_{constant.lstrip('_')}_{arm}.png"


def build_start(family: str) -> str:
    """Pickle the family's start under the shipped constants; its sha256."""
    path = _start_path(family)
    if not path.exists():
        was = compiled.set_enabled(True)
        data, st, ins, plan, kw = w._protocol(family)
        compiled.set_enabled(was)
        assert plan.closing_window_tol == 1e-3, "the protocols ride the shipped stage"
        assert ins.source.dispersion is None
        path.write_bytes(pickle.dumps((data, st, ins, plan, kw)))
    return hashlib.sha256(path.read_bytes()).hexdigest()


_STARTS: dict = {}


def _start(family: str):
    if family not in _STARTS:
        _STARTS[family] = pickle.loads(_start_path(family).read_bytes())
    return copy.deepcopy(_STARTS[family])


def _result_row(family, constant, arm, result, ref, solves, png) -> dict:
    """The JSON row of one fit, and the fitted state beside it for a polish."""
    rows = {path: list(pair) for path, pair in w._rows(result).items()}
    qpa = ({r.name: [r.weight_fraction, r.weight_fraction_stderr]
            for r in result.qpa.phases} if result.qpa is not None else None)
    result.plot(path=str(png))
    import matplotlib.pyplot as plt

    plt.close("all")
    _fit_path(constant, arm, family).write_bytes(pickle.dumps(
        (ref.fitted_structure, ref.fitted_instrument)))
    return {
        "family": family, "constant": constant, "arm": arm, "rows": rows, "qpa": qpa,
        "rwp": result.statistics.rwp, "gof": result.statistics.gof,
        "status": result.status, "converged": result.status == "converged",
        "cost_final": result.stages[-1].cost_final,
        "n_eval": int(sum(s.n_iterations for s in result.stages)),
        "stages": [{"name": s.name, "status": s.status, "termination": s.termination,
                    "n_iterations": s.n_iterations, "ftol": s.ftol}
                   for s in result.stages],
        "solves": solves, "png": str(png.relative_to(ROOT)),
    }


def _nudged(ref: rx.Refinement, plan) -> dict:
    """Nudge every free start value; how many moved and how many could not."""
    globs = {g for s in plan.stages for g in s.turn_on}
    values, zeros = {}, []
    for row in ref.parameters():
        if not row.refinable or not any(fnmatch.fnmatchcase(row.path, g) for g in globs):
            continue
        if row.value == 0.0:
            if ".dof." not in row.path:
                zeros.append(row.path)
                continue
            values[row.path] = NUDGE * COORDINATE_SCALE
            continue
        value = row.value * (1.0 + NUDGE)
        if not row.lo <= value <= row.hi:
            value = row.value * (1.0 - NUDGE)
        values[row.path] = value
    ref.set_values(values)
    return {"n_nudged": len(values), "zero_starts": zeros}


def fit_arm(task: dict) -> dict:
    """One whole fit: the shipped arm, a constant's arm, or the nudged start."""
    family, constant, arm, value = task["family"], task["constant"], task["arm"], task["value"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"family": family, "constant": constant, "arm": arm}
    try:
        data, st, ins, plan, kw = _start(family)
        ref = rx.Refinement(st, ins, history=False)
        extra = _nudged(ref, plan) if constant == "noise" else {}
        solves: list = []
        name = constant if constant in SHIPPED else None
        with patched(name, value), spied(solves):
            result = ref.fit(data, plan=plan, **kw)
        assert result.stages[-1].name == "closing"
        if constant == "FTOL":
            received = {s["ftol"] for s in solves}
            assert value in received and SHIPPED["FTOL"] not in received, received
            extra["ftol_received"] = sorted(received)
        row = _result_row(family, constant, arm, result, ref, solves,
                          _png(family, constant, arm))
        row.update(extra)
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def polish(task: dict) -> dict:
    """From an arm's answer, under the shipped constants, to a fixed point."""
    family, constant, arm = task["family"], task["constant"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    out: dict = {"family": family, "constant": constant, "arm": arm, "kind": "polish"}
    try:
        data, _, _, plan, kw = _start(family)
        st, ins = pickle.loads(_fit_path(constant, arm, family).read_bytes())
        closing = plan.closing_stage()
        one = rx.RefinementPlan(stages=[dataclasses.replace(closing, name="polish")],
                                closing_window_tol=plan.closing_window_tol)
        prev, settled, rounds, n_eval = None, False, 0, 0
        for rounds in range(1, POLISH_ROUNDS + 1):
            ref = rx.Refinement(st, ins, history=False)
            result = ref.fit(data, plan=copy.deepcopy(one), **copy.deepcopy(kw))
            cur = _axial_pair_ordered(w._rows(result))
            n_eval += int(sum(s.n_iterations for s in result.stages))
            st = ref.fitted_structure.model_copy(deep=True)
            ins = ref.fitted_instrument.model_copy(deep=True)
            if prev is not None and max(
                    w._shift(cur, prev, background=False)[0],
                    w._shift(cur, prev, background=True)[0]) < FIXED_POINT_ESD:
                settled = True
                break
            prev = cur
        png = _png(family, constant, f"{arm}_polish")
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        qpa = ({r.name: [r.weight_fraction, r.weight_fraction_stderr]
                for r in result.qpa.phases} if result.qpa is not None else None)
        out.update(rows=cur, qpa=qpa, rwp=result.statistics.rwp, gof=result.statistics.gof,
                   status=result.status, converged=result.status == "converged",
                   cost_final=result.stages[-1].cost_final, n_eval=n_eval, rounds=rounds,
                   settled=settled, png=str(png.relative_to(ROOT)))
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _read_reference(row: dict, family: str, where: str) -> tuple[float, float | None] | None:
    kind, key = where.split(":", 1)
    if kind == "rows":
        if key not in row["rows"]:
            return None
        value, esd = row["rows"][key]
        return value, esd
    if not row.get("qpa") or key not in row["qpa"]:
        return None
    value, esd = row["qpa"][key]
    if value is None:
        return None
    return 100.0 * value, None if esd is None else 100.0 * esd


def reference_measure(row: dict, shipped: dict, targets: dict) -> dict:
    """Each reference distance, shipped's beside it, and the worst growth in esd."""
    table, worst = {}, (None, None)
    for name, (where, target) in targets.items():
        got = _read_reference(row, row["family"], where)
        base = _read_reference(shipped, row["family"], where)
        if got is None or base is None:
            table[name] = None
            continue
        dist, dist0 = abs(got[0] - target), abs(base[0] - target)
        esds = [e for e in (got[1], base[1]) if e is not None and math.isfinite(e) and e > 0.0]
        further = (dist - dist0) / max(esds) if esds else None
        table[name] = {"value": got[0], "esd": got[1], "reference": target, "distance": dist,
                       "shipped_distance": dist0, "further_esd": further}
        if further is not None and (worst[0] is None or further > worst[0]):
            worst = (further, name)
    return {"table": table, "worst_further_esd": worst[0], "worst_name": worst[1]}


def measure(row: dict, shipped: dict, targets: dict) -> dict:
    """The row read against the shipped arm."""
    cur = _axial_pair_ordered(row["rows"])
    base = _axial_pair_ordered(shipped["rows"])
    model = w._shift(cur, base, background=False)
    background = w._shift(cur, base, background=True)
    same_answer = cur == base and row["rwp"] == shipped["rwp"]
    return {
        "model": model[0], "model_path": model[1],
        "background": background[0], "background_path": background[1],
        "rwp_ratio": row["rwp"] / shipped["rwp"],
        "eval_ratio": row["n_eval"] / shipped["n_eval"],
        "converged_changed": row["converged"] != shipped["converged"],
        "terminations_changed": [
            [a["name"], b["termination"], a["termination"]]
            for a, b in zip(row.get("stages", []), shipped.get("stages", []), strict=False)
            if a["termination"] != b["termination"]],
        "paths_only_here": sorted(set(cur) - set(base)),
        "paths_only_shipped": sorted(set(base) - set(cur)),
        "unreached": same_answer and row["n_eval"] == shipped["n_eval"],
        "over_bar": model[0] > ESD_BAR,
        "reference": reference_measure(row, shipped, targets),
    }


def read_rows() -> list[dict]:
    if not JSONL.exists():
        return []
    with JSONL.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _append(row: dict) -> None:
    with JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _key(row: dict) -> tuple:
    return (row.get("kind", "fit"), row["family"], row["constant"], row["arm"])


def _tasks() -> list[dict]:
    tasks = []
    for family in FAMILIES:
        for constant, values in ARMS.items():
            tasks += [{"family": family, "constant": constant, "arm": str(v), "value": v}
                      for v in values]
        tasks.append({"family": family, "constant": "noise", "arm": str(NUDGE), "value": None})
    return tasks


def _run(pool, func, tasks, done, read) -> None:
    futures = [pool.submit(func, t) for t in tasks if _key(t) not in done]
    for future in as_completed(futures):
        row = read(future.result())
        _append(row)
        done[_key(row)] = row
        print(_key(row), row.get("error") or round(row.get("rwp", math.nan), 6),
              flush=True)


def sweep() -> None:
    OUT.mkdir(exist_ok=True)
    FITS.mkdir(exist_ok=True)
    assert compiled.available(), compiled.unavailable()
    done = {_key(r): r for r in read_rows()}
    if ("meta", "", "", "") not in done:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        meta = {"kind": "meta", "family": "", "constant": "", "arm": "", "head": head,
                "version": rx.__version__, "platform": sys.platform,
                "threads": os.environ[COMPILED_THREADS_ENV],
                "starts": {f: build_start(f) for f in FAMILIES}}
        _append(meta)
        done[_key(meta)] = meta
    targets = {f: references(f) for f in FAMILIES}
    context = get_context("spawn")
    with ProcessPoolExecutor(WORKERS, mp_context=context) as pool:
        _run(pool, fit_arm,
             [{"family": f, "constant": "shipped", "arm": "shipped", "value": None}
              for f in FAMILIES], done, lambda r: r)
        shipped = {f: done[("fit", f, "shipped", "shipped")] for f in FAMILIES}
        bad = [f for f, r in shipped.items() if "error" in r]
        assert not bad, f"shipped arm failed on {bad}"
        for f in FAMILIES:
            if f == "nac":
                start = _start("nac")
                targets[f]["a_lebail"] = ("rows:phases.0.cell.a", start[1].phases[0].cell.a.value)

        def read(row):
            if "error" not in row:
                row["measures"] = measure(row, shipped[row["family"]], targets[row["family"]])
            return row

        _run(pool, fit_arm, _tasks(), done, read)

        over = [r for r in done.values() if r.get("kind", "fit") == "fit"
                and r.get("measures", {}).get("over_bar")]
        polish_tasks = [{"family": r["family"], "constant": r["constant"], "arm": r["arm"],
                         "kind": "polish"} for r in over]
        polish_tasks += [{"family": f, "constant": "shipped", "arm": "shipped",
                          "kind": "polish"}
                         for f in sorted({r["family"] for r in over})]
        _run(pool, polish, polish_tasks, done, lambda r: r)

    for key, row in list(done.items()):
        if (key[0] == "polish" and "error" not in row
                and ("polish_read", *key[1:]) not in done):
            family = row["family"]
            base = done.get(("polish", family, "shipped", "shipped"))
            versus = {"to_shipped": w._shift(row["rows"], _axial_pair_ordered(
                shipped[family]["rows"]), background=False)}
            if base is not None and "error" not in base:
                versus["to_shipped_polished"] = w._shift(row["rows"], base["rows"],
                                                         background=False)
                versus["to_shipped_polished_bkg"] = w._shift(row["rows"], base["rows"],
                                                             background=True)
                versus["chi2_ratio_to_shipped_polished"] = (
                    row["cost_final"] / base["cost_final"])
            _append({"kind": "polish_read", "family": family, "constant": row["constant"],
                     "arm": row["arm"], "versus": versus, "rwp": row["rwp"],
                     "rounds": row["rounds"], "settled": row["settled"]})
    summary()


def _fmt(x, spec=".3f") -> str:
    return "n/a" if x is None else format(x, spec)


def summary() -> None:
    """Rewrite ``group_a_summary.md`` from the JSONL, computing nothing new."""
    rows = read_rows()
    fits = [r for r in rows if r.get("kind", "fit") == "fit"]
    lines = ["# WP-2017 group A, read from group_a.jsonl", ""]
    meta = next((r for r in rows if r.get("kind") == "meta"), None)
    if meta is not None:
        lines += [f"head {meta['head'][:9]}, rietx {meta['version']}, {meta['platform']}, "
                  f"{meta['threads']} kernel thread per worker, compiled tier on, `[dev]`.", ""]
    lines += ["## Shipped", "", "| family | Rwp | evaluations | stage terminations |",
              "|---|---|---|---|"]
    for r in fits:
        if r["constant"] == "shipped":
            terms = ", ".join(f"{s['name']}:{s['termination']}" for s in r["stages"])
            lines.append(f"| {r['family']} | {r['rwp']:.6f} | {r['n_eval']} | {terms} |")
    lines += ["", "## Every arm", "",
              "| constant | arm | family | model esd | path | bkg esd | Rwp ratio | eval ratio "
              "| conv | reached | ref further esd | ref name |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in fits:
        m = r.get("measures")
        if r["constant"] == "shipped":
            continue
        if m is None:
            lines.append(f"| {r['constant']} | {r['arm']} | {r['family']} | "
                         f"error: {r.get('error')} |||||||||")
            continue
        ref = m["reference"]
        lines.append(
            f"| {r['constant']} | {r['arm']} | {r['family']} | {m['model']:.4f} | "
            f"{m['model_path']} | {m['background']:.4f} | {m['rwp_ratio']:.6f} | "
            f"{m['eval_ratio']:.3f} | {r['converged']} | "
            f"{'unreached' if m['unreached'] else 'yes'} | "
            f"{_fmt(ref['worst_further_esd'])} | {ref['worst_name']} |")
    reads = [r for r in rows if r.get("kind") == "polish_read"]
    lines += ["", "## Polish", "",
              "| constant | arm | family | to shipped | to shipped polished | path | "
              "bkg | S/S polished | rounds | settled |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in reads:
        v = r["versus"]
        lines.append(
            f"| {r['constant']} | {r['arm']} | {r['family']} | {v['to_shipped'][0]:.4f} | "
            f"{_fmt(v.get('to_shipped_polished', [None])[0])} | "
            f"{v.get('to_shipped_polished', [None, None])[1]} | "
            f"{_fmt(v.get('to_shipped_polished_bkg', [None])[0])} | "
            f"{_fmt(v.get('chi2_ratio_to_shipped_polished'), '.7f')} | "
            f"{r['rounds']} | {r['settled']} |")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] == ["summary"]:
        summary()
    else:
        sweep()

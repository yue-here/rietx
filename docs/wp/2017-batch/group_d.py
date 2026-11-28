"""WP-2017 group D: the joint solve's layout switch, ``blocked.DENSE_JACOBIAN_MAX_BYTES``.

The constant is read only in ``blocked.choose_layout``, which only
``least_squares.run_multi_least_squares`` calls, so only a joint fit reaches it, and on a
given fit its whole effect is the layout it picks: dense below 256 MiB of stacked
Jacobian, blocked above.  Forcing each layout (``blocked.set_layout``) therefore measures
every value the constant could take on that fit.

Fits, arms and reads were fixed in WP-2017 § What each group inherits, "D, its fits and
arms", before anything ran (2026-11-16):

==============  ================================================================
fit             what it is
==============  ================================================================
``cpd1_joint``  IUCr CPD round-robin cpd-1a, -1b and -1c together under the QPA
                acceptance protocol (its phases, ``qarr_instrument`` per pattern,
                ``seed_scales`` per pattern, ``qpa_plan``); default sharing: scales
                and instrument per pattern, the specimen shared.  Reference: the
                weighed fractions.
``cucr_cold``   the CuCr2O4 ramp's seven frames below the published transition near
                130 K (``OH_00`` to ``OH_24``, 6.8-122.7 K, APS 11-BM), group G's
                ``cucr_models`` for each, ``mccusker_default``, every cell
                parameter and Biso per pattern.  Reference: the 10 K Fddd cell of
                Suchomel et al. (2012), Table I, on the coldest frame.
``library20``   the synthetic parametric library at 20 patterns
                (``tests/test_parametric_series.library``, ``tt_max`` 10), the row's
                cited case: the harness's positive arm, which must repeat the
                test's 0.01 esd.  Reference: the library's surface.
==============  ================================================================

Arms: ``dense`` and ``blocked`` forced, ``rule`` (``set_layout(None)``: the shipped
constant), ``noise`` (dense, every non-zero ``Parameter`` of the start ×(1 + 1e-12); the
plan frees them stage by stage).  Control: a spy on ``blocked.choose_layout`` records each
joint solve's rows, columns and answer, so an arm whose solves did not take its layout
measured nothing.  Read: every free row of ``blocked`` (and ``rule``, ``noise``) against
``dense`` in plain esd over the larger of the two (``test_window_domain._shift``, 0.1
bar), with Rwp, evaluations, status and the diagnostic codes; each fit's largest dense
Jacobian against the constant.

    .venv/bin/python docs/wp/2017-batch/group_d.py          # every fit and arm, resumes
    .venv/bin/python docs/wp/2017-batch/group_d.py canary   # library20 dense and blocked
    .venv/bin/python docs/wp/2017-batch/group_d.py summary  # write group_d_summary.md

``WP2017D_RAW`` names the directory for the raw rows (default ``~/.cache/rietx/wp-2017-d``);
``WP2017D_WORKERS`` the pool (default 4).  The figures go to ``tests/output/wp2017_groupD_*.png``.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import subprocess
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
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

from pydantic import BaseModel  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.multi import MultiHistogramRefinement  # noqa: E402
from rietx.optimize import blocked  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.schemas.common import Parameter  # noqa: E402
from tests import test_window_domain as w  # noqa: E402

RAW = Path(os.environ.get("WP2017D_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-d"))
JSONL = RAW / "group_d.jsonl"
SUMMARY = HERE / "group_d_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017D_WORKERS", "4"))

FITS = ("library20", "cpd1_joint", "cucr_cold")
ARMS = ("dense", "blocked", "rule", "noise")
NUDGE = 1e-12
ESD_BAR = 0.1
COLD_FRAMES = 7          # OH_00 .. OH_24, below the transition near 130 K
CPD1 = ("cpd-1a", "cpd-1b", "cpd-1c")


class _Probe(MultiHistogramRefinement):
    """Keeps the last stage's solver outcome, which the result does not carry."""

    def _build_result(self, models, outcome, *args, **kwargs):
        self.outcome_ = outcome
        return super()._build_result(models, outcome, *args, **kwargs)


def _library():
    from tests.test_parametric_series import library
    from tests.test_sequential import _start_models

    n = 20
    patterns, coords, equation = library(n, tt_max=10.0)
    s, ins = _start_models()
    return patterns, s, [ins] * n, "mccusker_default", {
        "coordinates": coords, "parametric": [equation]}


def _cpd_joint():
    group_g = importlib.import_module("group_g")
    patterns, structures, instruments, plan = [], [], [], None
    for sample in CPD1:
        data, st, ins, plan = group_g._cpd(sample)
        patterns.append(data)
        structures.append(st)
        instruments.append(ins)
    return patterns, structures, instruments, plan, {}


def _cucr_cold():
    group_g = importlib.import_module("group_g")
    paths = group_g._ramp_paths()[:COLD_FRAMES]
    patterns = [rx.read_pattern(p) for p in paths]
    st, ins = group_g.cucr_models()
    instruments = [ins.model_copy(deep=True) for _ in paths]
    sharing = SharingMap(per_histogram=["phases.*.cell.*", "phases.*.atoms.*.biso"])
    return patterns, st, instruments, rx.RefinementPlan.mccusker_default(), {
        "sharing": sharing, "temperatures": [group_g.temperature(p) for p in paths]}


BUILDERS = {"library20": _library, "cpd1_joint": _cpd_joint, "cucr_cold": _cucr_cold}


def _nudge(obj, seen: set) -> int:
    """Every non-zero ``Parameter`` reachable from ``obj`` ×(1 + NUDGE), within its bounds."""
    if id(obj) in seen:
        return 0
    seen.add(id(obj))
    if isinstance(obj, Parameter):
        if obj.value == 0.0 or not math.isfinite(obj.value):
            return 0
        value = obj.value * (1.0 + NUDGE)
        if not obj.min <= value <= obj.max:
            value = obj.value * (1.0 - NUDGE)
        obj.value = value
        return 1
    if isinstance(obj, BaseModel):
        return sum(_nudge(getattr(obj, name), seen) for name in type(obj).model_fields)
    if isinstance(obj, (list, tuple)):
        return sum(_nudge(x, seen) for x in obj)
    if isinstance(obj, dict):
        return sum(_nudge(x, seen) for x in obj.values())
    return 0


def _rows(result) -> dict:
    return {p.path: (p.value, p.stderr_uncorrected if p.stderr_uncorrected is not None
                     else p.stderr) for p in result.parameters}


def _fractions(result) -> list | None:
    try:
        return [[[f.name, f.weight_fraction] for f in result.for_histogram(h).qpa.phases]
                for h in range(3)]
    except Exception:  # noqa: BLE001  not every fit carries QPA
        return None


def fit_one(task: dict) -> dict:
    fit, arm = task["fit"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"fit": fit, "arm": arm}
    calls: list = []
    real = blocked.choose_layout

    def spy(n_rows, n_cols, solver):
        layout = real(n_rows, n_cols, solver)
        calls.append([int(n_rows), int(n_cols), solver, layout])
        return layout

    try:
        patterns, structure, instruments, plan, kw = BUILDERS[fit]()
        temperatures = kw.pop("temperatures", None)
        if arm == "noise":
            row["n_nudged"] = _nudge([structure, instruments], set())
        ref = _Probe(structure, instruments, **kw)
        was = blocked.set_layout({"dense": "dense", "noise": "dense",
                                  "blocked": "blocked", "rule": None}[arm])
        blocked.choose_layout = spy
        t0 = time.perf_counter()
        try:
            result = ref.fit(patterns, plan=plan)
        finally:
            blocked.choose_layout = real
            blocked.set_layout(was)
        row["wall_s"] = time.perf_counter() - t0
        OUT.mkdir(parents=True, exist_ok=True)
        png = OUT / f"wp2017_groupD_{fit}_{arm}_h0.png"
        result.for_histogram(0).plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        row.update({
            "layout_calls": calls,
            "last_layout": getattr(ref.outcome_, "jacobian_layout", None),
            "max_dense_bytes": max((blocked.dense_jacobian_bytes(r, c) for r, c, _, _ in calls),
                                   default=0),
            "rows": {p: list(v) for p, v in _rows(result).items()},
            "rwp": result.statistics.rwp, "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "stages": [{"name": s.name, "status": s.status, "termination": s.termination,
                        "n_iterations": s.n_iterations} for s in result.stages],
            "codes": sorted({d.code for d in result.diagnostics}),
            "parametric": [[c.term, c.value, c.esd] for c in (result.parametric or [])],
            "fractions": _fractions(result) if fit == "cpd1_joint" else None,
            "temperatures": temperatures,
            "png": str(png.relative_to(ROOT)),
        })
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:300] if str(exc) else ''}"
        row["layout_calls"] = calls
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


def sweep(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {(r["fit"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if (t["fit"], t["arm"]) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["fit"], row["arm"],
                  row.get("error") or f"{row['rwp']:.7f} {row['n_eval']} {row['last_layout']}",
                  flush=True)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def _layouts(r: dict) -> str:
    seen = sorted({c[3] for c in r.get("layout_calls", [])})
    return "/".join(seen) or "none"


def summary() -> None:
    rows = read_rows()
    latest = {(r["fit"], r["arm"]): r for r in rows}
    meta = dict(next((r["meta"] for r in reversed(rows) if "meta" in r), {}))
    lines = ["# WP-2017 group D: the joint solve's layout switch on three joint fits", "",
             f"Run at `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, "
             f"Python {meta.get('python', '?')}, numpy {meta.get('numpy', '?')}, "
             f"rietx-kernels {meta.get('kernels', '?')}, {meta.get('workers', '?')} workers, "
             "compiled tier on, one kernel thread.  Written by `group_d.py summary`; fits, "
             "arms and reads in its docstring.", "",
             f"`DENSE_JACOBIAN_MAX_BYTES` = {blocked.DENSE_JACOBIAN_MAX_BYTES} "
             f"({blocked.DENSE_JACOBIAN_MAX_BYTES / 2**20:.0f} MiB).", "",
             "## Each fit and arm", "",
             "Shift: plain esd over the larger of the two arms' esds against `dense` "
             "(`_shift`), model rows and background rows; bar 0.1.  Solves: joint solves the "
             "spy saw, and the layouts they took.", "",
             "| Fit | Arm | solves (layouts) | largest dense J (MiB) | Rwp | evaluations | status "
             "| model shift (row) | background shift | same codes as dense | wall (s) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    errors = []
    for fit in FITS:
        d = latest.get((fit, "dense"))
        for arm in ARMS:
            r = latest.get((fit, arm))
            if r is None:
                continue
            if "error" in r:
                errors.append(r)
                lines.append(f"| {fit} | {arm} | {r['error']} | | | | | | | | |")
                continue
            if d is not None and "error" not in d and arm != "dense":
                m = w._shift(r["rows"], d["rows"], background=False)
                b = w._shift(r["rows"], d["rows"], background=True)
                shift = f"{_fmt(m[0])} (`{m[1]}`)"
                bshift = _fmt(b[0])
                codes = "yes" if r["codes"] == d["codes"] else f"no: {r['codes']}"
            else:
                shift = bshift = codes = "—"
            lines.append(
                f"| {fit} | {arm} | {len(r['layout_calls'])} ({_layouts(r)}) | "
                f"{r['max_dense_bytes'] / 2**20:.1f} | {r['rwp']:.9f} | {r['n_eval']} | "
                f"{r['status']} | {shift} | {bshift} | {codes} | {r['wall_s']:.0f} |")
    lines += ["", "## Esds against `dense`", "",
              "The rows carrying an esd, and the largest relative difference in an esd "
              "between the arm and `dense` (the near-cut case `blocked.py`'s docstring names "
              "would show here as a different set).", "",
              "| Fit | Arm | rows with an esd (dense) | same set | largest relative esd difference (row) |",
              "|---|---|---|---|---|"]
    for fit in FITS:
        d = latest.get((fit, "dense"))
        if d is None or "error" in d:
            continue
        for arm in ARMS[1:]:
            r = latest.get((fit, arm))
            if r is None or "error" in r:
                continue
            sd = {k for k, v in d["rows"].items() if v[1]}
            sr = {k for k, v in r["rows"].items() if v[1]}
            worst = max(((abs(r["rows"][k][1] / d["rows"][k][1] - 1.0), k) for k in sd & sr),
                        default=(0.0, None))
            lines.append(f"| {fit} | {arm} | {len(sr)} ({len(sd)}) | {'yes' if sd == sr else 'no'} "
                         f"| {_fmt(worst[0])} (`{worst[1]}`) |")
    lines += ["", "## References, read beside the bar", ""]
    for arm in ("dense", "blocked"):
        r = latest.get(("cpd1_joint", arm))
        if r and "error" not in r and r.get("fractions"):
            from tests.test_acceptance_qpa_roundrobin import WEIGHED

            for sample, fr in zip(CPD1, r["fractions"], strict=False):
                got = ", ".join(f"{p} {100 * f:.2f} ({WEIGHED[sample].get(p, 0.0):.2f})"
                                for p, f in fr)
                lines.append(f"- cpd1_joint {arm} {sample}, wt % (weighed): {got}")
        r = latest.get(("cucr_cold", arm))
        if r and "error" not in r:
            fddd = importlib.import_module("group_g").FDDD_10K
            # the CIF's b and c are the paper's c and b (``measure_real_ramp.report``)
            axes = {"a": "a", "b": "c", "c": "b"}
            parts = []
            for paper, cif in axes.items():
                hit = [r["rows"][k] for k in (f"hist.0.phases.0.cell.{cif}",
                                              f"phases.0.cell.{cif}") if k in r["rows"]]
                if hit:
                    parts.append(f"{paper} {1e6 * (hit[0][0] / fddd[paper] - 1):+.0f} ppm")
            lines.append(f"- cucr_cold {arm}, coldest frame against Suchomel et al. (2012) "
                         f"Table I at 10 K: {', '.join(parts) or 'path not found'}")
        r = latest.get(("library20", arm))
        if r and "error" not in r:
            lines.append(f"- library20 {arm} surface: " + ", ".join(
                f"{t} {v:.6g} ± {e:.2g}" for t, v, e in r["parametric"]))
    if errors:
        lines += ["", "## Errors", ""] + [f"- {r['fit']} {r['arm']}: {r['error']}"
                                           for r in errors]
    lines.append("")
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "summary":
        summary()
    elif arg == "canary":
        sweep([{"fit": "library20", "arm": a} for a in ("dense", "blocked")])
    else:
        sweep([{"fit": f, "arm": a} for f in FITS for a in ARMS])

"""WP-2017 group E: the TRF driver's ``GTOL`` and ``XTOL``, and the bound test's two thresholds.

Four rows: ``optimize.least_squares.GTOL`` and ``XTOL`` (1e-12 each, read only when a caller
picks ``solver="trf"``), and ``strategy.staged.BOUND_HIT_ESD_FRAC`` (1e-2) and
``BOUND_HIT_COS_MIN`` (1e-4), WP-1434's conjunction, whose evidence owes a third family under
TRF.  Fits, arms and cases were fixed in WP-2017 § What each group inherits, "E, its starts and
arms", before anything ran (2026-11-16).

Part 1, the tolerances, each fit through its plan's closing stage under ``solver="trf"``:

- ``cpd1a``: cpd-1a under the QPA acceptance protocol (group G's start).  Reference: the
  weighed fractions.
- ``corundum``: the Stephens acceptance fit with the block freed
  (``_with_block(corundum_phase())``, ``_plan(texture=False, stephens=True)``, the last
  stage's ``max_iter`` 1000 as its test sets).  Reference: its shipped arm.
- ``si640c``: 11-BM Si SRM 640c under ``test_acceptance_si640c``'s XND-range protocol
  (2-50°, FCJ with S/L tied to H/L, λ free, the cell held at the certificate).  Reference:
  XND's λ.

Arms: ``shipped``; ``gtol`` 1e-8; ``xtol`` 1e-8; ``both`` 1e-8 (WP-1109's trial); ``noise``
(every free start value that is not zero ×(1 + 1e-12)).  A spy on the module's
``least_squares`` records each TRF solve's ``gtol``, ``xtol``, ``ftol`` and scipy status.

Part 2, the bound test: issue #273's construction on cpd-1a's shipped TRF answer.  Five
cases, each one path freed alone for one stage (no closing stage) with its declared bound
moved 3 of the answer's esds past the optimum and the path started 1 esd inside that bound;
each at ``ftol`` 1e-9, 1e-6, 1e-4, 1e-3.  The control moves the bound 3 esds to the other side
from the same start, a free optimum that must stay silent.  Each case records the inputs
``bound_findings`` read (gap over esd, the residual cosine) through a spy on
``refine.check_guards``, and whether ``BOUND_HIT``/``FLOOR_HIT`` and ``at_bound`` fired.

    .venv/bin/python docs/wp/2017-batch/group_e.py          # both parts, resumes
    .venv/bin/python docs/wp/2017-batch/group_e.py canary   # si640c shipped, one bound case
    .venv/bin/python docs/wp/2017-batch/group_e.py summary  # write group_e_summary.md

``WP2017E_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-e``);
``WP2017E_WORKERS`` the pool (default 4).  Figures: ``tests/output/wp2017_groupE_*.png``.
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
from rietx.optimize import least_squares as ls  # noqa: E402
from rietx.strategy import staged  # noqa: E402
from tests import test_window_domain as w  # noqa: E402

RAW = Path(os.environ.get("WP2017E_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-e"))
JSONL = RAW / "group_e.jsonl"
SUMMARY = HERE / "group_e_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017E_WORKERS", "4"))

FAMILIES = ("cpd1a", "corundum", "si640c")
ARMS = {"shipped": (1e-12, 1e-12), "gtol": (1e-8, 1e-12), "xtol": (1e-12, 1e-8),
        "both": (1e-8, 1e-8), "noise": (1e-12, 1e-12)}       # (GTOL, XTOL)
NUDGE = 1e-12
ESD_BAR = 0.1
FTOLS = (1e-9, 1e-6, 1e-4, 1e-3)
BOUND_ESDS = 3.0
START_ESDS = 1.0
#: (name, path, side): side "min" puts a lower bound above the optimum, "max" an upper one below
CASES = (("fluorite_biso_min", "phases.2.atoms.0.biso", "min"),
         ("zincite_biso_max", "phases.1.atoms.-1.biso", "max"),
         ("fluorite_lor_size_max", "phases.2.lor_size", "max"),
         ("zincite_scale_max", "phases.1.scale", "max"),
         ("zero_shift_max", "instrument.zero_shift", "max"))
#: WP-1434's separations on FAP and Si SRM 640c, for the margins beside this family's
WP1434 = {"gap_max": 7.7e-4, "cos_min": 1.5e-2, "free_cos": 5.0e-10}


@contextmanager
def tolerances(gtol: float, xtol: float, calls: list):
    real, g0, x0 = ls.least_squares, ls.GTOL, ls.XTOL

    def spy(*args, **kwargs):
        res = real(*args, **kwargs)
        calls.append([kwargs.get("gtol"), kwargs.get("xtol"), kwargs.get("ftol"),
                      int(res.status), int(res.nfev)])
        return res

    ls.least_squares, ls.GTOL, ls.XTOL = spy, gtol, xtol
    try:
        yield
    finally:
        ls.least_squares, ls.GTOL, ls.XTOL = real, g0, x0


def build(family: str):
    """(data, structure, instrument, plan, fit kwargs, prepare(ref))."""
    if family == "cpd1a":
        data, st, ins, plan = importlib.import_module("group_g")._cpd("cpd-1a")
        return data, st, ins, plan, {}, None
    if family == "corundum":
        from tests.test_acceptance_qpa_roundrobin import DATA, qarr_instrument, seed_scales
        from tests.test_acceptance_stephens import _plan, _with_block, corundum_phase

        data = rx.read_pattern(DATA / "corundum.prn")
        st = rx.Structure(phases=[_with_block(corundum_phase())])
        ins = qarr_instrument()
        seed_scales(st, ins, data)
        plan = _plan(texture=False, stephens=True)
        plan.stages[-1].max_iter = 1000
        return data, st, ins, plan, {}, None
    from tests import test_acceptance_si640c as si

    data = rx.read_pattern(si.PATTERN)

    def prepare(ref):
        ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])

    return (data, si._structure(), si._instrument(si.FULL_LIMITS), si._plan(asymmetric=True),
            {"two_theta_limits": si.FULL_LIMITS}, prepare)


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


def _record(result) -> dict:
    return {
        "rows": {p.path: [p.value, p.stderr_uncorrected] for p in result.parameters},
        "rwp": result.statistics.rwp, "status": result.status,
        "converged": result.status == "converged",
        "n_eval": int(sum(s.n_iterations for s in result.stages)),
        "stages": [{"name": s.name, "status": s.status, "termination": s.termination,
                    "n_iterations": s.n_iterations} for s in result.stages],
        "codes": sorted({d.code for d in result.diagnostics}),
    }


def _fractions(result) -> dict | None:
    try:
        return {f.phase: 100.0 * f.weight_fraction for f in result.qpa.fractions}
    except Exception:  # noqa: BLE001
        return None


def fit_one(task: dict) -> dict:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    if task["kind"] == "bound":
        return bound_one(task)
    family, arm = task["family"], task["arm"]
    row: dict = {"kind": "tol", "family": family, "arm": arm}
    calls: list = []
    try:
        data, st, ins, plan, kw, prepare = build(family)
        ref = rx.Refinement(st, ins, solver="trf", history=False)
        if prepare:
            prepare(ref)
        if arm == "noise":
            row["n_nudged"] = _nudged(ref)
        with tolerances(*ARMS[arm], calls):
            result = ref.fit(data, plan=plan, **kw)
        png = OUT / f"wp2017_groupE_{family}_{arm}.png"
        OUT.mkdir(parents=True, exist_ok=True)
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        row.update(_record(result))
        row["solves"] = calls
        row["fractions"] = _fractions(result) if family == "cpd1a" else None
        if family == "si640c":
            lam = result.parameter("instrument.source.lines.0.wavelength")
            row["lambda"] = [lam.value, lam.stderr]
        if family == "cpd1a" and arm == "shipped":
            RAW.mkdir(parents=True, exist_ok=True)
            (RAW / "cpd1a_trf_answer.pkl").write_bytes(pickle.dumps(
                (data, ref.fitted_structure, ref.fitted_instrument,
                 {p.path: (p.value, p.stderr) for p in result.parameters})))
        row["png"] = str(png.relative_to(ROOT))
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = importlib.import_module("group_a")._error_line(exc)
        row["solves"] = calls
    return row


def _resolve(st: rx.Structure, ins: rx.Instrument, path: str):
    """The ``Parameter`` at a dot-path, negative list indices allowed; and the canonical path."""
    head, *parts = path.split(".")
    obj = st if head == "phases" else ins
    if head == "phases":
        parts = ["phases", *parts]
    canon = [head] if head != "phases" else []
    for part in parts:
        if isinstance(obj, list):
            i = int(part) % len(obj)
            obj = obj[i]
            canon.append(str(i))
        else:
            obj = getattr(obj, part)
            canon.append(part)
    return obj, ".".join(canon)


def bound_one(task: dict) -> dict:
    name, path, side, ftol, mode = task["case"], task["path"], task["side"], task["ftol"], task["mode"]
    row: dict = {"kind": "bound", "case": name, "ftol": ftol, "mode": mode}
    try:
        data, st, ins, answer = pickle.loads((RAW / "cpd1a_trf_answer.pkl").read_bytes())
        param, canon = _resolve(st, ins, path)
        row["path"] = canon
        if canon not in answer or not answer[canon][1]:
            row["error"] = f"{canon} has no esd in the shipped TRF answer"
            return row
        opt, esd = answer[canon]
        sign = 1.0 if side == "min" else -1.0          # min: bound above the optimum
        bound = opt + sign * BOUND_ESDS * esd if mode == "bind" else opt - sign * BOUND_ESDS * esd
        start = opt + sign * (BOUND_ESDS + START_ESDS) * esd
        # widen only as far as the start needs, place it, then set the moved bound: a
        # Parameter validates value against its bounds on every assignment
        if side == "min":                 # a lower bound: above the optimum, or (control) below
            param.max = max(param.max, start + esd)
            param.min = min(param.min, start)
            param.value = start
            param.min = bound
        else:                             # an upper bound: below the optimum, or (control) above
            param.min = min(param.min, start - esd)
            param.max = max(param.max, start)
            param.value = start
            param.max = bound
        row.update({"optimum": opt, "esd": esd, "bound": bound, "start": start,
                    "lo": param.min, "hi": param.max})
        captured: list = []
        refine_mod = sys.modules["rietx.refine"]
        real = refine_mod.check_guards

        def spy(table, outcome, *a, **k):
            captured.append((list(table.free_paths), getattr(outcome, "residual_cosine", None),
                             getattr(outcome, "x", None)))
            return real(table, outcome, *a, **k)

        stage = staged.Stage("bound", [canon])
        stage.ftol = ftol
        plan = staged.RefinementPlan(stages=[stage], closing_window_tol=None)
        refine_mod.check_guards = spy
        try:
            ref = rx.Refinement(st, ins, solver="trf", history=False)
            result = ref.fit(data, plan=plan)
        finally:
            refine_mod.check_guards = real
        fitted = result.parameter(canon)
        hits = [d for d in result.diagnostics if d.code in ("BOUND_HIT", "FLOOR_HIT")
                and canon in (d.where or [])]
        cos = None
        if captured and captured[-1][1] is not None:
            free, rc, _ = captured[-1]
            cos = float(np.asarray(rc)[free.index(canon)]) if canon in free else None
        limit = bound
        row.update({
            "value": fitted.value, "stderr": fitted.stderr, "at_bound": fitted.at_bound,
            "fired": [d.code for d in hits], "residual_cosine": cos,
            "gap_esd": abs(fitted.value - limit) / fitted.stderr if fitted.stderr else None,
            "gap_answer_esd": abs(fitted.value - limit) / esd,
            "status": result.status, "termination": result.stages[-1].termination,
            "n_eval": int(result.stages[-1].n_iterations),
        })
    except Exception as exc:  # noqa: BLE001
        row["error"] = importlib.import_module("group_a")._error_line(exc)
    return row


def read_rows(path: Path = JSONL) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _key(r: dict) -> tuple:
    if r["kind"] == "tol":
        return ("tol", r["family"], r["arm"])
    return ("bound", r["case"], r["ftol"], r["mode"])


def _meta() -> dict:
    import importlib.metadata as md

    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip() or "unknown"
    return {"head": head, "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "numpy": md.version("numpy"),
            "kernels": md.version("rietx-kernels"), "workers": WORKERS}


def _run(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {_key(r) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if _key(t) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(*_key(row), row.get("error") or f"{row.get('rwp', row.get('value'))}",
                  flush=True)


def _tol_tasks(families=FAMILIES, arms=tuple(ARMS)) -> list[dict]:
    return [{"kind": "tol", "family": f, "arm": a} for f in families for a in arms]


def _bound_tasks(cases=CASES, ftols=FTOLS, modes=("bind", "control")) -> list[dict]:
    return [{"kind": "bound", "case": c, "path": p, "side": s, "ftol": f, "mode": m}
            for c, p, s in cases for f in ftols for m in modes]


def sweep() -> None:
    _run(_tol_tasks(("cpd1a",), ("shipped",)))      # part 2 starts from this answer
    _run(_tol_tasks() + _bound_tasks())


def canary() -> None:
    _run(_tol_tasks(("cpd1a", "si640c"), ("shipped",)))
    _run(_bound_tasks(CASES[:1], (1e-9,), ("bind",)))


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def summary() -> None:
    rows = read_rows()
    latest = {_key(r): r for r in rows}
    meta = dict(next((r["meta"] for r in reversed(rows) if "meta" in r), {}))
    lines = ["# WP-2017 group E: TRF's GTOL and XTOL, and the bound test's thresholds", "",
             f"Run at `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, Python "
             f"{meta.get('python', '?')}, numpy {meta.get('numpy', '?')}, rietx-kernels "
             f"{meta.get('kernels', '?')}, {meta.get('workers', '?')} workers, compiled tier on, "
             "one kernel thread, `solver=\"trf\"` throughout.  Written by `group_e.py summary`; "
             "fits, arms and cases in its docstring.", "",
             "## Part 1: each arm against its family's shipped TRF fit", "",
             "Plain esd over the larger of the two arms' esds (`_shift`), bar 0.1.  Solves: TRF "
             "calls, and the scipy statuses they ended on (1 gtol, 2 ftol, 3 xtol, 4 ftol and "
             "xtol, 0 budget).", "",
             "| Family | Arm | Rwp | evaluations (× shipped) | status | model shift (row) | "
             "background | unreached | solves: statuses | reference |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    errors = [r for r in latest.values() if "error" in r]
    for fam in FAMILIES:
        s = latest.get(("tol", fam, "shipped"))
        for arm in ARMS:
            r = latest.get(("tol", fam, arm))
            if r is None:
                continue
            if "error" in r:
                lines.append(f"| {fam} | {arm} | {r['error']} | | | | | | | |")
                continue
            statuses = {}
            for c in r["solves"]:
                statuses[c[3]] = statuses.get(c[3], 0) + 1
            st = ", ".join(f"{k}×{v}" for k, v in sorted(statuses.items()))
            if s and "error" not in s and arm != "shipped":
                m = w._shift(r["rows"], s["rows"], background=False)
                b = w._shift(r["rows"], s["rows"], background=True)
                same = r["rows"] == s["rows"] and r["rwp"] == s["rwp"] and r["n_eval"] == s["n_eval"]
                cells = (f"{_fmt(m[0])} (`{m[1]}`)", _fmt(b[0]), "yes" if same else "no",
                         f"{r['n_eval']} ({r['n_eval'] / s['n_eval']:.2f})")
            else:
                cells = ("—", "—", "—", str(r["n_eval"]))
            if fam == "cpd1a" and r.get("fractions"):
                from tests.test_acceptance_qpa_roundrobin import WEIGHED

                ref = ", ".join(f"{p} {v - WEIGHED['cpd-1a'].get(p, 0.0):+.2f}"
                                for p, v in r["fractions"].items()) + " wt % from weighed"
            elif fam == "si640c" and r.get("lambda"):
                from tests.test_acceptance_si640c import XND

                ref = f"λ {1e6 * (r['lambda'][0] / XND['lam'] - 1):+.2f} ppm from XND"
            else:
                ref = "—"
            lines.append(f"| {fam} | {arm} | {r['rwp']:.7f} | {cells[3]} | {r['status']} | "
                         f"{cells[0]} | {cells[1]} | {cells[2]} | {st} | {ref} |")
    lines += ["", "## Part 2: issue #273's construction on cpd-1a under TRF", "",
              f"Bound {BOUND_ESDS:g} answer esds past the optimum (`bind`) or on the far side "
              f"(`control`), start {START_ESDS:g} esd inside it.  Gap: |value − limit| over the "
              "row's own esd, what `bound_findings` reads against "
              f"`BOUND_HIT_ESD_FRAC` = {staged.BOUND_HIT_ESD_FRAC:g}; cosine against "
              f"`BOUND_HIT_COS_MIN` = {staged.BOUND_HIT_COS_MIN:g}.", "",
              "| Case | path | mode | ftol | gap / esd | |cosine| | fired | at_bound | status "
              "(termination) | evaluations |", "|---|---|---|---|---|---|---|---|---|---|"]
    gaps, coss, free_coss = [], [], []
    for name, _, _ in CASES:
        for mode in ("bind", "control"):
            for ftol in FTOLS:
                r = latest.get(("bound", name, ftol, mode))
                if r is None:
                    continue
                if "error" in r:
                    lines.append(f"| {name} | {r.get('path', '')} | {mode} | {ftol:g} | "
                                 f"{r['error']} | | | | | |")
                    continue
                cos = None if r["residual_cosine"] is None else abs(r["residual_cosine"])
                if mode == "bind":
                    if r["gap_esd"] is not None:
                        gaps.append(r["gap_esd"])
                    if cos is not None:
                        coss.append(cos)
                elif cos is not None:
                    free_coss.append(cos)
                lines.append(
                    f"| {name} | `{r['path']}` | {mode} | {ftol:g} | {_fmt(r['gap_esd'])} | "
                    f"{_fmt(cos)} | {', '.join(r['fired']) or 'none'} | {r['at_bound']} | "
                    f"{r['status']} ({r['termination']}) | {r['n_eval']} |")
    if gaps and coss:
        lines += ["", f"Binding cases: largest gap {max(gaps):.2g} esd, margin "
                  f"{staged.BOUND_HIT_ESD_FRAC / max(gaps):.3g}× under the threshold "
                  f"(WP-1434: {staged.BOUND_HIT_ESD_FRAC / WP1434['gap_max']:.3g}×); smallest "
                  f"|cosine| {min(coss):.2g}, {min(coss) / staged.BOUND_HIT_COS_MIN:.3g}× above "
                  f"it (WP-1434: {WP1434['cos_min'] / staged.BOUND_HIT_COS_MIN:.3g}×)."]
    if free_coss:
        lines.append(f"Controls: largest |cosine| {max(free_coss):.2g}, "
                     f"{staged.BOUND_HIT_COS_MIN / max(free_coss):.3g}× under the threshold "
                     f"(WP-1434: {staged.BOUND_HIT_COS_MIN / WP1434['free_cos']:.3g}×).")
    if errors:
        lines += ["", "## Errors", ""] + [f"- {_key(r)}: {r['error']}" for r in errors]
    lines.append("")
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "summary":
        summary()
    elif arg == "canary":
        canary()
    else:
        sweep()

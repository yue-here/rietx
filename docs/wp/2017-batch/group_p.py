"""WP-2017 group P: the window numerics, measured on the four protocols and on fits that run away.

Fits and arms were fixed in WP-2017 § What each group inherits, "P, its fits and arms", before
anything ran (2026-11-16).  Four parts, one task kind each:

- ``p1`` ``forward.AXIAL_SIZING_FLOOR`` 0.01 / 0.02 (shipped) / 0.05, and ``noise`` (0.02, every
  refinable non-zero start ×(1 + 1e-12)): ``fap``, ``nac``, ``cpd1a``, ``lab6`` from their own
  starts, with the closing stage (``closing``) and with ``closing_window_tol=None`` (``none``).
- ``p2`` ``forward.REFLECTION_MARGIN_DEG``: bar 1 at fixed parameters (each family's shipped
  closing answer drawn at the 2 % and the 1e-3 windows under 0.25, 0.5, 5 and 20), the
  test's own construction beside it (the answer reached at 20 without the closing stage, drawn at
  2 %), and bar 2: the shipped answer polished once under 0.25, 0.5, 5 and 20, and ``noise``.
- ``p3`` ``STAGE_WINDOWS_STALE``: every stage's window loss on fits that run away: the QPA
  round-robin chain cpd-1a → cpd-1b under the pre-WP-2045 schedule (``chain_pre2045``) and the
  shipped one (``chain_shipped``), and group A's hard starts (``lab6_x1.01`` ... ``fap_x1.03``,
  ``cpd1a_zircon``).  The closing compile is refused above ``axial_sl`` 1, as the chain's test
  does.  P1's fits are the population that reaches its answer.
- ``p4`` ``report.NOMINAL_AXIAL_APERTURE`` 0.005-0.05 between ``report()`` calls on one fit with
  both apertures 0 (``zero``), on ``lab6``, ``fap`` and ``srm1976a``; ``free``: the protocol
  with the axial term free, for each family's own aperture.

    .venv/bin/python docs/wp/2017-batch/group_p.py          # every task
    .venv/bin/python docs/wp/2017-batch/group_p.py canary   # p1 fap none f0.02 + f0.05, p4 fap zero
    .venv/bin/python docs/wp/2017-batch/group_p.py summary  # write group_p_summary.md

``WP2017P_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-p``);
``WP2017P_WORKERS`` the pool (default 4).  Figures: ``tests/output/wp2017_groupP_*.png``.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import signal
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

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.model import forward as fwd  # noqa: E402

RAW = Path(os.environ.get("WP2017P_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-p"))
JSONL = RAW / "group_p.jsonl"
SUMMARY = HERE / "group_p_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017P_WORKERS", "4"))

FAMILIES = ("fap", "nac", "cpd1a", "lab6")
P1_ARMS = ("f0.01", "f0.02", "f0.05", "noise")
CLOSINGS = ("closing", "none")
P2_ARMS = ("m0.25", "m0.5", "m5", "m20", "noise")
MARGIN_REF = 20.0
P3_STARTS = ("chain_pre2045", "chain_shipped", "lab6_x1.01", "lab6_x1.03", "nac_x1.01",
             "nac_x1.03", "cpd1a_x1.03", "cpd1a_zircon", "fap_x1.03")
P4_FAMILIES = ("lab6", "fap", "srm1976a")
NOMINALS = (0.005, 0.01, 0.02, 0.03, 0.05)
NUDGE = 1e-12
#: a runaway guard, read between python bytecodes
FIT_GUARD_S = 2400
SL = "instrument.geometry.axial_sl"
HL = "instrument.geometry.axial_hl"
DISPLAY_LIMIT_DEG = 40.0


class _Runaway(BaseException):
    """Raised from a closing compile above axial_sl 1, past every handler a fit has."""


class _Timeout(BaseException):
    """The runaway guard."""


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


def _protocol(family: str):
    from tests import test_window_domain as w

    return w._protocol(family)


def _displaced(st: rx.Structure, factor: float) -> None:
    """Every phase's cell lengths × ``factor`` (group A's hard starts)."""
    for phase in st.phases:
        for name in ("a", "b", "c"):
            getattr(phase.cell, name).value *= factor


def _zircon_declared():
    """As group A's ``cpd1a_zircon`` start builds it."""
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
        zircon_phase,
    )
    data = rx.read_pattern(DATA / "cpd-1a.prn")
    st = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase(),
                              zircon_phase()])
    ins = qarr_instrument()
    seed_scales(st, ins, data)
    return data, st, ins, qpa_plan(), {}


def _srm1976a(axial: bool):
    """The SRM 1976a plate under its acceptance protocol (texture on)."""
    from tests import test_acceptance_srm1976a_texture as t

    data = rx.read_pattern(t.PATTERN)
    st, ins = t._structure(True), t._instrument()
    tex = ["phases.0.texture.*"]
    aberr = ["instrument.geometry.sample_transparency"] + ([SL] if axial else [])
    stages = [
        rx.Stage("scale_bkg", ["phases.0.scale", "instrument.background.*"]),
        rx.Stage("displacement", ["instrument.geometry.sample_displacement"]),
        rx.Stage("w", ["instrument.profile.w"]),
        rx.Stage("widths", ["instrument.profile.u", "instrument.profile.v",
                            "instrument.profile.x", "instrument.profile.y"]),
        rx.Stage("biso", ["phases.0.atoms.*.biso"]),
        rx.Stage("texture", tex),
        rx.Stage("aberrations", aberr),
        rx.Stage("final", ["phases.0.atoms.*.biso", *tex]),
    ]
    plan = rx.RefinementPlan(stages=stages, intermediate_ftol=1e-6, closing_window_tol=1e-3)
    return data, st, ins, plan, {"two_theta_limits": t.LIMITS}


def _stages(result) -> list[dict]:
    return [{"name": s.name, "loss": s.window_loss,
             "tol": fwd.recorded_window_tol(s.window_area_tol),
             "n_it": s.n_iterations, "status": s.status} for s in result.stages]


def _result_row(result) -> dict:
    row = {
        "rows": {p.path: [p.value, p.stderr_uncorrected] for p in result.parameters},
        "rwp": result.statistics.rwp, "status": result.status,
        "n_eval": int(sum(s.n_iterations for s in result.stages)),
        "codes": sorted({d.code for d in result.diagnostics}),
        "stages": _stages(result),
    }
    if result.qpa is not None:
        row["fractions"] = {f.name: 100.0 * f.weight_fraction for f in result.qpa.phases}
    return row


def _plot(result, tag: str) -> str:
    import matplotlib.pyplot as plt

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"wp2017_groupP_{tag}.png"
    result.plot(path=str(png))
    plt.close("all")
    return str(png.relative_to(ROOT))


class _set:
    """Module attributes set for a block, then restored."""

    def __init__(self, module, **values):
        self.module, self.values, self.old = module, values, {}

    def __enter__(self):
        for k, v in self.values.items():
            self.old[k] = getattr(self.module, k)
            setattr(self.module, k, v)

    def __exit__(self, *exc):
        for k, v in self.old.items():
            setattr(self.module, k, v)


def _p1(task: dict) -> dict:
    family, closing, arm = task["family"], task["closing"], task["arm"]
    floor = 0.02 if arm == "noise" else float(arm[1:])
    data, st, ins, plan, kw = _protocol(family)
    if closing == "none":
        plan.closing_window_tol = None
    with _set(fwd, AXIAL_SIZING_FLOOR=floor):
        ref = rx.Refinement(st, ins, history=False)
        row = {"floor": floor}
        if arm == "noise":
            row["n_nudged"] = _nudged(ref)
        result = ref.fit(data, plan=plan, **kw)
    row.update(_result_row(result))
    return row


def _bar1(st, ins, data, kw, tol: float, margins) -> dict:
    """y at fixed parameters under each margin against MARGIN_REF: max |dy|/σ and where."""
    from rietx.params.vector import ParameterTable

    ys = {}
    for m in (*margins, MARGIN_REF):
        with _set(fwd, REFLECTION_MARGIN_DEG=m):
            model = fwd.compile_model(st, ins, data,
                                      two_theta_limits=kw.get("two_theta_limits"),
                                      window_area_tol=tol)
            table = ParameterTable(st, ins)
            ys[m] = np.asarray(model.evaluate(table.decode(table.x0())), dtype=float)
            tt, sig = np.asarray(model.tt), np.asarray(model.sigma, dtype=float)
    out = {}
    for m in margins:
        d = np.abs(ys[m] - ys[MARGIN_REF]) / sig
        j = int(np.argmax(d))
        out[str(m)] = [float(d[j]), float(tt[j])]
    return out


def _p2(task: dict) -> dict:
    family = task["family"]
    data, st, ins, plan, kw = _protocol(family)
    globs = sorted({g for s in plan.stages for g in s.turn_on})
    ref = rx.Refinement(st, ins, history=False)
    shipped = ref.fit(data, plan=plan, **kw)
    st0 = ref.fitted_structure.model_copy(deep=True)
    ins0 = ref.fitted_instrument.model_copy(deep=True)
    row = {"shipped": _result_row(shipped), "globs": globs, "polish": {}}
    margins = (0.25, 0.5, 5.0)
    row["bar1_closing_answer"] = {f"{tol:g}": _bar1(st0, ins0, data, kw, tol, margins)
                                  for tol in (fwd.WINDOW_AREA_TOL, 1e-3)}
    # the window-domain test's construction: the answer reached at 20 without the closing stage
    d2, s2, i2, p2, k2 = _protocol(family)
    p2.closing_window_tol = None
    with _set(fwd, REFLECTION_MARGIN_DEG=MARGIN_REF):
        r2 = rx.Refinement(s2, i2, history=False)
        r2.fit(d2, plan=p2, **k2)
    row["bar1_test_answer"] = _bar1(r2.fitted_structure, r2.fitted_instrument, d2, k2,
                                    fwd.WINDOW_AREA_TOL, margins)
    for arm in P2_ARMS:
        margin = 0.5 if arm == "noise" else float(arm[1:])
        pol = rx.RefinementPlan(stages=[rx.Stage("polish", globs)], closing_window_tol=1e-3)
        with _set(fwd, REFLECTION_MARGIN_DEG=margin):
            pref = rx.Refinement(st0.model_copy(deep=True), ins0.model_copy(deep=True),
                                 history=False)
            if arm == "noise":
                _nudged(pref)
            res = pref.fit(data, plan=pol, **kw)
        row["polish"][arm] = _result_row(res)
    return row


def _guarded_compile():
    refine_mod = importlib.import_module("rietx.refine")
    real = refine_mod.compile_model
    from rietx.schemas.plan import CLOSING_WINDOW_TOL

    def guarded(structure, instrument, pattern, **kw):
        if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
                and instrument.geometry.axial_sl.value > 1.0):
            raise _Runaway(f"closing compile refused at axial_sl "
                           f"{instrument.geometry.axial_sl.value:.4g}")
        return real(structure, instrument, pattern, **kw)

    return _set(refine_mod, compile_model=guarded)


def _p3(task: dict) -> dict:
    start = task["family"]
    ends: list[dict] = []

    def listen(event):
        if event["kind"] == "stage_end":
            d = event["data"]
            ends.append({"stage": d.get("stage"), "loss": d.get("window_loss"),
                         "status": d.get("status"), "n_it": d.get("n_iterations"),
                         "rwp": d.get("rwp"), "series_index": d.get("series_index")})

    row: dict = {"events": ends}

    def alarm(signum, frame):
        raise _Timeout(f"runaway guard {FIT_GUARD_S} s")

    old = signal.signal(signal.SIGALRM, alarm)
    signal.alarm(FIT_GUARD_S)
    try:
        with _guarded_compile():
            if start.startswith("chain"):
                from tests.test_acceptance_qpa_roundrobin import (
                    DATA,
                    SAMPLE1,
                    corundum_phase,
                    fluorite_phase,
                    qarr_instrument,
                    qpa_plan,
                    seed_scales,
                    zincite_phase,
                )

                def pre_2045(self):
                    stages = self.run_stages()
                    return [s.ftol if s.ftol is not None
                            else (None if i == len(stages) - 1 else self.intermediate_ftol)
                            for i, s in enumerate(stages)]

                st = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase()])
                ins = qarr_instrument()
                patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
                seed_scales(st, ins, patterns[0])
                ctx = (_set(rx.RefinementPlan, stage_ftols=pre_2045)
                       if start == "chain_pre2045" else _set(rx.RefinementPlan))
                with ctx:
                    series = rx.SequentialRefinement(st, ins)
                    series.fit(patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan(),
                               events=listen)
                row["results"] = [_result_row(r) for r in series.results_]
                row["png"] = _plot(series.results_[-1], f"p3_{start}")
            else:
                if start == "cpd1a_zircon":
                    data, st, ins, plan, kw = _zircon_declared()
                else:
                    family, factor = start.split("_x")
                    data, st, ins, plan, kw = _protocol(family)
                    _displaced(st, float(factor))
                ref = rx.Refinement(st, ins, history=False)
                result = ref.fit(data, plan=plan, events=listen, **kw)
                row.update(_result_row(result))
                row["png"] = _plot(result, f"p3_{start}")
    except (_Runaway, _Timeout) as exc:
        row["stopped"] = f"{type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    return row


def _report_read(ref, plan) -> dict:
    rep = ref.report(plan=plan)
    action = next((a for a in rep.suggested_actions if a.kind == "refine_axial_asymmetry"), None)
    asym = []
    for a in rep.attribution:
        if a.mean_two_theta >= DISPLAY_LIMIT_DEG:
            continue
        for c in a.coefficients:
            if c.kind == "asymmetry":
                asym.append([a.mean_two_theta, c.value, c.stderr, c.significant, a.gates_passed])
    active = sorted(((a.kind, a.confidence) for a in rep.suggested_actions if a.active),
                    key=lambda t: -t[1])
    return {"layer1": rep.layer1_available, "abstained": rep.abstained_reason,
            "action_active": bool(action and action.active),
            "action_confidence": None if action is None else action.confidence,
            "n_regions": len(rep.attribution),
            "n_gated": sum(1 for a in rep.attribution if a.gates_passed),
            "n_misfit": sum(1 for a in rep.attribution if a.has_significant_misfit),
            "asym_below_40": asym, "active": active[:4]}


def _p4_build(family: str, axial: bool):
    if family == "srm1976a":
        data, st, ins, plan, kw = _srm1976a(axial)
        return data, st, ins, plan, kw, axial
    data, st, ins, plan, kw = _protocol(family)
    if not axial:
        for stage in plan.stages:
            stage.turn_on = [g for g in stage.turn_on if "axial" not in g]
        plan.stages = [s for s in plan.stages if s.turn_on]
    return data, st, ins, plan, kw, False


def _p4(task: dict) -> dict:
    family, arm = task["family"], task["arm"]
    data, st, ins, plan, kw, tie = _p4_build(family, arm == "free")
    if arm == "zero":
        ins.geometry.axial_sl.value = 0.0
        ins.geometry.axial_hl.value = 0.0
    ref = rx.Refinement(st, ins, history=False)
    if tie:
        ref.tie_equal([SL, HL])
    result = ref.fit(data, plan=plan, **kw)
    row = _result_row(result)
    g = ref.fitted_instrument.geometry
    row["apertures"] = [g.axial_sl.value, g.axial_hl.value]
    row["png"] = _plot(result, f"p4_{family}_{arm}")
    if arm == "zero":
        report_mod = importlib.import_module("rietx.report")
        row["nominal"] = {}
        for v in NOMINALS:
            with _set(report_mod, NOMINAL_AXIAL_APERTURE=v):
                row["nominal"][f"{v:g}"] = _report_read(ref, plan)
        # the first value read again last: the reading must not depend on the order
        with _set(report_mod, NOMINAL_AXIAL_APERTURE=NOMINALS[0]):
            row["nominal_again"] = _report_read(ref, plan)
    return row


PARTS = {"p1": _p1, "p2": _p2, "p3": _p3, "p4": _p4}


def fit_one(task: dict) -> dict:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = dict(task)
    t0 = time.time()
    try:
        row.update(PARTS[task["part"]](task))
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        lines = str(exc).splitlines()
        row["error"] = f"{type(exc).__name__}: {lines[0] if lines else ''}"
    row["seconds"] = time.time() - t0
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
            "python": platform.python_version(), "numpy": md.version("numpy"),
            "kernels": md.version("rietx-kernels"), "workers": WORKERS}


def _key(t: dict) -> tuple:
    return (t["part"], t["family"], t.get("closing", ""), t.get("arm", ""))


def _tasks() -> list[dict]:
    tasks = [{"part": "p3", "family": s} for s in P3_STARTS]
    tasks += [{"part": "p2", "family": f} for f in FAMILIES]
    tasks += [{"part": "p4", "family": f, "arm": a} for f in P4_FAMILIES for a in ("zero", "free")]
    tasks += [{"part": "p1", "family": f, "closing": c, "arm": a}
              for f in FAMILIES for c in CLOSINGS for a in P1_ARMS]
    return tasks


def sweep(tasks: list[dict]) -> None:
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
            print(*_key(row), row.get("error") or row.get("stopped")
                  or f"{row.get('rwp', 0):.7f} {row.get('n_eval', '')} "
                     f"{row.get('status', '')} {row['seconds']:.0f}s", flush=True)


# -- summary ----------------------------------------------------------------

def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def _ordered(rows: dict) -> dict:
    if SL in rows and HL in rows and rows[SL][0] > rows[HL][0]:
        rows = dict(rows)
        rows[SL], rows[HL] = rows[HL], rows[SL]
    return rows


def _shift(cur: dict, ref: dict, background: bool = False):
    """Largest |cur − ref| over the larger plain esd, background rows or the rest."""
    cur, ref = _ordered(cur), _ordered(ref)
    worst = (0.0, None)
    for path, (value, e1) in cur.items():
        if path.startswith("instrument.background.") != background or path not in ref:
            continue
        v0, e0 = ref[path]
        esds = [e for e in (e0, e1) if e is not None and math.isfinite(e) and e > 0.0]
        if not esds:
            continue
        worst = max(worst, (abs(value - v0) / max(esds), path), key=lambda t: t[0])
    return worst


def _same(a: dict, b: dict) -> bool:
    return a["rows"] == b["rows"] and a["rwp"] == b["rwp"] and a["n_eval"] == b["n_eval"]


def _fires(stages: list[dict], factor: float, rule: str) -> list[str]:
    """Stages a STAGE_WINDOWS_STALE arm reports: threshold ``factor`` × tol, ``rule`` which."""
    if not stages:
        return []
    if rule == "every":
        reach = stages
    elif rule == "last":
        reach = stages[-1:]
    else:
        reach = (stages[-2:] if len(stages) > 1 and stages[-1]["name"] == "closing"
                 else stages[-1:])
    return [s["name"] for s in reach
            if s["loss"] is not None and s["loss"] > factor * s["tol"]]


def _event_stages(events: list[dict], index=None) -> list[dict]:
    out = []
    for e in events:
        if index is not None and e.get("series_index") != index:
            continue
        tol = 1e-3 if e["stage"] == "closing" else fwd.WINDOW_AREA_TOL
        out.append({"name": e["stage"], "loss": e["loss"], "tol": tol, "n_it": e["n_it"],
                    "status": e["status"]})
    return out


def _worst_loss(stages: list[dict]) -> str:
    worst = max(((s["loss"] / s["tol"], s["name"]) for s in stages if s["loss"] is not None),
                default=None)
    return "—" if worst is None else f"{worst[0]:.3g} ({worst[1]})"


ARM_SET = [(0.5, "shipped"), (1.0, "shipped"), (2.0, "shipped"), (1.0, "last"), (1.0, "every"),
           (0.5, "every")]


def summary() -> None:
    rows = [r for r in read_rows() if "part" in r]
    by = {_key(r): r for r in rows}
    meta = next((r["meta"] for r in rows if "meta" in r), {})
    lines = ["# WP-2017 group P, read from group_p.jsonl", "",
             f"head {meta.get('head', '?')[:9]}, {meta.get('platform', '?')}, numpy "
             f"{meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}, "
             f"{meta.get('workers', '?')} workers, 1 kernel thread a worker, compiled tier on.", "",
             f"{len(rows)} rows, {sum('error' in r for r in rows)} errors.", ""]
    errs = [r for r in rows if "error" in r]
    for r in errs:
        lines.append(f"- error: {_key(r)}: {r['error']}")
    if errs:
        lines.append("")

    # P1
    lines += ["## P1. `AXIAL_SIZING_FLOOR` from each protocol's start", "",
              "Shift: the largest move of a row that is not background against the same "
              "closing setting's shipped (0.02) arm, in plain esd over the larger esd; the "
              "background's beside.  'Same' is bit-identical rows, Rwp and evaluations.", "",
              "| family | closing | arm | Rwp | evaluations | shift esd | row | background esd | "
              "noise esd there | same as shipped | S/L, H/L | codes |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in FAMILIES:
        for c in CLOSINGS:
            ship = by.get(("p1", f, c, "f0.02"))
            noise = by.get(("p1", f, c, "noise"))
            for a in P1_ARMS:
                r = by.get(("p1", f, c, a))
                if r is None or "error" in r or ship is None or "error" in ship:
                    continue
                s, p = _shift(r["rows"], ship["rows"])
                b, _ = _shift(r["rows"], ship["rows"], background=True)
                nz = (_shift(noise["rows"], ship["rows"])[0]
                      if noise and "error" not in noise else None)
                ax = _ordered(r["rows"])
                axs = ", ".join(_fmt(ax[k][0], ".4f") for k in (SL, HL) if k in ax) or "—"
                lines.append(f"| {f} | {c} | {a} | {r['rwp']:.6f} | {r['n_eval']} | {_fmt(s)} | "
                             f"{p or '—'} | {_fmt(b)} | {_fmt(nz)} | "
                             f"{'yes' if _same(r, ship) else 'no'} | {axs} | "
                             f"{', '.join(r['codes'])} |")
    lines.append("")
    lines += ["The floors' gap with the closing stage against without, per family (0.05 and "
              "0.01 each against 0.02):", "",
              "| family | 0.05 none | 0.05 closing | 0.01 none | 0.01 closing | noise none | "
              "noise closing |", "|---|---|---|---|---|---|---|"]
    for f in FAMILIES:
        cells = []
        for a in ("f0.05", "f0.01", "noise"):
            for c in CLOSINGS:
                r, ship = by.get(("p1", f, c, a)), by.get(("p1", f, c, "f0.02"))
                ok = r and ship and "error" not in r and "error" not in ship
                cells.append(_fmt(_shift(r["rows"], ship["rows"])[0]) if ok else "—")
        lines.append(f"| {f} | " + " | ".join(cells) + " |")
    lines.append("")

    # P2
    lines += ["## P2. `REFLECTION_MARGIN_DEG`", "",
              "Bar 1, at fixed parameters: max |Δy|/σ against a 20° margin, and the 2θ where "
              "it sits.  'Test answer' is `test_window_domain`'s construction (the answer at "
              "20° without the closing stage, drawn at 2 %).", "",
              "| family | answer | windows | 0.25 | 0.5 (shipped) | 5 |", "|---|---|---|---|---|---|"]
    for f in FAMILIES:
        r = by.get(("p2", f, "", ""))
        if r is None or "error" in r:
            continue
        cells = [("closing", tol, r["bar1_closing_answer"][tol])
                 for tol in r["bar1_closing_answer"]]
        cells.append(("test", f"{fwd.WINDOW_AREA_TOL:g}", r["bar1_test_answer"]))
        for ans, tol, d in cells:
            lines.append(f"| {f} | {ans} | {tol} | " + " | ".join(
                f"{d[m][0]:.3f}σ at {d[m][1]:.2f}°" for m in ("0.25", "0.5", "5.0")) + " |")
    lines += ["", "Bar 2, from the shipped closing answer, one polish stage and the closing "
              "stage under each margin, against the shipped margin's polish:", "",
              "| family | arm | Rwp | evaluations | shift esd | row | background esd | "
              "shipped polish vs shipped fit | codes |",
              "|---|---|---|---|---|---|---|---|---|"]
    for f in FAMILIES:
        r = by.get(("p2", f, "", ""))
        if r is None or "error" in r:
            continue
        base = r["polish"]["m0.5"]
        for a in P2_ARMS:
            p = r["polish"][a]
            s, path = _shift(p["rows"], base["rows"])
            b, _ = _shift(p["rows"], base["rows"], background=True)
            ctl = _shift(base["rows"], r["shipped"]["rows"])[0] if a == "m0.5" else None
            lines.append(f"| {f} | {a} | {p['rwp']:.6f} | {p['n_eval']} | {_fmt(s)} | "
                         f"{path or '—'} | {_fmt(b)} | {_fmt(ctl)} | {', '.join(p['codes'])} |")
    lines.append("")

    # P3
    answers = {f: by.get(("p1", f, "closing", "f0.02")) for f in FAMILIES}
    lines += ["## P3. `STAGE_WINDOWS_STALE`", "",
              "Worst loss is the largest `window_loss` over the stage's own tolerance.  'Runs "
              "away' is a miss of the family's shipped closing answer (P1) by more than 0.1 "
              "plain esd on a row that is not background.  The arms list the stages each would "
              "report: threshold × tolerance, and which stages are read (shipped: the last, "
              "and the one before a closing stage).", "",
              "| fit | stopped | Rwp | Rwp / answer | to answer esd | row | worst loss / tol | "
              + " | ".join(f"{k}× {rule}" for k, rule in ARM_SET) + " | codes |",
              "|---|---|---|---|---|---|---|" + "---|" * len(ARM_SET) + "---|"]

    def p3_line(name, stages, r, fam, stopped):
        ans = answers.get(fam)
        if r is not None and "rows" in r and ans and "error" not in ans:
            s, path = _shift(r["rows"], ans["rows"])
            ratio = r["rwp"] / ans["rwp"]
            rwp = f"{r['rwp']:.5f}"
        else:
            s, path, ratio, rwp = None, None, None, "—"
        arms = [", ".join(_fires(stages, k, rule)) or "silent" for k, rule in ARM_SET]
        codes = ", ".join(r.get("codes", [])) if r else ""
        return (f"| {name} | {stopped or ''} | {rwp} | {_fmt(ratio)} | {_fmt(s)} | {path or '—'} "
                f"| {_worst_loss(stages)} | " + " | ".join(arms) + f" | {codes} |")

    for start in P3_STARTS:
        r = by.get(("p3", start, "", ""))
        if r is None or "error" in r:
            continue
        if start.startswith("chain"):
            for idx, lab in ((0, "cpd-1a"), (1, "cpd-1b warm")):
                st = _event_stages(r["events"], idx)
                res = r.get("results", [None, None])[idx] if r.get("results") else None
                lines.append(p3_line(f"{start} {lab}", st, res, None, r.get("stopped")))
        else:
            fam = start.split("_x")[0] if "_x" in start else "cpd1a"
            st = r.get("stages") or _event_stages(r["events"])
            lines.append(p3_line(start, st, r, fam, r.get("stopped")))
    lines += ["", "The population that reaches its answer, P1's 32 fits: the worst loss over "
              "tolerance on any stage, and on the stages the shipped rule reads.", "",
              "| family | closing | arm | worst any stage | worst read stage | fires (shipped) |",
              "|---|---|---|---|---|---|"]
    for f in FAMILIES:
        for c in CLOSINGS:
            for a in P1_ARMS:
                r = by.get(("p1", f, c, a))
                if r is None or "error" in r:
                    continue
                st = r["stages"]
                reach = (st[-2:] if len(st) > 1 and st[-1]["name"] == "closing" else st[-1:])
                lines.append(f"| {f} | {c} | {a} | {_worst_loss(st)} | {_worst_loss(reach)} | "
                             f"{', '.join(_fires(st, 1.0, 'shipped')) or 'silent'} |")
    lines.append("")

    # P4
    lines += ["## P4. `NOMINAL_AXIAL_APERTURE`", "",
              "Each family fitted with both apertures 0, the report read at each nominal "
              "value.  Gated: Layer 1's regions passing their gates, of all.  Own aperture: "
              "the protocol with the axial term free.", "",
              "| family | own S/L, H/L | zero-aperture Rwp | free Rwp | "
              + " | ".join(f"{v:g}" for v in NOMINALS) + " |",
              "|---|---|---|---|" + "---|" * len(NOMINALS)]
    order_notes: list[str] = []
    for f in P4_FAMILIES:
        z, fr = by.get(("p4", f, "", "zero")), by.get(("p4", f, "", "free"))
        if z is None or "error" in z:
            continue
        own = ", ".join(f"{x:.4f}" for x in fr["apertures"]) if fr and "error" not in fr else "—"
        frw = f"{fr['rwp']:.5f}" if fr and "error" not in fr else "—"
        cells = []
        for v in NOMINALS:
            n = z["nominal"][f"{v:g}"]
            fire = ("fires " + _fmt(n["action_confidence"], ".2f")) if n["action_active"] else "no"
            cells.append(f"{n['n_gated']}/{n['n_regions']}, {fire}")
        lines.append(f"| {f} | {own} | {z['rwp']:.5f} | {frw} | " + " | ".join(cells) + " |")
        again = z.get("nominal_again")
        if again is not None:
            same = again == z["nominal"][f"{NOMINALS[0]:g}"]
            order_notes.append(f"- {f}: {NOMINALS[0]:g} read again after the sweep is "
                               f"{'identical' if same else 'different'}")
    lines += ["", *order_notes, "", "Asymmetry coefficients below 40° (value(esd), * when the "
              "region passes its gates), per nominal value, and the actions active:", ""]
    for f in P4_FAMILIES:
        z = by.get(("p4", f, "", "zero"))
        if z is None or "error" in z:
            continue
        for v in NOMINALS:
            n = z["nominal"][f"{v:g}"]
            co = "; ".join(f"{tt:.1f}° {val:+.4f}({err:.4f}){'*' if g else ''}"
                           for tt, val, err, _sig, g in n["asym_below_40"]) or "none"
            top = ", ".join(f"{k} {c:.2f}" for k, c in n["active"]) or "none"
            ab = f"; Layer 1 abstains: {n['abstained']}" if n["abstained"] else ""
            lines.append(f"- {f} at {v:g}: {co}; active: {top}{ab}")
    lines.append("")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {SUMMARY}")


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "canary":
        sweep([{"part": "p1", "family": "fap", "closing": "none", "arm": a}
               for a in ("f0.02", "f0.05")] + [{"part": "p4", "family": "fap", "arm": "zero"}])
        return
    if mode in PARTS:
        sweep([t for t in _tasks() if t["part"] == mode])
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)

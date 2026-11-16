"""WP-2017 group G: the absent-phase hold's threshold, ``PHASE_SUPPORT_SIGMA`` (3).

Three audit rows read it: the constant ``schemas.plan.PHASE_SUPPORT_SIGMA`` and its two
defaults, ``PlanSpec:phase_support_sigma`` and ``Refinement.run_stage:phase_support_sigma``.
Their evidence owes two cases (WP-1523): a weighed phase near 1 wt %, and a minor phase
started one FWHM off its cell, the case PR #1050's B1.1 named, where a scale that reads
under 3 sigma holds the cell that keeps it there.

Arms, families and starts were fixed in WP-2017 § The list before anything ran
(families 2026-11-05, starts and arms 2026-11-16):

==============  ===============================================================
arm             what the fit runs with
==============  ===============================================================
``s3``          the shipped plan, ``phase_support_sigma`` 3
``s1``          ``phase_support_sigma`` 1
``off``         ``phase_support_sigma`` None: no hold, no release, no window
``window_off``  3, with the support-based cell window declaring no phase
                (group H's arm, as #1494 runs it on group A)
``noise``       3, every free start value nudged by 1e-12 relative (group A's
                noise arm): the scatter floor an arm's shift is read against
==============  ===============================================================

Starts, each a whole fit through the closing stage:

- ``cpd1a``, ``cpd1b``, ``cpd1c``: the IUCr CPD round-robin sample 1 under the QPA
  acceptance protocol (``tests/test_acceptance_qpa_roundrobin.py``: its phases,
  instrument, ``seed_scales`` and ``qpa_plan``), whose trace phases are weighed at
  1.15 wt % corundum, 1.36 wt % zincite and 1.36 wt % fluorite.  Reference: the weighed
  fractions.
- ``cpd1a_zircon``: cpd-1a with zircon declared, a phase weighed at zero (group A's
  start).  Reference: the weighed fractions, zircon 0.
- ``cucr_cold`` and ``cucr_hot``: the GSAS-II SeqRefine CuCr2O4 ramp's coldest and
  hottest frames (APS 11-BM, ``tests/data/seqrefine_cucr2o4/``), the model, instrument
  and plan of ``docs/wp/2081-batch/measure_real_ramp.py``'s default route (the two CIFs
  with O's stated negative Biso reset, the 11-BM ``.prm``, eight Chebyshev terms,
  ``mccusker_default``).  Reference: CuO at 1.1 wt % (Suchomel et al. 2012, § II, its
  temperature not stated) and, on the cold frame, the paper's 10 K Fddd cell (Table I).
- ``<start>_off`` for each start above but the zircon one: the trace or minor phase's
  cell lengths scaled by 1 + Δd/d so its strongest line moves one FWHM to low angle.
  The line is the phase's strongest primary-line reflection in the ``s3`` answer from the
  database start, and the FWHM is the instrument's at that line in that answer
  (``indexing.peaks.predicted_fwhm``: TCH from U, V, W, X, Y; sample broadening left
  out, so the displacement is at most one whole peak width).  Δd/d = FWHM / (2 tan θ),
  FWHM in radians.  The database start is what the off start is read against.

The ramp: the 17 frames chained by ``SequentialRefinement`` under ``mccusker_default``,
CuO started one FWHM off (the factor of ``cucr_cold_off``), on the arms ``s3``, ``s1``,
``off`` and ``window_off``, and once from the database cell at ``s3``.

Each fit records, per stage, the paths the support hold held (``StageResult.held`` less
the width twins and the scale-B holds), what it released, and what collapsed; the minor
phase's scale over its esd, its weight fraction and its cell; group H's window count (the
spy #1494 added to ``group_a.py``, copied here, that PR not being on ``main``); Rwp,
evaluations, status and the diagnostic codes.

    .venv/bin/python docs/wp/2017-batch/group_g.py          # the single fits, resumes
    .venv/bin/python docs/wp/2017-batch/group_g.py ramp     # the five chains, resumes
    .venv/bin/python docs/wp/2017-batch/group_g.py summary  # write group_g_summary.md
    .venv/bin/python docs/wp/2017-batch/group_g.py canary   # cpd1c and cucr_cold at s3

``WP2017G_RAW`` names the directory for the raw rows and the off starts (default
``~/.cache/rietx/wp-2017-g``); ``WP2017G_WORKERS`` the pool (default 4).  The figures go
to ``tests/output/wp2017_groupG_*.png``.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import importlib
import json
import math
import os
import platform
import signal
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

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.indexing.peaks import predicted_fwhm  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.optimize import least_squares as ls  # noqa: E402
from rietx.schemas.instrument import BackgroundChebyshev  # noqa: E402
from tests import test_window_domain as w  # noqa: E402
from tests.test_staged_start_invariance import _axial_pair_ordered  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = Path(os.environ.get("WP2017G_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-g"))
JSONL = RAW / "group_g.jsonl"
RAMP_JSONL = RAW / "group_g_ramp.jsonl"
SUMMARY = HERE / "group_g_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017G_WORKERS", "4"))

ARMS = {"s3": 3.0, "s1": 1.0, "off": None, "window_off": 3.0, "noise": 3.0}
RAMP_ARMS = ("s3", "s1", "off", "window_off")
#: start: (family, trace or minor phase, weighed or reference wt %)
STARTS = {"cpd1a": ("cpd-1a", "corundum"), "cpd1b": ("cpd-1b", "zincite"),
          "cpd1c": ("cpd-1c", "fluorite"), "cpd1a_zircon": ("cpd-1a", "zircon"),
          "cucr_cold": ("cucr", "CuO"), "cucr_hot": ("cucr", "CuO")}
OFF_STARTS = ("cpd1a", "cpd1b", "cpd1c", "cucr_cold", "cucr_hot")
CUCR = ROOT / "tests" / "data" / "seqrefine_cucr2o4"
CUO_WT = 1.1
#: Suchomel et al. (2012) Table I, 10 K, the paper's axis order; the tutorial's CIF has
#: b and c the other way round (``measure_real_ramp.report``)
FDDD_10K = {"a": 7.71271, "b": 8.53611, "c": 8.54357}
FIT_GUARD_S = 1200
NUDGE = 1e-12
COORDINATE_SCALE = 0.25
ESD_BAR = 0.1


class FitTimeout(BaseException):
    """Past the runaway guard.  A ``BaseException``, so no handler in the package eats it."""


@contextmanager
def guarded(seconds: int | None):
    """Raise :class:`FitTimeout` in this process's main thread after ``seconds``."""
    if seconds is None:
        yield
        return

    def alarm(signum, frame):
        raise FitTimeout

    was = signal.signal(signal.SIGALRM, alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, was)


@contextmanager
def window_off(on: bool):
    """The support-based cell window declaring no phase (#1494's ``CELL_WINDOW`` arm)."""
    if not on:
        yield
        return
    inner = ls._freeze_cell_windows

    def unwindowed(model, table, *args, **kwargs):
        table.freeze_cell_windows(set())

    ls._freeze_cell_windows = unwindowed
    try:
        yield
    finally:
        ls._freeze_cell_windows = inner


@contextmanager
def window_spied(records: list):
    """Group H's count, as #1494's ``group_a.window_spied``: per solve, which phases took the
    cell window, which free cell columns it bounded, and which of those ended on an edge
    (within 1e-9 of the window's width)."""
    from rietx.params import vector as pv

    rf = importlib.import_module("rietx.refine")
    inner_run = rf.run_least_squares

    def spy(model, table, *args, **kwargs):
        record: dict = {"stage": kwargs.get("stage", ""), "windowed": [], "applied": [],
                        "at_edge": [], "min_edge_fraction": None}
        edges: dict = {}
        freeze_now = ls._freeze_cell_windows

        def freeze(*fargs, **fkwargs):
            freeze_now(*fargs, **fkwargs)
            phases = getattr(table, "_cell_window_phases", None) or set()
            record["windowed"] = sorted(phases)
            by_path = {e.path: e for e in table.entries}
            for path in table.free_paths:
                name = pv._cell_parameter_name(path, phases=phases)
                if name is None:
                    continue
                e = by_path[path]
                lo, hi = pv.cell_window(name, e.value, e.lo, e.hi, path=path)
                if (lo, hi) != (e.lo, e.hi):
                    edges[path] = (lo, hi)
            record["applied"] = sorted(edges)

        ls._freeze_cell_windows = freeze
        try:
            outcome = inner_run(model, table, *args, **kwargs)
        finally:
            ls._freeze_cell_windows = freeze_now
        free = table.free_paths
        fractions = []
        for path, (lo, hi) in edges.items():
            value = float(outcome.theta[free.index(path)])
            fraction = min(value - lo, hi - value) / (hi - lo)
            fractions.append(fraction)
            if fraction <= 1e-9:
                record["at_edge"].append(path)
        record["min_edge_fraction"] = min(fractions) if fractions else None
        records.append(record)
        return outcome

    rf.run_least_squares = spy
    try:
        yield
    finally:
        rf.run_least_squares = inner_run


# -- starts ------------------------------------------------------------------------------


def _cpd(sample: str, zircon: bool = False) -> tuple:
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
    data = rx.read_pattern(DATA / f"{sample}.prn")
    phases = [corundum_phase(), zincite_phase(), fluorite_phase()]
    if zircon:
        phases.append(zircon_phase())
    st = rx.Structure(phases=phases)
    ins = qarr_instrument()
    seed_scales(st, ins, data)
    return data, st, ins, qpa_plan()


def _ramp_paths() -> list[Path]:
    return sorted(CUCR.glob("OH_*.fxye"))


def temperature(path: Path) -> float:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]:
        if "Temp (K)" in line:
            return float(line.split("=")[-1].split()[0])
    raise ValueError(f"no temperature in {path}")


def cucr_models() -> tuple:
    """``measure_real_ramp.models``: both CIFs, O's stated Biso reset, the 11-BM ``.prm``."""
    main = rx.Structure.from_cif(CUCR / "CuCr2O4.cif")
    minor = rx.Structure.from_cif(CUCR / "CuO.cif")
    st = main.model_copy(deep=True)
    st.phases = list(main.phases) + list(minor.phases)
    st.phases[0].name, st.phases[1].name = "CuCr2O4", "CuO"
    for phase in st.phases:
        for atom in phase.atoms:
            if atom.biso.value <= 0.0:
                atom.biso.value = 0.3
    st.phases[0].scale.value = 1.0
    st.phases[1].scale.value = 0.05
    ins = rx.read_gsas_prm(CUCR / "OH_00.prm")
    ins.background = BackgroundChebyshev.with_terms(8)
    return st, ins


def database_start(name: str) -> tuple:
    """(data, structure, instrument, plan) of a start from its database cell."""
    family, _ = STARTS[name]
    if family.startswith("cpd"):
        return _cpd(family, zircon=name.endswith("zircon"))
    paths = _ramp_paths()
    data = rx.read_pattern(paths[0] if name == "cucr_cold" else paths[-1])
    st, ins = cucr_models()
    return data, st, ins, rx.RefinementPlan.mccusker_default()


def _phase_index(st: rx.Structure, phase: str) -> int:
    return [p.name for p in st.phases].index(phase)


def displace(st: rx.Structure, phase: str, factor: float) -> None:
    """The phase's cell lengths × ``factor``, angles unchanged."""
    cell = st.phases[_phase_index(st, phase)].cell
    for length in (cell.a, cell.b, cell.c):
        length.value *= factor


def off_factor(ref: rx.Refinement, phase: str) -> dict:
    """1 + Δd/d moving ``phase``'s strongest line one instrument FWHM to low angle, read
    off the ``s3`` answer from the database start."""
    rows = [r for r in ref.reflection_table() if r.phase == phase and r.line == 0]
    top = max(rows, key=lambda r: r.intensity)
    fwhm = float(predicted_fwhm(np.array([top.two_theta]), ref.fitted_instrument)[0])
    theta = math.radians(top.two_theta / 2.0)
    rel = math.radians(fwhm) / (2.0 * math.tan(theta))
    return {"hkl": [top.h, top.k, top.l], "two_theta": top.two_theta, "fwhm": fwhm,
            "factor": 1.0 + rel}


# -- one fit -----------------------------------------------------------------------------


def _plan(plan, arm: str):
    return dataclasses.replace(plan, phase_support_sigma=ARMS[arm])


def _nudged(ref: rx.Refinement, plan) -> dict:
    """Group A's noise arm: every free start value × (1 + 1e-12)."""
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


def _support_held(stage) -> list[str]:
    """The stage's held paths less the width twins and the scale-B holds."""
    twins = {p for ps in (stage.width_twins_held or {}).values() for p in ps}
    twins |= set(stage.width_twins_held or {})
    scale_b = {f"phases.{i}." for i in (stage.scale_b_held or {})}
    return [p for p in stage.held if p not in twins
            and not (any(p.startswith(s) for s in scale_b) and ".biso" in p)]


def _phase_of(path: str) -> int | None:
    parts = path.split(".")
    return int(parts[1]) if parts[0] == "phases" and parts[1].isdigit() else None


def fit_record(result, fitted: rx.Structure | None, st_start: rx.Structure,
               minor: str) -> dict:
    """The JSON row of one fitted pattern.  The minor phase's cell is its rows where they
    are reported, else ``fitted``'s (a held cell leaves the rows), else ``None``."""
    ip = _phase_index(st_start, minor)
    rows = {p: list(v) for p, v in w._rows(result).items()}
    qpa = ({r.name: [r.weight_fraction, r.weight_fraction_stderr]
            for r in result.qpa.phases} if result.qpa is not None else None)
    scale = rows.get(f"phases.{ip}.scale")
    cell = [rows[f"phases.{ip}.cell.{n}"][0] if f"phases.{ip}.cell.{n}" in rows
            else None if fitted is None
            else getattr(fitted.phases[ip].cell, n).value for n in "abc"]
    cell = None if None in cell else cell
    stages = []
    for s in result.stages:
        held = _support_held(s)
        stages.append({"name": s.name, "status": s.status, "termination": s.termination,
                       "n_iterations": s.n_iterations, "support_held": held,
                       "held_phases": sorted({_phase_of(p) for p in held} - {None}),
                       "released": list(s.released), "collapsed": list(s.collapsed or [])})
    return {
        "rows": rows, "qpa": qpa, "rwp": result.statistics.rwp, "gof": result.statistics.gof,
        "status": result.status, "n_eval": int(sum(s.n_iterations for s in result.stages)),
        "stages": stages, "codes": sorted({d.code for d in result.diagnostics}),
        "minor": {"name": minor, "index": ip,
                  "scale": None if scale is None else scale[0],
                  "scale_esd": None if scale is None else scale[1],
                  "cell": cell,
                  "cell_start": [st_start.phases[ip].cell.a.value,
                                 st_start.phases[ip].cell.b.value,
                                 st_start.phases[ip].cell.c.value],
                  "held_at_answer": ip in stages[-1]["held_phases"]},
    }


def _error_line(exc: Exception) -> str:
    lines = str(exc).splitlines()
    return f"{type(exc).__name__}: {lines[0] if lines else ''}"


def start_for(name: str) -> tuple:
    """A start by name: a database start, or ``<db>_off`` with its factor applied."""
    base = name[:-4] if name.endswith("_off") else name
    data, st, ins, plan = database_start(base)
    extra = {}
    if base != name:
        extra = json.loads((RAW / f"off_{base}.json").read_text(encoding="utf-8"))
        displace(st, STARTS[base][1], extra["factor"])
    return data, st, ins, plan, extra


def fit_one(task: dict) -> dict:
    name, arm = task["start"], task["arm"]
    base = name[:-4] if name.endswith("_off") else name
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"start": name, "base": base, "arm": arm}
    try:
        data, st, ins, plan, extra = start_for(name)
        row["off"] = extra or None
        st0 = st.model_copy(deep=True)
        ref = rx.Refinement(st, ins, history=False)
        plan = _plan(plan, arm)
        if arm == "noise":
            row["nudge"] = _nudged(ref, plan)
        windows: list = []
        with guarded(FIT_GUARD_S), window_off(arm == "window_off"), window_spied(windows):
            result = ref.fit(data, plan=plan)
        row.update(fit_record(result, ref.fitted_structure, st0, STARTS[base][1]))
        row["cell_window"] = windows
        png = OUT / f"wp2017_groupG_{name}_{arm}.png"
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        row["png"] = str(png.relative_to(ROOT))
        if arm == "s3" and name in OFF_STARTS:
            (RAW / f"off_{name}.json").write_text(
                json.dumps(off_factor(ref, STARTS[name][1])), encoding="utf-8")
    except FitTimeout:
        row.update(status="timeout", error=f"FitTimeout: past {FIT_GUARD_S} s")
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = _error_line(exc)
    return row


def ramp_one(task: dict) -> dict:
    """One chain over the 17 frames."""
    arm, start = task["arm"], task["start"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"start": start, "arm": arm}
    try:
        paths = _ramp_paths()
        patterns = [rx.read_pattern(p) for p in paths]
        temps = [temperature(p) for p in paths]
        st, ins = cucr_models()
        if start == "off":
            row["off"] = json.loads((RAW / "off_cucr_cold.json").read_text(encoding="utf-8"))
            displace(st, "CuO", row["off"]["factor"])
        st0 = st.model_copy(deep=True)
        plan = _plan(rx.RefinementPlan.mccusker_default(), arm)
        series = rx.SequentialRefinement(st, ins)
        windows: list = []
        with window_off(arm == "window_off"), window_spied(windows):
            result = series.fit(patterns, x=temps, x_label="T (K)", plan=plan)
        frames = []
        for k, entry in enumerate(result.entries):
            fit = series.results_[k]
            if fit is None:
                frames.append({"T": entry.x, "status": entry.status, "rung": entry.rung})
                continue
            rec = fit_record(fit, None, st0, "CuO")
            rec.update(T=entry.x, rung=entry.rung, entry_status=entry.status)
            frames.append(rec)
        row.update(frames=frames, codes=sorted({d.code for d in result.diagnostics}),
                   cell_window=windows)
    except Exception as exc:  # noqa: BLE001
        row["error"] = _error_line(exc)
    return row


# -- running -----------------------------------------------------------------------------


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _append(row: dict, path: Path) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip() or "unknown"


def _meta() -> dict:
    import importlib.metadata as md

    return {"head": _head(), "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "rietx": rx.__version__,
            "numpy": md.version("numpy"), "kernels": md.version("rietx-kernels"),
            "workers": WORKERS}


def _run(tasks: list[dict], func, path: Path) -> None:
    done = {(r["start"], r["arm"]) for r in read_rows(path) if "error" not in r}
    todo = [t for t in tasks if (t["start"], t["arm"]) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=min(WORKERS, len(todo)),
                             mp_context=get_context("spawn")) as pool:
        futures = [pool.submit(func, t) for t in todo]
        for future in as_completed(futures):
            row = future.result()
            row["meta"] = _meta()
            _append(row, path)
            print(row["start"], row["arm"], row.get("status"), row.get("error", ""),
                  flush=True)


def sweep(only: tuple[str, ...] | None = None, arms: tuple[str, ...] | None = None) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    starts = only or tuple(STARTS)
    arms = arms or tuple(ARMS)
    # database starts first: each off start reads its s3 answer
    _run([{"start": s, "arm": a} for s in starts for a in arms], fit_one, JSONL)
    if only is None:
        _run([{"start": f"{s}_off", "arm": a} for s in OFF_STARTS for a in ARMS],
             fit_one, JSONL)


def ramp() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if not (RAW / "off_cucr_cold.json").exists():
        raise SystemExit("run the single fits first: the ramp's off start reads cucr_cold's")
    tasks = [{"start": "off", "arm": a} for a in RAMP_ARMS] + [{"start": "db", "arm": "s3"}]
    _run(tasks, ramp_one, RAMP_JSONL)


# -- reading -----------------------------------------------------------------------------


def _wt(row: dict, name: str) -> tuple[float | None, float | None]:
    if not row.get("qpa") or name not in row["qpa"] or row["qpa"][name][0] is None:
        return None, None
    v, e = row["qpa"][name]
    return 100.0 * v, None if e is None else 100.0 * e


def reference(row: dict) -> dict[str, float]:
    """{phase: reference wt %} for the row's family."""
    family = STARTS[row["base"]][0]
    if family == "cucr":
        return {"CuO": CUO_WT}
    from tests.test_acceptance_qpa_roundrobin import WEIGHED

    out = dict(WEIGHED[family])
    if row["base"].endswith("zircon"):
        out["zircon"] = 0.0
    return out


def shift(row: dict, base: dict) -> tuple[float, str | None, float, str | None]:
    cur, ref = _axial_pair_ordered(row["rows"]), _axial_pair_ordered(base["rows"])
    model = w._shift(cur, ref, background=False)
    bkg = w._shift(cur, ref, background=True)
    return model[0], model[1], bkg[0], bkg[1]


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None else format(x, spec)


def _held_text(row: dict) -> str:
    held = [s["name"] for s in row["stages"] if row["minor"]["index"] in s["held_phases"]]
    return ", ".join(held) if held else "none"


def _sig(row: dict) -> str:
    m = row["minor"]
    if m["scale_esd"] in (None, 0.0):
        return "held" if m["held_at_answer"] else "—"
    return format(m["scale"] / m["scale_esd"], ".1f")


def _cell_text(row: dict, db: dict | None) -> str:
    """The minor phase's cell, as the share of the start's displacement still left
    against the database start's ``s3`` answer."""
    m = row["minor"]
    if db is None or "minor" not in db:
        return "—"
    target = np.asarray(db["minor"]["cell"])
    start, got = np.asarray(m["cell_start"]), np.asarray(m["cell"])
    gap0 = float(np.max(np.abs(start - target)))
    if gap0 == 0.0:
        return f"{float(np.max(np.abs(got - target))):.2g} Å"
    return f"{float(np.max(np.abs(got - target))) / gap0:.3f}"


def summary() -> None:
    rows = read_rows(JSONL)
    fits = {(r["start"], r["arm"]): r for r in rows}
    meta = rows[-1]["meta"] if rows else {}
    lines = ["# WP-2017 group G, the absent-phase hold's threshold", "",
             f"Rows: {len(rows)} fits, head `{meta.get('head', '?')[:9]}`, "
             f"{meta.get('platform', '?')}, numpy {meta.get('numpy', '?')}, "
             f"rietx-kernels {meta.get('kernels', '?')}.  Written by `group_g.py summary`; "
             "the raw rows are not committed.", "",
             "Columns: the minor phase's scale over its esd at the answer; the stages that "
             "held it; its weight fraction and the reference; the share of the off start's "
             "cell displacement left against the database start's `s3` answer (0 recovered, "
             "1 never moved); Rwp; evaluations; the largest shift of any other row against "
             "the same start's `s3` arm, in plain esd (background rows apart); and whether "
             "`PHASE_UNCONSTRAINED` fired.", ""]
    head = ("| start | arm | minor | scale/esd | held in | wt % (ref) | cell left | Rwp | "
            "evals | shift vs s3 | bkg shift | PHASE_UNCONSTRAINED |")
    lines += [head, "|" + "---|" * 12]
    order = [s for s in STARTS] + [f"{s}_off" for s in OFF_STARTS]
    for start in order:
        base = start[:-4] if start.endswith("_off") else start
        db = fits.get((base, "s3"))
        for arm in ARMS:
            row = fits.get((start, arm))
            if row is None:
                continue
            if "error" in row:
                lines.append(f"| {start} | {arm} | | | | | | | | {row['error']} | | |")
                continue
            minor = row["minor"]["name"]
            wt, wte = _wt(row, minor)
            ref = reference(row).get(minor)
            s3 = fits.get((start, "s3"))
            sh = shift(row, s3) if s3 and "rows" in s3 and arm != "s3" else None
            lines.append(
                f"| {start} | {arm} | {minor} | {_sig(row)} | {_held_text(row)} | "
                f"{_fmt(wt, '.2f')}({_fmt(wte, '.2f')}) ({_fmt(ref, '.2f')}) | "
                f"{_cell_text(row, db) if start != base else '—'} | {row['rwp']:.4f} | "
                f"{row['n_eval']} | "
                f"{'—' if sh is None else f'{sh[0]:.3g} {sh[1]}'} | "
                f"{'—' if sh is None else f'{sh[2]:.3g}'} | "
                f"{'yes' if 'PHASE_UNCONSTRAINED' in row['codes'] else 'no'} |")
    lines += ["", "## Off starts", ""]
    for s in OFF_STARTS:
        path = RAW / f"off_{s}.json"
        if path.exists():
            o = json.loads(path.read_text(encoding="utf-8"))
            lines.append(f"- `{s}_off`: line {tuple(o['hkl'])} at {o['two_theta']:.4f}°, "
                         f"FWHM {o['fwhm']:.5f}°, cell × {o['factor']:.6f}")
    lines += ["", "## Every fit's weight fractions against the reference", ""]
    for start in order:
        for arm in ARMS:
            row = fits.get((start, arm))
            if row is None or "error" in row:
                continue
            ref = reference(row)
            parts = []
            for name, value in ref.items():
                wt, wte = _wt(row, name)
                parts.append(f"{name} {_fmt(wt, '.2f')}({_fmt(wte, '.2f')}) vs {value:.2f}")
            lines.append(f"- {start} {arm}: " + "; ".join(parts))
    lines += ["", "## Group H's count on these fits", ""]
    n_solves = n_win = n_applied = n_edge = 0
    for row in rows:
        for rec in row.get("cell_window", []):
            n_solves += 1
            n_win += bool(rec["windowed"])
            n_applied += bool(rec["applied"])
            n_edge += bool(rec["at_edge"])
    lines.append(f"{n_solves} solves over {len(rows)} fits: a phase windowed in {n_win}, a "
                 f"free cell column bounded in {n_applied}, an edge reached in {n_edge}.")
    ramp_rows = read_rows(RAMP_JSONL)
    if ramp_rows:
        lines += ["", "## The ramp, 17 frames chained", "",
                  "| start | arm | frames CuO held at the answer | CuO wt %, median (range) | "
                  "CuO cell left, last frame | frames rejected | codes |",
                  "|---|---|---|---|---|---|---|"]
        db = next((r for r in ramp_rows if r["start"] == "db"), None)
        for row in ramp_rows:
            if "error" in row:
                lines.append(f"| {row['start']} | {row['arm']} | {row['error']} | | | | |")
                continue
            frames = [f for f in row["frames"] if "minor" in f]
            held = sum(f["minor"]["held_at_answer"] for f in frames)
            wts = [_wt(f, "CuO")[0] for f in frames]
            wts = [x for x in wts if x is not None]
            last = frames[-1] if frames else None
            dbl = db["frames"][-1] if db and "frames" in db else None
            lines.append(
                f"| {row['start']} | {row['arm']} | {held} of {len(row['frames'])} | "
                f"{_fmt(float(np.median(wts)) if wts else None, '.2f')} "
                f"({_fmt(min(wts) if wts else None, '.2f')}-{_fmt(max(wts) if wts else None, '.2f')}) | "
                f"{_cell_text(last, dbl) if last and row['start'] == 'off' else '—'} | "
                f"{sum(f.get('entry_status') == 'quarantined' for f in row['frames'])} | "
                f"{', '.join(row['codes'])} |")
        rec = sum(len(r.get("cell_window", [])) for r in ramp_rows)
        app = sum(bool(x["applied"]) for r in ramp_rows for x in r.get("cell_window", []))
        lines.append("")
        lines.append(f"Group H on the ramp: {rec} solves, a free cell column bounded in {app}.")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    if argv[:1] == ["summary"]:
        summary()
    elif argv[:1] == ["ramp"]:
        ramp()
    elif argv[:1] == ["canary"]:
        sweep(only=("cpd1c", "cucr_cold"), arms=("s3",))
    else:
        sweep()


if __name__ == "__main__":
    main(sys.argv[1:])

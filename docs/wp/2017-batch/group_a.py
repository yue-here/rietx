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
    .venv/bin/python docs/wp/2017-batch/group_a.py --hard   # the hard starts, resumes
    .venv/bin/python docs/wp/2017-batch/group_a.py --hard summary
    .venv/bin/python docs/wp/2017-batch/group_a.py --window control  # group H's positive arm
    .venv/bin/python docs/wp/2017-batch/group_a.py --window summary  # rewrite group_h_summary.md

Since 2026-11-09 (``WP2017_RAW`` names where the rows go, ``WP2017_WORKERS`` the pool) the
hard starts run all ten constants, ``FTOL``, ``_CONVERGED_RUNS`` and ``_M_LO`` added for the
failing case they owed, and every fit of both sweeps carries group H's count
(``window_spied``): per solve, which phases took the support-based cell window, which free cell
columns it bounded and which ended on an edge.  Each start also runs one ``CELL_WINDOW`` arm,
``_freeze_cell_windows`` declaring no phase, read like any other arm.

``--hard`` runs the seven constants the shipped starts rarely reach, on their same arms,
from nine harder starts (WP-2017 § The list, "Group A's hard starts", fixed 2026-11-05
before running): each family's start with every phase's cell lengths ×1.01 and ×1.03,
and cpd-1a with zircon declared.  NAC is displaced after its Le Bail pass, since that
pass fixes the cell.  Scales stay as the family's start seeded them.  Each start gets the
shipped constants, the noise arm and the 15 arms, 153 fits.  It writes
``group_a_hard.jsonl`` and ``group_a_hard_summary.md`` and reads ``group_a.jsonl`` for
each family's answer.  In these rows ``family`` is the start's name and ``base`` the family.

``verdict`` reads a hard fit against the family's answer, the shipped constants from the
family's shipped start: every non-background row of that answer present and within 0.1
plain esd.  ``verdict.changed`` says whether the arm's verdict differs from the verdict
of the shipped constants from the same start.  ``measures`` reads the arm against the
shipped constants from the same start, and an arm's effect counts only past that
start's noise arm, since a hard start may land in a wrong basin and scatter there.  The
shipped arm of each start carries ``reach``, what the fit asked of each constant.  A fit
past ``FIT_GUARD_S`` of wall clock is a row with ``status`` "timeout": a runaway guard,
never a result.

The polish covers an arm over the bar or one changing a verdict, and the shipped arm of
any start with such an arm or a shipped verdict that fails.

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
import signal
import subprocess
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager, nullcontext
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
# The JSONL files are not committed; the 2026-11-05 rows sit in ~/.cache/rietx/wp-2017/ on the
# maintainer's machine.  ``WP2017_RAW`` names a directory outside the tree for the rows and the
# summaries they rewrite; a rerun's summaries are copied in by hand once read.
RAW = Path(os.environ.get("WP2017_RAW", HERE))
RAW.mkdir(parents=True, exist_ok=True)
JSONL = RAW / "group_a.jsonl"
SUMMARY = RAW / "group_a_summary.md"
HARD_JSONL = RAW / "group_a_hard.jsonl"
HARD_SUMMARY = RAW / "group_a_hard_summary.md"
WINDOW_SUMMARY = RAW / "group_h_summary.md"
OUT = ROOT / "tests" / "output"
FITS = OUT / "wp2017_groupA_fits"

WORKERS = int(os.environ.get("WP2017_WORKERS", "4"))
FAMILIES = ("fap", "nac", "cpd1a", "lab6")
SHIPPED = {"_M_HI": 10.0, "_M_LO": 0.4, "_Q_TRIGGER": 5, "_Q_WINDOW": 10,
           "_LAMBDA_FAIL_FACTOR": 10.0, "_LAMBDA_FAIL_FLOOR": 0.1, "_CONVERGED_RUNS": 3,
           "_CURVATURE_GATE": 100.0, "FTOL": 1e-9, "SLOW_DESCENT_ESD": 1.0}
ARMS = {"_M_HI": (5.0, 20.0), "_M_LO": (0.2, 0.8), "_Q_TRIGGER": (3, 7),
        "_Q_WINDOW": (5, 20), "_LAMBDA_FAIL_FACTOR": (5.0, 20.0),
        "_LAMBDA_FAIL_FLOOR": (0.01, 1.0), "_CONVERGED_RUNS": (2, 5),
        "_CURVATURE_GATE": (30.0, 1000.0), "FTOL": (1e-8, 1e-10),
        "SLOW_DESCENT_ESD": (0.5, 2.0, None),
        # group H (2026-11-09): the support-based cell window switched off, one arm
        "CELL_WINDOW": ("off",)}

#: since 2026-11-09 every constant runs from the hard starts: the seven of 2026-11-05, and
#: ``FTOL``, ``_CONVERGED_RUNS`` and ``_M_LO``, which gave one answer from the shipped starts and
#: owed the same nine starts for a failing case (WP-2017 § The list), and the group H arm
HARD_ARMS = ARMS
#: start name: (family, factor on every phase's cell lengths); no factor is zircon declared
HARD_STARTS = {**{f"{f}_x{x}": (f, x) for f in FAMILIES for x in (1.01, 1.03)},
               "cpd1a_zircon": ("cpd1a", None)}
#: a runaway guard, read between python bytecodes
FIT_GUARD_S = 1200

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
    if constant == "CELL_WINDOW":
        assert value == "off", value
        inner = ls._freeze_cell_windows

        def unwindowed(model, table, *args, **kwargs):
            table.freeze_cell_windows(set())

        ls._freeze_cell_windows = unwindowed
        try:
            yield
        finally:
            ls._freeze_cell_windows = inner
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


@contextmanager
def window_spied(records: list):
    """Group H's count: per solve a stage runs, which phases took the cell window, which free
    cell columns it bounded, and which of those ended on an edge.

    ``refine`` holds ``run_least_squares`` by name, so the spy sits there; the window is frozen
    once inside each call (``least_squares._freeze_cell_windows``), at the values the solve
    starts from, so the edges are computed there with ``cell_window`` itself.  An edge is
    "reached" within 1e-9 of the window's width, the LM driver landing a value exactly on an
    active bound (root CLAUDE.md, WP-1938).
    """
    import importlib

    from rietx.params import vector as pv

    # ``rietx.refine`` the attribute is the function; the module is reached by name
    rf = importlib.import_module("rietx.refine")

    inner_run, inner_freeze = rf.run_least_squares, ls._freeze_cell_windows

    def spy(model, table, *args, **kwargs):
        record: dict = {"stage": kwargs.get("stage", ""), "windowed": [], "applied": [],
                        "at_edge": [], "min_edge_fraction": None}
        edges: dict = {}

        def freeze(*fargs, **fkwargs):
            inner_freeze(*fargs, **fkwargs)
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
            ls._freeze_cell_windows = inner_freeze
        free = table.free_paths
        fractions = []
        for path, (lo, hi) in edges.items():
            value = float(outcome.theta[free.index(path)])
            width = hi - lo
            fraction = min(value - lo, hi - value) / width
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
def lambda_spied():
    """Every λ update with what it read, the gate's reads and what each returned."""
    calls: list = []
    gates: list = []
    measured: list = []
    inner, moved, curvature = lm._next_lambda, lm._furthest_moved, lm._measured_curvature

    def spy(lam, r_u, q):
        out = inner(lam, r_u, q)
        calls.append((lam, r_u, q, out))
        return out

    def spy_moved(*args):
        gates.append(calls[-1][3])
        return moved(*args)

    def spy_curvature(*args):
        out = curvature(*args)
        measured.append(out)
        return out

    lm._next_lambda, lm._furthest_moved = spy, spy_moved
    lm._measured_curvature = spy_curvature
    try:
        yield calls, gates, measured
    finally:
        lm._next_lambda, lm._furthest_moved = inner, moved
        lm._measured_curvature = curvature


def reach_numbers(calls: list, gates: list, measured: list, solves: list) -> dict:
    """What a fit asked of each constant, ``group_a_reach.py``'s docstring naming the terms."""
    accepted = [c for c in calls if c[1] is not None]
    rejected = [c for c in calls if c[1] is None]
    damped = [c for c in accepted if c[0] > 0.0]
    return {
        "n_accepted": len(accepted), "n_rejected": len(rejected),
        "n_accepted_with_lambda_above_0": len(damped),
        "r_u_range_accepted": ([min(c[1] for c in accepted), max(c[1] for c in accepted)]
                               if accepted else None),
        "r_u_range_damped": ([min(c[1] for c in damped), max(c[1] for c in damped)]
                             if damped else None),
        "n_M_HI_reach": sum(c[1] > 5.0 for c in accepted),
        "n_M_LO_reach": sum(c[1] < 0.8 for c in damped),
        "max_q": max((c[2] for c in accepted), default=None),
        "max_lambda": max((c[3] for c in calls), default=None),
        "gate_lambdas": gates,
        "n_curvature_measured": sum(m is not None for m in measured),
        "max_stage_nfev": max((s["nfev"] for s in solves), default=None),
    }


def _start_path(family: str) -> Path:
    return FITS / f"start_{family}.pkl"


def _fit_path(constant: str, arm: str, family: str) -> Path:
    return FITS / f"{family}_{constant.lstrip('_')}_{arm}.pkl"


def _png(family: str, constant: str, arm: str) -> Path:
    group = "groupAhard" if family in HARD_STARTS else "groupA"
    return OUT / f"wp2017_{group}_{family}_{constant.lstrip('_')}_{arm}.png"


def build_start(family: str) -> str:
    """Pickle the family's start under the shipped constants; its sha256."""
    FITS.mkdir(parents=True, exist_ok=True)
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


def _displaced(st: rx.Structure, factor: float) -> None:
    """Every phase's cell lengths × ``factor``.  A tied length is stored and scaled too, so
    the table's tie reproduces it."""
    for phase in st.phases:
        for name in ("a", "b", "c"):
            length = getattr(phase.cell, name)
            length.value *= factor


def _zircon_declared() -> tuple:
    """As ``test_the_intermediate_tolerance_with_an_absent_phase_declared`` builds it."""
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


def build_hard_start(name: str) -> str:
    """Pickle a hard start; its sha256."""
    path = _start_path(name)
    if not path.exists():
        family, factor = HARD_STARTS[name]
        if factor is None:
            start = _zircon_declared()
        else:
            start = pickle.loads(_start_path(family).read_bytes())
            _displaced(start[1], factor)
        assert start[3].closing_window_tol == 1e-3, "the protocols ride the shipped stage"
        assert start[2].source.dispersion is None
        path.write_bytes(pickle.dumps(start))
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _error_line(exc: Exception) -> str:
    """The exception's type and first line."""
    lines = str(exc).splitlines()
    return f"{type(exc).__name__}: {lines[0] if lines else ''}"


def fit_arm(task: dict) -> dict:
    """One whole fit: the shipped arm, a constant's arm, or the nudged start."""
    family, constant, arm, value = task["family"], task["constant"], task["arm"], task["value"]
    hard = family in HARD_STARTS
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"family": family, "constant": constant, "arm": arm}
    try:
        data, st, ins, plan, kw = _start(family)
        ref = rx.Refinement(st, ins, history=False)
        extra = _nudged(ref, plan) if constant == "noise" else {}
        solves: list = []
        windows: list = []
        name = constant if constant in SHIPPED or constant == "CELL_WINDOW" else None
        lambdas = lambda_spied() if hard and constant == "shipped" else nullcontext()
        with guarded(FIT_GUARD_S if hard else None), patched(name, value), spied(solves), \
                window_spied(windows), lambdas as seen:
            result = ref.fit(data, plan=plan, **kw)
        extra["cell_window"] = windows
        assert hard or result.stages[-1].name == "closing"
        if seen is not None:
            extra["reach"] = reach_numbers(*seen, solves)
        if constant == "FTOL":
            received = {s["ftol"] for s in solves}
            assert value in received and SHIPPED["FTOL"] not in received, received
            extra["ftol_received"] = sorted(received)
        row = _result_row(family, constant, arm, result, ref, solves,
                          _png(family, constant, arm))
        row.update(extra)
    except FitTimeout:
        row.update(status="timeout", error=f"FitTimeout: past {FIT_GUARD_S} s")
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = _error_line(exc)
    if hard:
        row["base"] = HARD_STARTS[family][0]
    return row


def polish(task: dict) -> dict:
    """From an arm's answer, under the shipped constants, to a fixed point."""
    family, constant, arm = task["family"], task["constant"], task["arm"]
    hard = family in HARD_STARTS
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
            with guarded(FIT_GUARD_S if hard else None):
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
    except FitTimeout:
        out.update(status="timeout", error=f"FitTimeout: past {FIT_GUARD_S} s in one round")
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        out["error"] = _error_line(exc)
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


def read_rows(path: Path = JSONL) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _append(row: dict, path: Path = JSONL) -> None:
    with path.open("a", encoding="utf-8") as fh:
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


def _run(pool, func, tasks, done, read, path: Path = JSONL) -> None:
    futures = [pool.submit(func, t) for t in tasks if _key(t) not in done]
    for future in as_completed(futures):
        row = read(future.result())
        _append(row, path)
        done[_key(row)] = row
        print(_key(row), row.get("error") or round(row.get("rwp", math.nan), 6),
              flush=True)


def _polish_read(row: dict, shipped: dict, base: dict | None) -> dict:
    """A polished row against the shipped arm and the polished shipped arm."""
    versus = {"to_shipped": w._shift(_axial_pair_ordered(row["rows"]), _axial_pair_ordered(
        shipped["rows"]), background=False)}
    if base is not None and "error" not in base:
        versus["to_shipped_polished"] = w._shift(row["rows"], base["rows"], background=False)
        versus["to_shipped_polished_bkg"] = w._shift(row["rows"], base["rows"], background=True)
        versus["chi2_ratio_to_shipped_polished"] = row["cost_final"] / base["cost_final"]
    return {"kind": "polish_read", "family": row["family"], "constant": row["constant"],
            "arm": row["arm"], "versus": versus, "rwp": row["rwp"],
            "rounds": row["rounds"], "settled": row["settled"]}


def _hard_tasks() -> list[dict]:
    tasks = []
    for start in HARD_STARTS:
        for constant, values in HARD_ARMS.items():
            tasks += [{"family": start, "constant": constant, "arm": str(v), "value": v}
                      for v in values]
        tasks.append({"family": start, "constant": "noise", "arm": str(NUDGE), "value": None})
    return tasks


def verdict(row: dict, answer: dict, shipped: dict | None) -> dict:
    """Does the fit reach the family's answer, and does that differ from ``shipped``."""
    out: dict = {"reaches_answer": False, "to_answer_esd": None, "to_answer_path": None,
                 "missing": [], "unjudged": [], "rwp_to_answer": None, "changed": None}
    if "error" not in row:
        cur = _axial_pair_ordered(row["rows"])
        base = _axial_pair_ordered(answer["rows"])
        esd, path = w._shift(cur, base, background=False)
        model = [p for p in base if not p.startswith("instrument.background.")]
        missing = sorted(p for p in model if p not in cur)
        unjudged = sorted(
            p for p in model if p in cur and not any(
                e is not None and math.isfinite(e) and e > 0.0 for e in (cur[p][1], base[p][1])))
        out.update(reaches_answer=not missing and esd <= ESD_BAR, to_answer_esd=esd,
                   to_answer_path=path, missing=missing, unjudged=unjudged,
                   rwp_to_answer=row["rwp"] / answer["rwp"])
    if shipped is not None:
        out["changed"] = out["reaches_answer"] != shipped["verdict"]["reaches_answer"]
    return out


def _same_head(meta: dict) -> None:
    """Resume only rows from this head: an older head's rows carry no group H count, and an arm
    read against a shipped row from another tree measures the tree, not the constant."""
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert meta["head"] == head, (
        f"{RAW} holds rows from {meta['head'][:9]}, not {head[:9]}: point WP2017_RAW elsewhere")


def hard_sweep() -> None:
    OUT.mkdir(exist_ok=True)
    FITS.mkdir(exist_ok=True)
    assert compiled.available(), compiled.unavailable()
    first = read_rows()
    meta0 = next(r for r in first if r.get("kind") == "meta")
    _same_head(meta0)
    for family in FAMILIES:
        assert build_start(family) == meta0["starts"][family], f"{family}'s start moved"
    answers = {r["family"]: r for r in first
               if r.get("kind", "fit") == "fit" and r["constant"] == "shipped"}
    done = {_key(r): r for r in read_rows(HARD_JSONL)}
    if ("meta", "", "", "") in done:
        _same_head(done[("meta", "", "", "")])
    if ("meta", "", "", "") not in done:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        meta = {"kind": "meta", "family": "", "constant": "", "arm": "", "head": head,
                "version": rx.__version__, "platform": sys.platform,
                "threads": os.environ[COMPILED_THREADS_ENV],
                "starts": {s: build_hard_start(s) for s in HARD_STARTS}}
        _append(meta, HARD_JSONL)
        done[_key(meta)] = meta
    targets = {f: references(f) for f in FAMILIES}
    targets["nac"]["a_lebail"] = ("rows:phases.0.cell.a",
                                  _start("nac")[1].phases[0].cell.a.value)

    def shipped_of(start: str) -> dict | None:
        return done.get(("fit", start, "shipped", "shipped"))

    def read(row: dict) -> dict:
        shipped = shipped_of(row["family"])
        row["verdict"] = verdict(row, answers[row["base"]], shipped)
        if shipped is not None and "error" not in row and "error" not in shipped:
            row["measures"] = measure(row, shipped, targets[row["base"]])
        return row

    context = get_context("spawn")
    with ProcessPoolExecutor(WORKERS, mp_context=context) as pool:
        _run(pool, fit_arm,
             [{"family": s, "constant": "shipped", "arm": "shipped", "value": None}
              for s in HARD_STARTS], done, read, HARD_JSONL)
        _run(pool, fit_arm, _hard_tasks(), done, read, HARD_JSONL)

        fits = [r for r in done.values() if r.get("kind", "fit") == "fit"
                and r["constant"] != "shipped"]
        flagged = [r for r in fits if r.get("measures", {}).get("over_bar")
                   or r["verdict"]["changed"]]
        polish_tasks = [{"family": r["family"], "constant": r["constant"], "arm": r["arm"],
                         "kind": "polish"} for r in flagged if "error" not in r]
        wanted = {r["family"] for r in flagged}
        wanted |= {s for s in HARD_STARTS if not shipped_of(s)["verdict"]["reaches_answer"]}
        polish_tasks += [{"family": s, "constant": "shipped", "arm": "shipped", "kind": "polish"}
                         for s in sorted(wanted) if "error" not in shipped_of(s)]
        _run(pool, polish, polish_tasks, done, lambda r: r, HARD_JSONL)

    for key, row in list(done.items()):
        if (key[0] == "polish" and "error" not in row
                and ("polish_read", *key[1:]) not in done):
            start = row["family"]
            read_row = _polish_read(row, shipped_of(start),
                                    done.get(("polish", start, "shipped", "shipped")))
            answer = answers[HARD_STARTS[start][0]]
            read_row["versus"]["to_answer"] = w._shift(
                row["rows"], _axial_pair_ordered(answer["rows"]), background=False)
            read_row["versus"]["chi2_ratio_to_answer"] = row["cost_final"] / answer["cost_final"]
            _append(read_row, HARD_JSONL)
    hard_summary()


def sweep() -> None:
    OUT.mkdir(exist_ok=True)
    FITS.mkdir(exist_ok=True)
    assert compiled.available(), compiled.unavailable()
    done = {_key(r): r for r in read_rows()}
    if ("meta", "", "", "") in done:
        _same_head(done[("meta", "", "", "")])
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
            _append(_polish_read(row, shipped[family],
                                 done.get(("polish", family, "shipped", "shipped"))))
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


def _noise_floor(fits: list[dict]) -> dict:
    """Each start's noise arm, in plain esd against the same start's shipped arm."""
    return {r["family"]: r.get("measures", {}).get("model") for r in fits
            if r["constant"] == "noise"}


def _yes(flag) -> str:
    return "n/a" if flag is None else ("yes" if flag else "no")


def hard_summary() -> None:
    """Rewrite ``group_a_hard_summary.md`` from the JSONL, computing nothing new."""
    rows = read_rows(HARD_JSONL)
    fits = [r for r in rows if r.get("kind", "fit") == "fit"]
    noise = _noise_floor(fits)
    reaches = {r["family"]: r["verdict"]["reaches_answer"] for r in fits
               if r["constant"] == "shipped"}
    lines = ["# WP-2017 group A from hard starts, read from group_a_hard.jsonl", ""]
    meta = next((r for r in rows if r.get("kind") == "meta"), None)
    if meta is not None:
        lines += [f"head {meta['head'][:9]}, rietx {meta['version']}, {meta['platform']}, "
                  f"{meta['threads']} kernel thread per worker, compiled tier on, `[dev]`.", ""]
    planned = len(HARD_STARTS) * (2 + sum(len(v) for v in HARD_ARMS.values()))
    lines += [f"{len(fits)} of {planned} planned fits have a row, "
              f"{sum('error' in r for r in fits)} of them an error or a timeout.", "",
              "## Shipped constants from each start", "",
              "'Reaches' is the family's shipped answer within 0.1 plain esd on every "
              "non-background row.  'Noise' is the 1e-12 arm against this row, in plain esd.",
              "", "| start | reaches | to answer esd | path | Rwp | Rwp / answer | evaluations "
              "| noise esd | max r_u | max Q | max λ | rejected | longest stage | gate reads |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in fits:
        if r["constant"] != "shipped":
            continue
        v = r["verdict"]
        if "error" in r:
            lines.append(f"| {r['family']} | no | error: {r['error']} ||||||||||||")
            continue
        reach = r["reach"]
        lines.append(
            f"| {r['family']} | {_yes(v['reaches_answer'])} | {_fmt(v['to_answer_esd'], '.4g')} | "
            f"{v['to_answer_path']} | {r['rwp']:.6f} | {v['rwp_to_answer']:.6f} | {r['n_eval']} | "
            f"{_fmt(noise.get(r['family']), '.3g')} | "
            f"{_fmt(reach['r_u_range_accepted'] and reach['r_u_range_accepted'][1], '.3g')} | "
            f"{reach['max_q']} | {_fmt(reach['max_lambda'], '.3g')} | {reach['n_rejected']} | "
            f"{reach['max_stage_nfev']} | {len(reach['gate_lambdas'])} |")
    lines += ["", "## Per constant", "",
              "'Worst over noise' is the arm furthest from the same start's shipped arm among "
              "those past that start's noise arm.", "",
              "| constant | starts reached | worst esd | noise there | arm | start | path | "
              "verdict changes | worst where shipped reaches, noise there |",
              "|---|---|---|---|---|---|---|---|---|"]
    for constant in HARD_ARMS:
        arms = [r for r in fits if r["constant"] == constant]
        reached = sorted({r["family"] for r in arms
                          if "error" in r or not r.get("measures", {}).get("unreached", False)})
        over = [r for r in arms if "measures" in r and noise.get(r["family"]) is not None
                and r["measures"]["model"] > noise[r["family"]]]
        worst = max(over, key=lambda r: r["measures"]["model"], default=None)
        changes = [f"{r['family']} {r['arm']}" for r in arms if r["verdict"]["changed"]]
        sound = max((r for r in over if reaches[r["family"]]),
                    key=lambda r: r["measures"]["model"], default=None)
        tail = ("none" if sound is None else
                f"{sound['measures']['model']:.3g}, {noise[sound['family']]:.3g} "
                f"({sound['family']} {sound['arm']})")
        head = f"| {constant} | {len(reached)}: {', '.join(reached)} | "
        if worst is None:
            lines.append(head + f"none ||||| {', '.join(changes) or 'none'} | {tail} |")
            continue
        m = worst["measures"]
        lines.append(head + f"{m['model']:.4g} | {noise[worst['family']]:.3g} | {worst['arm']} | "
                     f"{worst['family']} | {m['model_path']} | {', '.join(changes) or 'none'} | "
                     f"{tail} |")
    lines += ["", "## Starts whose shipped fit misses the answer", "",
              "Esds on these answers can be huge or absent, so Rwp shows the scatter better.  "
              "One noise arm is one draw.", "",
              "| start | shipped Rwp | noise Rwp | reached arms' Rwp | polished shipped | "
              "polished noise | polished arms |", "|---|---|---|---|---|---|---|"]
    polished = [r for r in rows if r.get("kind") == "polish" and "error" not in r]

    def span(values: list[float]) -> str:
        return f"{min(values):.4f} to {max(values):.4f}" if values else "n/a"

    for start, good in reaches.items():
        if good:
            continue
        here = [r for r in fits if r["family"] == start and "error" not in r]
        pick = {r["constant"]: r["rwp"] for r in here if r["constant"] in ("shipped", "noise")}
        arms = [r["rwp"] for r in here if r["constant"] in HARD_ARMS
                and not r.get("measures", {}).get("unreached", False)]
        done = {(r["constant"]): r["rwp"] for r in polished
                if r["family"] == start and r["constant"] in ("shipped", "noise")}
        rest = [r["rwp"] for r in polished
                if r["family"] == start and r["constant"] in HARD_ARMS]
        lines.append(f"| {start} | {_fmt(pick.get('shipped'), '.4f')} | "
                     f"{_fmt(pick.get('noise'), '.4f')} | {span(arms)} | "
                     f"{_fmt(done.get('shipped'), '.4f')} | {_fmt(done.get('noise'), '.4f')} | "
                     f"{span(rest)} |")
    lines += ["", "## Every arm", "",
              "| start | constant | arm | model esd | noise esd | path | bkg esd | Rwp ratio | "
              "eval ratio | conv | reached | reaches answer | changed | ref further esd | "
              "ref name |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in fits:
        if r["constant"] == "shipped":
            continue
        m, v = r.get("measures"), r["verdict"]
        head = f"| {r['family']} | {r['constant']} | {r['arm']} | "
        if m is None:
            lines.append(head + f"error: {r.get('error')} ||||||||| "
                         f"{_yes(v['reaches_answer'])} | {_yes(v['changed'])} |||")
            continue
        ref = m["reference"]
        lines.append(
            head + f"{m['model']:.4g} | {_fmt(noise.get(r['family']), '.3g')} | {m['model_path']} | "
            f"{m['background']:.4g} | {m['rwp_ratio']:.6f} | {m['eval_ratio']:.3f} | "
            f"{r['converged']} | {'unreached' if m['unreached'] else 'yes'} | "
            f"{_yes(v['reaches_answer'])} | {_yes(v['changed'])} | "
            f"{_fmt(ref['worst_further_esd'])} | {ref['worst_name']} |")
    reads = [r for r in rows if r.get("kind") == "polish_read"]
    polish_rows = [r for r in rows if r.get("kind") == "polish"]
    lines += ["", "## Polish", "",
              f"{len(polish_rows)} polishes, {sum('error' in r for r in polish_rows)} refused.",
              "", "| start | constant | arm | to shipped | to shipped polished | path | bkg | "
              "S/S polished | to answer | S/S answer | rounds | settled |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in reads:
        v = r["versus"]
        lines.append(
            f"| {r['family']} | {r['constant']} | {r['arm']} | {v['to_shipped'][0]:.4g} | "
            f"{_fmt(v.get('to_shipped_polished', [None])[0], '.4g')} | "
            f"{v.get('to_shipped_polished', [None, None])[1]} | "
            f"{_fmt(v.get('to_shipped_polished_bkg', [None])[0], '.4g')} | "
            f"{_fmt(v.get('chi2_ratio_to_shipped_polished'), '.7f')} | "
            f"{v['to_answer'][0]:.4g} | {_fmt(v.get('chi2_ratio_to_answer'), '.7f')} | "
            f"{r['rounds']} | {r['settled']} |")
    HARD_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


WINDOW_CONTROL_JSONL = RAW / "group_h_control.jsonl"


def window_control() -> None:
    """The count's positive arm: LaB₆ +1 % with the absent-phase hold off at each stage's start,
    so the unseen phase's cell is a free column the window must bound.  An arm the count cannot
    fail on would confirm whatever it read (memory: controls need a positive arm)."""
    import importlib

    rf = importlib.import_module("rietx.refine")
    inner = rf._unsupported_phase_paths

    def no_start_hold(*args, **kwargs):
        return inner(*args, **kwargs) if kwargs.get("at_answer") else []

    for family in FAMILIES:
        build_start(family)
    build_hard_start("lab6_x1.01")
    WINDOW_CONTROL_JSONL.unlink(missing_ok=True)
    rf._unsupported_phase_paths = no_start_hold
    try:
        for constant, arm, value in (("shipped", "no_start_hold", None),
                                     ("CELL_WINDOW", "no_start_hold_off", "off")):
            row = fit_arm({"family": "lab6_x1.01", "constant": constant, "arm": arm,
                           "value": value})
            row["kind"] = "control"
            _append(row, WINDOW_CONTROL_JSONL)
    finally:
        rf._unsupported_phase_paths = inner


def window_summary() -> None:
    """Rewrite ``group_h_summary.md``: group H's count over every fit of both JSONLs."""
    lines = ["# WP-2017 group H, the cell window, counted over group A's fits", ""]
    totals = {"fits": 0, "solves": 0, "windowed": 0, "applied": 0, "at_edge": 0}
    table = ["| rows | start | fits | solves | a phase windowed | a free cell windowed | "
             "on an edge | nearest edge, fraction of window | window off: reached | "
             "window off: model esd |", "|---|---|---|---|---|---|---|---|---|---|"]
    edges: list = []
    for label, path in (("shipped starts", JSONL), ("hard starts", HARD_JSONL)):
        rows = read_rows(path)
        meta = next((r for r in rows if r.get("kind") == "meta"), None)
        if meta is not None:
            lines.append(f"{label}: head {meta['head'][:9]}, rietx {meta['version']}, "
                         f"{meta['platform']}, {meta['threads']} kernel thread per worker.")
        every = [r for r in rows if r.get("kind", "fit") == "fit"]
        fits = [r for r in every if "cell_window" in r]
        totals["uncounted"] = totals.get("uncounted", []) + [
            f"{r['family']} {r['constant']} {r['arm']}: {r.get('error', 'no count recorded')}"
            for r in every if "cell_window" not in r]
        for start in dict.fromkeys(r["family"] for r in fits):
            here = [r for r in fits if r["family"] == start and r["constant"] != "CELL_WINDOW"]
            solves = [s for r in here for s in r["cell_window"]]
            windowed = [s for s in solves if s["windowed"]]
            applied = [s for s in solves if s["applied"]]
            at_edge = [s for s in solves if s["at_edge"]]
            edges += [(start, r["constant"], r["arm"], s["stage"], s["at_edge"])
                      for r in here for s in r["cell_window"] if s["at_edge"]]
            nearest = [s["min_edge_fraction"] for s in applied
                       if s["min_edge_fraction"] is not None]
            off = next((r for r in every if r["family"] == start
                        and r["constant"] == "CELL_WINDOW"), None)
            m = (off or {}).get("measures")
            if off is not None and "error" in off:
                m = None
            table.append(
                f"| {label} | {start} | {len(here)} | {len(solves)} | {len(windowed)} | "
                f"{len(applied)} | {len(at_edge)} | "
                f"{_fmt(min(nearest), '.3g') if nearest else 'n/a'} | "
                f"{'n/a' if m is None else ('no, bit-identical' if m['unreached'] else 'yes')} | "
                f"{'n/a' if m is None else _fmt(m['model'], '.3g')} |")
            for key, n in (("fits", len(here)), ("solves", len(solves)),
                           ("windowed", len(windowed)), ("applied", len(applied)),
                           ("at_edge", len(at_edge))):
                totals[key] += n
    lines += ["", f"{totals['fits']} fits (every arm but the window's own), "
              f"{totals['solves']} solves: a phase took the window in {totals['windowed']}, "
              f"a free cell column was windowed in {totals['applied']}, and a windowed cell "
              f"ended on an edge in {totals['at_edge']}.", "",
              "'Window off' is the arm with ``_freeze_cell_windows`` declaring no phase, read "
              "against the same start's shipped arm: 'no, bit-identical' means the same "
              "evaluations and the same answer to the bit.", "",
              f"Not counted (fits): {len(totals.get('uncounted', []))}, "
              + ("; ".join(totals.get("uncounted", [])) or "none") + ".", ""] + table
    controls = read_rows(WINDOW_CONTROL_JSONL)
    if controls:
        lines += ["", "## Positive arm", "",
                  "LaB₆ +1 % with the absent-phase hold off at every stage's start "
                  "(``window_control``).", "",
                  "| arm | solves | a phase windowed | a free cell windowed | on an edge | "
                  "nearest edge | Rwp | evaluations |", "|---|---|---|---|---|---|---|---|"]
        for r in controls:
            if "error" in r:
                lines.append(f"| {r['arm']} | error: {r['error']} |||||||")
                continue
            cw = r.get("cell_window", [])
            nearest = [s["min_edge_fraction"] for s in cw if s["min_edge_fraction"] is not None]
            lines.append(
                f"| {r['arm']} | {len(cw)} | {sum(bool(s['windowed']) for s in cw)} | "
                f"{sum(bool(s['applied']) for s in cw)} | {sum(bool(s['at_edge']) for s in cw)} | "
                f"{_fmt(min(nearest), '.3g') if nearest else 'n/a'} | "
                f"{_fmt(r.get('rwp'), '.6f')} | {r.get('n_eval')} |")
    if edges:
        lines += ["", "## Solves ending on a window edge", "",
                  "| start | constant | arm | stage | paths |", "|---|---|---|---|---|"]
        lines += [f"| {a} | {b} | {c} | {d} | {', '.join(e)} |" for a, b, c, d, e in edges]
    WINDOW_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["summary"]:
        summary()
    elif args == ["--hard"]:
        hard_sweep()
    elif args == ["--hard", "summary"]:
        hard_summary()
    elif args == ["--window", "control"]:
        window_control()
    elif args == ["--window", "summary"]:
        window_summary()
    else:
        sweep()

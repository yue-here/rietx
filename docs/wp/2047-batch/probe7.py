"""WP-2047 probe 7: windows recomputed at every evaluation, emulated on the
numpy path, against the shipped per-stage freeze.

The ``perEval`` arm wraps the two closures ``run_least_squares`` builds
(``least_squares._make_residual`` and ``_make_jacobian``).  Before each
residual and each Jacobian evaluation it sizes every phase's nuclear windows
and FCJ node counts at that evaluation's values, by ``forward.rewindow``'s
rule (copied below, up to the layout, so a guard can refuse a huge model
before it is built), and swaps in a new ``CompiledPhase`` for each phase whose
sizing changed.  The scalar memo is kept, since ``phase_peaks`` reads no
window; the FCJ memo is cleared where a node count moved, since its key does
not hold the count.  A third wrapper, around ``refine.run_least_squares``,
sizes the windows at the solve's start (so the width inequalities LM builds
from the windows see the start's) and again at its answer (so what
``_run_stage`` measures after the solve reads the answer's windows).  The
Jacobian's own finite-difference columns run on the windows of the point it
is taken at.  The magnetic family and the extra peaks keep the compile's
windows; none of the families here has either.  The compiled tier is left at
its default (on), which takes the layout per call.

Guards: any sizing whose total window points pass ``GUARD`` times the stage
compile's (50, or the environment's ``PROBE7_GUARD``), or whose padded batch
layout passes ``PAD_CAP`` entries, raises ``Abort`` (a sizing at runaway values paged this Mac once);
a closing compile at ``axial_sl`` > 1 raises it too, as in probe 4; and the
run stops at ``LIMIT`` wall seconds.

Modes:

- ``fit FAMILY ARM``: one fit; for ``hostile`` (pre-WP-2045 schedule) and
  ``hostile5`` (shipped schedule), cpd-1b's warm read-outs.
- ``time FAMILY [N]``: one of the four protocols, ``N`` (5) interleaved
  pairs; the answer rows, per-solve records and median seconds of each arm.
- ``step FAMILY``: from the ``perEval`` answer, for each free column, the
  smallest step that changes the sizing, and the jump in cost there at one
  θ (windows of either side), against the ``ftol`` 1e-9 that LM's
  convergence test resolves.  At the last declared stage and the closing one.

One JSON line out per run.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe7.py . fit hostile perEval
"""
import json
import os
import signal
import statistics
import sys
import time
from dataclasses import replace

import numpy as np

sys.path.insert(0, sys.argv[1])

import rietx as rx  # noqa: E402
from rietx.model import forward as fw  # noqa: E402
from rietx.optimize import least_squares as lsq  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402
from rietx.strategy.staged import RefinementPlan  # noqa: E402

refine_mod = sys.modules["rietx.refine"]
real_compile = refine_mod.compile_model
real_solve = refine_mod.run_least_squares
real_make_res = lsq._make_residual
real_make_jac = lsq._make_jacobian
LIMIT = 300  # wall seconds a run
# a sizing past this many times the compile's window points aborts, and so
# does one whose padded batch layout (rows x widest window) passes PAD_CAP
GUARD = float(os.environ.get("PROBE7_GUARD", "50"))
PAD_CAP = 2e7
SOLVES: list[dict] = []
LAST: dict[float, tuple] = {}  # window tol -> (model, table, theta) of the last solve
CURRENT: dict = {}


class Abort(BaseException):
    pass


def sizing(model, values):
    """``forward.rewindow``'s loop up to the layout: (win, fcj_n) per phase."""
    tol = model.window_area_tol
    sl = float(values.get("instrument.geometry.axial_sl", 0.0))
    hl = float(values.get("instrument.geometry.axial_hl", 0.0))
    if sl > 0.0 or hl > 0.0 or any(cp.fcj_n.any() for cp in model.phases):
        sl, hl = max(sl, fw.AXIAL_SIZING_FLOOR), max(hl, fw.AXIAL_SIZING_FLOOR)
    fcj_on = fw.fcj_live(sl, hl)
    closing = tol <= CLOSING_WINDOW_TOL or tol < fw.WINDOW_AREA_TOL
    tt = np.asarray(model.tt, dtype=np.float64)
    out = []
    for ip, cp in enumerate(model.phases):
        win = np.zeros_like(cp.win)
        fcj_n = np.zeros_like(cp.fcj_n)
        for il, (pos, w1, w2, _) in enumerate(model.phase_peaks(ip, values)):
            pos = np.asarray(pos, dtype=np.float64)
            if model.shape == "voigt":
                gamma, eta = fw.tch_gamma_eta(
                    np.asarray(w1, dtype=np.float64) * fw.GAUSS_FWHM_TO_SIGMA,
                    2.0 * np.asarray(w2, dtype=np.float64))
            else:
                gamma = np.asarray(w1, dtype=np.float64)
                eta = np.asarray(w2, dtype=np.float64)
            half = fw.window_fwhm_mult(eta, tol) * gamma + model.window_slack_deg
            if fcj_on:
                half = half + fw.fcj_extent_deg(pos, sl, hl)
            valid = np.isfinite(pos) & np.isfinite(half)
            pos_v = np.where(valid, pos, 0.0)
            half_v = np.where(valid, half, 0.0)
            i0 = np.searchsorted(tt, pos_v - half_v, side="left")
            i1 = np.searchsorted(tt, pos_v + half_v, side="right")
            i0[~valid] = 0
            i1[~valid] = 0
            win[il, :, 0], win[il, :, 1] = i0, i1
            if fcj_on:
                live = valid & (i1 > i0)
                fcj_n[il, live] = fw.fcj_node_counts(pos[live], gamma[live], sl, hl,
                                                     closing=closing)
        out.append((win, fcj_n))
    return out


def points(wins):
    return int(sum((w[..., 1] - w[..., 0]).sum() for w in wins))


def sync(model, values):
    """Size ``model``'s windows at ``values`` in place; True if any moved."""
    base = model.__dict__.setdefault("_probe7_base", points([cp.win for cp in model.phases]))
    sized = sizing(model, values)
    pts = points([w for w, _ in sized])
    widths = [w[..., 1] - w[..., 0] for w, _ in sized]
    pad = max(int((d > 0).sum()) * int(d.max(initial=0)) for d in widths)
    rec = CURRENT.get("rec")
    if rec is not None and pts / max(base, 1) > rec["max_ratio"]:
        rec["max_ratio"] = round(pts / max(base, 1), 3)
        rec["axial_at_max"] = round(values.get("instrument.geometry.axial_sl", 0.0), 5)
    if pts > GUARD * max(base, 1) or pad > PAD_CAP:
        raise Abort(f"stage {CURRENT.get('rec', {}).get('stage')!r}: sizing at {pts} window"
                    f" points (padded {pad}) against the compile's {base}"
                    f" (axial_sl {values.get('instrument.geometry.axial_sl', 0.0):.4g})")
    moved = False
    for ip, (win, fcj_n) in enumerate(sized):
        cp = model.phases[ip]
        same_n = np.array_equal(fcj_n, cp.fcj_n)
        if same_n and np.array_equal(win, cp.win):
            continue
        moved = True
        model.phases[ip] = replace(
            cp, win=win, fcj_n=fcj_n, batch=fw._batch_layout(win, fcj_n, model.tt),
            fcj_cache=(cp.fcj_cache if same_n
                       else ({} if (fcj_n.any() or cp.fcj_cache is not None) else None)))
    return moved


def table_values(model, table, theta):
    n = len(table.free_paths)
    return table.decode(np.asarray(theta)[:n])


def counted(kind, model, table, inner):
    def call(theta):
        rec = CURRENT.get("rec")
        t0 = time.perf_counter()
        moved = sync(model, table_values(model, table, theta))
        if rec is not None:
            rec["moved_" + kind] += moved
            rec["n_" + kind] += 1
            rec["sync_s"] += time.perf_counter() - t0
        return inner(theta)
    return call


def per_eval_residual(model, table):
    return counted("res", model, table, real_make_res(model, table))


def per_eval_jacobian(model, table):
    return counted("jac", model, table, real_make_jac(model, table))


def per_eval_solve(model, table, **kw):
    rec = {"stage": kw.get("stage", ""), "tol": model.window_area_tol,
           "ftol": kw.get("ftol"), "n_res": 0, "n_jac": 0, "moved_res": 0, "moved_jac": 0,
           "sync_s": 0.0, "max_ratio": 0.0}
    model.__dict__.setdefault("_probe7_base", points([cp.win for cp in model.phases]))
    rec["moved_start"] = bool(sync(model, table.decode(table.x0())))
    CURRENT["rec"] = rec
    try:
        out = real_solve(model, table, **kw)
    finally:
        CURRENT.pop("rec", None)
        SOLVES.append(rec)
    sync(model, table.decode(out.theta))
    rec.update(nfev=out.n_iterations, status=out.status, termination=out.termination,
               cost=out.cost_final)
    LAST[model.window_area_tol] = (model, table, np.array(out.theta))
    return out


def shipped_solve(model, table, **kw):
    out = real_solve(model, table, **kw)
    SOLVES.append({"stage": kw.get("stage", ""), "tol": model.window_area_tol,
                   "ftol": kw.get("ftol"), "nfev": out.n_iterations, "status": out.status,
                   "termination": out.termination})
    LAST[model.window_area_tol] = (model, table, np.array(out.theta))
    return out


def guarded_compile(structure, instrument, pattern, **kw):
    if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
            and instrument.geometry.axial_sl.value > 1.0):
        raise Abort(f"closing compile at axial_sl {instrument.geometry.axial_sl.value:.4g}")
    return real_compile(structure, instrument, pattern, **kw)


def arm_on(arm):
    refine_mod.compile_model = guarded_compile
    if arm == "perEval":
        lsq._make_residual = per_eval_residual
        lsq._make_jacobian = per_eval_jacobian
        refine_mod.run_least_squares = per_eval_solve
    else:
        refine_mod.run_least_squares = shipped_solve


def arm_off():
    refine_mod.compile_model = real_compile
    refine_mod.run_least_squares = real_solve
    lsq._make_residual = real_make_res
    lsq._make_jacobian = real_make_jac


def old_stage_ftols(self):
    stages = self.run_stages()
    endpoints = {len(stages) - 1}
    if len(stages) == len(self.stages):
        endpoints.add(len(self.stages) - 1)
    return [s.ftol if s.ftol is not None
            else (None if i in endpoints else self.intermediate_ftol)
            for i, s in enumerate(stages)]


def on_alarm(signum, frame):
    raise Abort(f"over {LIMIT} s")


def solve_summary(solves):
    keys = ("stage", "nfev", "status", "termination", "n_res", "n_jac",
            "moved_start", "moved_res", "moved_jac", "sync_s", "max_ratio", "axial_at_max")
    return [{k: s[k] for k in keys if k in s} for s in solves]


def hostile(family, arm):
    from rietx.viz.compare import qpa_plan
    from tests.test_acceptance_qpa_roundrobin import DATA, SAMPLE1, qarr_instrument, seed_scales
    from tests.test_acceptance_sequential import _phases
    if family == "hostile":
        RefinementPlan.stage_ftols = old_stage_ftols
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
    seed_scales(structure, ins, patterns[0])
    series = rx.SequentialRefinement(structure, ins)
    t0 = time.perf_counter()
    arm_on(arm)
    try:
        result = series.fit(patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan())
    except Abort as exc:
        return {"family": family, "arm": arm, "runaway": str(exc),
                "seconds": round(time.perf_counter() - t0, 1),
                "solves": solve_summary(SOLVES[-6:])}
    finally:
        arm_off()
    res = series.results_[1]
    vals = {p.path: p.value for p in res.parameters}
    return {"family": family, "arm": arm, "seconds": round(time.perf_counter() - t0, 1),
            "rung": result.entries[1].rung, "rwp_1b": round(res.statistics.rwp, 5),
            "axial_sl_1b": round(vals["instrument.geometry.axial_sl"], 5),
            "corundum_a_1b": round(vals.get("phases.0.cell.a", float("nan")), 5),
            "evals_1b": sum(s.n_iterations for s in res.stages),
            "stages_1b": [(s.name, s.status, s.n_iterations) for s in res.stages],
            "solves": solve_summary(SOLVES)}


def fit_protocol(family, arm):
    from tests import test_window_domain as w
    data, st, ins, plan, kw = w._protocol(family)
    SOLVES.clear()
    arm_on(arm)
    t0 = time.perf_counter()
    try:
        res = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
    finally:
        arm_off()
    return res, time.perf_counter() - t0, list(SOLVES)


def timed(family, n):
    from tests import test_window_domain as w
    times = {"shipped": [], "perEval": []}
    first = {}
    for _ in range(n):
        for arm in ("shipped", "perEval"):
            try:
                res, sec, solves = fit_protocol(family, arm)
            except Abort as exc:
                return {"family": family, "arm": arm, "aborted": str(exc),
                        "solves": solve_summary(SOLVES)}
            times[arm].append(sec)
            first.setdefault(arm, (res, solves))
    out = {"family": family}
    ref = w._rows(first["shipped"][0])
    for arm, (res, solves) in first.items():
        shift = w._shift(w._rows(res), ref, background=False)
        bshift = w._shift(w._rows(res), ref, background=True)
        out[arm] = {"rwp": round(res.statistics.rwp, 6),
                    "evals": sum(s.n_iterations for s in res.stages),
                    "stages": [(s.name, s.status, s.n_iterations) for s in res.stages],
                    "shift_esd": (round(shift[0], 4), shift[1]),
                    "bkg_shift_esd": (round(bshift[0], 4), bshift[1]),
                    "s_median": round(statistics.median(times[arm]), 3),
                    "s_range": (round(min(times[arm]), 3), round(max(times[arm]), 3)),
                    "solves": solve_summary(solves)}
    out["ratio"] = round(out["perEval"]["s_median"] / out["shipped"]["s_median"], 3)
    return out


def step(family):
    """The cost's jump where a window edge or node count crosses, per column."""
    fit_protocol(family, "perEval")
    out = {"family": family}
    for tol, (model, table, theta) in sorted(LAST.items()):
        res_fn = real_make_res(model, table)
        sync(model, table.decode(theta))
        r0 = res_fn(theta)
        cost0 = 0.5 * float(r0 @ r0)
        rows = []
        for c, path in enumerate(table.free_paths):
            scale = max(abs(theta[c]), 1e-3)
            lo_t = np.array(theta)
            hi_t = None
            d = 1e-12 * scale
            while d < 1e-1 * scale:
                t = np.array(theta)
                t[c] += d
                if [(w.tobytes(), f.tobytes()) for w, f in sizing(model, table.decode(t))] != \
                        [(cp.win.tobytes(), cp.fcj_n.tobytes()) for cp in model.phases]:
                    hi_t = t
                    break
                lo_t = t
                d *= 4.0
            if hi_t is None:
                rows.append((path, None, None))
                continue
            for _ in range(60):  # bisect to the crossing
                mid = 0.5 * (lo_t + hi_t)
                if [(w.tobytes(), f.tobytes()) for w, f in sizing(model, table.decode(mid))] == \
                        [(cp.win.tobytes(), cp.fcj_n.tobytes()) for cp in model.phases]:
                    lo_t = mid
                else:
                    hi_t = mid
            sync(model, table.decode(lo_t))
            r_lo = res_fn(hi_t)  # θ past the edge, windows from before it
            sync(model, table.decode(hi_t))
            r_hi = res_fn(hi_t)
            jump = 0.5 * (float(r_hi @ r_hi) - float(r_lo @ r_lo))
            rows.append((path, float(hi_t[c] - theta[c]), jump / cost0))
            sync(model, table.decode(theta))
        found = [r for r in rows if r[2] is not None]
        big = sorted(found, key=lambda r: -abs(r[2]))[:5]
        out[str(tol)] = {"cost": cost0, "cost_solve": next(
            (r["cost"] for r in reversed(SOLVES) if r["tol"] == tol and "cost" in r), None),
                         "n_cols": len(rows), "n_crossed": len(found),
                         "over_1e-9": sum(abs(r[2]) > 1e-9 for r in found),
                         "largest": [(p, f"{s:.3g}", f"{j:.3g}") for p, s, j in big],
                         "median_abs": (f"{statistics.median(abs(r[2]) for r in found):.3g}"
                                        if found else None)}
    return out


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, on_alarm)
    mode, fam = sys.argv[2], sys.argv[3]
    if mode == "fit":
        signal.alarm(LIMIT)
        print(json.dumps(hostile(fam, sys.argv[4])), flush=True)
    elif mode == "time":
        signal.alarm(LIMIT * 4)
        print(json.dumps(timed(fam, int(sys.argv[4]) if len(sys.argv) > 4 else 5)), flush=True)
    else:
        signal.alarm(LIMIT)
        print(json.dumps(step(fam)), flush=True)

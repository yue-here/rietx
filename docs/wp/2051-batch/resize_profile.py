"""WP-2051 task 1: where one resize's time goes, by part, per phase and line.

Runs probe 7's perEval fit once, recording every sizing call's (model, values),
then times each part of ``forward.rewindow``'s loop (and the whole of
``forward.window_sizing``, its tabled k(η), with the layouts a sync rebuilds) on up to NS evenly spaced
calls (min of REP repeats each).  Prints one JSON line.

On a tree from WP-2051's task 2 on, ``rewindow_whole`` times the tabled k(η);
the bisection's ``rewindow`` row in the WP's first table was measured at
b70ba5972, and ``kmult`` still times the bisection alone on any tree.

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2051-batch/resize_profile.py . FAMILY
"""
import json
import pathlib
import sys
import time

import numpy as np

root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "docs/wp/2047-batch"))
sys.argv = [sys.argv[0], str(root)] + sys.argv[2:]
import probe7  # noqa: E402

from rietx.model import forward as fw  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402

NS, REP = 40, 5
SAMPLES = []
real_sync = probe7.sync


def rec_sync(model, values):
    # the windows as this call finds them: probe 7's sync replaces phases in
    # place, so reading them off the model later gives the fit's last ones
    SAMPLES.append((model, dict(values), [(cp.win, cp.fcj_n) for cp in model.phases]))
    return real_sync(model, values)


probe7.sync = rec_sync


def tmin(fn):
    best = np.inf
    out = None
    for _ in range(REP):
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return best, out


def parts(model, values, seen):
    tol = model.window_area_tol
    sl = float(values.get("instrument.geometry.axial_sl", 0.0))
    hl = float(values.get("instrument.geometry.axial_hl", 0.0))
    if sl > 0.0 or hl > 0.0 or any(cp.fcj_n.any() for cp in model.phases):
        sl, hl = max(sl, fw.AXIAL_SIZING_FLOOR), max(hl, fw.AXIAL_SIZING_FLOOR)
    fcj_on = fw.fcj_live(sl, hl)
    closing = tol <= CLOSING_WINDOW_TOL or tol < fw.WINDOW_AREA_TOL
    tt = np.asarray(model.tt, dtype=np.float64)
    t = dict.fromkeys(("peaks_warm", "peaks_cold", "gamma_eta", "kmult", "extent",
                       "bounds", "nodes", "layout", "equal"), 0.0)
    per = []
    for ip, cp in enumerate(model.phases):
        tw, peaks = tmin(lambda: model.phase_peaks(ip, values))
        saved = cp.scalar_cache
        def cold():
            cp.scalar_cache = {} if saved is not None else None
            return model.phase_peaks(ip, values)
        tc, _ = tmin(cold)
        cp.scalar_cache = saved
        t["peaks_warm"] += tw
        t["peaks_cold"] += tc
        win = np.zeros_like(cp.win)
        fcj_n = np.zeros_like(cp.fcj_n)
        for il, (pos, w1, w2, _) in enumerate(peaks):
            pos = np.asarray(pos, dtype=np.float64)
            a, (gamma, eta) = tmin(lambda: model.peak_gamma_eta(w1, w2))
            b, k = tmin(lambda: fw.window_fwhm_mult(eta, tol))
            half = k * gamma + model.window_slack_deg
            c = 0.0
            if fcj_on:
                c, ext = tmin(lambda: fw.fcj_extent_deg(pos, sl, hl))
                half = half + ext
            valid = np.isfinite(pos) & np.isfinite(half)
            d, (i0, i1) = tmin(lambda: fw._window_bounds(tt, pos, half, valid))
            win[il, :, 0], win[il, :, 1] = i0, i1
            e = 0.0
            if fcj_on:
                live = valid & (i1 > i0)
                e, nn = tmin(lambda: fw.fcj_node_counts(pos[live], gamma[live], sl, hl,
                                                        closing=closing))
                fcj_n[il, live] = nn
            for key, v in zip(("gamma_eta", "kmult", "extent", "bounds", "nodes"),
                              (a, b, c, d, e)):
                t[key] += v
            per.append({"ip": ip, "il": il, "n_refl": int(len(pos)),
                        "kmult_ms": round(b * 1e3, 3), "bounds_ms": round(d * 1e3, 3),
                        "nodes_ms": round(e * 1e3, 3)})
        f, _ = tmin(lambda: fw._batch_layout(win, fcj_n, tt))
        g, _ = tmin(lambda: (np.array_equal(fcj_n, seen[ip][1]),
                             np.array_equal(win, seen[ip][0])))
        t["layout"] += f
        t["equal"] += g
    tr, _ = tmin(lambda: fw.rewindow(model, values))
    t["rewindow_whole"] = tr
    t["window_sizing"], sized = tmin(lambda: fw.window_sizing(model, values))
    t["sync_layouts"] = tmin(lambda: [
        fw._batch_layout(w, f, tt) for (w, f, _), (sw, sf) in zip(sized, seen)
        if not (np.array_equal(w, sw) and np.array_equal(f, sf))])[0]
    return t, per


def main(family):
    t0 = time.perf_counter()
    res, sec, solves = probe7.fit_protocol(family, "perEval")
    fit_s = time.perf_counter() - t0
    n = len(SAMPLES)
    idx = np.unique(np.linspace(0, n - 1, min(NS, n)).astype(int))
    tots = []
    per0 = None
    for i in idx:
        model, values, seen = SAMPLES[i]
        t, per = parts(model, values, seen)
        tots.append(t)
        per0 = per0 or per
    med = {k: round(float(np.median([t[k] for t in tots])) * 1e3, 3) for k in tots[0]}
    m0 = SAMPLES[0][0]
    out = {"family": family, "fit_s": round(fit_s, 2), "n_sync": n,
           "sync_s_probe": round(sum(s.get("sync_s", 0.0) for s in solves), 3),
           "n_phases": len(m0.phases), "n_lines": len(m0.phases[0].win),
           "n_points": int(len(m0.tt)), "ms_median": med, "per_line_first": per0}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main(sys.argv[2])

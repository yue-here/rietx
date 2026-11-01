"""WP-2051 probe 9: probe 7 with the fast sizing.

Probe 7's modes and arms, with its ``sizing`` (a copy of ``rewindow``'s loop
using the 60-step k(η) bisection) replaced by ``forward.window_sizing``, which
reads k(η) off a table.  Probe 7's ``sync`` already rebuilds the layout only
for a phase whose windows or node counts moved, and keeps the scalar memo.

``PROBE9_TAPER=w`` (0, off, by default) adds the taper to the perEval arm:
after each sizing, every phase's 0/1 window mask becomes mask·T(u), with
u = |2θ − pos|/half at that evaluation's values and T = 1 inside 1 − w, a
cos² ramp to 0 at the edge.  The mask multiplies the forward Ω and every
partial plane, so the residual is continuous where an edge crosses a point
and the Jacobian leaves out ∂T/∂θ alone.  FCJ node counts still step.
``PROBE9_TAPER_SIDE=out`` widens each window to (1 + w) times its half-width
and ramps over the added strip alone, so nothing inside the sized edge is
dropped; the FCJ node counts stay the unwidened sizing's, so a peak whose
window was empty there and reaches the range only through the added strip is
drawn symmetric (a code review's finding, left as recorded: such a peak sits
outside the range, and the out rows were measured with it).

    OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2051-batch/probe9.py . time cpd1a
"""
import json
import os
import pathlib
import signal
import sys
from dataclasses import replace

import numpy as np

root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "docs/wp/2047-batch"))
import probe7  # noqa: E402

from rietx.model import forward as fw  # noqa: E402

TAPER = float(os.environ.get("PROBE9_TAPER", "0"))
HALVES: dict[int, list] = {}  # id(model) -> the last sizing's half-widths, per phase


OUT = os.environ.get("PROBE9_TAPER_SIDE", "in") == "out"
# the ramp's share of the edge: the outer w of the half-width, or, outward,
# the strip from the half-width to (1 + w) times it
RAMP = TAPER / (1.0 + TAPER) if OUT else TAPER


def sizing(model, values):
    sized = fw.window_sizing(model, values)
    if OUT and TAPER > 0.0:
        tt = np.asarray(model.tt, dtype=np.float64)
        wide = []
        for ip, (win, fcj_n, half) in enumerate(sized):
            edge = (1.0 + TAPER) * half
            win = win.copy()
            for il, (pos, *_rest) in enumerate(model.phase_peaks(ip, values)):
                valid = np.isfinite(edge[il])
                i0, i1 = fw._window_bounds(tt, np.asarray(pos, dtype=np.float64),
                                           np.where(valid, edge[il], 0.0), valid)
                win[il, :, 0], win[il, :, 1] = i0, i1
            wide.append((win, fcj_n, edge))
        sized = wide
    HALVES[id(model)] = [h for _, _, h in sized]
    return [(w, f) for w, f, _ in sized]


def taper(u, w):
    """1 inside 1 - w, a cos² ramp to 0 at u = 1 with zero slope at both ends."""
    t = np.clip((u - (1.0 - w)) / w, 0.0, 1.0)
    return np.cos(0.5 * np.pi * t) ** 2


real_sync = probe7.sync


def _segments(start, count):
    """(rows, cols) of each row r's columns start[r] .. start[r] + count[r]."""
    rows = np.repeat(np.arange(len(count)), count)
    first = np.cumsum(count) - count
    cols = np.arange(int(count.sum())) - np.repeat(first, count) + np.repeat(start, count)
    return rows, cols


def tapered_sync(model, values):
    """Probe 7's sync, then every phase's mask tapered at ``values``.

    Only the ramp's points are touched: each row's columns between its
    window edge and (1 - w)·half, found by ``searchsorted``.  The 0/1 mask
    rides on the layout and is copied, a cost a taper inside ``_omega_batch`` would
    not pay.
    """
    moved = real_sync(model, values)
    halves = HALVES[id(model)]
    tt = np.asarray(model.tt, dtype=np.float64)
    for ip, cp in enumerate(model.phases):
        lay = cp.batch
        mask0 = lay.__dict__.setdefault("_probe9_mask0", lay.mask)
        pos = lay.gather(model.phase_peaks(ip, values), 0)
        h = halves[ip][lay.il, lay.k]
        ok = np.isfinite(pos) & np.isfinite(h)
        p, hh = np.where(ok, pos, 0.0), np.where(ok, h, 0.0)
        j0 = np.searchsorted(tt, p - (1.0 - RAMP) * hh, side="left")
        j1 = np.searchsorted(tt, p + (1.0 - RAMP) * hh, side="right")
        n_l = np.where(ok, np.clip(j0 - lay.i0, 0, lay.width), 0)
        n_r = np.where(ok, np.clip(lay.i1 - j1, 0, lay.width - n_l), 0)
        rows = np.concatenate([_segments(np.zeros_like(n_l), n_l)[0],
                               _segments(lay.width - n_r, n_r)[0]])
        cols = np.concatenate([_segments(np.zeros_like(n_l), n_l)[1],
                               _segments(lay.width - n_r, n_r)[1]])
        mask = mask0.copy()
        mask[rows, cols] = taper(np.abs(lay.x[rows, cols] - p[rows]) / hh[rows], RAMP)
        tapered = replace(lay, mask=mask)
        tapered.__dict__["_probe9_mask0"] = mask0
        model.phases[ip] = replace(cp, batch=tapered)
    return moved


probe7.sizing = sizing
if TAPER > 0.0:
    probe7.sync = tapered_sync

if __name__ == "__main__":
    signal.signal(signal.SIGALRM, probe7.on_alarm)
    mode, fam = sys.argv[2], sys.argv[3]
    if mode == "fit":
        signal.alarm(probe7.LIMIT)
        print(json.dumps(probe7.hostile(fam, sys.argv[4])), flush=True)
    elif mode == "time":
        signal.alarm(probe7.LIMIT * 4)
        print(json.dumps(probe7.timed(fam, int(sys.argv[4]) if len(sys.argv) > 4 else 5)),
              flush=True)
    else:
        signal.alarm(probe7.LIMIT)
        print(json.dumps(probe7.step(fam)), flush=True)

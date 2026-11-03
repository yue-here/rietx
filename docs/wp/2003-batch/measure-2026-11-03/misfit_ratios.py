"""WP-2003 brief 2: the Rwp ratio against a GoF ratio over the accepted median.

Arms: the planted 24-pattern series (four events), its null twin, the null twin
with its counts cut 4x from pattern 6 under a right model (WP-1469's shape), and
the planted transition alone.  The Rwp ratio is SeriesEntry.rwp_over_median as
the branch writes it; the GoF ratio is the same walk with GoF in Rwp's place.
"""
import os
import statistics
import sys
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
ROOT = Path("/Users/yuewu/Code/rietx/.claude/worktrees/wp2003-chain-actions")
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from rietx.schemas.sequential import _rejected  # noqa: E402
from tests.planted_series import default_events, generate, null_series, refine  # noqa: E402

N = 24


def gof_ratios(result):
    accepted, out = [], []
    for e in result.entries:
        g = e.statistics.gof if e.statistics else None
        out.append(None if g is None or not accepted else g / statistics.median(accepted))
        if g is not None and not _rejected(e):
            accepted.append(g)
    return out


def falling(series, at=6, factor=4.0, seed=5):
    rng = np.random.default_rng(seed)
    for k, p in enumerate(series.patterns):
        if k < at:
            continue
        y = rng.poisson(np.maximum(np.asarray(p.intensity) / factor, 0)).astype(float)
        series.patterns[k] = p.model_copy(update={
            "intensity": y.tolist(), "sigma": np.sqrt(np.maximum(y, 1.0)).tolist()})
    return series


def report(name, result, marks):
    rwp = [e.rwp_over_median for e in result.entries]
    gof = gof_ratios(result)
    def top(vals):
        idx = sorted((i for i, v in enumerate(vals) if v is not None),
                     key=lambda i: -vals[i])[:3]
        return ", ".join(f"{i}:{vals[i]:.2f}" for i in idx)
    print(f"{name:18s} Rwp top3 [{top(rwp)}]   GoF top3 [{top(gof)}]")
    for label, i in marks.items():
        r, g = rwp[i], gof[i]
        print(f"{'':18s}   {label} @{i}: Rwp ratio {r if r is None else round(r, 2)}, "
              f"GoF ratio {g if g is None else round(g, 2)}")
    codes = sorted({d.code for d in result.diagnostics})
    print(f"{'':18s}   series codes: {codes}")


ev = default_events(N)
report("planted", refine(generate(N, seed=0)), ev)
report("null", refine(null_series(N, seed=0)), {})
report("null, counts /4", refine(falling(null_series(N, seed=0))), {"drop": 6})
report("transition alone", refine(generate(N, seed=0, events={"transition": ev["transition"]})),
       {"transition": ev["transition"]})

"""Tables for part 2 from results/series_*.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from analyse_single import FAMS, family

HERE = Path(__file__).resolve().parent


def quantities(row):
    q = {p: v for p, v in row["params"].items() if ".cell." in p}
    for name, (w, we) in row["qpa"].items():
        if w is not None:
            q[f"W[{name}]"] = [w, we]
    return q


def table(name, out=sys.stdout):
    d = json.loads((HERE / "results" / f"series_{name}.json").read_text())
    runs = d["runs"]
    ref = next(r for r in runs if r["stop"] == "ftol1e-9" and r["seed"] is None)
    n = len(ref["rows"])
    keys = sorted(quantities(ref["rows"][0]))
    # neighbour differences at the reference
    print(f"\n## {name}: {n} patterns; reference rungs {sorted({r['rung'] for r in ref['rows']})}",
          file=out)
    print("| quantity | median |Δ| | median esd(Δ) | median |Δ|/esd(Δ) | min |Δ|/esd(Δ) |", file=out)
    print("|---|---|---|---|---|", file=out)
    diffs = {}
    for k in keys:
        v = np.array([quantities(r)[k][0] for r in ref["rows"]])
        e = np.array([quantities(r)[k][1] or np.nan for r in ref["rows"]])
        dv = np.diff(v)
        de = np.hypot(e[1:], e[:-1])
        diffs[k] = (dv, de)
        z = np.abs(dv) / de
        print(f"| {k} | {np.median(np.abs(dv)):.3g} | {np.nanmedian(de):.3g} | "
              f"{np.nanmedian(z):.3g} | {np.nanmin(z):.3g} |", file=out)
    print("\n| stop | evals total | evals last stage | rungs | max single-pattern dep (esd): "
          + " ".join(FAMS[:-1]) + " | max jitter in Δ cell (esd(Δ)) | max jitter in Δ W (esd(Δ)) |",
          file=out)
    print("|" + "---|" * 6, file=out)
    for r in runs:
        tag = r["stop"] if r["seed"] is None else f"nudge{r['seed']}"
        dep = {f: 0.0 for f in FAMS}
        for a, b in zip(ref["rows"], r["rows"]):
            for p, (v, e) in a["params"].items():
                if p in b["params"] and e:
                    f = family(p)
                    dep[f] = max(dep[f], abs(b["params"][p][0] - v) / e)
        jc, jw = 0.0, 0.0
        for k in keys:
            try:
                v = np.array([quantities(x)[k][0] for x in r["rows"]])
            except KeyError:
                continue
            dv0, de = diffs[k]
            j = np.nanmax(np.abs(np.diff(v) - dv0) / de)
            if k.startswith("W["):
                jw = max(jw, j)
            else:
                jc = max(jc, j)
        print(f"| {tag} | {r['nfev_total']} | {r['nfev_last_stage']} | "
              f"{sorted({x['rung'] for x in r['rows']})} | "
              + " ".join(f"{dep[f]:.2g}" for f in FAMS[:-1])
              + f" | {jc:.2g} | {jw:.2g} |", file=out)


if __name__ == "__main__":
    for nm in sys.argv[1:]:
        table(nm)

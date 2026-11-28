"""The three readings on the cpd-1 series (8 patterns chained by warm start).

A series answer is the concatenation of every pattern's parameters (and QPA
weight fractions), each in the esd that pattern's reference (ftol1e-9,
unnudged) fit reports.  Basins: single-linkage at 0.5 esd (max-norm) over the
reference's own answers (unnudged + seeds).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
sys.path.insert(0, str(HERE))
import analyse as A  # noqa: E402


def load():
    runs = {}
    for f in RES.glob("series_cpd1__*__*.json"):
        _, stop, seed = f.stem.split("__")
        runs[(stop, seed)] = json.loads(f.read_text())
    return runs


def flat(rec):
    v, e = {}, {}
    for row in rec["rows"]:
        lab = row["label"]
        for p, (x, s) in row["params"].items():
            v[f"{lab}:{p}"], e[f"{lab}:{p}"] = x, s
        for n, (w, we) in row["qpa"].items():
            v[f"{lab}:W[{n}]"], e[f"{lab}:W[{n}]"] = w, we
    return v, e


def main():
    runs = load()
    R = "ftol1e-9"
    vR, eR = flat(runs[(R, "none")])
    seeds = [s for s in map(str, range(10)) if (R, s) in runs]
    allR = [vR] + [flat(runs[(R, s)])[0] for s in seeds]
    lab = A.basins(allR, eR)
    cs = A.centres(allR, lab)
    disc = A.discriminators(cs, eR)
    print(f"reference {R}: {len(seeds)} nudges; clusters {len(cs)}, members "
          f"{[lab.count(c) for c in range(len(cs))]}; discriminators (>1 esd) {disc}")
    # floor vs K
    per = []
    for s in seeds:
        w, p = A.worst(A.dep(flat(runs[(R, s)])[0], vR, eR))
        per.append((s, w, p))
    for K in (3, 5, 10):
        sel = per[:K]
        if len(sel) == K:
            ws = [x[1] for x in sel]
            print(f"floor K={K}: max {max(ws):.3g} ({max(sel, key=lambda t: t[1])[2]}), P90 {np.percentile(ws, 90):.3g}")
    print("per-seed worst departure:", ", ".join(f"{s}:{w:.3g}" for s, w, _ in per))
    nfree = {s: [r["n_free"] for r in runs[(R, s)]["rows"]] for s in ["none"] + seeds}
    print("n_free per pattern identical across seeds:", len({tuple(v) for v in nfree.values()}) == 1)
    print()
    print("| stop | K | naive (param) | floor max | floor_sub | floor_cmp | floor_glob | paired max / median / min (param) | pairs used / split | evals total (ref ~) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for S in sorted({k[0] for k in runs} - {R}):
        if (S, "none") not in runs:
            continue
        for K in (5, 10):
            ks = [s for s in map(str, range(K)) if (S, s) in runs and (R, s) in runs]
            vS = flat(runs[(S, "none")])[0]
            d = A.dep(vS, vR, eR)
            naive, naive_p = A.worst(d)
            F = defaultdict(float)
            for s in ks:
                for p, z in A.dep(flat(runs[(R, s)])[0], vR, eR).items():
                    F[p] = max(F[p], z)
            fsub, fsub_p = A.worst({p: max(0.0, z - F[p]) for p, z in d.items()})
            fcmp = all(z <= max(A.BAR, F[p]) for p, z in d.items())
            fglob = max(0.0, naive - max(F.values()))
            shifts, split = [], 0
            for s in ks:
                a, b = flat(runs[(S, s)])[0], flat(runs[(R, s)])[0]
                if A.assign(a, cs, eR, disc) != A.assign(b, cs, eR, disc):
                    split += 1
                    continue
                shifts.append(A.worst(A.dep(a, b, eR)))
            sm = max(shifts) if shifts else (float("nan"), "")
            print(f"| {S} | {K} | {naive:.3g} {A.verdict(naive)} ({naive_p}) | {max(F.values()):.3g} | "
                  f"{fsub:.3g} {A.verdict(fsub)} ({fsub_p}) | {'pass' if fcmp else 'FAIL'} | "
                  f"{fglob:.3g} {A.verdict(fglob)} | {sm[0]:.3g} / {np.median([x[0] for x in shifts]):.3g} / "
                  f"{min(x[0] for x in shifts):.3g} {A.verdict(sm[0])} ({sm[1]}) | {len(shifts)} / {split} | "
                  f"{runs[(S, 'none')]['nfev_total']} ({runs[(R, 'none')]['nfev_total']}) |")
    print()
    # per-seed shifts for gsas, to show whether the crawl is start-dependent
    for S in ("gsas", "ftol1e-6", "numpy"):
        if (S, "none") not in runs:
            continue
        row = []
        for s in ["none"] + [str(k) for k in range(10)]:
            if (S, s) in runs and (R, s) in runs:
                w, p = A.worst(A.dep(flat(runs[(S, s)])[0], flat(runs[(R, s)])[0], eR))
                row.append(f"{s}:{w:.3g}({p.split(':')[0]}:{p.split(':')[1].split('.')[-1]})")
        print(S, "paired worst per seed:", "; ".join(row))


if __name__ == "__main__":
    main()

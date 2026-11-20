"""Summary across standards.  Baseline: the staged plan without a closing
stage (the default once WP-2222 lands; WP-2224 § Measured), from the standard's own start.

reached = Rwp within 3 % (relative) of the baseline Rwp.
"""
import json
import math
import statistics
import sys
from collections import defaultdict

rows = []
for path in sys.argv[1:]:
    rows += [json.loads(line) for line in open(path, encoding="utf-8")]
by = defaultdict(dict)
for r in rows:
    by[r["standard"]][(r["start"], r["arm"])] = r   # a later row replaces an earlier

STARTS = ["own", "warm", "edit", "cell+0.1", "cell-0.1", "cell+0.3", "wx4", "w/4"]
arms = []
for d in by.values():
    for (_, a) in d:
        if a not in arms:
            arms.append(a)


def gap(r, ref):
    worst, path, ppm = 0.0, "", 0.0
    for p, (v, e) in ref["params"].items():
        if p not in r.get("params", {}):
            continue
        v2 = r["params"][p][0]
        if ".cell." in p and v:
            ppm = max(ppm, abs(v2 - v) / abs(v) * 1e6)
        if e and math.isfinite(e) and e > 0:
            d = abs(v2 - v) / e
            if d > worst:
                worst, path = d, p
    return worst, path, ppm


def reached(r, base):
    return (not r.get("error")) and r["rwp"] <= 1.03 * base["rwp"]


print("reached / run, then the median over reaching standards of: time vs staged "
      "at the same start, evaluations vs staged, largest gap in esd, cell gap ppm\n")
for start in STARTS:
    print(f"start {start}")
    for arm in arms:
        n = ok = 0
        tr, er, gs, pp, fails = [], [], [], [], []
        for std, d in by.items():
            base = d.get(("own", "staged"))
            r = d.get((start, arm))
            st = d.get((start, "staged"))
            if not base or not r:
                continue
            n += 1
            if not reached(r, base):
                fails.append(std)
                continue
            ok += 1
            g, _, ppm = gap(r, base)
            gs.append(g)
            pp.append(ppm)
            if st and not st.get("error"):
                tr.append(r["seconds"] / st["seconds"])
                er.append(sum(r["nfev"]) / sum(st["nfev"]))
        if not n:
            continue
        med = lambda x: statistics.median(x) if x else float("nan")
        rng = lambda x: f"{min(x):.2f}-{max(x):.2f}" if x else "-"
        print(f"  {arm:18} {ok}/{n}  time {med(tr):4.2f} ({rng(tr)})  evals {med(er):4.2f}  "
              f"gap {med(gs):5.2f} (max {max(gs) if gs else float('nan'):6.2f}) esd  "
              f"cell {max(pp) if pp else float('nan'):6.1f} ppm max"
              + (f"   missed: {','.join(fails)}" if fails else ""))
    print()

print("absolute seconds, own start and warm")
for std, d in by.items():
    for start in ("own", "warm"):
        cells = [f"{a}={d[(start, a)]['seconds']:.2f}" for a in arms if (start, a) in d]
        print(f"  {std:15} {start:5} " + "  ".join(cells))

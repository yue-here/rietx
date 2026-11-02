"""Retrospective: how often would a GoF-ratio trigger fire on the WP-2003 families' kept fits?

Reads docs/wp/2003-batch/reseed/<family>_<arm>.json (per-pattern rwp, gof, rung) and, walking each
chain in its stored order, computes each warm pattern's GoF over a reference: ``median``, the
median GoF of the patterns accepted before it (the Rwp fence's median, in noise units), or
``seed``, the GoF of the last accepted pattern, which seeded its warm start in a forward chain.
The Rwp ratio over the same reference rides beside it.

    python retro_ratio.py docs/wp/2003-batch/reseed off,status,on median|seed
"""
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
arms = sys.argv[2].split(",")
ref = sys.argv[3]
for f in sorted(root.glob("*.json")):
    fam, _, arm = f.stem.rpartition("_")
    if f.stem.endswith("_nobound") or f.stem.endswith("_maxiter") or f.stem.endswith("_runaway") or f.stem.endswith("_seeded"):
        continue
    if arm not in arms:
        continue
    d = json.loads(f.read_text())
    pats = d["patterns"]
    acc_g, acc_r = [], []
    rows = []
    for p in pats:
        g, r = p.get("gof"), p.get("rwp")
        if g is None or r is None:
            continue
        if acc_g and p["rungs_tried"][0] != "cold":
            gr = g / (statistics.median(acc_g) if ref == "median" else acc_g[-1])
            rr = r / (statistics.median(acc_r) if ref == "median" else acc_r[-1])
            rows.append((p["label"], p["rung"], p["rungs_tried"], round(gr, 3), round(rr, 3), p["status"]))
        if p["status"] != "diverged":
            acc_g.append(g)
            acc_r.append(r)
    grs = [x[3] for x in rows]
    n = len(rows)
    over = {t: sum(1 for x in grs if x > t) for t in (1.25, 1.5, 2.0)}
    first_kept = [x for x in rows if len(x[2]) == 1]
    fk_over = {t: sum(1 for x in first_kept if x[3] > t) for t in (1.25, 1.5, 2.0)}
    print(f"{fam:16s} {arm:7s} warm={n:3d} gof_ratio max={max(grs) if grs else None} "
          f"over1.25/1.5/2.0={over[1.25]}/{over[1.5]}/{over[2.0]}  first-rung-kept={len(first_kept)} "
          f"over={fk_over[1.25]}/{fk_over[1.5]}/{fk_over[2.0]}")
    for x in rows:
        if x[3] > 1.25:
            print("     ", x)

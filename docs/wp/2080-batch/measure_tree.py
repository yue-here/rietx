"""Issue #1214 family, noise seeds 2-21 for pattern 1, on the tree with the GoF step in (WP-2080 task 5).

No patch: reads SeriesEntry.warm_gof_over_seed and .escalated_on_gof.  Needs the issue's ``repro.py``
(its <details> block) saved in the directory given as the first argument:
    python measure_tree.py <dir with repro.py> > seeds20.jsonl
"""
import json
import sys
import time

sys.path.insert(0, sys.argv[1])
import repro as R

import rietx as rx

TRUE_C = R.C + 0.002
rows = []
for seed in range(2, 22):
    p0 = R.simulate([R.hexp(R.A, R.C, 1.0, 0.03), R.orth(R.A + 0.005, R.A - 0.003, R.C - 0.01, 0.4, 0.05)], seed=1)
    p1 = R.simulate([R.hexp(R.A + 0.003, R.C + 0.002, 0.15, 0.03), R.orth(R.A + 0.04, R.A - 0.03, R.C - 0.06, 1.0, 0.45)], seed=seed)
    start = [R.hexp(R.A + 0.01, R.C + 0.01, 1e-4, 0.03), R.orth(R.A + 0.01, R.A, R.C, 1e-4, 0.01)]
    t = time.perf_counter()
    s = rx.SequentialRefinement(rx.Structure(phases=start), R.instrument(), carry=("*",), history=False).fit([p0, p1], x=[0.0, 1.0], plan=R.PLAN)
    e = s.entries[1]
    c = e.value("phases.0.cell.c")
    rows.append(dict(seed=seed, gof0=round(s.entries[0].statistics.gof, 4), gof1=round(e.statistics.gof, 4), ratio=round(e.warm_gof_over_seed, 4),
                     escalated=e.escalated_on_gof, rungs=e.rungs_tried, kept=e.rung, iters=e.n_iterations,
                     hex_c_err=c - TRUE_C, hex_c_esd=e.stderr("phases.0.cell.c"), wall=round(time.perf_counter() - t, 2)))
    print(json.dumps(rows[-1]), flush=True)
print("SUMMARY gof1>1.5:", sum(r["gof1"] > 1.5 for r in rows), "escalated:", sum(r["escalated"] for r in rows),
      "iters:", sum(r["iters"] for r in rows), "worst|c err|:", max(abs(r["hex_c_err"]) for r in rows),
      "max ratio unescalated:", max(r["ratio"] for r in rows if not r["escalated"]),
      "min ratio unescalated:", min(r["ratio"] for r in rows if not r["escalated"]))

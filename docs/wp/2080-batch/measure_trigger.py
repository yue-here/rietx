"""Issue #1214 family, noise seeds 2-21 for pattern 1: what each escalation trigger keeps.

Needs the issue's ``repro.py`` (its <details> block) saved in the directory given as the first
argument:  python measure_trigger.py <dir with repro.py> main|status|gof_seed|gof_med [factor]

Arms (each patches rietx.sequential._reseed_needed; the ladder, _prefer and the rest are main's):
  main      main's rule: diverged, or Rwp above 1.25 x the median accepted Rwp
  status    diverged only (PR #1310's C1 default, before its error-level clause)
  gof_seed  diverged, or GoF above F x the GoF of the pattern the warm start came from
  gof_med   diverged, or GoF above F x the median accepted GoF (the issue's option 1)
"""
import json
import statistics
import sys
import time

sys.path.insert(0, sys.argv[1])
import repro as R
import rietx as rx
import rietx.sequential as S

ARM = sys.argv[2]
if ARM not in ("main", "status", "gof_seed", "gof_med"):
    raise SystemExit(f"unknown arm {ARM!r}")
F =float(sys.argv[3]) if len(sys.argv) > 3 else 1.25
SEEDS = range(2, 22)
GOF = {}
_orig_entry = S._entry_from_result
_orig_need = S._reseed_needed


def _entry(*a, **k):
    e = _orig_entry(*a, **k)
    if e.statistics is not None:
        GOF[e.statistics.rwp] = e.statistics.gof
    return e


def _need(result, accepted_rwp, factor):
    if result.status == "diverged":
        return True
    if ARM == "main":
        return _orig_need(result, accepted_rwp, factor)
    if ARM == "status" or not accepted_rwp:
        return False
    g = result.statistics.gof
    if ARM == "gof_seed":
        return g > F * GOF[accepted_rwp[-1]]
    return g > F * statistics.median(GOF[r] for r in accepted_rwp)


S._entry_from_result = _entry
S._reseed_needed = _need

TRUE_HEX_C = R.C + 0.002
p0 = R.simulate([R.hexp(R.A, R.C, 1.0, 0.03), R.orth(R.A + 0.005, R.A - 0.003, R.C - 0.01, 0.4, 0.05)], seed=1)
rows = []
for seed in SEEDS:
    p1 = R.simulate([R.hexp(R.A + 0.003, R.C + 0.002, 0.15, 0.03), R.orth(R.A + 0.04, R.A - 0.03, R.C - 0.06, 1.0, 0.45)], seed=seed)
    start = [R.hexp(R.A + 0.01, R.C + 0.01, 1e-4, 0.03), R.orth(R.A + 0.01, R.A, R.C, 1e-4, 0.01)]
    GOF.clear()
    t = time.perf_counter()
    sr = rx.SequentialRefinement(rx.Structure(phases=start), R.instrument(), carry=("*",), history=False)
    series = sr.fit([p0, p1], x=[0.0, 1.0], plan=R.PLAN)
    wall = time.perf_counter() - t
    e0, e1 = series.entries
    r1 = sr.results_[1]
    c = next(p.value for p in r1.parameters if p.path == "phases.0.cell.c")
    rows.append(dict(seed=seed, gof0=e0.statistics.gof, gof1=e1.statistics.gof, rwp1=e1.statistics.rwp,
                     rungs=e1.rungs_tried, kept=e1.rung, iters=e1.n_iterations, hex_c=c,
                     hex_c_err=c - TRUE_HEX_C, wall=round(wall, 2)))
    print(json.dumps(rows[-1]), flush=True)
print("SUMMARY", ARM, F, "high(gof1>1.5)=", sum(r["gof1"] > 1.5 for r in rows),
      "escalated=", sum(len(r["rungs"]) > 1 for r in rows), "iters=", sum(r["iters"] for r in rows),
      "wall=", round(sum(r["wall"] for r in rows), 1))

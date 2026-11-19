"""Prototype: a width twin whose specimen half sits on its floor at stage start holds the
specimen half instead of the instrument column (scratch monkeypatch, no src change).

  swap.py OUT.jsonl std,std
Arms per standard (closing off unless 'shipped'): swap, swap+staged, swap+single, swap:shipped, swap:shipped+1
"""
import json, sys, time, warnings
import numpy as np
from rietx.refine import Refinement
from rietx.strategy.staged import RefinementPlan, Stage
from rietx.viz import compare
warnings.simplefilter("ignore")
RF = sys.modules["rietx.refine"]
SWAPS = []

def swap_hold(table, unseen):
    names = table.free_paths
    flats = RF._width_twin_flats([(table, np.arange(len(names)), unseen)], len(names))
    if not flats:
        return [], {}, {}
    x = table.x0(); lo, _ = table.bounds()
    cols, pairs = [], {}
    for c, ks in flats.items():
        if ks and all(x[k] <= lo[k] for k in ks):
            cols += list(ks); SWAPS.append(names[c])
        else:
            cols.append(c)
        pairs[names[c]] = [names[k] for k in ks]
    held = list(dict.fromkeys(names[c] for c in cols))
    reach = RF._reach_beyond_self(table, held)
    table.set_vary(held, False)
    return held, reach, pairs

RF._hold_width_twins = swap_hold
OUT = sys.argv[1]; ONLY = sys.argv[2].split(",")
dd = compare.default_data_dir()

def plan(std, closing, single=False):
    p = std.build(dd).plan
    if single:
        g = list(dict.fromkeys(x for s in p.stages for x in s.turn_on))
        p = RefinementPlan(stages=[Stage("all", g, seed=max(s.seed for s in p.stages))])
    if not closing:
        p.closing_window_tol = None
    return p

with open(OUT, "a") as fh:
    for std in compare.STANDARDS:
        if std.key not in ONLY: continue
        for closing in (False, True):
            inp = std.build(dd)
            ref = Refinement(inp.structure, inp.instrument, history=False)
            tag = "swap" + (":shipped" if closing else "")
            arms = [(tag, False), (tag + "+staged", False), (tag + "+single", True)]
            S0 = I0 = None
            for k, (arm, single) in enumerate(arms):
                if k == 2:
                    ref = Refinement(S0, I0, history=False)
                SWAPS.clear(); t0 = time.perf_counter()
                res = ref.fit(inp.data, plan=plan(std, closing, single), two_theta_limits=inp.two_theta_limits)
                dt = time.perf_counter() - t0
                if k == 0:
                    S0, I0 = ref.structure.model_copy(deep=True), ref.instrument.model_copy(deep=True)
                prof = ref.instrument.profile
                row = {"standard": std.key, "arm": arm, "seconds": dt, "rwp": res.statistics.rwp,
                       "chi2": res.statistics.chi2, "nfev": sum(s.n_iterations for s in res.stages),
                       "swapped": sorted(set(SWAPS)),
                       "held": [s.held for s in res.stages][-1],
                       "profile": {c: getattr(prof, c).value for c in "uvwxy"},
                       "codes": sorted({d.code for d in res.diagnostics if d.level in ("warning", "error")}),
                       "params": {p.path: [p.value, p.stderr] for p in res.parameters}}
                fh.write(json.dumps(row) + "\n"); fh.flush()
                print(f"{std.key:10s} {arm:22s} rwp={row['rwp']:.6f} chi2={row['chi2']:.6f} nfev={row['nfev']} "
                      f"swapped={row['swapped']} held={row['held']} prof={ {c: round(v, 5) for c, v in row['profile'].items()} }", flush=True)

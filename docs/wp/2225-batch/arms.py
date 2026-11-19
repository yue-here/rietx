"""One-change-at-a-time arms from a first staged fit's end point.

  arms.py STD ARM[,ARM...]   (closing stage off everywhere unless the arm says so)

Arms run from the first fit's converged models unless named first:*.
"""
import copy
import json
import sys
import warnings

from rietx.history.events import EventStream
from rietx.refine import Refinement
from rietx.strategy.staged import RefinementPlan, Stage
from rietx.viz import compare

warnings.simplefilter("ignore")
import os, sys as _s; _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spy
if os.environ.get("NOHOLD"):
    _rf = _s.modules["rietx.refine"]
    _rf._hold_width_twins = lambda table, unseen: ([], {}, {})
KEY = sys.argv[1]
ARMS = sys.argv[2].split(",")
std = next(s for s in compare.STANDARDS if s.key == KEY)
dd = compare.default_data_dir()
inp = std.build(dd)
kw = dict(two_theta_limits=inp.two_theta_limits)


def staged(closing=False):
    p = std.build(dd).plan
    if not closing:
        p.closing_window_tol = None
    return p


def globs(p):
    return list(dict.fromkeys(g for s in p.stages for g in s.turn_on))


def single(seed=None, ftol=None, max_iter=None):
    p = staged()
    s = Stage("all", globs(p), max_iter=max_iter or max(s.max_iter for s in p.stages),
              seed=max(s.seed for s in p.stages) if seed is None else seed, ftol=ftol)
    return RefinementPlan(stages=[s], closing_window_tol=None)


def build(arm):
    if arm == "staged":
        return staged()
    if arm == "shipped":
        return staged(True)
    if arm == "single":
        return single()
    if arm == "single:seed0":
        return single(seed=0.0)
    if arm.startswith("single:ftol"):        # single:ftol1e-14
        return single(ftol=float(arm[11:]), max_iter=2000)
    if arm == "staged:seed0":
        p = staged()
        for s in p.stages:
            s.seed = 0.0
        return p
    if arm.startswith("staged:upto"):        # staged:upto5 -> first 5 stages, then single
        n = int(arm[11:])
        p = staged()
        p.stages = p.stages[:n]
        return p
    if arm.startswith("staged:ftol"):        # staged:ftolI,F
        i, f = (float(x) for x in arm[11:].split(";"))
        p = staged()
        p.intermediate_ftol = i
        p.stages[-1].ftol = f
        return p
    if arm.startswith("sub:"):               # sub:glob|glob  one stage freeing only these
        return RefinementPlan(stages=[Stage("sub", arm[4:].split("|"))], closing_window_tol=None)
    raise KeyError(arm)


def lamtrace(log):
    out = []

    def cb(ev):
        if ev.get("kind") == "eval":
            d = ev["data"]
            out.append((d["stage"], round(d["cost"], 4), d["accepted"], f"{d['lam']:.3g}"))
    log.append(out)
    return EventStream(callback=cb)


def run(ref, arm, trace=False):
    log = []
    ev = lamtrace(log) if trace else None
    res = ref.fit(inp.data, plan=build(arm), events=ev, **kw)
    return res, (log[0] if log else None)


def summary(tag, res):
    st = res.stages
    return {"arm": tag, "rwp": res.statistics.rwp, "chi2": res.statistics.chi2,
            "stages": [(s.name, s.status, s.n_iterations, round(s.cost_initial, 3),
                        round(s.cost_final, 3), s.termination) for s in st],
            "params": {p.path: [p.value, p.stderr] for p in res.parameters}}


first_arm = "staged"
for a in ARMS:
    if a.startswith("first:"):
        first_arm = a[6:]
ref = Refinement(inp.structure, inp.instrument, history=False)
r1, _ = run(ref, first_arm)
S1, I1 = ref.structure.model_copy(deep=True), ref.instrument.model_copy(deep=True)
rows = [summary("first:" + first_arm, r1)]
print(f"first:{first_arm:22s} rwp={r1.statistics.rwp:.6f} chi2={r1.statistics.chi2:.6f}")
for arm in ARMS:
    if arm.startswith("first:"):
        continue
    if arm.startswith("passes"):
        rr = Refinement(S1, I1, history=False)
        for k in range(int(arm[6:])):
            res, _ = run(rr, "staged")
            v = {p.path: p for p in res.parameters}
            print(f"  pass {k+2}: rwp={res.statistics.rwp:.6f} chi2={res.statistics.chi2:.6f} "
                  f"u={v['instrument.profile.u'].value if 'instrument.profile.u' in v else None} "
                  f"v={v['instrument.profile.v'].value:.6g} x={v.get('instrument.profile.x').value if 'instrument.profile.x' in v else None} "
                  f"axial={v['instrument.geometry.axial_sl'].value:.6g}")
        continue
    trace = arm.endswith("!")
    arm = arm.rstrip("!")
    rr = Refinement(S1, I1, history=False)
    res, tr = run(rr, arm, trace)
    p0 = {p.path: (p.value, p.stderr) for p in r1.parameters}
    shifts = {k: (v.value - p0[k][0]) / p0[k][1] for k, v in
              ((p.path, p) for p in res.parameters) if k in p0 and p0[k][1]}
    big = sorted(shifts.items(), key=lambda kv: -abs(kv[1]))[:4]
    print(f"{arm:28s} rwp={res.statistics.rwp:.6f} chi2={res.statistics.chi2:.6f} "
          f"nfev={sum(s.n_iterations for s in res.stages)} "
          + " ".join(f"{k.split('.')[-1]}={v:+.2f}" for k, v in big))
    for s, rec in zip(res.stages, spy.LOG[-len(res.stages):]):
        print(f"     {s.name:18s} {s.status:9s} nfev={s.n_iterations:4d} "
              f"c {s.cost_initial:.4f}->{s.cost_final:.4f} {s.termination} | n={rec['n']} box={rec['active_box']} trunc={rec['trunc_by']} blocks={rec['blocks']}")
    if tr:
        for t in tr:
            print("       ", t)
    rows.append(summary(arm, res))
with open(f"{sys.argv[0].rsplit('/', 1)[0]}/arms_{KEY}.jsonl", "a") as fh:
    for r in rows:
        fh.write(json.dumps(r) + "\n")

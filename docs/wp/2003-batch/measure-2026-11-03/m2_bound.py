"""Measurement 2: FIRST_RUNG_SAMPLES in {1,2,3} x first_rung_factor in {2,3}.
Usage: python m2_bound.py thermal|planted [compiled|numpy]
n_evals = SeriesEntry.n_iterations (residual evaluations over every rung)."""
import json, sys, time
from common import *
from rietx import sequential
from rietx.sequential import SequentialRefinement

fam = sys.argv[1]
path = sys.argv[2] if len(sys.argv) > 2 else "compiled"
compiled.set_enabled(path == "compiled")
LOG = {}
CUR = {"label": None}

_orig_budget = sequential._first_rung_budget
_orig_cut = sequential._cut_by_bound
_orig_fit_one = SequentialRefinement._fit_one


RECS = []   # one record per warm pattern, in call order; label attached by the next _fit_one


def _budget(accepted_first, factor):
    b = _orig_budget(accepted_first, factor)
    RECS.append({"label": None, "armed": b is not None, "budget": b, "cut": False,
                 "n_sample": len(accepted_first)})
    return b


def _cut(result, plan, bounded):
    c = _orig_cut(result, plan, bounded)
    RECS[-1]["cut"] = RECS[-1]["cut"] or c
    return c


def _fit_one(self, data, label, *a, **k):
    if RECS and RECS[-1]["label"] is None:
        RECS[-1]["label"] = label
    return _orig_fit_one(self, data, label, *a, **k)


sequential._first_rung_budget = _budget
sequential._cut_by_bound = _cut
SequentialRefinement._fit_one = _fit_one

if fam == "thermal":
    from tests.test_sequential import A0, RAMP, _simulate, _start_models
    N = 10
    patterns = [_simulate(A0 * (1 + RAMP * k), seed=11 + k) for k in range(N)]
    labels = [f"p{k:03d}" for k in range(N)]

    def run(factor):
        st, ins = _start_models()
        return rx.refine_sequential(patterns, st, ins, labels=labels,
                                    plan="mccusker_default", first_rung_factor=factor)
else:
    from tests import planted_series as ps
    series = ps.generate(24, seed=0)
    N = 24
    _refine = ps.refine.__wrapped__    # the fixture's refine without its numpy_path pin

    def run(factor):
        was = compiled.set_enabled(path == "compiled")
        try:
            return _refine(series, first_rung_factor=factor)
        finally:
            compiled.set_enabled(was)


def snapshot(res):
    return {e.label: {"status": e.status, "rung": e.rung, "rungs_tried": list(e.rungs_tried),
                      "n": e.n_iterations,
                      "params": {p.path: (p.value, p.stderr) for p in e.parameters},
                      "diag": [d.code for d in e.diagnostics]} for e in res.entries}


def compare(ref, arm):
    ident, worst, worst_at, ch = True, 0.0, None, []
    for lab, r in ref.items():
        a = arm[lab]
        if (r["status"], r["rung"], r["rungs_tried"], r["diag"]) != \
                (a["status"], a["rung"], a["rungs_tried"], a["diag"]):
            ch.append([lab, [r["status"], r["rung"], r["rungs_tried"]],
                       [a["status"], a["rung"], a["rungs_tried"]]])
        if set(r["params"]) != set(a["params"]):
            ident = False
            ch.append([lab, "param set differs"])
        for p, (v, s) in r["params"].items():
            if p not in a["params"]:
                continue
            v2, _ = a["params"][p]
            if v2 != v:
                ident = False
                if s and s > 0:
                    z = abs(v2 - v) / s
                    if z > worst:
                        worst, worst_at = z, [lab, p]
    return {"bit_identical_values": ident and not ch, "values_identical": ident,
            "status_rung_changes": ch, "max_dvalue_esd": worst, "max_dvalue_at": worst_at}


out = {"env": env(), "family": fam, "path": path, "N": N, "arms": {}}
out["env"]["numeric_path"] = f"{path} (set_enabled({path == 'compiled'}))"
t0 = time.time()
RECS.clear()
ref_res = run(None)
ref = snapshot(ref_res)
ref_total = sum(v["n"] for v in ref.values())
out["reference"] = {"total_evals": ref_total, "per_pattern_evals": {k: v["n"] for k, v in ref.items()},
                    "rungs": {k: v["rungs_tried"] for k, v in ref.items()}}
print("reference", ref_total, round(time.time() - t0, 1), "s", flush=True)
ref2 = snapshot(run(None))
out["reference_repeat"] = compare(ref, ref2)
print("repeat", out["reference_repeat"], flush=True)
ORIG_N = sequential.FIRST_RUNG_SAMPLES
import os
FACTORS = [float(x) for x in os.environ.get("FACTORS", "2.0,3.0").split(",")]
SUFFIX = os.environ.get("SUFFIX", "")
out["factors"] = FACTORS
for factor in FACTORS:
    for ns in (1, 2, 3):
        sequential.FIRST_RUNG_SAMPLES = ns
        RECS.clear()
        t = time.time()
        res = run(factor)
        LOG.clear()
        LOG.update({r["label"]: r for r in RECS})
        snap = snapshot(res)
        cmp = compare(ref, snap)
        cut = sorted(l for l, r in LOG.items() if r.get("cut"))
        armed = sorted(l for l, r in LOG.items() if r.get("armed"))
        esc = sorted(l for l, v in snap.items() if len(v["rungs_tried"]) > 1)
        total = sum(v["n"] for v in snap.values())
        key = f"samples{ns}_factor{factor}"
        out["arms"][key] = {"samples": ns, "factor": factor, "n_armed": len(armed), "n_cut": len(cut),
                            "cut": cut, "n_escalated": len(esc), "escalated": esc,
                            "escalated_in_ref": sorted(l for l, v in ref.items() if len(v["rungs_tried"]) > 1),
                            "total_evals": total, "budgets": {l: LOG[l]["budget"] for l in armed},
                            "per_pattern_evals": {k: v["n"] for k, v in snap.items()},
                            "vs_ref": cmp, "seconds": round(time.time() - t, 1)}
        print(key, "armed", len(armed), "cut", len(cut), "esc", len(esc), "evals", total,
              "bit-identical", cmp["bit_identical_values"], "max dv esd", cmp["max_dvalue_esd"],
              cmp["max_dvalue_at"], flush=True)
sequential.FIRST_RUNG_SAMPLES = ORIG_N
out["seconds"] = round(time.time() - t0, 1)
json.dump(out, open(f"{MEASURE}/m2_{fam}_{path}{SUFFIX}.json", "w"), indent=1)

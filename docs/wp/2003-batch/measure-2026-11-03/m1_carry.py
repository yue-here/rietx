"""Measurement 1: carry_hkl_intensities True vs False, lebail and pawley.
Usage: python m1_carry.py thermal|planted   (n_evals = SeriesEntry.n_iterations,
residual evaluations summed over every rung of the ladder)."""
import json, sys, time
from common import *
from rietx.sequential import SequentialRefinement

fam = sys.argv[1]
out = {"env": env(), "family": fam, "arms": {}}
t0 = time.time()
if fam == "thermal":
    from tests.test_sequential import A0, RAMP, _simulate, _start_models
    N = 8
    patterns = [_simulate(A0 * (1 + RAMP * k), seed=11 + k) for k in range(N)]
    truth = [A0 * (1 + RAMP * k) for k in range(N)]
    make = lambda: _start_models()
    kw = dict(labels=[f"p{k:03d}" for k in range(N)])
else:
    from tests import planted_series as ps
    s = ps.generate(24, seed=0)
    patterns = s.patterns
    tr = s.events["transition"]
    truth = [s.cell[k][0] if k < tr else None for k in range(24)]
    make = lambda: ps.cubic_model(s.temperature[0])
    kw = dict(x=s.temperature, x_label="T (K)", labels=s.labels)
    out["events"] = s.events
for mode in ("lebail", "pawley"):
    for carry in (True, False):
        st, ins = make()
        sr = SequentialRefinement(st, ins, carry_hkl_intensities=carry)
        t = time.time()
        try:
            res = sr.fit(patterns, mode=mode, **kw)
            rows = [row(e, truth[e.index]) for e in res.entries]
            err = None
        except Exception as exc:
            rows, err = [], repr(exc)
        key = f"{mode}_carry{carry}"
        out["arms"][key] = {"rows": rows, "error": err, "seconds": round(time.time() - t, 1),
                            "total_evals": sum(r["n_evals"] for r in rows)}
        print(key, "evals", out["arms"][key]["total_evals"], "err", err,
              round(time.time() - t, 1), "s", flush=True)
out["seconds"] = round(time.time() - t0, 1)
summ = {}
for mode in ("lebail", "pawley"):
    A, B = out["arms"][f"{mode}_carryTrue"], out["arms"][f"{mode}_carryFalse"]
    d = {"evals_true": A["total_evals"], "evals_false": B["total_evals"]}
    mx, where, diffs = 0.0, None, []
    for a, b in zip(A["rows"], B["rows"]):
        if a["a"] is not None and b["a"] is not None and a["a_esd"]:
            z = abs(a["a"] - b["a"]) / a["a_esd"]
            if z > mx:
                mx, where = z, a["label"]
        if (a["status"], a["rung"], a["rungs_tried"]) != (b["status"], b["rung"], b["rungs_tried"]):
            diffs.append([a["label"], [a["status"], a["rung"], a["rungs_tried"]],
                          [b["status"], b["rung"], b["rungs_tried"]]])
    d["max_dcell_esd"] = mx
    d["max_dcell_at"] = where
    d["status_rung_differs"] = diffs
    if A["rows"] and B["rows"]:
        d["max_drwp"] = max(abs(a["rwp"] - b["rwp"]) for a, b in zip(A["rows"], B["rows"]))
        e1 = [abs(r["a_err_ppm"]) for r in A["rows"] if r.get("a_err_ppm") is not None]
        e2 = [abs(r["a_err_ppm"]) for r in B["rows"] if r.get("a_err_ppm") is not None]
        d["max_abs_err_ppm_true"] = max(e1) if e1 else None
        d["max_abs_err_ppm_false"] = max(e2) if e2 else None
    summ[mode] = d
out["summary"] = summ
print(json.dumps(summ, indent=1))
json.dump(out, open(f"{MEASURE}/m1_{fam}.json", "w"), indent=1)

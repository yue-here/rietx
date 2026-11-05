"""Margin of the reference chain: each warm kept-first-rung's dearest stage over the sample max at
FIRST_RUNG_SAMPLES in {1,2,3} (replays sequential._first_rung_budget's rule from the reference run).
A factor above the max ratio cuts nothing on this chain."""
import json, sys
from common import *
from rietx.sequential import _stage_peak

fam = sys.argv[1]
compiled.set_enabled(True)
results = {}
if fam == "thermal":
    from tests.test_sequential import A0, RAMP, _simulate, _start_models
    patterns = [_simulate(A0 * (1 + RAMP * k), seed=11 + k) for k in range(10)]
    st, ins = _start_models()
    res = rx.refine_sequential(patterns, st, ins, labels=[f"p{k:03d}" for k in range(10)],
                               plan="mccusker_default", on_result=results.__setitem__)
else:
    from tests import planted_series as ps
    s = ps.generate(24, seed=0)
    res = ps.refine.__wrapped__(s, on_result=results.__setitem__)
out = {"env": env(), "family": fam}
peaks = {}
for e in res.entries[1:]:
    r = results[e.index]
    peaks[e.label] = {"peak": _stage_peak(r), "rungs": list(e.rungs_tried),
                      "all_converged": all(x.status == "converged" for x in r.stages),
                      "stage_evals": [x.n_iterations for x in r.stages]}
out["peaks"] = peaks
for ns in (1, 2, 3):
    sample, ratios = [], {}
    for e in res.entries[1:]:
        p = peaks[e.label]
        if p["rungs"] == ["warm"]:
            if len(sample) >= ns:
                ratios[e.label] = p["peak"] / max(sample)
            if p["all_converged"]:
                sample.append(p["peak"])
    mx = max(ratios.values()) if ratios else None
    out[f"samples{ns}"] = {"max_ratio": mx, "argmax": max(ratios, key=ratios.get) if ratios else None,
                           "top3": sorted(ratios.items(), key=lambda kv: -kv[1])[:3], "n_armed": len(ratios)}
    print(fam, ns, out[f"samples{ns}"])
print({k: (v["peak"], v["rungs"]) for k, v in peaks.items()})
json.dump(out, open(f"{MEASURE}/m2_margin_{fam}.json", "w"), indent=1)

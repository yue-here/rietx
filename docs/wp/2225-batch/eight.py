"""Width-twin hold on the eight comparison standards.

  eight.py OUT.jsonl [std,std]

Per standard, closing stage off unless the row says "shipped":
  first      the staged plan, hold on (today's behaviour without a closing stage)
  chain<k>   staged re-fits chained from `first`, hold on, until Rwp moves < 1e-7 (max 6)
  nohold     the staged plan from the standard's start with _hold_width_twins disabled
  nohold+1   one staged re-fit of `nohold`, hold still disabled
  shipped    the staged plan with the closing stage on, hold on
  shipped+1  one shipped re-fit of `shipped`
Each row: rwp, chi2, every RefinedParameter (value, esd), the instrument
profile values off the model (held ones are absent from parameters), the
width-twin pairs each stage held, and the warning codes.
"""
import json
import sys
import time
import warnings

from rietx.refine import Refinement
from rietx.viz import compare

warnings.simplefilter("ignore")
RF = sys.modules["rietx.refine"]
_HOLD = RF._hold_width_twins
OUT = sys.argv[1]
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 else None
dd = compare.default_data_dir()


def hold(on):
    RF._hold_width_twins = _HOLD if on else (lambda table, unseen: ([], {}, {}))


def plan(std, closing):
    p = std.build(dd).plan
    if not closing:
        p.closing_window_tol = None
    return p


def row(std, tag, ref, res, dt):
    prof = ref.instrument.profile
    return {"standard": std.key, "arm": tag, "seconds": dt,
            "rwp": res.statistics.rwp, "chi2": res.statistics.chi2,
            "nfev": sum(s.n_iterations for s in res.stages),
            "profile": {k: getattr(prof, k).value for k in ("u", "v", "w", "x", "y")
                        if hasattr(prof, k)},
            "twins": [s.width_twins_held for s in res.stages if getattr(s, "width_twins_held", None)][-1:]
            if any(getattr(s, "width_twins_held", None) for s in res.stages) else [],
            "codes": sorted({d.code for d in res.diagnostics if d.level in ("warning", "error")}),
            "floor": sorted({p for d in res.diagnostics if d.code == "FLOOR_HIT" for p in d.where}),
            "params": {p.path: [p.value, p.stderr] for p in res.parameters}}


def fit(std, inp, ref, closing):
    t0 = time.perf_counter()
    res = ref.fit(inp.data, plan=plan(std, closing), two_theta_limits=inp.two_theta_limits)
    return res, time.perf_counter() - t0


with open(OUT, "a", encoding="utf-8") as fh:
    def put(r):
        fh.write(json.dumps(r, default=str) + "\n")
        fh.flush()
        print(f"{r['standard']:15s} {r['arm']:10s} rwp={r['rwp']:.6f} chi2={r['chi2']:.6f} "
              f"nfev={r['nfev']} {r['seconds']:.1f}s twins={r['twins']} floor={r['floor']}", flush=True)

    for std in compare.STANDARDS:
        if ONLY and std.key not in ONLY:
            continue
        if not std.available(dd):
            print("missing", std.key)
            continue
        inp = std.build(dd)
        # hold on: first fit, then chained staged re-fits
        hold(True)
        ref = Refinement(inp.structure, inp.instrument, history=False)
        res, dt = fit(std, inp, ref, False)
        put(row(std, "first", ref, res, dt))
        last = res.statistics.rwp
        for k in range(1, 7):
            res, dt = fit(std, inp, ref, False)
            put(row(std, f"chain{k}", ref, res, dt))
            if abs(res.statistics.rwp - last) < 1e-7:
                break
            last = res.statistics.rwp
        # hold off
        hold(False)
        inp = std.build(dd)
        ref = Refinement(inp.structure, inp.instrument, history=False)
        res, dt = fit(std, inp, ref, False)
        put(row(std, "nohold", ref, res, dt))
        res, dt = fit(std, inp, ref, False)
        put(row(std, "nohold+1", ref, res, dt))
        # shipped default, hold on
        hold(True)
        inp = std.build(dd)
        ref = Refinement(inp.structure, inp.instrument, history=False)
        res, dt = fit(std, inp, ref, True)
        put(row(std, "shipped", ref, res, dt))
        res, dt = fit(std, inp, ref, True)
        put(row(std, "shipped+1", ref, res, dt))

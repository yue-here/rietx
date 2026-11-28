"""GSAS-II 5.8.4 sequential refinement of the CuCr2O4/CuO ramp (17 patterns), default
stop vs tight stop, Copy2Next on (GSAS-II's warm start). WP-2317 probe.
usage (cwd = OUT/g2seq): <g2 python> -I -u g2seq.py build | run default|dm|tight|presses"""
import json, shutil, sys, time
from pathlib import Path
import numpy as np
from GSASII import GSASIIscriptable as G2sc
from GSASII import GSASIImath as G2mth
HERE = Path.cwd()
DATA = Path("/Users/yue/Code/rietx/.claude/worktrees/ghostshift-land-2312-404666/tests/data/seqrefine_cucr2o4")
LOG = []
_h = G2mth.HessianLSQ
def hlsq(func, x0, Hess, *a, **kw):
    n = {"h": 0}
    def H(x, *aa):
        n["h"] += 1; return Hess(x, *aa)
    out = _h(func, x0, H, *a, **kw)
    info = out[2]
    LOG.append({"cycles": n["h"], "converged": bool(info.get("Converged")),
                "DelChi2": float(info.get("DelChi2", float("nan"))), "lamMax": float(info.get("lamMax", 0))})
    return out
G2mth.HessianLSQ = hlsq
FILES = sorted(DATA.glob("OH_*.fxye"))

def flags(gpx, hists):
    for h in hists:
        h.set_refinements({"Background": {"refine": True},
                           "Instrument Parameters": ["Zero", "U", "V", "W", "X", "Y"],
                           "Sample Parameters": ["Scale"]})
    for ph in gpx.phases():
        ph.data["General"]["Cell"][0] = False   # GSAS-II refuses a seq refinement with the cell flag on;
        for h in hists:                          # its sequential cell is the per-histogram Dij (HStrain)
            ph.set_HAP_refinements({"Scale": ph.name == "CuO", "HStrain": True}, histograms=[h])

def build():
    gpx = G2sc.G2Project(newgpx=str(HERE / "p0.gpx"))
    h0 = gpx.add_powder_histogram(str(FILES[0]), str(DATA / "OH_00.prm"), fmthint="GSAS powder")
    p1 = gpx.add_phase(str(DATA / "CuCr2O4.cif"), phasename="CuCr2O4", histograms=[h0])
    p2 = gpx.add_phase(str(DATA / "CuO.cif"), phasename="CuO", histograms=[h0])
    p2.data["Histograms"][h0.name]["Scale"][0] = 0.05
    h0.set_refinements({"Background": {"type": "chebyschev-1", "no. coeffs": 8, "refine": True}})
    gpx.data["Controls"]["data"]["max cyc"] = 100; gpx.data["Controls"]["data"]["min dM/M"] = 1e-6
    steps = [{"Sample Parameters": ["Scale"]}, {"Instrument Parameters": ["Zero"]}, None,
             {"Instrument Parameters": ["W"]}, {"Instrument Parameters": ["U", "V", "X", "Y"]}]
    p2.set_HAP_refinements({"Scale": True}, histograms=[h0])
    for st in steps:
        if st is None:
            p1.set_refinements({"Cell": True}); p2.set_refinements({"Cell": True})
        else:
            h0.set_refinements(st)
        gpx.refine()
    gpx.data["Controls"]["data"]["max cyc"] = 1000; gpx.data["Controls"]["data"]["min dM/M"] = 1e-9
    gpx.refine(); gpx.refine()
    print("P0", LOG, flush=True)
    for f in FILES[1:]:
        gpx.add_powder_histogram(str(f), str(DATA / "OH_00.prm"), fmthint="GSAS powder", phases=gpx.phases())
    hists = gpx.histograms()
    gpx.copyHistParms(hists[0], [h for h in hists[1:]], "all")
    for ph in gpx.phases():
        ph.copyHAPvalues(hists[0], [h for h in hists[1:]])
    flags(gpx, hists)
    gpx.set_Controls("sequential", hists)
    gpx.set_Controls("seqCopy", True)
    gpx.save(str(HERE / "seq_base.gpx"))
    print("BUILD", [h.name for h in hists], flush=True)

def run(mode):
    f = HERE / f"seq_{mode}.gpx"
    shutil.copy(HERE / "seq_base.gpx", f)
    gpx = G2sc.G2Project(gpxfile=str(f))
    ctl = gpx.data["Controls"]["data"]
    ctl["max cyc"], ctl["min dM/M"] = {"default": (3, 1e-3), "default2": (3, 1e-3), "dm": (1000, 1e-3), "tight": (1000, 1e-9)}[mode]
    t0 = time.time(); gpx.refine()
    if mode == "default2":
        LOG.clear(); gpx.refine()
    wall = time.time() - t0
    seq = gpx.data["Sequential results"]["data"]
    rows = []
    for h in seq["histNames"]:
        r = seq[h]
        rows.append({"hist": h, "values": dict(zip(r["varyList"], map(float, r["variables"]))),
                     "sig": dict(zip(r["varyList"], map(float, r["sig"]))),
                     "chisq": float(r["Rvals"]["chisq"]), "converged": bool(r["Rvals"].get("converged")),
                     "Nobs": int(r["Rvals"]["Nobs"]), "GOF": float(r["Rvals"]["GOF"])})
    out = {"mode": mode, "log": LOG, "rows": rows, "wall": wall}
    (HERE / f"seq_{mode}.json").write_text(json.dumps(out, indent=1, default=float))
    print("SEQ", mode, "cycles", [l["cycles"] for l in LOG], "conv", sum(l["converged"] for l in LOG), "of", len(LOG), flush=True)

if __name__ == "__main__":
    build() if sys.argv[1] == "build" else run(sys.argv[2])

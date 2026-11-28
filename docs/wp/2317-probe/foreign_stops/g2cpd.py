"""GSAS-II 5.8.4 self-comparison of its stop on cpd-1f (WP-2317 probe).
usage (cwd = OUT/g2):  <g2 python> -I g2cpd.py build5
                       <g2 python> -I g2cpd.py run6 default|presses|dm|tight
build5: project on cpd-1e, start = rietx's 1e answer converted; GSAS-II's own
        tight answer (bkg+fractions 30 cyc, then all, dM/M 1e-9, 1000 cyc).
run6:   copy of that project with cpd-1f's counts/weights (same 2theta grid),
        phase fractions re-seeded equal then scaled by rietx's seed_scales rule,
        every other value carried (= rietx's chained warm start), then one stop.
"""
import json, math, shutil, sys, time
from pathlib import Path
import numpy as np
from GSASII import GSASIIscriptable as G2sc
from GSASII import GSASIIstrIO as G2strIO
from GSASII import GSASIImath as G2mth

HERE = Path.cwd()
CPD = HERE.parent / "cpd"
R = json.loads((CPD / "rietx_cpd.json").read_text())
LOG = []
_hlsq = G2mth.HessianLSQ
def hlsq(func, x0, Hess, *a, **kw):
    n = {"h": 0, "f": 0}
    def H(x, *aa):
        n["h"] += 1; return Hess(x, *aa)
    def F(x, *aa):
        n["f"] += 1; return func(x, *aa)
    out = _hlsq(F, x0, H, *a, **kw)
    info = out[2]
    LOG.append({"cycles": n["h"], "nfev": n["f"], "converged": bool(info.get("Converged")),
                "DelChi2": float(info.get("DelChi2", float("nan"))),
                "maxcyc": kw.get("maxcyc"), "ftol": kw.get("ftol"),
                "lamMax": float(info.get("lamMax", 0))})
    return out
G2mth.HessianLSQ = hlsq
_gf = G2strIO.GetFprime
def no_fprime(cd, H):
    _gf(cd, H)
    for tab in (cd.get("FFtables") or {}).values():
        for k in list(tab):
            if k.endswith("FP") or k.endswith("FPP"):
                tab[k] = 0.0
G2strIO.GetFprime = no_fprime

SEED = [0.5936213160179067, 0.1321488235680308, 0.37131363189890804]
PH = [("corundum", "R -3 c"), ("zincite", "P 63 m c"), ("fluorite", "F m -3 m")]
G2S = 1e4 / (8.0 * math.log(2.0))

def chi2_of(hist):
    x, yo, w, yc = (np.ma.getdata(a) for a in hist.data["data"][1][:4])
    lo, hi = hist.data["Limits"][1]
    s = slice(np.searchsorted(x, lo), np.searchsorted(x, hi) + 1)
    return float(np.sum(w[s] * (yo[s] - yc[s]) ** 2)), s.stop - s.start

def free_all(gpx, hist, phases):
    hist.set_refinements({"Background": {"refine": True},
        "Instrument Parameters": ["Zero", "V", "W", "SH/L", "I(L2)/I(L1)"],
        "Sample Parameters": ["Shift"]})
    hist.data["Sample Parameters"]["Scale"][1] = False
    for ph in phases:
        ph.set_refinements({"Cell": True, "Atoms": {a[0]: "U" for a in ph.data["Atoms"]}})
        ph.set_HAP_refinements({"Scale": True, "Size": {"type": "isotropic", "refine": True},
                                "Mustrain": {"type": "isotropic", "refine": True}})

def build5():
    st = R["states"]["cpd-1f"]  # carry state after 1e (scales re-seeded: not used)
    ans = R["answers"]["cpd-1e"]["params"]
    ins = st["instrument"]; prof = ins["profile"]; geo = ins["geometry"]
    lines = ins["source"]["lines"]
    v = lambda d: d["value"]
    inst = HERE / "cpd.instprm"
    inst.write_text("\n".join(["#GSAS-II instrument parameter file: cpd round robin, rietx carry",
        "Type:PXC", "Bank:1", f"Lam1:{v(lines[0]['wavelength'])}", f"Lam2:{v(lines[1]['wavelength'])}",
        f"I(L2)/I(L1):{v(lines[1]['weight'])}", f"Zero:{v(ins['zero_shift'])}",
        f"Polariz.:{v(ins['source']['polarization'])}", "Azimuth:0.0",
        f"U:{v(prof['u']) * G2S}", f"V:{v(prof['v']) * G2S}", f"W:{v(prof['w']) * G2S}",
        f"X:{v(prof['x']) * 100}", "Y:0.0", "Z:0.0",
        f"SH/L:{v(geo['axial_sl']) + v(geo['axial_hl'])}", ""]), encoding="utf-8")
    gpx = G2sc.G2Project(newgpx=str(HERE / "p5.gpx"))
    hist = gpx.add_powder_histogram(str(CPD / "cpd-1e.xye"), str(inst), fmthint="Topas xye")
    lam = v(lines[0]["wavelength"])
    phases = []
    for k, (name, sg) in enumerate(PH):
        sp = st["structure"]["phases"][k]
        cell = [v(sp["cell"][c]) for c in ("a", "b", "c", "alpha", "beta", "gamma")]
        ph = gpx.add_phase(phasename=name, spacegroup=sg, cell=cell, histograms=[hist])
        for at in sp["atoms"]:
            ph.add_atom(v(at["x"]), v(at["y"]), v(at["z"]), at["species"], at["label"], 1.0,
                        v(at["biso"]) / (8 * math.pi ** 2))
        hap = ph.data["Histograms"][hist.name]
        ls = max(v(sp["lor_size"]), 1e-3)
        hap["Size"][1][0] = 1.8 * lam / (math.pi * 100 * ls); hap["Size"][1][2] = 1.0  # LGmix: Lorentzian
        hap["Mustrain"][1][0] = math.pi * 100 * (v(sp["lor_strain"]) + v(prof["y"])) / 0.018
        hap["Mustrain"][1][2] = 1.0  # LGmix: Lorentzian
        hap["Scale"][0] = ans[f"phases.{k}.scale"][0] * 1e3
        phases.append(ph)
    sample = hist.data["Sample Parameters"]
    sample["Type"] = "Bragg-Brentano"; sample["Gonio. radius"] = 173.0
    sample["Shift"][0] = 1000.0 * v(geo["sample_displacement"])
    hist.set_refinements({"Limits": [4.999, 150.001],
        "Background": {"type": "chebyschev-1", "no. coeffs": 6,
                       "coeffs": [v(c) for c in ins["background"]["coefficients"]]}})
    sample["Scale"][1] = False
    # stage 1: background + fractions
    hist.set_refinements({"Background": {"refine": True}})
    for ph in phases:
        ph.set_HAP_refinements({"Scale": True})
    gpx.set_Controls("cycles", 30); gpx.data["Controls"]["data"]["min dM/M"] = 1e-4
    gpx.refine()
    free_all(gpx, hist, phases)
    gpx.set_Controls("cycles", 1000); gpx.data["Controls"]["data"]["min dM/M"] = 1e-9
    for _ in range(3):
        gpx.refine()
    c2, n = chi2_of(hist)
    print("BUILD5", LOG, "chi2", c2, n, flush=True)
    (HERE / "build5.json").write_text(json.dumps({"log": LOG, "chi2": c2, "n": n,
        "rvals": {k: v_ for k, v_ in gpx.data["Covariance"]["data"]["Rvals"].items()
                  if isinstance(v_, (int, float, bool, str))}}, indent=1, default=float))

def refine_flags(gpx, restore, prev=None):
    """Turn every refine flag off except background and phase fractions (restore=False),
    or put them back (restore=True)."""
    hist = gpx.histograms()[0]
    if not restore:
        prev = {"inst": {k: v[2] for k, v in hist.data["Instrument Parameters"][0].items()
                         if isinstance(v, list) and len(v) == 3 and isinstance(v[2], bool)},
                "shift": hist.data["Sample Parameters"]["Shift"][1], "ph": {}}
        for k in prev["inst"]:
            hist.data["Instrument Parameters"][0][k][2] = False
        hist.data["Sample Parameters"]["Shift"][1] = False
        for ph in gpx.phases():
            hap = ph.data["Histograms"][hist.name]
            prev["ph"][ph.name] = (ph.data["General"]["Cell"][0], [a[ph.data["General"]["AtomPtrs"][1] + 1] for a in ph.data["Atoms"]],
                                   hap["Size"][2][0], hap["Mustrain"][2][0])
            ph.data["General"]["Cell"][0] = False
            for a in ph.data["Atoms"]:
                a[ph.data["General"]["AtomPtrs"][1] + 1] = ""
            hap["Size"][2][0] = False; hap["Mustrain"][2][0] = False
        return prev
    for k, f in prev["inst"].items():
        hist.data["Instrument Parameters"][0][k][2] = f
    hist.data["Sample Parameters"]["Shift"][1] = prev["shift"]
    for ph in gpx.phases():
        hap = ph.data["Histograms"][hist.name]
        cell, af, sz, ms = prev["ph"][ph.name]
        ph.data["General"]["Cell"][0] = cell
        for a, f in zip(ph.data["Atoms"], af):
            a[ph.data["General"]["AtomPtrs"][1] + 1] = f
        hap["Size"][2][0] = sz; hap["Mustrain"][2][0] = ms

def snapshot(gpx, hist):
    cov = gpx.data["Covariance"]["data"]
    vals = dict(zip(cov["varyList"], map(float, cov["variables"])))
    sig = dict(zip(cov["varyList"], map(float, cov["sig"])))
    rv = {k: v_ for k, v_ in cov["Rvals"].items() if isinstance(v_, (int, float, bool, str))}
    nvar = len(cov["varyList"]); cov = json.loads(json.dumps(cov, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    nlog = len(LOG)
    ctl = gpx.data["Controls"]["data"]; mc = ctl["max cyc"]
    ctl["max cyc"] = 0; gpx.refine(); ctl["max cyc"] = mc   # evaluate at the answer
    del LOG[nlog:]
    c2, n = chi2_of(gpx.histograms()[0])
    return {"values": vals, "sig": sig, "chi2": c2, "n": n, "rvals": rv, "nvar": nvar}

def run6(mode, start="seed"):
    gfile = HERE / f"p6_{start}_{mode}.gpx"
    shutil.copy(HERE / "p5.gpx", gfile)
    gpx = G2sc.G2Project(gpxfile=str(gfile))
    hist = gpx.histograms()[0]
    phases = gpx.phases()
    d6 = np.loadtxt(CPD / "cpd-1f.xye")
    data = hist.data["data"][1]
    assert np.allclose(np.ma.getdata(data[0]), d6[:, 0])
    data[1][:] = d6[:, 1]; data[2][:] = 1.0 / d6[:, 2] ** 2
    # rietx's own 1f start, in relative terms: each phase's scale at the start of
    # cpd-1f over its 1e answer (seed_scales' equal split), applied to GSAS-II's 1e answer
    ratio = SEED if start != "carry" else [1.0, 1.0, 1.0]
    for ph, f in zip(phases, ratio):
        ph.data["Histograms"][hist.name]["Scale"][0] *= f
    if start == "seedlin":   # scales + background alone first, to their own convergence
        prev = refine_flags(gpx, False)
        gpx.data["Controls"]["data"]["max cyc"] = 100; gpx.data["Controls"]["data"]["min dM/M"] = 1e-6
        gpx.refine()
        refine_flags(gpx, True, prev)
    LOG.clear()
    ctl = gpx.data["Controls"]["data"]
    t0 = time.time(); presses = []
    if mode == "default":
        ctl["max cyc"] = 3; ctl["min dM/M"] = 1e-3; gpx.refine()
        presses.append(snapshot(gpx, gpx.histograms()[0]))
    elif mode == "presses":
        ctl["max cyc"] = 3; ctl["min dM/M"] = 1e-3
        for _ in range(30):
            gpx.refine(); presses.append(snapshot(gpx, gpx.histograms()[0]))
            if LOG[-1]["converged"] or LOG[-1]["DelChi2"] == -10.0:
                break
    elif mode == "dm":
        ctl["max cyc"] = 1000; ctl["min dM/M"] = 1e-3; gpx.refine()
        presses.append(snapshot(gpx, gpx.histograms()[0]))
    elif mode == "tight":
        ctl["max cyc"] = 1000; ctl["min dM/M"] = 1e-9
        for _ in range(3):
            gpx.refine(); presses.append(snapshot(gpx, gpx.histograms()[0]))
    out = {"mode": mode, "log": LOG, "presses": presses, "wall": time.time() - t0,
           "seed_ratio": ratio}
    (HERE / f"run6_{start}_{mode}.json").write_text(json.dumps(out, indent=1, default=float))
    print("RUN6", start, mode, [(l["cycles"], l["converged"], round(l["DelChi2"], 6)) for l in LOG],
          [round(p["chi2"], 2) for p in presses], flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "build5":
        build5()
    else:
        run6(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "seed")

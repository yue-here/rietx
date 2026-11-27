"""WP-2317 cross-code timing: GSAS-II 5.8.4 on the bench's bigcell patterns.

A measurement scaffold, not package code.  Run it with GSAS-II's own
interpreter, from WORKDIR (it writes run-KEY/ there):

    .venv/bin/python docs/wp/2317-probe/export_bigcell.py . WORKDIR
    (cd WORKDIR && <gsas2 python> -I <this file> KEY . [CYCLES])

<gsas2 python> is ``.../GSAS-II-5.8.4/pixi/.pixi/envs/default/bin/python``.
CYCLES caps each step (default 100, rietx-bench's cycle limit); GSAS-II
stops a step earlier on its own default test, a 0.1 % change in χ²
(``min dM/M``).  Readings: the WP-2317 file, Context.

KEY is a bench case (bigcell-structural, bigcell-pawley, bigcell-pawley-120,
bigcell-lebail); WORKDIR holds KEY.xye and KEY.json from export_bigcell.py.
The free set follows rietx's plan stage for stage, cumulatively, through
G2Project.do_refinements:
  1 background (+ scale in Rietveld; + Pawley intensities throughout in Pawley)
  2 + zero    3 + cell    4 + W    5 + U, V, X, Y
  structural: 6 + atom coordinates    7 + Uiso
Units: rietx Γ_G² (deg²) = 8 ln2 σ², GSAS-II σ² in centideg²; X and Y are
FWHM terms in both (1/cosθ and tanθ), centideg in GSAS-II; rietx's held
lor_size (also 1/cosθ) folds into GSAS-II's X; SH/L = S/L + H/L (held, as
rietx holds both axial terms).  Dispersion is switched off (rietx declines
it): GetFprime is patched to f' = f'' = 0.
Timed: do_refinements only (its .gpx writes included); the zero-cycle scale
seed before it is setup.  Prints one RESULT line.
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from GSASII import GSASIIlattice as G2lat
from GSASII import GSASIIpwd as G2pwd
from GSASII import GSASIIscriptable as G2sc
from GSASII import GSASIIspc as G2spc
from GSASII import GSASIIstrIO as G2strIO
from GSASII import GSASIIstrMain as G2strMain

key, workdir = sys.argv[1], Path(sys.argv[2]).resolve()
CYCLES = int(sys.argv[3]) if len(sys.argv) > 3 else 100
start = json.loads((workdir / f"{key}.json").read_text(encoding="utf-8"))
mode = start["mode"]
structural = mode == "rietveld"
run = workdir / f"run-{key}"
run.mkdir(exist_ok=True)

# --- dispersion off, as rietx declares it --------------------------------
_get_fprime = G2strIO.GetFprime


def no_fprime(controlDict, Histograms):
    _get_fprime(controlDict, Histograms)
    for tab in (controlDict.get("FFtables") or {}).values():
        for k in list(tab):
            if k.endswith("FP") or k.endswith("FPP"):
                tab[k] = 0.0


G2strIO.GetFprime = no_fprime

# --- instrument -----------------------------------------------------------
G2S = 1e4 / (8.0 * math.log(2.0))          # rietx deg² FWHM² -> GSAS centideg² σ²
(l1, _), (l2, r2) = start["lines"]
inst = workdir / f"{key}.instprm"
inst.write_text("\n".join([
    "#GSAS-II instrument parameter file: WP-2317 bigcell, rietx's Cu Ka doublet, "
    "graphite monochromator 2theta_m = 26.6 deg",
    "Type:PXC", "Bank:1", f"Lam1:{l1}", f"Lam2:{l2}", f"I(L2)/I(L1):{r2}",
    f"Zero:{start['zero']}", "Polariz.:0.5557063", "Azimuth:0.0",
    f"U:{start['u'] * G2S}", f"V:{start['v'] * G2S}", f"W:{start['w'] * G2S}",
    f"X:{(start['x'] + start['lor_size']) * 100.0}",
    f"Y:{(start['y'] + start['lor_strain']) * 100.0}", "Z:0.0",
    f"SH/L:{start['axial_sl'] + start['axial_hl']}", ""]), encoding="utf-8")

gpx = G2sc.G2Project(newgpx=str(run / f"{key}.gpx"))
hist = gpx.add_powder_histogram(str(workdir / f"{key}.xye"), str(inst),
                                fmthint="Topas xye")
phase = gpx.add_phase(phasename="bigcell", spacegroup="P 21 21 21",
                      cell=[*start["cell"], 90.0, 90.0, 90.0], histograms=[hist])
for label, species, x, y, z, biso in start["atoms"]:
    phase.add_atom(x, y, z, species, label, 1.0, biso / (8.0 * math.pi ** 2))
hap = phase.data["Histograms"][hist.name]
hap["Size"][1][0] = 10.0            # "nothing", as rietx-bench's PbSO4 driver
hap["Size"][1][2] = 0.0
hap["Mustrain"][1][0] = 0.0
sample = hist.data["Sample Parameters"]
sample["Type"] = "Bragg-Brentano"
sample["Gonio. radius"] = 250.0
# GSAS-II fits searchsorted(x, lo) .. searchsorted(x, hi) inclusive
LIMITS = [start["tt_min"] - 0.01, start["tt_max"] - 0.01]
hist.set_refinements({
    "Limits": LIMITS,
    "Background": {"type": "chebyschev-1", "no. coeffs": len(start["bkg"]),
                   "coeffs": list(start["bkg"])}})
gpx.set_Controls("cycles", CYCLES)
# a new histogram's scale carries refine=True; structure-free modes hold it
# (rietx force-fixes .scale in lebail/pawley)
hist.data["Sample Parameters"]["Scale"][1] = False

dmin = l1 / (2.0 * math.sin(math.radians(start["tt_max"] / 2.0)))
if mode == "pawley":
    gen = phase.data["General"]
    gen["doPawley"] = True
    gen["Pawley dmin"] = dmin
    # GSAS-II's default dmax (100 Å) is kept.  (0 2 0) sits at 4.9°, below
    # the first point, and its tail is in the data (rietx carries it); GSAS-II
    # draws no peak placed below its lower limit, so the tail stays unfitted
    # with or without it (Rwp 0.07022 both ways at 90°).
elif mode == "lebail":
    hap["LeBail"] = True


def fitted(x):
    return slice(np.searchsorted(x, LIMITS[0]), np.searchsorted(x, LIMITS[1]) + 1)


def rwp_of():
    x, yo, w, yc = (np.ma.getdata(a) for a in hist.data["data"][1][:4])
    s = fitted(x)
    return (float(np.sqrt(np.sum(w[s] * (yo[s] - yc[s]) ** 2) / np.sum(w[s] * yo[s] ** 2))),
            s.stop - s.start)


cycles_done = [0]


def on_cycle(histograms, icycle=None):
    # HessianLSQ/HessianSVD pass the cycle; RefineCore's leastsq paths
    # (deriv type 'Jacobian' and numeric) call with Histograms alone
    cycles_done[0] += 1


_refine = G2strMain.Refine
lebail_init = [mode == "lebail"]


def refine_with_hook(gpxfile, **kwargs):
    if lebail_init[0]:
        # the GUI's "reset Le Bail structure factors?  Yes" path: unity start,
        # one Le Bail-only pass (DoLeBail cycles=1), then least squares
        ok = G2strMain.DoLeBail(gpxfile, cycles=1)
        if not ok[0]:
            raise SystemExit("GSAS-II DoLeBail failed")
        lebail_init[0] = False
    outcome = _refine(gpxfile, refPlotUpdate=on_cycle, **kwargs)
    if outcome is not None and not outcome[0]:
        raise SystemExit("GSAS-II refinement failed: " + str(outcome[1]))


# --- untimed setup: seed the scale (Rietveld) or the Pawley list ----------
if structural:
    gpx.set_Controls("cycles", 0)
    gpx.do_refinements([{}])
    x, yo, w, yc = (np.ma.getdata(a) for a in hist.data["data"][1][:4])
    s = fitted(x)
    k = float(np.sum((yo[s] - start["bkg"][0]) * yc[s]) / np.sum(yc[s] ** 2))
    hist.data["Sample Parameters"]["Scale"][0] *= k
    gpx.set_Controls("cycles", CYCLES)
elif mode == "pawley":
    # GSAS-II's "Pawley create" (OnPawleyLoad) then "Pawley estimate"
    # (OnPawleyEstimate, J. Hester's algorithm), with the refine flag set
    gen = phase.data["General"]
    A = G2lat.cell2A(gen["Cell"][1:7])
    SGData = gen["SGData"]
    instd = hist.data["Instrument Parameters"][0]
    xd = np.ma.getdata(hist.data["data"][1][0])
    yd = np.ma.getdata(hist.data["data"][1][1])
    bd = np.ma.getdata(hist.data["data"][1][4])
    Vst = 1.0 / gen["Cell"][7]
    refs = []
    for h, k_, l_, d in np.array(G2lat.GenHLaue(dmin, SGData, A)):
        if d > gen["Pawley dmax"]:
            continue
        ext, mul = G2spc.GenHKLf([h, k_, l_], SGData)[:2]
        if ext:
            continue
        mul *= 2
        pos = G2lat.Dsp2pos(instd, d)
        i = min(np.searchsorted(xd, pos), len(xd) - 1)
        fwhm = max(0.001, G2pwd.getFWHM(pos, instd))
        lor = 1.0 / (2.0 * math.sin(math.radians(xd[i] / 2)) ** 2
                     * math.cos(math.radians(xd[i] / 2)))
        pola = G2pwd.Polarization(instd["Polariz."][1], xd[i], instd["Azimuth"][1])[0]
        f2 = (yd[i] - bd[i]) * fwhm * math.sqrt(math.pi)
        f2 /= hist.data["Sample Parameters"]["Scale"][0] * Vst * lor * pola * mul
        refs.append([int(h), int(k_), int(l_), mul, float(d), True, float(f2), 1.0])
    refs.sort(key=lambda r: -r[4])
    phase.data["Pawley ref"] = refs
    print(f"pawley reflections {len(refs)}  dmin {dmin:.4f}", flush=True)
if mode == "lebail":
    gpx.data["Controls"]["data"]["newLeBail"] = True

G2strMain.Refine = refine_with_hook

recipe = [{"set": {"Background": {"refine": True},
                   **({"Sample Parameters": ["Scale"]} if structural else {})}},
          {"set": {"Instrument Parameters": ["Zero"]}},
          {"set": {"Cell": True}},
          {"set": {"Instrument Parameters": ["W"]}},
          {"set": {"Instrument Parameters": ["U", "V", "X", "Y"]}}]
if structural:
    labels = [a[0] for a in start["atoms"]]
    recipe += [{"set": {"Atoms": {lab: "X" for lab in labels}}},
               {"set": {"Atoms": {lab: "XU" for lab in labels}}}]

t0 = time.perf_counter()
gpx.do_refinements(recipe)
wall = time.perf_counter() - t0
rwp, npts = rwp_of()
rvals = gpx.data["Covariance"]["data"].get("Rvals", {})
cov = gpx.data["Covariance"]["data"]
print(f"RESULT {key} mode={mode} wall {wall:.2f} s  Rwp(own) {rwp:.5f}  "
      f"Rwp(G2) {rvals.get('Rwp', float('nan')) / 100:.5f}  points {npts}  "
      f"cycles {cycles_done[0]}  nvar {len(cov.get('varyList', []))}  "
      f"converged {rvals.get('converged')}  cell {phase.data['General']['Cell'][1:4]}",
      flush=True)

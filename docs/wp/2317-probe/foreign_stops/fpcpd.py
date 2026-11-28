"""FullProf 8.20 self-comparison of its Eps stop on cpd-1f (WP-2317 probe).
Writes PCR files from a parameter dict; runs fp2k; parses .out / new .pcr.
usage: python3 fpcpd.py build5 | run6 MODE"""
import json, math, os, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
CPD = HERE / "cpd"; FPD = HERE / os.environ.get("FP_DIR", "fp")
FPBIN = Path.home() / "Code/rietx-bench/tools/fullprof/files"
R = json.loads((CPD / "rietx_cpd.json").read_text())
PERPHASE_VW = os.environ.get("FP_PERPHASE_VW") == "1"
FREE_SL = os.environ.get("FP_HOLD_SL") != "1"
SHARE_U = os.environ.get("FP_SHARE_U") == "1"
SEED = [0.5936213160179067, 0.1321488235680308, 0.37131363189890804]
PHASES = [
 ("corundum", "R -3 c", 611.77, [("Al", "AL", 1/3), ("O", "O", 0.5)], ["a", "a", "c"]),
 ("zincite", "P 63 m c", 162.76, [("Zn", "ZN", 1/6), ("O", "O", 1/6)], ["a", "a", "c"]),
 ("fluorite", "F m -3 m", 312.30, [("Ca", "CA", 4/192), ("F", "F", 8/192)], ["a", "a", "a"]),
]

def start_params():
    st = R["states"]["cpd-1f"]; ins = st["instrument"]; pr = ins["profile"]
    v = lambda d: d["value"]
    P = {"zero": 0.0, "sycos": 0.0, "bkg": [30.0, 0, 0, 0, 0, 0],
         "ratio": v(ins["source"]["lines"][1]["weight"]),
         "lam1": v(ins["source"]["lines"][0]["wavelength"]), "lam2": v(ins["source"]["lines"][1]["wavelength"]),
         "V": -0.005, "W": 0.008,  # rietx's u, v, w make H_G^2 < 0 above ~120 deg for corundum (rietx clamps it); FullProf then freezes U, V, W
 "SL": float(os.environ.get("FP_SL", v(ins["geometry"]["axial_sl"]))), "DL": 0.0, "ph": []}
    for k, sp in enumerate(st["structure"]["phases"]):
        P["ph"].append({"scale": 1e-3,
            "U": 0.005, "X": v(pr["y"]) + v(sp["lor_strain"]),
            "Y": v(pr["x"]) + v(sp["lor_size"]), "IG": 0.0,
            "cell": [v(sp["cell"][c]) for c in ("a", "b", "c", "alpha", "beta", "gamma")],
            "atoms": [[v(a["x"]), v(a["y"]), v(a["z"]), v(a["biso"])] for a in sp["atoms"]]})
    return P

def write_pcr(path, P, ncy, eps, free="all"):
    """free: 'linear' (scales+background) or 'all' (the rietx last-stage analogue)."""
    n = [0]
    def c(on=True):
        if not on: return 0.0
        n[0] += 1; return 10.0 * n[0] + 1.0
    allf = free == "all"
    cz, cs = c(allf), c(allf)
    cb = [c() for _ in range(6)]
    cV, cW = (None, None) if PERPHASE_VW else (c(allf), c(allf)); cSL = c(allf and FREE_SL)
    cUs = c(allf) if SHARE_U else None
    L = ["COMM cpd-1 round robin, WP-2317 stop probe",
         "!Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt Aut",
         "   0   7   3   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0",
         "!Ipr Ppl Ioc Mat Pcr Ls1 Ls2 Ls3 NLI Prf Ins Rpa Sym Hkl Fou Sho Ana",
         "   0   0   1   1   1   0   4   0   0   3   0   1   0   0   0   0   0",
         "! Lambda1  Lambda2    Ratio    Bkpos    Wdt    Cthm     muR   AsyLim   Rpolarz  2nd-muR",
         f" {P['lam1']:.7f} {P['lam2']:.7f} {P['ratio']:.5f}  77.500 15.0000  0.7998  0.0000  160.00    0.0000  0.0000",
         "!NCY  Eps  R_at  R_an  R_pr  R_gl     Thmin       Step       Thmax    PSD    Sent0",
         f" {ncy:3d}  {eps:.4f}  1.00  1.00  1.00  1.00     5.0000   0.020000   150.0000   0.000   0.000",
         "!", "!"]
    body = []
    body += ["!  Zero    Code    SyCos    Code   SySin    Code  Lambda     Code MORE",
             f" {P['zero']:.6f} {cz:.1f} {P['sycos']:.6f} {cs:.1f} 0.00000 0.0 0.000000 0.00 0",
             "!   Background coefficients/codes (Polynomial of 6th degree)",
             " " + " ".join(f"{b:.6f}" for b in P["bkg"]), " " + " ".join(f"{x:.2f}" for x in cb)]
    for k, (name, sg, atz, atoms, cellmap) in enumerate(PHASES):
        ph = P["ph"][k]
        body += ["!-------------------------------------------------------------------------------",
                 name,
                 "!Nat Dis Ang Pr1 Pr2 Pr3 Jbt Irf Isy Str Furth       ATZ    Nvk Npr More",
                 f"   2   0   0 0.0 0.0 1.0   0   0   0   0   0  {atz:.3f}   0   7   0",
                 "!", "!", f"{sg}                  <--Space group symbol",
                 "!Atom   Typ       X        Y        Z     Biso       Occ     In Fin N_t Spc /Codes"]
        for (lab, typ, occ), (x, y, z, b) in zip(atoms, ph["atoms"]):
            body += [f"{lab:6s} {typ:5s} {x:.6f} {y:.6f} {z:.6f} {b:.6f} {occ:.6f} 0 0 0 0",
                     f"  0.00 0.00 0.00 {c(allf):.2f} 0.00"]
        csc = c()
        cU = cUs if SHARE_U else c(allf)
        if PERPHASE_VW:
            cV, cW = c(allf), c(allf)
        cX, cY, cIG = c(allf), c(allf), c(False)  # IG held: IG/cos^2 = IG(1+tan^2) is W+U, an exact degeneracy with shared W and per-phase U
        cells = {"a": c(allf), "c": c(allf) if cellmap[2] == "c" else None}
        cc = [cells["a"], cells["a"], cells["c"] if cells["c"] is not None else cells["a"], 0, 0, 0]
        body += ["!-------> Profile Parameters for Pattern #   1  ----> Phase #   %d" % (k + 1),
                 "!  Scale          Shape1      Bov      Str1      Str2      Str3   Strain-Model",
                 f" {ph['scale']:.7e} 0.0 0.0 0.0 0.0 0.0 0", f" {csc:.2f} 0 0 0 0 0",
                 "!       U         V          W           X          Y        GauSiz   LorSiz Size-Model",
                 f" {ph['U']:.7f} {P['V']:.7f} {P['W']:.7f} {ph['X']:.7f} {ph['Y']:.7f} {ph['IG']:.7f} 0.0 0",
                 f" {cU:.2f} {cV:.2f} {cW:.2f} {cX:.2f} {cY:.2f} {cIG:.2f} 0.0",
                 "!     a          b         c        alpha      beta       gamma      #Cell Info",
                 " " + " ".join(f"{x:.6f}" for x in ph["cell"]), " " + " ".join(f"{float(x):.2f}" for x in cc),
                 "!  Pref1    Pref2      Asy1     Asy2     Asy3     Asy4      S_L      D_L",
                 f"  0.0 0.0 0.0 0.0 0.0 0.0 {P['SL']:.6f} {P['DL']:.6f}",
                 f"  0.0 0.0 0.0 0.0 0.0 0.0 {cSL:.2f} 0.0"]
    body += ["!  2Th1/TOF1    2Th2/TOF2  Pattern to plot", "      5.000     150.000       1"]
    L += [f" {n[0]:6d}    !Number of refined parameters", "!"] + body
    Path(path).write_text("\n".join(L) + "\n")

def run(dirpath, stem="cpd"):
    env = dict(os.environ, FULLPROF=str(FPBIN))
    with open(Path(dirpath) / "console.log", "w") as f:
        subprocess.run([str(FPBIN / "fp2k"), stem], cwd=dirpath, env=env, stdout=f, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL, timeout=500)

def parse(d):
    out = (Path(d) / "cpd.out").read_text(errors="replace")
    vals, sig = {}, {}
    if "FINAL VALUES AND SIGMA" in out:
        tail = out[out.index("FINAL VALUES AND SIGMA"):]
        for m in re.finditer(r"Parameter number\s+(\d+)\s*:\s+(\S+)\s+(\S+)\s*\(\s*\+/-\s+(\S+)\s*\)", tail):
            vals[m.group(2)] = float(m.group(3)); sig[m.group(2)] = float(m.group(4))
    cyc = [int(x) for x in re.findall(r"=> CYCLE No\.:\s+(\d+)", out)]
    chis = [float(x) for x in re.findall(r"Conventional Rietveld Rp,Rwp,Re and Chi2:\s+\S+\s+\S+\s+\S+\s+(\S+)", out)]
    conv = "Convergence reached" in out
    # chi2 from the .prf at the final parameters: weights 1/y (Ins=0 counts)
    import numpy as np
    rows = []
    for line in (Path(d) / "cpd.prf").read_text(errors="replace").splitlines():
        t = line.split()
        if len(t) >= 4:
            try:
                rows.append([float(t[0]), float(t[1]), float(t[2])])
            except ValueError:
                pass
    a = np.array(rows); a = a[(a[:, 0] >= 4.99) & (a[:, 0] <= 150.01)]
    a = a[np.r_[True, np.diff(a[:, 0]) > 0]]
    chi2 = float(np.sum((a[:, 1] - a[:, 2]) ** 2 / np.maximum(a[:, 1], 1.0)))
    return {"values": vals, "sig": sig, "cycles": max(cyc) if cyc else 0, "converged": conv,
            "chi2red_fp": chis[-1] if chis else None, "chi2": chi2, "npts": len(a), "nvar": len(vals)}

def edit_pcr(text, ncy, eps, scale_mult=None):
    L = text.splitlines(); k = 0
    for i, line in enumerate(L):
        if line.startswith("!NCY"):
            t = L[i + 1].split(); t[0] = str(ncy); t[1] = f"{eps:.4f}"; L[i + 1] = " " + "  ".join(t)
        if line.startswith("!  Scale") and scale_mult is not None:
            t = L[i + 1].split(); t[0] = f"{float(t[0]) * scale_mult[k]:.7e}"; L[i + 1] = " " + "  ".join(t); k += 1
    return "\n".join(L) + "\n"

def build5():
    d = FPD / "b5"; d.mkdir(parents=True, exist_ok=True)
    P = start_params(); write_pcr(d / "cpd.pcr", P, 300, 0.01, free="linear")
    shutil.copy(CPD / "cpd-1e.dat", d / "cpd.dat"); run(d)
    lin = parse(d); print("B5 linear", lin["cycles"], lin["converged"], lin["chi2"])
    # now the same model with every code on, values from the linear fit
    P["bkg"] = [lin["values"][f"Bck_{i}_pat1"] for i in range(6)]
    for k in range(3):
        P["ph"][k]["scale"] = lin["values"][f"Scale_ph{k+1}_pat1"]
    d2 = FPD / "b5all"; d2.mkdir(parents=True, exist_ok=True)
    write_pcr(d2 / "cpd.pcr", P, 300, 0.01, free="all")
    shutil.copy(CPD / "cpd-1e.dat", d2 / "cpd.dat"); run(d2)
    r = parse(d2); print("B5 all", r["cycles"], r["converged"], r["chi2"], r["chi2red_fp"], r["nvar"])
    shutil.copy(d2 / "cpd.pcr", FPD / "p5.pcr")

def run6(mode, start):
    ncy, eps = {"default": (100, 0.2), "eps0.1": (100, 0.1), "ncy15": (15, 0.2),
                "tight": (600, 0.001)}[mode]
    d = FPD / f"r6_{start}_{mode}"; d.mkdir(parents=True, exist_ok=True)
    txt = (FPD / "p5.pcr").read_text()
    (d / "cpd.pcr").write_text(edit_pcr(txt, ncy, eps, SEED if start == "seed" else None))
    shutil.copy(CPD / "cpd-1f.dat", d / "cpd.dat"); run(d)
    r = parse(d); r.update(mode=mode, start=start, ncy=ncy, eps=eps)
    (FPD / f"r6_{start}_{mode}.json").write_text(json.dumps(r, indent=1))
    print("R6", start, mode, r["cycles"], r["converged"], round(r["chi2"], 2), r["chi2red_fp"], r["nvar"])

if __name__ == "__main__":
    if sys.argv[1] == "build5":
        build5()
    if sys.argv[1] == "run6":
        run6(sys.argv[2], sys.argv[3])
    if sys.argv[1] == "test":
        d = FPD / "test"; d.mkdir(parents=True, exist_ok=True)
        P = start_params(); write_pcr(d / "cpd.pcr", P, 10, 0.2, free="linear")
        shutil.copy(CPD / "cpd-1e.dat", d / "cpd.dat"); run(d)

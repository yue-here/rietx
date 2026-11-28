import json, sys
from pathlib import Path
D = Path(sys.argv[1]); starts = sys.argv[2].split(",")
def fam(n):
    if "::A" in n and "Uiso" not in n: return "cell"
    if n.endswith(":Zero") or n.endswith(":Shift"): return "zero/disp"
    if "Uiso" in n: return "Biso"
    if n.endswith(":Scale"): return "scale"
    if ":Back;" in n: return "bkg"
    return "profile"
FAMS = ["cell", "zero/disp", "profile", "Biso", "scale", "bkg"]
for st in starts:
    ref = json.loads((D / f"run6_{st}_tight.json").read_text())["presses"][-1]
    for mode in ["default", "presses", "dm", "tight"]:
        r = json.loads((D / f"run6_{st}_{mode}.json").read_text())
        for ip, p in enumerate(r["presses"]):
            if mode == "presses" and ip not in (0, len(r["presses"]) - 1): continue
            worst = {f: (0, "") for f in FAMS}
            for n, v in p["values"].items():
                d = abs(v - ref["values"][n]) / ref["sig"][n] if ref["sig"][n] > 0 else float("inf")
                f = fam(n)
                if d > worst[f][0]: worst[f] = (d, n)
            cyc = sum(l["cycles"] for l in r["log"][: ip + 1])
            conv = r["log"][ip]["converged"]
            print(f"{st:8s} {mode:8s} press{ip+1} cyc={cyc:3d} conv={conv!s:5s} chi2={p['chi2']:.1f} (ref {ref['chi2']:.1f}, chi2red {p['chi2']/(p['n']-1-p['nvar']):.4f}) "
                  + " ".join(f"{f}={worst[f][0]:.2g}" for f in FAMS)
                  + f"  worst={max(worst.values())[1]} {max(worst.values())[0]:.3g}")

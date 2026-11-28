import json, sys
from pathlib import Path
D = Path(sys.argv[1]); prefix = sys.argv[2]; ref_name = sys.argv[3]; modes = sys.argv[4].split(",")
def fam(n):
    if n.startswith("Cell_"): return "cell"
    if n.startswith("Zero") or n.startswith("SyCos"): return "zero/disp"
    if n.startswith("Biso"): return "Biso"
    if n.startswith("Scale"): return "scale"
    if n.startswith("Bck"): return "bkg"
    return "profile"
FAMS = ["cell", "zero/disp", "profile", "Biso", "scale", "bkg"]
ref = json.loads((D / f"{ref_name}.json").read_text())
for m in modes:
    r = json.loads((D / f"{prefix}_{m}.json").read_text())
    worst = {f: (0, "") for f in FAMS}
    for n, v in r["values"].items():
        d = abs(v - ref["values"][n]) / ref["sig"][n]
        if d > worst[fam(n)][0]: worst[fam(n)] = (d, n)
    w = max(worst.values())
    print(f"{prefix} {m:8s} cyc={r['cycles']:3d} conv={r['converged']!s:5s} chi2={r['chi2']:.2f} (ref {ref['chi2']:.2f}) chi2red_fp={r['chi2red_fp']} "
          + " ".join(f"{f}={worst[f][0]:.2g}" for f in FAMS) + f"  worst={w[1]} {w[0]:.3g}")

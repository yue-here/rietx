import json, sys
from pathlib import Path
D = Path(sys.argv[1])
def fam(n):
    k = n.split(":")[-1]
    if k.startswith("D") and k[1:3].isdigit(): return ("CuO " if n.startswith("1:") else "CuCr2O4 ") + "cell(Dij)"
    if k in ("Zero", "Shift", "DisplaceX", "DisplaceY"): return "zero/disp"
    if k.startswith("Back"): return "bkg"
    if k == "Scale": return "scale"
    return "profile"
ref = json.loads((D / "seq_tight.json").read_text())
FAMS = ["CuCr2O4 cell(Dij)", "CuO cell(Dij)", "zero/disp", "profile", "scale", "bkg"]
print("tight: cycles", [l["cycles"] for l in ref["log"]], "sum", sum(l["cycles"] for l in ref["log"]))
for mode in ["default", "default2", "dm"]:
    r = json.loads((D / f"seq_{mode}.json").read_text())
    worst = {f: (0, "", "") for f in FAMS}; dchi = []
    for a, b in zip(r["rows"], ref["rows"]):
        assert a["hist"] == b["hist"]
        dchi.append(a["chisq"] - b["chisq"])
        for n, v in a["values"].items():
            d = abs(v - b["values"][n]) / b["sig"][n]
            f = fam(n)
            if d > worst[f][0]: worst[f] = (d, n, a["hist"].split()[1])
    print(f"{mode}: cycles total {sum(l['cycles'] for l in r['log'])}, converged {sum(r_['converged'] for r_ in r['rows'])}/17, "
          f"max dchi2 {max(dchi):.1f} (median {sorted(dchi)[8]:.1f}; tight chi2 median {sorted(x['chisq'] for x in ref['rows'])[8]:.0f}, Nobs {ref['rows'][0]['Nobs']})")
    for f in FAMS:
        print(f"   {f:18s} {worst[f][0]:8.3g}  {worst[f][1]} {worst[f][2]}")

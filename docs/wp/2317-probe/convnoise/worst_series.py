import json,sys
from pathlib import Path
d=json.loads((Path(__file__).parent/"results"/f"series_{sys.argv[1]}.json").read_text())
runs=d["runs"]; ref=next(r for r in runs if r["stop"]=="ftol1e-9" and r["seed"] is None)
for r in runs:
    tag=r["stop"] if r["seed"] is None else f"nudge{r['seed']}"
    if tag not in sys.argv[2:]: continue
    L=[]
    for k,(a,b) in enumerate(zip(ref["rows"],r["rows"])):
        for p,(v,e) in a["params"].items():
            if p in b["params"] and e: L.append((abs(b["params"][p][0]-v)/e,k,p,v,b["params"][p][0],e))
        L.append((0,k,"chi2 ref/new",a["chi2"],b["chi2"],0))
    L.sort(reverse=True)
    print(tag); [print("  %.3g pat%d %s ref %.6g new %.6g esd %.3g"%x) for x in L[:8]]
    print("  chi2 per pattern ref:", [round(a["chi2"],5) for a in ref["rows"]]); print("  new:", [round(b["chi2"],5) for b in r["rows"]])

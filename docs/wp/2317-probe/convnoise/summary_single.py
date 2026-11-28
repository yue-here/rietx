import io, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import analyse_single as a
fx = ["srm660c", "fap", "nac", "cpd1a", "bigcell"]
allrows = {f: a.table(f, out=io.StringIO())[0] for f in fx}
stops = [r["stop"] for r in allrows["srm660c"]]
fams = a.FAMS[:-1]
print("| stop | " + " | ".join(fams) + " | phase frac | worst fixture | last-stage evals (srm/fap/nac/cpd1a/big) |")
print("|" + "---|" * (len(fams) + 4))
for s in stops:
    vals, worst = {}, (0, "")
    for f in fx:
        row = next(r for r in allrows[f] if r["stop"] == s)
        for fam in fams + ["qpa"]:
            v = row["qpa_dep"] if fam == "qpa" else row["dep"][fam]
            if v > vals.get(fam, -1): vals[fam] = v
            if v > worst[0]: worst = (v, f)
    ev = "/".join(str(next(r for r in allrows[f] if r["stop"] == s)["nfev_last"]) for f in fx)
    print(f"| {s} | " + " | ".join(f"{vals[k]:.2g}" for k in fams + ["qpa"]) + f" | {worst[1]} | {ev} |")

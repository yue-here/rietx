"""bigcell: a setting's paired shift, per pair, split by the basin the pair sits in.

python basin_split.py SETTING REF [PARAM ...]
Prints, for each pair (seed none, 0-9), its basin and shift/esd on each named
parameter (default: the four basin-separating coordinates and the overall worst
non-background parameter).
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import analyse as A  # noqa: E402

S, R = sys.argv[1], sys.argv[2]
params = sys.argv[3:] or ["phases.0.atoms.23.x", "phases.0.atoms.23.y",
                          "phases.0.atoms.27.x", "phases.0.atoms.27.y"]
A.NO_BKG = True
runs = A.load()
vR, eR = A.vec(runs[("bigcell", R, "none")])
allR = [vR] + [A.vec(runs[("bigcell", R, str(s))])[0] for s in range(20) if ("bigcell", R, str(s)) in runs]
lab = A.basins(allR, eR)
cs = A.centres(allR, lab)
disc = A.discriminators(cs, eR)
print("setting", S, "vs", R, "| basins", len(cs), "| discriminators", disc)
print("seed basin chi2_R chi2_S worst(param) " + " ".join(p.split(".", 2)[2] for p in params))
by = {}
for s in ["none"] + [str(k) for k in range(10)]:
    a, b = runs.get(("bigcell", S, s)), runs.get(("bigcell", R, s))
    if a is None or b is None:
        continue
    va, vb = A.vec(a)[0], A.vec(b)[0]
    la, lb = A.assign(va, cs, eR, disc), A.assign(vb, cs, eR, disc)
    d = A.dep(va, vb, eR)
    w, wp = A.worst(d)
    by.setdefault(lb, []).append(w)
    sh = [(va[p] - vb[p]) / eR[p] for p in params]
    print(f"{s:>4} {lb}{'' if la == lb else '->' + str(la)} {b['chi2']:.6f} {a['chi2']:.6f} "
          f"{w:.3f}({wp.split('.', 2)[2]}) " + " ".join(f"{x:+.3f}" for x in sh))
for k, v in sorted(by.items()):
    print(f"basin {k}: n {len(v)}, worst shift range {min(v):.3f}-{max(v):.3f}")

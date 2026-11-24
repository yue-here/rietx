"""Reduce eight.jsonl: per standard, shifts of the chain limit (and shipped+1) from the first fit, in first-fit esds."""
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
by = {}
for r in rows:
    by.setdefault(r["standard"], {})[r["arm"]] = r
QUOTED = ("cell", "biso", "scale", "atoms")
def kind(p):
    if ".cell." in p: return "cell"
    if "biso" in p or ".atoms." in p: return "atoms"
    if p.endswith(".scale"): return "scale"
    if "size" in p or "strain" in p: return "specimen width"
    if "background" in p: return "background"
    return "instrument"
for std, arms in by.items():
    first = arms["first"]
    chains = [a for a in arms if a.startswith("chain")]
    last = arms[sorted(chains, key=lambda a: int(a[5:]))[-1]]
    for tag, a, b in (("chain", first, last), ("shipped+1", arms["shipped"], arms["shipped+1"])):
        p0 = a["params"]; p1 = b["params"]
        best = {}
        for k, (v0, e0) in p0.items():
            if k in p1 and e0:
                z = (p1[k][0] - v0) / e0
                kd = kind(k)
                if kd not in best or abs(z) > abs(best[kd][1]):
                    best[kd] = (k, z)
        top = sorted(best.items(), key=lambda kv: -abs(kv[1][1]))
        print(f"{std:15s} {tag:10s} rwp {a['rwp']:.6f}->{b['rwp']:.6f} chi2 {a['chi2']:.5f}->{b['chi2']:.5f} ({(b['chi2']/a['chi2']-1)*100:+.2f}%) "
              + "; ".join(f"{kd}: {k.split('.',1)[1] if k.startswith('phases') else k.replace('instrument.','')} {z:+.2f}" for kd, (k, z) in top))
    pr0, pr1 = first["profile"], last["profile"]
    print(f"{'':15s} profile first {pr0}\n{'':15s} profile chain {pr1}\n{'':15s} floor first {first['floor']}")

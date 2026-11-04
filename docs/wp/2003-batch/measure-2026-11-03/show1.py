import json,sys
d=json.load(open(sys.argv[1]))
for k,v in d["arms"].items():
    print(k, v["total_evals"], v["seconds"])
modes=["lebail","pawley"]
for m in modes:
    A=d["arms"][m+"_carryTrue"]["rows"];B=d["arms"][m+"_carryFalse"]["rows"]
    print(m)
    for a,b in zip(A,B):
        z=abs(a["a"]-b["a"])/a["a_esd"] if a["a"] and a["a_esd"] else None
        print(a["label"],a["status"],b["status"],a["rung"],a["n_evals"],b["n_evals"],"rwp %.4f %.4f"%(a["rwp"],b["rwp"]),"gof %.3f"%a["gof"],"err",None if a.get("a_err_ppm") is None else round(a["a_err_ppm"],1),None if b.get("a_err_ppm") is None else round(b["a_err_ppm"],1),"dz",None if z is None else "%.3g"%z)

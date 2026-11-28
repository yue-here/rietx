import sys, os, shutil
sys.argv = ["x"]; sys.path.insert(0, os.path.dirname(__file__))
import fpcpd
from pathlib import Path
for tag, dl, sl in [("dl0", 0.0, None), ("dl", 0.01, None), ("noasym", 0.0, 0.0)]:
    d = fpcpd.FPD / f"t_{tag}"; d.mkdir(exist_ok=True)
    P = fpcpd.start_params(); P["DL"] = dl
    if sl is not None: P["SL"] = sl
    fpcpd.write_pcr(d / "cpd.pcr", P, 20, 0.01, free="all")
    shutil.copy(fpcpd.CPD / "cpd-1e.dat", d / "cpd.dat"); fpcpd.run(d)
    r = fpcpd.parse(d)
    print(tag, r["cycles"], round(r["chi2"], 1), [(k, "%.4g" % r["values"][k], "%.2g" % r["sig"][k]) for k in r["values"] if k[:2] in ("U-", "V-", "W-", "SL")])

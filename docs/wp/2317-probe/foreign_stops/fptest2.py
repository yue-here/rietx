import sys, os, shutil, re
sys.argv = ["x"]; sys.path.insert(0, os.path.dirname(__file__))
import fpcpd
for tag, dl, slfree in [("dl001", 0.01, True), ("dl0_slheld", 0.0, False)]:
    d = fpcpd.FPD / f"t2_{tag}"; d.mkdir(exist_ok=True)
    P = fpcpd.start_params(); P["DL"] = dl
    # use the linear-fit background and scales from b5 so the start is the same
    lin = fpcpd.parse(fpcpd.FPD / "b5")
    P["bkg"] = [lin["values"][f"Bck_{i}_pat1"] for i in range(6)]
    for k in range(3): P["ph"][k]["scale"] = lin["values"][f"Scale_ph{k+1}_pat1"]
    fpcpd.FREE_SL = slfree
    fpcpd.write_pcr(d / "cpd.pcr", P, 300, 0.001, free="all")
    shutil.copy(fpcpd.CPD / "cpd-1e.dat", d / "cpd.dat"); fpcpd.run(d)
    r = fpcpd.parse(d)
    out = (d / "cpd.out").read_text(errors="replace")
    chis = [float(x) for x in re.findall(r"Conventional Rietveld Rp,Rwp,Re and Chi2:\s+\S+\s+\S+\s+\S+\s+(\S+)", out)][1::2]
    print(tag, r["cycles"], r["converged"], round(r["chi2"], 1), "chi2red at cyc 10,20,50,100,300:", [chis[i] for i in (9, 19, 49, 99, -1)],
          "min", min(chis), [(k, "%.4g" % r["values"][k], "%.2g" % r["sig"][k]) for k in r["values"] if k[:2] in ("SL", "Ze", "Sy")])

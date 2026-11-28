"""Run rietx's cpd-1 chained fixture (shipped stops) over cpd-1a..1f and export
the model states at the start of 1e and 1f plus the 1e/1f answers.
usage: <rietx python> export_cpd.py OUTDIR   (cwd = repo root)"""
import json, os, sys
from pathlib import Path
os.environ.setdefault("RIETX_TELEMETRY", "0"); os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.getcwd())
import numpy as np
import rietx as rx
from tests.test_acceptance_qpa_roundrobin import (DATA, SAMPLE1, corundum_phase, fluorite_phase,
    qarr_instrument, qpa_plan, seed_scales, zincite_phase)
from tests.test_acceptance_sequential import CARRY
out = Path(sys.argv[1]); out.mkdir(exist_ok=True)
labels = list(SAMPLE1[:6])
patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in labels]
for s, p in zip(labels, patterns):
    x = np.asarray(p.two_theta); y = np.asarray(p.intensity); sig = np.asarray(p.sig())
    np.savetxt(out / f"{s}.xye", np.c_[x, y, sig], fmt="%.4f %.3f %.4f")
    with open(out / f"{s}.dat", "w") as f:
        f.write(f"{x[0]:.4f} {x[1]-x[0]:.4f} {x[-1]:.4f}\n")
        for i in range(0, len(y), 10):
            f.write(" ".join(f"{v:.0f}" for v in y[i:i+10]) + "\n")
states = {}
def hook(index, data, structure, instrument):
    seed_scales(structure, instrument, data)
    states[labels[index]] = {"structure": structure.model_dump(mode="json"),
                             "instrument": instrument.model_dump(mode="json")}
structure = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase()])
ins = qarr_instrument()
series = rx.SequentialRefinement(structure, ins, carry=CARRY)
res = series.fit(patterns, labels=labels, plan=qpa_plan(), prepare=hook)
answers = {}
for k, e in enumerate(res.entries):
    fit = series.results_[k]
    answers[e.label] = {"chi2": fit.statistics.chi2, "n_points": fit.statistics.n_points,
        "n_free": fit.statistics.n_free_parameters, "rung": e.rung, "status": e.status,
        "rwp": fit.statistics.rwp,
        "params": {p.path: [p.value, p.stderr, p.stderr_uncorrected] for p in fit.parameters},
        "qpa": {ph.name: [ph.weight_fraction, ph.weight_fraction_stderr] for ph in fit.qpa.phases}}
(out / "rietx_cpd.json").write_text(json.dumps({"states": states, "answers": answers}, indent=1))
print("done", {k: (v["chi2"], v["n_free"]) for k, v in answers.items()})

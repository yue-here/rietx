"""Part 2: differences across a series under each last-stage stop.

usage: python series.py cucr2o4|cpd1   -> results/series_<name>.json

cucr2o4: WP-2081's ``default`` route (docs/wp/2081-batch/measure_real_ramp.py):
  SequentialRefinement(structure, instrument).fit(patterns, x=T, plan=mccusker_default).
cpd1: tests/test_acceptance_sequential.py's ``chained`` fixture: carry=CARRY,
  prepare=seed hook, qpa_plan() (closing stage on).
"""
from __future__ import annotations

import dataclasses
import json
import os
import platform
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # the repository root
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
import stops  # noqa: E402
from single import nudge  # noqa: E402

stops.install()
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
DATA = ROOT / "tests" / "data" / "seqrefine_cucr2o4"


def temperature(path: Path) -> float:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]:
        if "Temp (K)" in line:
            return float(line.split("=")[-1].split()[0])
    raise ValueError(path)


def cucr2o4_models():
    from rietx.schemas.instrument import BackgroundChebyshev
    main = rx.Structure.from_cif(DATA / "CuCr2O4.cif")
    minor = rx.Structure.from_cif(DATA / "CuO.cif")
    structure = main.model_copy(deep=True)
    structure.phases = list(main.phases) + list(minor.phases)
    structure.phases[0].name, structure.phases[1].name = "CuCr2O4", "CuO"
    for phase in structure.phases:
        for atom in phase.atoms:
            if atom.biso.value <= 0.0:
                atom.biso.value = 0.3
    structure.phases[0].scale.value = 1.0
    structure.phases[1].scale.value = 0.05
    instrument = rx.read_gsas_prm(DATA / "OH_00.prm")
    instrument.background = BackgroundChebyshev.with_terms(8)
    return structure, instrument


def last_ftol(plan, stop):
    """As stops.set_last_ftol, but a plain ftol is lifted 1e-7 relative so the
    last stage's solves can be told from the intermediate ones in the log."""
    f = stops.last_stage_ftol(stop)
    if f is None:
        f = 1e-9 * (1 + 1e-7)
    elif stop.startswith("ftol"):
        f = f * (1 + 1e-7)
    plan.stages[-1] = dataclasses.replace(plan.stages[-1], ftol=f)
    return plan, f


def run(name: str, stop: str, seed: int | None = None) -> dict:
    stops.LOG.clear()
    if name == "cucr2o4":
        paths = sorted(DATA.glob("OH_*.fxye"))
        patterns = [rx.read_pattern(p) for p in paths]
        x = [temperature(p) for p in paths]
        structure, ins = cucr2o4_models()
        plan, f = last_ftol(rx.RefinementPlan.mccusker_default(), stop)
        if seed is not None:
            rng = np.random.default_rng(seed)
            nudge(structure, rng)
            nudge(ins, rng)
        series = rx.SequentialRefinement(structure, ins)
        t0 = time.time()
        result = series.fit(patterns, x=x, x_label="T (K)", plan=plan)
    else:
        from tests.test_acceptance_qpa_roundrobin import (
            DATA as QD, SAMPLE1, corundum_phase, fluorite_phase, qarr_instrument,
            qpa_plan, seed_scales, zincite_phase)
        from tests.test_acceptance_sequential import CARRY
        patterns = [rx.read_pattern(QD / f"{s}.prn") for s in SAMPLE1]
        structure = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase()])
        ins = qarr_instrument()
        if seed is not None:
            rng = np.random.default_rng(seed)
            nudge(structure, rng)
            nudge(ins, rng)
        plan, f = last_ftol(qpa_plan(), stop)

        def hook(index, data, structure, instrument):
            seed_scales(structure, instrument, data)
        series = rx.SequentialRefinement(structure, ins, carry=CARRY)
        t0 = time.time()
        result = series.fit(patterns, labels=list(SAMPLE1), plan=plan, prepare=hook)
    wall = time.time() - t0
    rows = []
    for k, entry in enumerate(result.entries):
        fit = series.results_[k]
        rows.append({
            "x": entry.x, "label": entry.label, "rung": entry.rung, "status": entry.status,
            "chi2": fit.statistics.chi2, "n_points": fit.statistics.n_points,
            "n_free": fit.statistics.n_free_parameters,
            "params": {p.path: [p.value, p.stderr] for p in fit.parameters},
            "qpa": ({ph.name: [ph.weight_fraction, ph.weight_fraction_stderr]
                     for ph in fit.qpa.phases} if fit.qpa is not None else {}),
        })
    last = [c for c in stops.LOG if c["ftol"] == f]
    return {"series": name, "stop": stop, "seed": seed, "wall_s": round(wall, 1),
            "nfev_total": sum(c["nfev"] for c in stops.LOG),
            "nfev_last_stage": sum(c["nfev"] for c in last), "n_last_calls": len(last),
            "n_calls": len(stops.LOG), "rows": rows,
            "codes": sorted({d.code for d in result.diagnostics})}


def main():
    name = sys.argv[1]
    plan_stops = ["ftol1e-9", "ftol1e-8", "ftol1e-6", "ftol1e-4", "gsas", "gsas3",
                  "fp0.2", "fp0.1"]
    recs = []
    out_path = OUT / f"series_{name}.json"
    for stop in plan_stops:
        recs.append(run(name, stop))
        print(name, stop, recs[-1]["nfev_total"], recs[-1]["nfev_last_stage"], flush=True)
        out_path.write_text(json.dumps({"runs": recs}, indent=1))
    for seed in range(2):
        recs.append(run(name, "ftol1e-9", seed=seed))
        print(name, "nudge", seed, flush=True)
        out_path.write_text(json.dumps({"runs": recs}, indent=1))
    out = {"platform": f"{platform.system()} {platform.machine()}",
           "python": platform.python_version(), "rietx": rx.__version__, "runs": recs}
    out_path.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

"""Part 1: convergence noise in a single fit.

usage: python single.py FIXTURE [FIXTURE ...]   -> results/single_<fixture>.json
"""
from __future__ import annotations

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
sys.path.insert(1, str(ROOT / "tests"))  # test_large_cell_refinement.py, on main since PR #1866

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
import stops  # noqa: E402

stops.install()
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)


# -- fixtures: each returns (structure, instrument, data, plan, kwargs, prepare)

def _std(key):
    from rietx.viz.compare import STANDARD_BY_KEY, default_data_dir

    def build():
        inp = STANDARD_BY_KEY[key].build(default_data_dir())
        return (inp.structure, inp.instrument, inp.data, inp.plan,
                {"two_theta_limits": inp.two_theta_limits}, None)
    return build


def _cpd1a():
    from tests.test_acceptance_qpa_roundrobin import (
        DATA, corundum_phase, fluorite_phase, qarr_instrument, qpa_plan,
        seed_scales, zincite_phase)
    data = rx.read_pattern(DATA / "cpd-1a.prn")
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase()])
    ins = qarr_instrument()
    seed_scales(structure, ins, data)
    return structure, ins, data, qpa_plan(), {}, None


def _bigcell():
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import BackgroundChebyshev
    from test_large_cell_refinement import NB18W16O93, large_cell_phase, tie_co_sited

    def phase(drift):
        return large_cell_phase(NB18W16O93, scale=3e-5, drift=drift)

    def instrument(truth):
        ins = rx.Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=250.0,
                                           monochromator_two_theta=26.6)
        ins.background = BackgroundChebyshev.with_terms(6)
        ins.source.dispersion = None
        ins.geometry.axial_sl.value = 0.03 if truth else 0.02
        ins.geometry.axial_hl.value = 0.03 if truth else 0.02
        ins.profile.w.value = 0.006 if truth else 0.010
        ins.profile.x.value = 0.02 if truth else 0.01
        if truth:
            ins.background.coefficients[0].value = 900.0
        return ins

    tt = np.arange(5.0, 90.0, 0.02)
    s0 = rx.Structure(phases=[phase(0.0)])
    i0 = instrument(True)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())
    model = compile_model(s0, i0, blank)
    table = ParameterTable(s0, i0)
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    counts = np.random.default_rng(1).poisson(np.clip(y, 1.0, None))
    data = rx.PatternData(two_theta=tt.tolist(), intensity=counts.astype(float).tolist())
    return (rx.Structure(phases=[phase(5e-4)]), instrument(False), data,
            rx.RefinementPlan.mccusker_structural(), {"mode": "rietveld"}, tie_co_sited)


FIXTURES = {"srm660c": _std("srm660c"), "fap": _std("fap"), "nac": _std("nac"),
            "cpd1a": _cpd1a, "bigcell": _bigcell}


def nudge(obj, rng, rel=1e-12, _path=""):
    """Multiply every Parameter value outside the source by (1 + rel*u)."""
    from pydantic import BaseModel
    if isinstance(obj, rx.Parameter):
        if obj.value != 0.0:
            obj.value = obj.value * (1.0 + rel * rng.uniform(-1, 1))
        return
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            if name == "source":
                continue
            nudge(getattr(obj, name), rng, rel, f"{_path}.{name}")
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            nudge(v, rng, rel, _path)


def run_one(fixture: str, stop: str, seed: int | None = None) -> dict:
    structure, ins, data, plan, kw, prepare = FIXTURES[fixture]()
    if seed is not None:
        rng = np.random.default_rng(seed)
        nudge(structure, rng)
        nudge(ins, rng)
    stops.set_last_ftol(plan, stop)
    stops.LOG.clear()
    ref = rx.Refinement(structure, ins, history=False)
    if prepare is not None:
        prepare(ref)
    t0 = time.time()
    result = ref.fit(data, plan=plan, **kw)
    wall = time.time() - t0
    st = result.statistics
    params = {p.path: [p.value, p.stderr, p.stderr_uncorrected] for p in result.parameters}
    qpa = {}
    if result.qpa is not None:
        for ph in result.qpa.phases:
            qpa[ph.name] = [ph.weight_fraction, ph.weight_fraction_stderr]
    return {
        "fixture": fixture, "stop": stop, "seed": seed, "wall_s": round(wall, 2),
        "chi2": st.chi2, "rwp": st.rwp, "gof": st.gof, "n_points": st.n_points,
        "n_free": st.n_free_parameters, "esd_inflation": st.esd_inflation,
        "max_shift_over_esd": st.max_shift_over_esd, "status": result.status,
        "stages": [{"name": s.name, "ftol": s.ftol, "n_iterations": s.n_iterations,
                    "termination": s.termination, "status": s.status}
                   for s in result.stages],
        "calls": [dict(c) for c in stops.LOG],
        "params": params, "qpa": qpa,
        "codes": sorted({d.code for d in result.diagnostics}),
    }


def main():
    stop_list = os.environ.get("STOPS", ",".join(stops.STOPS)).split(",")
    n_nudge = int(os.environ.get("NUDGES", "5"))
    suffix = os.environ.get("SUFFIX", "")
    for fixture in sys.argv[1:]:
        recs = []
        for stop in stop_list:
            recs.append(run_one(fixture, stop))
            print(fixture, stop, recs[-1]["chi2"], recs[-1]["calls"][-1]["nfev"], flush=True)
        for seed in range(n_nudge):
            recs.append(run_one(fixture, "ftol1e-9", seed=seed))
            print(fixture, "nudge", seed, recs[-1]["chi2"], flush=True)
        out = {"platform": f"{platform.system()} {platform.machine()}",
               "python": platform.python_version(), "rietx": rx.__version__,
               "runs": recs}
        (OUT / f"single_{fixture}{suffix}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

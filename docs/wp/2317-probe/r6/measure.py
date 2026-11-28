"""R6 as shipped: the shift test against the 1e-9 stop it replaces (WP-2317).

usage: python measure.py single KEY [KEY ...]   -> results/single_<key>.json
       python measure.py series cucr2o4|cpd1    -> results/series_<name>.json

Two arms run on the shipped code and differ in one plan field:
``tight`` sets ``RefinementPlan.shift_over_esd_tol = None`` (every stage stops
on its ftol, the last at 1e-9, as before WP-2317) and ``shipped`` keeps the
default 0.1.  The departure of a value is |shipped - tight| over the tight
arm's reported esd, over every refined parameter and QPA fraction, the worst
reported with its path.  Evaluations are the LM driver's own counts
(``nfev`` residual evaluations, ``njev`` Jacobians), summed over every solve.

Single-fit keys: the R6 probe's five (``srm660c``, ``fap``, ``nac``, ``cpd1a``,
``bigcell`` from ``../convnoise/single.py``) and the acceptance's bench cases
(``bigcell-structural``, ``bigcell-pawley``, ``bigcell-pawley-120``,
``bigcell-lebail`` from ``examples/bench_refinement.py``).  Each single fit runs
the arms interleaved, ``REPEATS`` times (default 2), for a wall-clock range.
The series run once an arm: the CuCr2O4 ramp (17 patterns, mccusker_default)
and the cpd-1 chain (8 patterns, qpa_plan), as ``../convnoise/series.py``.
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
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "convnoise"))
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "tests"))
sys.path.insert(2, str(ROOT / "examples"))

import rietx as rx  # noqa: E402
import rietx.optimize.lm as lm  # noqa: E402

_ORIG = lm.minimize
import single as _single  # noqa: E402  (installs the probe's wrapper, undone below)

lm.minimize = _ORIG
import series as _series  # noqa: E402

lm.minimize = _ORIG
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
LOG: list[dict] = []


def _spy(*args, **kwargs):
    out = _ORIG(*args, **kwargs)
    LOG.append({"nfev": out.nfev, "njev": out.njev, "termination": out.termination,
                "shift_tol": kwargs.get("shift_tol"), "n_free": len(out.x)})
    return out


lm.minimize = _spy


def _bench(key):
    import bench_refinement as bench

    def build():
        setup = next(c for c in bench.CASES if c.key == key).build()
        kw = {"mode": setup.mode}
        if setup.limits is not None:
            kw["two_theta_limits"] = setup.limits
        return (setup.structure, setup.instrument, setup.data, setup.plan, kw,
                setup.prepare)
    return build


FIXTURES = dict(_single.FIXTURES)
for _key in ("bigcell-structural", "bigcell-pawley", "bigcell-pawley-120",
             "bigcell-lebail"):
    FIXTURES[_key] = _bench(_key)


def _arm(plan, arm):
    plan.shift_over_esd_tol = None if arm == "tight" else rx.RefinementPlan(
        stages=[]).shift_over_esd_tol
    return plan


def _values(fit):
    vals = {p.path: (p.value, p.stderr) for p in fit.parameters}
    if fit.qpa is not None:
        for ph in fit.qpa.phases:
            vals[f"qpa.{ph.name}"] = (ph.weight_fraction, ph.weight_fraction_stderr)
    return vals


def _counts():
    shipped_stops = [c for c in LOG if c["shift_tol"] is not None]
    return {"nfev": sum(c["nfev"] for c in LOG), "njev": sum(c["njev"] for c in LOG),
            "n_solves": len(LOG),
            "terminations": [c["termination"] for c in shipped_stops]}


def run_single(key, arm):
    structure, ins, data, plan, kw, prepare = FIXTURES[key]()
    _arm(plan, arm)
    LOG.clear()
    ref = rx.Refinement(structure, ins, history=False)
    if prepare is not None:
        prepare(ref)
    t0 = time.perf_counter()
    result = ref.fit(data, plan=plan, **kw)
    wall = time.perf_counter() - t0
    last = result.stages[-1]
    return {"arm": arm, "wall_s": wall, **_counts(), "rwp": result.statistics.rwp,
            "last_stage": {"name": last.name, "n_iterations": last.n_iterations,
                           "termination": last.termination,
                           "shift_over_esd_tol": last.shift_over_esd_tol},
            "values": _values(result)}


def run_series(name, arm):
    LOG.clear()
    if name == "cucr2o4":
        paths = sorted(_series.DATA.glob("OH_*.fxye"))
        patterns = [rx.read_pattern(p) for p in paths]
        x = [_series.temperature(p) for p in paths]
        structure, ins = _series.cucr2o4_models()
        plan = _arm(rx.RefinementPlan.mccusker_default(), arm)
        series = rx.SequentialRefinement(structure, ins)
        t0 = time.perf_counter()
        series.fit(patterns, x=x, x_label="T (K)", plan=plan)
    else:
        from tests.test_acceptance_qpa_roundrobin import (
            DATA as QD,
        )
        from tests.test_acceptance_qpa_roundrobin import (
            SAMPLE1,
            corundum_phase,
            fluorite_phase,
            qarr_instrument,
            qpa_plan,
            seed_scales,
            zincite_phase,
        )
        from tests.test_acceptance_sequential import CARRY
        patterns = [rx.read_pattern(QD / f"{s}.prn") for s in SAMPLE1]
        structure = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase()])
        ins = qarr_instrument()
        plan = _arm(qpa_plan(), arm)

        def hook(index, data, structure, instrument):
            seed_scales(structure, instrument, data)
        series = rx.SequentialRefinement(structure, ins, carry=CARRY)
        t0 = time.perf_counter()
        series.fit(patterns, labels=list(SAMPLE1), plan=plan, prepare=hook)
    wall = time.perf_counter() - t0
    return {"arm": arm, "wall_s": wall, **_counts(),
            "patterns": [_values(fit) for fit in series.results_]}


def departure(tight, shipped):
    worst, where = 0.0, None
    for path, (v0, e0) in tight.items():
        if path not in shipped or e0 is None or not e0 > 0.0:
            continue
        d = abs(shipped[path][0] - v0) / e0
        if d > worst:
            worst, where = d, path
    return worst, where


def main():
    kind, keys = sys.argv[1], sys.argv[2:]
    repeats = int(os.environ.get("REPEATS", "2"))
    head = {"platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "rietx": rx.__version__,
            "venv": sys.prefix}
    for key in keys:
        if kind == "single":
            runs = [run_single(key, arm) for _ in range(repeats)
                    for arm in ("tight", "shipped")]
            t = next(r for r in runs if r["arm"] == "tight")
            s = next(r for r in runs if r["arm"] == "shipped")
            worst, where = departure(t["values"], s["values"])
        else:
            runs = [run_series(key, arm) for arm in ("tight", "shipped")]
            t, s = runs
            worst, where = 0.0, None
            for k, (pt, ps) in enumerate(zip(t["patterns"], s["patterns"], strict=True)):
                w, p = departure(pt, ps)
                if w > worst:
                    worst, where = w, f"pattern {k}: {p}"
        summary = {
            "key": key, "worst_esd": worst, "worst_at": where,
            "nfev": {a: [r["nfev"] for r in runs if r["arm"] == a] for a in ("tight", "shipped")},
            "njev": {a: [r["njev"] for r in runs if r["arm"] == a] for a in ("tight", "shipped")},
            "wall_s": {a: [round(r["wall_s"], 2) for r in runs if r["arm"] == a]
                       for a in ("tight", "shipped")},
            "shipped_terminations": sorted(set(s["terminations"])),
        }
        if kind == "single":
            summary["last_stage"] = {a: next(r for r in runs if r["arm"] == a)["last_stage"]
                                     for a in ("tight", "shipped")}
            summary["rwp"] = {"tight": t["rwp"], "shipped": s["rwp"]}
        print(json.dumps(summary), flush=True)
        (OUT / f"{kind}_{key}.json").write_text(
            json.dumps({**head, "summary": summary, "runs": runs}, indent=1),
            encoding="utf-8")


if __name__ == "__main__":
    main()

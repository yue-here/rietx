"""Error-measurement jobs: one fit per (fixture, setting, seed), one JSON each.

usage: python run.py JOBFILE NWORKERS
  JOBFILE: lines "fixture setting seed" (seed "none" = unnudged start).
  Each job writes results/<fixture>__<setting>__<seed>.json; existing files skip.

Reuses ../convnoise: its fixtures, its nudge (every model Parameter value x
(1 + 1e-12 u), u ~ U[-1, 1], default_rng(seed), structure then instrument) and
its stop wrapper (stops.py).  Nothing in src/ is changed.

Settings:
  ref            the shipped plan (cpd1a's qpa_plan carries closing 1e-3)
  ftol<x>        last declared stage's ftol = x (the closing stage copies it)
  gsas           convnoise's GSAS-II-like stop on the last stage
  cw<x>          plan.closing_window_tol = x (closing stage on, at window x)
  cwNone         closing stage off
  cw<x>+gsas etc combinations joined by '+'
  hold<x>        bigcell injection, see inject()
"""
from __future__ import annotations

import concurrent.futures as cf
import dataclasses
import json
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("RIETX_COMPILED_THREADS", "2")
HERE = Path(__file__).resolve().parent
CONV = HERE.parent / "convnoise"
ROOT = HERE.parents[3]
OUT = HERE / "results"
PLOTS = ROOT / "tests" / "output"


def _setup():
    for p in (str(HERE / "bigcell"), str(CONV), str(ROOT), str(ROOT / "tests")):
        if p not in sys.path:
            sys.path.insert(0, p)


def apply_setting(plan, setting: str, ref_obj, fixture: str):
    import stops
    for part in setting.split("+"):
        if part == "ref":
            continue
        if part.startswith("ftol"):
            f = float(part[4:])
            plan.stages[-1] = dataclasses.replace(plan.stages[-1], ftol=f)
        elif part == "gsas":
            stops.set_last_ftol(plan, "gsas")
        elif part.startswith("cw"):
            v = part[2:]
            plan.closing_window_tol = None if v == "None" else float(v)
        elif part.startswith("hold"):
            pass  # handled in prepare
        else:
            raise ValueError(part)
    return plan


def job(fixture: str, setting: str, seed) -> str:
    _setup()
    import numpy as np
    import rietx as rx
    import single  # convnoise: installs the stop wrapper
    import stops

    name = f"{fixture}__{setting}__{seed}"
    out = OUT / f"{name}.json"
    if out.exists():
        return f"skip {name}"
    structure, ins, data, plan, kw, prepare = single.FIXTURES[fixture]()
    if seed != "none":
        rng = np.random.default_rng(int(seed))
        single.nudge(structure, rng)
        single.nudge(ins, rng)
    plan = apply_setting(plan, setting, None, fixture)
    stops.LOG.clear()
    ref = rx.Refinement(structure, ins, history=False)
    if prepare is not None:
        prepare(ref)
    inj = None
    for part in setting.split("+"):
        if part.startswith("hold"):
            inj = inject(ref, part)
    t0 = time.time()
    result = ref.fit(data, plan=plan, **kw)
    wall = time.time() - t0
    st = result.statistics
    params = {p.path: [p.value, p.stderr, p.stderr_uncorrected] for p in result.parameters}
    qpa = {}
    if result.qpa is not None:
        for ph in result.qpa.phases:
            qpa[ph.name] = [ph.weight_fraction, ph.weight_fraction_stderr]
    rec = {
        "fixture": fixture, "setting": setting, "seed": seed, "wall_s": round(wall, 2),
        "chi2": st.chi2, "rwp": st.rwp, "n_points": st.n_points,
        "n_free": st.n_free_parameters, "esd_inflation": st.esd_inflation,
        "max_shift_over_esd": st.max_shift_over_esd, "status": result.status,
        "stages": [{"name": s.name, "ftol": s.ftol, "n_iterations": s.n_iterations,
                    "termination": s.termination, "window_area_tol": s.window_area_tol}
                   for s in result.stages],
        "nfev": [c["nfev"] for c in stops.LOG],
        "params": params, "qpa": qpa, "inject": inj,
    }
    out.write_text(json.dumps(rec))
    if seed == "none":
        try:
            from rietx.viz.plots import plot_result
            PLOTS.mkdir(parents=True, exist_ok=True)
            fig = plot_result(result, path=PLOTS / f"errmeasure_{fixture}_{setting}.png")
            import matplotlib.pyplot as plt
            plt.close("all")
        except Exception as e:  # a plot never fails a job
            rec["plot_error"] = repr(e)
            out.write_text(json.dumps(rec))
    return f"done {name} wall={wall:.1f}s chi2={st.chi2:.6f}"


def inject(ref, part):
    """hold<path>@<delta_esd>: hold <path> at the unnudged reference answer + delta x esd.

    The value and esd are read from results/<fixture>__ref__none.json, so the
    injected error on that parameter is delta esd by construction.
    """
    spec = part[4:]
    path, delta = spec.split("@")
    refrec = json.loads((OUT / "bigcell__ref__none.json").read_text())
    v, e, _ = refrec["params"][path]
    target = v + float(delta) * e
    ref.set_values({path: target})
    ref.hold([path])
    return {"path": path, "target": target, "ref_value": v, "esd": e, "delta_esd": float(delta)}


def main():
    jobs = [ln.split() for ln in Path(sys.argv[1]).read_text().splitlines() if ln.strip()]
    n = int(sys.argv[2])
    OUT.mkdir(exist_ok=True)
    with cf.ProcessPoolExecutor(max_workers=n, max_tasks_per_child=1) as ex:
        futs = {ex.submit(job, *j): j for j in jobs}
        for f in cf.as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception:
                print("FAIL", futs[f], traceback.format_exc(), flush=True)


if __name__ == "__main__":
    main()

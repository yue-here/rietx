"""WP-1964 task 13: the WO3 ramp's Einstein cell equations written as formula text.

    .venv/bin/python docs/wp/1964-measure/wo3_formula.py --arm=design [--subset=topas11]
    .venv/bin/python docs/wp/1964-measure/wo3_formula.py --arm=text [--subset=topas11]
    .venv/bin/python docs/wp/1964-measure/wo3_formula.py --arm=free [--subset=topas11]
    .venv/bin/python docs/wp/1964-measure/wo3_formula.py --arm=pin --theta=71.47 [--subset=topas11]
    .venv/bin/python docs/wp/1964-measure/wo3_formula.py --arm=report [--subset=topas11] \
        > docs/wp/1964-measure/wo3_formula_results.txt

Run from the repository root, after WP-1325's ``wo3_ramp.py`` both ways.
Every joint fit starts from each pattern's better chain answer (``wo3_ramp.best_chain``).
The chains are read from ``$WO3_SCRATCH``, and each arm caches its answer there as JSON.
``--arm=report`` reads those answers and prints this measurement's results.
The data is Durham TOPAS tutorials 9.3/9.4, local only (``python -m tests.local_data durham-topas/wo3``).

The protocol is WP-1325's (``wo3_form.py``, ``wo3_ramp.py``'s docstring), unchanged.
Nothing is shared across patterns but the equations' coefficients.
B is held at the chain's value, the coordinates at TOPAS's, and each pattern refines its own strains.
The input's own protocol ties one B per pattern across every atom and shares the W coordinates and strains.
That needs WP-2103's tie in a joint fit, which has not landed, so this script does not build it.
Each angle is a quadratic in T (``polynomial``) in every arm.

The arms, each one joint fit:

* ``design``: each of the nine cell edges a ``design`` equation, a0 + g/(exp(θ/T) - 1).
  θ is held at TOPAS's 125.370423 K, as WP-1325 ran it.
* ``text``: the same nine edges as formula text, ``zero_X + grad_X/(exp(theta/T) - 1)``.
  ``theta`` is one variable named by all nine, held at 125.370423 K.
  Each edge's two variables start where the design arm's coefficients start.
  That start is the unweighted least-squares line through the chain's cells (``least_squares_start``).
  So the two arms differ in nothing but how the equation is written.
* ``free``: as ``text``, with ``theta`` freed in the cell stage, bounded to [1, 2000] K.
* ``pin``: as ``text``, with ``theta`` held at ``--theta``, one point of a hand profile.

The gate is ``text`` against ``design``: every parameter the two report agrees to 0.01 of its esd.
The rest has no gate.
The report gives θ free with its esd and whether it reaches a bound, and the profile χ² against θ.
It gives each cell parameter's largest gap to TOPAS over the ramp's 100 temperatures, in ppm.
Beside that it gives the spread between ``parametric_05.inp`` and ``parametric_06.inp``.
``parametric_05.inp`` stores TOPAS's 11-pattern fit (``#define refine_some``), θ 125.37 K, Rwp 12.872 %.
``parametric_06.inp`` stores its 100-pattern fit, θ 71.47 K, Rwp 12.809 %.
``--subset=topas11`` fits TOPAS's own 11 patterns (0-based 0, 10, ..., 90, 99), the ones its 05 fit used.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE.parent / "1325-measure"))

import numpy as np  # noqa: E402
from wo3_form import joint_plan, topas_equations, widened  # noqa: E402
from wo3_ramp import (  # noqa: E402
    DATASET,
    SCRATCH,
    _number,
    _total_chi2,
    best_chain,
    einstein,
    load,
    parse_args,
    targets,
    topas_equation,
)

import rietx as rx  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.viz.plots import plot_result  # noqa: E402
from tests import local_data  # noqa: E402

OUT = REPO / "tests" / "output"
THETA_MIN, THETA_MAX = 1.0, 2000.0
SUBSETS = {"all": list(range(100)), "topas11": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 99]}


def edges() -> dict[str, str]:
    return {k: p for k, p in targets().items() if k.split("_", 1)[1] in "abc"}


def text_equations() -> list[rx.ParametricEquation]:
    """Nine edges as text, then the five angles as WP-1325's polynomials."""
    out = [rx.ParametricEquation(name=k, target=p, basis="expression",
                                 expression=f"zero_{k} + grad_{k}/(exp(theta/T) - 1)")
           for k, p in edges().items()]
    angles = [k for k in targets() if k not in edges()]
    return out + topas_equations(np.zeros(1), 0.0, keys=angles)


def start_variables(structures: list[rx.Structure], temps: np.ndarray, theta: float,
                    free: bool) -> dict[str, rx.Parameter]:
    """Each edge's (zero, grad) where a design equation starts: lstsq through the start cells."""
    out = {}
    phi = np.column_stack([np.ones(len(temps)), [einstein(float(t), theta) for t in temps]])
    for k, path in edges().items():
        i, name = int(path.split(".")[1]), path.rsplit(".", 1)[1]
        v = np.array([getattr(s.phases[i].cell, name).value for s in structures])
        c, *_ = np.linalg.lstsq(phi, v, rcond=None)
        out[f"zero_{k}"] = rx.Parameter(value=float(c[0]), vary=True)
        out[f"grad_{k}"] = rx.Parameter(value=float(c[1]), vary=True)
    out["theta"] = rx.Parameter(value=theta, vary=free, min=THETA_MIN, max=THETA_MAX, unit="K")
    return out


def cache_path(arm: str, subset: str, theta: float) -> Path:
    return SCRATCH / f"wo3_formula_{subset}_{arm}_{theta:.4f}.json"


def run(arm: str, subset: str, theta: float) -> None:
    data = load(0, 99)
    chain = best_chain()
    if chain is None:
        raise SystemExit("run wo3_ramp.py first, both directions: this reads its cached chains")
    idx = SUBSETS[subset]
    temps = data["temps"][idx]
    structures = widened([chain["structures"][k] for k in idx])
    if arm == "design":
        equations, variables = topas_equations(temps, theta), None
    else:
        equations = text_equations()
        variables = start_variables(structures, temps, theta, free=(arm == "free"))
    t0 = time.perf_counter()
    fit = rx.MultiHistogramRefinement(
        structures, [chain["instruments"][k] for k in idx],
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": temps.tolist()}, units={"T": "K"}),
        parametric=equations, variables=variables)
    result = fit.fit([data["patterns"][k] for k in idx], plan=joint_plan(),
                     two_theta_limits=data["proto"]["limits"])
    seconds = time.perf_counter() - t0
    s = result.statistics
    rows = {p.path: [p.value, p.stderr, bool(getattr(p, "at_bound", False) or False)]
            for p in result.parameters}
    all_t = data["temps"]
    curves = {}
    for key in targets():
        if key in edges() and arm != "design":
            th = rows["vars.theta"][0] if "vars.theta" in rows else theta
            curves[key] = [rows[f"vars.zero_{key}"][0] + rows[f"vars.grad_{key}"][0] * einstein(float(t), th)
                           for t in all_t]
        elif key in edges():
            curves[key] = [result.parametric_value(key, row=[1.0, einstein(float(t), theta)]).value
                           for t in all_t]
        else:
            curves[key] = [result.parametric_value(key, {"T": float(t)}).value for t in all_t]
    payload = dict(
        arm=arm, subset=subset, theta=theta, seconds=seconds, status=result.status,
        load=os.getloadavg(), iters=[st.n_iterations for st in result.stages],
        rwp=s.rwp, chi2=_total_chi2(s), chi2r=s.chi2, n_free=s.n_free_parameters,
        inflation=s.esd_inflation, rows=rows, curves=curves,
        coefficients=[[c.equation, c.term, c.value, c.esd] for c in result.parametric or []],
        diagnostics=sorted({d.code for d in result.diagnostics}),
        held=sorted({p for st in result.stages for p in st.held}))
    cache_path(arm, subset, theta).write_text(json.dumps(payload), encoding="utf-8")
    print(f"{arm} {subset} θ {theta:g}: {seconds:.1f} s, {result.status}, Rwp {100 * s.rwp:.3f} %, "
          f"χ² {payload['chi2']:.1f}, {s.n_free_parameters} free, iters {payload['iters']}")
    if arm in ("text", "free"):
        OUT.mkdir(exist_ok=True)
        for h in sorted({0, len(idx) // 2, len(idx) - 1}):
            plot_result(result.for_histogram(h),
                        path=str(OUT / f"wp1964_wo3_{subset}_{arm}_h{h}_fit.png"))


# -- the report --------------------------------------------------------------

def topas06() -> dict:
    root = local_data.dataset(DATASET)
    if root is None:
        raise SystemExit(f"{DATASET} is not in the local data root")
    with zipfile.ZipFile(root / "parametric_06.zip") as z:
        name = next(n for n in z.namelist() if n.endswith("parametric_06.inp"))
        text = z.read(name).decode("utf-8", errors="replace")
    prm = {m.group(1): _number(m.group(2))
           for m in re.finditer(r"\bprm\s+!?(\w+)\s+(-?\d[\d.eE+-]*`?)", text)}
    return dict(prm=prm, theta=prm["theta_ma"])


def gate(design: dict, text: dict) -> None:
    worst = {}
    for path, (v, e, _) in design["rows"].items():
        if path not in text["rows"] or e is None or e <= 0:
            continue
        z = abs(text["rows"][path][0] - v) / e
        kind = re.sub(r"\.\d+", ".*", re.sub(r"^hist\.\d+\.", "", path))
        if z > worst.get(kind, (0.0, ""))[0]:
            worst[kind] = (z, path)
    common = sum(1 for p in design["rows"] if p in text["rows"])
    print(f"  rows in both {common}; design-only {len(set(design['rows']) - set(text['rows']))}, "
          f"text-only {len(set(text['rows']) - set(design['rows']))}; {len(worst)} kinds, the worst six:")
    for kind, (z, path) in sorted(worst.items(), key=lambda x: -x[1][0])[:6]:
        print(f"  worst |text - design|/esd among {kind:10} {z:.2e} at {path}")
    coef = {}
    for eq, term, v, e in design["coefficients"]:
        coef.setdefault(eq, []).append((term, v, e))
    zc = []
    for k in edges():
        (t0, v0, e0), (t1, v1, e1) = coef[k]
        for name, v, e in ((f"zero_{k}", v0, e0), (f"grad_{k}", v1, e1)):
            got, got_e, _ = text["rows"][f"vars.{name}"]
            zc.append((abs(got - v) / e, name, v, e, got, got_e))
    z, name, v, e, got, got_e = max(zc)
    print(f"  worst coefficient: {name} design {v:.9g} ± {e:.3g}, text {got:.9g} ± {got_e:.3g}, "
          f"{z:.2e} esd; esd ratio text/design {got_e / e:.6f}")
    ratios = [r[5] / r[3] for r in zc]
    print(f"  coefficient esd ratio text/design over all 18: {min(ratios):.6f} to {max(ratios):.6f}")
    allz = max([z for z, _ in worst.values()] + [r[0] for r in zc])
    print(f"  Δχ² text - design {text['chi2'] - design['chi2']:+.4f}; Rwp {100 * design['rwp']:.4f} % "
          f"and {100 * text['rwp']:.4f} %")
    print(f"  GATE (every reported parameter within 0.01 esd): worst {allz:.2e} esd: "
          f"{'PASS' if allz < 0.01 else 'FAIL'}")


def gaps(fits: dict[str, dict], temps: np.ndarray, proto: dict) -> None:
    p06 = topas06()
    print("  ppm = 1e6 · max over the 100 temperatures of |x - TOPAS 05| / TOPAS 05")
    head = "  " + f"{'':8}" + "".join(f"{lab:>14}" for lab in [*fits, "TOPAS 06"])
    print(head)
    for key, path in targets().items():
        i, name = int(path.split(".")[1]), path.rsplit(".", 1)[1]
        ref = np.array([topas_equation(proto, i, name, float(t)) for t in temps])
        cells = [1e6 * np.max(np.abs(np.array(f["curves"][key]) - ref) / ref) for f in fits.values()]
        other = np.array([topas_equation(p06, i, name, float(t)) for t in temps])
        cells.append(1e6 * np.max(np.abs(other - ref) / ref))
        print(f"  {key:8}" + "".join(f"{c:14.0f}" for c in cells))


def report(subset: str) -> None:
    data = load(0, 99)
    proto, temps = data["proto"], data["temps"]
    theta0 = proto["theta"]
    print("WP-1964 task 13: the WO3 ramp's Einstein equations as formula text (Durham TOPAS 9.3/9.4)")
    print(f"rietx     {rx.__version__}; subset {subset}: {len(SUBSETS[subset])} patterns {SUBSETS[subset]}")
    print("protocol  WP-1325's: B held at the chain's, coordinates at TOPAS's, strains per pattern; "
          "angles quadratic in T")
    print("          the input's one B per pattern tied across atoms needs WP-2103 (not landed): not built")
    print("text      " + text_equations()[0].expression + "  (one per edge; theta shared by all nine)")
    print()
    found = {}
    for path in sorted(SCRATCH.glob(f"wo3_formula_{subset}_*.json")):
        f = json.loads(path.read_text(encoding="utf-8"))
        found[(f["arm"], round(f["theta"], 4))] = f
    for (arm, th), f in sorted(found.items()):
        print(f"fit {arm:6} θ {th:9.4f}: {f['seconds']:7.1f} s (load {f['load'][0]:.1f}); {f['status']}; "
              f"iters {f['iters']}; Rwp {100 * f['rwp']:.3f} %; χ² {f['chi2']:.1f} with {f['n_free']} free; "
              f"χ²r {f['chi2r']:.4f}; diagnostics {f['diagnostics']}")
    print()
    design, text = found.get(("design", round(theta0, 4))), found.get(("text", round(theta0, 4)))
    print(f"GATE: text against design, θ held at {theta0:.6f} K")
    if design and text:
        gate(design, text)
    else:
        print("  not run")
    print()
    free = next((f for (a, _), f in found.items() if a == "free"), None)
    print("θ FREE")
    if free:
        v, e, at = free["rows"]["vars.theta"]
        near = min(v - THETA_MIN, THETA_MAX - v)
        print(f"  θ {v:.3f} ± {e:.3f} K (bounds [{THETA_MIN:g}, {THETA_MAX:g}] K, {near:.3g} K from the "
              f"nearer); at_bound {at}; TOPAS 05 {theta0:.3f} K, TOPAS 06 {topas06()['theta']:.3f} K")
        print(f"  Rwp {100 * free['rwp']:.3f} %; χ² {free['chi2']:.1f}, "
              f"{free['chi2'] - text['chi2'] if text else float('nan'):+.1f} against θ held at TOPAS 05's")
    else:
        print("  not run")
    print()
    print("PROFILE: θ pinned, everything else refitted (χ² of the whole joint fit)")
    prof = sorted((th, f) for (a, th), f in found.items() if a in ("pin", "text"))
    if free:
        prof = sorted([*prof, (free["rows"]["vars.theta"][0], free)])
    lo = min(f["chi2"] for _, f in prof) if prof else 0.0
    for th, f in prof:
        print(f"  θ {th:9.3f} K  χ² {f['chi2']:12.1f}  Δχ² {f['chi2'] - lo:8.1f}  ({f['arm']})")
    print()
    print("GAP TO TOPAS per cell parameter (no gate)")
    fits = {}
    if text:
        fits["text θ held"] = text
    if free:
        fits["text θ free"] = free
    gaps(fits, temps, proto)


def main() -> None:
    args = parse_args(sys.argv[1:], {"arm": "report", "subset": "topas11", "theta": 0.0})
    load_theta = load(0, 0)["proto"]["theta"]
    theta = args["theta"] or load_theta
    if args["arm"] == "report":
        report(args["subset"])
    elif args["arm"] in ("design", "text", "free", "pin"):
        run(args["arm"], args["subset"], theta)
    else:
        raise SystemExit(f"unknown arm {args['arm']!r}")


if __name__ == "__main__":
    main()

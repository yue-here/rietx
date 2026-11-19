"""Task 9: Wald (2-esd) coverage over seeds on two synthetic ramps.

usage (from the repo root): python docs/wp/1964-measure/coverage.py CASE SEED0 NSEEDS   (CASE: order | order_low | avrami)
one JSON line per seed on stdout.
"""
import json
import sys
import time

sys.path.insert(0, ".")
import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.multi import refine_multi  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.schemas.parametric import CoordinateTable, ParametricEquation  # noqa: E402
from tests.test_sequential import A0, TRUE_SCALE, _simulate, _start_models  # noqa: E402

CASES = {
    "order": dict(
        target="phases.0.cell.a", unit="K",
        expression="a0 + k*(T - 300) + A*if(T < Tc, (1 - T/Tc)^(2*beta), 0)",
        truth={"a0": A0, "k": A0 * 5e-6, "A": 0.004, "Tc": 830.0, "beta": 0.3},
        start={"a0": (A0 * 1.0005, None, None), "k": (A0 * 4e-6, None, None),
               "A": (0.003, 0.0, 0.05), "Tc": (870.0, 500.0, 1100.0),
               "beta": (0.35, 0.05, 1.0)},
        coords=[300.0 + 70.0 * i for i in range(12)]),
    "avrami": dict(
        target="phases.0.scale", unit="s",
        expression="S*(1 - exp(-(kr*t)^n))",
        truth={"S": TRUE_SCALE, "kr": 1.0 / 600.0, "n": 2.0},
        start={"S": (TRUE_SCALE * 1.2, 0.0, None), "kr": (1.0 / 500.0, 1e-5, 1.0),
               "n": (1.6, 0.5, 4.0)},
        coords=[200.0 + 100.0 * i for i in range(12)]),
}


def truth_value(case, c):
    v = dict(case["truth"])
    if "T" in case["expression"].replace("Tc", ""):
        T = c
        a = v["a0"] + v["k"] * (T - 300) + (v["A"] * (1 - T / v["Tc"]) ** (2 * v["beta"])
                                            if T < v["Tc"] else 0.0)
        return a
    return v["S"] * (1 - np.exp(-(v["kr"] * c) ** v["n"]))


def run(name, seed):
    case = CASES[name]
    coord = "t" if name == "avrami" else "T"
    cs = case["coords"]
    if name.startswith("order"):
        patterns = [_simulate(truth_value(case, c), seed=1000 * seed + k)
                    for k, c in enumerate(cs)]
    else:
        patterns = [_simulate(A0, scale=truth_value(case, c), seed=1000 * seed + k)
                    for k, c in enumerate(cs)]
    structure, ins = _start_models()
    # the clean protocol: Biso at the simulation's 0.4, so the model is exact
    for atom in structure.phases[0].atoms:
        atom.biso.value = 0.4
    if name == "avrami":
        for nm in "abc":
            getattr(structure.phases[0].cell, nm).value = A0
    variables = {k: rx.Parameter(value=v, vary=True,
                                 **({} if lo is None else {"min": lo}),
                                 **({} if hi is None else {"max": hi}))
                 for k, (v, lo, hi) in case["start"].items()}
    t0 = time.perf_counter()
    result = refine_multi(
        patterns, structure, [ins] * len(cs), plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={coord: cs}, units={coord: case["unit"]}),
        variables=variables,
        parametric=[ParametricEquation(name="eq", target=case["target"], basis="expression",
                                       expression=case["expression"])])
    wall = time.perf_counter() - t0
    rows = {p.path: p for p in result.parameters}
    out = {"case": name, "seed": seed, "status": result.status, "wall": round(wall, 2),
           # the Bérar-Lelann factor every esd carries
           "f2": result.statistics.esd_inflation}
    for k, truth in case["truth"].items():
        r = rows.get(f"vars.{k}")
        if r is None or r.stderr is None:
            out[k] = None
            continue
        out[k] = [r.value, r.stderr, (r.value - truth) / r.stderr]
    form = result.parametric_form[0] if result.parametric_form else None
    out["form"] = None if form is None else form.rejected
    if seed == 0:
        from pathlib import Path

        from rietx.viz.plots import plot_result
        Path("tests/output").mkdir(exist_ok=True)
        for h in (0, len(cs) - 1):
            plot_result(result.for_histogram(h),
                        path=f"tests/output/wp1964_t9_{name}_h{h}_fit.png")
    return out


CASES["order_low"] = dict(CASES["order"], start=dict(CASES["order"]["start"],
                                                     Tc=(760.0, 500.0, 1100.0)))


if __name__ == "__main__":
    name, s0, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    for seed in range(s0, s0 + n):
        try:
            print(json.dumps(run(name, seed)), flush=True)
        except Exception as exc:  # a probe: record and go on
            print(json.dumps({"case": name, "seed": seed, "error": repr(exc)}), flush=True)

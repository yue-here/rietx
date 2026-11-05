"""Task 9: a profile interval on the order ramp, by hand, against the Wald one.

usage (from the repo root): python docs/wp/1964-measure/profile.py SEED VAR    (VAR: Tc | beta)
Pins vars.VAR at value ± m·esd (m = 1, 2, 3 each side), refits everything
else, and reads Δχ² against 4·χ²_red·f² (2 esd on a quadratic profile).
Prints one JSON line.

A χ² read across separate fits carries an offset: here the free fit sat
about 0.19 of the cut above the pinned fits' curve at every step.  Not
measured why; one candidate is that each fit freezes its own peak windows.  Read the profile's shape from
differences between pinned fits, Δ(3) − Δ(1) = 2 and Δ(2) − Δ(1) = 0.75 on a
quadratic profile.
"""
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "docs/wp/1964-measure")
import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.multi import refine_multi  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.schemas.parametric import CoordinateTable, ParametricEquation  # noqa: E402
from coverage import CASES, truth_value  # noqa: E402
from tests.test_sequential import _simulate, _start_models  # noqa: E402

seed, var = int(sys.argv[1]), sys.argv[2]
case = CASES["order"]
cs = case["coords"]
patterns = [_simulate(truth_value(case, c), seed=1000 * seed + k) for k, c in enumerate(cs)]


def fit(pin=None):
    structure, ins = _start_models()
    for atom in structure.phases[0].atoms:
        atom.biso.value = 0.4
    variables = {}
    for k, (v, lo, hi) in case["start"].items():
        kw = {} if lo is None else {"min": lo}
        kw.update({} if hi is None else {"max": hi})
        if pin is not None and k == var:
            variables[k] = rx.Parameter(value=pin, vary=False, **kw)
        else:
            variables[k] = rx.Parameter(value=v, vary=True, **kw)
    return refine_multi(
        patterns, structure, [ins] * len(cs), plan="mccusker_default",
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": cs}, units={"T": "K"}),
        variables=variables,
        parametric=[ParametricEquation(name="eq", target=case["target"], basis="expression",
                                       expression=case["expression"])])


best = fit()
row = {p.path: p for p in best.parameters}[f"vars.{var}"]
st = best.statistics
f = st.esd_inflation or 1.0
red = st.chi2 / max(st.n_points - st.n_free_parameters, 1)
cut = 4.0 * red * f * f
steps = [-3, -2, -1, 1, 2, 3]
d = []
for m in steps:
    r = fit(row.value + m * row.stderr)
    d.append((r.statistics.chi2 - st.chi2) / cut)
# a quadratic profile reads Δχ²/cut = m²/4: the ratio says how far it departs
ratio = [di / (m * m / 4.0) for di, m in zip(d, steps)]
print(json.dumps({"seed": seed, "var": var, "value": row.value, "esd": row.stderr,
                  "truth": case["truth"][var], "f": f,
                  "dchi2_over_cut": [round(x, 4) for x in d],
                  "ratio_to_quadratic": [round(x, 4) for x in ratio]}), flush=True)
_ = np

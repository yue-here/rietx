"""WP-2106 task 3: an equation fitted to a series trajectory against the joint fit.

    .venv/bin/python docs/wp/2106-measure/trajectory_vs_joint.py > docs/wp/2106-measure/trajectory_vs_joint_results.txt

Run from the repository root.  The data is the guides' synthetic LaB6 ramp
(``examples/guides/_lab6_ramp.py``): seven patterns, 300-900 K, a cell edge
growing by 0.05 % per 100 K, Poisson noise.  Twenty noise seeds, pattern k of
seed s drawn with ``seed = s + k``; s = 11 is the guides' own ramp.

Each seed is fitted three ways, from the guides' starting model and plan:

* a chain, ``refine_sequential(direction="both")``, then
  ``fit_trajectory`` of a0 + k·(T − 600) to each chain's cell-edge trajectory;
* ``refine_multi`` with the same equation as a ``ParametricEquation`` of basis
  ``expression``, so the coefficients are the same two numbers.

Nothing is shared across patterns in either but the coefficients.  The report
gives, per coefficient and chain: the largest gap to the joint value in combined
esds, and the ratio of the trajectory fit's esds (scaled and unscaled) to the
joint fit's.
"""

import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "examples" / "guides"))

from _lab6_ramp import TEMPERATURES, TRUE_A, simulate, starting_model  # noqa: E402

import rietx as rx  # noqa: E402

SEEDS = [11 + 100 * i for i in range(20)]
EXPRESSION = "a0 + k*(T - 600)"
PATH = "phases.0.cell.a"


def _start():
    return {"a0": rx.Parameter(value=4.163, vary=True), "k": rx.Parameter(value=0.0, vary=True)}


def one_seed(base: int, coords: rx.CoordinateTable) -> dict:
    patterns = [simulate(a, seed=base + k) for k, a in enumerate(TRUE_A)]
    structure, instrument = starting_model()
    series = rx.refine_sequential(patterns, structure, instrument, plan="mccusker_default",
                                  x=TEMPERATURES, x_label="T (K)", direction="both")
    equation = rx.ParametricEquation(name="a", target=PATH, basis="expression",
                                     expression=EXPRESSION)
    joint = rx.refine_multi(patterns, starting_model()[0],
                            [starting_model()[1] for _ in patterns],
                            plan="mccusker_default", coordinates=coords,
                            parametric=[equation], variables=_start())
    rows = {p.path: p for p in joint.parameters}
    row = {"seed": base,
           "joint": {n: (rows[f"vars.{n}"].value, rows[f"vars.{n}"].stderr) for n in ("a0", "k")}}
    for chain in ("forward", "backward"):
        fit = rx.fit_trajectory(series, PATH, EXPRESSION, _start(), coordinates=coords,
                                chain=chain)
        row[chain] = {v.name: (v.value, v.esd, v.esd_unscaled) for v in fit.variables}
        row[f"{chain}_reduced_chi2"] = fit.reduced_chi2
        row[f"{chain}_skipped"] = len(fit.skipped)
    return row


def main() -> None:
    coords = rx.CoordinateTable(columns={"T": [float(t) for t in TEMPERATURES]},
                                units={"T": "K"})
    rows = [one_seed(s, coords) for s in SEEDS]
    for row in rows:
        print(json.dumps(row))
    truth = {"a0": TRUE_A[3], "k": TRUE_A[0] * 5e-4 / 100}
    print(f"# {len(rows)} seeds; truth a0 = {truth['a0']:.7f} Å at 600 K, "
          f"k = {truth['k']:.4e} Å/K")
    for chain in ("forward", "backward"):
        for n in ("a0", "k"):
            gap = [abs(r[chain][n][0] - r["joint"][n][0]) / math.hypot(r[chain][n][1],
                                                                       r["joint"][n][1])
                   for r in rows]
            scaled = [r[chain][n][1] / r["joint"][n][1] for r in rows]
            raw = [r[chain][n][2] / r["joint"][n][1] for r in rows]
            print(f"# {chain} {n}: largest gap to the joint value {max(gap):.3f} combined esd; "
                  f"esd / joint esd: scaled median {statistics.median(scaled):.3f} "
                  f"({min(scaled):.3f}-{max(scaled):.3f}), unscaled median "
                  f"{statistics.median(raw):.4f} ({min(raw):.4f}-{max(raw):.4f})")
    chi = [r["forward_reduced_chi2"] for r in rows]
    print(f"# forward trajectory chi2/nu (5 dof): median {statistics.median(chi):.2f} "
          f"({min(chi):.2f}-{max(chi):.2f}); points left out: "
          f"{sum(r['forward_skipped'] + r['backward_skipped'] for r in rows)}")
    for who, idx in (("joint", 1), ("forward", 1), ("forward", 2)):
        label = who if who == "joint" else f"trajectory, {'scaled' if idx == 1 else 'unscaled'} esd"
        for n in ("a0", "k"):
            z = [(r[who][n][0] - truth[n]) / r[who][n][idx] for r in rows]
            print(f"# {label} {n}: (value - truth)/esd rms {math.sqrt(sum(x * x for x in z) / len(z)):.2f}")


if __name__ == "__main__":
    main()

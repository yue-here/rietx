"""WP-1964 task 13: the ZrP2O7 input's cell equations written as formula text.

    .venv/bin/python docs/wp/1964-measure/zrp2o7_formula.py \
        > docs/wp/1964-measure/zrp2o7_formula_results.txt

Run from the repository root.
The data is Durham TOPAS tutorial 9.5 (Stinton & Evans, 2007, *J. Appl. Cryst.* 40, 87).
It is local only, from ``python -m tests.local_data durham-topas/zrp2o7``.
The model, the protocol and the chain are WP-1325's ``zrp2o7_model.py``, imported unchanged.

The input computes three cell edges from the temperature.
The silicon edge is three Einstein terms on a log scale.
The two Al2O3 edges are Taylor's quadratics in (T - 273 K).
A cubic temperature calibration in u = (T_set - 738)/369 feeds all three.
Its constant term is fixed by delta_T(303 K) = 0, and the input holds b, c and d at 0.
This script writes each of those as rietx formula text.
The calibration is one intermediate equation, ``T_true``, which the three cell formulas name.
Every coefficient is read from the input at run time.

What it measures, in order.

(a) A preview with no fit, at the input's own coefficients.
    Each previewed cell is compared with the cell the input prints at each of the 37 patterns.
    The bar is 1e-6 Å.
    The input prints six decimals, so its own coefficients agree with it to about 6.6e-7 Å.
(b) A second preview with the calibration coefficients set nonzero.
    Each previewed cell is compared with a numpy evaluation of the input's own arithmetic.
    The bar is 1e-6 Å at every cell.
(c) A synthetic recovery of known calibration coefficients.
    ``tests/test_parametric_expression.py::test_a_temperature_calibration_feeding_the_cell_recovers_its_coefficients``
    covers it, so this script only cites it.
(d) A joint fit on the real data that frees b, c and d and reports them with esds and Rwp.
    There is no gate, since TOPAS stores no answer for them.
    The fit is seeded from WP-1325's chain, under ``SharingMap(per_histogram=["phases.*"])``.
    The ZrP2O7 edge stays one value per pattern, as the input refines it.

What (d) leaves out, because rietx cannot yet express it.
TOPAS refines a 2θ calibration curve quadratic in (2θ - 54°), shared by all patterns.
The input's refined curve is 0.0105° at 15°, zero at 54° and 0.0059° at 90°.
TOPAS also refines one TCHZ profile per phase shared by all patterns.
Here each phase's four broadening terms refine per pattern instead, as in WP-1325.
Both join the protocol once WP-2107 lands.
The omitted curve is the same in every pattern, so it shifts every silicon edge alike.
The specimen displacement refines per pattern and absorbs part of it.
How far the rest moves the calibration is not measured here, so (d) is not compared with TOPAS.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE.parent / "1325-measure"))

import numpy as np  # noqa: E402
from zrp2o7_model import (  # noqa: E402
    INP,
    instrument,
    load,
    plan,
    run_chain,
    structure,
    total_chi2,
)

import rietx as rx  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.viz.plots import plot_result  # noqa: E402

OUT = REPO / "tests" / "output"
SI, AL_A, AL_C = "phases.1.cell.a", "phases.2.cell.a", "phases.2.cell.c"
BAR = 1e-6
#: nonzero calibration coefficients for gate (b), in K; arbitrary, of the size a furnace offset has
TRIAL = {"cal_b": 6.0, "cal_c": -4.0, "cal_d": 2.5}

SI_NAMES = ("a0", "const1", "theta1", "const2", "theta2", "const3", "theta3")
AL_NAMES = ("a0_al2o3", "ax1_al2o3", "ax2_al2o3", "a_al2o3_offset",
            "c0_al2o3", "cx1_al2o3", "cx2_al2o3", "c_al2o3_offset")
CAL_NAMES = ("t_middle", "tra2", "T_calibration_b", "T_calibration_c", "T_calibration_d")


def coefficients(text: str) -> dict[str, float]:
    out = {}
    for name in SI_NAMES + AL_NAMES + CAL_NAMES:
        m = re.search(rf"^\s*prm\s+!?{name}\s+(-?[\d.]+(?:[eE][-+]?\d+)?)", text, re.M)
        if m is None:
            raise SystemExit(f"{INP}: no prm {name}")
        out[name] = float(m.group(1))
    return out


def stored_cells(text: str, temps: list[float]) -> dict[str, np.ndarray]:
    """The cells the input prints after each ``Cubic(=…;:v)`` and ``Trigonal(…)``, six decimals."""
    out = {SI: [], AL_A: [], AL_C: []}
    for t in temps:
        tag = f"t_{int(t):04d}"
        si = re.search(rf"Cubic\(=lpa_si_{tag};:([\d.]+)\)", text)
        al = re.search(rf"Trigonal\(=lpa_al2o3_{tag};:([\d.]+),=lpc_al2o3_{tag};:([\d.]+)\)", text)
        out[SI].append(float(si.group(1)))
        out[AL_A].append(float(al.group(1)))
        out[AL_C].append(float(al.group(2)))
    return {k: np.array(v) for k, v in out.items()}


def hand(c: dict[str, float], temps: np.ndarray, cal: dict[str, float]) -> dict[str, np.ndarray]:
    """The input's own arithmetic in numpy, independent of rietx's expression code."""
    tm, tr = c["t_middle"], c["tra2"]
    b, cc, d = cal["cal_b"], cal["cal_c"], cal["cal_d"]
    u0 = (303 - tm) / tr
    a_cal = 0 - (b * u0 + cc * u0 ** 2 + d * u0 ** 3)
    u = (temps - tm) / tr
    t = temps + a_cal + b * u + cc * u ** 2 + d * u ** 3
    log_si = np.log(c["a0"])
    for j in (1, 2, 3):
        th = c[f"theta{j}"]
        log_si = log_si + (c[f"const{j}"] / 1e6) * th / (np.exp(th / t) - 1)
    x = t - 273
    return {SI: np.exp(log_si),
            AL_A: c["a_al2o3_offset"] + c["a0_al2o3"] * (1 + c["ax1_al2o3"] * x + c["ax2_al2o3"] * x ** 2),
            AL_C: c["c_al2o3_offset"] + c["c0_al2o3"] * (1 + c["cx1_al2o3"] * x + c["cx2_al2o3"] * x ** 2)}


def equations(c: dict[str, float]) -> list[rx.ParametricEquation]:
    """The input's lines as rietx text; t_middle and tra2 are written in as numbers."""
    u = f"((T - {c['t_middle']:g})/{c['tra2']:g})"
    u0 = f"((303 - {c['t_middle']:g})/{c['tra2']:g})"
    calibration = (f"T + cal_b*({u} - {u0}) + cal_c*({u}^2 - {u0}^2) + cal_d*({u}^3 - {u0}^3)")
    silicon = ("exp(log(a0) + (const1/1000000)*theta1/(exp(theta1/T_true) - 1)"
               " + (const2/1000000)*theta2/(exp(theta2/T_true) - 1)"
               " + (const3/1000000)*theta3/(exp(theta3/T_true) - 1))")
    al_a = "a_al2o3_offset + a0_al2o3*(1 + ax1_al2o3*(T_true - 273) + ax2_al2o3*(T_true - 273)^2)"
    al_c = "c_al2o3_offset + c0_al2o3*(1 + cx1_al2o3*(T_true - 273) + cx2_al2o3*(T_true - 273)^2)"
    return [rx.ParametricEquation(name="T_true", basis="expression", expression=calibration),
            rx.ParametricEquation(name="si_a", target=SI, basis="expression", expression=silicon),
            rx.ParametricEquation(name="al_a", target=AL_A, basis="expression", expression=al_a),
            rx.ParametricEquation(name="al_c", target=AL_C, basis="expression", expression=al_c)]


def variables(c: dict[str, float], cal: dict[str, float], free: bool) -> dict[str, rx.Parameter]:
    out = {n: rx.Parameter(value=c[n], vary=False) for n in SI_NAMES + AL_NAMES}
    for n, v in cal.items():
        out[n] = rx.Parameter(value=v, vary=free, min=-200.0, max=200.0)
    return out


def preview(proto, temps, c, cal) -> dict[str, np.ndarray]:
    fit = rx.MultiHistogramRefinement(
        structure(proto), [instrument(proto) for _ in temps],
        sharing=SharingMap(per_histogram=["phases.*"]),
        coordinates=rx.CoordinateTable(columns={"T": list(temps)}, units={"T": "K"}),
        parametric=equations(c), variables=variables(c, cal, free=False))
    rows = fit.preview_equations()
    out = {}
    for r in rows:
        if r.nonfinite:
            raise SystemExit(f"{r.name}: non-finite at patterns {r.nonfinite}")
        assert r.patterns == list(range(len(temps))), r.patterns
        out[r.target] = np.array(r.values)
    return out


def worst(a: dict, b: dict) -> tuple[float, str, int]:
    best = (-1.0, "", -1)
    for key in (SI, AL_A, AL_C):
        d = np.abs(a[key] - b[key])
        k = int(np.argmax(d))
        if d[k] > best[0]:
            best = (float(d[k]), key, k)
    return best


def main() -> None:
    from tests.local_data import dataset

    text = (dataset("durham-topas/zrp2o7") / INP).read_text(encoding="utf-8", errors="replace")
    c = coefficients(text)
    print("WP-1964 task 13: the ZrP2O7 input's cell equations as formula text "
          "(Durham TOPAS tutorial 9.5)")
    print(f"rietx     {rx.__version__}; load {' '.join(f'{x:.1f}' for x in os.getloadavg())}")
    print("coefficients read from the input: " + ", ".join(f"{k} {v:g}" for k, v in c.items()))
    for e in equations(c):
        print(f"  {e.name:6} {e.target or '(intermediate)':16} {e.expression}")
    print()

    t0 = time.perf_counter()
    data = load()
    proto, temps = data["proto"], data["temps"]
    stored = stored_cells(text, list(temps))
    zero = {n: 0.0 for n in TRIAL}
    if any(c[f"T_calibration_{n[-1]}"] != 0.0 for n in TRIAL):
        raise SystemExit("the input's calibration coefficients are not all 0; gate (a)'s premise moved")

    print(f"(a) preview at the input's coefficients, against the cells it prints ({len(temps)} patterns)")
    got = preview(proto, temps, c, zero)
    own = hand(c, temps, zero)
    d_pre, key, k = worst(got, stored)
    d_own = worst(own, stored)[0]
    d_hand = worst(got, hand(c, temps, zero))[0]
    for target in (SI, AL_A, AL_C):
        print(f"    {target:16} max |preview - printed| {np.max(np.abs(got[target] - stored[target])):.2e} Å; "
              f"max |input's arithmetic - printed| {np.max(np.abs(own[target] - stored[target])):.2e} Å")
    print(f"    worst {d_pre:.2e} Å at {key}, {temps[k]:.0f} K; bar {BAR:g} Å: "
          f"{'PASS' if d_pre < BAR else 'FAIL'}")
    print(f"    the input's own arithmetic reaches {d_own:.2e} Å, the printed digits; "
          f"preview against that arithmetic {d_hand:.1e} Å")
    print()

    print(f"(b) preview with the calibration set nonzero ({TRIAL}), against numpy of the input's arithmetic")
    got_b = preview(proto, temps, c, TRIAL)
    want_b = hand(c, temps, TRIAL)
    d_b, key_b, k_b = worst(got_b, want_b)
    moved = worst(got_b, got)[0]
    print(f"    the calibration moves the cells by up to {moved:.2e} Å, so the feed reaches")
    for target in (SI, AL_A, AL_C):
        print(f"    {target:16} max |preview - hand| {np.max(np.abs(got_b[target] - want_b[target])):.2e} Å")
    print(f"    worst {d_b:.2e} Å at {key_b}, {temps[k_b]:.0f} K; bar {BAR:g} Å: "
          f"{'PASS' if d_b < BAR else 'FAIL'}")
    print()

    print("(c) synthetic recovery: tests/test_parametric_expression.py::"
          "test_a_temperature_calibration_feeding_the_cell_recovers_its_coefficients")
    print()

    print("(d) the real data, calibration b, c and d freed (no gate)")
    chain = run_chain(data)
    print(f"    chain {chain['seconds']:.1f} s; status {sorted(set(chain['status']))}; "
          f"Σχ² {chain['chi2']:.1f}, Rwp {100 * min(chain['rwp']):.2f}-{100 * max(chain['rwp']):.2f} %")
    series = chain["series"]
    coords = rx.CoordinateTable(columns={"T": temps.tolist()}, units={"T": "K"})
    fits = {}
    for label, eqs in (("untied", None), ("formula", equations(c))):
        t1 = time.perf_counter()
        fit = rx.MultiHistogramRefinement(
            list(series.fitted_structures), list(series.fitted_instruments),
            sharing=SharingMap(per_histogram=["phases.*"]), coordinates=coords,
            parametric=eqs, variables=variables(c, zero, free=True) if eqs else None)
        result = fit.fit(data["patterns"], plan=plan(), two_theta_limits=proto["limits"])
        s = result.statistics
        fits[label] = result
        print(f"    {label:8} {time.perf_counter() - t1:6.1f} s; status {result.status}; "
              f"Rwp {100 * s.rwp:.3f} % (TOPAS 31.56 %); χ² {total_chi2(s):.1f} with "
              f"{s.n_free_parameters} free; χ²r {s.chi2:.4f}")
    result = fits["formula"]
    rows = {p.path: p for p in result.parameters}
    cal = {}
    for n in TRIAL:
        r = rows.get(f"vars.{n}")
        cal[n] = r.value
        bound = " AT BOUND" if getattr(r, "at_bound", None) else ""
        print(f"    vars.{n:6} {r.value:+9.3f} ± {r.stderr:.3f} K{bound}")
    tm, tr = c["t_middle"], c["tra2"]
    for t in (303.0, 600.0, 900.0, 1173.0):
        dt = hand_delta(t, tm, tr, cal)
        print(f"    delta_T at {t:.0f} K: {dt:+.2f} K")
    print("    the formula fit's silicon edge against the chain's free edge, per pattern:")
    v, e = chain["traj"]["si_a"]
    si = np.array([rows[f"hist.{h}.{SI}"].value for h in range(len(temps))])
    z = (si - v) / e
    print(f"      (formula - chain)/chain esd: median {np.median(z):+.2f}, range {z.min():+.2f} to "
          f"{z.max():+.2f}; in Å {1e4 * np.min(si - v):+.2f}e-4 to {1e4 * np.max(si - v):+.2f}e-4")
    codes = sorted({d.code for d in result.diagnostics})
    print(f"    diagnostics {codes}")
    dchi = total_chi2(result.statistics) - total_chi2(fits["untied"].statistics)
    dfree = fits["untied"].statistics.n_free_parameters - result.statistics.n_free_parameters
    print(f"    the formulas cost Δχ² {dchi:.1f} for {dfree} fewer free parameters against the untied fit")
    OUT.mkdir(exist_ok=True)
    for h in (0, int(np.argmax(temps)), len(temps) - 1):
        plot_result(result.for_histogram(h), path=str(OUT / f"wp1964_zrp2o7_formula_h{h}_fit.png"))
    print(f"    plots: tests/output/wp1964_zrp2o7_formula_h*_fit.png (patterns 0, {int(np.argmax(temps))}, "
          f"{len(temps) - 1})")
    print()
    print(f"total {time.perf_counter() - t0:.0f} s; load at end {' '.join(f'{x:.1f}' for x in os.getloadavg())}")


def hand_delta(t: float, tm: float, tr: float, cal: dict[str, float]) -> float:
    u, u0 = (t - tm) / tr, (303 - tm) / tr
    return (cal["cal_b"] * (u - u0) + cal["cal_c"] * (u ** 2 - u0 ** 2)
            + cal["cal_d"] * (u ** 3 - u0 ** 3))


if __name__ == "__main__":
    main()

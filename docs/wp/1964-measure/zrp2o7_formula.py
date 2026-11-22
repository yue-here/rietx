"""WP-1964 task 13 and WP-2151: the ZrP2O7 input's equations written as rietx text.

    .venv/bin/python docs/wp/1964-measure/zrp2o7_formula.py \
        > docs/wp/1964-measure/zrp2o7_formula_results.txt
    .venv/bin/python docs/wp/1964-measure/zrp2o7_formula.py e   # arm (e) alone

Run from the repository root.
An argument names the arms to run, as letters; the default is all of them.
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

What (d) leaves out.
TOPAS refines a 2θ calibration curve quadratic in (2θ - 54°), shared by all patterns.
The input's refined curve is 0.0105° at 15°, zero at 54° and 0.0059° at 90°.
TOPAS also refines one TCHZ profile per phase shared by all patterns.
In (d) each phase's four broadening terms refine per pattern instead, as in WP-1325.
The omitted curve is the same in every pattern, so it shifts every silicon edge alike.
The specimen displacement refines per pattern and absorbs part of it.

(e) WP-2151: the fit of (d) with both put back as peak equations (WP-2107).
    The curve is one ``shift`` equation on the instrument, written in ``two_theta``.
    Each phase's TCHZ is a ``gauss_fwhm_squared`` equation, u·tan²θ + v·tanθ + w + z/cos²θ,
    and a ``lor_fwhm`` equation, x·tanθ + y/cosθ, read by argument position (WP-1455).
    Every coefficient is seeded from the input and shared by the 37 patterns, as the input shares it.
    The instrument's U, V, X and Y are held at 0 and W at its floor, since the equations
    duplicate them, and so are each phase's four built-in broadening terms.
    z/cos²θ is z + z·tan²θ, so u, w and z are one exact degeneracy, and the covariance
    solve then gives none of the three an esd.  So the fit runs four times.
    "as written" frees all six terms, as the input does.
    "z held" holds each z at the input's value, which leaves the fitted widths the same
    and gives u and w an esd; its coefficients are the ones reported.
    "closed" is "z held" with the plan closed at ``CLOSING_WINDOW_TOL``, to see whether
    the answer moves when the peaks are cut wider.
    "Si seeded" lifts silicon's w: the input's silicon Γ_G² is below zero across the
    whole range, so its Gaussian coefficients start on the width floor with no gradient.
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
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402
from rietx.strategy.staged import RefinementPlan, Stage  # noqa: E402
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
CURVE_NAMES = ("zero", "step_error", "square", "data_middle")
#: the input's TCHZ_Peak_Type slots by argument position (WP-1455)
TCHZ_SLOTS = ("u", "v", "w", "z", "x", "y")
GAUSS = "u*tan(theta)^2 + v*tan(theta) + w + z/cos(theta)^2"
LOR = "x*tan(theta) + y/cos(theta)"


def coefficients(text: str) -> dict[str, float]:
    out = {}
    for name in SI_NAMES + AL_NAMES + CAL_NAMES + CURVE_NAMES:
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


def main(arms: str) -> None:
    from tests.local_data import dataset

    text = (dataset("durham-topas/zrp2o7") / INP).read_text(encoding="utf-8", errors="replace")
    c = coefficients(text)
    print("WP-1964 task 13 and WP-2151: the ZrP2O7 input's equations as rietx text "
          f"(Durham TOPAS tutorial 9.5); arms {arms}")
    print(f"rietx     {rx.__version__}; load {' '.join(f'{x:.1f}' for x in os.getloadavg())}")
    print("coefficients read from the input: " + ", ".join(f"{k} {v:g}" for k, v in c.items()))
    for e in equations(c):
        print(f"  {e.name:6} {e.target or '(intermediate)':16} {e.expression}")
    print()

    t0 = time.perf_counter()
    data = load()
    if any(c[f"T_calibration_{n[-1]}"] != 0.0 for n in TRIAL):
        raise SystemExit("the input's calibration coefficients are not all 0; gate (a)'s premise moved")
    if set(arms) & set("abc"):
        previews(text, c, data)
    if set(arms) & set("de"):
        chain = run_chain(data)
        print(f"WP-1325's chain, the seed of (d) and (e): {chain['seconds']:.1f} s; status "
              f"{sorted(set(chain['status']))}; Σχ² {chain['chi2']:.1f}, "
              f"Rwp {100 * min(chain['rwp']):.2f}-{100 * max(chain['rwp']):.2f} %")
        print()
        formula = arm_d(data, c, chain) if "d" in arms else None
        if "e" in arms:
            arm_e(data, c, chain, formula)
    print(f"total {time.perf_counter() - t0:.0f} s; load at end {' '.join(f'{x:.1f}' for x in os.getloadavg())}")


def previews(text: str, c: dict[str, float], data: dict) -> None:
    proto, temps = data["proto"], data["temps"]
    stored = stored_cells(text, list(temps))
    zero = {n: 0.0 for n in TRIAL}

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



def arm_d(data: dict, c: dict[str, float], chain: dict):
    proto, temps = data["proto"], data["temps"]
    zero = {n: 0.0 for n in TRIAL}
    print("(d) the real data, calibration b, c and d freed (no gate)")
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
    return result


def tchz_equations(tchz: list[float]) -> list[rx.PeakEquation]:
    """A phase's TCHZ as two peak equations, seeded from the input's slots."""
    v = dict(zip(TCHZ_SLOTS, tchz, strict=True))
    return [rx.PeakEquation(target="gauss_fwhm_squared", expression=GAUSS,
                            coefficients={k: rx.Parameter(value=v[k]) for k in "uvwz"}),
            rx.PeakEquation(target="lor_fwhm", expression=LOR,
                            coefficients={k: rx.Parameter(value=v[k]) for k in "xy"})]


def curve_equation(c: dict[str, float]) -> rx.PeakEquation:
    """The input's ``th2_offset`` with its held zero left out, in ``two_theta`` (degrees)."""
    m = f"(two_theta - {c['data_middle']:g})"
    return rx.PeakEquation(target="shift", expression=f"square*{m}^2/1000 + step_error*{m}/1000",
                           coefficients={k: rx.Parameter(value=c[k]) for k in ("square", "step_error")})


def peak_models(chain: dict, proto: dict, c: dict[str, float],
                seeds: dict[int, list[float]] | None = None) -> tuple[list, list]:
    """The chain's fitted models with the input's TCHZ and curve as peak equations.

    The built-in width terms the equations duplicate are held: each phase's four
    broadening terms and the instrument's U, V, X and Y at 0, and W at its floor.
    ``seeds`` replaces a phase's six stored TCHZ values, keyed by phase index.
    """
    seeds = seeds or {}
    structures, instruments = [], []
    series = chain["series"]
    for s, ins in zip(series.fitted_structures, series.fitted_instruments, strict=True):
        s, ins = s.model_copy(deep=True), ins.model_copy(deep=True)
        for ip, (ph, read) in enumerate(zip(s.phases, proto["phases"], strict=True)):
            for name in ("gauss_size", "gauss_strain", "lor_size", "lor_strain"):
                getattr(ph, name).value = 0.0
            ph.peak_equations = tchz_equations(seeds.get(ip, read["tchz"]))
        for name in "uvxy":
            getattr(ins.profile, name).value = 0.0
        ins.profile.w.value = _MIN_GAMMA_G2
        ins.peak_equations = [curve_equation(c)]
        structures.append(s)
        instruments.append(ins)
    return structures, instruments


def peak_plan(closing: float | None, free_z: bool) -> RefinementPlan:
    """WP-1325's plan with its per-pattern broadening stage replaced by the equations'.

    z/cos²θ is z + z·tan²θ, so with z free the Gaussian's u, w and z are one exact
    degeneracy and only u + z and w + z are measured.  ``free_z=False`` holds z where
    it was seeded, which leaves the fitted width the same and gives u and w an esd.
    """
    gauss = (["phases.*.peak_equations.0.*"] if free_z else
             [f"phases.*.peak_equations.0.{k}" for k in "uvw"])
    stages = []
    for s in plan().stages:
        if s.name == "sample_profile":
            s = Stage(name="peak_equations", turn_on=[
                *gauss, "phases.*.peak_equations.1.*", "instrument.peak_equations.*"])
        stages.append(s)
    return RefinementPlan(stages=stages, closing_window_tol=closing)


#: (d)'s per-pattern phases, with every peak equation's coefficient one value for all 37
PEAK_SHARING = SharingMap(per_histogram=["phases.*.cell.*", "phases.*.atoms.*"],
                          shared=["instrument.peak_equations.*"])


def widths(v: dict[str, float], two_theta: float) -> tuple[float, float]:
    """Γ_G² (deg²) and Γ_L (deg) of one TCHZ at one angle."""
    th = np.radians(two_theta / 2)
    g2 = v["u"] * np.tan(th) ** 2 + v["v"] * np.tan(th) + v["w"] + v["z"] / np.cos(th) ** 2
    return float(g2), float(v["x"] * np.tan(th) + v["y"] / np.cos(th))


def curve_at(square: float, step: float, middle: float, two_theta: float) -> float:
    return (two_theta - middle) ** 2 * square / 1000 + (two_theta - middle) * step / 1000


def arm_e(data: dict, c: dict[str, float], chain: dict, formula) -> None:
    proto, temps = data["proto"], data["temps"]
    if c["zero"] != 0.0:
        raise SystemExit("the input's zero is not 0; the curve equation leaves it out")
    print("(e) WP-2151: (d) plus the 2θ curve and each phase's TCHZ as peak equations (no gate)")
    lo, hi = proto["limits"]
    stored = {f"instrument.peak_equations.0.{k}": c[k] for k in ("square", "step_error")}
    tchz = []
    for ip, ph in enumerate(proto["phases"]):
        v = dict(zip(TCHZ_SLOTS, ph["tchz"], strict=True))
        tchz.append(v)
        stored.update({f"phases.{ip}.peak_equations.0.{k}": v[k] for k in "uvwz"})
        stored.update({f"phases.{ip}.peak_equations.1.{k}": v[k] for k in "xy"})
        g_lo, l_lo = widths(v, lo)
        g_hi, l_hi = widths(v, hi)
        print(f"    stored TCHZ, {ph['name']:8} Γ_G² {g_lo:+.5f} deg² at {lo:g}°, {g_hi:+.5f} at {hi:g}°; "
              f"Γ_L {l_lo:+.5f}° at {lo:g}°, {l_hi:+.5f}° at {hi:g}°")
    print(f"    stored curve {curve_at(c['square'], c['step_error'], c['data_middle'], lo):+.5f}° at {lo:g}°, "
          f"{curve_at(c['square'], c['step_error'], c['data_middle'], hi):+.5f}° at {hi:g}°")
    coords = rx.CoordinateTable(columns={"T": temps.tolist()}, units={"T": "K"})
    zero = {n: 0.0 for n in TRIAL}
    # silicon's stored Γ_G² is below zero over the whole range, so its four Gaussian
    # coefficients start on the floor with no gradient; one variant lifts w until the
    # smallest Γ_G² in the range is 0.002 deg², a Gaussian FWHM of 0.045°
    si = tchz[1]
    deficit = -min(widths(si, t)[0] for t in np.linspace(lo, hi, 301))
    si_seed = [si[k] + (deficit + 0.002 if k == "w" else 0.0) for k in TCHZ_SLOTS]
    print(f"    silicon's seeded variant lifts w from {si['w']:+.5f} to {si_seed[2]:+.5f} deg²")
    fits = {}
    for label, closing, free_z, seeds in (
            ("as written", None, True, None), ("z held", None, False, None),
            ("closed", CLOSING_WINDOW_TOL, False, None), ("Si seeded", None, False, {1: si_seed})):
        structures, instruments = peak_models(chain, proto, c, seeds)
        t1 = time.perf_counter()
        fit = rx.MultiHistogramRefinement(
            structures, instruments, sharing=PEAK_SHARING, coordinates=coords,
            parametric=equations(c), variables=variables(c, zero, free=True))
        result = fit.fit(data["patterns"], plan=peak_plan(closing, free_z),
                         two_theta_limits=proto["limits"])
        s = result.statistics
        fits[label] = result
        beside = f"(d) {100 * formula.statistics.rwp:.3f} %, " if formula is not None else ""
        print(f"    {label:10} {time.perf_counter() - t1:6.1f} s (load {os.getloadavg()[0]:.1f}); "
              f"status {result.status}; Rwp {100 * s.rwp:.3f} % ({beside}TOPAS 31.56 %); "
              f"χ² {total_chi2(s):.1f} with {s.n_free_parameters} free; χ²r {s.chi2:.4f}")
    result = fits["z held"]
    rows = {p.path: p for p in result.parameters}
    crows = {p.path: p for p in fits["closed"].parameters}
    srows = {p.path: p for p in fits["Si seeded"].parameters}
    wrows = {p.path: p for p in fits["as written"].parameters}

    def tchz_of(rr: dict, ip: int) -> dict[str, float]:
        """A fit's six values for one phase; a held row leaves the result, so it is the seed's."""
        seed = dict(zip(TCHZ_SLOTS, si_seed, strict=True)) if rr is srows and ip == 1 else tchz[ip]
        return {k: rr[path].value if (path := f"phases.{ip}.peak_equations.{0 if k in 'uvwz' else 1}.{k}")
                in rr else seed[k] for k in TCHZ_SLOTS}

    print("    the z-held fit: z stays at the input's value, so u and w carry u + z and w + z")
    print("    coefficient                       stored     fit ± esd              (fit-stored)/esd  "
          "(closed-fit)/esd  Si seeded ± esd")
    moves, seeded_moves = {}, {}

    def line(path: str, ref: float | None) -> None:
        r, rc, rs = rows.get(path), crows.get(path), srows.get(path)
        seeded = (f"{rs.value:+10.5f} ± {rs.stderr:.5f}" if rs is not None and rs.stderr is not None
                  else "no esd" if rs is not None else "held")
        if r is None or r.stderr is None:
            value = "held" if r is None else f"no esd, value {r.value:+.5f}"
            print(f"    {path:32} z-held fit: {value}; Si seeded {seeded}")
            return
        bound = " AT BOUND" if getattr(r, "at_bound", None) else ""
        moves[path] = (rc.value - r.value) / r.stderr if rc is not None else float("nan")
        if rs is not None and not path.startswith("phases.1.peak_equations.0."):
            seeded_moves[path] = (rs.value - r.value) / r.stderr
        z = f"{(r.value - ref) / r.stderr:+8.2f}" if ref is not None else "        "
        ref_s = f"{ref:+10.5f}" if ref is not None else " " * 10
        print(f"    {path:32} {ref_s} {r.value:+10.5f} ± {r.stderr:.5f}   {z}          "
              f"{moves[path]:+6.2f}{bound}   {seeded}")

    for path, v0 in stored.items():
        line(path, v0)
    for n in TRIAL:
        line(f"vars.{n}", None)
    if formula is not None:
        frows = {p.path: p for p in formula.parameters}
        print("    calibration in (d), same run: " + ", ".join(
            f"{n} {frows[f'vars.{n}'].value:+.2f} ± {frows[f'vars.{n}'].stderr:.2f} K" for n in TRIAL))
    worst_path = max(moves, key=lambda p: abs(moves[p]))
    print(f"    closing at CLOSING_WINDOW_TOL = {CLOSING_WINDOW_TOL:g}: largest move "
          f"{moves[worst_path]:+.2f} esd at {worst_path}; "
          f"{sum(abs(m) > 0.5 for m in moves.values())} of {len(moves)} rows move more than 0.5 esd")
    for ip in (0, 2):
        held, written = tchz_of(rows, ip), tchz_of(wrows, ip)
        print(f"    {proto['phases'][ip]['name']:8} u + z, w + z: stored "
              f"{tchz[ip]['u'] + tchz[ip]['z']:+.5f}, {tchz[ip]['w'] + tchz[ip]['z']:+.5f}; "
              f"as written {written['u'] + written['z']:+.5f}, {written['w'] + written['z']:+.5f}; "
              f"z held {held['u'] + held['z']:+.5f}, {held['w'] + held['z']:+.5f}")
    fitted = {k: rows[f"instrument.peak_equations.0.{k}"].value for k in ("square", "step_error")}
    print("    fitted curve " + ", ".join(
        f"{curve_at(fitted['square'], fitted['step_error'], c['data_middle'], t):+.5f}° at {t:g}°"
        for t in (lo, 30.0, c["data_middle"], hi)))
    for label, rr in (("z held", rows), ("Si seeded", srows)):
        for ip, ph in enumerate(proto["phases"]):
            v = tchz_of(rr, ip)
            g_lo, l_lo = widths(v, lo)
            g_hi, l_hi = widths(v, hi)
            print(f"    fitted TCHZ ({label}), {ph['name']:8} Γ_G² {g_lo:+.5f} deg² at {lo:g}°, "
                  f"{g_hi:+.5f} at {hi:g}°; Γ_L {l_lo:+.5f}° at {lo:g}°, {l_hi:+.5f}° at {hi:g}°")
    worst_seed = max(seeded_moves, key=lambda p: abs(seeded_moves[p]))
    print(f"    silicon seeded against the z-held fit: largest move of any other row "
          f"{seeded_moves[worst_seed]:+.2f} esd at {worst_seed}; "
          f"{sum(abs(m) > 1.0 for m in seeded_moves.values())} of {len(seeded_moves)} move more than 1 esd")
    for label, r in fits.items():
        counts: dict[str, int] = {}
        for d in r.diagnostics:
            counts[d.code] = counts.get(d.code, 0) + 1
        print(f"    diagnostics, {label}: " + ", ".join(f"{k} ×{v}" for k, v in sorted(counts.items())))
        for d in r.diagnostics:
            if d.code in ("PEAK_WIDTH_NOT_POSITIVE", "FLOOR_HIT", "BOUND_HIT",
                          "COVARIANCE_DIRECTION_DISCARDED", "HIGH_CORRELATION"):
                print(f"      {d.code} {d.where[:6]}: {d.message[:300]}")
    OUT.mkdir(exist_ok=True)
    picks = (0, int(np.argmax(temps)), len(temps) - 1)
    for h in picks:
        one = result.for_histogram(h)
        plot_result(one, path=str(OUT / f"wp2151_zrp2o7_peak_h{h}_fit.png"))
        plot_result(one, path=str(OUT / f"wp2151_zrp2o7_peak_h{h}_high.png"), two_theta_range=(70.0, hi))
    for label, tag in (("z held", "zheld"), ("Si seeded", "siseeded")):
        plot_result(fits[label].for_histogram(0), two_theta_range=(27.6, 29.4),
                    path=str(OUT / f"wp2151_zrp2o7_peak_h0_si111_{tag}.png"))
    print(f"    plots: tests/output/wp2151_zrp2o7_peak_h*_{{fit,high}}.png (patterns "
          f"{', '.join(map(str, picks))}), and pattern 0's Si 111 line in two fits, "
          "wp2151_zrp2o7_peak_h0_si111_*.png")
    print()


def hand_delta(t: float, tm: float, tr: float, cal: dict[str, float]) -> float:
    u, u0 = (t - tm) / tr, (303 - tm) / tr
    return (cal["cal_b"] * (u - u0) + cal["cal_c"] * (u ** 2 - u0 ** 2)
            + cal["cal_d"] * (u ** 3 - u0 ** 3))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "abcde")

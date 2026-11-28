"""A curve another program computed, held in the fixed-background slot and tied to the phase scale.

WP-1512 closed as documentation of a route that exists (option A, Yue,
2026-11-18).  The curve is stored as c*·D in
:class:`~rietx.schemas.instrument.BackgroundFixedPlusChebyshev`, and
``ref.tie("instrument.background.scale", "phases.0.scale")`` makes its
amplitude S·c*·D.  Two claims carry the route, and this file pins both:

* one tied fit lands at the **joint** least-squares minimum, where the
  residual is orthogonal to S's whole column (Bragg term plus curve).  The
  outer loop of refits it replaces stops at a different point, where the
  residual is orthogonal to the Bragg term alone, because the loop holds the
  curve fixed while it refits S.  Both points are linear solves here, so the
  oracle is exact and independent of the solver;
* a preset-style glob over ``instrument.background.*`` frees the Chebyshev
  terms and leaves the tied scale alone.  Since WP-1309 that glob frees an
  untied scale, so without the tie the curve's amplitude floats free of the
  phase scale.

The case is synthetic, built at a known phase scale, so the fit's answer can be
compared with a number rather than judged plausible.  Only linear parameters
are freed, which is what makes the joint minimum a closed-form solve.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import rietx as rx
from rietx.schemas.instrument import BackgroundChebyshev, BackgroundFixedPlusChebyshev
from rietx.schemas.pattern import PatternData
from rietx.schemas.plan import CLOSING_WINDOW_TOL
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_schemas import make_lab6

_OUT = Path(__file__).parent / "output"

#: The phase scale the data are built with.
S_TRUE = 3e-4
#: The unit conversion from the other program's units to counts at phase scale 1.
C_STAR = 5e5
#: The Chebyshev level under everything, in counts.
LEVEL = (60.0, -15.0, 6.0, 0.0)
#: LaB6 lines (Cu Kα1) the diffuse features sit under, and their HWHM in degrees.
CENTRES = (21.36, 30.38, 37.44, 43.51, 48.96)
HWHM = 0.5


def _diffuse(tt: np.ndarray) -> np.ndarray:
    """The other program's curve D, in its own units: Lorentzian features under
    the Bragg lines they broaden, peaking near 1."""
    return sum(1.0 / (1.0 + ((tt - c) / HWHM) ** 2) for c in CENTRES)


def _instrument(level=LEVEL, *, curve_scale: float = 1.0) -> rx.Instrument:
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    grid = np.arange(14.0, 111.0, 0.1)
    ins.background = BackgroundFixedPlusChebyshev(
        fixed_two_theta=grid.tolist(),
        fixed_intensity=(C_STAR * _diffuse(grid)).tolist(),
        fixed_source="synthetic diffuse curve, stored as c*·D (tests/test_simulated_curve_tie.py)",
        scale=rx.Parameter(value=curve_scale, min=0.0),
        chebyshev=BackgroundChebyshev(
            coefficients=[rx.Parameter(value=c) for c in level]))
    return ins


def _structure(scale: float) -> rx.Structure:
    structure = make_lab6()
    structure.phases[0].scale.value = scale
    return structure


def _case(seed: int = 7) -> PatternData:
    """Bragg at S_TRUE, plus S_TRUE·c*·D, plus the level, with Poisson noise."""
    tt = np.arange(15.0, 110.0, 0.02)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    ref = rx.Refinement(_structure(S_TRUE), _instrument(curve_scale=S_TRUE))
    y = np.asarray(ref.predict(grid))
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=tt.tolist(), intensity=counts.tolist(),
                       sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def _columns(data: PatternData) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The model's linear columns on the data grid: Bragg at S = 1, the stored
    curve at scale 1, and one column per Chebyshev term."""
    zero = (0.0,) * len(LEVEL)

    def predict(scale, curve_scale, level):
        return np.asarray(rx.Refinement(_structure(scale), _instrument(
            level, curve_scale=curve_scale)).predict(data))

    bragg = predict(1.0, 0.0, zero)
    curve = predict(0.0, 1.0, zero)
    cheb = np.column_stack([predict(0.0, 0.0, tuple(float(i == k) for i in range(len(LEVEL))))
                            for k in range(len(LEVEL))])
    return bragg, curve, cheb


def _joint_minimum(data, bragg, curve, cheb) -> float:
    """S at the weighted least-squares minimum of y = S·(Bragg + curve) + Σ cₖTₖ."""
    w = 1.0 / np.asarray(data.sigma)
    design = np.column_stack([bragg + curve, cheb]) * w[:, None]
    solution, *_ = np.linalg.lstsq(design, np.asarray(data.intensity) * w, rcond=None)
    return float(solution[0])


def _loop_fixed_point(data, bragg, curve, cheb) -> float:
    """S where the outer loop of refits stops.

    Each pass holds the curve at the previous S and refits S against the Bragg
    term alone, so the loop stops where the residual is orthogonal to the Bragg
    column, with the curve's own dependence on S never differentiated.
    """
    w = 1.0 / np.asarray(data.sigma)
    y = np.asarray(data.intensity)
    design = np.column_stack([bragg, cheb]) * w[:, None]
    s = S_TRUE
    for _ in range(200):
        solution, *_ = np.linalg.lstsq(design, (y - s * curve) * w, rcond=None)
        if abs(solution[0] - s) < 1e-14 * s:
            return s
        s = float(solution[0])
    raise AssertionError(f"the outer loop did not reach its fixed point in 200 passes (S = {s})")


def _tied_fit(data: PatternData):
    """One fit with the tie, the route the manual documents.

    The plan declares its closing stage (off by default since WP-2222), so the answer is measured on the closing
    windows, which are the windows ``predict(grid)`` compiles at.  With
    ``closing_window_tol=None`` the fit's own columns lose tails the oracle's
    keep, and the two minima part by 4e-4 for that reason alone.
    """
    ref = rx.Refinement(_structure(1e-4), _instrument((0.0,) * len(LEVEL)))
    ref.tie("instrument.background.scale", "phases.0.scale")
    plan = RefinementPlan(stages=[Stage("scale_bkg", ["phases.0.scale", "instrument.background.*"])],
                          closing_window_tol=CLOSING_WINDOW_TOL)
    return ref, ref.fit(data, plan=plan, telemetry=False)


def test_one_tied_fit_reaches_the_joint_minimum_and_not_the_loops_fixed_point():
    data = _case()
    ref, result = _tied_fit(data)

    s_fit = result.parameter("phases.0.scale").value
    bragg, curve, cheb = _columns(data)
    s_joint = _joint_minimum(data, bragg, curve, cheb)
    s_loop = _loop_fixed_point(data, bragg, curve, cheb)

    _OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result
    plot_result(result, path=str(_OUT / "simulated_curve_tie.png"))
    plot_result(result, path=str(_OUT / "simulated_curve_tie_zoom.png"),
                two_theta_limits=(18.0, 52.0))

    # the curve's amplitude is the phase scale
    assert ref.fitted_instrument.background.scale.value == s_fit
    # measured 2026-11-18, darwin/arm64 [dev]: the fit sits 5.7e-11 from the
    # joint minimum and the loop's point 8.7e-4 from it (0.17 of S's esd)
    joint_gap = abs(s_fit / s_joint - 1.0)
    loop_gap = abs(s_loop / s_joint - 1.0)
    assert joint_gap < 1e-6, (s_fit, s_joint)
    # the bar discriminates: the loop's point is far outside it
    assert loop_gap > 100 * 1e-6, (s_loop, s_joint)


def test_a_preset_glob_frees_the_terms_and_not_the_tied_scale():
    ref = rx.Refinement(_structure(1e-4), _instrument())
    ref.tie("instrument.background.scale", "phases.0.scale")
    ref.set_vary(["instrument.background.*"], True)
    rows = {row.path: row for row in ref.parameters()}
    assert all(rows[f"instrument.background.c{k}"].vary for k in range(len(LEVEL)))
    scale = rows["instrument.background.scale"]
    assert not scale.vary
    assert scale.tie is not None and scale.tie.user
    assert scale.tie.terms == [("phases.0.scale", 1.0)]

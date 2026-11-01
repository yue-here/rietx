"""``AIR_SCATTER_UNDECLARED`` (issue #636): a P-spline background without its
1/(2θ) term, on a fit whose own residual the term would cut.

``auto_background`` declares the term on ``PatternDiagnostics.air_scatter_gain``,
an envelope test that a broad hump on a line-dense synchrotron pattern blinds,
and since WP-1454 a declined term is absent.  These patterns are the issue's:
rietx's own public NAC fixture simulated on a capillary grid (λ 0.4133 Å) over
a level, a broad hump and, in the positive arms, an A/(2θ) rise.  The control
is the same pattern without the rise, where declaring the term cuts nothing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.refine import (
    AIR_SCATTER_UNDECLARED_FRACTION,
    AIR_SCATTER_UNDECLARED_SCORE,
)
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev, BackgroundPSpline

CIF = Path(__file__).parent / "data" / "cod_1000236.cif"
WAVELENGTH = 0.4133
CODE = "AIR_SCATTER_UNDECLARED"


def _instrument() -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(WAVELENGTH)
    ins.profile.u.value, ins.profile.v.value, ins.profile.w.value = 0.0, 0.0, 4e-4
    ins.profile.x.value = 4e-3
    return ins


def _structure() -> rx.Structure:
    s = rx.Structure.from_cif(str(CIF))
    s.phases[0].scale.value = 2.0e-3
    return s


def _pattern(air: float, *, lo: float = 0.5, hi: float = 50.0, step: float = 0.005,
             seed: int = 7) -> rx.PatternData:
    """Level + a broad hump at 9° (a 1°-knot spline sampling a Gaussian), plus
    ``air``/(2θ), Poisson-noised."""
    grid = np.arange(lo, hi, step)
    truth = BackgroundPSpline.for_range(0.5, 50.0, knot_step_deg=1.0)
    xs = np.linspace(truth.breakpoints[0], truth.breakpoints[-1], len(truth.coefficients))
    for c, x in zip(truth.coefficients, xs, strict=True):
        c.value = float(300.0 + 900.0 * np.exp(-0.5 * ((x - 9.0) / 3.5) ** 2))
        c.vary = False
    if air:
        truth.air_scatter = Parameter(value=air, min=0.0, transform="softplus")
    ins = _instrument()
    ins.background = truth
    y = rx.Refinement(_structure(), ins, history=False).predict(grid)
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 0.0)).astype(float)
    return rx.PatternData(two_theta=grid.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def _fit(data: rx.PatternData, background=None):
    ins = _instrument()
    ins.background = background if background is not None else rx.auto_background(data).background
    ref = rx.Refinement(_structure(), ins, history=False)
    return ins.background, ref.fit(data)


def _found(result):
    return [d for d in result.diagnostics if d.code == CODE]


@pytest.fixture(scope="module")
def rise():
    """The issue's positive arm: a strong rise the envelope trigger declines."""
    data = _pattern(600.0, step=0.01)
    background, result = _fit(data)
    return data, background, result


def test_thresholds_are_the_registered_constants():
    assert AIR_SCATTER_UNDECLARED_FRACTION == 0.005
    assert AIR_SCATTER_UNDECLARED_SCORE == 25.0


def test_a_declined_rise_under_a_hump_fires(rise):
    """The trigger declines the term (the defect #636 reports), and the fit's
    own residual says so: the score reads about 0.14 against the 0.005 bar."""
    _, background, result = rise
    assert background.air_scatter is None, "the envelope trigger declined it"
    found = _found(result)
    assert len(found) == 1, [d.code for d in result.diagnostics]
    d = found[0]
    assert d.level == "warning"
    assert d.value > 10 * AIR_SCATTER_UNDECLARED_FRACTION
    assert "air_scatter = Parameter(" in d.suggestion


def test_declaring_the_term_clears_it_and_cuts_chi2(rise):
    """The remedy it names is the one that works: the declared refit is
    silent, and its χ² is materially lower (25 % on this pattern)."""
    data, _, before = rise
    background = rx.auto_background(data).background
    background.air_scatter = Parameter(value=1e-3, min=0.0, transform="softplus")
    _, after = _fit(data, background)
    assert not _found(after)
    assert after.statistics.chi2 < 0.85 * before.statistics.chi2


def test_fires_where_the_low_angle_region_is_silent():
    """A weaker rise: ``LOW_ANGLE_UNMODELLED`` reads only below the first
    reflection and stays silent, while the whole residual still carries the
    rise (0.015 against the 0.005 bar)."""
    _, result = _fit(_pattern(180.0, step=0.01))
    codes = {d.code for d in result.diagnostics}
    assert "LOW_ANGLE_UNMODELLED" not in codes
    assert CODE in codes


@pytest.mark.parametrize("seed", [7, 8])
def test_silent_without_a_rise(seed):
    """The control: the same hump and lines with no rise.  Declaring the term
    there cuts nothing, and the column's best coefficient is negative."""
    background, result = _fit(_pattern(0.0, step=0.01, seed=seed))
    assert background.air_scatter is None
    assert not _found(result)


def test_silent_where_the_spline_already_draws_the_rise():
    """From 3.2° a 3°-knot spline follows 1/(2θ) on its own, so declaring the
    term buys nothing, and the projected column is small: silent."""
    data = _pattern(600.0, lo=3.2, step=0.01)
    _, result = _fit(data, BackgroundPSpline.for_range(3.2, 49.99, knot_step_deg=3.0))
    assert not _found(result)


def test_silent_on_a_background_that_cannot_carry_the_term():
    """A Chebyshev has no air term to declare, so there is nothing to suggest."""
    _, result = _fit(_pattern(600.0, step=0.01), BackgroundChebyshev.with_terms(8))
    assert not _found(result)


def test_one_sided_the_bounded_term_cannot_take_a_negative_direction():
    """The sign rule, on a fit with the background block solved: push the
    residual along +1/(2θ) and it fires; push it the other way by the same
    amount and it is silent, where a two-sided score would fire on both."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    rfn = __import__("sys").modules["rietx.refine"]

    data = _pattern(0.0, step=0.01)
    ins = _instrument()
    ins.background = rx.auto_background(data).background
    ref = rx.Refinement(_structure(), ins, history=False)
    result = ref.fit(data)
    model = compile_model(ref.fitted_structure, ref.fitted_instrument, data,
                          mode="rietveld")
    table = ParameterTable(ref.fitted_structure, ref.fitted_instrument)
    values = table.decode(table.x0())
    y_calc = model.evaluate(values)
    stats = result.statistics
    push = 300.0 / np.maximum(model.tt, 1e-3)
    assert rfn._air_scatter_undeclared_diagnostics(model, values, y_calc - push, stats)
    assert not rfn._air_scatter_undeclared_diagnostics(model, values, y_calc + push, stats)

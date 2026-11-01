"""WP-1929: the profile interval, ``Refinement.profile_interval``.

A row the fit left on its bound keeps its value and its marginal esd, and is
flagged.  A Wald esd is no interval there, since an estimate on the boundary
has no symmetric sampling distribution (Self & Liang, 1987), so the number a
caller can quote is a profile interval: pin the parameter, refit the rest, and
read where the data's χ² has risen by a χ²₁ quantile.

**The fixture.**  LaB₆ under one wavelength, synthesised with instrument W at
0.0020 deg² and fitted with W fixed at 0.0024.  Every peak in the model is
then a little too broad in its Gaussian part, so the phase's own
``gauss_size``, which can only add Gaussian width, is pushed onto its floor of
0 by the data rather than by noise: the LM active set holds it there and
``FLOOR_HIT`` fires.  The cell is interior and nearly uncorrelated with the
widths, which makes ``cell.a`` the quadratic control.  A fit costs 0.07 s and a
profile under a second (macOS arm64, ``[dev]``).

The real-data case, BT-1's Lorentzian ``y`` on its floor, is
``tests/test_acceptance_wavelength.py``'s, which is slow.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import chi2

import rietx as rx
from rietx import Instrument, PatternData
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.interval import (
    PARAMETER_INTERVAL_CHI2_TOL,
    ParameterInterval,
)
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.parameter_interval import interval_quantile
from rietx.strategy.staged import RefinementPlan, Stage

pytestmark = pytest.mark.xdist_group("parameter-interval")

TWO_THETA = np.arange(20.0, 100.0, 0.02)
W_TRUE, W_FITTED = 0.0020, 0.0024
FLOOR = "phases.0.gauss_size"
INTERIOR = "phases.0.cell.a"
FREE = ["phases.*.scale", "phases.*.cell.*", "instrument.background.*",
        "instrument.zero_shift", "phases.*.lor_strain", FLOOR]
PLAN = RefinementPlan(stages=[
    Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    Stage("all", FREE),
])


def _p(value: float) -> Parameter:
    return Parameter(value=value)


def _models(w: float) -> tuple[Structure, Instrument]:
    lab6 = Phase(name="LaB6", space_group="P m -3 m", cell=Cell.cubic(4.1569),
                 atoms=[Atom(label="La", species="La", x=_p(0.0), y=_p(0.0), z=_p(0.0)),
                        Atom(label="B", species="B", x=_p(0.1993), y=_p(0.5), z=_p(0.5))])
    structure = Structure(phases=[lab6])
    structure.phases[0].scale.value = 1e-3
    structure.phases[0].lor_strain.value = 0.05
    instrument = Instrument.debye_scherrer(wavelength=1.5406)
    instrument.profile.u.value = 0.004
    instrument.profile.v.value = -0.002
    instrument.profile.w.value = w
    instrument.background = BackgroundChebyshev(
        coefficients=[_p(200.0), _p(-60.0), _p(20.0)])
    return structure, instrument


def _synthesize() -> PatternData:
    structure, instrument = _models(W_TRUE)
    blank = PatternData(two_theta=TWO_THETA.tolist(),
                        intensity=np.zeros_like(TWO_THETA).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


def _fitted():
    data = _synthesize()
    ref = rx.Refinement(*_models(W_FITTED))
    return ref, ref.fit(data, plan=PLAN, telemetry=False), data


@pytest.fixture(scope="module")
def fitted():
    return _fitted()


@pytest.fixture(scope="module")
def intervals(fitted):
    """Both profiles, with the state they were run from."""
    ref, _, data = fitted
    before = {row.path: row.value for row in ref.parameters()}
    head = ref.history.head
    floor = ref.profile_interval(data, FLOOR)
    interior = ref.profile_interval(data, INTERIOR)
    return floor, interior, (before, head)


def _end(interval: ParameterInterval, value: float):
    """The probe an end was solved at: the end is always a measured point."""
    [point] = [p for p in interval.points if p.value == value]
    return point


def test_the_floor_row_is_on_its_floor(fitted):
    """The premise: the data, not noise, put ``gauss_size`` on 0."""
    _, result, _ = fitted
    row = result.parameter(FLOOR)
    assert (row.value, row.at_bound) == (0.0, True)
    assert row.stderr > 0.0
    assert "FLOOR_HIT" in [d.code for d in result.diagnostics]
    assert result.parameter(INTERIOR).at_bound is False


def test_a_row_on_its_floor_gets_a_one_sided_interval(fitted, intervals):
    """The bound is one end; the other is at Δχ² = χ²₁(0.90) × χ²_red × f²."""
    _, result, _ = fitted
    interval, _, _ = intervals
    assert interval.one_sided and interval.at_bound is True
    assert (interval.lower, interval.lower_stop) == (0.0, "bound")
    assert interval.upper_stop == "threshold" and interval.upper > 0.0
    # Self & Liang's ½χ²₀ + ½χ²₁: 2.71 at 95 %, not 3.84
    assert interval.quantile == pytest.approx(chi2.ppf(0.90, 1), rel=1e-12)
    stats = result.statistics
    assert interval.delta_chi2_cut == pytest.approx(
        interval.quantile * stats.chi2 * stats.esd_inflation ** 2, rel=1e-12)
    end = _end(interval, interval.upper)
    assert abs(end.delta_chi2 - interval.delta_chi2_cut) <= (
        PARAMETER_INTERVAL_CHI2_TOL * interval.delta_chi2_cut)
    # every probe went inward from the floor, and the refits add up
    assert all(p.value > 0.0 for p in interval.points)
    assert interval.n_refits == sum(p.runs for p in interval.points)
    assert interval.fit_is_minimum


def test_an_interior_row_gets_a_two_sided_interval_at_1_96_esd(intervals):
    """On a near-quadratic profile each end is √3.84 esd from the value.

    Measured 1.9651 and 1.9655 esd, 0.26 % from 1.9600; the band is ten times
    that.  The marginal esd and the profile agree because ``cell.a`` barely
    correlates with the width on its floor, which a profile holds there.
    """
    _, interval, _ = intervals
    assert not interval.one_sided and interval.at_bound is False
    assert (interval.lower_stop, interval.upper_stop) == ("threshold", "threshold")
    assert interval.quantile == pytest.approx(chi2.ppf(0.95, 1), rel=1e-12)
    half = np.sqrt(interval.quantile)
    assert (interval.value - interval.lower) / interval.stderr == pytest.approx(half, rel=0.03)
    assert (interval.upper - interval.value) / interval.stderr == pytest.approx(half, rel=0.03)
    for end in (interval.lower, interval.upper):
        assert abs(_end(interval, end).delta_chi2 - interval.delta_chi2_cut) <= (
            PARAMETER_INTERVAL_CHI2_TOL * interval.delta_chi2_cut)


def test_the_profile_moves_nothing(fitted, intervals):
    """No accepted value moves, ``result_`` stays, and HEAD is put back."""
    ref, result, _ = fitted
    _, _, (before, head) = intervals
    assert ref.result_ is result
    assert {row.path: row.value for row in ref.parameters()} == before
    assert ref.history.head == head


def test_without_history_the_profile_still_moves_nothing(fitted):
    _, _, data = fitted
    ref = rx.Refinement(*_models(W_FITTED), history=False)
    result = ref.fit(data, plan=PLAN, telemetry=False)
    before = {row.path: row.value for row in ref.parameters()}
    interval = ref.profile_interval(data, FLOOR)
    assert interval.upper_stop == "threshold"
    assert all(p.node_id is None for p in interval.points)
    assert ref.result_ is result
    assert {row.path: row.value for row in ref.parameters()} == before


def test_a_side_that_runs_out_of_refits_says_so(fitted):
    """One refit a side: 1 esd out is under the threshold, so neither side ends."""
    ref, _, data = fitted
    interval = ref.profile_interval(data, INTERIOR, max_refits=1)
    assert (interval.lower, interval.lower_stop) == (None, "refits")
    assert (interval.upper, interval.upper_stop) == (None, "refits")
    assert interval.n_refits == 2
    assert all(p.delta_chi2 < interval.delta_chi2_cut for p in interval.points)


def test_a_refit_that_raises_ends_its_side_and_not_the_call(fitted, monkeypatch):
    ref, _, data = fitted

    def broken(*args, **kwargs):
        raise FloatingPointError("a probe that cannot be measured")

    monkeypatch.setattr(rx.Refinement, "run_stage", broken)
    interval = ref.profile_interval(data, INTERIOR)
    assert (interval.lower_stop, interval.upper_stop) == ("error", "error")
    assert interval.lower is None and interval.upper is None
    assert [p.chi2 for p in interval.points] == [None, None]
    assert all("cannot be measured" in p.error for p in interval.points)


def test_a_fit_short_of_its_minimum_says_so(fitted):
    """A last stage cut to one iteration from a poor start: the first refit
    finds χ² below the fit's."""
    _, _, data = fitted
    ref = rx.Refinement(*_models(W_FITTED))
    ref.set_values({INTERIOR: 4.159, "phases.0.lor_strain": 0.09})
    # the declared last stage's cut; the closing stage is tests/test_closing_stage.py's
    short = RefinementPlan(stages=[PLAN.stages[0], Stage("all", FREE, max_iter=1)],
                           closing_window_tol=None)
    result = ref.fit(data, plan=short, telemetry=False)
    interval = ref.profile_interval(data, INTERIOR, max_refits=1)
    assert interval.chi2_fit == pytest.approx(
        result.statistics.chi2 * (result.statistics.n_points
                                  - result.statistics.n_free_parameters), rel=1e-12)
    assert interval.chi2_lowest < interval.chi2_fit - (
        PARAMETER_INTERVAL_CHI2_TOL * interval.delta_chi2_cut)
    assert not interval.fit_is_minimum
    assert min(p.delta_chi2 for p in interval.points) < 0.0


def test_the_profile_refuses_what_it_cannot_answer(fitted):
    ref, _, data = fitted
    with pytest.raises(RuntimeError, match="run a fit"):
        rx.Refinement(*_models(W_FITTED)).profile_interval(data, INTERIOR)
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.profile_interval(data, "phases.0.cell.aa")
    with pytest.raises(ValueError, match="tied: = "):
        ref.profile_interval(data, "phases.0.cell.b")
    with pytest.raises(ValueError, match="structurally fixed"):
        ref.profile_interval(data, "phases.0.cell.alpha")
    with pytest.raises(ValueError, match="was not free in the last fit"):
        ref.profile_interval(data, "instrument.profile.u")
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        ref.profile_interval(data, INTERIOR, level=1.0)
    with pytest.raises(ValueError, match="the bound alone"):
        ref.profile_interval(data, FLOOR, level=0.5)
    with pytest.raises(ValueError, match="max_refits"):
        ref.profile_interval(data, INTERIOR, max_refits=0)


def test_the_one_sided_quantile_is_the_mixtures():
    """P(½χ²₀ + ½χ²₁ > c) = ½·P(χ²₁ > c), so c sits at χ²₁'s 2·level − 1."""
    assert interval_quantile(0.95, one_sided=False) == pytest.approx(3.841459, abs=1e-6)
    assert interval_quantile(0.95, one_sided=True) == pytest.approx(2.705543, abs=1e-6)
    level = 0.9
    c = interval_quantile(level, one_sided=True)
    assert 0.5 * chi2.sf(c, 1) == pytest.approx(1.0 - level, rel=1e-12)


def test_the_interval_round_trips_through_json(intervals):
    for interval in intervals[:2]:
        assert ParameterInterval.model_validate_json(interval.model_dump_json()) == interval

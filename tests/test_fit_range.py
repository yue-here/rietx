"""WP-2075: the result records its fit range, and what lies outside it.

The record restates the caller's own act, so these tests check it against the
pattern and the limits handed in, and against ``len(result.two_theta)`` — the
fitted channel count ``compile_model`` is pinned to — never against a second
derivation of the mask.  One fit with nothing cut and one with both limits and
an excluded region share the termination view's synthetic LaB6 (about two
seconds each).

Issue #1219's two cases run on its family A, a cubic perovskite ABO3 in a
capillary at λ 1.5406 Å drawn by rietx's own forward model: C7, a planted
low-angle rise cut away at each of the issue's lower limits, and C8, the
upper limit on the centre of (420) and half a FWHM below it (a fraction of a
second per fit).
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.fit_range import model_reflections
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.results import RefinementResult
from tests.planted_series import _perovskite
from tests.test_refine_synthetic import synthesize
from tests.test_termination_view import _instrument, make_lab6

pytestmark = pytest.mark.xdist_group("fit-range")

LIMITS = (5.0, 20.0)
BAND = (10.0, 11.0)


def _fit(data, limits=None):
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    result = ref.fit(data, plan=rx.RefinementPlan.mccusker_default(),
                     two_theta_limits=limits)
    return ref, result


@pytest.fixture(scope="module")
def uncut():
    return _fit(synthesize())


@pytest.fixture(scope="module")
def cut():
    data = synthesize()
    data = data.model_copy(update={"excluded_regions": [BAND, (30.0, 31.0)]})
    return data, *_fit(data, LIMITS)


def test_an_uncut_fit_reports_the_file_range_and_nothing_else(uncut):
    _ref, result = uncut
    fr = result.fit_range
    assert fr is not None
    assert fr.fitted_range == fr.file_range
    assert fr.n_fitted == fr.n_file == len(result.two_theta)
    assert fr.limits_requested is fr.limits_applied is None
    assert fr.excluded_declared == fr.excluded_applied == []
    assert fr.outside == []
    assert fr.counts_fitted == pytest.approx(fr.counts_file)


def test_a_cut_fit_records_the_limits_and_regions_as_asked_and_applied(cut):
    data, _ref, result = cut
    fr = result.fit_range
    assert fr.limits_requested == LIMITS
    assert fr.limits_applied == LIMITS
    assert fr.file_range == (data.two_theta[0], data.two_theta[-1])
    assert fr.n_file == len(data.two_theta)
    assert fr.n_fitted == len(result.two_theta)
    assert fr.fitted_range == (result.two_theta[0], result.two_theta[-1])
    # declared beyond the file's range, so declared and not applied
    assert fr.excluded_declared == [BAND, (30.0, 31.0)]
    assert fr.excluded_applied == [BAND]


def test_each_unfitted_stretch_is_one_span_with_its_share_of_the_counts(cut):
    data, _ref, result = cut
    fr = result.fit_range
    assert [s.kind for s in fr.outside] == ["below", "excluded", "above"]
    assert sum(s.n_points for s in fr.outside) == fr.n_file - fr.n_fitted
    assert fr.count_share_outside == pytest.approx(
        1.0 - fr.counts_fitted / fr.counts_file)
    below, band, above = fr.outside
    assert below.lo == data.two_theta[0] and below.hi < LIMITS[0]
    assert BAND[0] <= band.lo and band.hi <= BAND[1]
    assert above.lo > LIMITS[1] and above.hi == data.two_theta[-1]


def test_the_record_round_trips_through_json(cut):
    _data, _ref, result = cut
    back = RefinementResult.model_validate_json(result.model_dump_json())
    assert back.fit_range == result.fit_range
    dumped = result.model_dump(mode="json")["fit_range"]
    assert dumped["limits_requested"] == list(LIMITS)


def test_the_summary_prints_the_range_beside_the_excluded_line(uncut, cut):
    ref, result = uncut
    line = f"    {result.fit_range.line()}"
    assert line in ref.summary().splitlines()
    assert "% of the file's counts outside" not in line
    _data, ref, result = cut
    lines = ref.summary().splitlines()
    excluded = next(i for i, s in enumerate(lines) if s.startswith("    excluded: "))
    assert lines[excluded + 1] == f"    {result.fit_range.line()}"
    assert "outside, in 3 spans" in lines[excluded + 1]


# -- issue #1219's family A: C7 and C8 ---------------------------------------

CU_KA1 = 1.5406
A_TRUE = 3.950
FILE_STEP = 0.01
BKG_TRUE = (300.0, -60.0, 20.0)
#: C7's planted rise: 20x the mean background at the file's start, decaying
#: over 3 degrees (issue #1219)
RISE_AT_START, RISE_DECAY_DEG = 20.0, 3.0
#: the issue's lower limits for C7
C7_CUTS = (9.0, 11.0, 13.0, 16.0, 22.0)


def _family_a_instrument(true: bool) -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=CU_KA1)
    ins.profile.u.value = 2e-3
    ins.profile.w.value = 3e-3 if true else 4e-3
    ins.background = (
        BackgroundChebyshev(coefficients=[Parameter(value=v) for v in BKG_TRUE])
        if true else BackgroundChebyshev.with_terms(4))
    return ins


def _family_a_structure(true: bool) -> rx.Structure:
    phase = _perovskite(A_TRUE if true else A_TRUE + 0.003)
    phase.scale.value = 5e-4 if true else 6.5e-4
    return rx.Structure(phases=[phase])


@pytest.fixture(scope="module")
def family_a():
    """Family A's truth on a 5-130 degree file: the noise-free pattern, the
    truth's (420), and a function drawing Poisson counts with or without
    C7's rise."""
    structure, ins = _family_a_structure(True), _family_a_instrument(True)
    tt = np.arange(5.0, 130.0, FILE_STEP)
    grid = rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    y = model.evaluate(values)
    r420 = next(r for r in model_reflections(model, values, ["ABO3"])
                if r.hkl == [4, 2, 0])

    def draw(rise: bool) -> rx.PatternData:
        extra = (RISE_AT_START * BKG_TRUE[0]
                 * np.exp(-(model.tt - model.tt[0]) / RISE_DECAY_DEG)
                 if rise else 0.0)
        rng = np.random.default_rng(7)
        counts = rng.poisson(np.maximum(y + extra, 1.0)).astype(float)
        return rx.PatternData(two_theta=model.tt.tolist(),
                              intensity=counts.tolist())

    return draw, r420


def _fit_family_a(data, limits):
    ref = rx.Refinement(_family_a_structure(False),
                        _family_a_instrument(False), history=False)
    result = ref.fit(data, plan=rx.RefinementPlan.mccusker_default(),
                     two_theta_limits=limits)
    return ref, result


@pytest.mark.parametrize("cut", C7_CUTS)
def test_c7_a_low_cut_reports_the_rise_it_left_out(family_a, cut):
    """C7: whatever the lower limit, the span below it carries its share of
    the counts and its level, at the cut and at the file's start, rising
    away from the fitted range."""
    draw, _r420 = family_a
    data = draw(rise=True)
    ref, result = _fit_family_a(data, (cut, 130.0))
    fr = result.fit_range
    assert fr.limits_requested == (cut, 130.0)
    assert fr.n_fitted == len(result.two_theta)
    [below] = fr.outside
    assert below.kind == "below"
    assert below.lo == data.two_theta[0] and below.hi < cut
    assert 0.0 < below.count_share == pytest.approx(fr.count_share_outside)
    assert below.level_ratio_at_cut is not None
    assert below.level_ratio_far is not None
    # the rise grows toward the file's start, and rises away from the cut
    assert below.level_ratio_far > below.level_ratio_at_cut > 1.0
    assert below.slope_at_cut > 0.0
    assert any(line.strip() == fr.line() for line in ref.summary().splitlines())


@pytest.fixture(scope="module")
def c8(family_a):
    """C8: the upper limit on the truth's (420) centre, and half its FWHM
    below; the fitted model's (420) as each record lists it."""
    draw, r420 = family_a
    data = draw(rise=False)
    out = {}
    for offset in (0.0, -0.5):
        limits = (5.0, r420.two_theta + offset * r420.fwhm)
        ref, result = _fit_family_a(data, limits)
        [above] = result.fit_range.outside
        out[offset] = (ref, result, above)
    return r420, out


@pytest.mark.parametrize("offset", [0.0, -0.5])
def test_c8_an_upper_limit_through_420_lists_it_as_straddling(c8, offset):
    r420, fits = c8
    ref, result, above = fits[offset]
    assert above.kind == "above"
    assert above.lo > result.fit_range.limits_applied[1]
    [row] = [r for r in above.reflections if r.hkl == [4, 2, 0]]
    assert row.phase == "ABO3" and row.line == 0
    assert row.two_theta == pytest.approx(r420.two_theta, abs=0.2 * r420.fwhm)
    assert any(line.strip() == result.fit_range.line()
               for line in ref.summary().splitlines())


def test_c8_half_of_420_is_outside_at_its_centre_and_more_below_it(c8):
    _r420, fits = c8
    at_centre = next(r for r in fits[0.0][2].reflections if r.hkl == [4, 2, 0])
    below = next(r for r in fits[-0.5][2].reflections if r.hkl == [4, 2, 0])
    # the cut falls half a channel past the limit at most: a channel's
    # share of the profile either side of one half
    assert 0.4 < at_centre.fraction_outside < 0.6
    assert below.fraction_outside > at_centre.fraction_outside
    assert below.fraction_outside > 0.75

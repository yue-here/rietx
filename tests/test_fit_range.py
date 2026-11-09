"""WP-2075: the result records its fit range, and what lies outside it.

The record restates the caller's own act, so these tests check it against the
pattern and the limits handed in, and against ``len(result.two_theta)`` — the
fitted channel count ``compile_model`` is pinned to — never against a second
derivation of the mask.  One fit with nothing cut and one with both limits and
an excluded region share the termination view's synthetic LaB6 (about two
seconds each).
"""

from __future__ import annotations

import pytest

import rietx as rx
from rietx.schemas.results import RefinementResult
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

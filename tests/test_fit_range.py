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
second per fit).  ``STRADDLE_FWHM``'s listing is held complete on family A and
the synthetic LaB6, with cuts placed one channel either side of 3 FWHM of each
reflection and exactly at it (no fit: the truth's reflections are described
directly).
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.fit_range import (
    describe_outside,
    fit_range_record,
    model_reflections,
)
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.results import RefinementResult
from tests.planted_series import _perovskite
from tests.test_refine_synthetic import synthesize, truth
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


def test_channels_the_sigma_rule_drops_are_no_cut_of_the_callers():
    """With no limits and no regions, the channels WP-1952's default
    (``nonpositive_sigma="exclude"``) drops for σ = 0 are in no span: they
    are counted by ``sigma_rule``, not reported as a range end or an excluded
    region the caller declared.  Before the fix the record held three spans
    here, ``below``, ``excluded`` and ``excluded``."""
    data = synthesize()
    sig = np.sqrt(np.maximum(np.asarray(data.intensity), 1.0))
    zeros = [0, 500, 501, 900]
    sig[zeros] = 0.0
    data = data.model_copy(update={"sigma": sig.tolist()})
    _ref, result = _fit(data)
    fr = result.fit_range
    assert fr.limits_requested is None
    assert fr.excluded_declared == fr.excluded_applied == []
    assert fr.outside == []
    assert fr.n_fitted == len(result.two_theta) == fr.n_file - len(zeros)
    assert result.sigma_rule.n_nonpositive_excluded == len(zeros)
    assert "outside" not in fr.line()
    # with limits, the spans are the limits' alone, and the three counts
    # still add up to the file's
    rec = fit_range_record(data, LIMITS)
    assert [s.kind for s in rec.outside] == ["below", "above"]
    assert rec.outside[0].hi < LIMITS[0] < LIMITS[1] < rec.outside[1].lo
    n_sigma = data.sigma_rule(
        (data.tt() >= LIMITS[0]) & (data.tt() <= LIMITS[1])).n_nonpositive_excluded
    assert n_sigma == 3
    assert rec.n_fitted + sum(s.n_points for s in rec.outside) + n_sigma == rec.n_file


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
def family_a_truth():
    """Family A's truth compiled on a 5-130 degree file: the model, its
    values and every (line, reflection) it generates there."""
    structure, ins = _family_a_structure(True), _family_a_instrument(True)
    tt = np.arange(5.0, 130.0, FILE_STEP)
    grid = rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    return model, values, model_reflections(model, values, ["ABO3"])


@pytest.fixture(scope="module")
def family_a(family_a_truth):
    """Family A's truth on a 5-130 degree file: the truth's (420), and a
    function drawing Poisson counts from the noise-free pattern with or
    without C7's rise."""
    model, values, reflections = family_a_truth
    y = model.evaluate(values)
    r420 = next(r for r in reflections if r.hkl == [4, 2, 0])

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
    away from the fitted range.

    Family A's own Chebyshev background already rises toward low angle, so
    each fact is read against the same fit of the same draw without the rise.
    Without the rise (rise / no rise, 2026-11-17): ``level_ratio_far`` 19.4 /
    1.35 at 9 degrees and 19.7 / 1.37 at 22, about 14x at every cut;
    ``count_share`` 0.268 / 0.041 at 9 and 0.437 / 0.166 at 22, 2.6x at the
    least; ``slope_at_cut`` 0.271 / 0.013 at 9 and 0.053 / 0.037 at 22."""
    draw, _r420 = family_a
    data = draw(rise=True)
    ref, result = _fit_family_a(data, (cut, 130.0))
    _ref0, plain = _fit_family_a(draw(rise=False), (cut, 130.0))
    [plain_below] = plain.fit_range.outside
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
    # ... and the record sees the rise, not the background beneath it
    assert below.level_ratio_far > 5.0 * plain_below.level_ratio_far
    assert below.count_share > 2.0 * plain_below.count_share
    assert below.slope_at_cut > plain_below.slope_at_cut
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


# -- the straddle window: complete at 3 FWHM, and nothing beyond ------------

#: The grounds' 3 FWHM, written out rather than imported, so a changed
#: ``STRADDLE_FWHM`` fails these tests instead of moving their oracle with it.
STRADDLE = 3.0


def _cuts(tt, span):
    """A span's two cuts in 2θ as ``OutsideSpan.reflections`` reads them: half
    a step past its first and last channel, open where it runs to the file's
    end."""
    i0, i1 = int(np.searchsorted(tt, span.lo)), int(np.searchsorted(tt, span.hi))
    lo = -math.inf if i0 == 0 else 0.5 * (tt[i0 - 1] + tt[i0])
    hi = math.inf if i1 == tt.size - 1 else 0.5 * (tt[i1] + tt[i1 + 1])
    return lo, hi


def _described(data, limits, regions, reflections):
    """Every span of ``data`` cut by ``limits`` and ``regions``, described
    against ``reflections``, each with its two cuts."""
    data = data.model_copy(update={"excluded_regions": list(regions)})
    record = describe_outside(fit_range_record(data, limits), data, limits,
                              [], reflections, None)
    assert record.straddle_fwhm == STRADDLE
    return [(span, _cuts(data.tt(), span)) for span in record.outside]


def _key(r):
    return (tuple(r.hkl), r.line, r.two_theta)


def _placements(tt, r):
    """Cuts placed beside reflection ``r``: ``(where, limits, regions, cut,
    side)`` for an upper limit and an excluded band above it (``side`` +1),
    a lower limit and an excluded band below it (-1), each with its cut on
    the last channel boundary within 3 FWHM of the centre (``"inside"``) and
    on the next one out (``"outside"``), one channel apart."""
    step = float(tt[1] - tt[0])
    mid = 0.5 * (tt[:-1] + tt[1:])
    reach = STRADDLE * r.fwhm
    up = np.flatnonzero((mid > r.two_theta) & (mid - r.two_theta <= reach))[-1]
    down = np.flatnonzero((mid < r.two_theta) & (r.two_theta - mid <= reach))[0]
    out = []
    for where, k in (("inside", up), ("outside", up + 1)):
        out.append((where, (tt[0], tt[k] + step / 4), [], mid[k], +1))
        out.append((where, None, [(tt[k + 1] - step / 4, tt[k + 1] + 1.0)],
                    mid[k], +1))
    for where, k in (("inside", down), ("outside", down - 1)):
        out.append((where, (tt[k + 1] - step / 4, tt[-1] + 1.0), [], mid[k], -1))
        out.append((where, None, [(tt[k] - 1.0, tt[k] + step / 4)], mid[k], -1))
    return out


@pytest.fixture(scope="module", params=["family A", "LaB6"])
def straddle_case(request, family_a, family_a_truth):
    """A pattern drawn from a known truth, the truth's reflections, and those
    a placed cut and a 1 degree band beside them keep inside the file: family
    A (Cu Kα1, 0.01 degree step), and the synthetic LaB6 the fits above use
    (0.4139 Å, 0.005 degree step, a zero shift)."""
    if request.param == "family A":
        draw, _r420 = family_a
        data = draw(rise=False)
        *_, reflections = family_a_truth
    else:
        data = synthesize()
        structure, ins = truth()
        model = compile_model(structure, ins, data, mode="rietveld")
        table = ParameterTable(structure, ins)
        reflections = model_reflections(model, table.decode(table.x0()), ["LaB6"])
    tt = data.tt()
    placed = [r for r in reflections if tt[0] + 2.0 < r.two_theta < tt[-1] - 2.0]
    assert len(placed) >= 10
    return data, reflections, placed


def test_every_reflection_within_3_fwhm_of_a_cut_is_listed_and_none_beyond(
        straddle_case):
    """Each reflection gets a cut just inside 3 FWHM of its centre and one a
    channel further (5 to 10 % of 3 FWHM on these two families), above
    and below it, as a range end and as an excluded band's edge.  The
    reflection is listed exactly when the cut is inside, and every span's
    list is the whole set the definition names: each model reflection
    centred in the span or within 3 of its own FWHM of either cut, and no
    other."""
    data, reflections, placed = straddle_case
    tt = data.tt()
    step = float(tt[1] - tt[0])
    for r in placed:
        reach = STRADDLE * r.fwhm
        for where, limits, regions, cut, side in _placements(tt, r):
            gap = side * (cut - r.two_theta)
            if where == "inside":
                assert reach - step < gap <= reach
            else:
                assert reach < gap <= reach + step
            spans = _described(data, limits, regions, reflections)
            [span] = [s for s, c in spans if cut in c]
            assert (_key(r) in {_key(x) for x in span.reflections}) == (
                where == "inside"), (r.hkl, where, limits, regions)
            for s, (lo, hi) in spans:
                expected = {_key(x) for x in reflections
                            if lo <= x.two_theta <= hi
                            or min(abs(x.two_theta - lo), abs(x.two_theta - hi))
                            <= STRADDLE * x.fwhm}
                assert {_key(x) for x in s.reflections} == expected


def test_a_reflection_exactly_3_fwhm_from_a_cut_is_listed_and_one_ulp_past_is_not(
        straddle_case):
    """The boundary itself, at each cut of the test above: a copy of the
    reflection with its FWHM rounded to 1/1024 degree, so that 3 FWHM and the
    centre's distance to the cut are exact in binary, centred exactly 3 FWHM
    from the cut is listed ("within" is inclusive), and the same copy one ulp
    further out is not."""
    data, _reflections, placed = straddle_case
    tt = data.tt()
    for r in placed:
        fwhm = round(r.fwhm * 1024) / 1024
        for where, limits, regions, cut, side in _placements(tt, r):
            if where != "inside":
                continue
            at = cut - side * STRADDLE * fwhm
            assert abs(at - cut) == STRADDLE * fwhm
            past = float(np.nextafter(at, -side * math.inf))
            pair = [dataclasses.replace(r, two_theta=at, fwhm=fwhm),
                    dataclasses.replace(r, two_theta=past, fwhm=fwhm)]
            spans = _described(data, limits, regions, pair)
            [span] = [s for s, c in spans if cut in c]
            assert [x.two_theta for x in span.reflections] == [at], (
                r.hkl, limits, regions)


def test_the_record_carries_the_widths_its_facts_were_read_with(uncut, cut):
    from rietx.report.fit_range import CUT_WINDOW_DEG, STRADDLE_FWHM

    _ref, result = uncut
    assert result.fit_range.cut_window_deg is result.fit_range.straddle_fwhm is None
    _data, _ref, result = cut
    assert result.fit_range.cut_window_deg == CUT_WINDOW_DEG
    assert result.fit_range.straddle_fwhm == STRADDLE_FWHM


def test_run_stage_keeps_the_record(cut):
    data, _ref, result = cut
    ref, _ = _fit(data, LIMITS)  # its own fit: run_stage moves the shared one
    ref.run_stage(data, rx.Stage("scale", ["phases.*.scale"]), two_theta_limits=LIMITS)
    assert ref.result_.fit_range is not None
    assert ref.result_.fit_range.n_fitted == result.fit_range.n_fitted
    assert f"    {ref.result_.fit_range.line()}" in ref.summary().splitlines()


def test_an_uncut_pdcif_without_the_pattern_keeps_its_step(uncut):
    from rietx.io.cif.powder import pattern_items

    _ref, result = uncut
    pairs = dict(pattern_items(result, 0.4139)[0])
    assert "_pd_meas_2theta_range_inc" in pairs

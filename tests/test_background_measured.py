"""A measured background: the scale, its esds, and the four ways it goes wrong.

:class:`~rietx.schemas.instrument.BackgroundFixedPlusChebyshev` held a curve and
added it with an implicit coefficient of exactly 1.0, which is TOPAS's
``bkg_file("f.xy")`` and only that form.  WP-1309 adds the other one,
``bkg_file("f.xy", @, s)``, and every test here exists because one step of that
can be wrong in a way nothing else would notice:

* a curve carried **twice** — as the frozen ``fixed_background`` term and as a
  design row — is absorbed by the refined scale as ``s_true − 1``, leaves Rwp
  bit-for-bit unchanged, and is wrong only in the number the caller asked for;
* a scale outside ``bkg_paths`` falls to the finite-difference fallback, which
  is still correct and rebuilds the profile derivative bases every iteration;
* a scale the stage cannot move must be folded into the frozen curve, where 1.0
  is exactly the identity, or every number a project produced before this field
  existed moves by an ulp for nothing;
* and a curve that does not cover the pattern was extrapolated by ``np.interp``
  silently, which is counts nobody measured.

The fixture here is **synthetic**, and deliberately so: it is built at a known
scale, so it can ask whether the machinery recovers a number rather than whether
a number is plausible.  The **real** blank arrived on 2026-09-17 and is
`tests/data/11BM_Kapton.xy`; issue #171's own measurements are checked against
it in `test_acceptance_si640c.py`'s blank arms, which is also where the
synthetic findings below are corroborated on data nobody built — the recovered
scale is biased low by the same regression dilution, and a longer polynomial
eats it the same way.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.background import select_chebyshev_order
from rietx.background.models import FIXED_RANGE_SLACK_STEPS, interpolate_fixed
from rietx.model.forward import SCALE_PATH, compile_model
from rietx.optimize.least_squares import _make_jacobian
from rietx.params.vector import ParameterTable, background_parameters
from rietx.refine import mode_fixed_path
from rietx.schemas.instrument import BackgroundFixedPlusChebyshev, Instrument
from rietx.schemas.pattern import PatternData
from rietx.schemas.plan import StageSpec
from rietx.strategy.staged import PLAN_PRESETS, RefinementPlan, Stage
from tests.test_schemas import make_lab6

_OUT = Path(__file__).parent / "output"

#: The scale the synthetic data are built with.  0.85 because that is where the
#: issue's own hand-set scan found its interior minimum, so the fixture asks the
#: machinery the question the real blank will ask it.
S_TRUE = 0.85

WAVELENGTH = 1.5405929


# ----------------------------------------------------------------------
# the case
# ----------------------------------------------------------------------
def _container_scattering(tt: np.ndarray) -> np.ndarray:
    """What the empty container scatters, as a smooth curve of 2θ.

    Shaped like the thing being modelled rather than like a polynomial: a broad
    low-angle feature (a Kapton or quartz halo), on a level that falls away with
    angle.  Nothing here is fitted, so its only job is to be a shape a Chebyshev
    of low order cannot reproduce.
    """
    halo = 420.0 * np.exp(-0.5 * ((tt - 21.0) / 6.5) ** 2)
    return 140.0 + 5200.0 / tt + halo


def _blank_scan(*, seed: int = 4, step: float = 0.05) -> PatternData:
    """The blank, as somebody measured it: its own coarser grid, its own noise.

    Coarser than the specimen scan on purpose — a blank is a cheap scan, the
    grids never match, and interpolation is therefore part of the feature
    rather than an implementation detail.
    """
    tt = np.arange(14.5, 110.5, step)
    counts = np.random.default_rng(seed).poisson(_container_scattering(tt))
    return PatternData(two_theta=tt.tolist(),
                       intensity=counts.astype(float).tolist(),
                       sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def synthetic_blank_case(*, s_true: float = S_TRUE, seed: int = 5):
    """``(data, blank, structure, instrument)`` for a specimen in a container.

    The specimen scan carries ``s_true`` times the container's **true**
    scattering, because that is the physical situation: the blank is one noisy
    measurement of a curve the sample run sees through the specimen, at a
    different monitor normalisation and counting time.  A fixture that reused
    the noisy blank itself would be asking the fit to recover a number it had
    been handed exactly.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3

    tt = np.arange(15.0, 110.0, 0.02)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = (np.asarray(model.evaluate(table.decode(table.x0())))
         + s_true * _container_scattering(model.tt))
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 1.0))
    data = PatternData(two_theta=model.tt.tolist(),
                       intensity=counts.astype(float).tolist(),
                       sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())
    return data, _blank_scan(), structure, ins


def _with_blank(ins: Instrument, blank: PatternData, *, vary_scale: bool,
                n_terms: int = 3, scale: float = 1.0) -> Instrument:
    ins = ins.model_copy(deep=True)
    ins.background = BackgroundFixedPlusChebyshev.from_pattern(
        blank, n_terms=n_terms, vary_scale=vary_scale, scale=scale,
        source="synthetic container scan (tests/test_background_measured.py)")
    return ins


def _state(*, vary_scale: bool, **kw):
    """``(data, structure, instrument, table, model)`` at the starting values."""
    data, blank, structure, ins = synthetic_blank_case()
    ins = _with_blank(ins, blank, vary_scale=vary_scale, **kw)
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return data, structure, ins, table, model


def _plot(result, stem):
    """obs/calc/diff PNGs to tests/output/ (gitignored), full range + a
    low-angle zoom, where the container's halo is — house convention."""
    from rietx.viz.plots import plot_result

    _OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(_OUT / f"{stem}.png"))
    plot_result(result, path=str(_OUT / f"{stem}_zoom.png"),
                two_theta_range=(15.0, 40.0))


# ----------------------------------------------------------------------
# the schema
# ----------------------------------------------------------------------
def test_the_default_is_the_form_this_package_already_had():
    """Declaring nothing must be ``bkg_file("f.xy")``: one, held, unbounded
    below by nothing at all."""
    bkg = BackgroundFixedPlusChebyshev(fixed_two_theta=[10.0, 20.0],
                                       fixed_intensity=[100.0, 90.0])
    assert bkg.scale.value == 1.0
    assert bkg.scale.vary is False
    assert bkg.scale.min == 0.0
    assert bkg.fixed_sigma is None and bkg.fixed_source is None


def test_from_pattern_carries_the_esds_it_has_and_invents_none():
    """``PatternData.sig()`` would hand back a Poisson fallback, which is the
    one thing a curve with no statistics must not be given: ``fixed_sigma`` is
    what says the blank was counted, and a fabricated √y would say it falsely.
    """
    counted = PatternData(two_theta=[10.0, 20.0], intensity=[100.0, 90.0],
                          sigma=[10.0, 9.5])
    uncounted = PatternData(two_theta=[10.0, 20.0], intensity=[100.0, 90.0])
    assert BackgroundFixedPlusChebyshev.from_pattern(counted).fixed_sigma == [10.0, 9.5]
    assert BackgroundFixedPlusChebyshev.from_pattern(uncounted).fixed_sigma is None


def test_a_region_excluded_in_the_blank_does_not_become_background():
    """A channel somebody marked bad in the blank is not a background level.

    The curve skips it and the interpolation bridges the gap, which is the
    honest reading of an exclusion: "I do not know what the container did here",
    rather than "the container did this".
    """
    blank = PatternData(two_theta=[1.0, 2.0, 3.0, 4.0],
                        intensity=[10.0, 11.0, 900.0, 13.0],
                        sigma=[1.0, 1.1, 30.0, 1.3],
                        excluded_regions=[(2.5, 3.5)])
    bkg = BackgroundFixedPlusChebyshev.from_pattern(blank)
    assert bkg.fixed_two_theta == [1.0, 2.0, 4.0]
    assert bkg.fixed_intensity == [10.0, 11.0, 13.0]
    assert bkg.fixed_sigma == [1.0, 1.1, 1.3]
    # and the gap is bridged rather than left as a spike
    assert interpolate_fixed(np.array([3.0]),
                             np.asarray(bkg.fixed_two_theta),
                             np.asarray(bkg.fixed_intensity))[0] == 12.0


def test_a_sigma_that_does_not_match_the_curve_is_refused():
    with pytest.raises(ValidationError, match="fixed_sigma has 2 points"):
        BackgroundFixedPlusChebyshev(fixed_two_theta=[10.0], fixed_intensity=[1.0],
                                     fixed_sigma=[1.0, 2.0])
    with pytest.raises(ValidationError, match="non-negative"):
        BackgroundFixedPlusChebyshev(fixed_two_theta=[10.0], fixed_intensity=[1.0],
                                     fixed_sigma=[-1.0])


def test_the_scale_is_registered_where_the_write_back_reads_it():
    """One authority for the sub-path, or a refined scale reverts at the next
    stage's recompile and nothing says so (``background_parameters``'s own rule).
    """
    _d, structure, ins, table, _m = _state(vary_scale=True)
    assert [s for s, _ in background_parameters(ins.background)][-1] == "scale"
    assert SCALE_PATH in table.free_paths

    table.entries[table._paths[SCALE_PATH]].value = 0.7
    table.apply_to_models(structure, ins)
    assert ins.background.scale.value == pytest.approx(0.7)


def test_the_cif_says_measured_only_when_somebody_named_the_measurement():
    """The exported description is a claim, so it follows ``fixed_source``.

    Before WP-1309 it read "fixed estimated curve" whatever the curve was, which
    described a blank capillary scan as an estimator's output.
    """
    from rietx.io.exporters import _background_description

    _d, _s, ins, _t, _m = _state(vary_scale=True)
    assert "measured curve" in _background_description(ins)
    assert "refined scale" in _background_description(ins)

    ins.background.fixed_source = None
    ins.background.scale.vary = False
    text = _background_description(ins)
    assert "fixed estimated curve" in text and "scale held at 1" in text


def test_le_bail_leaves_this_scale_free():
    """``mode_fixed_path`` force-fixes a *phase* scale, and this is not one.

    The suffix test WP-1119 anchored at ``phases.`` is what makes that true, and
    this path is the second one to depend on it.
    """
    for mode in ("lebail", "pawley"):
        assert mode_fixed_path(SCALE_PATH, mode) is False
        assert mode_fixed_path("phases.0.scale", mode) is True


# ----------------------------------------------------------------------
# the curve is carried once
# ----------------------------------------------------------------------
def test_a_held_scale_is_folded_into_the_frozen_curve():
    """The bit-identity claim, which has no golden to protect it: before this
    WP nothing in the suite built this background at all.

    A held scale must leave the design matrix the width it was and the frozen
    term the curve it was, because ``1.0 * f`` is exactly ``f`` and a design row
    would re-associate the sum.
    """
    data, _s, ins, _t, model = _state(vary_scale=False)
    curve = interpolate_fixed(np.asarray(model.tt),
                              np.asarray(ins.background.fixed_two_theta),
                              np.asarray(ins.background.fixed_intensity))
    assert SCALE_PATH not in model.bkg_paths
    assert model.bkg_design.shape[0] == len(ins.background.chebyshev.coefficients)
    assert np.array_equal(model.fixed_background, curve)
    assert len(data.two_theta) == len(model.tt)


def test_a_held_scale_that_is_not_one_is_folded_at_its_value():
    _d, _s, ins, _t, model = _state(vary_scale=False, scale=0.5)
    curve = interpolate_fixed(np.asarray(model.tt),
                              np.asarray(ins.background.fixed_two_theta),
                              np.asarray(ins.background.fixed_intensity))
    assert np.array_equal(model.fixed_background, 0.5 * curve)


def test_a_free_scale_is_a_row_and_the_frozen_term_is_gone():
    """Trap 1, made unrepresentable rather than tested for: the two ways of
    carrying the curve are branches of one ``if``."""
    _d, _s, ins, _t, model = _state(vary_scale=True)
    assert model.bkg_paths[-1] == SCALE_PATH
    assert model.fixed_background is None
    curve = interpolate_fixed(np.asarray(model.tt),
                              np.asarray(ins.background.fixed_two_theta),
                              np.asarray(ins.background.fixed_intensity))
    assert np.array_equal(model.bkg_design[-1], curve)


def test_the_row_and_the_fold_are_the_same_background_at_one():
    _d, _s, _i, table, held = _state(vary_scale=False)
    _d2, _s2, _i2, table2, freed = _state(vary_scale=True)
    values = table.decode(table.x0())
    values2 = table2.decode(table2.x0())
    assert values2[SCALE_PATH] == 1.0
    assert np.allclose(held.background(values), freed.background(values2),
                       rtol=0, atol=1e-9)


def test_no_claim_about_what_moves_gives_the_curve_a_row():
    """``moving_paths=None`` gates nothing, and here the permissive branch is
    the row: a fold is a freeze, and freezing on an unasked question would hand
    a caller who had freed the scale a column that cannot move."""
    data, blank, structure, ins = synthetic_blank_case()
    ins = _with_blank(ins, blank, vary_scale=True)
    model = compile_model(structure, ins, data, mode="rietveld")
    assert model.bkg_paths[-1] == SCALE_PATH
    assert model.fixed_background is None


def test_a_double_counted_curve_asks_for_a_scale_the_parameter_may_not_hold():
    """The trap, built by hand because the code can no longer build it.

    With the curve carried twice the fit still has one right answer for the
    *pattern*: drive the refined scale to ``s_true − 1``.  Here that is −0.15,
    which ``min=0`` puts outside the parameter's range, so the fit cannot reach
    it and ends with its background too high.  That is the whole argument for
    ``min=0``: the wrong answer is loud rather than silent.
    """
    import dataclasses

    _d, _s, ins, table, model = _state(vary_scale=True)
    curve = np.asarray(model.bkg_design[-1])
    doubled = dataclasses.replace(model, fixed_background=curve)

    values = table.decode(table.x0())
    honest = model.background({**values, SCALE_PATH: S_TRUE})
    # the doubled model draws the same background, one scale lower — which is
    # the whole failure: the residual cannot tell the two apart
    lying = doubled.background({**values, SCALE_PATH: S_TRUE - 1.0})
    assert np.allclose(lying, honest, rtol=1e-12, atol=0)
    # and one scale lower is not a value the parameter may hold
    assert S_TRUE - 1.0 < ins.background.scale.min == 0.0


# ----------------------------------------------------------------------
# the column
# ----------------------------------------------------------------------
def test_the_scale_column_is_the_curve_itself():
    """Exact where the check is exact (CLAUDE.md § Invariants).

    The model is *linear* in this parameter, so its column is the sampled curve
    weighted, with no truncation term to tolerate. The oracle is that product,
    not another finite difference.
    """
    _d, _s, _i, table, model = _state(vary_scale=True)
    theta = table.x0()
    free = list(table.free_paths)
    c = free.index(SCALE_PATH)
    col = _make_jacobian(model, table)(theta)[:len(model.tt), c]

    truth = -(1.0 / model.sigma) * model.bkg_design[-1]
    assert np.max(np.abs(col - truth)) <= 1e-15 * np.max(np.abs(truth))


def test_a_physical_step_of_a_hundred_percent_reproduces_the_column():
    """The same exactness from the other side, and the reason the bar above can
    be that tight: in **physical** space a difference quotient of a linear model
    has no truncation error at any step, so a 100 % step is the sharpest oracle
    rather than the crudest (WP-1121).
    """
    _d, _s, _i, table, model = _state(vary_scale=True)
    values = table.decode(table.x0())
    base = model.background(values)
    stepped = dict(values)
    stepped[SCALE_PATH] = values[SCALE_PATH] + 1.0
    assert np.allclose(stepped[SCALE_PATH] - values[SCALE_PATH], 1.0)
    assert np.max(np.abs((model.background(stepped) - base)
                         - model.bkg_design[-1])) <= 1e-9


# ----------------------------------------------------------------------
# the weights
# ----------------------------------------------------------------------
def test_the_blank_s_counting_statistics_reach_the_weight():
    """σ² = σ_y² + s²σ_f², which is what makes a short blank honestly worse."""
    data, blank, structure, ins = synthetic_blank_case()
    with_esd = _with_blank(ins, blank, vary_scale=False)
    bare = _with_blank(ins, blank, vary_scale=False)
    bare.background.fixed_sigma = None

    m_bare = compile_model(structure, bare, data, mode="rietveld")
    m_esd = compile_model(structure, with_esd, data, mode="rietveld")
    sig_f = interpolate_fixed(np.asarray(m_esd.tt),
                              np.asarray(blank.two_theta),
                              np.asarray(blank.sigma))
    assert np.allclose(m_esd.sigma, np.sqrt(m_bare.sigma ** 2 + sig_f ** 2))
    assert np.all(m_esd.sigma > m_bare.sigma)


def test_a_noisier_blank_is_worth_less():
    """The point of the term: the same curve counted for a quarter of the time
    carries twice the σ, and the weights say so."""
    data, blank, structure, ins = synthetic_blank_case()
    short = blank.model_copy(deep=True)
    short.sigma = [2.0 * s for s in blank.sigma]
    m_long = compile_model(structure, _with_blank(ins, blank, vary_scale=False),
                           data, mode="rietveld")
    m_short = compile_model(structure, _with_blank(ins, short, vary_scale=False),
                            data, mode="rietveld")
    assert np.all(m_short.sigma > m_long.sigma)


def test_the_result_divides_by_the_weight_the_model_used():
    """WP-1029's rule with a second term in it: ``result.sigma`` is a lookup of
    ``model.sigma``, so adding the blank's variance must reach every renderer
    without any of them knowing about it."""
    data, blank, structure, ins = synthetic_blank_case()
    ins = _with_blank(ins, blank, vary_scale=False)
    # the declared stage's weights; the closing stage is tests/test_closing_stage.py's
    result = rx.refine(data, structure, ins, plan=_bkg_only_plan(closing_window_tol=None),
                       telemetry=False)
    model = compile_model(structure, ins, data, mode="rietveld")
    assert np.allclose(np.asarray(result.sigma), model.sigma)


def test_a_last_stage_that_moved_the_scale_reports_the_solves_weights():
    """#272's final compile rebuilds the model at the returned values, and a
    compile widens σ at the scale it sees — so without a rule the result would
    divide by σ at the *fitted* scale while its χ², esds and solve used σ at the
    scale the stage started from.  The rule: the solve's σ, and the reported
    Rwp is measured with it."""
    data, blank, structure, ins = synthetic_blank_case()
    ins = _with_blank(ins, blank, vary_scale=True)
    ref = rx.Refinement(structure, ins)
    # the declared last stage's weights; the closing stage is tests/test_closing_stage.py's
    result = ref.fit(data, plan=_bkg_only_plan(closing_window_tol=None), telemetry=False)
    assert abs(ref.fitted_instrument.background.scale.value - 1.0) > 0.05, \
        "the last stage must move the scale, or this pins nothing"

    at_start = compile_model(structure, ins, data, mode="rietveld")
    at_answer = compile_model(ref.fitted_structure, ref.fitted_instrument, data,
                              mode="rietveld")
    assert not np.allclose(at_answer.sigma, at_start.sigma), \
        "the two readings must differ for the choice to be visible"
    sigma = np.asarray(result.sigma)
    assert np.array_equal(sigma, at_start.sigma)

    diff = np.asarray(result.y_obs) - np.asarray(result.y_calc)
    w = 1.0 / sigma ** 2
    rwp = np.sqrt((w @ (diff * diff)) / (w @ np.asarray(result.y_obs) ** 2))
    assert result.statistics.rwp == pytest.approx(rwp, rel=1e-12)


# ----------------------------------------------------------------------
# the range
# ----------------------------------------------------------------------
def test_a_channel_the_curve_does_not_cover_is_refused():
    curve_tt = np.arange(10.0, 50.0, 0.01)
    curve_y = np.full_like(curve_tt, 100.0)
    with pytest.raises(ValueError, match="above its range"):
        interpolate_fixed(np.arange(10.0, 70.0, 0.02), curve_tt, curve_y)
    with pytest.raises(ValueError, match="below its range"):
        interpolate_fixed(np.arange(2.0, 40.0, 0.02), curve_tt, curve_y)
    with pytest.raises(ValueError, match="below and above"):
        interpolate_fixed(np.arange(2.0, 70.0, 0.02), curve_tt, curve_y)


def test_two_scans_of_one_range_still_agree():
    """The slack, and why it is not zero: a blank ending at 49.995° under a
    specimen ending at 49.996° is a grid offset rather than a gap."""
    curve_tt = np.arange(10.0, 50.0, 0.01)
    curve_y = np.full_like(curve_tt, 100.0)
    step = 0.01
    just_inside = np.array([10.0 - 0.9 * step, 49.99 + 0.9 * step])
    assert np.allclose(interpolate_fixed(just_inside, curve_tt, curve_y), 100.0)
    assert FIXED_RANGE_SLACK_STEPS == 1.0


def test_a_curve_with_no_range_is_refused_rather_than_carried_flat():
    """The range guard reads ``ft[0]`` and ``ft[-1]``, and a one-point curve has
    neither: ``np.interp`` would carry its single value across every fitted
    channel, which is the clamp the guard exists to refuse."""
    for n in (0, 1):
        with pytest.raises(ValueError, match="point"):
            interpolate_fixed(np.arange(10.0, 20.0, 0.1),
                              np.full(n, 12.0), np.full(n, 100.0))


def test_an_unsorted_curve_is_refused_because_its_ends_are_not_its_range():
    """Same rule from the other side.  ``np.interp`` requires an increasing
    abscissa; given a decreasing one it reads each channel off whichever
    neighbours bracket it in array order, and the two endpoints the guard
    compares against are not the curve's range at all."""
    curve_tt = np.arange(50.0, 10.0, -0.01)
    with pytest.raises(ValueError, match="decrease"):
        interpolate_fixed(np.arange(20.0, 30.0, 0.02), curve_tt,
                          np.full_like(curve_tt, 100.0))


def test_the_refusal_names_both_ranges():
    """A refusal a caller cannot act on is an assertion, so the message carries
    the two intervals and the two ways out."""
    curve_tt = np.arange(10.0, 50.0, 0.01)
    with pytest.raises(ValueError) as excinfo:
        interpolate_fixed(np.arange(10.0, 70.0, 0.02), curve_tt,
                          np.full_like(curve_tt, 100.0))
    message = str(excinfo.value)
    assert "10.0000-49.9900" in message and "10.0000-69.9800" in message
    assert "two_theta_max" in message


# ----------------------------------------------------------------------
# the fit
# ----------------------------------------------------------------------
def _bkg_only_plan(*, with_scale: bool = True, **plan) -> RefinementPlan:
    """One stage over the background block, with or without the curve's scale.

    ``instrument.background.*`` reaches the scale and ``…c*`` does not, which is
    what makes the two arms of the comparison below differ by exactly the
    parameter under test.  It is also the whole of this WP's behaviour change
    for an existing project: the shipped plans all free the wider glob.
    """
    free = ["phases.*.scale",
            "instrument.background.*" if with_scale else "instrument.background.c*"]
    return RefinementPlan(stages=[Stage("scale_bkg", free)], **plan)


@pytest.mark.xdist_group("measured-background")
def test_a_known_scale_comes_back_with_an_esd():
    """The headline, and the record field rather than Rwp is the evidence.

    The blank is one noisy measurement of a curve the specimen scan carries at
    0.85, so this asks the question the feature exists for: can the fit tell
    that the container scattered less into the specimen scan than into the
    blank?  It lands at 0.83 against the 1.0 the code could express before, six
    times closer, on a two-term base.

    The bar is 3 %, not the esd, and the gap between the two is the measurement
    below: the scale is biased *low* and the esd does not cover it.
    """
    data, blank, structure, ins = synthetic_blank_case()
    ins = _with_blank(ins, blank, vary_scale=True, n_terms=2)
    result = rx.refine(data, structure, ins, plan=_bkg_only_plan(),
                       telemetry=False)
    _plot(result, "measured_background_free_scale")

    scale = next(p for p in result.parameters if p.path == SCALE_PATH)
    assert scale.stderr is not None and scale.stderr > 0.0
    assert abs(scale.value - S_TRUE) <= 0.03
    assert abs(scale.value - S_TRUE) < abs(1.0 - S_TRUE) / 5.0


@pytest.mark.xdist_group("measured-background")
def test_a_flexible_polynomial_eats_the_scale_while_rwp_improves():
    """The identifiability warning of issue #171, measured rather than asserted.

    The polynomial and the curve are not orthogonal, so every term added to the
    base takes a bite out of the scale.  Measured on this fixture (2026-09-17,
    truth 0.85): 1 term 0.8378(42), 2 terms 0.8315(58), 3 terms 0.8057(91),
    4 terms 0.7130(154), 6 terms 0.6479(182) — and Rwp *falls* monotonically
    across that row, 0.07634 to 0.07299.  The scale is a measurement only
    against a low-order base, and Rwp cannot tell anybody which.

    Two ends of the row rather than five, because the claim is the direction and
    five fits is four more than it takes to show it.
    """
    data, blank, structure, ins = synthetic_blank_case()
    low = rx.refine(data, structure, _with_blank(ins, blank, vary_scale=True,
                                                 n_terms=1),
                    plan=_bkg_only_plan(), telemetry=False)
    high = rx.refine(data, structure, _with_blank(ins, blank, vary_scale=True,
                                                  n_terms=6),
                     plan=_bkg_only_plan(), telemetry=False)
    s_low = next(p for p in low.parameters if p.path == SCALE_PATH)
    s_high = next(p for p in high.parameters if p.path == SCALE_PATH)

    assert s_high.value < s_low.value < S_TRUE
    assert high.statistics.rwp < low.statistics.rwp
    assert any(d.code == "HIGH_CORRELATION" for d in high.diagnostics)


@pytest.mark.xdist_group("measured-background")
def test_the_scale_is_not_screened_against_the_block_it_belongs_to():
    """A defect this WP made and had to fix, and the sibling it shares.

    ``background_absorption`` selected its targets by suffix, and this path ends
    in ``.scale``.  A background parameter screened against the background block
    is a column projected onto a span containing it: R² = 1.00, exactly, on
    every fit that frees the scale, and ``BACKGROUND_ABSORPTION`` firing to say
    the background can reproduce the background.  ``extra_peak_absorption``
    carried a copy of the same line, so both are now one anchored function.
    """
    data, blank, structure, ins = synthetic_blank_case()
    ins = _with_blank(ins, blank, vary_scale=True, n_terms=2)
    result = rx.refine(data, structure, ins, plan=_bkg_only_plan(),
                       telemetry=False)
    screened = result.identifiability.background_absorption
    assert SCALE_PATH not in screened
    assert all(p.startswith("phases.") for p in screened)
    assert "phases.0.scale" in screened
    assert not any(d.code == "BACKGROUND_ABSORPTION" for d in result.diagnostics)


@pytest.mark.xdist_group("measured-background")
def test_freeing_the_scale_beats_holding_it_at_one():
    """Rwp is not the evidence for the *scale*, and it is the evidence for the
    claim that 1.0 is the wrong number to be stuck at."""
    data, blank, structure, ins = synthetic_blank_case()
    held = rx.refine(data, structure, _with_blank(ins, blank, vary_scale=False),
                     plan=_bkg_only_plan(with_scale=False), telemetry=False)
    freed = rx.refine(data, structure, _with_blank(ins, blank, vary_scale=True),
                      plan=_bkg_only_plan(), telemetry=False)
    _plot(held, "measured_background_held_scale")

    assert not any(p.path == SCALE_PATH for p in held.parameters)
    assert freed.statistics.rwp < held.statistics.rwp
    assert (held.statistics.n_free_parameters + 1
            == freed.statistics.n_free_parameters)


@pytest.mark.xdist_group("measured-background")
def test_a_preset_plan_frees_the_scale():
    """Recorded rather than asserted quietly: every preset frees
    ``instrument.background.*``, so a project that already held a fixed curve
    now refines one more parameter than it did before WP-1309.

    That is the same reach the P-spline's air term has always had, and it is
    what makes a measured background work under the shipped plans rather than
    only under a hand-written one.
    """
    stages = PLAN_PRESETS["mccusker_structural"]().stages
    globs = [g for stage in stages for g in stage.turn_on]
    assert "instrument.background.*" in globs

    _d, _s, _i, table, _m = _state(vary_scale=False)
    assert SCALE_PATH not in table.free_paths
    table.set_vary(["instrument.background.*"], True)
    assert SCALE_PATH in table.free_paths


@pytest.mark.xdist_group("measured-background")
def test_a_series_refines_one_scale_per_pattern_and_quotes_its_trajectory():
    """Issue #171, 2026-09-16: in a furnace run the blank is scanned cold and
    reused hot, so the scale is a per-pattern quantity.

    Nothing new was needed for that — a ``Parameter`` on the kind is per pattern
    because each pattern carries its own models, the warm start chains it like
    any other value, and ``SeriesResult.trajectory`` is generic over the paths a
    fit determined.  The test is here because "nothing was needed" is a claim
    about three mechanisms, and a trajectory that quietly lacked the scale would
    look exactly like a series where it never moved.
    """
    data, blank, structure, ins = synthetic_blank_case()
    hotter, _b2, _s2, _i2 = synthetic_blank_case(s_true=0.65, seed=9)
    ins = _with_blank(ins, blank, vary_scale=True, n_terms=2)

    series = rx.refine_sequential([data, hotter], structure, ins,
                                  x=[300.0, 500.0], plan=_bkg_only_plan(),
                                  telemetry=False)
    traj = series.trajectory(SCALE_PATH)
    assert SCALE_PATH in series.paths()
    assert len(traj.value) == 2
    assert traj.value[0] > traj.value[1]
    assert all(e is not None for e in traj.stderr)


@pytest.mark.xdist_group("measured-background")
def test_the_order_scan_chooses_for_the_remainder():
    """Trap 4: the scan had no notion of a declared curve, so it measured the
    curve's own shape as flexibility the polynomial needed.

    Measured here: blind it runs to 12 terms chasing the halo, and with the
    curve held at its true scale it selects 2 and gets worse with every term
    after — the curve is worth ten polynomial terms, which is the whole reason
    somebody measured a blank.
    """
    data, blank, structure, ins = synthetic_blank_case()
    held = _with_blank(ins, blank, vary_scale=False, scale=S_TRUE).background

    blind = select_chebyshev_order(data, max_order=12)
    informed = select_chebyshev_order(data, max_order=12, fixed=held)
    assert blind.selected == 12
    assert informed.selected == 2
    # and the scan is monotone upward after its minimum, which is what says the
    # remainder has no structure left for a polynomial to take
    bics = [s.bic for s in informed.scores]
    assert bics == sorted(bics)


def test_a_free_scale_costs_a_parameter_in_the_scan():
    """The scale is a fitted direction, so the BIC must be charged for it.

    Left out of k the scan would credit the fit with a degree of freedom it
    spent, which is the same double count trap 1 is about, one statistic over.
    """
    from rietx.background import peak_mask
    from rietx.background.models import chebyshev_design_matrix
    from rietx.background.select import _bic

    data, blank, structure, ins = synthetic_blank_case()
    freed = _with_blank(ins, blank, vary_scale=True).background
    scan = select_chebyshev_order(data, max_order=4, fixed=freed)

    mask = data.in_range_mask()
    tt, y, sigma = data.tt()[mask], data.y()[mask], data.sig()[mask]
    keep = peak_mask(tt, y, sigma)
    tt_m, y_m, s_m = tt[keep], y[keep], sigma[keep]
    m = len(tt_m)
    curve = interpolate_fixed(tt_m, np.asarray(freed.fixed_two_theta),
                              np.asarray(freed.fixed_intensity))
    n = int(scan.scores[0].complexity)
    rows = np.vstack([chebyshev_design_matrix(tt_m, n, float(tt[0]), float(tt[-1])),
                      curve[None, :]])
    w = 1.0 / s_m
    A = (rows * w).T
    coef, *_ = np.linalg.lstsq(A, y_m * w, rcond=None)
    r = y_m * w - A @ coef
    assert scan.scores[0].bic == pytest.approx(_bic(float(r @ r), m, n + 1))
    assert scan.scores[0].bic != pytest.approx(_bic(float(r @ r), m, n))


def test_a_stage_spec_reaches_the_scale_by_name():
    """The other direction: a caller who wants only the scale can say so."""
    _d, _s, _i, table, _m = _state(vary_scale=False)
    before = set(table.free_paths)
    spec = StageSpec(name="blank", turn_on=[SCALE_PATH])
    table.set_vary(list(spec.turn_on), True)
    assert set(table.free_paths) - before == {SCALE_PATH}

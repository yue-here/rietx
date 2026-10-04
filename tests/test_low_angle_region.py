"""Q3 — the region below the first Bragg reflection.

``LOW_ANGLE_UNMODELLED`` (``rietx.refine``) reads the fit's own residual over
``[two_theta_min, first_tick - 2*FWHM)`` — the channels no reflection, of any
phase, emission line or declared peak, can reach, ``first_tick`` being the
lowest tick with at least ``PHASE_SUPPORT_SIGMA`` of calculated intensity
behind it (WP-1458) — and fires when their mean weighted-squared
residual exceeds :data:`rietx.refine.LOW_ANGLE_UNMODELLED_RATIO` times the
whole-pattern reduced chi-square.  It exists beside
``PatternDiagnostics.air_scatter_gain`` (``background/diagnostics.py``) rather
than instead of it: that diagnostic is a nested cubic-vs-cubic+1/x test on the
background envelope over the *whole* fitted range, so a tail a few tens of
channels wide out of several hundred barely moves it (measured on
Ba2FeSbSe5 1.5 K, Maier, Gaultois et al. 2021, PRB 103, 054115: 0.019 against
the 0.3 trigger — the 19 tail channels out of 779 carry 0.3% of the
whole-range RSS the nested fit compares).  This diagnostic reads the fit's own
residual instead, and only over the region where "no reflection explains it"
is true by construction.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.refine import (
    LOW_ANGLE_MIN_CHANNELS,
    LOW_ANGLE_UNMODELLED_RATIO,
    _first_reflection_fwhm,
    _low_angle_diagnostics,
)
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.pattern import PatternData
from tests.test_schemas import make_lab6

WAVELENGTH = 1.5405929  # CuKa1


def _lab6_air_scatter_pattern(*, lo: float, hi: float = 90.0, step: float = 0.02,
                              seed: int = 11) -> PatternData:
    """LaB6, CuKa1 only, on a true background carrying a steep 1/(2theta)
    tail — the same functional form ``test_background_auto._air_scatter_bkg``
    uses, scaled up so a plain Chebyshev cannot absorb it over a range that
    starts this close to zero (the mechanism ``air_scatter_gain`` is blind to
    at a *narrow* tail is exactly a strong, narrow one — see the module
    docstring). LaB6's first CuKa1 reflection sits at ~21.3 deg (a = 4.1566
    Ang, (100)), comfortably above the brief's 12 deg floor.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.bragg_brentano(radiation="CuKa1")
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    tt = np.arange(lo, hi, step)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    true_bkg = 40.0 + 90000.0 / model.tt
    y = model.evaluate(table.decode(table.x0())) + true_bkg
    rng = np.random.default_rng(seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0))
                       .astype(float).tolist())


def _fit_plain_chebyshev(pattern: PatternData, *, n_terms: int = 6):
    structure = make_lab6()
    ins = rx.Instrument.bragg_brentano(radiation="CuKa1")
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=0.0) for _ in range(n_terms)])
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("profile", ["phases.*.scale", "instrument.background.c*",
                             "instrument.profile.w", "instrument.profile.x",
                             "instrument.zero_shift", "phases.*.cell.*"]),
    ])
    ref = rx.Refinement(structure, ins, history=False)
    return ref.fit(pattern, plan=plan)


# --------------------------------------------------------------------------
# the threshold constants
# --------------------------------------------------------------------------
def test_thresholds_are_the_registered_constants():
    """The threshold and its channel floor are named module constants next to
    ``STEPS_PER_FWHM_MIN``/``OBS_PER_PARAMETER_MIN`` (``rietx.refine``) — a
    Layer-0 ``Diagnostic`` threshold, the same tier ``PATTERN_UNDERSAMPLED``
    sits at, which never bumped ``report.schemas.THRESHOLDS_VERSION`` either:
    that registry versions the FitReport Layer-2 gates/vocabulary contract,
    which a raw ``RefinementResult.diagnostics`` code does not touch.
    """
    assert LOW_ANGLE_UNMODELLED_RATIO == 3.0
    assert LOW_ANGLE_MIN_CHANNELS == 10


# --------------------------------------------------------------------------
# fires / silent
# --------------------------------------------------------------------------
def test_1x_tail_below_the_first_reflection_fires():
    """A steep 1/(2theta) tail from 4 deg, no reflection below 21 deg, fit
    with a plain Chebyshev background: ``LOW_ANGLE_UNMODELLED`` fires."""
    pattern = _lab6_air_scatter_pattern(lo=4.0)
    result = _fit_plain_chebyshev(pattern)
    found = [d for d in result.diagnostics if d.code == "LOW_ANGLE_UNMODELLED"]
    assert found, [d.code for d in result.diagnostics]
    d = found[0]
    assert d.level == "warning"
    assert d.value is not None and d.value > LOW_ANGLE_UNMODELLED_RATIO
    assert "raise" in d.suggestion and "air-scatter" in d.suggestion


def test_same_pattern_with_the_tail_excluded_is_silent():
    """Excluding the tail channels (4-12 deg) leaves nothing below the first
    reflection for the diagnostic to measure a level from."""
    pattern = _lab6_air_scatter_pattern(lo=4.0).model_copy(
        update={"excluded_regions": [(4.0, 12.0)]})
    result = _fit_plain_chebyshev(pattern)
    assert "LOW_ANGLE_UNMODELLED" not in {d.code for d in result.diagnostics}


def test_first_reflection_at_the_low_edge_is_silent():
    """Starting the pattern within 2 FWHM of the first reflection leaves no
    region at all — silent by channel count, not by a level that happens to
    be low."""
    pattern = _lab6_air_scatter_pattern(lo=21.2, hi=40.0)
    result = _fit_plain_chebyshev(pattern)
    assert "LOW_ANGLE_UNMODELLED" not in {d.code for d in result.diagnostics}


# --------------------------------------------------------------------------
# already-bundled non-magnetic fixtures stay silent
# --------------------------------------------------------------------------
def test_silent_on_the_flat_background_fixture():
    """``test_background_auto._peaky_pattern`` with a flat true background —
    no tail, nothing below the first reflection to flag."""
    from tests.test_background_auto import _flat_bkg, _peaky_pattern

    result = _fit_plain_chebyshev(
        _peaky_pattern(background=_flat_bkg, lo=15.0, hi=110.0, step=0.02))
    assert "LOW_ANGLE_UNMODELLED" not in {d.code for d in result.diagnostics}


def test_silent_on_the_lab6_data_support_fixture():
    """``test_data_support._sampled`` — the well-sampled LaB6 synthetic
    already exercised for ``PATTERN_UNDERSAMPLED``; no low-angle tail was
    built into it, so this diagnostic must stay quiet on it too."""
    from tests.test_data_support import _lab6, _sampled

    pattern = _sampled(0.002, 4.0e-3)
    structure, instrument = _lab6()
    result = rx.Refinement(structure, instrument, history=False).fit(
        pattern, plan="mccusker_default")
    assert "LOW_ANGLE_UNMODELLED" not in {d.code for d in result.diagnostics}


# --------------------------------------------------------------------------
# the region boundary itself
# --------------------------------------------------------------------------
def test_first_reflection_fwhm_reads_the_lowest_tick_across_phases():
    """``_first_reflection_fwhm`` returns the global minimum tick position and
    an instrumental FWHM there, agreeing with ``model.peak_fwhm`` on the same
    reflection computed the ordinary way (``model.phase_peaks``)."""
    structure = make_lab6()
    ins = rx.Instrument.bragg_brentano(radiation="CuKa1")
    tt = np.arange(15.0, 90.0, 0.02)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    ticks = {"LaB6": sorted(float(p) for lam in model.line_wavelengths
                            for p in model.phases[0].reflections.two_theta(
                                tuple(values[f"phases.0.cell.{k}"] for k in
                                     ("a", "b", "c", "alpha", "beta", "gamma")),
                                lam) + values["instrument.zero_shift"]
                            if np.isfinite(p))}
    got = _first_reflection_fwhm(model, values, ticks)
    assert got is not None
    first_tick, fwhm = got
    assert first_tick == pytest.approx(min(ticks["LaB6"]))
    assert fwhm > 0.0

    pos, w1, w2, _ = model.phase_peaks(0, values)[0]
    i = int(np.argmin(np.where(np.isfinite(pos), pos, np.inf)))
    expected_fwhm = float(np.asarray(model.peak_fwhm(w1, w2))[i])
    # instrument-only FWHM (no sample size/strain, both zero on this
    # structure) is the same number ``phase_peaks`` reports for this
    # reflection, since LaB6 here carries no size/strain terms of its own
    assert fwhm == pytest.approx(expected_fwhm, rel=1e-6)


def test_no_reflections_returns_none():
    """A model with no phases at all (Pawley-style empty structure list is not
    constructible here, so this checks the empty-ticks branch directly) —
    ``_first_reflection_fwhm`` must not raise on an empty tick dict."""
    structure = make_lab6()
    ins = rx.Instrument.bragg_brentano(radiation="CuKa1")
    tt = np.arange(15.0, 90.0, 0.02)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    assert _first_reflection_fwhm(model, values, {}) is None
    assert _low_angle_diagnostics(model, values, model.y_obs, None, {}) == []


# --------------------------------------------------------------------------
# the boundary is the first tick with intensity behind it (WP-1458, #436)
# --------------------------------------------------------------------------
def _hump_pattern() -> PatternData:
    """Issue #436's pattern: the synthetic LaB6 of ``test_refine_synthetic``
    (lambda 0.4139 Ang, 3-24 deg, first reflection (100) at 5.72 deg) plus an
    unmodelled Gaussian hump at 4.0 deg (400 counts, sigma 0.3 deg)."""
    from tests.test_refine_synthetic import synthesize

    pat = synthesize()
    tt = np.asarray(pat.two_theta)
    y = np.asarray(pat.intensity, float)
    y += 400.0 * np.exp(-0.5 * ((tt - 4.0) / 0.3) ** 2)
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist())


@pytest.fixture(scope="module")
def hump_pattern() -> PatternData:
    return _hump_pattern()


def _dummy(scale: Parameter) -> rx.Phase:
    """A large-cell cubic phase whose lowest ticks (2.51 deg on) fall below
    LaB6 (100) and below the data's 3 deg start."""
    from rietx.schemas.structure import Atom, Cell

    return rx.Phase(
        name="dummy", space_group="P m -3 m", cell=Cell.cubic(30.0, vary=False),
        atoms=[Atom(label="C", species="C", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))],
        scale=scale)


def _low_angle(structure, instrument, pattern):
    result = rx.Refinement(structure, instrument, history=False).fit(
        pattern, plan="mccusker_default", telemetry=False)
    return result, [d for d in result.diagnostics
                    if d.code == "LOW_ANGLE_UNMODELLED"]


def _assert_fires_at_lab6_100(found):
    """The region the LaB6-only fit reads: below (100) at 5.72 deg."""
    assert len(found) == 1
    assert "(5.72° − 2×FWHM = 5.68°)" in found[0].message
    assert found[0].value > LOW_ANGLE_UNMODELLED_RATIO


def test_the_issue_pair_fires_with_and_without_the_dummy(hump_pattern):
    """#436: a cubic dummy at a fixed 1e-14 scale leaves the fit unchanged and
    put its 2.51 deg tick below the data, silencing the diagnostic.  None of
    its reflections reaches 1 sigma, so the boundary stays at LaB6 (100)."""
    from tests.test_refine_synthetic import perturbed_models

    structure, instrument = perturbed_models()
    alone, found = _low_angle(structure, instrument, hump_pattern)
    _assert_fires_at_lab6_100(found)

    structure, instrument = perturbed_models()
    structure.phases.append(_dummy(Parameter(value=1e-14, vary=False)))
    result, found = _low_angle(structure, instrument, hump_pattern)
    assert min(result.ticks["dummy"]) < hump_pattern.two_theta[0]
    assert result.statistics.rwp == pytest.approx(alone.statistics.rwp, rel=1e-3)
    _assert_fires_at_lab6_100(found)


def test_a_held_phase_does_not_silence_it(hump_pattern):
    """A phase ``PHASE_UNCONSTRAINED`` holds keeps its ticks (WP-1301); with
    nothing behind them they do not move the boundary."""
    from tests.test_refine_synthetic import perturbed_models

    structure, instrument = perturbed_models()
    structure.phases.append(_dummy(Parameter(value=1e-14, min=0.0, max=1e-10)))
    result, found = _low_angle(structure, instrument, hump_pattern)
    assert "PHASE_UNCONSTRAINED" in {d.code for d in result.diagnostics}
    _assert_fires_at_lab6_100(found)


def test_a_zero_area_declared_peak_does_not_silence_it(hump_pattern):
    """A declared ``PeakComponent`` at 3.3 deg, area at its default 0: its
    ticks sit under ``EXTRA_TICK_KEY`` and carry nothing."""
    from rietx.model.components import EXTRA_TICK_KEY
    from rietx.schemas.instrument import PeakComponent
    from tests.test_refine_synthetic import perturbed_models

    structure, instrument = perturbed_models()
    instrument.extra_components = [PeakComponent(
        center=Parameter(value=3.3, min=3.1, max=3.5, unit="deg"),
        fwhm=Parameter(value=0.05, min=0.01, max=0.2, unit="deg"))]
    result, found = _low_angle(structure, instrument, hump_pattern)
    assert min(result.ticks[EXTRA_TICK_KEY]) < 3.5
    _assert_fires_at_lab6_100(found)


def test_empty_ticks_of_a_supported_phase_do_not_silence_it(hump_pattern):
    """The row #433's magnetic phase adds, stood in for without magnetism: LaB6
    described in a doubled cell, whose half-order reflections (2.85, 4.04,
    4.94 deg) are ticks with |F| = 0 on a phase the data plainly supports —
    the case no per-phase test can see."""
    from rietx.schemas.structure import Atom, Cell
    from tests.test_refine_synthetic import TRUE_A, TRUE_SCALE, perturbed_models

    structure, instrument = perturbed_models()
    atoms = [Atom(label=f"La{i}", species="La", x=Parameter(value=x),
                  y=Parameter(value=y), z=Parameter(value=z))
             for i, (x, y, z) in enumerate([(0, 0, 0), (.5, 0, 0),
                                            (.5, .5, 0), (.5, .5, .5)])]
    atoms += [Atom(label=f"B{i}", species="B", x=Parameter(value=x0 + 0.1993 / 2),
                   y=Parameter(value=.25), z=Parameter(value=.25))
              for i, x0 in enumerate((0.0, 0.5))]
    structure.phases[0] = rx.Phase(
        name="LaB6x2", space_group="P m -3 m",
        cell=Cell.cubic(2 * (TRUE_A + 0.004), vary=True), atoms=atoms,
        scale=Parameter(value=TRUE_SCALE * 1.8 / 64))
    result, found = _low_angle(structure, instrument, hump_pattern)
    assert min(result.ticks["LaB6x2"]) < 3.0
    _assert_fires_at_lab6_100(found)


def test_reflection_support_is_phase_support_one_rank_down():
    """Per-reflection support is ‖y/σ‖₂ over one window (WP-1523): never above
    the phase's norm over the whole range, since every contribution is
    non-negative.  (Under the strongest-point test it equalled the phase's on
    LaB6, whose strongest reflection stands alone; a norm sums every line.)
    A reflection with an empty frozen window reads 0."""
    from rietx.model.forward import PHASE_SUPPORT_SIGMA

    pattern = _lab6_air_scatter_pattern(lo=15.0, hi=60.0)
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.bragg_brentano(radiation="CuKa1")
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    rows = model.reflection_support(0, values)
    best = max(float(np.max(r)) for r in rows)
    assert 0.0 < best <= float(model.phase_support(values)[0])
    empty = model.phases[0].win[0, :, 1] <= model.phases[0].win[0, :, 0]
    assert np.all(rows[0][empty] == 0.0)
    assert (rows[0][~empty] >= PHASE_SUPPORT_SIGMA).any()


def test_first_reflection_skips_ticks_without_support():
    """``support`` pairs with ``ticks`` by index; a tick below the threshold
    is not the first reflection, and a row with none supported is no row."""
    structure = make_lab6()
    ins = rx.Instrument.bragg_brentano(radiation="CuKa1")
    tt = np.arange(15.0, 90.0, 0.02)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    ticks = {"LaB6": [21.36, 30.4], "ghost": [16.0]}
    got = _first_reflection_fwhm(model, values, ticks,
                                 {"LaB6": [50.0, 80.0], "ghost": [0.99]})
    assert got is not None and got[0] == 21.36
    got = _first_reflection_fwhm(model, values, ticks,
                                 {"LaB6": [0.5, 80.0], "ghost": [0.99]})
    assert got is not None and got[0] == 30.4
    assert _first_reflection_fwhm(model, values, ticks,
                                  {"LaB6": [0.0, 0.0], "ghost": [0.0]}) is None
    assert _first_reflection_fwhm(model, values, ticks)[0] == 16.0


def test_extra_peak_support_pairs_with_the_tick_positions():
    """``extra_peak_support`` lists the images ``extra_peak_tick_positions``
    does, in the same order, each naming its peak; a zero area reads 0 and a
    real one reads its height in sigma."""
    from rietx.schemas.instrument import PeakComponent

    structure = make_lab6()
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.extra_components = [
        PeakComponent(center=Parameter(value=18.0, min=17.5, max=18.5, unit="deg")),
        PeakComponent(center=Parameter(value=25.0, min=24.5, max=25.5, unit="deg"),
                      area=Parameter(value=50.0, min=0.0, transform="softplus"))]
    tt = np.arange(15.0, 40.0, 0.02)
    grid = PatternData(two_theta=tt.tolist(), intensity=[100.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    images = model.extra_peak_support(values)
    assert [p for p, _, _ in images] == model.extra_peak_tick_positions(values)
    assert {j for _, j, _ in images} == {0, 1}
    assert all(s == 0.0 for _, j, s in images if j == 0)
    assert max(s for _, j, s in images if j == 1) > 1.0

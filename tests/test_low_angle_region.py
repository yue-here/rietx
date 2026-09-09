"""Q3 — the region below the first Bragg reflection.

``LOW_ANGLE_UNMODELLED`` (``rietx.refine``) reads the fit's own residual over
``[two_theta_min, first_tick - 2*FWHM)`` — the channels no reflection, of any
phase or emission line, can reach — and fires when their mean weighted-squared
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

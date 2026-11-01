"""WP-1977: a residual lobe on the flank of a drawn peak is not an unindexed line.

Layer 0 lists a positive residual peak as ``unmatched_obs`` only when no peak
the model draws explains it.  A tick within ``LAYER0_MATCH_TOL_DEG`` explains
one, as before.  Since WP-1977 so does the observed flank of a drawn peak, when
the observed curve rises into that peak with no resolved valley
(:func:`rietx.report.layer0.on_drawn_flank`).  The drawn curve is ``y_calc``
whole, so a line of a measured blank counts (#1217).

The cases: the unit behaviour on hand-built curves; the asymmetry lobes of
#1106, rebuilt on the synthetic LaB₆ truth with the model's apertures at 0; an
unmodelled second phase, whose isolated lines must still be listed; and an
under-scaled blank, whose line must not be.
"""

import numpy as np
import pytest

import rietx as rx
from rietx.report.layer0 import (
    LAYER0_MATCH_TOL_DEG,
    on_drawn_flank,
    residual_peak_indices,
)
from rietx.report.layer2 import IMPURITY_SIGMA
from tests.test_fitreport_layers import _plot_state, _report_for, _result_for, _truth

K = 5.0   # the report's detection level, ``build_report(min_peak_sigma=)``


def _gauss(x, centre, fwhm):
    return np.exp(-4.0 * np.log(2.0) * ((x - centre) / fwhm) ** 2)


@pytest.fixture
def drawn():
    """One drawn peak at 5.0 (FWHM 0.1, height 1000) on a flat 50."""
    x = np.arange(0.0, 10.0, 0.01)
    y_calc = 50.0 + 1000.0 * _gauss(x, 5.0, 0.1)
    return x, y_calc, np.sqrt(y_calc)


def test_a_lobe_on_the_flank_is_explained(drawn):
    """1.5 FWHM below the apex, the observed curve still rises into the peak."""
    x, y_calc, sigma = drawn
    y_obs = y_calc + 40.0 * _gauss(x, 4.85, 0.1)
    i = int(np.argmin(np.abs(x - 4.85)))
    assert on_drawn_flank(y_obs, y_calc, sigma, i, min_sigma=K)


def test_a_resolved_line_beside_the_peak_is_not(drawn):
    """5 FWHM away the observed curve falls to background between the two."""
    x, y_calc, sigma = drawn
    y_obs = y_calc + 300.0 * _gauss(x, 4.5, 0.1)
    i = int(np.argmin(np.abs(x - 4.5)))
    assert not on_drawn_flank(y_obs, y_calc, sigma, i, min_sigma=K)


def test_a_line_resolved_on_a_strong_tail_is_not():
    """A Lorentzian tail keeps the drawn curve high far from its apex.  A line
    standing on that tail with its own valley is still a line of its own."""
    x = np.arange(0.0, 10.0, 0.01)
    lor = 1.0 / (1.0 + (2.0 * (x - 5.0) / 0.1) ** 2)
    y_calc = 50.0 + 1e5 * lor
    sigma = np.sqrt(y_calc)
    y_obs = y_calc + 400.0 * _gauss(x, 4.4, 0.08)
    i = int(np.argmin(np.abs(x - 4.4)))
    assert on_drawn_flank(y_calc, y_calc, sigma, i, min_sigma=K)  # the tail alone
    assert not on_drawn_flank(y_obs, y_calc, sigma, i, min_sigma=K)


def test_a_peak_the_noise_hides_explains_nothing():
    """A drawn peak below the detection level is no apex to belong to."""
    x = np.arange(0.0, 10.0, 0.01)
    y_calc = 50.0 + 10.0 * _gauss(x, 5.0, 0.1)
    sigma = np.sqrt(y_calc)
    y_obs = y_calc + 40.0 * _gauss(x, 4.9, 0.1)
    i = int(np.argmin(np.abs(x - 4.9)))
    assert not on_drawn_flank(y_obs, y_calc, sigma, i, min_sigma=K)


def test_the_pattern_edge_is_no_apex():
    """A background rising to the first channel is not a peak."""
    x = np.arange(5.0, 15.0, 0.01)
    y_calc = 50.0 + 500.0 * np.exp(-(x - 5.0))
    sigma = np.sqrt(y_calc)
    y_obs = y_calc + 60.0 * _gauss(x, 5.3, 0.1)
    i = int(np.argmin(np.abs(x - 5.3)))
    assert not on_drawn_flank(y_obs, y_calc, sigma, i, min_sigma=K)


def _window_only(result):
    """The residual peaks the 0.08° window alone would list (the pre-1977 rule)."""
    tt = np.asarray(result.two_theta)
    resid = (np.asarray(result.y_obs) - np.asarray(result.y_calc)) / result.sig()
    ticks = np.concatenate([np.asarray(v) for v in result.ticks.values()])
    return [(float(tt[i]), float(resid[i]))
            for i in residual_peak_indices(resid, min_peak_sigma=K)
            if np.min(np.abs(ticks - tt[i])) > LAYER0_MATCH_TOL_DEG]


def _obs(report):
    return [u for u in report.unmatched if u.kind == "unmatched_obs"]


def test_asymmetry_lobes_with_the_apertures_at_zero_are_explained():
    """#1106's signature: the data carry axial divergence (S/L = H/L = 0.03),
    the model declares none.  The lines leave lobes on their flanks outside
    the 0.08° window (here at 116-121°, up to 11.5σ), and before WP-1977 each
    read as an unindexed line.  Now none does, and no impurity phase is
    suggested.  The real-data case, SRM 660c fitted with the apertures at 0,
    is measured in WP-1977's Task 4 (11 rows to 0); WP-2054 owns its test."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure, ins, data = _truth()
    asym = ins.model_copy(deep=True)
    asym.geometry.axial_sl.value = asym.geometry.axial_hl.value = 0.03
    table = ParameterTable(structure, asym)
    y = compile_model(structure, asym, data, mode="rietveld").evaluate(
        table.decode(table.x0()))
    rng = np.random.default_rng(17)
    counts = 60.0   # the truth's own count scale
    data = rx.PatternData(
        two_theta=data.two_theta,
        intensity=(rng.poisson(np.maximum(y, 1.0) * counts) / counts).tolist(),
        sigma=np.sqrt(np.maximum(y, 1.0) / counts).tolist())
    flat = ins.model_copy(deep=True)
    flat.geometry.axial_sl.value = flat.geometry.axial_hl.value = 0.0

    result, _, _ = _result_for(structure, flat, data)
    lobes = _window_only(result)
    assert [t for t, s in lobes if s > IMPURITY_SIGMA], lobes
    report = _report_for(structure, flat, data)
    assert _obs(report) == [], _obs(report)
    assert "add_impurity_phase" not in [a.kind for a in report.suggested_actions]
    _plot_state(structure, flat, data, "wp1977_axial_lobes")


def _si() -> rx.Phase:
    return rx.Phase(
        name="Si", space_group="F d -3 m", cell=rx.Cell.cubic(5.4309),
        atoms=[rx.Atom(label="Si", species="Si", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                       biso=rx.Parameter(value=0.5))],
        scale=rx.Parameter(value=2e-4, min=0.0))


def test_an_unmodelled_phase_still_reads_as_unmatched():
    """The guard on the other side: silicon in the data, LaB₆ alone in the
    model.  Every silicon line that stands clear of LaB₆ (no LaB₆ tick within
    0.5°) and reaches the impurity level is listed, and the impurity call is
    made.  A silicon line on a LaB₆ flank that the data do not resolve is
    explained, which no positions test could avoid."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure, ins, data = _truth()
    both = rx.Structure(phases=[structure.phases[0], _si()])
    model = compile_model(both, ins, data, mode="rietveld")
    y = model.evaluate(ParameterTable(both, ins).decode(ParameterTable(both, ins).x0()))
    rng = np.random.default_rng(23)
    doped = rx.PatternData(two_theta=data.two_theta,
                           intensity=rng.poisson(np.maximum(y, 1.0)).tolist(),
                           sigma=np.sqrt(np.maximum(y, 1.0)).tolist())

    result, _, _ = _result_for(structure, ins, doped)
    tt = np.asarray(result.two_theta)
    resid = (np.asarray(result.y_obs) - np.asarray(result.y_calc)) / result.sig()
    lab6 = np.asarray(result.ticks["LaB6"])
    si = np.asarray(sorted(model.phases[1].reflections.two_theta(
        (5.4309, 5.4309, 5.4309, 90.0, 90.0, 90.0), model.line_wavelengths[0])))
    clear = [p for p in si if np.isfinite(p) and np.min(np.abs(lab6 - p)) > 0.5
             and resid[np.argmin(np.abs(tt - p))] > IMPURITY_SIGMA]
    assert len(clear) >= 4, clear

    report = _report_for(structure, ins, doped)
    listed = np.asarray([u.two_theta for u in _obs(report)])
    missing = [p for p in clear
               if not len(listed) or np.min(np.abs(listed - p)) > LAYER0_MATCH_TOL_DEG]
    assert missing == [], (missing, listed)
    assert "add_impurity_phase" in [a.kind for a in report.suggested_actions]
    _plot_state(structure, ins, doped, "wp1977_unmodelled_si")


def _blank(tt, lines):
    y = 40.0 + 0.0 * tt
    for centre in lines:
        y = y + 3000.0 * _gauss(tt, centre, 0.1)
    return y


@pytest.mark.parametrize("model_lines, listed", [
    ((42.1, 65.0), False),   # the blank the model holds has the line: explained
    ((65.0,), True),         # it has not: the line is the specimen's, listed
])
def test_a_line_of_an_under_scaled_blank_is_explained(model_lines, listed):
    """#1217: a measured blank declared as a fixed background, refined low
    (here 0.45 against a truth of 0.60, the regression dilution WP-1309
    measured).  What is left of the blank's own line at 42.1° lies on a line
    the model draws, so it is not an unindexed line.  The control removes that
    line from the blank the model holds, and the same residual is listed."""
    from rietx.schemas.instrument import BackgroundFixedPlusChebyshev

    structure, ins, data = _truth()
    tt = np.asarray(data.two_theta)
    rng = np.random.default_rng(31)
    clean = np.asarray(_result_for(structure, ins, data)[0].y_calc)
    y = clean + 0.60 * _blank(tt, (42.1, 65.0))
    doped = rx.PatternData(two_theta=data.two_theta,
                           intensity=rng.poisson(y).tolist(),
                           sigma=np.sqrt(y).tolist())
    held = ins.model_copy(deep=True)
    blank = rx.PatternData(two_theta=data.two_theta,
                           intensity=_blank(tt, model_lines).tolist())
    held.background = BackgroundFixedPlusChebyshev.from_pattern(
        blank, n_terms=3, scale=0.45)
    held.background.chebyshev.coefficients[0].value = 80.0   # the truth's flat term

    result, _, _ = _result_for(structure, held, doped)
    assert [t for t, s in _window_only(result) if abs(t - 42.1) < 0.1]
    report = _report_for(structure, held, doped)
    near = [u for u in _obs(report) if abs(u.two_theta - 42.1) < 0.1]
    assert bool(near) is listed, _obs(report)
    _plot_state(structure, held, doped, f"wp1977_blank_line_{len(model_lines)}")

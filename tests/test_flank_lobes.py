"""WP-1977: a residual peak on the flank of a drawn peak carries that evidence.

Layer 0 lists a positive residual peak as ``unmatched_obs`` when no tick lies
within ``LAYER0_MATCH_TOL_DEG``, as before.  Since WP-1977 each such row also
says whether the observed curve rises from it into a peak the model draws with
no resolved valley (:func:`rietx.report.layer0.on_drawn_flank`), and against
which peak (``UnmatchedPeak.flank``).  The data do not decide such a shoulder:
a shape misfit, an unmodelled Kα2, a lower-symmetry split and a foreign line
all leave one.  So the row stays listed and Layer 2 names no single cause for
it.  The drawn curve is ``y_calc`` whole, so a line of a measured blank counts
(#1217).

The cases: the unit behaviour on hand-built curves; the asymmetry lobes of
#1106, rebuilt on the synthetic LaB₆ truth with the model's apertures at 0; an
unmodelled second phase, whose isolated lines keep the impurity call; a
tetragonal specimen modelled cubic, whose split lines keep the re-index
pointer; and an under-scaled blank.
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


def test_a_lobe_on_the_flank_is_unresolved(drawn):
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


def test_a_peak_the_noise_hides_is_no_apex():
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
    """The residual peaks the 0.08° window lists, as ``(2θ, height in σ)``."""
    tt = np.asarray(result.two_theta)
    resid = (np.asarray(result.y_obs) - np.asarray(result.y_calc)) / result.sig()
    ticks = np.concatenate([np.asarray(v) for v in result.ticks.values()])
    return [(float(tt[i]), float(resid[i]))
            for i in residual_peak_indices(resid, min_peak_sigma=K)
            if np.min(np.abs(ticks - tt[i])) > LAYER0_MATCH_TOL_DEG]


def _obs(report):
    return [u for u in report.unmatched if u.kind == "unmatched_obs"]


def _every_row_measured(report):
    """The writer of ``UnmatchedPeak.flank`` is ``build_layer0``, one per
    ``unmatched_obs`` row; an ``unmatched_calc`` row is not measured."""
    for u in report.unmatched:
        assert (u.flank is not None) is (u.kind == "unmatched_obs"), u
        f = u.flank
        if f is None:
            continue
        drawn = f.peak_two_theta is not None
        assert drawn or not f.on_flank, f
        assert (f.offset_fwhm is not None) is drawn, f
        if f.on_flank:
            assert 1 <= f.lines_with_lobe <= f.lines_as_strong, f
        else:
            assert f.lines_as_strong is None and f.lines_with_lobe is None, f


def _active(report, kind):
    return [a for a in report.suggested_actions if a.kind == kind and a.active]


def test_asymmetry_lobes_with_the_apertures_at_zero_carry_their_peak():
    """#1106's signature: the data carry axial divergence (S/L = H/L = 0.03),
    the model declares none.  The lines leave lobes on their flanks outside
    the 0.08° window (here at 116-121°, up to 11.5σ).  Before WP-1977 each
    read as an unindexed line and bought ``add_impurity_phase``.  Now each is
    still listed, names the drawn peak it sits unresolved on, and buys no
    impurity call.  The real-data case, SRM 660c fitted with the apertures at
    0, is measured in WP-1977's handover; WP-2054 owns its test."""
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
    lobes = [t for t, s in _window_only(result) if s > IMPURITY_SIGMA]
    assert lobes, _window_only(result)
    report = _report_for(structure, flat, data)
    _every_row_measured(report)
    rows = {round(u.two_theta, 4): u for u in _obs(report)}
    for t in lobes:
        u = rows[round(t, 4)]
        assert u.flank.on_flank, u
        assert abs(u.two_theta - u.flank.peak_two_theta) < 0.5, u
    assert _active(report, "add_impurity_phase") == []
    _plot_state(structure, flat, data, "wp1977_axial_lobes")


def test_a_lone_shoulder_counts_one_lobe():
    """A foreign line 1 FWHM below the third-strongest LaB₆ line, at 15 % of
    its height: the data do not resolve it, so the row is on the flank, and
    no other line as strong carries a lobe on that side.  The asymmetry case
    above counts 1 of 14 too, its other lobes being under the detection level
    (measured), so the count can say "most lines" and cannot say "one line
    only"; the help entry says so."""
    from scipy.signal import find_peaks, peak_widths

    structure, ins, data = _truth()
    clean = _result_for(structure, ins, data)[0]
    tt = np.asarray(clean.two_theta)
    yc = np.asarray(clean.y_calc)
    apex, props = find_peaks(yc, prominence=1.0)
    j = np.argsort(props["prominences"])[::-1][2]
    fwhm = peak_widths(yc, apex[[j]], rel_height=0.5)[0][0] * (tt[1] - tt[0])
    centre = tt[apex[j]] - fwhm
    y = np.asarray(data.intensity) + 0.15 * props["prominences"][j] * _gauss(
        tt, centre, fwhm)
    doped = rx.PatternData(two_theta=data.two_theta, intensity=y.tolist(),
                           sigma=data.sigma)

    report = _report_for(structure, ins, doped)
    _every_row_measured(report)
    (u,) = [u for u in _obs(report) if abs(u.two_theta - centre) < fwhm / 2]
    assert u.flank.on_flank, u
    assert -1.5 < u.flank.offset_fwhm < -0.5, u
    assert (u.flank.lines_with_lobe, u.flank.lines_as_strong) == (1, 3), u
    assert _active(report, "add_impurity_phase") == []


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
    0.5°) and reaches the impurity level is listed, the data resolve it from
    every drawn peak, and the impurity call is made."""
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
    _every_row_measured(report)
    rows = _obs(report)
    for p in clear:
        near = [u for u in rows if abs(u.two_theta - p) <= LAYER0_MATCH_TOL_DEG]
        assert near and not any(u.flank.on_flank for u in near), (p, near)
    assert _active(report, "add_impurity_phase")
    _plot_state(structure, ins, doped, "wp1977_unmodelled_si")


def test_a_lower_symmetry_split_keeps_the_reindex_pointer():
    """The case WP-1977's generality review named: a tetragonal specimen
    (c/a = 1.004) modelled cubic.  Each line with an l component splits.  At
    low angle the data do not resolve the split, and the row says so; higher
    up they do.  Before WP-1977 this fit got ``reindex_or_recheck_cell`` at
    0.4 and a capped ``add_impurity_phase`` with re-indexing first among its
    alternatives, from the resolved components.  It still gets both: the
    unresolved rows are left out of the impurity count, the resolved ones are
    not."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure, ins, data = _truth()
    a = structure.phases[0].cell.a.value
    p = rx.Parameter
    tetragonal = rx.Structure(phases=[rx.Phase(
        name="LaB6t", space_group="P 4/m m m",
        cell=rx.Cell(a=p(value=a), b=p(value=a), c=p(value=a * 1.004),
                     alpha=p(value=90.0), beta=p(value=90.0), gamma=p(value=90.0)),
        atoms=[rx.Atom(label="La", species="La", x=p(value=0.0), y=p(value=0.0),
                       z=p(value=0.0)),
               rx.Atom(label="B1", species="B", x=p(value=0.1993), y=p(value=0.5),
                       z=p(value=0.5)),
               rx.Atom(label="B2", species="B", x=p(value=0.5), y=p(value=0.5),
                       z=p(value=0.1993))],
        scale=structure.phases[0].scale.model_copy())])
    table = ParameterTable(tetragonal, ins)
    y = compile_model(tetragonal, ins, data, mode="rietveld").evaluate(
        table.decode(table.x0()))
    rng = np.random.default_rng(41)
    split = rx.PatternData(two_theta=data.two_theta,
                           intensity=rng.poisson(np.maximum(y, 1.0)).tolist(),
                           sigma=np.sqrt(np.maximum(y, 1.0)).tolist())

    report = _report_for(structure, ins, split)
    _every_row_measured(report)
    rows = _obs(report)
    assert any(u.flank.on_flank for u in rows), rows
    assert any(not u.flank.on_flank and u.height_over_sigma > IMPURITY_SIGMA
               for u in rows), rows
    # the longer c puts every split component below its cubic line
    assert all(u.flank.offset_fwhm < 0 for u in rows if u.flank.on_flank), rows
    assert _active(report, "reindex_or_recheck_cell")
    impurity = _active(report, "add_impurity_phase")
    assert impurity and impurity[0].alternatives[0] == "reindex_or_recheck_cell"
    _plot_state(structure, ins, split, "wp1977_tetragonal_split")


def _blank(tt, lines):
    y = 40.0 + 0.0 * tt
    for centre in lines:
        y = y + 3000.0 * _gauss(tt, centre, 0.1)
    return y


@pytest.mark.parametrize("model_lines, on_flank", [
    ((42.1, 65.0), True),    # the blank the model holds has the line
    ((65.0,), False),        # it has not: nothing drawn to sit under
])
def test_a_line_of_an_under_scaled_blank_sits_on_its_drawn_line(model_lines,
                                                                 on_flank):
    """#1217: a measured blank declared as a fixed background, refined low
    (here 0.45 against a truth of 0.60, the regression dilution WP-1309
    measured).  What is left of the blank's own line at 42.1° is listed, and
    its row says it sits on a line the model draws: the blank's.  The control
    removes that line from the blank the model holds, and the same residual
    sits under no drawn peak."""
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
    _every_row_measured(report)
    near = [u for u in _obs(report) if abs(u.two_theta - 42.1) < 0.1]
    assert near, _obs(report)
    assert all(u.flank.on_flank is on_flank for u in near), near
    _plot_state(structure, held, doped, f"wp1977_blank_line_{len(model_lines)}")

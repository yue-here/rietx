"""A zero scale holds the instrument only where the residual is noise.

WP-2049 held the zero shift and the profile terms at a stage's answer whenever
every phase read as unseen, reasoning that their columns reach the pattern only
through phase peaks.  That is true of a blank frame.  It is false of a phase
whose peaks missed: the scale goes to zero, every real peak stays in the
residual, and those columns are how the phase reaches them.  So the hold now
also needs Hill & Flack's (1987) d ≥ Q at the answer.

The fixture is tutorial 05's: seven LaB₆ patterns' worth of synchrotron
capillary instrument, one specimen, Poisson noise.  Every test below that moves
a fit also runs it with the check taken out (``no_check``), so the record of
what the check does is measured in the same test, on the same tree.

**A single fit's rescue is pinned as a decision, never as an outcome.**  Declining
the hold only leaves the fit free to walk, and the walk runs 90 to 150 solver
iterations from a scale at zero, so a start value moved by 1e-14 changes where it
lands.  What is robust is the decision read before the walk starts, at the ``zero``
stage's answer.  WP-2086's record has the recovery rates on both platforms.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

import rietx as rx
from rietx.optimize.statistics import (
    HILL_FLACK_Z,
    compute_statistics,
    durbin_watson,
    durbin_watson_q,
    residual_is_noise,
)
from rietx.schemas.instrument import Dispersion
from rietx.viz.plots import plot_result

pytestmark = pytest.mark.xdist_group("instrument-hold-noise")

OUT = pathlib.Path(__file__).parent / "output"

_REFINE = sys.modules["rietx.refine"]  # ``rietx.refine`` the attribute is a function

A_TRUE = 4.1566 * (1 + 5e-6 * 300)
TWO_THETA = np.arange(3.0, 24.0, 0.005)
PEAK_ONLY = {"instrument.zero_shift",
             *(f"instrument.profile.{n}" for n in "uvwxy")}

CIF = """data_LaB6
_space_group_name_H-M_alt 'P m -3 m'
_cell_length_a 4.1566
_cell_length_b 4.1566
_cell_length_c 4.1566
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_B_iso_or_equiv
La1 La 0 0 0 0.4
B1  B  0.1996 0.5 0.5 0.4
"""


@pytest.fixture(scope="module")
def lab6(tmp_path_factory):
    path = tmp_path_factory.mktemp("lab6") / "LaB6.cif"
    path.write_text(CIF, encoding="utf-8")
    return rx.Structure.from_cif(path)


def _true_instrument():
    ins = rx.Instrument.debye_scherrer(wavelength=0.4139)
    ins.source.dispersion = Dispersion()  # declared: these tests pin Rwp
    ins.zero_shift.value = 0.008
    ins.profile.w.value = 2.5e-4
    ins.background = rx.BackgroundChebyshev.with_terms(3)
    for c, v in zip(ins.background.coefficients, (40.0, -6.0, 1.5), strict=True):
        c.value = v
    return ins


def _start_instrument():
    ins = rx.Instrument.debye_scherrer(wavelength=0.4139)
    ins.source.dispersion = Dispersion()
    ins.profile.w.value = 2.5e-4 * 1.5
    ins.background = rx.BackgroundChebyshev.with_terms(3)
    return ins


def _with_cell(lab6, a: float, scale: float | None = None):
    s = lab6.model_copy(deep=True)
    for edge in "abc":
        getattr(s.phases[0].cell, edge).value = a
    if scale is not None:
        s.phases[0].scale.value = scale
    return s


def _pattern(lab6, a: float, seed: int, scale: float = 5e-4, **kw) -> rx.PatternData:
    """Poisson counts from the true instrument; ``scale=0`` is a blank frame."""
    y = rx.Refinement(_with_cell(lab6, a, scale), _true_instrument()).predict(TWO_THETA)
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=TWO_THETA, intensity=counts, **kw)


@pytest.fixture
def no_check(monkeypatch):
    """Take the check out: every unseen frame reads as noise, which is the
    hold as WP-2049 built it."""
    def remove():
        monkeypatch.setattr(_REFINE, "_residual_is_noise", lambda model, table: True)
    return remove


def _spy(monkeypatch):
    """The d each check read, in order, at the channels and P it read them."""
    read: list[tuple[float, int, int, bool]] = []
    real = _REFINE._residual_is_noise

    def spy(model, table):
        y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64)
        delta = (np.asarray(model.y_obs) - y) / np.asarray(model.sigma)
        answer = real(model, table)
        read.append((durbin_watson(delta), len(delta), len(table.free_paths), answer))
        return answer

    monkeypatch.setattr(_REFINE, "_residual_is_noise", spy)
    return read


def _draw(result, name: str, two_theta_range=None) -> None:
    OUT.mkdir(exist_ok=True)
    plot_result(result, path=OUT / f"{name}.png", two_theta_range=two_theta_range)


# ---- the arithmetic ---------------------------------------------------------


def test_the_check_reads_the_d_a_result_carries():
    """One d: the number on ``Statistics`` is the number the check tests."""
    rng = np.random.default_rng(1)
    y_obs = 100.0 + rng.normal(0.0, 10.0, 500)
    sigma = np.full(500, 10.0)
    stats = compute_statistics(y_obs, np.full(500, 100.0), sigma, 3)
    assert stats.durbin_watson == durbin_watson(
        np.sqrt(1.0 / sigma ** 2) * (y_obs - 100.0))
    # the check divides by σ where the statistics multiply by √w, an ulp apart
    assert stats.durbin_watson == pytest.approx(
        durbin_watson((y_obs - 100.0) / sigma), rel=1e-14)


@pytest.mark.parametrize("delta", [np.zeros(50), np.array([1.0])])
def test_a_residual_with_nothing_to_difference_has_no_d(delta):
    """0/0 is absent rather than a number."""
    assert durbin_watson(delta) is None


def test_q_is_the_papers_equation_2():
    """Worked by hand from Hill & Flack (1987), eq. 2, and the paper's z is the
    normal 0.1 % point it says it is."""
    from scipy.stats import norm

    n, p = 1000, 10
    assert durbin_watson_q(n, p) == pytest.approx(
        2.0 * (999.0 / 990.0 - 3.0902 / np.sqrt(1002.0)), rel=1e-15)
    assert HILL_FLACK_Z == pytest.approx(norm.ppf(0.999), abs=5e-5)


def test_q_is_the_point_it_claims_on_white_noise():
    """The 0.1 % point, in the only way that does not repeat the formula.
    Under the null a draw falls below Q about one time in a thousand, so
    20 000 draws expect 20, and the bar is a wide Poisson band about that."""
    n, draws = 800, 20000
    rng = np.random.default_rng(20261104)
    delta = rng.standard_normal((draws, n))
    d = np.sum(np.diff(delta, axis=1) ** 2, axis=1) / np.sum(delta ** 2, axis=1)
    below = int(np.sum(d < durbin_watson_q(n, 0)))
    assert 4 <= below <= 42, below


def test_white_noise_reads_as_noise_and_a_peak_does_not():
    rng = np.random.default_rng(2)
    white = rng.standard_normal(4000)
    x = np.arange(4000.0)
    peak = 40.0 * np.exp(-0.5 * ((x - 2000.0) / 30.0) ** 2) + white
    assert residual_is_noise(white, 15)
    assert not residual_is_noise(peak, 15)


def test_the_reading_does_not_depend_on_the_scale_of_sigma():
    """Why d and not χ²: a file whose esds are 1000× wrong reads the same."""
    rng = np.random.default_rng(3)
    x = np.arange(4000.0)
    for delta in (rng.standard_normal(4000),
                  5.0 * np.sin(x / 40.0) + rng.standard_normal(4000)):
        assert residual_is_noise(delta, 15) == residual_is_noise(1e3 * delta, 15)
        assert residual_is_noise(delta, 15) == residual_is_noise(1e-3 * delta, 15)


def test_the_test_is_one_sided():
    """Hill & Flack also read d > 4 − Q, as neighbours of opposite sign.  No
    peak leaves that, so an alternating residual does not decline the hold."""
    alternating = np.where(np.arange(2000) % 2 == 0, 1.0, -1.0)
    assert durbin_watson(alternating) > 4.0 - durbin_watson_q(2000, 15)
    assert residual_is_noise(alternating, 15)


@pytest.mark.parametrize(("delta", "n_free"), [
    (np.zeros(100), 3),                   # a residual of nothing
    (np.array([1.0, 2.0, 3.0]), 2),       # N = P + 1
    (np.array([1.0, 2.0, 3.0]), 5),       # P > N: Q would divide by a negative
    (np.arange(30.0), 25),                # Q above 4, which no d can reach
    (np.array([1.0]), 0),
])
def test_with_nothing_to_test_there_is_no_structure(delta, n_free):
    assert residual_is_noise(delta, n_free)


# ---- a phase whose peaks missed ---------------------------------------------


def test_a_phase_whose_peaks_missed_keeps_its_instrument_free(lab6, monkeypatch, no_check):
    """Read at the first stages' answers, which come before the walk.  With the
    check the residual reads as structure and nothing of the instrument is held.
    Without it the zero shift is held at ``zero`` and W at ``profile_w``."""
    data = _pattern(lab6, A_TRUE, seed=14)

    def run():
        ref = rx.Refinement(_with_cell(lab6, A_TRUE / 1.02), _start_instrument(), history=False)
        return ref.fit(data, plan="mccusker_default")

    read = _spy(monkeypatch)
    result = run()
    _draw(result, "hold_noise_single_2pct")
    held = {s.name: set(s.held) for s in result.stages}
    d, n, p, answer = read[0]
    assert answer is False
    assert d < durbin_watson_q(n, p)
    for stage in ("zero", "cell", "profile_w"):
        assert not PEAK_ONLY & held[stage], stage

    no_check()
    held = {s.name: set(s.held) for s in run().stages}
    assert "instrument.zero_shift" in held["zero"]
    assert {"instrument.zero_shift", "instrument.profile.w"} <= held["profile_w"]


def test_the_tutorials_step_is_reached_warm(lab6, no_check):
    """Tutorial 05's jump.  Without the check the warm rung fails, the ladder
    runs out at Rwp 0.998, and the pattern is quarantined."""
    a = [A_TRUE, 4.1566 * (1 + 5e-6 * 400) * 1.02]
    patterns = [_pattern(lab6, a[0], seed=14), _pattern(lab6, a[1], seed=15)]

    def run():
        runner = rx.SequentialRefinement(_with_cell(lab6, 4.1566 * 1.001),
                                         _start_instrument())
        return runner, runner.fit(patterns, plan="mccusker_default",
                                  x=[600.0, 700.0], x_label="T (K)")

    runner, series = run()
    assert [e.rung for e in series] == ["cold", "warm"]
    assert series.entries[1].statistics.rwp == pytest.approx(0.0390, abs=5e-4)
    _draw(runner.results_[1], "hold_noise_tutorial_step")

    no_check()
    assert run()[1].entries[1].statistics.rwp > 0.9


def test_the_peaks_still_read_as_structure_past_an_excluded_region(lab6, monkeypatch):
    """Excluding a span leaves one bridged pair in d per span, and a residual
    of peaks still declines the hold.  Worst placed, fifteen such pairs moved d
    by 0.45 with 1.36 still to go to Q (the WP's record), so d stays the
    number the result carries.  Where the walk lands moves with the channels,
    so this asserts the reading rather than the outcome."""
    read = _spy(monkeypatch)
    data = _pattern(lab6, A_TRUE, seed=14, excluded_regions=[(9.0, 9.6), (15.0, 15.4)])
    ref = rx.Refinement(_with_cell(lab6, A_TRUE / 1.02), _start_instrument(), history=False)
    result = ref.fit(data, plan="mccusker_default")
    _draw(result, "hold_noise_excluded")
    assert read
    assert {n for _, n, _, _ in read} == {result.statistics.n_points}
    assert not any(answer for _, _, _, answer in read)
    assert not PEAK_ONLY & {p for s in result.stages[:4] for p in s.held}


def test_a_joint_fit_with_one_misplaced_and_one_blank_histogram(lab6, no_check):
    """The case nobody had measured.  Each histogram answers for itself: the
    blank one's zero shift and widths are held, the misplaced one's stay free
    and reach the peaks, and the shared cell comes home.  Without the check
    both are held, the cell stops 7800 ppm short and Rwp is 0.92."""
    data = [_pattern(lab6, A_TRUE, seed=14), _pattern(lab6, A_TRUE, seed=3, scale=0.0)]

    def run():
        start = [_with_cell(lab6, A_TRUE / 1.02) for _ in data]
        ref = rx.MultiHistogramRefinement(start, [_start_instrument() for _ in data])
        return ref.fit(data, plan="mccusker_default")

    result = run()
    _draw(result.for_histogram(0), "hold_noise_joint_misplaced")
    _draw(result.for_histogram(1), "hold_noise_joint_blank")
    rows = {p.path: p for p in result.parameters}
    assert rows["phases.0.cell.a"].value == pytest.approx(A_TRUE, rel=2e-5)
    assert result.histograms[0].statistics.rwp == pytest.approx(0.0405, abs=5e-4)
    held = set(result.stages[-1].held)
    assert {f"hist.1.{p}" for p in PEAK_ONLY} <= held
    assert not {f"hist.0.{p}" for p in PEAK_ONLY} & held
    assert rows["hist.0.instrument.zero_shift"].value == pytest.approx(0.008, abs=1e-4)

    no_check()
    without = run()
    assert without.histograms[0].statistics.rwp > 0.9
    rows = {p.path: p for p in without.parameters}
    assert abs(rows["phases.0.cell.a"].value / A_TRUE - 1.0) > 0.005


# ---- a blank frame ----------------------------------------------------------


@pytest.mark.parametrize("excluded", [[], [(9.0, 9.6)]], ids=["whole", "excluded"])
@pytest.mark.parametrize("seed", [3, 4])
def test_a_blank_frame_is_held_and_bit_identical_to_the_hold_without_the_check(
        lab6, no_check, seed, excluded):
    """The guard on the other side: the check takes nothing from WP-2049's
    case.  Every number of a blank frame's answer is the unchecked hold's."""
    data = _pattern(lab6, A_TRUE, seed=seed, scale=0.0, excluded_regions=excluded)

    def run():
        ref = rx.Refinement(_with_cell(lab6, A_TRUE), _start_instrument(), history=False)
        return ref.fit(data, plan="mccusker_default")

    checked = run()
    assert PEAK_ONLY <= set(checked.stages[-1].held)
    no_check()
    unchecked = run()
    assert checked.statistics == unchecked.statistics
    assert [(p.path, p.value, p.stderr) for p in checked.parameters] == [
        (p.path, p.value, p.stderr) for p in unchecked.parameters]
    if seed == 3 and not excluded:
        _draw(checked, "hold_noise_blank")


def test_a_real_line_in_an_excluded_region_does_not_decline_the_hold(lab6):
    """d is read over the fitted channels.  An excluded span holding a line
    from outside the model (a holder, a beamstop) is no structure in the
    residual: the frame is blank, and the hold stands."""
    data = _pattern(lab6, A_TRUE, seed=3, scale=0.0)
    y = np.asarray(data.y()).copy()
    x = np.asarray(data.tt())
    y += 5000.0 * np.exp(-0.5 * ((x - 12.0) / 0.03) ** 2)
    data = rx.PatternData(two_theta=x, intensity=np.round(y),
                          excluded_regions=[(11.5, 12.5)])
    ref = rx.Refinement(_with_cell(lab6, A_TRUE), _start_instrument(), history=False)
    result = ref.fit(data, plan="mccusker_default")
    _draw(result, "hold_noise_excluded_line")
    assert PEAK_ONLY <= set(result.stages[-1].held)
    assert result.statistics.durbin_watson >= durbin_watson_q(
        result.statistics.n_points, result.statistics.n_free_parameters)


# ---- the record -------------------------------------------------------------


def test_a_fit_left_unseen_carries_the_d_that_declined_the_hold(lab6, monkeypatch):
    """Rule 1: a withheld verdict leaves its statistic.  A 5 % error is past
    what this reaches, so the fit ends with no phase seen and the instrument
    free.  The last d read is the result's own, printed as ``DW``, and N sits
    beside it to give Q."""
    read = _spy(monkeypatch)
    data = _pattern(lab6, A_TRUE, seed=14)
    ref = rx.Refinement(_with_cell(lab6, A_TRUE / 1.05), _start_instrument(), history=False)
    result = ref.fit(data, plan="mccusker_default")
    _draw(result, "hold_noise_unreached_5pct")
    assert not PEAK_ONLY & set(result.stages[-1].held)
    d, n, p, answer = read[-1]
    assert answer is False
    assert result.statistics.durbin_watson == pytest.approx(d, rel=1e-13)
    assert result.statistics.n_points == n
    assert d < durbin_watson_q(result.statistics.n_points,
                               result.statistics.n_free_parameters)
    assert f"DW {d:.2f}" in str(result)


def test_a_fit_that_goes_on_leaves_the_declining_d_on_its_history_node(lab6, monkeypatch):
    """A fit that goes on from a declined hold has a later answer, so the
    result's d need not be the one that declined.  Each stage's node keeps the
    statistics of that stage's answer, so the d that declined is on the node."""
    read = _spy(monkeypatch)
    data = _pattern(lab6, A_TRUE, seed=14)
    ref = rx.Refinement(_with_cell(lab6, A_TRUE / 1.02), _start_instrument())
    result = ref.fit(data, plan="mccusker_default")
    _draw(result, "hold_noise_recovered")
    declined = [d for d, _, _, answer in read if not answer]
    assert declined
    recorded = [n.metrics.statistics.durbin_watson for n in ref.history.nodes.values()
                if n.metrics is not None and n.metrics.statistics is not None]
    assert any(d == pytest.approx(declined[0], rel=1e-9) for d in recorded), (
        declined, recorded)

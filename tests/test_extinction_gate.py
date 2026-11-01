"""The extinction screen's reference-fit gate and its cell-free prefit.

Two claims, each with an arm that must come out a known way:

* **the gate** — when the absence-free class's own fit has not modelled the
  allowed lines, every absence test downstream reads that misfit, so the
  screen must abstain (``status="unreliable"``, ``EXTINCTION_SCREEN_UNRELIABLE``,
  ``best_or_none() is None``) instead of answering.  Positive arm: a cell 0.4 %
  off at synchrotron resolution, held; the class the screen would otherwise
  return is ``F - - -`` with every rival's absences "untestable", a confident
  wrong answer.  Negative arm: the same pattern at its own cell answers ``F d - -``.
* **the prefit** (``refine_cell=True``, the default) — a cell-free
  ``profile_only`` Le Bail of the lattice group before the screen, so the same
  0.4 %-off cell is brought back and the screen answers at the sample's cell.
  A cell outside any Le Bail's basin (1 % off) still reaches the gate.

Synthetic Si (F d -3 m, a = 5.4311 Å) at λ = 0.8257 Å and a 0.004° step,
generated here from the structure — public, and the generator of the drafted
issue's reproducer.  The public rows behind
:data:`~rietx.indexing.extinction.REFERENCE_NET_RWP_MAX` (this pattern, the
synthetic P 2₁/c, FAP, 11-BM NAC, SRM 676a corundum, PbSO₄): every right or
nearly right cell read ≤ 0.36, and every cell outside the refinable basin read
≥ 1.0 but one, PbSO₄ X-ray at ×0.99, which reads 0.45 and passes (a known miss,
pinned below).

Round 4 of #939's review asked for three follow-ups, all here: the perfect-fit
value beside ``reference_rwp_net`` (weak data or misfit), the gate firing on a
real family, and the envelope's bias in a continuum of lines.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

import rietx as rx
from rietx import determine_extinction_symbol
from rietx.indexing.extinction import (
    REFERENCE_NET_RWP_MAX,
    _background_unseeded,
    _reference_net_rwp,
)
from rietx.schemas.indexing import CellCandidate

pytestmark = pytest.mark.xdist_group("extinction-gate")

SI_A = 5.4311
LAM = 0.825739
LIMITS = (12.1, 60.0)


def _si_structure():
    from rietx.schemas.structure import Atom, Cell, Parameter, Phase, Structure

    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m",
        cell=Cell(a=Parameter(value=SI_A), b=Parameter(value=SI_A),
                  c=Parameter(value=SI_A), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Si1", species="Si", x=Parameter(value=0.125),
                    y=Parameter(value=0.125), z=Parameter(value=0.125),
                    biso=Parameter(value=0.5))])])


@pytest.fixture(scope="module")
def si():
    """The pattern, the declared instrument, and the picked lines."""
    instrument = rx.Instrument.debye_scherrer(wavelength=LAM)
    instrument.source.dispersion = None         # a pinned number declares it
    instrument.profile.w.value = 3e-4
    instrument.profile.u.value = 5e-4
    instrument.profile.x.value = 5e-3
    tt = np.round(np.arange(12.088, 62.0, 0.004), 3)
    y = rx.Refinement(_si_structure(), instrument, history=False).predict(two_theta=tt)
    obs = np.random.default_rng(1).poisson(y / y.max() * 1.3e6 + 7700.0).astype(float)
    data = rx.PatternData(two_theta=tt.tolist(), intensity=obs.tolist(),
                          sigma=np.sqrt(np.maximum(obs, 1.0)).tolist())
    return data, instrument, rx.pick_peaks(data, instrument, two_theta_range=LIMITS)


def _cubic_f(a: float) -> CellCandidate:
    return CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(0.0,) * 6,
                         system="cubic", centring="F", volume=a ** 3)


def _screen(si, factor, **kw):
    data, instrument, peaks = si
    return determine_extinction_symbol(data, _cubic_f(SI_A * factor), instrument,
                                       peaks=peaks, two_theta_limits=LIMITS, **kw)


def _codes(screen):
    return [d.code for d in screen.diagnostics]


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
def test_a_held_cell_off_by_four_parts_per_thousand_abstains(si):
    """The positive arm: without the gate this returns a confident wrong class."""
    screen = _screen(si, 1.004, refine_cell=False)
    assert screen.status == "unreliable"
    assert screen.reference_rwp_net > REFERENCE_NET_RWP_MAX
    assert screen.best_or_none() is None
    assert "EXTINCTION_SCREEN_UNRELIABLE" in _codes(screen)
    # what the gate withholds: a top class that is not the specimen's (F d - -)
    # and not refuted, every rival's absences untestable because the misfit fills
    # their windows.  Before this branch's rebase onto main (c9dde14d) the top was
    # the absence-free F - - - with every rival 10 ΔBIC worse; the class moved
    # and the withholding did not.
    top = screen.candidates[0]
    assert top.symbol != "F d - -" and not top.refuted
    rivals = [c for c in screen.candidates if c.n_absent and not c.refuted]
    assert rivals and all(c.n_testable == 0 for c in rivals)


def test_the_same_pattern_at_its_own_cell_passes_the_gate(si):
    """The negative arm, held and refined alike."""
    for refine_cell in (False, True):
        screen = _screen(si, 1.0, refine_cell=refine_cell)
        assert screen.status == "converged", refine_cell
        assert screen.reference_rwp_net < 0.1 * REFERENCE_NET_RWP_MAX
        assert "EXTINCTION_SCREEN_UNRELIABLE" not in _codes(screen)
        best = screen.best_or_none()
        assert best is not None and best.symbol == "F d - -", refine_cell


def test_a_cell_outside_the_prefits_basin_reaches_the_gate(si):
    """1 % off at this resolution: the prefit cannot bring it back, and the
    screen says so rather than ranking on the wreckage."""
    screen = _screen(si, 1.01)
    assert screen.prefit_rwp is not None
    assert screen.status == "unreliable"
    assert screen.best_or_none() is None
    message = next(d.message for d in screen.diagnostics
                   if d.code == "EXTINCTION_SCREEN_UNRELIABLE")
    assert "prefit" in message


def test_the_unreliable_suggestion_lists_the_causes_without_ranking_them(si):
    """Round 4 (#939): a second phase and weak data trip the gate at a right
    cell, so the suggestion may not name the cell the first suspect."""
    screen = _screen(si, 1.01)
    diag = next(d for d in screen.diagnostics
                if d.code == "EXTINCTION_SCREEN_UNRELIABLE")
    text = diag.suggestion
    assert "first suspect" not in text and "no order" in text
    for cause in ("the cell", "a phase the reference does not model",
                  "weak data", "the range", "the wavelength", "the width law"):
        assert cause in text, cause
    assert "may measure that misfit" in diag.message


def test_the_gate_reads_a_background_no_fit_can_move():
    """A fit that has lost its peaks can sink its own background and let the
    Le Bail intensities carry the pedestal; the background-subtracted Rwp then
    divides by the pedestal and passes.  The gate divides by the net signal
    over the picker's envelope, which no candidate can touch."""
    tt = np.arange(10.0, 40.0, 0.01)
    pedestal = np.full_like(tt, 3000.0)
    lines = 5000.0 * np.exp(-4 * np.log(2) * ((tt[:, None] - [15.0, 22.0, 31.0])
                                              / 0.05) ** 2).sum(axis=1)
    y_obs = pedestal + lines
    sigma = np.sqrt(y_obs)
    # every line missed, the background sunk to zero, the pedestal in "reflections"
    y_bkg = np.zeros_like(tt)
    y_calc = pedestal.copy()
    fit_bs = np.sqrt(np.sum((y_obs - y_calc) ** 2 / sigma ** 2)
                     / np.sum((y_obs - y_bkg) ** 2 / sigma ** 2))
    assert fit_bs < 0.1 * REFERENCE_NET_RWP_MAX     # the fit's own net form passes
    lost = SimpleNamespace(two_theta=tt, y_obs=y_obs, y_calc=y_calc, sigma=sigma,
                           y_background=y_bkg)
    assert _reference_net_rwp(lost)[0] > 1.3 * REFERENCE_NET_RWP_MAX
    good = SimpleNamespace(two_theta=tt, y_obs=y_obs, y_calc=y_obs + 0.5 * sigma,
                           sigma=sigma, y_background=pedestal)
    assert _reference_net_rwp(good)[0] < 0.3 * REFERENCE_NET_RWP_MAX


# ----------------------------------------------------------------------
# the perfect-fit value: weak data or misfit (review of #939, round 4)
# ----------------------------------------------------------------------
def _lines_on_a_pedestal(height: float, seed: int = 4):
    """Three Gaussian lines of the given height on a 3000-count pedestal, with
    Poisson noise; returns the noiseless truth beside them."""
    tt = np.arange(10.0, 40.0, 0.01)
    truth = 3000.0 + height * np.exp(
        -4 * np.log(2) * ((tt[:, None] - [15.0, 22.0, 31.0]) / 0.05) ** 2).sum(axis=1)
    y_obs = np.random.default_rng(seed).poisson(truth).astype(float)
    return tt, truth, y_obs, np.sqrt(np.maximum(y_obs, 1.0))


@pytest.mark.parametrize("height", [60.0, 5000.0])
def test_the_perfect_fit_value_is_what_a_noise_only_fit_reads(height):
    """√(N/D) is the gate's quantity for a fit that leaves only the noise: hand
    the gate the noiseless truth as its calculated pattern and the two agree,
    at S < N (60-count lines on 3000, the value past the bound) and at S ≫ N."""
    tt, truth, y_obs, sigma = _lines_on_a_pedestal(height)
    perfect_fit = SimpleNamespace(two_theta=tt, y_obs=y_obs, y_calc=truth,
                                  sigma=sigma)
    net, perfect = _reference_net_rwp(perfect_fit)
    assert perfect == pytest.approx(net, rel=0.05)
    s_over_n = float(np.sum(((truth - 3000.0) / sigma) ** 2)) / len(tt)
    assert perfect == pytest.approx(np.sqrt(1.0 / (1.0 + s_over_n)), rel=0.05)
    assert (perfect > REFERENCE_NET_RWP_MAX) == (s_over_n < 1.0)


def test_the_message_says_weak_data_when_no_fit_could_pass(si):
    """S < N: Si at its own cell, its lines cut to 3000 counts on the 7700-count
    background (S/N ≈ 0.5).  The gate fires at the right cell, and the message
    now says the data are weak rather than leaving the cell under suspicion."""
    data, instrument, _peaks = si
    tt = np.asarray(data.two_theta)
    y = rx.Refinement(_si_structure(), instrument, history=False).predict(two_theta=tt)
    obs = np.random.default_rng(1).poisson(y / y.max() * 3.0e3 + 7700.0).astype(float)
    weak = rx.PatternData(two_theta=tt.tolist(), intensity=obs.tolist(),
                          sigma=np.sqrt(np.maximum(obs, 1.0)).tolist())
    screen = determine_extinction_symbol(weak, _cubic_f(SI_A), instrument,
                                         two_theta_limits=LIMITS, refine_cell=False)
    assert screen.status == "unreliable" and screen.best_or_none() is None
    # measured 0.816 against √(N/(N+S)) = 0.814 from the noiseless truth
    assert screen.perfect_fit_rwp_net > REFERENCE_NET_RWP_MAX
    message = next(d.message for d in screen.diagnostics
                   if d.code == "EXTINCTION_SCREEN_UNRELIABLE")
    assert f"would read {screen.perfect_fit_rwp_net:.3f}" in message
    assert "the data are weak" in message and "misfits" not in message
    # the pair cannot separate weak data from an envelope inside the lines
    assert "envelope sits inside the lines" in message


def test_the_message_says_misfit_when_the_data_could_pass(si):
    """S ≫ N: the 1 % cell the prefit cannot bring back.  A noise-only fit would
    read 0.024, so the gate's 1.17 is misfit, and the message says by how much."""
    screen = _screen(si, 1.01)
    assert screen.status == "unreliable"
    assert screen.perfect_fit_rwp_net < 0.1 * REFERENCE_NET_RWP_MAX
    message = next(d.message for d in screen.diagnostics
                   if d.code == "EXTINCTION_SCREEN_UNRELIABLE")
    ratio = screen.reference_rwp_net / screen.perfect_fit_rwp_net
    assert f"misfits them, by {ratio:.1f}×" in message
    assert "the data are weak" not in message


# ----------------------------------------------------------------------
# the prefit
# ----------------------------------------------------------------------
def test_the_default_prefit_brings_a_four_per_thousand_cell_back(si):
    screen = _screen(si, 1.004)
    assert screen.prefit_rwp is not None and screen.prefit_rwp < 0.05
    assert screen.cell[0] == pytest.approx(SI_A, rel=1e-4)
    assert screen.status == "converged"
    best = screen.best_or_none()
    assert best is not None and best.symbol == "F d - -"


def test_only_the_presets_all_zero_background_is_replaced():
    from rietx.schemas.instrument import BackgroundChebyshev
    from rietx.schemas.structure import Parameter

    assert _background_unseeded(rx.Instrument.debye_scherrer(wavelength=1.0).background)
    assert _background_unseeded(BackgroundChebyshev.with_terms(6))
    declared = BackgroundChebyshev(coefficients=[Parameter(value=v)
                                                 for v in (40.0, -6.0, 2.0)])
    assert not _background_unseeded(declared)


# ----------------------------------------------------------------------
# the prefit on real data: #726's public case
# ----------------------------------------------------------------------
def _pbso4_arrays():
    """The X-ray histogram of ``tests/data/gsas2_pbso4.gpx`` (Hill 1992): 2θ,
    counts, weights, and GSAS-II's own fitted pattern and background."""
    from pathlib import Path

    from rietx.io.projects.gsas2 import _read_tree

    tree = _read_tree(Path(__file__).parent / "data" / "gsas2_pbso4.gpx")
    head = next(item[0] for item in tree if isinstance(item[0], list)
                and str(item[0][0]).startswith("PWDR PBSO4.XRA"))
    return tuple(np.asarray(a, dtype=float) for a in head[1][1][:5])


def _pbso4_inputs(factor: float = 1.0):
    """The issue's reproducer: the X-ray histogram on the preset instrument at
    the cell ``index_pattern`` returned for its neutron twin (0.1-0.2 % long),
    scaled by ``factor``."""
    from rietx.schemas.instrument import EmissionLine, Source

    x, y, w, _calc, _bkg = _pbso4_arrays()
    data = rx.PatternData(two_theta=x.tolist(), intensity=y.tolist(),
                          sigma=(1.0 / np.sqrt(np.maximum(w, 1e-12))).tolist())
    instrument = rx.Instrument.bragg_brentano()
    instrument.source = Source(
        lines=[EmissionLine(wavelength=1.5405),
               EmissionLine(wavelength=1.5443,
                            weight=rx.Parameter(value=0.5, min=0.0, max=1.0))],
        polarization=rx.Parameter(value=0.5, min=0.0, max=1.0), dispersion=None)
    limits = (15.0, float(x.max()))
    peaks = rx.pick_peaks(data, instrument, two_theta_range=limits)
    cell = tuple(v * factor for v in (6.9644, 5.4038, 8.4956)) + (90.0, 90.0, 90.0)
    candidate = CellCandidate(cell=cell, cell_esd=(0.0,) * 6, system="orthorhombic",
                              centring="P", volume=float(np.prod(cell[:3])))
    return data, instrument, limits, peaks, candidate


@pytest.mark.slow
def test_pbso4_xray_gets_its_class_only_through_the_seeded_prefit():
    """The X-ray histogram of ``tests/data/gsas2_pbso4.gpx`` (Hill 1992) at the
    cell ``index_pattern`` returned for its neutron twin, 0.1-0.2 % long, on the
    preset instrument — the issue's reproducer.

    Measured (M-C7-3): held, the screen abstains with ``P 21 21 21`` on top; the
    default prefit gives ``P c - n`` (P n m a in this setting) at ΔBIC −564;
    the same prefit from the preset's all-zero background returns ``P - - n``,
    confidently and wrongly, which is why the prefit seeds it.
    """
    data, instrument, limits, peaks, candidate = _pbso4_inputs()

    screen = determine_extinction_symbol(data, candidate, instrument, peaks=peaks,
                                         two_theta_limits=limits)
    best = screen.best_or_none()
    assert best is not None, [(c.symbol, c.delta_bic) for c in screen.candidates[:4]]
    assert best.symbol == "P c - n"
    assert "P c m n" in best.space_groups
    assert screen.status == "converged"

    held = determine_extinction_symbol(data, candidate, instrument, peaks=peaks,
                                       two_theta_limits=limits, refine_cell=False)
    held_best = held.best_or_none()
    assert held_best is None or held_best.symbol != "P c - n"


# ----------------------------------------------------------------------
# the gate on real families (review of #939, round 4)
# ----------------------------------------------------------------------
def _corundum():
    from tests.test_extinction_symbol import (
        CORUNDUM_CELL,
        CORUNDUM_RANGE,
        corundum_inputs,
    )

    data, _cand, instrument = corundum_inputs.__wrapped__()
    return data, instrument, CORUNDUM_RANGE, CORUNDUM_CELL, "trigonal", "R", "R - c -"


def _fap():
    from tests.test_extinction_symbol import DATA, _fap_inputs

    if not (DATA / "FAP.XRA").exists():
        pytest.skip("GSAS-II LabData tutorial dataset not present")
    data, cand, instrument = _fap_inputs()
    return data, instrument, (15.0, 90.0), cand.cell, "hexagonal", "P", "P 63 - -"


@pytest.mark.parametrize(("inputs", "factor"), [(_corundum, 1.02), (_fap, 0.99)],
                         ids=["srm676a-x1.02", "fap-x0.99"])
def test_the_gate_fires_on_a_real_family_outside_the_prefits_basin(inputs, factor):
    """The firing side on real patterns, not only synthetic Si.

    The cell is the right one scaled past the prefit's basin: for SRM 676a
    corundum the basin is measured from ×0.998 to ×1.01
    (``test_extinction_refine_cell``), so ×1.02 is the next step out; for the
    GSAS-II fluorapatite ×0.99 is the first of ±0.5 %, ±1 % that the prefit does
    not bring back.  The prefit's own cell is the evidence: it stays ≥ 0.5 %
    off.  Measured: 1.00 against 0.19 at the right cell (corundum), 1.00
    against 0.12 (FAP), with a perfect fit reading 0.09 and 0.07, so misfit.

    Fast tier on purpose: it runs two real fits per case, measured at 0.96 s and
    2.95 s alone (``tests/CLAUDE.md``: a fast test that runs real fits says why).
    """
    data, instrument, limits, cell, system, centring, truth = inputs()

    def screen_at(f):
        scaled = tuple(v * f for v in cell[:3]) + tuple(cell[3:])
        return determine_extinction_symbol(data, CellCandidate(
            cell=scaled, cell_esd=(0.0,) * 6, system=system, centring=centring,
            volume=1.0), instrument, two_theta_limits=limits)

    right = screen_at(1.0)
    assert right.status == "converged"
    assert right.reference_rwp_net < 0.5 * REFERENCE_NET_RWP_MAX
    best = right.best_or_none()
    assert best is not None and best.symbol == truth

    wrong = screen_at(factor)
    assert abs(wrong.cell[0] / cell[0] - 1.0) > 0.005      # outside the basin
    assert wrong.status == "unreliable", wrong.reference_rwp_net
    assert wrong.reference_rwp_net > REFERENCE_NET_RWP_MAX
    assert wrong.best_or_none() is None
    assert wrong.perfect_fit_rwp_net < 0.2 * REFERENCE_NET_RWP_MAX   # misfit


@pytest.mark.slow
@pytest.mark.xfail(strict=True, reason=(
    "known miss: PbSO4 X-ray at x0.99 of its index cell; the prefit stops about "
    "0.3 % short, the reference reads 0.45 (below 1/sqrt(2)) and the screen "
    "returns P c - - confidently, where the specimen is P c - n; belongs to "
    "WP-1910's open task (re-screen at the prefit's cell, held, flag a "
    "disagreement between the two screens, ruled 2026-10-26), which may not "
    "flag it either, since a held re-screen with no decisive class is "
    "recorded, not flagged: strict until a run shows it does"))
def test_the_gate_misses_pbso4_at_one_percent_short():
    """The counter-example to "every cell outside the basin reads ≥ 1.6": an
    out-of-basin cell inside the 0.36-1.6 gap.  The prefit moves 6.895 Å to
    6.935 (the specimen's is 6.959), short on every axis, and the reference
    fit's widths absorb the rest.  Pinned strict, so a fix shows up as a pass."""
    data, instrument, limits, peaks, candidate = _pbso4_inputs(0.99)
    screen = determine_extinction_symbol(data, candidate, instrument, peaks=peaks,
                                         two_theta_limits=limits)
    best = screen.best_or_none()
    assert best is None or best.symbol == "P c - n"


# ----------------------------------------------------------------------
# the envelope in a continuum of lines (review of #939, round 1)
# ----------------------------------------------------------------------
def test_the_envelope_rides_up_where_the_lines_form_a_continuum():
    """A known limit, pinned so a change to the envelope is seen.

    GSAS-II's own Rietveld fit of the PbSO₄ X-ray histogram (Hill 1992), read by
    the gate's quantity against the picker's envelope and against GSAS-II's
    fitted background: the two agree where the lines are resolved, and at high
    angle, where orthorhombic lines run together, the envelope sits in the
    tails, the net shrinks and the same fit reads 1.8× worse."""
    from rietx.indexing.peaks import _debiased_envelope

    x, y, w, calc, bkg = _pbso4_arrays()
    keep = (x >= 15.0) & (w > 0)
    x, y, w, calc, bkg = x[keep], y[keep], w[keep], calc[keep], bkg[keep]
    env = _debiased_envelope(x, y)

    def ratio(lo, hi):
        m = (x >= lo) & (x < hi)
        chi = np.sum(w[m] * (y[m] - calc[m]) ** 2)
        return [float(np.sqrt(chi / np.sum(w[m] * (y[m] - b[m]) ** 2)))
                for b in (env, bkg)]

    low_env, low_bkg = ratio(15.0, 60.0)          # 0.136 against 0.128
    high_env, high_bkg = ratio(110.0, 160.0)      # 0.436 against 0.245
    assert low_env / low_bkg < 1.15
    assert high_env / high_bkg > 1.5


# ----------------------------------------------------------------------
# a stop, and the gate (review of #939, round 1)
# ----------------------------------------------------------------------
def test_a_late_stop_keeps_the_gates_verdict(si):
    """The token is set before the screen starts, so every class after the
    first is skipped and the status used to be overwritten with "cancelled" —
    which ``best_or_none`` does not abstain on."""
    from rietx.optimize.cancel import CancelToken

    token = CancelToken()
    token.cancel()
    screen = _screen(si, 1.004, refine_cell=False, cancel=token)
    assert screen.status == "unreliable"
    assert screen.best_or_none() is None
    assert "EXTINCTION_SCREEN_UNRELIABLE" in _codes(screen)


def test_a_stop_reaches_the_prefit(si):
    """Without ``cancel=`` on the prefit's fit the five-stage Le Bail ran to the
    end before the stop was read, and the screen came back with its cell moved."""
    from rietx.optimize.cancel import CancelToken

    token = CancelToken()
    token.cancel()
    screen = _screen(si, 1.004, cancel=token)
    assert screen.status == "cancelled"
    assert screen.prefit_rwp is None
    assert screen.candidates == [] and screen.best_or_none() is None
    assert screen.cell == pytest.approx(_cubic_f(SI_A * 1.004).cell)


def test_the_unreliable_warning_survives_an_empty_candidate_list():
    from rietx.indexing.diagnostics import extinction_diagnostics
    from rietx.schemas.indexing import ExtinctionScreen

    screen = ExtinctionScreen.model_construct(
        status="unreliable", candidates=[], reference_rwp_net=0.9,
        prefit_rwp=None, lattice_group="F", system="cubic", centring="F",
        cell=(5.4, 5.4, 5.4, 90.0, 90.0, 90.0), two_theta_range=(10.0, 60.0))
    codes = [d.code for d in extinction_diagnostics(screen)]
    assert codes == ["EXTINCTION_SCREEN_UNRELIABLE", "EXTINCTION_SYMBOL_AMBIGUOUS"]


def test_a_cancelled_empty_screen_says_it_was_stopped():
    """A stop during the prefit leaves no candidates; the diagnostic must not
    blame the cell for 'no fittable reflections'."""
    from rietx.indexing.diagnostics import extinction_diagnostics
    from rietx.schemas.indexing import ExtinctionScreen

    screen = ExtinctionScreen.model_construct(
        status="cancelled", candidates=[], reference_rwp_net=None,
        prefit_rwp=None, lattice_group="F", system="cubic", centring="F",
        cell=(5.4, 5.4, 5.4, 90.0, 90.0, 90.0), two_theta_range=(10.0, 60.0))
    (diag,) = extinction_diagnostics(screen)
    assert "stopped" in diag.message and "fittable" not in diag.message

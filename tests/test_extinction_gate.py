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
nearly right cell read ≤ 0.36, every cell outside the refinable basin ≥ 1.6.
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
    """The positive arm: without the gate this returns ``F - - -`` confidently."""
    screen = _screen(si, 1.004, refine_cell=False)
    assert screen.status == "unreliable"
    assert screen.reference_rwp_net > REFERENCE_NET_RWP_MAX
    assert screen.best_or_none() is None
    assert "EXTINCTION_SCREEN_UNRELIABLE" in _codes(screen)
    # what the gate withholds: the absence-free class on top, every rival's
    # absences untestable because the misfit fills their windows
    top = screen.candidates[0]
    assert top.symbol == "F - - -" and not top.refuted
    rivals = [c for c in screen.candidates if c.n_absent and not c.refuted]
    assert rivals and all(c.n_testable == 0 for c in rivals)
    assert screen.candidates[1].delta_bic - top.delta_bic > 10.0


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
    assert _reference_net_rwp(lost) > 1.3 * REFERENCE_NET_RWP_MAX
    good = SimpleNamespace(two_theta=tt, y_obs=y_obs, y_calc=y_obs + 0.5 * sigma,
                           sigma=sigma, y_background=pedestal)
    assert _reference_net_rwp(good) < 0.3 * REFERENCE_NET_RWP_MAX


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
    from pathlib import Path

    from rietx.io.projects.gsas2 import _read_tree
    from rietx.schemas.instrument import EmissionLine, Source

    path = Path(__file__).parent / "data" / "gsas2_pbso4.gpx"
    tree = _read_tree(path)
    head = next(item[0] for item in tree if isinstance(item[0], list)
                and str(item[0][0]).startswith("PWDR PBSO4.XRA"))
    x, y, w = (np.asarray(a, dtype=float) for a in head[1][1][:3])
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
    cell = (6.9644, 5.4038, 8.4956, 90.0, 90.0, 90.0)
    candidate = CellCandidate(cell=cell, cell_esd=(0.0,) * 6, system="orthorhombic",
                              centring="P", volume=float(np.prod(cell[:3])))

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

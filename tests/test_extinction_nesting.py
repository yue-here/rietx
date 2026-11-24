"""The extinction screen's comparison is nested (WP-2076).

Five synthetic specimens on which the Le Bail screen named a class excluding the
true group at a correct cell, silently: P 6₃/m m c, P 6/m c c, P n -3 n,
P 4/n m m and F m -3 m.  Each pattern is built here from rietx's own forward
model, as WP-2076's sweep built it: Ca, Si and O at random general positions
(``seed=11``), Biso 0.8 Å², Cu Kα1+Kα2 Bragg-Brentano over 10-80° at 0.02°,
20 000 net counts at the strongest line on a Chebyshev background of about 200
counts, Poisson noise, and the true background declared (the sweep's
``clean+bkg`` arm at ×1.0).

On ``main`` before WP-2076 the screen read every fit it compares as a Le Bail
partition, which is not a χ² minimum, so a class could fit **better** than the
absence-free reference that contains it.  It then named ``P 63 - -``,
``P 63 - -``, ``P 41 - -``, ``P - 21 -`` and ``F 41 - -`` on these five.  The
screen now fits Pawley and scores each class on the lattice less only its
testable forbidden lines.  The acceptance is the WP's: a class containing the
true group, or ``None`` with ``EXTINCTION_SYMBOL_AMBIGUOUS`` naming where the
leading classes differ — never a class that excludes it.
"""

from __future__ import annotations

from pathlib import Path

import gemmi
import numpy as np
import pytest

from rietx.indexing.extinction import determine_extinction_symbol

pytestmark = pytest.mark.xdist_group("extinction-nesting")

OUT = Path(__file__).parent / "output"
LIMITS = (10.0, 80.0)
PEAK_COUNTS = 20000.0
BKG = (200.0, -40.0, 15.0)
PROFILE = dict(u=0.006, v=-0.004, w=0.003, x=0.03, y=0.005)
SPECIES = ("Ca", "Si", "O")
#: group → (crystal system of the candidate, the cell)
GROUPS = {
    "P 63/m m c": ("hexagonal", (6.9, 6.9, 7.6, 90.0, 90.0, 120.0)),
    "P 6/m c c": ("hexagonal", (6.9, 6.9, 7.6, 90.0, 90.0, 120.0)),
    "P n -3 n:2": ("cubic", (8.3, 8.3, 8.3, 90.0, 90.0, 90.0)),
    "P 4/n m m:2": ("tetragonal", (5.4, 5.4, 9.8, 90.0, 90.0, 90.0)),
    "F m -3 m": ("cubic", (8.3, 8.3, 8.3, 90.0, 90.0, 90.0)),
}


def _structure(group, cell, seed, scale=1.0):
    from rietx.schemas.structure import Atom, Cell, Parameter, Phase, Structure

    rng = np.random.default_rng(seed)
    a, b, c, alpha, beta, gamma = cell
    atoms = [Atom(label=f"{sp}{i}", species=sp,
                  x=Parameter(value=float(rng.uniform(0.05, 0.45))),
                  y=Parameter(value=float(rng.uniform(0.05, 0.45))),
                  z=Parameter(value=float(rng.uniform(0.05, 0.45))),
                  biso=Parameter(value=0.8))
             for i, sp in enumerate(SPECIES)]
    return Structure(phases=[Phase(
        name="synthetic", space_group=group,
        cell=Cell(a=Parameter(value=a, min=0.1), b=Parameter(value=b, min=0.1),
                  c=Parameter(value=c, min=0.1), alpha=Parameter(value=alpha),
                  beta=Parameter(value=beta), gamma=Parameter(value=gamma)),
        scale=Parameter(value=scale, min=0.0), atoms=atoms)])


def _instrument(background=BKG):
    from rietx.schemas.instrument import BackgroundChebyshev, Instrument
    from rietx.schemas.structure import Parameter

    ins = Instrument.bragg_brentano()
    for name, value in PROFILE.items():
        getattr(ins.profile, name).value = value
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in background])
    return ins


def _evaluate(structure, instrument, tt):
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    return np.asarray(model.evaluate(table.decode(table.x0()))), np.asarray(model.tt)


def _pattern(group, cell, seed=11):
    from rietx.schemas.pattern import PatternData

    tt = np.arange(LIMITS[0], LIMITS[1] + 1e-9, 0.02)
    net, _ = _evaluate(_structure(group, cell, seed), _instrument((0.0, 0.0, 0.0)), tt)
    scale = PEAK_COUNTS / float(net.max())
    y, tt = _evaluate(_structure(group, cell, seed, scale=scale), _instrument(), tt)
    y = np.random.default_rng(seed + 7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist())


def _screen(group):
    """The default screen on one specimen, keeping each class's own fit."""
    from rietx.indexing import extinction
    from rietx.indexing.fom import lattice_group
    from rietx.schemas.indexing import CellCandidate

    system, cell = GROUPS[group]
    centring = gemmi.find_spacegroup_by_name(group).centring_type()
    fits = {}
    real = extinction._fit_class

    def keep(candidate, data, instrument, symbol, two_theta_limits, omit=None):
        if omit is not None:            # a scoring refit, not a class's own fit
            return real(candidate, data, instrument, symbol, two_theta_limits,
                        omit=omit)
        ref, result = real(candidate, data, instrument, symbol, two_theta_limits)
        fits[symbol] = result
        return ref, result

    candidate = CellCandidate(cell=cell, cell_esd=(1e-4,) * 6, system=system,
                              centring=centring,
                              lattice_group=lattice_group(system, centring),
                              volume=float(np.prod(cell[:3])))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(extinction, "_fit_class", keep)
        screen = determine_extinction_symbol(_pattern(group, cell), candidate,
                                             _instrument(), two_theta_limits=LIMITS)
    _draw(group, screen, fits)
    return screen


@pytest.fixture(scope="module")
def screens():
    """Each specimen's screen, computed once for both tests (one xdist group)."""
    cache = {}

    def get(group):
        if group not in cache:
            cache[group] = _screen(group)
        return cache[group]
    return get


def _draw(group, screen, fits):
    """obs/calc/diff of the true class's own fit, and of the answer's when it differs."""
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    true = gemmi.find_spacegroup_by_name(group).xhm()
    best = screen.best_or_none()
    stem = "extinction_nesting_" + group.replace(" ", "").replace("/", "_").replace(":", "_")
    answer = "nothing" if best is None else best.symbol
    for cls in screen.candidates:
        if true in cls.space_groups or (best is not None and cls is best):
            result = fits.get(cls.representative)
            if result is None:
                continue
            which = "true" if true in cls.space_groups else "answer"
            plot_result(result, path=str(OUT / f"{stem}_{which}.png"),
                        title=(f"{group}: {which} class {cls.symbol} "
                               f"(ΔBIC {cls.delta_bic:+.1f}"
                               f"{', refuted' if cls.refuted else ''}); "
                               f"the screen returns {answer}"))


@pytest.mark.parametrize("group", list(GROUPS))
def test_the_screen_never_names_a_class_excluding_the_true_group(group, screens):
    screen = screens(group)
    true = gemmi.find_spacegroup_by_name(group).xhm()
    said = [(k.symbol, round(k.delta_bic, 1), k.n_testable, k.refuted_reason)
            for k in screen.candidates[:4]]
    best = screen.best_or_none()
    if best is None:
        ambiguous = [d for d in screen.diagnostics
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS"]
        assert ambiguous and "tested position" in ambiguous[0].message, (
            said, [str(d) for d in screen.diagnostics])
    else:
        assert true in best.space_groups, said


@pytest.mark.parametrize("group", list(GROUPS))
def test_no_class_fits_better_than_the_lattice_that_contains_it(group, screens):
    """The nesting itself: a class's score is a fit of a subset of the
    reference's reflections, so its χ² cannot fall below the reference's beyond
    the solver's stopping tolerance.  On ``main`` before WP-2076 2410 of 14 788
    class fits did, over WP-2076's 1230-row sweep."""
    screen = screens(group)
    below = [(k.symbol, k.chi2, screen.reference_chi2) for k in screen.candidates
             if k.screened and k.chi2 < screen.reference_chi2 * (1.0 - 1e-6)]
    assert not below, below


# ----------------------------------------------------------------------
# the margin as ruled 2026-11-13: max(DECISIVE_DELTA_BIC, 2·ln N + d), strict
# ----------------------------------------------------------------------
def _margin_screen(n_points, lead, top_tested, runner_tested=()):
    """Two unrefuted classes, ``top`` ahead of ``runner`` by ``lead`` in ΔBIC,
    each with its tested forbidden positions (2θ, hkl)."""
    from rietx.schemas.indexing import ExtinctionCandidate, ExtinctionScreen

    def cand(symbol, group, delta_bic, tested):
        return ExtinctionCandidate(
            symbol=symbol, representative=group, space_groups=[group],
            n_absent=len(tested), n_testable=len(tested), screened=True,
            delta_bic=delta_bic, tested_two_theta=[t for t, _ in tested],
            tested_hkl=[h for _, h in tested])

    top = cand("P - 21 -", "P 1 21 1", -lead, top_tested)
    runner = cand("P - - -", "P 1 2 1", 0.0, runner_tested)
    return ExtinctionScreen(candidates=[top, runner], system="monoclinic",
                            n_points=n_points)


SILENT = [(20.123, (0, 1, 0)), (40.456, (0, 3, 0))]


def test_a_lead_of_exactly_two_silent_positions_plus_d_abstains():
    """P 4/m b m's ``P - 21 -`` rows in WP-2076's sweep won by exactly 2·ln N,
    their two 0k0 intensities on the Pawley bound of zero: the bar is strictly
    exceeded or the screen abstains.  Positive arm: the same screen a hair
    above the bar names the class."""
    import math

    from rietx.indexing.diagnostics import extinction_diagnostics

    n = 3501
    need = 2 * math.log(n) + 2                     # d = 2: the top's two positions
    at_bar = _margin_screen(n, need, SILENT)
    assert at_bar.best_or_none() is None
    ambiguous = next(d for d in extinction_diagnostics(at_bar)
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert (f"decisive is {need:.1f}, 2·ln N + d with N = {n} points and d = 2"
            in ambiguous.message), ambiguous.message
    assert "(0, 1, 0) at 20.123°" in ambiguous.message, ambiguous.message

    above = _margin_screen(n, need * (1 + 1e-9), SILENT)
    assert above.best_or_none() is above.candidates[0]
    assert not [d for d in extinction_diagnostics(above)
                if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS"]


def test_the_margin_scales_with_n_where_a_fixed_bar_would_slip():
    """At N = 40 001 two silent positions buy 21.2, so a lead of 19.7 on three
    differing positions (11-BM Si 640c's in WP-2076's table) abstains where the
    margin of 10 named it; at a small N the floor is DECISIVE_DELTA_BIC, also
    strictly exceeded."""
    from rietx.indexing.extinction import DECISIVE_DELTA_BIC

    three = SILENT + [(60.789, (0, 5, 0))]
    assert _margin_screen(40_001, 19.7, three).best_or_none() is None
    assert _margin_screen(40_001, 24.3, three).best_or_none() is not None
    assert _margin_screen(50, DECISIVE_DELTA_BIC, []).best_or_none() is None
    assert _margin_screen(50, DECISIVE_DELTA_BIC + 1e-9, []).best_or_none() is not None


def test_d_counts_positions_at_a_thousandth_of_a_degree_on_both_sides():
    """d is read off ``tested_two_theta`` at 1e-3°, because two classes can
    name different hkl at one position; a position both test is no part of
    it, and one only the runner-up tests is."""
    from rietx.indexing.extinction import _decisive_margin, _differing_positions

    screen = _margin_screen(3501, 0.0, SILENT + [(70.0001, (1, 0, 0))],
                            [(70.0003, (0, 0, 1)), (75.5, (0, 0, 3))])
    top, runner = screen.candidates
    assert _differing_positions(top, runner) == [
        (20.123, (0, 1, 0)), (40.456, (0, 3, 0)), (75.5, (0, 0, 3))]
    assert _decisive_margin(3501, top, runner)[1] == 3

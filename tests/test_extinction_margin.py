"""The extinction screen's cell margin, per pattern (WP-1910 task 1, #726).

``determine_extinction_symbol`` holds the cell it is handed (``refine_cell=False``)
or Le Bail-refines it first in a cell-free prefit (the default since #939).  Either
way the answer depends on how far the handed cell is from the specimen's, and the
WP asks for that margin per pattern rather than as one number.  Each row below
scales every axis of the suite's own fixture (``tests/test_extinction_symbol.py``)
by a factor: SRM 676a corundum (R -3 c, IUCr CPD round robin), GSAS-II's FAP
tutorial pattern (P 6₃/m) and the synthetic P 2₁/c.

Measured on ``main`` 8658fa26 with a scan of 24 factors over ×0.97-1.03 for the
default and 20 over ×0.997-1.003 for the held cell, identical on macOS arm64 and
Linux x86_64 at every factor re-run on both:

======================  ====================  =================================
pattern                 held cell             default (cell-free prefit)
======================  ====================  =================================
corundum, ``R - c -``   ×0.998 to ×1.0004     ×0.9975 to ×1.015, and ×0.99-0.9925
FAP, ``P 63 - -``       ×0.9996 to ×1.001     ×1.000 to ×1.005, and ×0.9925-0.995
P 2₁/c, ``P 1 21/c 1``  ×0.9998 to ×1.0002    ×0.9995 to ×1.001
======================  ====================  =================================

Outside those ranges the screen mostly abstains (``EXTINCTION_SCREEN_UNRELIABLE``
past about ±2 %, or the prefit fails).  But at some offsets the prefit's screen
names a **wrong class** (eight of the 72 default rows): what crosses from the
prefit besides the cell (its widths, zero and seeded background) refutes the
true class.  Carrying the cell alone is no cure, because PbSO₄'s X-ray histogram
needs the prefit's seeded background to get ``P c - n`` at all
(``test_extinction_gate.py``).  So, as ruled on #1178 (2026-10-26), a second
screen at the prefit's cell, held, from the declared instrument checks every
class the default names, and two different classes make the screen name neither
(``EXTINCTION_SCREENS_DISAGREE``).  Re-measured on ``main`` 3defa3b6 plus this
check (pearl, ``ws_jobs/m1910i1``): it catches six of the eight (``CAUGHT``) and
fires on none of the 51 rows where the default is right
(these three patterns, PbSO₄ X-ray and 11-BM NAC, 121 rows).  The other two are
strict ``xfail`` rows: the prefit's own cell is off there (corundum ×0.985 lands
1611 ppm short, the monoclinic ×0.9975 586 ppm on a), and both screens name the
same wrong class.

Measured beside it and not built: (b), the prefit's cell held with the prefit's
fitted background carried and the widths and zero re-fitted from the declared
instrument.  It returns the true class on three of the six caught rows, keeps
the wrong ``P 1 - 1`` on the other three, and names ``P c - -`` on PbSO₄ X-ray at
×0.975 where the default abstains.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rietx.indexing.extinction import determine_extinction_symbol

# One module, one group: the three patterns' inputs are module fixtures shared by
# every row (tests/CLAUDE.md § Shared fixtures).
pytestmark = pytest.mark.xdist_group("extinction-margin")

OUT = Path(__file__).parent / "output"

#: pattern → (one space group of the true class, the class's symbol)
TRUE = {"corundum": ("R -3 c:H", "R - c -"),
        "fap": ("P 63/m", "P 63 - -"),
        "mono": ("P 1 21/c 1", "P 1 21/c 1")}


@pytest.fixture(scope="module")
def patterns():
    """(data, candidate builder, instrument, 2θ limits) per pattern, each the
    fixture of ``test_extinction_symbol.py`` verbatim."""
    from tests import test_extinction_symbol as T

    data, cand, ins = T.corundum_inputs.__wrapped__()
    out = {"corundum": (data, T.CORUNDUM_CELL, "trigonal", "R", ins, T.CORUNDUM_RANGE)}
    if not (T.DATA / "FAP.XRA").exists():
        pytest.skip("GSAS-II LabData tutorial dataset not present")
    data, cand, ins = T._fap_inputs()
    out["fap"] = (data, tuple(cand.cell), "hexagonal", "P", ins, (15.0, 90.0))
    structure, ins = T._mono_models()
    out["mono"] = (T._pattern(structure, ins), T.MONO_CELL, "monoclinic", "P", ins,
                   T.MONO_RANGE)
    return out


def _screen(patterns, name, factor, monkeypatch=None, **kw):
    """The screen at the cell scaled by ``factor``; with ``monkeypatch``, every
    class fit the screen makes is kept so the picture is the screen's own."""
    from rietx.indexing import extinction
    from tests.test_extinction_symbol import _candidate

    data, cell, system, centring, ins, limits = patterns[name]
    fits: dict[str, object] = {}
    if monkeypatch is not None:
        real = extinction._fit_class

        def keep(candidate, data, instrument, symbol, two_theta_limits):
            ref, result = real(candidate, data, instrument, symbol, two_theta_limits)
            fits[symbol] = result
            return ref, result

        monkeypatch.setattr(extinction, "_fit_class", keep)
    scaled = tuple(v * factor for v in cell[:3]) + tuple(cell[3:])
    screen = determine_extinction_symbol(data, _candidate(scaled, system, centring),
                                         ins, two_theta_limits=limits, **kw)
    return screen, fits


def _true_class(screen, name):
    group = TRUE[name][0]
    return next((k for k in screen.candidates if group in k.space_groups), None)


def _draw(name, factor, mode, screen, fits):
    """obs/calc/diff of the true class's own screen fit, whole range and, when
    the class was refuted, zoomed on the position that refuted it."""
    from rietx.viz.plots import plot_result

    true = _true_class(screen, name)
    result = None if true is None else fits.get(true.representative)
    if result is None:
        return
    OUT.mkdir(exist_ok=True)
    stem = f"extinction_margin_{name}_{mode}_x{factor:.4f}"
    best = screen.best_or_none()
    title = (f"{name} ×{factor:.4f} ({mode}): true class {true.symbol}"
             f"{' refuted' if true.refuted else ''}; screen returns "
             f"{'nothing' if best is None else best.symbol}")
    plot_result(result, path=str(OUT / f"{stem}.png"), title=title)
    if true.refuted and true.forbidden_two_theta:
        tt = float(true.forbidden_two_theta[0])
        plot_result(result, path=str(OUT / f"{stem}_refuting.png"),
                    two_theta_range=(tt - 2.0, tt + 2.0),
                    title=f"{title}; first refuting position {tt:.3f}°")


def _says(screen):
    return (screen.status, [(k.symbol, round(k.delta_bic, 1), k.refuted_reason)
                            for k in screen.candidates[:3]])


# ----------------------------------------------------------------------
# the held cell: the margin is a few hundred ppm, and it is not symmetric
# ----------------------------------------------------------------------
@pytest.mark.parametrize("name,factor", [
    ("corundum", 0.998), ("corundum", 1.0004),
    ("fap", 0.9996), ("fap", 1.001),
    ("mono", 0.9998), ("mono", 1.0002),
])
def test_a_held_cell_inside_its_patterns_margin_returns_the_true_class(
        patterns, name, factor):
    screen, _ = _screen(patterns, name, factor, refine_cell=False)
    best = screen.best_or_none()
    assert best is not None and TRUE[name][0] in best.space_groups, _says(screen)


@pytest.mark.parametrize("name,factor", [
    ("corundum", 0.9975), ("corundum", 1.0006),
    ("fap", 0.9994), ("fap", 1.0012),
    ("mono", 0.9996), ("mono", 1.0004),
])
def test_a_held_cell_one_step_outside_its_margin_does_not(patterns, name, factor):
    """One scan step past each edge.  Corundum's +0.06 % is the row WP-1910 was
    opened on.  Past FAP's edges the gate abstains; past corundum's and the
    monoclinic's a subgroup's class comes back instead."""
    screen, _ = _screen(patterns, name, factor, refine_cell=False)
    best = screen.best_or_none()
    assert best is None or TRUE[name][0] not in best.space_groups, _says(screen)


# ----------------------------------------------------------------------
# the default prefit: wider on the lab patterns, barely on the monoclinic
# ----------------------------------------------------------------------
@pytest.mark.parametrize("name,factor", [
    ("corundum", 0.9975), ("corundum", 1.0), ("corundum", 1.015),
    ("fap", 1.0), ("fap", 1.005),
    ("mono", 0.9995), ("mono", 1.001),
])
def test_the_default_returns_the_true_class_across_its_patterns_margin(
        patterns, name, factor, monkeypatch):
    screen, fits = _screen(patterns, name, factor, monkeypatch)
    _draw(name, factor, "default", screen, fits)
    best = screen.best_or_none()
    assert best is not None and TRUE[name][0] in best.space_groups, _says(screen)
    # the silent side of the second screen: it ran, and nothing fired
    assert screen.held_screen is not None and not screen.screens_disagree()
    assert "EXTINCTION_SCREENS_DISAGREE" not in {d.code for d in screen.diagnostics}


#: the default's confident misses the held second screen catches: the prefit
#: lands within 400 ppm, and the same cell held, from the declared instrument,
#: names the true class (WP-1910, ruled on #1178)
CAUGHT = [("corundum", 0.995), ("fap", 1.0075), ("mono", 0.998), ("mono", 0.999),
          ("mono", 1.002), ("mono", 1.0025)]


@pytest.mark.parametrize("name,factor", CAUGHT)
def test_the_default_never_returns_a_wrong_class_confidently(
        patterns, name, factor, monkeypatch):
    """The open half of WP-1910's acceptance: return the class, or abstain with
    a finding.  After the prefit ``R - - -``, ``P - - -`` or ``P 1 - 1`` leads,
    refuting the true class on one to four forbidden positions; the second
    screen, at the prefit's cell held from the declared instrument, names the
    true class.  Two classes sharing no group cannot both be right, so the
    screen names neither and keeps both rankings."""
    screen, fits = _screen(patterns, name, factor, monkeypatch)
    _draw(name, factor, "default", screen, fits)
    assert screen.best_or_none() is None, _says(screen)
    assert screen.screens_disagree()
    own, held = screen._own_best(), screen.held_screen.best_or_none()
    assert TRUE[name][0] not in own.space_groups, _says(screen)
    assert TRUE[name][0] in held.space_groups, _says(screen.held_screen)
    assert tuple(screen.held_screen.cell) == tuple(screen.cell)
    found = [d for d in screen.diagnostics if d.code == "EXTINCTION_SCREENS_DISAGREE"]
    assert len(found) == 1 and own.symbol in found[0].message
    assert held.symbol in found[0].message


@pytest.mark.parametrize("name,factor", [("corundum", 0.985), ("mono", 0.9975)])
@pytest.mark.xfail(strict=True, reason=(
    "WP-1910: prefit cell off — the prefit lands 1611 ppm (corundum) and 586 ppm "
    "(mono, a) from the specimen's cell, and the held second screen at that cell "
    "names the same wrong class, so there is no disagreement to report (ruled on "
    "#1178, 2026-10-26)"))
def test_a_prefit_cell_that_is_off_is_not_caught(patterns, name, factor):
    """Both screens name one wrong class: ``R - - -`` at corundum ×0.985 and
    ``P 1 - 1`` at the monoclinic ×0.9975.  Pinned strict, so a fix shows as a
    pass."""
    screen, _ = _screen(patterns, name, factor)
    best = screen.best_or_none()
    assert best is None or TRUE[name][0] in best.space_groups, _says(screen)


def _zero_background(patterns, name):
    """``patterns`` with the instrument's background declared all-zero, the
    preset's own start and what the GUI hands the screen (round 1 of #1286)."""
    data, cell, system, centring, ins, limits = patterns[name]
    zero = ins.model_copy(deep=True)
    for c in zero.background.coefficients:
        c.value = 0.0
    return {name: (data, cell, system, centring, zero, limits)}


@pytest.mark.xfail(strict=True, reason=(
    "#1286 round 1: from the preset's all-zero declared background the held "
    "reference fit is poor and the class forbidding nothing wins by elimination, "
    "so the check fires needlessly (synthetic P 2_1/c at x1.0005 and x1.001). "
    "Seeding the held background removes it and fires on eleven right PbSO4 rows "
    "instead; a gate on the held fit's chi2 does not separate them (measured)"))
def test_a_held_screen_with_a_poor_reference_fit_does_not_veto_a_right_default(
        patterns):
    """Round 1 of #1286 (Yue's zero-background sweep), pinned as a known failure.
    From the all-zero declared background the held reference fit is poor and the
    class forbidding nothing wins it by elimination: here it names ``P 1 - 1`` at
    ×1.001 where the default names the true ``P 1 21/c 1``, and the screens
    disagree.  A pass here is a fix."""
    zero = _zero_background(patterns, "mono")
    screen, _ = _screen(zero, "mono", 1.001)
    held = screen.held_screen
    assert held is not None and held.best_or_none() is not None, _says(held)
    assert TRUE["mono"][0] not in held.best_or_none().space_groups
    assert held.reference_chi2 > screen.reference_chi2 + 10.0
    assert not screen.screens_disagree()
    best = screen.best_or_none()
    assert best is not None and TRUE["mono"][0] in best.space_groups, _says(screen)
    assert "EXTINCTION_SCREENS_DISAGREE" not in {d.code for d in screen.diagnostics}


def test_a_better_fitting_held_screen_still_flags_from_a_zero_background(patterns):
    """The positive arm: at ×0.999 the default names ``P 1 - 1`` and the held
    screen, whose reference fit is *better* than the default's, names another
    class from the same all-zero background, so the check still fires."""
    zero = _zero_background(patterns, "mono")
    screen, _ = _screen(zero, "mono", 0.999)
    assert screen.held_screen.reference_chi2 < screen.reference_chi2
    assert screen.screens_disagree() and screen.best_or_none() is None, _says(screen)


def test_a_held_cell_runs_no_second_screen(patterns):
    """``refine_cell=False`` has no prefit to check, so ``held_screen`` stays
    None and the answer is the held screen's own."""
    screen, _ = _screen(patterns, "corundum", 1.0, refine_cell=False)
    assert screen.held_screen is None and not screen.screens_disagree()
    assert screen.best_or_none() is not None

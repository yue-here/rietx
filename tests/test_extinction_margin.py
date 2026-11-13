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

Outside those ranges the screen mostly abstained (``EXTINCTION_SCREEN_UNRELIABLE``
past about ±2 %, or the prefit failed).  But at some offsets it returned a **wrong
class confidently** (eight of the 72 default rows), four of them pinned as strict
``xfail`` rows of WP-1910.

**WP-2076 moved every number above, and the table is kept as the Le Bail
screen's record.**  The screen's compared fits are Pawley now, and a class is
scored on the lattice less only its testable forbidden lines.  What that changed
here, re-measured 2026-11-07 on macOS arm64:

* The four confident misses return the true class or abstain, so they are plain
  rows below.
* The held margin widened.  Corundum returns ``R - c -`` at every held factor
  scanned, ×0.995 to ×1.002.  The monoclinic returns ``P 1 21/c 1`` from ×0.9996
  to at least ×1.0012, and at ×0.9994 ``P 1 21 1`` instead, its true class
  refuted.
* FAP abstains at every factor, held or not.  ``P 63 - -`` leads unrefuted on
  one testable position, (0 0 5) at 68.0°, and one position buys ΔBIC ln N = 8.2 at most,
  under the margin of 10.  Ruled by the maintainer on 2026-11-07 (WP-2076's
  handover log).

**The second screen (WP-1910, ruled on #1178).**  Before WP-2076 the default
named a wrong class at eight of the 72 rows, because what crosses from the prefit
besides the cell (its widths, zero and seeded background) refuted the true class.
A second screen at the prefit's cell, held, from the declared instrument checks
every class the default names, and two different classes make the screen name
neither (``EXTINCTION_SCREENS_DISAGREE``).  It caught six of the eight (corundum
×0.995, FAP ×1.0075, the monoclinic ×0.998, ×0.999, ×1.002 and ×1.0025) and fired
on none where the default was right; the other two (corundum ×0.985, the
monoclinic ×0.9975) have the prefit's own cell off, so both screens name one wrong
class.  From the preset's all-zero background the held screen seeds its own, as the
prefit does (#1286 round 2).  That cost PbSO₄'s X-ray histogram eleven of the
twelve right rows the default had (×0.999 to ×1.015, measured by hand; the strict
``xfail`` at ×1.0 alone ran in the suite).

**WP-2076 left the second screen nothing to catch on these three patterns.**
Re-measured 2026-11-08 on ``main`` 1d054085 (macOS arm64): at 25 factors over
×0.97-1.03 per pattern, with the true and with the all-zero declared background
(150 rows), the screens disagree on none.  The six rows above now return the true
class or abstain, except the monoclinic ×0.998, which both screens read ``P 1 21 1``
(a wrong class they agree on, like ×0.9975 and ×0.995).  On PbSO₄ X-ray the default
names ``P c - a`` at 13 of 14 scales (×0.99-1.015; nothing at ×1.0125) and the held
screen names ``P c - a`` or nothing, so the eleven withheld rows are gone with the right answers
that made them a cost.  The rows below pin that state, and one built split pins the
check's own behaviour.
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

        def keep(candidate, data, instrument, symbol, two_theta_limits, omit=None):
            ref, result = real(candidate, data, instrument, symbol, two_theta_limits,
                               omit=omit)
            if omit is None:        # a class's own fit, never a scoring refit
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
    ("corundum", 0.995), ("corundum", 1.002),
    ("mono", 0.9996), ("mono", 1.0012),
])
def test_a_held_cell_inside_its_patterns_margin_returns_the_true_class(
        patterns, name, factor):
    screen, _ = _screen(patterns, name, factor, refine_cell=False)
    best = screen.best_or_none()
    assert best is not None and TRUE[name][0] in best.space_groups, _says(screen)


@pytest.mark.parametrize("name,factor", [("mono", 0.9994)])
def test_a_held_cell_one_step_outside_its_margin_does_not(patterns, name, factor):
    """One scan step past the monoclinic's low edge, where ``P 1 21 1`` comes
    back.  Corundum's edges lie outside the held scan since WP-2076, and its
    +0.06 % row, the one WP-1910 was opened on, now returns ``R - c -``."""
    screen, _ = _screen(patterns, name, factor, refine_cell=False)
    best = screen.best_or_none()
    assert best is None or TRUE[name][0] not in best.space_groups, _says(screen)


# ----------------------------------------------------------------------
# the default prefit: wider on the lab patterns, barely on the monoclinic
# ----------------------------------------------------------------------
@pytest.mark.parametrize("name,factor", [
    ("corundum", 0.9975), ("corundum", 1.0), ("corundum", 1.015),
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


#: the rows WP-1910's second screen was built for.  Before WP-2076 the default
#: named a wrong class at each (the prefit landed within 400 ppm, and the same
#: cell held, from the declared instrument, named the true one: the two
#: disagreed, six of the eight confident misses).  WP-2076's nested comparison
#: moved the default off every one of them
CAUGHT = [("corundum", 0.995), ("fap", 1.0075), ("mono", 0.998), ("mono", 0.999),
          ("mono", 1.002), ("mono", 1.0025)]


@pytest.mark.parametrize("name,factor", CAUGHT)
def test_the_second_screen_has_nothing_left_to_catch_on_its_six_rows(
        patterns, name, factor, monkeypatch):
    """Re-measured 2026-11-08 on ``main`` 1d054085 (macOS arm64): the six rows
    WP-1910's second screen caught before WP-2076 no longer split the two
    screens.  The held screen runs and names what the default names (or both
    name nothing), so ``best_or_none()`` is the default's own answer and no
    ``EXTINCTION_SCREENS_DISAGREE`` is raised.  Pinned so that a change which
    makes the second screen veto a right answer shows here."""
    screen, fits = _screen(patterns, name, factor, monkeypatch)
    _draw(name, factor, "default", screen, fits)
    own = screen._own_best()
    # the held screen runs only when the first names a class (FAP abstains here)
    assert (screen.held_screen is not None) == (own is not None)
    assert not screen.screens_disagree(), _says(screen)
    assert screen.best_or_none() is own
    assert "EXTINCTION_SCREENS_DISAGREE" not in {d.code for d in screen.diagnostics}


def test_two_screens_that_name_disjoint_classes_abstain_and_say_so(patterns):
    """The positive arm.  No fixture splits the two screens since WP-2076, so the
    split is built: corundum's screen (``R - c -``) gets the monoclinic's
    (``P 1 21/c 1``) as its held screen, two classes that share no group.
    ``best_or_none`` then names neither, the diagnostic names both with a
    suggestion, and the two notes that describe the default's class and say to
    pass its groups on (``EXTINCTION_GROUPS_NOT_SEPARABLE``,
    ``LAUE_CLASS_NOT_SEPARABLE``) are silent.  Without a held screen both are
    present: the silence is the disagreement's."""
    from rietx.indexing.diagnostics import extinction_diagnostics

    corundum, _ = _screen(patterns, "corundum", 1.0)
    mono, _ = _screen(patterns, "mono", 1.0)
    own, theirs = corundum._own_best(), mono._own_best()
    assert own.symbol == "R - c -" and theirs.symbol == "P 1 21/c 1"

    def codes(screen):
        return {d.code: d for d in extinction_diagnostics(screen, {})}

    corundum.held_screen = None
    alone = codes(corundum)
    assert "EXTINCTION_GROUPS_NOT_SEPARABLE" in alone      # the arm that can fail
    assert "EXTINCTION_SCREENS_DISAGREE" not in alone

    corundum.held_screen = mono
    assert corundum.screens_disagree() and corundum.best_or_none() is None
    split = codes(corundum)
    found = split["EXTINCTION_SCREENS_DISAGREE"]
    assert own.symbol in found.message and theirs.symbol in found.message
    assert "(an all-zero background seeded first)" in found.message
    assert found.suggestion and "refuted_reason" in found.suggestion
    assert [w.split(":")[0] for w in found.where] == [
        "after the cell-free fit", "held second screen"]
    assert "EXTINCTION_GROUPS_NOT_SEPARABLE" not in split
    assert "LAUE_CLASS_NOT_SEPARABLE" not in split


@pytest.mark.xfail(strict=True, reason=(
    "WP-1910: prefit cell off — the prefit lands 586 ppm from the specimen's a "
    "and the held second screen at that cell names the same wrong class, "
    "`P 1 21 1`, so there is no disagreement to report (ruled on #1178, "
    "2026-10-26)"))
def test_a_prefit_cell_that_is_off_is_not_caught(patterns):
    """Both screens name one wrong class, ``P 1 21 1`` at the monoclinic ×0.9975
    (``P 1 - 1`` before WP-2076).  Pinned strict, so a fix shows as a pass.
    Corundum ×0.985, the other row of this test before WP-2076, now returns
    ``R - c -``."""
    screen, _ = _screen(patterns, "mono", 0.9975)
    best = screen.best_or_none()
    assert best is None or TRUE["mono"][0] in best.space_groups, _says(screen)


def _zero_background(patterns, name):
    """``patterns`` with the instrument's background declared all-zero, the
    preset's own start and what the GUI hands the screen (round 1 of #1286)."""
    data, cell, system, centring, ins, limits = patterns[name]
    zero = ins.model_copy(deep=True)
    for c in zero.background.coefficients:
        c.value = 0.0
    return {name: (data, cell, system, centring, zero, limits)}


def test_a_held_screen_from_a_zero_background_does_not_veto_a_right_default(
        patterns):
    """Round 1 of #1286 (Yue's zero-background sweep): from the all-zero declared
    background the unseeded held reference fit was poor and the class forbidding
    nothing won it by elimination (``P 1 - 1`` at ×1.001), so the check fired
    needlessly.  The held screen's background is seeded as the prefit's is
    (round 2), and the outcome is what counts: the screens agree and
    ``best_or_none`` names the true class.  This row cannot show the seed since
    WP-2076: the nested comparison moved the base screen, and re-measured
    2026-11-08 the held reference fit from the all-zero background reads
    chi2 2851.95 seeded against 2853.40 unseeded here (2865.81 from the true
    background), a 0.05 % difference.  Round 2's sweep tables, which show the seed, predate WP-2076."""
    zero = _zero_background(patterns, "mono")
    screen, _ = _screen(zero, "mono", 1.001)
    assert not screen.screens_disagree()
    best = screen.best_or_none()
    assert best is not None and TRUE["mono"][0] in best.space_groups, _says(screen)
    assert "EXTINCTION_SCREENS_DISAGREE" not in {d.code for d in screen.diagnostics}


def test_a_held_cell_runs_no_second_screen(patterns):
    """``refine_cell=False`` has no prefit to check, so ``held_screen`` stays
    None and the answer is the held screen's own."""
    screen, _ = _screen(patterns, "corundum", 1.0, refine_cell=False)
    assert screen.held_screen is None and not screen.screens_disagree()
    assert screen.best_or_none() is not None


@pytest.mark.parametrize("held,factor", [
    (True, 0.9996), (True, 1.001), (False, 1.0), (False, 1.005), (False, 1.0075),
])
def test_fap_abstains_on_its_one_testable_position(patterns, held, factor):
    """FAP's class forbids one line the data can test, so it cannot reach the
    margin: ``P 63 - -`` leads unrefuted, ``best_or_none`` abstains, and the
    finding names (0 0 5).  The known cost of the nested comparison, ruled by
    the maintainer on 2026-11-07 (WP-2076)."""
    screen, _ = _screen(patterns, "fap", factor,
                        **({"refine_cell": False} if held else {}))
    assert screen.best_or_none() is None, _says(screen)
    top = screen.candidates[0]
    assert top.symbol == TRUE["fap"][1] and not top.refuted, _says(screen)
    assert top.n_testable == 1
    ambiguous = next(d for d in screen.diagnostics
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert "(0, 0, 5)" in ambiguous.message, ambiguous.message

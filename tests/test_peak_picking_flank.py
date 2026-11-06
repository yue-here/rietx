"""``pick_peaks`` on a background the envelope cannot follow: lines that are not there.

Forward-modelled silicon (Cu Kα1 + Kα2, pseudo-Voigt lines, Poisson noise,
numpy and gemmi's IT92 form factors only, no measured data) on two backgrounds.
Silicon has no reflection below 28.4° 2θ, so any usable "line" below 28° is
false.  On the gentle background there is none.  On a sigmoid fall, 2300 → 800
counts over 11–22°, the 3° rolling-10th-percentile envelope under-tracks the
curvature, the net above it clears detection's 5σ, and the fit returns
components whose intensity is a third of their own esd.  They were offered to
every indexing engine as evidence of a lattice and ``index_pattern`` returned no
cubic cell, while the same pattern cropped above the flank returned the F cell.

The fix is in the flag, not the envelope: a component whose intensity is under
``PEAK_NO_INTENSITY_SIGMA`` of its own esd is ``no_intensity`` and unusable.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.indexing import PEAK_UNUSABLE_FLAGS
from tests import indexing_gallery as gallery
from tests._synthetic_silicon import A_SI, silicon_pattern

FIRST_SI_LINE = 28.0      # Si 111 is at 28.44°; nothing real lies below this


# the module fixtures ``flat`` and ``steep`` are shared by four tests: pin the module
pytestmark = pytest.mark.xdist_group("peak-picking-flank")

INSTRUMENT = rx.Instrument.bragg_brentano(radiation="CuKa")


@pytest.fixture(scope="module")
def flat():
    return silicon_pattern("flat")


@pytest.fixture(scope="module")
def steep():
    return silicon_pattern("steep")


def _false(peaks):
    return [p for p in peaks.usable() if p.two_theta < FIRST_SI_LINE]


def test_the_control_has_no_false_line(flat):
    peaks = rx.pick_peaks(flat, INSTRUMENT, two_theta_range=(10.0, 110.0))
    assert _false(peaks) == []
    assert len(peaks.usable()) >= 8


def test_a_steep_flank_gives_no_usable_false_line(steep):
    peaks = rx.pick_peaks(steep, INSTRUMENT, two_theta_range=(10.0, 110.0))
    # drawn before asserting, so a red run leaves its own picture rather than
    # the last green run's sidecar
    gallery.draw("silicon_steep_peaks", peaks=peaks, data=steep,
                 note="only usable lines are drawn, so the flank components "
                      "below 28\u00b0, all unusable, are absent from the ticks")
    assert _false(peaks) == [], [
        (round(p.two_theta, 2), round(p.intensity / p.intensity_esd, 2))
        for p in _false(peaks)]
    from rietx.schemas.indexing import PEAK_NO_INTENSITY_SIGMA

    # they are reported, not dropped: every flank component carries the flag a
    # zero-intensity component carries, it is in the unusable set, and each
    # one is under the floor of its own esd
    flank = [p for p in peaks.peaks if p.two_theta < FIRST_SI_LINE]
    assert flank and "no_intensity" in PEAK_UNUSABLE_FLAGS
    for p in flank:
        assert "no_intensity" in p.flags, (round(p.two_theta, 2), p.flags)
        assert p.intensity < PEAK_NO_INTENSITY_SIGMA * p.intensity_esd


#: Si Kα1 positions in 10–110° 2θ (hkl all odd or all even, and h+k+l ≠ 4n+2).
def _true_lines():
    out = []
    for hkl in ((1, 1, 1), (2, 2, 0), (3, 1, 1), (4, 0, 0), (3, 3, 1),
                (4, 2, 2), (5, 1, 1), (4, 4, 0), (5, 3, 1), (6, 2, 0)):
        d = A_SI / np.sqrt(sum(v * v for v in hkl))
        out.append(2 * np.degrees(np.arcsin(1.540598 / (2 * d))))
    return [t for t in out if t < 108.0]


@pytest.mark.parametrize("which", ["flat", "steep"])
def test_every_true_line_is_still_found_and_nothing_false_is_kept(
        which, flat, steep):
    """The negative arm: the floor takes no true silicon line from either
    pattern, and every usable component of either lies on a true Kα1 or Kα2
    position."""
    data = flat if which == "flat" else steep
    peaks = rx.pick_peaks(data, INSTRUMENT, two_theta_range=(10.0, 110.0))
    found = [p.two_theta for p in peaks.usable()]
    for t in _true_lines():
        assert min(abs(t - u) for u in found) < 0.05, (which, round(t, 3))
    ka2 = [t + 0.0 for t in _true_lines()]      # Kα2 sits a few 0.01° to 0.3° above
    for u in found:
        assert min(abs(u - t) for t in ka2) < 0.5, (which, round(u, 3))


def test_index_pattern_finds_the_cubic_cell_on_the_steep_flank(steep):
    peaks = rx.pick_peaks(steep, INSTRUMENT, two_theta_range=(10.0, 110.0))
    result = rx.index_pattern(peaks, data=steep, instrument=INSTRUMENT,
                              two_theta_limits=(10.0, 110.0), preset="quick")
    gallery.draw("silicon_steep", peaks=peaks, data=steep, result=result,
                 instrument=INSTRUMENT)
    # ranked first, as the issue's cropped run had it.  Eight usable lines
    # reduce the panel to cubic alone (INDEX_SYSTEMS_NOT_COVERED), whose units
    # finish in ~1 s of the quick preset's 120 s ceiling, so the order is not
    # a load sensor (tests/CLAUDE.md § Budgets in tests)
    best = result.candidates[0]
    assert (best.system, best.centring) == ("cubic", "F") and abs(
        best.cell[0] - A_SI) < 0.01, [
        (round(c.cell[0], 3), c.system, c.centring)
        for c in result.candidates[:5]]
